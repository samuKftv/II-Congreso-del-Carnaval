"""Cola del estudio: envía a ComfyUI un trabajo cada vez y guarda los resultados."""

from __future__ import annotations

import asyncio
import io
import logging
import random
import time
import uuid
from collections import deque
from dataclasses import dataclass

from PIL import Image, ImageOps

from . import workflow
from .comfy import ComfyNoDisponible, ComfyUI, Interrumpido
from .config import Ajustes, Estilo, Formato
from .db import BaseDatos

log = logging.getLogger("estudio")

ESPERA_INICIAL = 12.0  # segundos por imagen hasta medir los reales
REINTENTOS = 3


@dataclass
class Actual:
    id: str
    inicio: float
    valor: int = 0
    maximo: int = 0
    preview: bytes | None = None
    version: int = 0


class Estudio:
    def __init__(self, aj: Ajustes, db: BaseDatos, comfy: ComfyUI):
        self.aj, self.db, self.comfy = aj, db, comfy
        self.nodos = workflow.localizar(aj.workflow, aj.nodo_prompt, aj.nodo_tamano)
        self.avisos = workflow.avisos(aj.workflow, self.nodos)
        for carpeta in ("imagenes", "miniaturas", "estilos"):
            (aj.datos / carpeta).mkdir(parents=True, exist_ok=True)

        self.abierto = db.leer_estado("abierto", "1") == "1"
        self.comfy_info: dict | None = None
        self.duraciones = deque(reversed(db.duraciones_recientes()), maxlen=10)
        self.actual: Actual | None = None
        self.cola: list[str] = []
        self.duenos: dict[str, str] = {}
        for t in db.pendientes():  # trabajos que quedaron a medias al cerrar la app
            db.actualizar(t["id"], estado="cola", inicio=None)
            self.cola.append(t["id"])
            self.duenos[t["id"]] = t["token"]

        self._despertar = asyncio.Event()
        self._tarea: asyncio.Task | None = None
        self._cancelados: set[str] = set()
        self._intentos: dict[str, int] = {}

    # --- Consultas ---

    def abrir(self, abierto: bool):
        self.abierto = abierto
        self.db.guardar_estado("abierto", "1" if abierto else "0")

    def activos_de(self, token: str) -> list[str]:
        return [i for i in self.cola if self.duenos.get(i) == token]

    def media(self) -> float:
        return sum(self.duraciones) / len(self.duraciones) if self.duraciones else ESPERA_INICIAL

    def espera(self, id_: str) -> tuple[int, float] | None:
        """(personas delante, segundos estimados) o None si ya no está en la cola."""
        if id_ not in self.cola:
            return None
        delante = self.cola.index(id_)
        media = self.media()
        restante = media
        if self.actual:
            restante = max(media - (time.time() - self.actual.inicio), 1.0)
        return delante, restante if delante == 0 else restante + delante * media

    # --- Acciones ---

    def encolar(self, token: str, alias: str, prompt: str, estilo: Estilo, formato: Formato,
                miniatura_estilo: str | None = None) -> str:
        id_ = uuid.uuid4().hex
        self.db.crear_trabajo({
            "id": id_, "token": token, "alias": alias, "prompt": prompt,
            "estilo": estilo.id, "formato": formato.id, "prompt_final": estilo.aplicar(prompt),
            "semilla": random.randint(1, 2**50), "estado": "cola", "creado": time.time(),
            "miniatura_estilo": miniatura_estilo,
        })
        self.cola.append(id_)
        self.duenos[id_] = token
        self._despertar.set()
        return id_

    async def cancelar(self, id_: str) -> bool:
        if id_ not in self.cola:
            return False
        if self.actual and self.actual.id == id_ and self._tarea:
            self._cancelados.add(id_)
            await self.comfy.interrumpir(self.comfy.prompt_actual)
            self._tarea.cancel()
        else:
            self.cola.remove(id_)
            self.duenos.pop(id_, None)
            self.db.actualizar(id_, estado="cancelado", fin=time.time())
        return True

    # --- Bucles en segundo plano ---

    async def vigilar_comfy(self):
        while True:
            self.comfy_info = await self.comfy.estado()
            await asyncio.sleep(5)

    async def bucle(self):
        while True:
            if not self.cola:
                self._despertar.clear()
                await self._despertar.wait()
                continue
            id_ = self.cola[0]
            t = self.db.trabajo(id_)
            if t is None:
                self._sacar(id_)
                continue
            if await self.comfy.estado() is None:
                self.comfy_info = None
                await asyncio.sleep(3)
                continue
            await self._generar(t)

    async def _generar(self, t: dict):
        id_, inicio = t["id"], time.time()
        self.actual = Actual(id_, inicio)
        self.db.actualizar(id_, estado="generando", inicio=inicio)
        try:
            formato = self.aj.formatos.get(t["formato"]) or next(iter(self.aj.formatos.values()))
            wf = workflow.preparar(self.aj.workflow, self.nodos, t["prompt_final"], formato.ancho, formato.alto,
                                   t["semilla"], "congreso_carnaval/estudio")
            self._tarea = asyncio.create_task(
                self.comfy.generar(wf, self._progreso, self._preview, self.aj.tiempo_maximo))
            imagenes = await self._tarea
            await asyncio.to_thread(self._guardar, id_, imagenes[0], t["miniatura_estilo"])
            fin = time.time()
            self.db.actualizar(id_, estado="hecho", fin=fin)
            self.duraciones.append(fin - inicio)
            log.info("Imagen de %s lista en %.1f s", t["alias"], fin - inicio)
        except asyncio.CancelledError:
            if id_ not in self._cancelados:
                raise
            self.db.actualizar(id_, estado="cancelado", fin=time.time())
        except Interrumpido:
            self.db.actualizar(id_, estado="cancelado", fin=time.time())
        except ComfyNoDisponible as e:
            self._intentos[id_] = self._intentos.get(id_, 0) + 1
            if self._intentos[id_] < REINTENTOS:
                log.warning("ComfyUI no disponible (%s). Reintentando.", e)
                self.db.actualizar(id_, estado="cola", inicio=None)
                self.actual = self._tarea = None
                await asyncio.sleep(3)
                return
            self.db.actualizar(id_, estado="error", error=str(e), fin=time.time())
        except Exception as e:
            log.exception("Error generando %s", id_)
            self.db.actualizar(id_, estado="error", error=str(e) or e.__class__.__name__, fin=time.time())
        self.actual = self._tarea = None
        self._cancelados.discard(id_)
        self._intentos.pop(id_, None)
        self._sacar(id_)

    def _sacar(self, id_: str):
        if id_ in self.cola:
            self.cola.remove(id_)
        self.duenos.pop(id_, None)

    def _progreso(self, valor: int, maximo: int):
        if self.actual:
            self.actual.valor, self.actual.maximo = valor, maximo

    def _preview(self, imagen: bytes):
        if self.actual:
            self.actual.preview = imagen
            self.actual.version += 1

    def _guardar(self, id_: str, datos: bytes, miniatura_estilo: str | None):
        carpeta = self.aj.datos
        with Image.open(io.BytesIO(datos)) as im:
            im.load()
            ruta = carpeta / "imagenes" / f"{id_}.png"
            if im.format == "PNG":
                ruta.write_bytes(datos)
            else:
                im.save(ruta, "PNG")
            rgb = im.convert("RGB")
        mini = rgb.copy()
        mini.thumbnail((512, 512))
        mini.save(carpeta / "miniaturas" / f"{id_}.webp", "WEBP", quality=82)
        if miniatura_estilo:
            ImageOps.fit(rgb, (320, 320)).save(carpeta / "estilos" / f"{miniatura_estilo}.webp", "WEBP", quality=85)
