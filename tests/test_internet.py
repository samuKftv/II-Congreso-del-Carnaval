"""Modo internet: el túnel de Cloudflare (simulado) y que el panel no quede abierto a internet."""

import sys
import threading
import time

import httpx
import pytest
import uvicorn

from app.main import crear_app
from app.tunel import Tunel
from tests.conftest import Servidor, puerto_libre

URL = "https://risa-confeti-murga-tambor.trycloudflare.com"

# Imita lo que escribe cloudflared al abrir un túnel rápido
FALSO = f'''#!{sys.executable}
import sys, time
print("2026-10-15T09:00:00Z INF Requesting new quick Tunnel on trycloudflare.com...", flush=True)
print("2026-10-15T09:00:01Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |", flush=True)
print("2026-10-15T09:00:01Z INF |  {URL}                                               |", flush=True)
print("2026-10-15T09:00:02Z INF Registered tunnel connection connIndex=0 location=mad01 protocol=quic", flush=True)
time.sleep(60)
'''


@pytest.fixture
def cloudflared_falso(tmp_path, monkeypatch):
    ruta = tmp_path / "cloudflared"
    ruta.write_text(FALSO)
    ruta.chmod(0o755)
    monkeypatch.setattr("app.tunel.buscar_cloudflared", lambda: str(ruta))
    return str(ruta)


def esperar(condicion, limite=10):
    fin = time.time() + limite
    while time.time() < fin:
        if condicion():
            return True
        time.sleep(0.05)
    return False


def test_el_tunel_lee_la_direccion(cloudflared_falso):
    t = Tunel(8080)
    t.arrancar()
    try:
        assert esperar(lambda: t.listo)
        assert t.url == URL and t.detalle == "listo"
    finally:
        t.parar()


def test_sin_cloudflared_lo_dice(monkeypatch):
    monkeypatch.setattr("app.tunel.buscar_cloudflared", lambda: None)
    t = Tunel(8080)
    t.arrancar()  # no hace nada
    assert t.url is None and not t.listo and "falta cloudflared" in t.detalle


@pytest.fixture
def estudio_por_internet(ajustes, cloudflared_falso):
    ajustes.internet = True
    puerto = puerto_libre()
    servidor = Servidor(uvicorn.Config(crear_app(ajustes), host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{puerto}"
    servidor.should_exit = True
    hilo.join(5)


def test_qr_con_la_direccion_publica_y_panel_cerrado_a_internet(estudio_por_internet):
    c = httpx.Client(base_url=estudio_por_internet, trust_env=False)
    assert esperar(lambda: c.get("/api/info").json()["url"].startswith(URL))
    assert c.get("/api/info").json()["url"] == f"{URL}/?c=carnaval"
    estado = c.get("/api/panel/estado").json()  # desde este PC: sin clave
    assert estado["internet"] == {"activado": True, "listo": True, "url": URL, "detalle": "listo"}
    assert estado["local"] is True
    # Lo que llega por el túnel trae estas cabeceras: es de fuera, aunque entre por 127.0.0.1
    for cabecera in ({"Cf-Connecting-Ip": "85.1.2.3"}, {"X-Forwarded-For": "85.1.2.3"}, {"Cf-Ray": "abc-MAD"}):
        assert c.get("/api/panel/estado", headers=cabecera).status_code == 401
        assert c.post("/api/panel/abierto", json={"valor": False}, headers=cabecera).status_code == 401
    # La clave del profesor sí abre el panel desde fuera
    assert c.get("/api/panel/estado", headers={"Cf-Connecting-Ip": "85.1.2.3", "X-Clave": "secreta"}).status_code == 200
    # El público, por el túnel, entra y crea con normalidad
    r = c.post("/api/entrar", json={"alias": "Ana", "codigo": "carnaval"}, headers={"Cf-Connecting-Ip": "85.1.2.3"})
    assert r.status_code == 200
