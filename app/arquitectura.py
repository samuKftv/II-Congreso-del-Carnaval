"""¿De qué familia es tu modelo o tu LoRA? (Z-Image Turbo, FLUX.2 Klein, SDXL…)

Cada familia necesita su propio workflow: si se mezclan, ComfyUI falla con "mat1 and mat2 shapes cannot be
multiplied". Para saberlo se lee solo la cabecera del archivo .safetensors (los nombres y tamaños de los pesos),
que ComfyUI tiene en este mismo PC: /internal/folder_paths dice en qué carpetas están.
"""

from __future__ import annotations

import asyncio
import json
import re
import struct
from collections import Counter
from pathlib import Path

NOMBRES = {
    "z-image": "Z-Image Turbo",
    "lumina2": "Lumina 2",
    "flux2-klein-4b": "FLUX.2 Klein 4B",
    "flux2-klein-9b": "FLUX.2 Klein 9B",
    "flux2": "FLUX.2",
    "flux1": "FLUX.1",
    "qwen-image": "Qwen-Image",
    "sdxl": "SDXL",
    "sd15": "Stable Diffusion 1.5",
    "sd": "Stable Diffusion",
}
# Lo que hay que poner en [mi_modelo] base para cada familia (las que tienen workflow preparado)
BASE_PARA = {"z-image": "z-image-turbo", "flux2-klein-4b": "flux2-klein-4b"}
CARPETA_DE = {"unet_name": "diffusion_models", "ckpt_name": "checkpoints", "lora_name": "loras"}
# Dimensión del texto que espera cada familia (sale en el error "mat1 and mat2")
TEXTO_QUE_ESPERA = {7680: "flux2-klein-4b", 12288: "flux2-klein-9b", 15360: "flux2", 4096: "flux1",
                    2048: "sdxl", 768: "sd15", 2560: "z-image", 3584: "qwen-image", 2304: "lumina2"}
MAT = re.compile(r"mat1 and mat2 shapes cannot be multiplied \((\d+)x(\d+) and (\d+)x(\d+)\)")
BLOQUE = re.compile(r"(single_transformer_blocks|single_blocks|double_blocks|transformer_blocks)[._](\d+)[._]")


def cabecera(ruta: Path) -> dict | None:
    """La cabecera JSON de un .safetensors: {nombre del peso: {"dtype", "shape", …}, "__metadata__": …}."""
    try:
        with open(ruta, "rb") as f:
            largo = struct.unpack("<Q", f.read(8))[0]
            if not 0 < largo < 200_000_000:
                return None
            return json.loads(f.read(largo))
    except (OSError, ValueError, struct.error):
        return None


def _forma(cab: dict, clave: str | None) -> list | None:
    valor = cab.get(clave) if clave else None
    return valor.get("shape") if isinstance(valor, dict) else None


def familia_modelo(cab: dict) -> str | None:
    """Como hace ComfyUI (model_detection.py), pero solo con los nombres y las formas."""
    claves = [k for k in cab if k != "__metadata__"]

    def acaba(sufijo: str) -> str | None:
        return next((k for k in claves if k.endswith(sufijo)), None)

    if acaba("double_stream_modulation_img.lin.weight"):
        forma = _forma(cab, acaba("txt_in.weight"))
        return {7680: "flux2-klein-4b", 12288: "flux2-klein-9b"}.get(forma[1] if forma else 0, "flux2")
    if acaba("cap_embedder.1.weight") and acaba("noise_refiner.0.attention.k_norm.weight"):
        forma = _forma(cab, acaba("cap_embedder.1.weight"))
        return "z-image" if forma and forma[0] == 3840 else "lumina2"
    if acaba("double_blocks.0.img_attn.norm.key_norm.scale") or acaba("double_blocks.0.img_attn.norm.key_norm.weight"):
        return "flux1"
    if acaba("transformer_blocks.0.img_mod.1.weight") and acaba("txt_in.weight"):
        return "qwen-image"
    if acaba("input_blocks.0.0.weight"):
        return "sdxl" if acaba("label_emb.0.0.weight") else "sd15"
    return None


def familia_lora(cab: dict) -> str | None:
    claves = [k for k in cab if k != "__metadata__"]
    if not claves:
        return None
    dimensiones = Counter(forma[1] for k in claves
                          if re.search(r"(lora_A|lora_down)\.weight$", k) and len(forma := _forma(cab, k) or []) == 2)
    oculta = dimensiones.most_common(1)[0][0] if dimensiones else None

    # Stable Diffusion: el contexto de attn2.to_k dice si es SDXL (2048) o 1.5 (768)
    to_k = next((k for k in claves if re.search(r"attn2[._]to_k.*(lora_A|lora_down)\.weight$", k)), None)
    if to_k or any(k.startswith(("lora_unet_down", "lora_unet_up", "lora_unet_input", "lora_unet_output", "lora_te"))
                   for k in claves):
        forma = _forma(cab, to_k)
        if any(k.startswith("lora_te2_") for k in claves) or (forma and forma[1] == 2048):
            return "sdxl"
        return "sd15" if forma and forma[1] == 768 else "sd"

    # Bloques dobles y simples: FLUX.1 tiene 19 y 38, FLUX.2 Klein 4B 5 y 20
    dobles, simples = -1, -1
    for k in claves:
        if m := BLOQUE.search(k):
            n = int(m.group(2))
            if m.group(1).startswith("single"):
                simples = max(simples, n)
            else:
                dobles = max(dobles, n)
    if dobles >= 0 or simples >= 0:
        if simples < 0 and dobles >= 30:
            return "qwen-image"
        if any(re.search(r"(img_mod|txt_mod|[._]modulation[._]lin|norm1[._]linear)", k) for k in claves):
            return "flux1"  # FLUX.2 no tiene modulación en cada bloque
        if oculta == 6144:
            return "flux2"
        if oculta == 4096:
            return "flux2-klein-9b"
        if dobles <= 4 and simples <= 19:
            return "flux2-klein-4b"
        return "flux1"

    # Z-Image y Lumina 2: bloques "layers.N" con attention / feed_forward
    if any(re.search(r"layers[._]\d+[._](attention|feed_forward)", k) for k in claves):
        return "lumina2" if oculta == 2304 else "z-image"
    return None


