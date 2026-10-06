"""Carga de ajustes, estilos y workflow desde la carpeta config/."""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
# Nombres de los colores en ajustes.toml -> variables CSS de la app
COLORES_CSS = {
    "fondo": "--noche",
    "principal": "--magenta",
    "secundario": "--amarillo",
    "acento": "--cian",
    "extra": "--naranja",
}


@dataclass
class Formato:
    id: str
    ancho: int
    alto: int


@dataclass
class Estilo:
    """Una técnica (foto, acuarela…) o una temática (Venecia, Río…)."""

    id: str
    nombre: str
    emoji: str
    colores: list[str]
    receta: str
    ejemplo: str

    def aplicar(self, prompt: str) -> str:
        return self.receta.replace("{prompt}", prompt)


@dataclass
class Ajustes:
    evento: str
    subtitulo: str
    logo: Path | None
    colores: dict[str, str]
    puerto: int
    direccion: str
    abrir_navegador: bool
    codigo: str
    clave_profesor: str
    comfy_url: str
    workflow: dict
    tiempo_maximo: float
    nodo_prompt: str
    nodo_tamano: str
    en_cola_por_persona: int
    max_caracteres: int
    formatos: dict[str, Formato]
    fuerzas: dict[str, float]
    palabras_prohibidas: list[str]
    estilos: dict[str, Estilo]
    temas: dict[str, Estilo]
    ideas: list[str]
    detalles: list[dict]
    datos: Path = field(default_factory=lambda: RAIZ / "datos")


def _ruta(valor: str) -> Path:
    ruta = Path(valor)
    return ruta if ruta.is_absolute() else RAIZ / ruta


def _estilos(lista: list[dict]) -> dict[str, Estilo]:
    return {
        d["id"]: Estilo(
            id=d["id"],
            nombre=d.get("nombre", d["id"]),
            emoji=d.get("emoji", "🎨"),
            colores=d.get("colores", ["#6d28d9", "#db2777"]),
            receta=d.get("receta", "{prompt}"),
            ejemplo=d.get("ejemplo", d.get("nombre", d["id"])),
        )
        for d in lista
    }


def cargar(ruta_ajustes: str | Path | None = None) -> Ajustes:
    ruta_ajustes = _ruta(str(ruta_ajustes or os.environ.get("ESTUDIO_AJUSTES", "config/ajustes.toml")))
    with open(ruta_ajustes, "rb") as f:
        t = tomllib.load(f)

    evento, servidor, acceso = t.get("evento", {}), t.get("servidor", {}), t.get("acceso", {})
    comfy, limites, moderacion = t.get("comfyui", {}), t.get("limites", {}), t.get("moderacion", {})

    with open(_ruta(comfy.get("workflow", "config/workflow_api.json")), encoding="utf-8") as f:
        workflow = json.load(f)
    if "nodes" in workflow and "links" in workflow:
        raise ValueError(
            "config/workflow_api.json está en formato normal, no en formato API. "
            "En ComfyUI usa Workflow > Exportar (API)."
        )

    ruta_estilos = ruta_ajustes.parent / "estilos.json"
    with open(ruta_estilos, encoding="utf-8") as f:
        e = json.load(f)
    estilos = _estilos(e.get("estilos", []))
    if not estilos:
        raise ValueError("config/estilos.json no tiene ningún estilo.")

    formatos = {
        nombre: Formato(nombre, int(medidas[0]), int(medidas[1]))
        for nombre, medidas in t.get("formatos", {"cuadrado": [1024, 1024]}).items()
    }

    logo = evento.get("logo", "")
    logo = _ruta(logo) if logo else None
    colores = {}
    for nombre, valor in t.get("colores", {}).items():
        if nombre not in COLORES_CSS or not COLOR.match(str(valor)):
            raise ValueError(f"Color no válido en [colores]: {nombre} = {valor!r} (usa el formato \"#rrggbb\").")
        colores[nombre] = valor

    fuerzas = {k: float(v) for k, v in t.get("fotos", {}).get("fuerzas", {}).items()} or {
        "poco": 0.5, "bastante": 0.68, "mucho": 0.82,
    }

    datos = _ruta(os.environ.get("ESTUDIO_DATOS", "datos"))

    return Ajustes(
        evento=evento.get("nombre", "Estudio de imágenes"),
        subtitulo=evento.get("subtitulo", ""),
        logo=logo,
        colores=colores,
        puerto=int(servidor.get("puerto", 8080)),
        direccion=str(servidor.get("direccion", "")).strip(),
        abrir_navegador=bool(servidor.get("abrir_navegador", True)),
        codigo=str(acceso.get("codigo", "")).strip(),
        clave_profesor=str(acceso.get("clave_profesor", "")),
        comfy_url=str(comfy.get("url", "http://127.0.0.1:8188")).rstrip("/"),
        workflow=workflow,
        tiempo_maximo=float(comfy.get("tiempo_maximo", 180)),
        nodo_prompt=str(comfy.get("nodo_prompt", "")).strip(),
        nodo_tamano=str(comfy.get("nodo_tamano", "")).strip(),
        en_cola_por_persona=max(1, int(limites.get("en_cola_por_persona", 1))),
        max_caracteres=int(limites.get("max_caracteres", 400)),
        formatos=formatos,
        fuerzas=fuerzas,
        palabras_prohibidas=list(moderacion.get("palabras_prohibidas", [])),
        estilos=estilos,
        temas=_estilos(e.get("temas", [])),
        ideas=list(e.get("ideas", [])),
        detalles=list(e.get("detalles", [])),
        datos=datos,
    )
