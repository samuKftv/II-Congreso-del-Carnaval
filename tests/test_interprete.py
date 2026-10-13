"""Intérprete de ideas (Ollama simulado) delante del ComfyUI simulado."""

import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.main import crear_app
from tests.conftest import Servidor, puerto_libre
from tests.ollama_falso import crear_ollama_falso
from tests.test_estudio import PROFE, entrar, esperar_fin


@pytest.fixture
def ollama():
    puerto = puerto_libre()
    app = crear_ollama_falso(retardo=0.05)
    servidor = Servidor(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{puerto}", app
    servidor.should_exit = True
    hilo.join(5)


def crear(c, h, prompt, **extra):
    r = c.post("/api/crear", json={"prompt": prompt, "estilo": "cartel", "tema": "venecia", "formato": "cuadrado", **extra}, headers=h)
    assert r.status_code == 200, r.text
    return esperar_fin(c, r.json()["id"], h)


def esperar_interprete(c):
    fin = time.time() + 10
    while time.time() < fin:
        if c.get("/api/panel/estado", headers=PROFE).json()["interprete"]["ok"]:
            return
        time.sleep(0.1)
    raise AssertionError("El intérprete no está listo")


def test_la_idea_se_interpreta_antes_de_pintarla(ajustes, comfy_falso, ollama):
    url, ollama_app = ollama
    ajustes.interprete_activado, ajustes.interprete_url = True, url
    with TestClient(crear_app(ajustes)) as c:
        esperar_interprete(c)
        estado = c.get("/api/panel/estado", headers=PROFE).json()["interprete"]
        assert estado == {"activado": True, "ok": True, "modelo": "qwen2.5:3b", "detalle": "listo"}
        h = entrar(c)
        t = crear(c, h, "Un gato con antifaz")

        pedido = ollama_app.state.recibidos[-1]
        assert pedido["options"]["num_gpu"] == 0  # en el procesador: la gráfica es para ComfyUI
        assert pedido["messages"][0]["role"] == "system" and pedido["messages"][-1]["content"] == "Un gato con antifaz"

        idea = "A vivid carnival scene of Un gato con antifaz."
        receta = ajustes.estilos["cartel"].aplicar(ajustes.temas["venecia"].aplicar(idea))
        assert comfy_falso[1].state.recibidos[-1]["6"]["inputs"]["text"] == receta
        img = c.get("/api/panel/imagenes", headers=PROFE).json()[0]
        assert img["prompt_ia"] == idea and img["prompt"] == "Un gato con antifaz"  # el alumno ve su idea
        assert t["prompt"] == "Un gato con antifaz"

        # Si el intérprete se pasa de la raya, se pinta la idea tal cual
        crear(c, h, "Algo PROHIBIDO")
        enviado = comfy_falso[1].state.recibidos[-1]["6"]["inputs"]["text"]
        assert "nude" not in enviado and "Algo PROHIBIDO" in enviado
        assert c.get("/api/panel/imagenes", headers=PROFE).json()[0]["prompt_ia"] == ""

        # Las miniaturas de estilos no pasan por el intérprete
        antes = len(ollama_app.state.recibidos)
        c.post("/api/panel/miniaturas", headers=PROFE)
        time.sleep(1)
        assert len(ollama_app.state.recibidos) == antes


def test_sin_ollama_se_pinta_la_idea_tal_cual(ajustes, comfy_falso):
    ajustes.interprete_activado, ajustes.interprete_url = True, f"http://127.0.0.1:{puerto_libre()}"
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        t = crear(c, h, "Un perro con sombrero")
        assert t["estado"] == "hecho"
        assert "Un perro con sombrero" in comfy_falso[1].state.recibidos[-1]["6"]["inputs"]["text"]
        estado = c.get("/api/panel/estado", headers=PROFE).json()["interprete"]
        assert estado["ok"] is False and "Ollama" in estado["detalle"]