def familia_workflow(wf: dict) -> str | None:
    """La familia para la que está hecho el workflow, por cómo carga el texto."""
    for n in wf.values():
        e, clase = n.get("inputs", {}), n.get("class_type")
        nombre = str(e.get("clip_name", "")).lower()
        if clase == "CLIPLoader" and e.get("type") == "lumina2":
            return "z-image" if "qwen" in nombre else "lumina2"
        if clase == "CLIPLoader" and e.get("type") == "flux2":
            return "flux2-klein-9b" if "8b" in nombre else "flux2-klein-4b" if "4b" in nombre else "flux2"
        if clase == "DualCLIPLoader" and e.get("type") == "flux":
            return "flux1"
        if clase == "CheckpointLoaderSimple":
            return "sd"
    return None


def compatibles(a: str | None, b: str | None) -> bool:
    if not a or not b or a == b:
        return True
    # "sd" y "flux2" a secas = no se sabe la variante: valen con cualquiera de su grupo
    for grupo, generica in (({"sd", "sdxl", "sd15"}, "sd"), ({"flux2", "flux2-klein-4b", "flux2-klein-9b"}, "flux2")):
        if {a, b} <= grupo and generica in (a, b):
            return True
    return False


def nombre(familia: str | None) -> str:
    return NOMBRES.get(familia or "", familia or "desconocido")


def como_arreglarlo(familia: str) -> str:
    if familia in BASE_PARA:
        return f'en config/ajustes.toml > [mi_modelo] pon base = "{BASE_PARA[familia]}" y vuelve a abrir el estudio.'
    return ("monta en ComfyUI un workflow que funcione con él, expórtalo con Exportar (API) y guárdalo como "
            "config/workflow_api.json.")


def explicar(mensaje: str) -> str:
    """Traduce los errores de ComfyUI que salen al mezclar familias."""
    m = MAT.search(mensaje or "")
    if not m:
        return mensaje
    llega, espera = int(m.group(2)), int(m.group(3))
    familia = TEXTO_QUE_ESPERA.get(espera)
    texto = (f"El modelo no es de la familia del workflow: ComfyUI le pasa el texto con {llega} valores y el modelo "
             f"espera {espera}.")
    if familia:
        texto += f" Parece un modelo {nombre(familia)}: {como_arreglarlo(familia)}"
    return texto


async def revisar(comfy, wf: dict, modelo_propio: bool, lora_propio: bool) -> tuple[list[str], dict]:
    """Mira de qué familia son tu modelo y tu LoRA y si encajan con el workflow.

    Devuelve (avisos para el profesor, {"modelo": familia, "lora": familia, "workflow": familia})."""
    familias = {"workflow": familia_workflow(wf)}
    if not modelo_propio and not lora_propio:
        return [], familias
    carpetas = await comfy.carpetas()
    if not carpetas:
        return [], familias  # ComfyUI antiguo o en otro PC: no se puede mirar

    async def leer(entrada: str) -> tuple[str, dict | None] | None:
        archivo = next((n["inputs"][entrada] for n in wf.values()
                        if isinstance(n.get("inputs", {}).get(entrada), str)), None)
        if not archivo:
            return None
        for carpeta in carpetas.get(CARPETA_DE[entrada], []):
            ruta = Path(carpeta) / archivo
            if ruta.is_file():
                return archivo, await asyncio.to_thread(cabecera, ruta)
        return archivo, None

    avisos = []
    del_workflow = familias["workflow"]
    if modelo_propio and (leido := await leer("unet_name") or await leer("ckpt_name")):
        archivo, cab = leido
        familias["modelo"] = familia = familia_modelo(cab) if cab else None
        if familia and not compatibles(familia, del_workflow):
            avisos.append(f"Tu modelo «{archivo}» es {nombre(familia)}, pero el estudio usa el workflow de "
                          f"{nombre(del_workflow)}: así da el error «mat1 and mat2». Para arreglarlo, "
                          f"{como_arreglarlo(familia)}")
    if lora_propio and (leido := await leer("lora_name")):
        archivo, cab = leido
        familias["lora"] = familia = familia_lora(cab) if cab else None
        destino = familias.get("modelo") or del_workflow
        if familia and not compatibles(familia, destino):
            avisos.append(f"Tu LoRA «{archivo}» parece de {nombre(familia)} y el modelo es {nombre(destino)}: "
                          "no le hará efecto o dará error. Usa un LoRA entrenado sobre ese mismo modelo.")
    return avisos, familias
