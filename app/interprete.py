"""Intérprete de ideas: una IA de texto local (Ollama) convierte la idea del alumnado en una descripción
detallada en inglés, que es como mejor entiende Z-Image.

Va en el procesador (num_gpu = 0) para no quitarle memoria a la gráfica, y trabaja por adelantado
mientras las imágenes esperan en la cola. Si no está disponible o tarda, la idea se pinta tal cual.
"""

from __future__ import annotations

import logging
import re

import httpx

from .moderacion import Filtro

log = logging.getLogger("estudio")

SISTEMA = """You write prompts for an image generator at CarnaLab, a carnival event in Tenerife.
The user sends a short idea, usually in Spanish. Rewrite it as ONE vivid description in English.
- Keep exactly what the person asked for: the same subject, characters, actions, number of things and any text they want written. Never change or replace the idea.
- If it is short or vague, add concrete visual details: appearance, costume, colors, materials, place, lighting.
- If the person talks about themselves ("me", "conviérteme"), describe "a person".
- Do not mention art styles, painting techniques, cameras or image quality: that is added later.
- Keep it suitable for a public event for all ages.
- Answer only with the description: one paragraph, 40 to 70 words, no quotes, no lists."""

EJEMPLOS = [
    ("un pulpo pirata",
     "A cheerful giant purple octopus dressed as a pirate captain, with a tricorn hat trimmed in gold, an eye "
     "patch and a tiny wooden sword in one tentacle, standing proudly on the deck of a ship decorated with "
     "colorful streamers and confetti, festive lights glowing in the night sky."),
    ("conviérteme en reina del carnaval con un traje del Teide",
     "A person dressed as a carnival queen in a monumental costume inspired by the Teide volcano: a huge "
     "backpiece shaped like the mountain, covered in red and orange sequins like flowing lava, black "
     "rhinestones like volcanic rock and white feathers like snow on the summit, with a matching jeweled "
     "headdress, standing on a big stage under bright spotlights."),
]

PENSAMIENTO = re.compile(r"<think>.*?</think>", re.S | re.I)
ETIQUETA = re.compile(r"^(description|prompt|descripci[oó]n)\s*:\s*", re.I)


class Interprete:
    def __init__(self, url: str, modelo: str, filtro: Filtro):
        self.url, self.modelo, self.filtro = url.rstrip("/"), modelo, filtro
        self.http = httpx.AsyncClient(timeout=90, trust_env=False)
        self.ok = False
        self.detalle = "comprobando…"

    async def comprobar(self) -> bool:
        """¿Está Ollama abierto y tiene el modelo?"""
        try:
            r = await self.http.get(f"{self.url}/api/tags", timeout=3)
            r.raise_for_status()
            nombres = {m.get("name", "") for m in r.json().get("models", [])}
        except (httpx.HTTPError, ValueError, AttributeError):
            self.ok, self.detalle = False, "Ollama no está abierto"
            return False
        self.ok = self.modelo in nombres or f"{self.modelo}:latest" in nombres
        self.detalle = "listo" if self.ok else f"falta el modelo {self.modelo} (ejecuta 4-INSTALAR-INTERPRETE.bat)"
        return self.ok

    def mensajes(self, idea: str) -> list[dict]:
        m = [{"role": "system", "content": SISTEMA}]
        for pregunta, respuesta in EJEMPLOS:
            m += [{"role": "user", "content": pregunta}, {"role": "assistant", "content": respuesta}]
        return m + [{"role": "user", "content": idea}]

    async def interpretar(self, idea: str) -> str | None:
        """La descripción en inglés, o None si no se ha podido (se pintará la idea tal cual)."""
        try:
            r = await self.http.post(f"{self.url}/api/chat", json={
                "model": self.modelo, "messages": self.mensajes(idea), "stream": False, "keep_alive": "8h",
                "options": {"num_gpu": 0, "temperature": 0.5, "num_predict": 180, "num_ctx": 2048},
            })
            r.raise_for_status()
            texto = r.json()["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
            log.warning("El intérprete no ha podido con «%s»: %s", idea, e)
            return None
        return self.limpiar(texto)

    def limpiar(self, texto: str) -> str | None:
        texto = " ".join(PENSAMIENTO.sub("", texto).split())
        texto = ETIQUETA.sub("", texto).strip().strip('"“”«»').strip()
        if len(texto) < 15 or self.filtro.bloqueada(texto):
            return None
        return texto[:700]

    async def cerrar(self):
        await self.http.aclose()
