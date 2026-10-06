"""Flujo completo contra el ComfyUI simulado."""

import io
import time

from fastapi.testclient import TestClient
from PIL import Image

from app.main import crear_app
from tests.conftest import preparar_ajustes, puerto_libre

PROFE = {"X-Clave": "secreta"}


def entrar(c, alias="Ana"):
    r = c.post("/api/entrar", json={"alias": alias, "codigo": "CARNAVAL"})
    assert r.status_code == 200, r.text
    return {"X-Token": r.json()["token"]}


def esperar_fin(c, id_, h, limite=10):
    fin = time.time() + limite
    while time.time() < fin:
        t = c.get(f"/api/trabajos/{id_}", headers=h).json()
        if t["estado"] in ("hecho", "error", "cancelado"):
            return t
        time.sleep(0.05)
    raise AssertionError(f"El trabajo no terminó: {t}")


def test_flujo_completo(ajustes, comfy_falso):
    _, comfy_app = comfy_falso
    with TestClient(crear_app(ajustes)) as c:
        info = c.get("/api/info").json()
        assert info["requiere_codigo"] and len(info["estilos"]) > 5

        h = entrar(c)
        r = c.post("/api/crear", json={"prompt": "Un gato con antifaz", "estilo": "cartel", "formato": "vertical"}, headers=h)
        assert r.status_code == 200, r.text
        id_ = r.json()["id"]

        # Una imagen en marcha por persona
        r = c.post("/api/crear", json={"prompt": "Otra cosa", "estilo": "foto", "formato": "cuadrado"}, headers=h)
        assert r.status_code == 409 and r.json()["id"] == id_

        t = esperar_fin(c, id_, h)
        assert t["estado"] == "hecho"
        im = Image.open(io.BytesIO(c.get(t["imagen"]).content))
        assert im.size == (832, 1216)
        assert c.get(t["mini"]).headers["content-type"] == "image/webp"
        assert "attachment" in c.get(t["imagen"] + "?descargar=1").headers["content-disposition"]

        enviado = comfy_app.state.recibidos[-1]
        assert enviado["6"]["inputs"]["text"].startswith("Vintage carnival festival poster: Un gato con antifaz")

        assert [x["id"] for x in c.get("/api/mis-creaciones", headers=h).json()] == [id_]
        assert c.get("/api/galeria").json()["imagenes"][0]["id"] == id_

        # Panel: requiere clave desde fuera del PC
        assert c.get("/api/panel/estado").status_code == 401
        estado = c.get("/api/panel/estado", headers=PROFE).json()
        assert estado["comfy"]["ok"] and estado["comfy"]["gpu"]["nombre"] == "cuda:0 NVIDIA GeForce RTX 5070"
        assert estado["estadisticas"]["hechas"] == 1

        # Ocultar del proyector
        assert c.post(f"/api/panel/ocultar/{id_}", json={"valor": True}, headers=PROFE).status_code == 200
        assert c.get("/api/galeria").json()["imagenes"] == []
        assert c.get("/api/panel/imagenes", headers=PROFE).json()[0]["oculto"] is True


