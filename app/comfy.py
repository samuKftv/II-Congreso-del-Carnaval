"""Cliente mínimo de la API de ComfyUI: encola un workflow, sigue el progreso y descarga la imagen."""

from __future__ import annotations

import asyncio
import json
import struct
import uuid
from typing import Callable

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

# Tipos de mensajes binarios del websocket de ComfyUI
PREVIEW_IMAGE = 1
PREVIEW_IMAGE_WITH_METADATA = 4


class ErrorComfy(Exception):
    pass


class ComfyNoDisponible(ErrorComfy):
    pass


class Interrumpido(ErrorComfy):
    pass


def _extraer_preview(datos: bytes) -> bytes | None:
    if len(datos) < 8:
        return None
    tipo = struct.unpack(">I", datos[:4])[0]
    if tipo == PREVIEW_IMAGE:
        imagen = datos[8:]
    elif tipo == PREVIEW_IMAGE_WITH_METADATA:
        largo = struct.unpack(">I", datos[4:8])[0]
        imagen = datos[8 + largo:]
    else:
        return None
    if imagen[:3] == b"\xff\xd8\xff" or imagen[:4] == b"\x89PNG":
        return imagen
    return None


def _mensaje_error(respuesta: httpx.Response) -> str:
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return f"ComfyUI respondió {respuesta.status_code}"
    error = cuerpo.get("error", {})
    texto = error.get("message", "") if isinstance(error, dict) else str(error)
    for nodo in cuerpo.get("node_errors", {}).values():
        for e in nodo.get("errors", []):
            texto += f" · {nodo.get('class_type', '')}: {e.get('message', '')} {e.get('details', '')}".rstrip()
    return texto or f"ComfyUI respondió {respuesta.status_code}"


class ComfyUI:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.ws_url = "ws" + self.url[4:] if self.url.startswith("http") else self.url
        self.client_id = uuid.uuid4().hex
        self.prompt_actual: str | None = None
        self.http = httpx.AsyncClient(base_url=self.url, timeout=30)

    async def cerrar(self):
        await self.http.aclose()

    async def estado(self) -> dict | None:
        """Datos del sistema (GPU, VRAM) o None si ComfyUI no responde."""
        try:
            r = await self.http.get("/system_stats", timeout=3)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError):
            return None

    async def interrumpir(self, prompt_id: str | None = None):
        """Quita el trabajo de la cola de ComfyUI y lo detiene si ya se está generando."""
        try:
            if prompt_id:
                await self.http.post("/queue", json={"delete": [prompt_id]}, timeout=5)
            await self.http.post("/interrupt", json={"prompt_id": prompt_id} if prompt_id else {}, timeout=5)
        except httpx.HTTPError:
            pass

    async def generar(
        self,
        workflow: dict,
        al_progresar: Callable[[int, int], None],
        al_previsualizar: Callable[[bytes], None],
        tiempo_maximo: float,
    ) -> list[bytes]:
        try:
            async with connect(f"{self.ws_url}/ws?clientId={self.client_id}", max_size=None, open_timeout=5) as ws:
                r = await self.http.post("/prompt", json={"prompt": workflow, "client_id": self.client_id})
                if r.status_code != 200:
                    raise ErrorComfy(_mensaje_error(r))
                prompt_id = self.prompt_actual = r.json()["prompt_id"]
                try:
                    async with asyncio.timeout(tiempo_maximo):
                        await self._esperar(ws, prompt_id, al_progresar, al_previsualizar)
                except TimeoutError as e:
                    await self.interrumpir(prompt_id)
                    raise ErrorComfy(f"La imagen ha tardado más de {tiempo_maximo:.0f} s") from e
            return await self._descargar(prompt_id)
        except ErrorComfy:
            raise
        except (OSError, httpx.TransportError, WebSocketException) as e:
            raise ComfyNoDisponible(f"No se puede conectar con ComfyUI: {e}") from e

    async def _esperar(self, ws, prompt_id, al_progresar, al_previsualizar):
        async for mensaje in ws:
            if isinstance(mensaje, bytes):
                if imagen := _extraer_preview(mensaje):
                    al_previsualizar(imagen)
                continue
            m = json.loads(mensaje)
            tipo, d = m.get("type"), m.get("data") or {}
            if d.get("prompt_id", prompt_id) != prompt_id:
                continue
            if tipo == "progress":
                al_progresar(int(d.get("value", 0)), int(d.get("max", 1)))
            elif tipo == "execution_error":
                raise ErrorComfy(d.get("exception_message") or "Error en ComfyUI")
            elif tipo == "execution_interrupted":
                raise Interrumpido("Generación interrumpida")
            elif tipo == "execution_success":
                return
            elif tipo == "executing" and d.get("node") is None and d.get("prompt_id") == prompt_id:
                return
        raise ComfyNoDisponible("Se ha cerrado la conexión con ComfyUI")

    async def _descargar(self, prompt_id: str) -> list[bytes]:
        # ComfyUI guarda el historial un instante después de avisar de que ha terminado.
        for _ in range(50):
            r = await self.http.get(f"/history/{prompt_id}")
            historial = r.json().get(prompt_id) if r.status_code == 200 else None
            if historial and historial.get("outputs"):
                break
            await asyncio.sleep(0.2)
        else:
            raise ErrorComfy("ComfyUI no ha devuelto ninguna imagen")

        archivos = [im for salida in historial["outputs"].values() for im in salida.get("images", [])]
        archivos.sort(key=lambda im: im.get("type") != "output")  # primero las guardadas
        imagenes = []
        for im in archivos:
            r = await self.http.get(
                "/view",
                params={"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")},
            )
            if r.status_code == 200:
                imagenes.append(r.content)
        if not imagenes:
            raise ErrorComfy("ComfyUI no ha devuelto ninguna imagen")
        return imagenes
