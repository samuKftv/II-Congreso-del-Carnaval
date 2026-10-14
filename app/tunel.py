"""Modo internet: un túnel gratuito de Cloudflare (sin cuenta) da al estudio una dirección pública https.

Así los móviles entran con sus datos o con cualquier WiFi, aunque la red del recinto aísle los dispositivos.
Solo hace falta que el PC tenga internet. El túnel sale del PC hacia Cloudflare: no hay que abrir nada.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config import RAIZ

log = logging.getLogger("estudio")

DIRECCION = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com")
LISTO = re.compile(r"Registered tunnel connection|Connection [0-9a-f-]+ registered", re.I)
SITIOS = [
    RAIZ / "cloudflared.exe",
    RAIZ / "cloudflared",
    Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
    Path(r"C:\Program Files\cloudflared\cloudflared.exe"),
]


def buscar_cloudflared() -> str | None:
    for ruta in SITIOS:
        if ruta.is_file():
            return str(ruta)
    return shutil.which("cloudflared")


class Tunel:
    def __init__(self, puerto: int, ejecutable: str | None = None):
        self.puerto = puerto
        self.ejecutable = ejecutable or buscar_cloudflared()
        self.url: str | None = None      # https://....trycloudflare.com, cuando Cloudflare la da
        self.listo = False               # el túnel ya lleva tráfico
        self.detalle = "arrancando…" if self.ejecutable else "falta cloudflared (usa 2-INICIAR-ESTUDIO-POR-INTERNET.bat)"
        self._proceso: subprocess.Popen | None = None
        self._parar = threading.Event()

    def arrancar(self):
        if self.ejecutable:
            threading.Thread(target=self._vigilar, name="tunel", daemon=True).start()

    def parar(self):
        self._parar.set()
        if self._proceso and self._proceso.poll() is None:
            self._proceso.terminate()

    def _vigilar(self):
        espera = 3
        while not self._parar.is_set():
            self._una_vez()
            if self._parar.is_set():
                return
            if self.listo:  # funcionaba: se reintenta enseguida
                espera = 3
            self.listo, self.url = False, None  # Cloudflare dará otra dirección: el QR se actualiza solo
            self.detalle = "reconectando…"
            log.warning("El túnel a internet se ha cortado: lo vuelvo a abrir en %d s", espera)
            self._parar.wait(espera)
            espera = min(espera * 2, 60)

    def _una_vez(self):
        orden = [self.ejecutable, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.puerto}"]
        opciones = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        try:
            self._proceso = subprocess.Popen(orden, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                             errors="replace", **opciones)
        except OSError as e:
            self.detalle = f"no se puede abrir cloudflared: {e}"
            log.error("Modo internet: %s", self.detalle)
            self._parar.wait(30)
            return
        self.detalle = "pidiendo una dirección a Cloudflare…"
        for linea in self._proceso.stdout:
            if m := DIRECCION.search(linea):
                if m.group(0) != self.url:
                    self.url = m.group(0)
                    self.detalle = "conectando…"
            elif LISTO.search(linea) and self.url and not self.listo:
                self.listo, self.detalle = True, "listo"
                log.info("Acceso por internet listo: %s", self.url)
            elif ("ERR" in linea or "failed to" in linea) and not self.listo:
                self.detalle = "sin conexión con Cloudflare: ¿el PC tiene internet?"
        self._proceso.wait()
        time.sleep(0.1)
