"""Filtro sencillo de palabras para los prompts."""

from __future__ import annotations

import re
import unicodedata


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


class Filtro:
    def __init__(self, palabras: list[str]):
        self.exactas: set[str] = set()
        self.prefijos: list[str] = []
        self.frases: list[re.Pattern] = []
        for p in palabras:
            p = normalizar(p.strip())
            if not p:
                continue
            if " " in p:
                self.frases.append(re.compile(r"\b" + re.escape(p.rstrip("*")) + r"\b"))
            elif p.endswith("*"):
                self.prefijos.append(p[:-1])
            else:
                self.exactas.add(p)

    def bloqueada(self, texto: str) -> str | None:
        """Devuelve la palabra que bloquea el texto, o None si está permitido."""
        texto = normalizar(texto)
        for palabra in re.findall(r"\w+", texto):
            if palabra in self.exactas or any(palabra.startswith(p) for p in self.prefijos):
                return palabra
        for frase in self.frases:
            if m := frase.search(texto):
                return m.group(0)
        return None
