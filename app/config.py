"""Carga de ajustes, estilos y workflow desde la carpeta config/."""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOW_NORMAL = "config/workflow_api.json"  # Z-Image Turbo
# Familias de modelos con workflow ya preparado (config/plantillas). "auto" mira el nombre de tu modelo o tu LoRA.
BASES = {
    "auto": None,
    "z-image-turbo": None,  # el workflow de [comfyui]
    "flux2-klein-4b": "config/plantillas/flux2_klein_4b.json",
    "flux2-klein-4b-base": "config/plantillas/flux2_klein_4b.json",
}
CARPETA_SIMULACRO = "datos-simulacro"  # carpeta de datos del simulacro (3-PROBAR-CON-100-PERSONAS.bat)
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
# Nombres de los colores en ajustes.toml -> variables CSS de la app
COLORES_CSS = {
    "fondo": "--noche",
    "principal": "--magenta",
    "secundario": "--amarillo",
    "acento": "--cian",
    "extra": "--naranja",
    "extra2": "--deco-1",
    "extra3": "--deco-2",
    "texto_suave": "--suave",
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
    congreso: str
    lema: str
    centro: str
    logo: Path | None
    cartel: Path | None
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
    revisar_antes: bool = True  # el profesor aprueba cada imagen antes de que sea pública
    ligero: bool = True  # modelo de difusión en fp8 (cabe entero en 12 GB de VRAM)
    internet: bool = False  # modo internet: túnel de Cloudflare con dirección pública https
    piezas_mosaico: int = 150  # máximo de piezas del mosaico del proyector
    sencillo: bool = True  # móvil sencillo: solo la idea (técnica y formato fijos)
    estilo_sencillo: str = "libre"
    formato_sencillo: str = "cuadrado"
    fotos: bool = True  # crear a partir de una foto propia
    interprete_activado: bool = False  # IA de texto (Ollama) que convierte la idea en una descripción en inglés
    interprete_url: str = "http://127.0.0.1:11434"
    interprete_modelo: str = "qwen2.5:3b"
    base: str = ""  # familia elegida en [mi_modelo] (vacío = el workflow de [comfyui])
    pasos: int = 0  # 0 = los del workflow
    cfg: float = 0.0  # 0 = la del workflow
    modelo: str = ""  # tu modelo (sustituye al del workflow)
    lora: str = ""  # tu LoRA (la app lo mete en el workflow)
    fuerza_lora: float = 1.0
    palabra_clave: str = ""  # palabra de activación del LoRA, delante de cada prompt


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


def elegir_base(mio: dict, ruta_workflow: str) -> str:
    """La familia del modelo: la que pone [mi_modelo] base o, con "auto", la que delata el nombre del archivo
    (solo si se usa el workflow normal: un workflow exportado por ti manda)."""
    base = str(mio.get("base", "auto")).strip().lower()
    if base not in BASES:
        raise ValueError(f"En [mi_modelo], base = \"{base}\" no existe. Usa una de estas: "
                         + ", ".join(f'"{b}"' for b in BASES) + ".")
    if base != "auto":
        return base
    if _ruta(ruta_workflow).resolve() != _ruta(WORKFLOW_NORMAL).resolve():
        return "auto"
    nombres = f"{mio.get('modelo', '')} {mio.get('lora', '')}".lower()
    if "klein" in nombres:
        return "flux2-klein-4b-base" if "base" in nombres else "flux2-klein-4b"
    return "auto"


def klein_base(wf: dict) -> dict:
    """FLUX.2 Klein 4B sin destilar: 20 pasos con guía 5 y un negativo de verdad (como su plantilla oficial)."""
    wf = json.loads(json.dumps(wf))
    for n in wf.values():
        e = n.get("inputs", {})
        if n.get("class_type") == "UNETLoader" and e.get("unet_name") == "flux-2-klein-4b.safetensors":
            e["unet_name"] = "flux-2-klein-base-4b.safetensors"
        if n.get("class_type") == "Flux2Scheduler":
            e["steps"] = 20
        if n.get("class_type") == "CFGGuider":
            e["cfg"] = 5.0
            negativo = e.get("negative")
            if isinstance(negativo, list) and wf.get(negativo[0], {}).get("class_type") == "ConditioningZeroOut":
                clip = next((v["inputs"]["clip"] for v in wf.values() if v.get("class_type") == "CLIPTextEncode"), None)
                wf[negativo[0]] = {"class_type": "CLIPTextEncode", "_meta": {"title": "CLIP Text Encode (Negative Prompt)"},
                                   "inputs": {"text": "", "clip": clip}}
    return wf


def cargar(ruta_ajustes: str | Path | None = None) -> Ajustes:
    ruta_ajustes = _ruta(str(ruta_ajustes or os.environ.get("ESTUDIO_AJUSTES", "config/ajustes.toml")))
    with open(ruta_ajustes, "rb") as f:
        t = tomllib.load(f)

    evento, servidor, acceso = t.get("evento", {}), t.get("servidor", {}), t.get("acceso", {})
    comfy, limites, moderacion = t.get("comfyui", {}), t.get("limites", {}), t.get("moderacion", {})
    interprete, alumnado = t.get("interprete", {}), t.get("alumnado", {})
    mio = t.get("mi_modelo", {})
    for clave in ("pasos", "cfg", "fuerza_lora"):
        if not isinstance(mio.get(clave, 0), (int, float)):
            raise ValueError(f"En [mi_modelo], {clave} tiene que ser un número (sin comillas).")

    ruta_workflow = str(comfy.get("workflow", WORKFLOW_NORMAL))
    base = elegir_base(mio, ruta_workflow)
    with open(_ruta(BASES.get(base) or ruta_workflow), encoding="utf-8") as f:
        workflow = json.load(f)
    if "nodes" in workflow and "links" in workflow:
        raise ValueError(
            "config/workflow_api.json está en formato normal, no en formato API. "
            "En ComfyUI usa Workflow > Exportar (API)."
        )
    if base == "flux2-klein-4b-base":
        workflow = klein_base(workflow)

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

    logo, cartel = evento.get("logo", ""), evento.get("cartel", "")
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
        congreso=evento.get("congreso", ""),
        lema=evento.get("lema", ""),
        centro=evento.get("centro", ""),
        logo=_ruta(logo) if logo else None,
        cartel=_ruta(cartel) if cartel else None,
        colores=colores,
        puerto=int(servidor.get("puerto", 8080)),
        direccion=str(servidor.get("direccion", "")).strip(),
        abrir_navegador=bool(servidor.get("abrir_navegador", True)),
        codigo=str(acceso.get("codigo", "")).strip(),
        clave_profesor=str(acceso.get("clave_profesor", "")),
        comfy_url=str(comfy.get("url", "auto")).rstrip("/"),
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
        revisar_antes=bool(moderacion.get("revisar_antes", True)),
        ligero=bool(comfy.get("ligero", True)),
        piezas_mosaico=min(max(int(t.get("proyector", {}).get("piezas_mosaico", 150)), 20), 3000),
        sencillo=bool(alumnado.get("sencillo", False)),
        estilo_sencillo=alumnado.get("estilo") if alumnado.get("estilo") in estilos else next(iter(estilos)),
        formato_sencillo=alumnado.get("formato") if alumnado.get("formato") in formatos else next(iter(formatos)),
        fotos=bool(alumnado.get("fotos", True)),
        internet=bool(t.get("internet", {}).get("activado", False)) or os.environ.get("ESTUDIO_INTERNET") == "1",
        interprete_activado=bool(interprete.get("activado", False)),
        interprete_url=str(interprete.get("url", "http://127.0.0.1:11434")).rstrip("/"),
        interprete_modelo=str(interprete.get("modelo", "qwen2.5:3b")).strip(),
        base=base if BASES.get(base) else "",
        pasos=min(max(int(mio.get("pasos", 0)), 0), 200),
        cfg=min(max(float(mio.get("cfg", 0)), 0.0), 30.0),
        modelo=str(mio.get("modelo", "")).strip(),
        lora=str(mio.get("lora", "")).strip(),
        fuerza_lora=min(max(float(mio.get("fuerza_lora", 1.0)), -3.0), 3.0),
        palabra_clave=" ".join(str(mio.get("palabra_clave", "")).split()),
    )
