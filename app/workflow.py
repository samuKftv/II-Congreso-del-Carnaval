"""Rellena el workflow de ComfyUI (formato API) con el prompt, el tamaño y la semilla."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

SAMPLERS = ("KSampler", "KSamplerAdvanced")
GUIAS = ("CFGGuider", "BasicGuider", "DualCFGGuider")  # FLUX.2 y otros: SamplerCustomAdvanced + guía


class ErrorWorkflow(Exception):
    pass


@dataclass
class Nodos:
    prompt: str
    tamano: str | None
    semillas: list[tuple[str, str]]  # (nodo, nombre de la entrada)
    guardar: list[str]
    sampler: str | None = None
    vae: list | None = None  # enlace al VAE que usa el VAEDecode
    tamanos: list[str] = field(default_factory=list)  # todos los nodos con el tamaño (FLUX.2: lienzo y planificador)

    @property
    def admite_fotos(self) -> bool:
        return self.vae is not None and self.sampler is not None


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


def _muestreo(wf: dict) -> dict:
    """Los enlaces model, positive y latent_image del muestreo, venga de un KSampler o de un
    SamplerCustomAdvanced con su guía (así son los workflows de FLUX.2 Klein)."""
    for n in wf.values():
        if n.get("class_type") in SAMPLERS:
            e = n.get("inputs", {})
            return {"model": e.get("model"), "positive": e.get("positive"), "latent_image": e.get("latent_image")}
    for n in wf.values():
        if n.get("class_type") == "SamplerCustomAdvanced":
            e = n.get("inputs", {})
            guia = e.get("guider")
            g = wf.get(guia[0], {}).get("inputs", {}) if _es_enlace(guia) else {}
            return {"model": g.get("model"), "positive": g.get("positive", g.get("conditioning", g.get("cond1"))),
                    "latent_image": e.get("latent_image")}
    return {}


def localizar(wf: dict, nodo_prompt: str = "", nodo_tamano: str = "") -> Nodos:
    samplers = [k for k, n in wf.items() if n.get("class_type") in SAMPLERS]
    muestreo = _muestreo(wf)

    prompt = nodo_prompt or None
    if prompt is None and _es_enlace(muestreo.get("positive")):
        prompt = _seguir(wf, muestreo["positive"][0], _tiene_texto)
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
    if tamano is None and _es_enlace(muestreo.get("latent_image")):
        tamano = _seguir(wf, muestreo["latent_image"][0], _tiene_tamano)
    if tamano is None:
        tamano = next((k for k, n in wf.items() if _tiene_tamano(n)), None)
    if tamano is not None and (tamano not in wf or not _tiene_tamano(wf[tamano])):
        raise ErrorWorkflow(f"El nodo {tamano} (nodo_tamano) no tiene ancho y alto.")
    # Los planificadores que calculan los pasos según el tamaño (Flux2Scheduler) llevan el mismo tamaño
    tamanos = ([tamano] if tamano else []) + [
        k for k, n in wf.items() if k != tamano and "Scheduler" in n.get("class_type", "") and _tiene_tamano(n)]

    semillas = [
        (k, entrada)
        for k, n in wf.items()
        for entrada in ("seed", "noise_seed")
        if isinstance(n.get("inputs", {}).get(entrada), int)
    ]
    guardar = [k for k, n in wf.items() if n.get("class_type") == "SaveImage"]

    # Para usar una foto como base hace falta un KSampler normal (tiene "denoise") y el VAE.
    sampler = next((k for k in samplers if wf[k]["class_type"] == "KSampler"), None)
    vae = next((n["inputs"]["vae"] for n in wf.values()
                if n.get("class_type") == "VAEDecode" and _es_enlace(n.get("inputs", {}).get("vae"))), None)

    return Nodos(prompt=prompt, tamano=tamano, semillas=semillas, guardar=guardar, sampler=sampler, vae=vae,
                 tamanos=tamanos)


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
    for nodo in nodos.tamanos or ([nodos.tamano] if nodos.tamano else []):
        wf[nodo]["inputs"]["width"] = ancho
        wf[nodo]["inputs"]["height"] = alto
    for nodo, entrada in nodos.semillas:
        wf[nodo]["inputs"][entrada] = semilla
    for nodo in nodos.guardar:
        wf[nodo]["inputs"]["filename_prefix"] = prefijo
    return wf


def aligerar(wf: dict) -> dict:
    """Carga el modelo de difusión en fp8: ocupa la mitad de memoria. Z-Image Turbo en bf16 (12 GB) no cabe
    entero en una gráfica de 12 GB y ComfyUI tiene que ir pasando trozos; en fp8 cabe y va más rápido."""
    wf = copy.deepcopy(wf)
    for n in wf.values():
        entradas = n.get("inputs", {})
        if n.get("class_type") == "UNETLoader" and entradas.get("weight_dtype") == "default":
            entradas["weight_dtype"] = "fp8_e4m3fn"
    return wf


LORA = "9100"  # número del nodo del LoRA que añade la app
ARCHIVO_DEL_MODELO = ("unet_name", "ckpt_name")


def _origen(wf: dict, enlace, entrada: str):
    """Sube por la cadena de `entrada` (model o clip) hasta el nodo que la crea, el cargador.
    Devuelve el enlace a su salida, p. ej. ["16", 0]."""
    vistos = set()
    while _es_enlace(enlace) and enlace[0] in wf and enlace[0] not in vistos:
        vistos.add(enlace[0])
        anterior = wf[enlace[0]].get("inputs", {}).get(entrada)
        if not _es_enlace(anterior):
            return enlace
        enlace = anterior
    return None


def con_mi_modelo(wf: dict, modelo: str = "", lora: str = "", fuerza: float = 1.0) -> dict:
    """Pone tu modelo en el cargador del workflow y mete tu LoRA justo detrás (también en el CLIP, por si
    lo entrenaste con el codificador de texto: si no lo tiene, no cambia nada)."""
    if not modelo and not lora:
        return wf
    wf = copy.deepcopy(wf)
    entradas = _muestreo(wf)
    if not entradas:
        raise ErrorWorkflow("El workflow no tiene sampler: no sé dónde poner tu modelo y tu LoRA.")
    modelo_de = _origen(wf, entradas.get("model"), "model")
    if modelo_de is None:
        raise ErrorWorkflow("No encuentro el nodo que carga el modelo en el workflow.")

    if modelo:
        cargador = wf[modelo_de[0]]
        clave = next((c for c in ARCHIVO_DEL_MODELO if c in cargador.get("inputs", {})), None)
        if clave is None:
            raise ErrorWorkflow(
                f"No sé cambiar el modelo en el nodo {modelo_de[0]} ({cargador.get('class_type')}). "
                "Deja «modelo» vacío y exporta tu propio workflow con tu modelo ya puesto.")
        cargador["inputs"][clave] = modelo

    if lora:
        n_lora = LORA if LORA not in wf else str(max(int(k) for k in wf if k.isdigit()) + 1)
        positivo = entradas.get("positive")
        texto = _seguir(wf, positivo[0], _tiene_texto) if _es_enlace(positivo) else None
        clip_de = _origen(wf, wf[texto]["inputs"].get("clip"), "clip") if texto else None
        if clip_de:
            wf[n_lora] = {"class_type": "LoraLoader", "_meta": {"title": "Tu LoRA"}, "inputs": {
                "model": list(modelo_de), "clip": list(clip_de), "lora_name": lora,
                "strength_model": fuerza, "strength_clip": fuerza}}
        else:
            wf[n_lora] = {"class_type": "LoraLoaderModelOnly", "_meta": {"title": "Tu LoRA"}, "inputs": {
                "model": list(modelo_de), "lora_name": lora, "strength_model": fuerza}}
        # Todo lo que tiraba del cargador ahora tira del LoRA
        for k, n in wf.items():
            if k == n_lora:
                continue
            for nombre, valor in n.get("inputs", {}).items():
                if valor == modelo_de:
                    n["inputs"][nombre] = [n_lora, 0]
                elif clip_de and valor == clip_de:
                    n["inputs"][nombre] = [n_lora, 1]
    return wf


def ajustar(wf: dict, pasos: int = 0, cfg: float = 0) -> dict:
    """Cambia los pasos y la guía (CFG) del workflow. 0 = los que trae."""
    if not pasos and not cfg:
        return wf
    wf = copy.deepcopy(wf)
    for n in wf.values():
        entradas = n.get("inputs", {})
        if pasos and isinstance(entradas.get("steps"), int):
            entradas["steps"] = int(pasos)
        if cfg and isinstance(entradas.get("cfg"), (int, float)):
            entradas["cfg"] = float(cfg)
    return wf


def con_palabra_clave(prompt: str, palabra: str) -> str:
    """La palabra de activación del LoRA, al principio del prompt."""
    if not palabra or prompt.lower().startswith(palabra.lower()):
        return prompt
    return f"{palabra}, {prompt}"


# Archivos que carga el workflow y la carpeta de ComfyUI donde van
CARPETAS = {
    "unet_name": "models/diffusion_models",
    "ckpt_name": "models/checkpoints",
    "lora_name": "models/loras",
    "vae_name": "models/vae",
    "clip_name": "models/text_encoders",
    "clip_name1": "models/text_encoders",
    "clip_name2": "models/text_encoders",
}


def archivos(wf: dict) -> list[tuple[str, str, str]]:
    """(nodo, entrada, archivo) de todos los modelos, LoRA, VAE y codificadores que carga el workflow."""
    return [(k, entrada, valor) for k, n in wf.items() for entrada, valor in n.get("inputs", {}).items()
            if entrada in CARPETAS and isinstance(valor, str) and valor]


def _normal(nombre: str) -> str:
    return nombre.replace("\\", "/").lower()


def parecido(nombre: str, opciones: list[str]) -> str | None:
    """El archivo que ComfyUI tiene con ese nombre aunque esté en una subcarpeta, con la otra barra
    o sin la extensión: «mi_lora» -> «carnaval\\mi_lora.safetensors»."""
    buscado = _normal(nombre)
    for o in opciones:
        if _normal(o) == buscado:
            return o
    base = buscado.rsplit("/", 1)[-1]
    candidatos = [o for o in opciones
                  if _normal(o).rsplit("/", 1)[-1] in (base, f"{base}.safetensors")
                  or _normal(o).rsplit("/", 1)[-1].rsplit(".", 1)[0] == base]
    return candidatos[0] if len(candidatos) == 1 else None


def con_foto(wf: dict, nodos: Nodos, imagen: str, fuerza: float) -> dict:
    """Cambia el lienzo vacío por la foto subida a ComfyUI (img2img). `wf` ya viene preparado."""
    if not nodos.admite_fotos:
        raise ErrorWorkflow("Este workflow no permite usar fotos como base.")
    sampler = wf[nodos.sampler]["inputs"]
    latente = sampler.get("latent_image")
    wf["9001"] = {"class_type": "LoadImage", "inputs": {"image": imagen}, "_meta": {"title": "Foto del alumno"}}
    wf["9002"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["9001", 0], "vae": nodos.vae}}
    sampler["latent_image"] = ["9002", 0]
    sampler["denoise"] = fuerza
    if _es_enlace(latente) and not any(  # el lienzo vacío ya no lo usa nadie
        v == latente for n in wf.values() for v in n.get("inputs", {}).values()
    ):
        wf.pop(latente[0], None)
    return wf
