"""Intérprete de ideas (Ollama simulado) delante del ComfyUI simulado."""

import re
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
        assert estado == {"activado": True, "ok": True, "modelo": "qwen2.5:3b", "detalle": "listo",
                          "ideas": 0, "mejoradas": 0}
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


def test_esperando_al_interprete_todas_las_ideas_salen_mejoradas(ajustes, comfy_falso, tmp_path):
    """Con FLUX.2 Klein la gráfica va más rápida que el intérprete: con esperar = true, ninguna idea se lo salta."""
    puerto = puerto_libre()
    lento = crear_ollama_falso(retardo=0.4)  # el intérprete tarda más que el ComfyUI simulado
    servidor = Servidor(uvicorn.Config(lento, host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.02)
    try:
        ajustes.interprete_activado, ajustes.interprete_url = True, f"http://127.0.0.1:{puerto}"
        assert ajustes.interprete_esperar  # lo normal
        with TestClient(crear_app(ajustes)) as c:
            esperar_interprete(c)
            ids = []
            for n in range(4):  # cuatro personas a la vez
                h = entrar(c, f"Persona {n}")
                r = c.post("/api/crear", json={"prompt": f"Idea {n}", "estilo": "carnaval", "formato": "cuadrado"},
                           headers=h)
                ids.append((r.json()["id"], h))
            for id_, h in ids:
                assert esperar_fin(c, id_, h, limite=20)["estado"] == "hecho"
            estado = c.get("/api/panel/estado", headers=PROFE).json()["interprete"]
            assert estado["ideas"] == estado["mejoradas"] == 4
            textos = [wf["6"]["inputs"]["text"] for wf in comfy_falso[1].state.recibidos[-4:]]
            assert all(x.startswith("A vivid carnival scene of Idea") and "Santa Cruz de Tenerife" in x for x in textos)
            assert "num_gpu" in lento.state.recibidos[-1]["options"]  # en el procesador
    finally:
        servidor.should_exit = True
        hilo.join(5)


def test_interprete_en_la_grafica_y_ambientacion_de_carnaval(ajustes, ollama):
    import asyncio

    from app.interprete import Interprete
    from app.moderacion import Filtro

    url, ollama_app = ollama

    async def pedir():
        ia = Interprete(url, "qwen2.5:3b", Filtro([]), grafica=True)
        try:
            return await ia.interpretar("un gato")
        finally:
            await ia.cerrar()

    assert asyncio.run(pedir()) == "A vivid carnival scene of un gato."
    pedido = ollama_app.state.recibidos[-1]
    assert "num_gpu" not in pedido["options"]  # en la gráfica: Ollama decide
    ejemplos = [m["content"] for m in pedido["messages"] if m["role"] == "user"]
    assert len(ejemplos) == 6 and "murga" in pedido["messages"][0]["content"]
    carnaval = ajustes.estilos["carnaval"]
    texto = carnaval.aplicar("A purple octopus murga singing on stage.")
    assert texto.startswith("A purple octopus murga singing on stage. Vibrant editorial photography at the Carnival "
                            "of Santa Cruz de Tenerife")
    assert ".." not in texto
    assert ajustes.estilos["libre"].aplicar("Una idea.") == "Una idea."


def test_ideas_de_inspirame_con_prompt_optimizado(ajustes, comfy_falso, ollama):
    """Una idea de Inspírame sin tocar va con su prompt para FLUX.2; si la persona la cambia, pasa por el intérprete."""
    url, ollama_app = ollama
    ajustes.interprete_activado, ajustes.interprete_url = True, url
    idea = ajustes.ideas[0]
    optimizado = ajustes.prompts_ideas[idea.lower()]
    with TestClient(crear_app(ajustes)) as c:
        esperar_interprete(c)
        assert c.get("/api/info").json()["ideas"][0] == idea  # el móvil ve la idea en español
        h = entrar(c)
        antes = len(ollama_app.state.recibidos)
        r = c.post("/api/crear", json={"prompt": f"  {idea.upper()}. ", "estilo": "carnaval", "formato": "cuadrado"},
                   headers=h)
        t = esperar_fin(c, r.json()["id"], h)
        assert t["estado"] == "hecho" and t["prompt"] == f"{idea.upper()}."
        enviado = comfy_falso[1].state.recibidos[-1]["6"]["inputs"]["text"]
        assert enviado == ajustes.estilos["carnaval"].aplicar(optimizado)  # el estilo (foto) lo pone la receta
        assert len(ollama_app.state.recibidos) == antes  # sin intérprete
        img = c.get("/api/panel/imagenes", headers=PROFE).json()[0]
        assert img["prompt_ia"] == optimizado

        # Cambiada: pasa por el intérprete y lleva la ambientación de carnaval
        h2 = entrar(c, "Otra")
        r = c.post("/api/crear", json={"prompt": idea + " con sombrero", "estilo": "carnaval", "formato": "cuadrado"},
                   headers=h2)
        esperar_fin(c, r.json()["id"], h2)
        enviado = comfy_falso[1].state.recibidos[-1]["6"]["inputs"]["text"]
        assert enviado.startswith("A vivid carnival scene of") and "Vibrant editorial photography" in enviado


def test_lista_de_prompts_optimizados(ajustes):
    assert len(ajustes.ideas) >= 30 and len(ajustes.prompts_ideas) == len(ajustes.ideas)
    for prompt in ajustes.prompts_ideas.values():
        palabras = len(prompt.split())
        assert 30 <= palabras <= 80, prompt  # FLUX.2: frases completas, ni muy cortas ni kilométricas
        assert not re.search(r"\b(no|not|without|avoid|never)\b", prompt, re.I), prompt  # sin negativos
        assert not re.search(r"photo|cinematic|bokeh|depth of field|macro|drone", prompt, re.I), prompt  # sin estilo
    # El estilo lo pone la receta: foto sin modelo propio, dibujo con tu modelo o tu LoRA
    assert "photography" in ajustes.estilos["carnaval"].receta
    dibujo = ajustes.estilos["carnaval-dibujo"].receta
    assert "Illustration" in dibujo and "photo" not in dibujo.lower()
