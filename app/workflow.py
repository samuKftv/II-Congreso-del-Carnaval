"""Rellena el workflow de ComfyUI (formato API) con el prompt, el tamaño y la semilla."""

from __future__ import annotations

import copy
from dataclasses import dataclass

SAMPLERS = ("KSampler", "KSamplerAdvanced")


class ErrorWorkflow(Exception):
    pass


@dataclass
class Nodos:
    prompt: str
    tamano: str | None
    semillas: list[tuple[str, str]]  # (nodo, nombre de la entrada)
    guardar: list[str]


def _es_enlace(valor) -> bool:
    return isinstance(valor, list) and len(valor) == 2 and isinstance(valor[0], str)


def _seguir(wf: dict, inicio: str, condicion) -> str | None:
    """Recorre los enlaces hacia atrás desde `inicio` hasta un nodo que cumpla `condicion`."""
    pendientes, vistos = [inicio], set()
    while pendientes:
        nodo = pendientes.pop(0)
        if nodo in vistos or nodo not in wf:
            continue
        vistos.add(nodo)
        if condicion(wf[nodo]):
            return nodo
        pendientes.extend(v[0] for v in wf[nodo].get("inputs", {}).values() if _es_enlace(v))
    return None


def _tiene_texto(n: dict) -> bool:
    return isinstance(n.get("inputs", {}).get("text"), str)


def _tiene_tamano(n: dict) -> bool:
    i = n.get("inputs", {})
    return isinstance(i.get("width"), int) and isinstance(i.get("height"), int)


def localizar(wf: dict, nodo_prompt: str = "", nodo_tamano: str = "") -> Nodos:
    samplers = [k for k, n in wf.items() if n.get("class_type") in SAMPLERS]

    prompt = nodo_prompt or None
    if prompt is None and samplers:
        positivo = wf[samplers[0]]["inputs"].get("positive")
        if _es_enlace(positivo):
            prompt = _seguir(wf, positivo[0], _tiene_texto)
    if prompt is None:
        titulados = [k for k, n in wf.items() if _tiene_texto(n) and "positive" in n.get("_meta", {}).get("title", "").lower()]
        textos = [k for k, n in wf.items() if _tiene_texto(n)]
        prompt = (titulados or (textos if len(textos) == 1 else [None]))[0]
    if prompt is None or prompt not in wf or not _tiene_texto(wf[prompt]):
        raise ErrorWorkflow(
            "No encuentro el nodo del prompt en el workflow. Indica su número en "
            "config/ajustes.toml (nodo_prompt)."
        )

    tamano = nodo_tamano or None
    if tamano is None and samplers:
        latente = wf[samplers[0]]["inputs"].get("latent_image")
        if _es_enlace(latente):
            tamano = _seguir(wf, latente[0], _tiene_tamano)
    if tamano is None:
        tamano = next((k for k, n in wf.items() if _tiene_tamano(n)), None)
    if tamano is not None and (tamano not in wf or not _tiene_tamano(wf[tamano])):
        raise ErrorWorkflow(f"El nodo {tamano} (nodo_tamano) no tiene ancho y alto.")

    semillas = [
        (k, entrada)
        for k, n in wf.items()
        for entrada in ("seed", "noise_seed")
        if isinstance(n.get("inputs", {}).get(entrada), int)
    ]
    guardar = [k for k, n in wf.items() if n.get("class_type") == "SaveImage"]

    return Nodos(prompt=prompt, tamano=tamano, semillas=semillas, guardar=guardar)


def avisos(wf: dict, nodos: Nodos) -> list[str]:
    """Problemas que no impiden generar, pero conviene que el profesor conozca."""
    lista = []
    if nodos.tamano is None:
        lista.append("No encuentro el nodo de tamaño: todas las imágenes saldrán con el tamaño del workflow.")
    if not nodos.semillas:
        lista.append("El workflow no tiene semilla: 'Otra versión' puede devolver la misma imagen.")
    if not nodos.guardar:
        lista.append("El workflow no tiene nodo 'Save Image': añade uno para recibir las imágenes.")
    return lista


def preparar(wf: dict, nodos: Nodos, prompt: str, ancho: int, alto: int, semilla: int, prefijo: str) -> dict:
    wf = copy.deepcopy(wf)
    wf[nodos.prompt]["inputs"]["text"] = prompt
    if nodos.tamano is not None:
        wf[nodos.tamano]["inputs"]["width"] = ancho
        wf[nodos.tamano]["inputs"]["height"] = alto
    for nodo, entrada in nodos.semillas:
        wf[nodo]["inputs"][entrada] = semilla
    for nodo in nodos.guardar:
        wf[nodo]["inputs"]["filename_prefix"] = prefijo
    return wf
