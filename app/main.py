"""Servidor web del estudio: páginas, API del alumnado, panel del profesor y proyector."""

from __future__ import annotations

import asyncio
import hmac
import io
import logging
import re
import secrets
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, unquote

import segno
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from . import VERSION, config, fotos
from .cola import Estudio, guardar_tesela, guardar_vista
from .comfy import ComfyUI
from .db import BaseDatos
from .interprete import Interprete
from .tunel import Tunel
from .moderacion import Filtro, normalizar

log = logging.getLogger("estudio")

ESTATICOS = Path(__file__).parent / "static"
ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")
CLAVE_POR_DEFECTO = "cambia-esta-clave"
FASES_RETO = ("creando", "votando", "podio", "cerrado")
VISTAS_PROYECTOR = ("mosaico", "galeria", "podio")  # podio = ganadoras del concurso (cierra la votación)
LOCALES = {"127.0.0.1", "::1", "localhost"}
# Cabeceras que pone un intermediario (el túnel de Cloudflare): esa petición viene de internet, no de este PC
DE_FUERA = ("cf-connecting-ip", "cf-ray", "x-forwarded-for", "x-forwarded-host", "forwarded")
SIN_COMPRIMIR = ("/img/", "/estilos/", "/cartel", "/logo", "/static/fuentes/")  # ya van comprimidas (PNG, WebP, JPG)
ANCHOS_CARTEL = (480, 720, 960)
ALTOS_LOGO = (80, 120, 160)


class ComprimirTexto:
    """Gzip para HTML, JS, CSS y JSON (pesan 4-5 veces menos por la WiFi); las imágenes, tal cual."""

    def __init__(self, app):
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=800)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not scope["path"].startswith(SIN_COMPRIMIR):
            return await self.gzip(scope, receive, send)
        return await self.app(scope, receive, send)


def reducida(ruta: Path, ancho: int | None = None, alto: int | None = None) -> bytes:
    """Versión WebP más pequeña del cartel o del logo, para que el móvil no baje el original."""
    with Image.open(ruta) as im:
        im.load()
        if ancho and im.width > ancho:
            im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
        elif alto and im.height > alto:
            im = im.resize((round(im.width * alto / im.height), alto), Image.LANCZOS)
        buffer = io.BytesIO()
        im.save(buffer, "WEBP", quality=85)
        return buffer.getvalue()


class Entrada(BaseModel):
    alias: str = ""
    codigo: str = ""


# Si alguien entra sin escribir su nombre, recibe uno de carnaval
ALIAS_DE_CARNAVAL = ("Arlequín", "Antifaz", "Confeti", "Serpentina", "Purpurina", "Lentejuela", "Pluma",
                     "Tambor", "Murguera", "Comparsa", "Farolillo", "Maraca", "Pierrot", "Colombina")


class Pedido(BaseModel):
    prompt: str
    estilo: str
    formato: str = ""
    tema: str = ""
    foto: str = ""
    fuerza: str = ""


class FotoSubida(BaseModel):
    datos: str = Field(max_length=15_000_000)


class NuevoReto(BaseModel):
    titulo: str
    minutos: int = 0


class Fase(BaseModel):
    fase: str


class Interruptor(BaseModel):
    valor: bool


class Bloqueo(BaseModel):
    token: str
    valor: bool


class Direccion(BaseModel):
    direccion: str


class Revision(BaseModel):
    ids: list[str] = Field(max_length=200)
    decision: str


class Vista(BaseModel):
    vista: str


