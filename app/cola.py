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

from . import arquitectura, workflow
from .comfy import ComfyNoDisponible, ComfyUI, Interrumpido
from .config import Ajustes, Estilo, Formato
from .db import BaseDatos
from .interprete import Interprete

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


TESELA = 160  # lado de la pieza del mosaico: pequeña para que el proyector aguante cientos
VISTA = 1280  # lado máximo de la imagen que se ve en el móvil


def guardar_vista(imagen: Image.Image, ruta) -> None:
    """La imagen para ver en el móvil: WebP de unos 150 KB en vez del PNG de 1,5 MB (que sigue para descargar)."""
    vista = imagen.convert("RGB")
    vista.thumbnail((VISTA, VISTA))
    vista.save(ruta, "WEBP", quality=86, method=4)


def guardar_tesela(imagen: Image.Image, ruta) -> None:
    ImageOps.fit(imagen.convert("RGB"), (TESELA, TESELA)).save(ruta, "WEBP", quality=80)


class Estudio:
    def __init__(self, aj: Ajustes, db: BaseDatos, comfy: ComfyUI, interprete: Interprete | None = None):
        self.aj, self.db, self.comfy, self.interprete = aj, db, comfy, interprete
        wf = workflow.ajustar(workflow.con_mi_modelo(aj.workflow, aj.modelo, aj.lora, aj.fuerza_lora), aj.pasos, aj.cfg)
        self.workflow = workflow.aligerar(wf) if aj.ligero else wf
        self.nodos = workflow.localizar(wf, aj.nodo_prompt, aj.nodo_tamano)
        self.avisos = workflow.avisos(wf, self.nodos)
        self.faltan: list[str] = []  # nodos o archivos del workflow que ComfyUI no tiene, o familias que no encajan
        self.familias: dict = {"workflow": arquitectura.familia_workflow(wf)}
        self._comprobado = 0.0
        for carpeta in ("imagenes", "vistas", "miniaturas", "teselas", "estilos", "fotos"):
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
        self._hay_ideas = asyncio.Event()       # despierta al intérprete
        self._ia_en_curso: str | None = None     # trabajo que está interpretando ahora
        self._ia_decidida: set[str] = set()      # trabajos que ya no necesitan intérprete
        self._ia_media = 6.0                     # segundos que tarda en interpretar una idea

    # --- Consultas ---

    def abrir(self, abierto: bool):
        self.abierto = abierto
        self.db.guardar_estado("abierto", "1" if abierto else "0")

    def activos_de(self, token: str) -> list[str]:
        return [i for i in self.cola if self.duenos.get(i) == token]

    def modelo(self) -> dict:
        """Qué modelo y qué LoRA se están usando, para el panel."""
        nombres = {entrada: valor for _, entrada, valor in workflow.archivos(self.workflow)}
        familia = self.familias.get("modelo") or self.familias.get("workflow")
        return {"modelo": nombres.get("unet_name") or nombres.get("ckpt_name") or "", "propio": bool(self.aj.modelo),
                "lora": nombres.get("lora_name", "") if self.aj.lora else "", "fuerza": self.aj.fuerza_lora,
                "palabra_clave": self.aj.palabra_clave, "familia": arquitectura.nombre(familia) if familia else ""}

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

    def encolar(self, token: str, alias: str, prompt: str, estilo: Estilo, formato: Formato | None, *,
                tema: Estilo | None = None, foto: tuple[str, int, int] | None = None, fuerza: float | None = None,
                publico: bool = True, reto: int | None = None, miniatura_estilo: str | None = None,
                revision: str = "aprobada") -> str:
        """Añade un trabajo a la cola. Con `foto` (id, ancho, alto) se usa la foto como base.

        `revision` = "pendiente" si el profesor tiene que aprobar la imagen antes de que sea pública."""
        id_ = uuid.uuid4().hex
        formato = formato or next(iter(self.aj.formatos.values()))
        ancho, alto = (foto[1], foto[2]) if foto else (formato.ancho, formato.alto)
        self.db.crear_trabajo({
            "id": id_, "token": token, "alias": alias, "prompt": prompt,
            "estilo": estilo.id, "tema": tema.id if tema else None,
            "formato": "foto" if foto else formato.id,
            "prompt_final": estilo.aplicar(tema.aplicar(prompt) if tema else prompt),
            "semilla": random.randint(1, 2**50), "estado": "cola", "creado": time.time(),
            "foto": foto[0] if foto else None, "fuerza": fuerza, "publico": int(publico),
            "ancho": ancho, "alto": alto, "reto": reto, "miniatura_estilo": miniatura_estilo,
            "revision": revision,
        })
        self.cola.append(id_)
        self.duenos[id_] = token
        self._despertar.set()
        if self.interprete and not miniatura_estilo:
            self._hay_ideas.set()
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
        fallos = 0
        while True:
            info = await self.comfy.estado()
            fallos = 0 if info is not None else fallos + 1
            if info is not None or fallos >= 2:  # un fallo suelto (ComfyUI muy ocupado) no cuenta
                self.comfy_info = info
            if info is None and fallos >= 2:
                self._comprobado = 0.0  # cuando vuelva ComfyUI (quizá con archivos nuevos), se comprueba otra vez
            elif info is not None and (not self._comprobado or (self.faltan and time.time() - self._comprobado > 20)):
                faltan = await self.comfy.comprobar(self.workflow)
                if faltan is not None:
                    familia, self.familias = await arquitectura.revisar(
                        self.comfy, self.workflow, bool(self.aj.modelo), bool(self.aj.lora))
                    self.faltan, self._comprobado = faltan + familia, time.time()
                    for f in faltan:
                        log.warning("%s", f)
            if self.interprete:
                await self.interprete.comprobar()
            await asyncio.sleep(5)

    # --- Intérprete de ideas: trabaja por adelantado sobre la cola ---

    def _siguiente_idea(self) -> str | None:
        """La primera idea de la cola que dé tiempo a interpretar antes de que le toque a la gráfica.
        Si el intérprete va más lento que la gráfica, se salta las más cercanas en vez de hacerla esperar."""
        pendientes = []
        for posicion, id_ in enumerate(list(self.cola)):
            if id_ in self._ia_decidida:
                continue
            t = self.db.trabajo(id_)
            if not t or t["miniatura_estilo"] or t["prompt_ia"] is not None:
                self._ia_decidida.add(id_)
                continue
            if self.aj.interprete_esperar or posicion * self.media() >= self._ia_media * 0.8:
                return id_  # esperando, por orden de llegada: la gráfica pinta una mientras él prepara la siguiente
            pendientes.append(id_)
        return pendientes[0] if pendientes else None

    async def bucle_interprete(self):
        if not self.interprete:
            return
        while True:
            id_ = self._siguiente_idea()
            if id_ is None:
                self._hay_ideas.clear()
                await self._hay_ideas.wait()
                continue
            if not self.interprete.ok:  # Ollama cerrado: se pinta la idea tal cual hasta que vuelva
                await asyncio.sleep(3)
                continue
            t = self.db.trabajo(id_)
            self._ia_en_curso, inicio = id_, time.time()
            try:
                texto = await self.interprete.interpretar(t["prompt"])
            finally:
                self._ia_en_curso = None
            self._ia_media = 0.7 * self._ia_media + 0.3 * (time.time() - inicio)
            self._ia_decidida.add(id_)
            ahora = self.db.trabajo(id_)
            if ahora and ahora["prompt_ia"] is None:  # si la gráfica no se ha adelantado
                self.db.actualizar(id_, prompt_ia=texto or "")
                if texto:
                    log.info("Intérprete: «%s» → %s", t["prompt"], texto)

    async def _idea_interpretada(self, id_: str) -> str | None:
        """Lo que entendió el intérprete. Con [interprete] esperar, lo espera hasta 25 s; si no, solo si está
        con esta idea o libre para empezarla. Si no funciona, se pinta la idea tal cual."""
        esperar = self.aj.interprete_esperar
        limite = time.time() + (25 if esperar else 15)
        while time.time() < limite:
            t = self.db.trabajo(id_)
            if t["prompt_ia"] is not None:
                return t["prompt_ia"] or None
            if not self.interprete.ok or (not esperar and self._ia_en_curso not in (None, id_)):
                break
            self._hay_ideas.set()
            await asyncio.sleep(0.2)
        self._ia_decidida.add(id_)
        self.db.actualizar(id_, prompt_ia="")
        return None

    def _receta(self, t: dict, idea: str) -> str:
        estilo, tema = self.aj.estilos.get(t["estilo"]), self.aj.temas.get(t["tema"] or "")
        texto = tema.aplicar(idea) if tema else idea
        return estilo.aplicar(texto) if estilo else texto

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
            ancho, alto = t["ancho"], t["alto"]
            if not ancho:  # trabajos de la primera versión
                formato = self.aj.formatos.get(t["formato"]) or next(iter(self.aj.formatos.values()))
                ancho, alto = formato.ancho, formato.alto
            prompt_final = t["prompt_final"]
            if self.interprete and not t["miniatura_estilo"]:
                if idea := await self._idea_interpretada(id_):
                    prompt_final = self._receta(t, idea)
                    self.db.actualizar(id_, prompt_final=prompt_final)
            wf = workflow.preparar(self.workflow, self.nodos,
                                   workflow.con_palabra_clave(prompt_final, self.aj.palabra_clave),
                                   ancho, alto, t["semilla"], "congreso_carnaval/estudio")
            if t["foto"]:
                try:
                    datos = (self.aj.datos / "fotos" / f"{t['foto']}.jpg").read_bytes()
                except OSError as e:
                    raise ValueError("La foto ya no está en el ordenador. Súbela otra vez.") from e
                nombre = await self.comfy.subir_imagen(datos, f"estudio_{t['foto']}.jpg")
                wf = workflow.con_foto(wf, self.nodos, nombre, t["fuerza"] or 0.68)
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
        guardar_vista(rgb, carpeta / "vistas" / f"{id_}.webp")
        mini = rgb.copy()
        mini.thumbnail((512, 512))
        mini.save(carpeta / "miniaturas" / f"{id_}.webp", "WEBP", quality=82)
        guardar_tesela(rgb, carpeta / "teselas" / f"{id_}.webp")
        if miniatura_estilo:
            ImageOps.fit(rgb, (320, 320)).save(carpeta / "estilos" / f"{miniatura_estilo}.webp", "WEBP", quality=85)
