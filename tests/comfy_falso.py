"""ComfyUI simulado para probar el estudio sin GPU.

Imita /prompt, /ws, /history, /view, /upload/image, /system_stats, /interrupt y /queue.
Uso manual: python -m tests.comfy_falso  (escucha en 127.0.0.1:8188)
"""

from __future__ import annotations

import asyncio
import io
import json
import random
import struct
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw, ImageFont

PASOS = 9


def pintar(texto: str, ancho: int, alto: int, semilla: int, base: Image.Image | None = None) -> Image.Image:
    rnd = random.Random(semilla)
    colores = [(255, 46, 136), (255, 210, 63), (34, 211, 238), (255, 138, 0), (61, 220, 132), (139, 92, 246)]
    a, b = rnd.sample(colores, 2)
    if base is not None:  # img2img: la foto teñida de un color
        ancho, alto = base.size
        im = Image.blend(base.convert("RGB"), Image.new("RGB", base.size, a), 0.35)
    else:
        im = Image.new("RGB", (ancho, alto))
    d = ImageDraw.Draw(im)
    for y in range(alto if base is None else 0):
        t = y / alto
        d.line([(0, y), (ancho, y)], fill=tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)))
    for _ in range(60 if base is None else 15):
        x, y, r = rnd.randrange(ancho), rnd.randrange(alto), rnd.randrange(6, 40)
        d.ellipse([x - r, y - r, x + r, y + r], fill=rnd.choice(colores), outline=(255, 255, 255))
    fuente = ImageFont.load_default(size=max(28, ancho // 22))
    palabras, lineas, linea = texto.split(), [], ""
    for p in palabras:
        if len(linea) + len(p) > 24:
            lineas.append(linea)
            linea = ""
        linea = f"{linea} {p}".strip()
    lineas.append(linea)
    y = alto // 2 - len(lineas[:6]) * fuente.size // 2
    for l in lineas[:6]:
        d.text((ancho // 2, y), l, font=fuente, fill="white", anchor="mt", stroke_width=3, stroke_fill="black")
        y += int(fuente.size * 1.2)
    return im


def crear_comfy_falso(retardo_paso: float = 0.15, fallar_con: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def vida(_app):
        tarea = asyncio.create_task(trabajador())
        yield
        tarea.cancel()

    app = FastAPI(lifespan=vida)
    clientes: dict[str, WebSocket] = {}
    historial: dict[str, dict] = {}
    entradas: dict[str, bytes] = {}
    archivos: dict[str, bytes] = {}
    cola: asyncio.Queue = asyncio.Queue()
    interrumpir = asyncio.Event()
    app.state.recibidos = []

    async def enviar(cid: str, mensaje):
        ws = clientes.get(cid)
        if not ws:
            return
        try:
            if isinstance(mensaje, bytes):
                await ws.send_bytes(mensaje)
            else:
                await ws.send_text(json.dumps(mensaje))
        except Exception:
            clientes.pop(cid, None)

    async def trabajador():
        while True:
            pid, wf, cid = await cola.get()
            interrumpir.clear()
            texto = next(n["inputs"]["text"] for n in wf.values() if n["class_type"] == "CLIPTextEncode")
            semilla = next(n["inputs"]["seed"] for n in wf.values() if "seed" in n.get("inputs", {}))
            carga = next((n for n in wf.values() if n["class_type"] == "LoadImage"), None)
            base = Image.open(io.BytesIO(entradas[carga["inputs"]["image"]])) if carga else None
            tam = next((n["inputs"] for n in wf.values() if "width" in n.get("inputs", {})), {"width": 0, "height": 0})
            await enviar(cid, {"type": "execution_start", "data": {"prompt_id": pid}})
            if fallar_con and fallar_con in texto:
                await enviar(cid, {"type": "execution_error", "data": {"prompt_id": pid, "exception_message": "CUDA out of memory (simulado)"}})
                continue
            im = pintar(texto, tam["width"], tam["height"], semilla, base)
            interrumpido = False
            for paso in range(1, PASOS + 1):
                await asyncio.sleep(retardo_paso)
                if interrumpir.is_set():
                    interrumpido = True
                    break
                await enviar(cid, {"type": "progress", "data": {"value": paso, "max": PASOS, "prompt_id": pid, "node": "3"}})
                pre = im.copy()
                pre.thumbnail((256, 256))
                buf = io.BytesIO()
                pre.save(buf, "JPEG", quality=60)
                await enviar(cid, struct.pack(">II", 1, 1) + buf.getvalue())
            if interrumpido:
                await enviar(cid, {"type": "execution_interrupted", "data": {"prompt_id": pid}})
                continue
            nombre = f"estudio_{pid[:8]}.png"
            buf = io.BytesIO()
            im.save(buf, "PNG")
            archivos[nombre] = buf.getvalue()
            historial[pid] = {"outputs": {"9": {"images": [{"filename": nombre, "subfolder": "", "type": "output"}]}}}
            await enviar(cid, {"type": "executing", "data": {"node": None, "prompt_id": pid}})

    @app.get("/system_stats")
    async def system_stats():
        return {"system": {"os": "nt"}, "devices": [{
            "name": "cuda:0 NVIDIA GeForce RTX 5070 : cudaMallocAsync", "type": "cuda",
            "vram_total": 12 * 2**30, "vram_free": 7 * 2**30}]}

    @app.post("/prompt")
    async def prompt(request: Request):
        cuerpo = await request.json()
        wf = cuerpo["prompt"]
        if not any(n.get("class_type") == "SaveImage" for n in wf.values()):
            return JSONResponse({"error": {"message": "Prompt has no outputs"}, "node_errors": {}}, status_code=400)
        pid = str(uuid.uuid4())
        app.state.recibidos.append(wf)
        await cola.put((pid, wf, cuerpo.get("client_id", "")))
        return {"prompt_id": pid, "number": len(app.state.recibidos), "node_errors": {}}

    @app.post("/upload/image")
    async def upload(request: Request):
        formulario = await request.form()
        archivo = formulario["image"]
        entradas[archivo.filename] = await archivo.read()
        return {"name": archivo.filename, "subfolder": "", "type": "input"}

    @app.get("/history/{pid}")
    async def history(pid: str):
        return {pid: historial[pid]} if pid in historial else {}

    @app.get("/view")
    async def view(filename: str, subfolder: str = "", type: str = "output"):
        if filename not in archivos:
            return Response(status_code=404)
        return Response(archivos[filename], media_type="image/png")

    @app.post("/interrupt")
    async def interrupt():
        interrumpir.set()
        return {}

    @app.post("/queue")
    async def queue():
        return {}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket, clientId: str = ""):
        await websocket.accept()
        clientes[clientId] = websocket
        await websocket.send_text(json.dumps({"type": "status", "data": {"status": {"exec_info": {"queue_remaining": 0}}, "sid": clientId}}))
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            if clientes.get(clientId) is websocket:
                clientes.pop(clientId, None)

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(crear_comfy_falso(retardo_paso=0.4), host="127.0.0.1", port=8188)