def direcciones_locales() -> list[str]:
    """IPs de este PC en la red, empezando por la de la conexión principal (WiFi o cable)."""
    candidatas = []
    for destino in ("8.8.8.8", "10.255.255.255"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((destino, 1))  # no envía nada: solo elige la interfaz de red
                candidatas.append(s.getsockname()[0])
        except OSError:
            pass
    try:
        candidatas += [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    except OSError:
        pass
    unicas = []
    for ip in candidatas:
        if ip not in unicas and not ip.startswith(("127.", "169.254.", "0.")):
            unicas.append(ip)
    return unicas or ["127.0.0.1"]


def url_alumnado(aj: config.Ajustes, direccion: str) -> str:
    puerto = "" if aj.puerto == 80 else f":{aj.puerto}"
    codigo = f"?c={quote(aj.codigo)}" if aj.codigo else ""
    return f"http://{direccion}{puerto}/{codigo}"


def crear_app(aj: config.Ajustes | None = None) -> FastAPI:
    aj = aj or config.cargar()
    db = BaseDatos(aj.datos / "estudio.db")
    comfy = ComfyUI(aj.comfy_url)
    filtro = Filtro(aj.palabras_prohibidas)
    interprete = (Interprete(aj.interprete_url, aj.interprete_modelo, filtro, aj.interprete_grafica)
                  if aj.interprete_activado else None)
    estudio = Estudio(aj, db, comfy, interprete)
    cache_red = {"hasta": 0.0, "direcciones": []}

    def direcciones() -> list[str]:
        if time.monotonic() > cache_red["hasta"]:  # la red puede cambiar con la app abierta
            cache_red["direcciones"] = direcciones_locales()
            cache_red["hasta"] = time.monotonic() + 15
        return cache_red["direcciones"]

    def direccion_actual() -> str:
        if aj.direccion:
            return aj.direccion
        elegida = db.leer_estado("direccion", "")
        return elegida if elegida in direcciones() else direcciones()[0]

    tunel = Tunel(aj.puerto) if aj.internet else None

    def url() -> str:
        if tunel and tunel.url:
            return f"{tunel.url}/" + (f"?c={quote(aj.codigo)}" if aj.codigo else "")
        return url_alumnado(aj, direccion_actual())

    def es_local(request: Request) -> bool:
        """Solo cuenta como "este PC" lo que llega directo de 127.0.0.1, no lo que trae el túnel."""
        return bool(request.client and request.client.host in LOCALES
                    and not any(c in request.headers for c in DE_FUERA))

    panel_remoto = bool(aj.clave_profesor) and aj.clave_profesor != CLAVE_POR_DEFECTO

    def revisar_antes() -> bool:
        return db.leer_estado("revisar_antes", "1" if aj.revisar_antes else "0") == "1"

    def vista() -> str:
        return db.leer_estado("vista_proyector", "mosaico")

    def concurso() -> dict:
        v = vista()
        return {"vista": v, "votacion_abierta": v != "podio", "revisar_antes": revisar_antes()}

    @asynccontextmanager
    async def vida(_app):
        tareas = [asyncio.create_task(estudio.bucle()), asyncio.create_task(estudio.vigilar_comfy()),
                  asyncio.create_task(estudio.bucle_interprete())]
        if tunel:
            tunel.arrancar()
        yield
        if tunel:
            tunel.parar()
        for t in tareas:
            t.cancel()
        await comfy.cerrar()
        if interprete:
            await interprete.cerrar()

    app = FastAPI(lifespan=vida, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(ComprimirTexto)
    reducidas: dict[tuple, bytes] = {}

    def servir_reducida(ruta: Path, ancho: int | None = None, alto: int | None = None) -> Response:
        clave = (str(ruta), ruta.stat().st_mtime, ancho, alto)
        if clave not in reducidas:
            reducidas[clave] = reducida(ruta, ancho, alto)
        return Response(reducidas[clave], media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})
    app.state.estudio = estudio
    app.state.url = url
    app.state.direcciones = direcciones
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
        if es_local(request):
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

    def trabajo_json(t: dict, publico: bool = False, token: str = "") -> dict:
        formato = aj.formatos.get(t["formato"])
        d = {
            "id": t["id"], "alias": t["alias"], "prompt": t["prompt"], "estilo": t["estilo"],
            "tema": t.get("tema"), "formato": t["formato"], "estado": t["estado"], "fin": t["fin"],
            "ancho": t.get("ancho") or (formato.ancho if formato else None),
            "alto": t.get("alto") or (formato.alto if formato else None),
            "con_foto": bool(t.get("foto")), "publico": bool(t.get("publico", 1)),
            "revision": t.get("revision") or "aprobada", "votos": t.get("votos", 0),
        }
        if token:
            d["mia"] = t["token"] == token
            d["votado"] = bool(t.get("votado"))
        if t["estado"] == "hecho":
            d["imagen"] = f"/img/{t['id']}.png"
            d["vista"] = f"/img/{t['id']}/vista.webp"
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

    def reto_actual() -> dict | None:
        r = db.reto_activo()
        if r and r["fase"] == "creando" and r["fin_creacion"] and time.time() >= r["fin_creacion"]:
            db.fase_reto(r["id"], "votando")  # se acabó el tiempo: a votar
            r["fase"] = "votando"
            log.info("Fin del tiempo del reto «%s»: empieza la votación", r["titulo"])
        return r

    def reto_json(r: dict | None) -> dict | None:
        if not r:
            return None
        d = {"id": r["id"], "titulo": r["titulo"], "fase": r["fase"], "imagenes": db.imagenes_reto(r["id"]), "quedan": None}
        if r["fase"] == "creando" and r["fin_creacion"]:
            d["quedan"] = max(0, round(r["fin_creacion"] - time.time()))
        if r["fase"] == "podio":
            d["podio"] = [trabajo_json(t, publico=True) for t in db.galeria(3, reto=r["id"], por_votos=True)]
        return d

    def tarjetas(lista: dict[str, config.Estilo], prefijo: str = "") -> list[dict]:
        return [{"id": e.id, "nombre": e.nombre, "emoji": e.emoji, "colores": e.colores,
                 "miniatura": miniatura_estilo(prefijo + e.id)} for e in lista.values()]

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

    @app.get("/img/{id_}/vista.webp")
    def vista_ligera(id_: str = Depends(id_valido)):
        ruta = aj.datos / "vistas" / f"{id_}.webp"
        if not ruta.exists():  # imágenes de antes: se hace la primera vez que se pide
            png = aj.datos / "imagenes" / f"{id_}.png"
            if not png.exists():
                raise HTTPException(404, "No existe")
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(png) as im:
                guardar_vista(im, ruta)
        return FileResponse(ruta, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/img/{id_}/tesela.webp")
    def tesela(id_: str = Depends(id_valido)):
        ruta = aj.datos / "teselas" / f"{id_}.webp"
        if not ruta.exists():  # imágenes de antes del mosaico: se hace la primera vez que se pide
            mini = aj.datos / "miniaturas" / f"{id_}.webp"
            if not mini.exists():
                raise HTTPException(404, "No existe")
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(mini) as im:
                guardar_tesela(im, ruta)
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
        if estilo_id not in aj.estilos and estilo_id.removeprefix("tema-") not in aj.temas:
            raise HTTPException(404, "No existe")
        ruta = aj.datos / "estilos" / f"{estilo_id}.webp"
        if not ruta.exists():
            raise HTTPException(404, "No existe")
        return FileResponse(ruta, media_type="image/webp")

    def recurso(ruta: Path | None, nombre: str) -> str | None:
        return f"/{nombre}?v={int(ruta.stat().st_mtime)}" if ruta and ruta.exists() else None

    @app.get("/logo")
    def logo(alto: int = 0):
        if not aj.logo or not aj.logo.exists():
            raise HTTPException(404, "Sin logo")
        if alto in ALTOS_LOGO and aj.logo.suffix.lower() != ".svg":
            return servir_reducida(aj.logo, alto=alto)
        return FileResponse(aj.logo)

    @app.get("/cartel")
    def cartel(ancho: int = 0):
        if not aj.cartel or not aj.cartel.exists():
            raise HTTPException(404, "Sin cartel")
        if ancho in ANCHOS_CARTEL:
            return servir_reducida(aj.cartel, ancho=ancho)
        return FileResponse(aj.cartel)

    @app.get("/tema.css")
    def tema_css():
        variables = {config.COLORES_CSS[k]: v for k, v in aj.colores.items()}
        if "fondo" in aj.colores:
            r, g, b = (int(aj.colores["fondo"][i:i + 2], 16) for i in (1, 3, 5))
            variables["--noche-2"] = "#%02x%02x%02x" % tuple(min(255, c + 18) for c in (r, g, b))
            variables["--tinta"] = aj.colores["fondo"]  # texto sobre botones claros
        cuerpo = "".join(f"{k}:{v};" for k, v in variables.items())
        return Response(f":root{{{cuerpo}}}" if cuerpo else "", media_type="text/css")

    @app.get("/qr.svg")
    def qr():
        buffer = io.BytesIO()
        oscuro = aj.colores.get("fondo", "#1a0b2e")
        segno.make(url(), error="m").save(buffer, kind="svg", scale=10, border=2, dark=oscuro, light="#ffffff")
        return Response(buffer.getvalue(), media_type="image/svg+xml")

    # --- API del alumnado ---

    @app.get("/api/info")
    def info():
        return {
            "version": VERSION,
            "evento": aj.evento,
            "subtitulo": aj.subtitulo,
            "requiere_codigo": bool(aj.codigo),
            "abierto": estudio.abierto,
            "comfy_ok": estudio.comfy_info is not None,
            "en_cola": len(estudio.cola),
            "media": round(estudio.media(), 1),
            "max_caracteres": aj.max_caracteres,
            "url": url(),
            "congreso": aj.congreso,
            "lema": aj.lema,
            "centro": aj.centro,
            "logo": recurso(aj.logo, "logo"),
            "cartel": recurso(aj.cartel, "cartel"),
            "estilos": tarjetas(aj.estilos),
            "temas": tarjetas(aj.temas, "tema-"),
            "formatos": [{"id": f.id, "ancho": f.ancho, "alto": f.alto} for f in aj.formatos.values()],
            "fotos": estudio.nodos.admite_fotos and aj.fotos,
            "sencillo": aj.sencillo,
            "estilo_sencillo": aj.estilo_sencillo,
            "formato_sencillo": aj.formato_sencillo,
            "fuerzas": [] if estudio.nodos.edita else list(aj.fuerzas),  # FLUX.2 Klein edita: no hay fuerza
            "ideas": aj.ideas,
            "detalles": aj.detalles,
            "reto": reto_json(reto_actual()),
            "concurso": concurso(),
        }

    @app.post("/api/entrar")
    def entrar(e: Entrada):
        alias = " ".join(e.alias.split())[:24] or f"{secrets.choice(ALIAS_DE_CARNAVAL)} {secrets.randbelow(90) + 10}"
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
        estilo, tema = aj.estilos.get(pedido.estilo), aj.temas.get(pedido.tema)
        if not estilo or (pedido.tema and not tema):
            raise HTTPException(422, "Elige un estilo.")
        if filtro.bloqueada(prompt):
            raise HTTPException(422, "Tu idea incluye palabras que no están permitidas en el estudio. Prueba a contarla de otra forma.")

        # Las imágenes con foto también son públicas: como todas, pasan antes por la revisión del profesor
        formato, foto, fuerza, publico = aj.formatos.get(pedido.formato), None, None, True
        if pedido.foto:
            ruta = aj.datos / "fotos" / f"{pedido.foto}.jpg"
            if not ID_VALIDO.match(pedido.foto) or not ruta.exists():
                raise HTTPException(422, "La foto ya no está. Vuelve a elegirla.")
            if not estudio.nodos.edita and pedido.fuerza not in aj.fuerzas:
                raise HTTPException(422, "Elige cuánto quieres transformar la foto.")
            with Image.open(ruta) as im:
                foto = (pedido.foto, *im.size)
            fuerza = None if estudio.nodos.edita else aj.fuerzas[pedido.fuerza]
        elif not formato:
            raise HTTPException(422, "Elige un formato.")

        activos = estudio.activos_de(p["token"])
        if len(activos) >= aj.en_cola_por_persona:
            return JSONResponse({"detail": "Ya tienes una imagen en marcha.", "id": activos[0]}, status_code=409)
        r = reto_actual()
        # Una idea de Inspírame sin tocar lleva su prompt optimizado para FLUX.2 (config/estilos.json)
        listo = None if foto or tema else aj.prompts_ideas.get(config.normalizar(prompt))
        id_ = estudio.encolar(p["token"], p["alias"], prompt, estilo, formato, tema=tema, foto=foto, fuerza=fuerza,
                              publico=publico, reto=r["id"] if r and r["fase"] == "creando" else None,
                              revision="pendiente" if publico and revisar_antes() else "aprobada", prompt_listo=listo)
        log.info("%s pide: %s [%s%s%s]", p["alias"], prompt, estilo.id,
                 f" · {tema.id}" if tema else "", " · con foto" if foto else "")
        return trabajo_json(db.trabajo(id_))

    @app.post("/api/fotos")
    def subir_foto(f: FotoSubida, p: dict = Depends(persona)):
        if p["bloqueado"]:
            raise HTTPException(403, "Tu acceso al estudio está en pausa. Habla con el profesor.")
        if not estudio.abierto:
            raise HTTPException(423, "El estudio está cerrado ahora mismo.")
        if not estudio.nodos.admite_fotos or not aj.fotos:
            raise HTTPException(422, "Este estudio no admite fotos.")
        try:
            id_, ancho, alto = fotos.guardar(f.datos, aj.datos / "fotos")
        except fotos.FotoNoValida as e:
            raise HTTPException(422, str(e)) from e
        return {"id": id_, "ancho": ancho, "alto": alto}

    @app.post("/api/trabajos/{id_}/voto")
    def votar(v: Interruptor, id_: str = Depends(id_valido), p: dict = Depends(persona)):
        t = db.trabajo(id_)
        if not t or t["estado"] != "hecho" or t["revision"] != "aprobada" or not t["publico"] or t["miniatura_estilo"]:
            raise HTTPException(404, "Esa imagen no está en la galería.")
        if t["token"] == p["token"]:
            raise HTTPException(422, "No puedes votar tu propia imagen 😉")
        if p["bloqueado"]:
            raise HTTPException(403, "Tu acceso al estudio está en pausa.")
        if vista() == "podio":
            raise HTTPException(423, "La votación está cerrada: ¡mira las ganadoras en la pantalla! 🏆")
        return {"votos": db.votar(id_, p["token"], v.valor), "votado": v.valor}

    @app.get("/api/votar")
    def para_votar(ambito: str = "todo", p: dict = Depends(persona)):
        """Imágenes para votar de una en una. Con ambito=reto, solo las del reto en marcha."""
        r = reto_actual()
        filas = db.para_votar(p["token"], 150, reto=r["id"] if ambito == "reto" and r else None)
        return {"abierta": vista() != "podio",
                "imagenes": [trabajo_json(t, publico=True, token=p["token"]) for t in filas]}

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
        return [trabajo_json(t, publico=True, token=p["token"]) for t in db.de_persona(p["token"])]

    # --- Proyector ---

    @app.get("/api/galeria")
    def galeria(limite: int = 30, ambito: str = "todo", orden: str = "recientes", ranking: bool = False,
                antes: float | None = None, x_token: str | None = Header(None)):
        """Galería de la clase (alumnado) y datos del proyector. Solo imágenes públicas y aprobadas."""
        p = db.persona(x_token) if x_token else None
        token = p["token"] if p else ""
        r = reto_actual()
        limite = min(max(limite, 1), 100)
        if ambito == "reto":
            filas = db.galeria(limite, reto=r["id"], por_votos=orden == "votos", token=token) if r else []
        else:
            filas = db.galeria(limite, por_votos=orden == "votos", token=token,
                               antes=antes if orden != "votos" else None)
        respuesta = {
            "abierto": estudio.abierto,
            "en_cola": len(estudio.cola),
            "url": url(),
            "total": db.estadisticas()["hechas"],
            "reto": reto_json(r),
            "concurso": concurso(),
            "en_revision": db.cuantas_por_revisar(),
            "imagenes": [trabajo_json(t, publico=True, token=token) for t in filas],
        }
        if ranking:
            respuesta["ranking"] = [trabajo_json(t, publico=True) for t in db.galeria(3, por_votos=True) if t["votos"]]
        return respuesta

    @app.get("/api/mosaico")
    def mosaico():
        """Las últimas imágenes públicas, en el orden en que se aprobaron: cada una es una pieza del mosaico.

        `primera` es el número de orden de la primera pieza: la pieza n va siempre al mismo hueco
        (n módulo huecos), así que cuando el mosaico se llena, cada nueva sustituye a la más antigua."""
        filas = db.mosaico(aj.piezas_mosaico)
        total = db.cuantas_visibles()
        return {
            "maximo": aj.piezas_mosaico,
            "total": total,
            "primera": total - len(filas),
            "piezas": [{"id": t["id"], "alias": t["alias"], "prompt": t["prompt"], "votos": t["votos"],
                        "tesela": f"/img/{t['id']}/tesela.webp", "mini": f"/img/{t['id']}/mini.webp",
                        "imagen": f"/img/{t['id']}/vista.webp"}
                       for t in filas],
            "en_revision": db.cuantas_por_revisar(),
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
            "comfy": {"ok": info_comfy is not None, "url": comfy.url, "auto": len(comfy.candidatas) > 1, "gpu": gpu},
            "cola": cola,
            "media": round(estudio.media(), 1),
            "estadisticas": db.estadisticas(),
            "url_alumnado": url(),
            "direccion": direccion_actual(),
            "direcciones": direcciones(),
            "direccion_fija": bool(aj.direccion),
            "codigo": aj.codigo,
            "avisos": estudio.avisos + estudio.faltan,
            "modelo": estudio.modelo(),
            "bloqueados": db.bloqueados(),
            "local": es_local(request),
            "internet": {"activado": True, "listo": tunel.listo, "url": tunel.url, "detalle": tunel.detalle}
                        if tunel else {"activado": False},
            "panel_remoto": panel_remoto,
            "reto": reto_json(reto_actual()),
            "concurso": concurso(),
            "por_revisar": db.cuantas_por_revisar(),
            "simulacro": aj.datos.name == config.CARPETA_SIMULACRO,
            "interprete": {"activado": True, "ok": interprete.ok, "modelo": interprete.modelo,
                           "detalle": interprete.detalle, **db.ideas_mejoradas()} if interprete else {"activado": False},
        }

    @app.post("/api/panel/reto", dependencies=[Depends(profesor)])
    def lanzar_reto(n: NuevoReto):
        titulo = " ".join(n.titulo.split())[:80]
        if not titulo:
            raise HTTPException(422, "Escribe el tema del reto.")
        minutos = min(max(n.minutos, 0), 180)
        db.crear_reto(titulo, time.time() + minutos * 60 if minutos else None)
        log.info("Nuevo reto: «%s» (%s)", titulo, f"{minutos} min" if minutos else "sin límite")
        return reto_json(reto_actual())

    @app.post("/api/panel/reto/fase", dependencies=[Depends(profesor)])
    def fase_reto(f: Fase):
        r = reto_actual()
        if not r:
            raise HTTPException(404, "No hay ningún reto en marcha.")
        if f.fase not in FASES_RETO:
            raise HTTPException(422, "Fase desconocida.")
        db.fase_reto(r["id"], f.fase)
        return reto_json(db.reto_activo())

    @app.post("/api/panel/abierto", dependencies=[Depends(profesor)])
    def abrir(i: Interruptor):
        estudio.abrir(i.valor)
        log.info("Estudio %s", "abierto" if i.valor else "cerrado")
        return {"abierto": estudio.abierto}

    @app.post("/api/panel/direccion", dependencies=[Depends(profesor)])
    def elegir_direccion(d: Direccion):
        if aj.direccion:
            raise HTTPException(409, "La dirección está fijada en config/ajustes.toml (direccion).")
        if d.direccion not in direcciones():
            raise HTTPException(422, "Esa dirección no es de este PC.")
        db.guardar_estado("direccion", d.direccion)
        return {"url_alumnado": url()}

    @app.post("/api/panel/cancelar/{id_}", dependencies=[Depends(profesor)])
    async def cancelar(id_: str = Depends(id_valido)):
        return {"ok": await estudio.cancelar(id_)}

    @app.get("/api/panel/imagenes", dependencies=[Depends(profesor)])
    def imagenes(antes: float | None = None, limite: int = 60):
        filas = db.galeria(min(max(limite, 1), 200), panel=True, antes=antes)
        return [trabajo_json(t, publico=True) | {"token": t["token"], "prompt_ia": t.get("prompt_ia") or ""}
                for t in filas]

    @app.get("/api/panel/revision", dependencies=[Depends(profesor)])
    def revision(limite: int = 40):
        """Imágenes que esperan la aprobación del profesor, de la más antigua a la más nueva."""
        filas = db.por_revisar(min(max(limite, 1), 200))
        return {"total": db.cuantas_por_revisar(),
                "imagenes": [trabajo_json(t, publico=True) | {"token": t["token"], "prompt_ia": t.get("prompt_ia") or ""}
                             for t in filas]}

    @app.post("/api/panel/revisar", dependencies=[Depends(profesor)])
    def revisar(r: Revision):
        if r.decision not in ("aprobada", "rechazada"):
            raise HTTPException(422, "Decisión desconocida.")
        ids = [i for i in r.ids if ID_VALIDO.match(i)]
        cambiadas = db.revisar(ids, r.decision)
        log.info("%s %d %s", "Publica" if r.decision == "aprobada" else "Rechaza", cambiadas,
                 "imagen" if cambiadas == 1 else "imágenes")
        return {"cambiadas": cambiadas, "por_revisar": db.cuantas_por_revisar()}

    @app.post("/api/panel/moderacion", dependencies=[Depends(profesor)])
    def moderacion(i: Interruptor):
        db.guardar_estado("revisar_antes", "1" if i.valor else "0")
        log.info("Revisión antes de publicar: %s", "sí" if i.valor else "no")
        return concurso()

    @app.post("/api/panel/proyector", dependencies=[Depends(profesor)])
    def elegir_vista(v: Vista):
        if v.vista not in VISTAS_PROYECTOR:
            raise HTTPException(422, "Vista desconocida.")
        db.guardar_estado("vista_proyector", v.vista)
        log.info("Proyector: %s", v.vista)
        return concurso()

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
        tecnica = aj.estilos.get("foto") or next(iter(aj.estilos.values()))
        for tema in aj.temas.values():
            estudio.encolar("profesor", "Profe", tema.ejemplo, tecnica, formato, tema=tema,
                            miniatura_estilo=f"tema-{tema.id}")
        return {"encoladas": len(aj.estilos) + len(aj.temas)}

    return app
