"""Servidor web del estudio: páginas, API del alumnado, panel del profesor y proyector."""

from __future__ import annotations

import asyncio
import hmac
import io
import logging
import re
import secrets
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, unquote

import segno
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .cola import Estudio
from .comfy import ComfyUI
from .db import BaseDatos
from .moderacion import Filtro, normalizar

log = logging.getLogger("estudio")

ESTATICOS = Path(__file__).parent / "static"
ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")
CLAVE_POR_DEFECTO = "cambia-esta-clave"
LOCALES = {"127.0.0.1", "::1", "localhost"}


class Entrada(BaseModel):
    alias: str
    codigo: str = ""


class Pedido(BaseModel):
    prompt: str
    estilo: str
    formato: str


class Interruptor(BaseModel):
    valor: bool


class Bloqueo(BaseModel):
    token: str
    valor: bool


def ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no envía nada: solo elige la interfaz de red
            return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def url_alumnado(aj: config.Ajustes) -> str:
    puerto = "" if aj.puerto == 80 else f":{aj.puerto}"
    codigo = f"?c={quote(aj.codigo)}" if aj.codigo else ""
    return f"http://{aj.direccion or ip_local()}{puerto}/{codigo}"


def crear_app(aj: config.Ajustes | None = None) -> FastAPI:
    aj = aj or config.cargar()
    db = BaseDatos(aj.datos / "estudio.db")
    comfy = ComfyUI(aj.comfy_url)
    estudio = Estudio(aj, db, comfy)
    filtro = Filtro(aj.palabras_prohibidas)
    url = url_alumnado(aj)
    panel_remoto = bool(aj.clave_profesor) and aj.clave_profesor != CLAVE_POR_DEFECTO

    @asynccontextmanager
    async def vida(_app):
        tareas = [asyncio.create_task(estudio.bucle()), asyncio.create_task(estudio.vigilar_comfy())]
        yield
        for t in tareas:
            t.cancel()
        await comfy.cerrar()

    app = FastAPI(lifespan=vida, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.estudio = estudio
    app.state.url_alumnado = url
    app.state.panel_remoto = panel_remoto

    @app.middleware("http")
    async def sin_cache(request: Request, call_next):
        respuesta = await call_next(request)
        if not request.url.path.startswith("/img/"):
            respuesta.headers.setdefault("Cache-Control", "no-cache")
        return respuesta

    # --- Dependencias ---

    def persona(x_token: str | None = Header(None)) -> dict:
        p = db.persona(x_token) if x_token else None
        if not p:
            raise HTTPException(401, "Vuelve a entrar con tu alias.")
        return p

    def profesor(request: Request, x_clave: str | None = Header(None)) -> None:
        if request.client and request.client.host in LOCALES:
            return
        if panel_remoto and x_clave and hmac.compare_digest(unquote(x_clave).encode(), aj.clave_profesor.encode()):
            return
        raise HTTPException(401, "Clave del profesor incorrecta.")

    def id_valido(id_: str) -> str:
        if not ID_VALIDO.match(id_):
            raise HTTPException(404, "No existe")
        return id_

    # --- Representación ---

    def miniatura_estilo(estilo_id: str) -> str | None:
        ruta = aj.datos / "estilos" / f"{estilo_id}.webp"
        return f"/estilos/{estilo_id}.webp?v={int(ruta.stat().st_mtime)}" if ruta.exists() else None

    def trabajo_json(t: dict, publico: bool = False) -> dict:
        formato = aj.formatos.get(t["formato"])
        d = {
            "id": t["id"], "alias": t["alias"], "prompt": t["prompt"], "estilo": t["estilo"],
            "formato": t["formato"], "estado": t["estado"], "fin": t["fin"],
            "ancho": formato.ancho if formato else None, "alto": formato.alto if formato else None,
        }
        if t["estado"] == "hecho":
            d["imagen"] = f"/img/{t['id']}.png"
            d["mini"] = f"/img/{t['id']}/mini.webp"
        if publico:
            return d
        if t["estado"] == "error":
            d["error"] = t["error"]
        if espera := estudio.espera(t["id"]):
            d["delante"], d["segundos"] = espera[0], round(espera[1])
            d["comfy_ok"] = estudio.comfy_info is not None
        if estudio.actual and estudio.actual.id == t["id"]:
            d["estado"] = "generando"
            d["paso"], d["pasos"] = estudio.actual.valor, estudio.actual.maximo
            d["preview"] = estudio.actual.version
        return d

    # --- Páginas ---

    @app.get("/", include_in_schema=False)
    def inicio():
        return FileResponse(ESTATICOS / "index.html")

    @app.get("/panel", include_in_schema=False)
    def pagina_panel():
        return FileResponse(ESTATICOS / "panel.html")

    @app.get("/proyector", include_in_schema=False)
    def pagina_proyector():
        return FileResponse(ESTATICOS / "proyector.html")

    app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")

    # --- Imágenes ---

    @app.get("/img/{id_}.png")
    def imagen(id_: str = Depends(id_valido), descargar: bool = False):
        ruta = aj.datos / "imagenes" / f"{id_}.png"
        if not ruta.exists():
            raise HTTPException(404, "No existe")
        nombre = f"carnaval-{id_[:8]}.png" if descargar else None
        return FileResponse(ruta, media_type="image/png", filename=nombre,
                            headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/img/{id_}/mini.webp")
    def miniatura(id_: str = Depends(id_valido)):
        ruta = aj.datos / "miniaturas" / f"{id_}.webp"
        if not ruta.exists():
            raise HTTPException(404, "No existe")
        return FileResponse(ruta, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/img/{id_}/preview")
    def preview(id_: str = Depends(id_valido)):
        actual = estudio.actual
        if not actual or actual.id != id_ or not actual.preview:
            raise HTTPException(404, "Sin vista previa")
        tipo = "image/png" if actual.preview[:4] == b"\x89PNG" else "image/jpeg"
        return Response(actual.preview, media_type=tipo, headers={"Cache-Control": "no-store"})

    @app.get("/estilos/{estilo_id}.webp")
    def imagen_estilo(estilo_id: str):
        if estilo_id not in aj.estilos:
            raise HTTPException(404, "No existe")
        ruta = aj.datos / "estilos" / f"{estilo_id}.webp"
        if not ruta.exists():
            raise HTTPException(404, "No existe")
        return FileResponse(ruta, media_type="image/webp")

    @app.get("/qr.svg")
    def qr():
        buffer = io.BytesIO()
        segno.make(url, error="m").save(buffer, kind="svg", scale=10, border=2, dark="#1a0b2e", light="#ffffff")
        return Response(buffer.getvalue(), media_type="image/svg+xml")

    # --- API del alumnado ---

    @app.get("/api/info")
    def info():
        return {
            "evento": aj.evento,
            "subtitulo": aj.subtitulo,
            "requiere_codigo": bool(aj.codigo),
            "abierto": estudio.abierto,
            "comfy_ok": estudio.comfy_info is not None,
            "en_cola": len(estudio.cola),
            "media": round(estudio.media(), 1),
            "max_caracteres": aj.max_caracteres,
            "url": url,
            "estilos": [
                {"id": e.id, "nombre": e.nombre, "emoji": e.emoji, "colores": e.colores,
                 "miniatura": miniatura_estilo(e.id)}
                for e in aj.estilos.values()
            ],
            "formatos": [{"id": f.id, "ancho": f.ancho, "alto": f.alto} for f in aj.formatos.values()],
            "ideas": aj.ideas,
        }

    @app.post("/api/entrar")
    def entrar(e: Entrada):
        alias = " ".join(e.alias.split())[:24]
        if not alias:
            raise HTTPException(422, "Escribe un alias para entrar.")
        if aj.codigo and normalizar(e.codigo.strip()) != normalizar(aj.codigo):
            raise HTTPException(403, "El código del aula no es correcto.")
        if filtro.bloqueada(alias):
            raise HTTPException(422, "Elige otro alias, por favor.")
        token = secrets.token_hex(16)
        db.crear_persona(token, alias)
        log.info("Entra %s", alias)
        return {"token": token, "alias": alias}

    @app.get("/api/yo")
    def yo(p: dict = Depends(persona)):
        activos = [trabajo_json(db.trabajo(i)) for i in estudio.activos_de(p["token"])]
        return {"alias": p["alias"], "bloqueado": bool(p["bloqueado"]), "activos": activos}

    @app.post("/api/crear")
    def crear(pedido: Pedido, p: dict = Depends(persona)):
        if p["bloqueado"]:
            raise HTTPException(403, "Tu acceso al estudio está en pausa. Habla con el profesor.")
        if not estudio.abierto:
            raise HTTPException(423, "El estudio está cerrado ahora mismo.")
        prompt = " ".join(pedido.prompt.split())
        if len(prompt) < 3:
            raise HTTPException(422, "Cuéntame un poco más tu idea.")
        if len(prompt) > aj.max_caracteres:
            raise HTTPException(422, f"Tu idea es muy larga: máximo {aj.max_caracteres} caracteres.")
        estilo, formato = aj.estilos.get(pedido.estilo), aj.formatos.get(pedido.formato)
        if not estilo or not formato:
            raise HTTPException(422, "Elige un estilo y un formato.")
        if filtro.bloqueada(prompt):
            raise HTTPException(422, "Tu idea incluye palabras que no están permitidas en el estudio. Prueba a contarla de otra forma.")
        activos = estudio.activos_de(p["token"])
        if len(activos) >= aj.en_cola_por_persona:
            return JSONResponse({"detail": "Ya tienes una imagen en marcha.", "id": activos[0]}, status_code=409)
        id_ = estudio.encolar(p["token"], p["alias"], prompt, estilo, formato)
        log.info("%s pide: %s [%s]", p["alias"], prompt, estilo.id)
        return trabajo_json(db.trabajo(id_))

    @app.get("/api/trabajos/{id_}")
    def ver_trabajo(id_: str = Depends(id_valido), p: dict = Depends(persona)):
        t = db.trabajo(id_)
        if not t or t["token"] != p["token"]:
            raise HTTPException(404, "No existe")
        return trabajo_json(t)

    @app.post("/api/trabajos/{id_}/cancelar")
    async def cancelar_propio(id_: str = Depends(id_valido), p: dict = Depends(persona)):
        t = db.trabajo(id_)
        if not t or t["token"] != p["token"]:
            raise HTTPException(404, "No existe")
        await estudio.cancelar(id_)
        return {"ok": True}

    @app.get("/api/mis-creaciones")
    def mis_creaciones(p: dict = Depends(persona)):
        return [trabajo_json(t, publico=True) for t in db.de_persona(p["token"])]

    # --- Proyector ---

    @app.get("/api/galeria")
    def galeria(limite: int = 30):
        return {
            "abierto": estudio.abierto,
            "en_cola": len(estudio.cola),
            "total": db.estadisticas()["hechas"],
            "imagenes": [trabajo_json(t, publico=True) for t in db.galeria(min(max(limite, 1), 100))],
        }

    # --- Panel del profesor ---

    @app.get("/api/panel/estado", dependencies=[Depends(profesor)])
    def estado_panel(request: Request):
        info_comfy = estudio.comfy_info
        gpu = None
        if info_comfy and info_comfy.get("devices"):
            dispositivo = info_comfy["devices"][0]
            gpu = {
                "nombre": dispositivo.get("name", "").split(" : ")[0],
                "vram_total": dispositivo.get("vram_total"),
                "vram_libre": dispositivo.get("vram_free"),
            }
        cola = []
        for i in list(estudio.cola):
            if t := db.trabajo(i):
                d = trabajo_json(t)
                d["token"], d["miniatura_estilo"] = t["token"], t["miniatura_estilo"]
                cola.append(d)
        return {
            "abierto": estudio.abierto,
            "comfy": {"ok": info_comfy is not None, "url": aj.comfy_url, "gpu": gpu},
            "cola": cola,
            "media": round(estudio.media(), 1),
            "estadisticas": db.estadisticas(),
            "url_alumnado": url,
            "codigo": aj.codigo,
            "avisos": estudio.avisos,
            "bloqueados": db.bloqueados(),
            "local": bool(request.client and request.client.host in LOCALES),
            "panel_remoto": panel_remoto,
        }

    @app.post("/api/panel/abierto", dependencies=[Depends(profesor)])
    def abrir(i: Interruptor):
        estudio.abrir(i.valor)
        log.info("Estudio %s", "abierto" if i.valor else "cerrado")
        return {"abierto": estudio.abierto}

    @app.post("/api/panel/cancelar/{id_}", dependencies=[Depends(profesor)])
    async def cancelar(id_: str = Depends(id_valido)):
        return {"ok": await estudio.cancelar(id_)}

    @app.get("/api/panel/imagenes", dependencies=[Depends(profesor)])
    def imagenes(antes: float | None = None, limite: int = 60):
        filas = db.galeria(min(max(limite, 1), 200), incluir_ocultas=True, antes=antes)
        return [trabajo_json(t, publico=True) | {"token": t["token"], "oculto": bool(t["oculto"])} for t in filas]

    @app.post("/api/panel/ocultar/{id_}", dependencies=[Depends(profesor)])
    def ocultar(i: Interruptor, id_: str = Depends(id_valido)):
        db.actualizar(id_, oculto=int(i.valor))
        return {"ok": True}

    @app.post("/api/panel/bloquear", dependencies=[Depends(profesor)])
    async def bloquear(b: Bloqueo):
        if not db.persona(b.token):
            raise HTTPException(404, "No existe")
        db.bloquear(b.token, b.valor)
        if b.valor:
            for id_ in estudio.activos_de(b.token):
                await estudio.cancelar(id_)
        return {"ok": True}

    @app.post("/api/panel/miniaturas", dependencies=[Depends(profesor)])
    def generar_miniaturas():
        formato = aj.formatos.get("cuadrado") or next(iter(aj.formatos.values()))
        for e in aj.estilos.values():
            estudio.encolar("profesor", "Profe", e.ejemplo, e, formato, miniatura_estilo=e.id)
        return {"encoladas": len(aj.estilos)}

    return app
