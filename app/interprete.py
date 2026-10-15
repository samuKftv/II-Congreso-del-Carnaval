"""Intérprete de ideas: una IA de texto local (Ollama) convierte la idea del alumnado en una descripción
detallada en inglés, que es como mejor entiende Z-Image.

Va en el procesador (num_gpu = 0) para no quitarle memoria a la gráfica, salvo con [interprete] grafica = true,
y trabaja por adelantado mientras las imágenes esperan en la cola. Si no está disponible o tarda, la idea se pinta
tal cual (con la ambientación de carnaval del estilo).
"""

from __future__ import annotations

import logging
import re

import httpx

from .moderacion import Filtro

log = logging.getLogger("estudio")

SISTEMA = """You write prompts for an image generator at CarnaLab, a congress about the Carnival of Santa Cruz de Tenerife.
The user sends a short idea, usually in Spanish. Rewrite it as ONE vivid description in English of a carnival scene.
- Keep exactly what the person asked for: the same subject, characters, actions, number of things and any text they want written. Never replace the idea.
- Always bring it into the Carnival of Santa Cruz de Tenerife. If the idea is not about carnival, show it in carnival form: in a carnival costume, as a parade float, in a murga or a comparsa, at the night street party, on the big stage of the queen gala.
- Put the most important things first: start with the main subject and what it is doing, then the costume details (sequins, feathers, rhinestones, satin, glitter, masks, face paint, bright colors), then the place, the lighting and the mood (confetti, streamers, music).
- Write natural sentences, not lists of keywords. Describe only what should appear, never what should not.
- Canarian carnival words: murga = group of singers in identical colorful costumes and painted faces, singing funny songs with kazoos; comparsa = troupe of dancers in feathered costumes dancing to Latin drums; rondalla = choir with guitars and lutes in elegant costumes; Reina del Carnaval = queen wearing a monumental costume with a giant backpiece of feathers and sequins on wheels; Coso = big daytime parade with floats; Entierro de la Sardina = funny funeral parade with a giant papier-mache sardine and people dressed as mourning widows in black; mascarita = person in costume and mask; guagua = bus.
- If the person talks about themselves ("me", "conviérteme"), describe "a person".
- Do not mention art styles, painting techniques, cameras or image quality: that is added later.
- Keep it suitable for a public event for all ages.
- Answer only with the description: one paragraph, 35 to 60 words, no quotes, no lists."""

EJEMPLOS = [
    ("un pulpo pirata",
     "A cheerful giant purple octopus dressed as a carnival pirate captain, with a tricorn hat covered in gold "
     "sequins, a glittering eye patch and a feathered cape, waving from the top of a ship-shaped parade float "
     "in the streets of Santa Cruz de Tenerife at night, confetti and streamers flying, colorful lights."),
    ("conviérteme en reina del carnaval con un traje del Teide",
     "A person crowned as carnival queen in a monumental costume inspired by the Teide volcano: a huge "
     "backpiece shaped like the mountain, covered in red and orange sequins like flowing lava, black "
     "rhinestones like volcanic rock and white feathers like snow on the summit, on the big gala stage "
     "under bright spotlights."),
    ("un gato",
     "A fluffy orange cat wearing a tiny carnival costume with a golden sequined cape and a headdress of pink "
     "and turquoise feathers, sitting proudly on a decorated parade float, surrounded by dancers in bright "
     "costumes, falling confetti and serpentine streamers, warm festive lights at night."),
    ("una murga de abuelas",
     "A murga of smiling grandmothers in identical red and yellow satin costumes with ruffled collars, painted "
     "clown faces and glittering hats, singing funny songs and blowing kazoos together on an open-air carnival "
     "stage, the audience in costumes cheering, spotlights and confetti."),
    ("una costurera",
     "A seamstress in her workshop sewing a giant carnival queen costume, surrounded by mannequins, rolls of "
     "shiny fabric, boxes of sequins and rhinestones and huge bundles of colorful feathers, her hands guiding "
     "the sewing machine, warm light and sparkling details everywhere."),
]

PENSAMIENTO = re.compile(r"<think>.*?</think>", re.S | re.I)
ETIQUETA = re.compile(r"^(description|prompt|descripci[oó]n)\s*:\s*", re.I)


class Interprete:
    def __init__(self, url: str, modelo: str, filtro: Filtro, grafica: bool = False):
        self.url, self.modelo, self.filtro, self.grafica = url.rstrip("/"), modelo, filtro, grafica
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
                "options": {**({} if self.grafica else {"num_gpu": 0}),  # 0 = en el procesador
                            "temperature": 0.6, "num_predict": 150, "num_ctx": 4096},
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
