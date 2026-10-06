import shutil
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from app import config
from tests.comfy_falso import crear_comfy_falso

RAIZ = Path(__file__).resolve().parent.parent


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Servidor(uvicorn.Server):
    def install_signal_handlers(self):
        pass


@pytest.fixture
def comfy_falso():
    puerto = puerto_libre()
    app = crear_comfy_falso(retardo_paso=0.02, fallar_con="FALLA")
    servidor = Servidor(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{puerto}", app
    servidor.should_exit = True
    hilo.join(5)


def preparar_ajustes(tmp_path, monkeypatch, url_comfy: str) -> config.Ajustes:
    carpeta = tmp_path / "config"
    carpeta.mkdir()
    shutil.copy(RAIZ / "config" / "estilos.json", carpeta)
    toml = (RAIZ / "config" / "ajustes.toml").read_text(encoding="utf-8")
    toml = (
        toml.replace('url = "auto"', f'url = "{url_comfy}"')
        .replace('clave_profesor = "cambia-esta-clave"', 'clave_profesor = "secreta"')
        .replace('workflow = "config/workflow_api.json"',
                 f'workflow = "{(RAIZ / "config" / "workflow_api.json").as_posix()}"')
    )
    (carpeta / "ajustes.toml").write_text(toml, encoding="utf-8")
    monkeypatch.setenv("ESTUDIO_DATOS", str(tmp_path / "datos"))
    return config.cargar(carpeta / "ajustes.toml")


@pytest.fixture
def ajustes(tmp_path, monkeypatch, comfy_falso):
    return preparar_ajustes(tmp_path, monkeypatch, comfy_falso[0])
