"""Arranque: python -m app"""

import json
import logging
import socket
import sys
import threading
import tomllib
import urllib.request
import webbrowser
from urllib.parse import urlparse

import uvicorn

from . import VERSION, config
from .main import crear_app
from .workflow import ErrorWorkflow


def puerto_ocupado(puerto: int) -> str | None:
    """Si el puerto está en uso, explica por qué (otro estudio abierto u otro programa)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", puerto))
            return None
        except OSError:
            pass
    try:
        directo = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # sin proxy del centro
        with directo.open(f"http://127.0.0.1:{puerto}/api/info", timeout=3) as r:
            info = json.load(r)
        version = info.get("version", "anterior")
        return (f"Ya hay un Estudio abierto en el puerto {puerto} (versión {version}).\n"
                "  Cierra esa otra ventana negra del estudio y vuelve a abrir este.")
    except (OSError, ValueError):
        return (f"El puerto {puerto} lo está usando otro programa.\n"
                "  Ciérralo o cambia el puerto en config/ajustes.toml (y en el archivo del firewall).")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        aj = config.cargar()
        app = crear_app(aj)
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError, ErrorWorkflow) as e:
        print(f"\nNo se puede arrancar el estudio:\n  {e}\n")
        sys.exit(1)

    if problema := puerto_ocupado(aj.puerto):
        print(f"\nNo se puede arrancar el estudio:\n  {problema}\n")
        sys.exit(1)

    panel = f"http://127.0.0.1:{aj.puerto}/panel"
    linea = "=" * 64
    print(f"\n{linea}\n  {aj.evento} - {aj.subtitulo} (version {VERSION})\n{linea}")
    print(f"  Alumnado:   {app.state.url()}")
    print(f"  Panel:      {panel}")
    print(f"  Proyector:  http://127.0.0.1:{aj.puerto}/proyector")
    print(f"  ComfyUI:    {'se busca solo en los puertos 8188 y 8000' if aj.comfy_url == 'auto' else aj.comfy_url}")
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
    uvicorn.run(app, host="0.0.0.0", port=aj.puerto, log_level="warning", use_colors=False)


if __name__ == "__main__":
    main()
