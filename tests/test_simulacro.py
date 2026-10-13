"""El simulacro de 3-PROBAR-CON-100-PERSONAS.bat contra el ComfyUI simulado."""

import asyncio
import threading
import time

import pytest
import uvicorn

from app import config
from app.main import crear_app
from app.simulacro import NoSePuede, Simulacro
from tests.conftest import Servidor, preparar_ajustes, puerto_libre


def arrancar(ajustes):
    puerto = puerto_libre()
    servidor = Servidor(uvicorn.Config(crear_app(ajustes), host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.02)
    return servidor, hilo, f"http://127.0.0.1:{puerto}"


def test_simulacro_con_jurado_automatico(tmp_path, monkeypatch, comfy_falso):
    ajustes = preparar_ajustes(tmp_path, monkeypatch, comfy_falso[0], revisar_antes=True)
    ajustes.datos = tmp_path / config.CARPETA_SIMULACRO
    servidor, hilo, url = arrancar(ajustes)
    lineas = []
    try:
        s = Simulacro(url, personas=6, segundos=12, publicar=True, aj=ajustes, salida=lineas.append, llegada=1)
        datos = asyncio.run(s.ejecutar())
    finally:
        servidor.should_exit = True
        hilo.join(5)
    assert datos["personas"] == 6 and datos["hechas"] >= 6 and datos["errores"] == 0
    assert datos["media"] > 0 and datos["respuesta_max"] < 2
    assert not s.activos  # al acabar no deja nada en cola
    texto = "\n".join(lineas)
    assert "RESUMEN DEL SIMULACRO" in texto and "por imagen" in texto


def test_simulacro_no_toca_los_datos_de_verdad(ajustes):
    servidor, hilo, url = arrancar(ajustes)
    try:
        s = Simulacro(url, personas=2, segundos=5, publicar=False, aj=ajustes, salida=lambda *_: None)
        with pytest.raises(NoSePuede, match="datos de verdad"):
            asyncio.run(s.ejecutar())
    finally:
        servidor.should_exit = True
        hilo.join(5)
