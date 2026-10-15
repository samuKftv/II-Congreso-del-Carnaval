"""Tu modelo y tu LoRA: el workflow, la comprobación de archivos en ComfyUI y la hoja de prueba."""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import workflow
from app.config import RAIZ
from app.main import crear_app
from app.probar_modelo import CABECERA, CELDA, MARGEN, NoSePuede, Prueba
from tests.test_estudio import PROFE, entrar, esperar_fin


def plantilla():
    return json.loads((RAIZ / "config" / "workflow_api.json").read_text(encoding="utf-8"))


def sdxl():
    """Un workflow clásico: checkpoint completo, CLIP con capa saltada y sampling cambiado."""
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "10": {"class_type": "CLIPSetLastLayer", "inputs": {"clip": ["4", 1], "stop_at_clip_layer": -2}},
        "11": {"class_type": "ModelSamplingDiscrete", "inputs": {"model": ["4", 0], "sampling": "eps", "zsnr": False}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "x", "clip": ["10", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["10", 0]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "3": {"class_type": "KSampler", "inputs": {"model": ["11", 0], "positive": ["6", 0], "negative": ["7", 0],
                                                   "latent_image": ["5", 0], "seed": 1, "steps": 25, "cfg": 6.0,
                                                   "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "x"}},
    }


def test_modelo_y_lora_en_z_image():
    original = plantilla()
    wf = workflow.con_mi_modelo(original, "mi_modelo.safetensors", "mi_lora.safetensors", 0.8)
    assert wf["16"]["inputs"]["unet_name"] == "mi_modelo.safetensors"
    lora = wf[workflow.LORA]
    assert lora["class_type"] == "LoraLoader"
    assert lora["inputs"] == {"model": ["16", 0], "clip": ["18", 0], "lora_name": "mi_lora.safetensors",
                              "strength_model": 0.8, "strength_clip": 0.8}
    assert wf["3"]["inputs"]["model"] == [workflow.LORA, 0]
    assert wf["6"]["inputs"]["clip"] == wf["7"]["inputs"]["clip"] == [workflow.LORA, 1]
    assert original["16"]["inputs"]["unet_name"] == "z_image_turbo_bf16.safetensors"  # la plantilla no cambia
    assert workflow.LORA not in original
    # El resto de la app sigue encontrando sus nodos, y el fp8 se aplica a tu modelo
    nodos = workflow.localizar(wf)
    assert (nodos.prompt, nodos.tamano, nodos.semillas) == ("6", "13", [("3", "seed")])
    assert workflow.aligerar(wf)["16"]["inputs"]["weight_dtype"] == "fp8_e4m3fn"


def test_lora_en_workflow_con_checkpoint_y_nodos_intermedios():
    wf = workflow.con_mi_modelo(sdxl(), "mi_sdxl.safetensors", "mi_lora.safetensors", 0.7)
    assert wf["4"]["inputs"]["ckpt_name"] == "mi_sdxl.safetensors"
    lora = wf[workflow.LORA]["inputs"]
    assert (lora["model"], lora["clip"]) == (["4", 0], ["4", 1])  # justo detrás del cargador
    assert wf["11"]["inputs"]["model"] == [workflow.LORA, 0]
    assert wf["10"]["inputs"]["clip"] == [workflow.LORA, 1]
    assert wf["3"]["inputs"]["model"] == ["11", 0] and wf["6"]["inputs"]["clip"] == ["10", 0]
    assert wf["8"]["inputs"]["vae"] == ["4", 2]  # el VAE no pasa por el LoRA


def test_solo_lora_y_sin_cambios():
    wf = workflow.con_mi_modelo(plantilla(), lora="mi_lora.safetensors")
    assert wf["16"]["inputs"]["unet_name"] == "z_image_turbo_bf16.safetensors"
    assert wf[workflow.LORA]["inputs"]["lora_name"] == "mi_lora.safetensors"
    original = plantilla()
    assert workflow.con_mi_modelo(original) is original


def test_lora_solo_modelo_si_el_texto_no_usa_clip():
    wf = plantilla()
    wf["6"] = {"class_type": "TextEncodeExterno", "inputs": {"text": "x"}}
    listo = workflow.con_mi_modelo(wf, lora="mi_lora.safetensors", fuerza=0.5)
    assert listo[workflow.LORA] == {"class_type": "LoraLoaderModelOnly", "_meta": {"title": "Tu LoRA"},
                                    "inputs": {"model": ["16", 0], "lora_name": "mi_lora.safetensors",
                                               "strength_model": 0.5}}
    assert listo["7"]["inputs"]["clip"] == ["18", 0]


def test_cargador_desconocido():
    wf = plantilla()
    wf["16"] = {"class_type": "CargadorRaro", "inputs": {"ruta": "x"}}
    with pytest.raises(workflow.ErrorWorkflow, match="modelo"):
        workflow.con_mi_modelo(wf, modelo="mi_modelo.safetensors")
    assert workflow.con_mi_modelo(wf, lora="l.safetensors")["3"]["inputs"]["model"] == [workflow.LORA, 0]


def test_nombres_parecidos_y_palabra_clave():
    opciones = ["carnaval\\lora_carnaval.safetensors", "otro.safetensors", "a/repe.safetensors", "b/repe.safetensors"]
    assert workflow.parecido("lora_carnaval", opciones) == "carnaval\\lora_carnaval.safetensors"
    assert workflow.parecido("carnaval/LORA_carnaval.safetensors", opciones) == "carnaval\\lora_carnaval.safetensors"
    assert workflow.parecido("otro", opciones) == "otro.safetensors"
    assert workflow.parecido("repe.safetensors", opciones) is None  # dos posibles: no se adivina
    assert workflow.parecido("nada", opciones) is None
    assert workflow.con_palabra_clave("a carnival queen", "crnvl") == "crnvl, a carnival queen"
    assert workflow.con_palabra_clave("CRNVL style queen", "crnvl") == "CRNVL style queen"
    assert workflow.con_palabra_clave("a carnival queen", "") == "a carnival queen"


def comprobado(c, limite=5):
    estudio = c.app.state.estudio
    fin = time.time() + limite
    while not estudio._comprobado and time.time() < fin:
        time.sleep(0.05)
    assert estudio._comprobado, "el estudio no ha comprobado los archivos de ComfyUI"
    return c.get("/api/panel/estado", headers=PROFE).json()


def test_estudio_con_tu_modelo_y_tu_lora(ajustes, comfy_falso):
    _, comfy_app = comfy_falso
    ajustes.modelo, ajustes.lora, ajustes.fuerza_lora = "mi_modelo_carnaval", "lora_carnaval", 0.8
    ajustes.palabra_clave = "crnvl style"
    with TestClient(crear_app(ajustes)) as c:
        estado = comprobado(c)
        assert estado["avisos"] == []
        assert estado["modelo"] == {"modelo": "mi_modelo_carnaval.safetensors", "propio": True,
                                    "lora": "carnaval\\lora_carnaval.safetensors", "fuerza": 0.8,
                                    "palabra_clave": "crnvl style", "familia": "Z-Image Turbo"}
        h = entrar(c)
        id_ = c.post("/api/crear", json={"prompt": "Una murga de pulpos", "estilo": "libre", "formato": "cuadrado"}, headers=h).json()["id"]
        assert esperar_fin(c, id_, h)["estado"] == "hecho"
        enviado = comfy_app.state.recibidos[-1]
        assert enviado["16"]["inputs"] == {"unet_name": "mi_modelo_carnaval.safetensors", "weight_dtype": "fp8_e4m3fn"}
        assert enviado[workflow.LORA]["inputs"]["lora_name"] == "carnaval\\lora_carnaval.safetensors"
        assert enviado["6"]["inputs"]["text"] == "crnvl style, Una murga de pulpos"
        assert c.get(f"/api/trabajos/{id_}", headers=h).json()["prompt"] == "Una murga de pulpos"


def test_el_panel_avisa_si_falta_el_lora(ajustes):
    ajustes.lora = "no_existe.safetensors"
    with TestClient(crear_app(ajustes)) as c:
        estado = comprobado(c)
        assert estado["avisos"] == ["ComfyUI no tiene «no_existe.safetensors». Cópialo en la carpeta "
                                    "ComfyUI/models/loras y vuelve a abrir ComfyUI."]
        assert estado["modelo"]["modelo"] == "z_image_turbo_bf16.safetensors" and not estado["modelo"]["propio"]


def test_hoja_de_prueba_con_varias_fuerzas(ajustes, comfy_falso, tmp_path):
    _, comfy_app = comfy_falso
    ajustes.lora = "lora_carnaval"
    lineas = []
    prueba = Prueba(ajustes, ["Una murga de pulpos", "La reina del carnaval"], [0.5, 1.0], interprete=False,
                    salida=lineas.append, carpeta=tmp_path / "prueba")
    ruta = asyncio.run(prueba.ejecutar())
    assert [c.titulo for c in prueba.cols] == ["Sin LoRA", "LoRA 0.5", "LoRA 1"]
    with Image.open(ruta) as hoja:
        assert hoja.size == (MARGEN + 3 * CELDA, CABECERA + 2 * CELDA)
    assert len(list(ruta.parent.glob("*.png"))) == 6
    enviados = comfy_app.state.recibidos[-6:]
    fuerzas = [next((n["inputs"]["strength_model"] for n in wf.values() if n["class_type"] == "LoraLoader"), None)
               for wf in enviados]
    assert fuerzas == [None, None, 0.5, 0.5, 1.0, 1.0]
    semillas = [wf["3"]["inputs"]["seed"] for wf in enviados]
    assert semillas[0::2] == [semillas[0]] * 3 and semillas[1::2] == [semillas[1]] * 3  # misma semilla por idea
    texto = "\n".join(lineas)
    assert "RESULTADO DE LA PRUEBA" in texto and "s por imagen" in texto and "fuerza_lora" in texto


def test_hoja_sin_lora_compara_con_el_modelo_original(ajustes, comfy_falso, tmp_path):
    ajustes.modelo = "mi_modelo_carnaval.safetensors"
    prueba = Prueba(ajustes, ["Una murga de pulpos"], [], interprete=False, salida=lambda *_: None,
                    carpeta=tmp_path / "prueba")
    asyncio.run(prueba.ejecutar())
    assert [c.titulo for c in prueba.cols] == ["Modelo original", "Tu modelo"]
    _, comfy_app = comfy_falso
    assert [wf["16"]["inputs"]["unet_name"] for wf in comfy_app.state.recibidos[-2:]] == [
        "z_image_turbo_bf16.safetensors", "mi_modelo_carnaval.safetensors"]


def test_hoja_avisa_de_lo_que_falta(ajustes, tmp_path):
    sola = Prueba(ajustes, ["x"], [1.0], interprete=False)  # sin modelo ni LoRA: el del workflow, para comparar
    assert [c.titulo for c in sola.cols] == ["Z-Image Turbo"]
    ajustes.lora = "no_existe.safetensors"
    lineas = []
    prueba = Prueba(ajustes, ["x"], [1.0], interprete=False, salida=lineas.append, carpeta=tmp_path / "p")
    with pytest.raises(NoSePuede, match="Copia los archivos"):
        asyncio.run(prueba.ejecutar())
    assert any("models/loras" in linea for linea in lineas)
