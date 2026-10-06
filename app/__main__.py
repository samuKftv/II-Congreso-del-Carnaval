"""Arranque: python -m app"""

import logging
import sys
import threading
import tomllib
import webbrowser
from urllib.parse import urlparse

import uvicorn

from . import config
from .main import crear_app
from .workflow import ErrorWorkflow


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        aj = config.cargar()
        app = crear_app(aj)
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError, ErrorWorkflow) as e:
        print(f"\nNo se puede arrancar el estudio:\n  {e}\n")
        sys.exit(1)

    panel = f"http://127.0.0.1:{aj.puerto}/panel"
    linea = "=" * 64
    print(f"\n{linea}\n  {aj.evento} - {aj.subtitulo}\n{linea}")
    print(f"  Alumnado:   {app.state.url()}")
    print(f"  Panel:      {panel}")
    print(f"  Proyector:  http://127.0.0.1:{aj.puerto}/proyector")
    print(f"  ComfyUI:    {aj.comfy_url}")
    otras = [d for d in app.state.direcciones() if d != urlparse(app.state.url()).hostname]
    if otras and not aj.direccion:
        print(f"  Otras IP de este PC: {', '.join(otras)}")
        print("  (Si el movil no abre la pagina, elige otra en el panel, junto al QR.)")
    if not app.state.panel_remoto:
        print("  (El panel solo se abre desde este PC: pon una clave_profesor en config/ajustes.toml")
        print("   si quieres abrirlo desde otro dispositivo.)")
    print(f"{linea}\n  Deja esta ventana abierta. Para parar el estudio, ciérrala.\n{linea}\n")

    if aj.abrir_navegador:
        threading.Timer(1.5, webbrowser.open, [panel]).start()
    uvicorn.run(app, host="0.0.0.0", port=aj.puerto, log_level="warning")


if __name__ == "__main__":
    main()