def test_validaciones_y_moderacion(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        assert c.post("/api/entrar", json={"alias": "Ana", "codigo": "otro"}).status_code == 403
        assert c.post("/api/entrar", json={"alias": "   ", "codigo": "carnaval"}).status_code == 422
        h = entrar(c)
        pedido = {"estilo": "foto", "formato": "cuadrado"}
        r = c.post("/api/crear", json={"prompt": "Una persona desnuda", **pedido}, headers=h)
        assert r.status_code == 422 and "no están permitidas" in r.json()["detail"]
        assert c.post("/api/crear", json={"prompt": "ab", **pedido}, headers=h).status_code == 422
        assert c.post("/api/crear", json={"prompt": "Un perro", "estilo": "x", "formato": "cuadrado"}, headers=h).status_code == 422
        assert c.post("/api/crear", json={"prompt": "Un perro", **pedido}, headers={"X-Token": "falso"}).status_code == 401


def test_estudio_cerrado_y_bloqueo(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        pedido = {"prompt": "Un perro bailando", "estilo": "foto", "formato": "cuadrado"}
        c.post("/api/panel/abierto", json={"valor": False}, headers=PROFE)
        assert c.post("/api/crear", json=pedido, headers=h).status_code == 423
        c.post("/api/panel/abierto", json={"valor": True}, headers=PROFE)

        token = h["X-Token"]
        c.post("/api/panel/bloquear", json={"token": token, "valor": True}, headers=PROFE)
        assert c.post("/api/crear", json=pedido, headers=h).status_code == 403
        assert c.get("/api/panel/estado", headers=PROFE).json()["bloqueados"][0]["alias"] == "Ana"
        c.post("/api/panel/bloquear", json={"token": token, "valor": False}, headers=PROFE)
        assert c.post("/api/crear", json=pedido, headers=h).status_code == 200


def test_error_de_comfy_llega_al_alumno(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        r = c.post("/api/crear", json={"prompt": "Esto FALLA seguro", "estilo": "libre", "formato": "cuadrado"}, headers=h)
        t = esperar_fin(c, r.json()["id"], h)
        assert t["estado"] == "error" and "out of memory" in t["error"]
        # Puede volver a intentarlo
        r = c.post("/api/crear", json={"prompt": "Un perro", "estilo": "libre", "formato": "cuadrado"}, headers=h)
        assert esperar_fin(c, r.json()["id"], h)["estado"] == "hecho"


def test_turnos_y_cancelar_en_cola(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        ana, luis = entrar(c, "Ana"), entrar(c, "Luis")
        pedido = {"prompt": "Un desfile de robots", "estilo": "foto", "formato": "cuadrado"}
        id_ana = c.post("/api/crear", json=pedido, headers=ana).json()["id"]
        t_luis = c.post("/api/crear", json=pedido, headers=luis).json()
        assert t_luis["delante"] == 1 and t_luis["segundos"] > 0
        assert c.post(f"/api/trabajos/{t_luis['id']}/cancelar", headers=luis).status_code == 200
        assert c.get(f"/api/trabajos/{t_luis['id']}", headers=luis).json()["estado"] == "cancelado"
        # Nadie ve trabajos ajenos
        assert c.get(f"/api/trabajos/{id_ana}", headers=luis).status_code == 404
        assert esperar_fin(c, id_ana, ana)["estado"] == "hecho"


def test_miniaturas_de_estilos(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        n = c.post("/api/panel/miniaturas", headers=PROFE).json()["encoladas"]
        fin = time.time() + 20
        while time.time() < fin and any(e["miniatura"] is None for e in c.get("/api/info").json()["estilos"]):
            time.sleep(0.1)
        estilos = c.get("/api/info").json()["estilos"]
        assert n == len(estilos) and all(e["miniatura"] for e in estilos)
        assert c.get(estilos[0]["miniatura"]).headers["content-type"] == "image/webp"
        # No aparecen en el proyector ni cuentan como imágenes del alumnado
        assert c.get("/api/galeria").json()["imagenes"] == []


def test_sin_comfy_la_imagen_espera_en_cola(tmp_path, monkeypatch):
    ajustes = preparar_ajustes(tmp_path, monkeypatch, f"http://127.0.0.1:{puerto_libre()}")
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        t = c.post("/api/crear", json={"prompt": "Un perro", "estilo": "foto", "formato": "cuadrado"}, headers=h).json()
        time.sleep(0.5)
        t = c.get(f"/api/trabajos/{t['id']}", headers=h).json()
        assert t["estado"] == "cola" and t["comfy_ok"] is False
        assert c.get("/api/info").json()["comfy_ok"] is False


def test_qr_y_paginas(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        assert c.get("/qr.svg").headers["content-type"] == "image/svg+xml"
        for ruta in ("/", "/panel", "/proyector", "/static/alumno.js"):
            assert c.get(ruta).status_code == 200
        assert c.get("/img/../../config/ajustes.toml").status_code == 404


def test_elegir_direccion_del_qr(ajustes, monkeypatch):
    monkeypatch.setattr("app.main.direcciones_locales", lambda: ["192.168.1.50", "172.20.0.1"])
    with TestClient(crear_app(ajustes)) as c:
        e = c.get("/api/panel/estado", headers=PROFE).json()
        assert e["direcciones"] == ["192.168.1.50", "172.20.0.1"]
        assert e["url_alumnado"] == "http://192.168.1.50:8080/?c=carnaval"
        assert c.post("/api/panel/direccion", json={"direccion": "8.8.8.8"}, headers=PROFE).status_code == 422
        r = c.post("/api/panel/direccion", json={"direccion": "172.20.0.1"}, headers=PROFE)
        assert r.json()["url_alumnado"] == "http://172.20.0.1:8080/?c=carnaval"
        assert c.get("/api/info").json()["url"] == "http://172.20.0.1:8080/?c=carnaval"
        assert c.get("/api/galeria").json()["url"] == "http://172.20.0.1:8080/?c=carnaval"
        assert c.post("/api/panel/direccion", json={"direccion": "192.168.1.50"}).status_code == 401
