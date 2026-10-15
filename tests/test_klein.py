"""FLUX.2 Klein 4B: su workflow, la familia de tu modelo y de tu LoRA, y el error «mat1 and mat2» explicado."""

import asyncio
import json
import struct
import time

import pytest
from fastapi.testclient import TestClient

from app import arquitectura, config, workflow
from app.main import crear_app
from app.probar_modelo import NoSePuede, Prueba
from tests.conftest import preparar_ajustes
from tests.test_estudio import PROFE, entrar, esperar_fin, foto_base64


def safetensors(ruta, formas: dict):
    """Un .safetensors con solo la cabecera: basta para saber la familia."""
    cab = {k: {"dtype": "BF16", "shape": f, "data_offsets": [0, 0]} for k, f in formas.items()}
    datos = json.dumps(cab).encode()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(struct.pack("<Q", len(datos)) + datos)


MODELO_KLEIN = {"double_stream_modulation_img.lin.weight": [18432, 3072], "txt_in.weight": [3072, 7680],
                "img_in.weight": [3072, 128], "double_blocks.0.img_attn.norm.key_norm.scale": [128]}
MODELO_ZIMAGE = {"cap_embedder.1.weight": [3840, 2560], "noise_refiner.0.attention.k_norm.weight": [128]}
MODELO_SDXL = {"model.diffusion_model.input_blocks.0.0.weight": [320, 4, 3, 3],
               "model.diffusion_model.label_emb.0.0.weight": [1280, 2816]}
MODELO_FLUX1 = {"double_blocks.0.img_attn.norm.key_norm.scale": [128], "img_in.weight": [3072, 64],
                "txt_in.weight": [3072, 4096]}
LORA_KLEIN = {**{f"diffusion_model.double_blocks.{d}.img_attn.qkv.lora_A.weight": [16, 3072] for d in range(5)},
              **{f"diffusion_model.single_blocks.{s}.linear1.lora_A.weight": [16, 3072] for s in range(20)},
              **{f"diffusion_model.single_blocks.{s}.linear1.lora_B.weight": [27648, 16] for s in range(20)}}
LORA_FLUX1 = {**{f"lora_unet_double_blocks_{d}_img_attn_qkv.lora_down.weight": [16, 3072] for d in range(19)},
              "lora_unet_double_blocks_0_img_mod_lin.lora_down.weight": [16, 3072],
              **{f"lora_unet_single_blocks_{s}_linear1.lora_down.weight": [16, 3072] for s in range(38)}}
LORA_ZIMAGE = {f"diffusion_model.layers.{n}.attention.qkv.lora_A.weight": [16, 3840] for n in range(30)}
LORA_SDXL = {"lora_unet_input_blocks_4_1_transformer_blocks_0_attn2_to_k.lora_down.weight": [16, 2048],
             "lora_te2_text_model_encoder_layers_0_mlp_fc1.lora_down.weight": [16, 1280]}


def con_mi_modelo(tmp_path, monkeypatch, url, **mio) -> config.Ajustes:
    """Ajustes con el apartado [mi_modelo] que se pida."""
    aj = preparar_ajustes(tmp_path, monkeypatch, url)
    ruta = tmp_path / "config" / "ajustes.toml"
    toml = ruta.read_text(encoding="utf-8")
    for clave, valor in mio.items():
        actual = next(linea for linea in toml.splitlines() if linea.startswith(f"{clave} = "))
        toml = toml.replace(actual, f"{clave} = {json.dumps(valor)}", 1)
    ruta.write_text(toml, encoding="utf-8")
    return config.cargar(ruta) if mio else aj


def test_familias_por_la_cabecera(tmp_path):
    for formas, familia in ((MODELO_KLEIN, "flux2-klein-4b"), (MODELO_ZIMAGE, "z-image"), (MODELO_SDXL, "sdxl"),
                            (MODELO_FLUX1, "flux1")):
        safetensors(tmp_path / "m.safetensors", formas)
        assert arquitectura.familia_modelo(arquitectura.cabecera(tmp_path / "m.safetensors")) == familia
    for formas, familia in ((LORA_KLEIN, "flux2-klein-4b"), (LORA_FLUX1, "flux1"), (LORA_ZIMAGE, "z-image"),
                            (LORA_SDXL, "sdxl")):
        safetensors(tmp_path / "l.safetensors", formas)
        assert arquitectura.familia_lora(arquitectura.cabecera(tmp_path / "l.safetensors")) == familia
    (tmp_path / "roto.safetensors").write_bytes(b"no soy un safetensors")
    assert arquitectura.cabecera(tmp_path / "roto.safetensors") is None


def test_familia_del_workflow_y_compatibilidad():
    klein = json.loads((config.RAIZ / "config" / "plantillas" / "flux2_klein_4b.json").read_text(encoding="utf-8"))
    normal = json.loads((config.RAIZ / config.WORKFLOW_NORMAL).read_text(encoding="utf-8"))
    assert arquitectura.familia_workflow(klein) == "flux2-klein-4b"
    assert arquitectura.familia_workflow(normal) == "z-image"
    assert arquitectura.compatibles("flux2-klein-4b", "flux2") and arquitectura.compatibles("sd", "sdxl")
    assert not arquitectura.compatibles("flux2-klein-4b", "z-image")
    assert not arquitectura.compatibles("sdxl", "sd15")


def test_error_mat1_mat2_explicado():
    texto = arquitectura.explicar("mat1 and mat2 shapes cannot be multiplied (512x2560 and 7680x3072)")
    assert "FLUX.2 Klein 4B" in texto and 'base = "flux2-klein-4b"' in texto and "2560" in texto
    assert "SDXL" in arquitectura.explicar("mat1 and mat2 shapes cannot be multiplied (154x2560 and 2048x640)")
    assert arquitectura.explicar("CUDA out of memory") == "CUDA out of memory"


def test_workflow_de_klein(tmp_path, monkeypatch, comfy_falso):
    aj = con_mi_modelo(tmp_path, monkeypatch, comfy_falso[0], base="flux2-klein-4b")
    assert aj.base == "flux2-klein-4b" and arquitectura.familia_workflow(aj.workflow) == "flux2-klein-4b"
    nodos = workflow.localizar(aj.workflow)
    assert (nodos.prompt, nodos.tamanos, nodos.semillas) == ("74", ["66", "62"], [("73", "noise_seed")])
    assert nodos.admite_fotos and nodos.edita and nodos.guia == "63"  # la foto va de referencia a la guía
    listo = workflow.preparar(aj.workflow, nodos, "una murga", 832, 1216, 99, "x")
    assert listo["66"]["inputs"]["width"] == listo["62"]["inputs"]["width"] == 832
    assert listo["62"]["inputs"]["height"] == 1216 and listo["73"]["inputs"]["noise_seed"] == 99
    con_lora = workflow.con_mi_modelo(aj.workflow, "mi_klein.safetensors", "lora.safetensors", 0.7)
    assert con_lora["70"]["inputs"]["unet_name"] == "mi_klein.safetensors"
    assert con_lora["63"]["inputs"]["model"] == [workflow.LORA, 0] and con_lora["74"]["inputs"]["clip"] == [workflow.LORA, 1]
    assert workflow.ajustar(aj.workflow, pasos=8, cfg=2)["62"]["inputs"]["steps"] == 8


def test_base_auto_por_el_nombre_y_klein_base(tmp_path, monkeypatch, comfy_falso):
    aj = con_mi_modelo(tmp_path, monkeypatch, comfy_falso[0], modelo="mi_klein_carnaval.safetensors")
    assert aj.base == "flux2-klein-4b"
    (tmp_path / "b").mkdir()
    (tmp_path / "c").mkdir()
    aj = con_mi_modelo(tmp_path / "b", monkeypatch, comfy_falso[0], base="flux2-klein-4b-base")
    assert aj.workflow["62"]["inputs"]["steps"] == 20 and aj.workflow["63"]["inputs"]["cfg"] == 5.0
    assert aj.workflow["70"]["inputs"]["unet_name"] == "flux-2-klein-base-4b.safetensors"
    assert aj.workflow["76"]["class_type"] == "CLIPTextEncode" and aj.workflow["76"]["inputs"]["text"] == ""
    assert workflow.localizar(aj.workflow).prompt == "74"  # el positivo, no el negativo vacío
    with pytest.raises(ValueError, match="flux2-klein-4b"):
        con_mi_modelo(tmp_path / "c", monkeypatch, comfy_falso[0], base="klein")


def esperar_comprobado(c):
    estudio, fin = c.app.state.estudio, time.time() + 5
    while not estudio._comprobado and time.time() < fin:
        time.sleep(0.05)
    return c.get("/api/panel/estado", headers=PROFE).json()


def test_estudio_con_tu_klein_y_tu_lora(tmp_path, monkeypatch, comfy_falso):
    url, comfy_app = comfy_falso
    safetensors(tmp_path / "unet" / "mi_klein_carnaval.safetensors", MODELO_KLEIN)
    safetensors(tmp_path / "loras" / "otro_lora.safetensors", LORA_KLEIN)
    comfy_app.state.carpetas = {"diffusion_models": [str(tmp_path / "unet")], "loras": [str(tmp_path / "loras")]}
    aj = con_mi_modelo(tmp_path, monkeypatch, url, base="flux2-klein-4b", modelo="mi_klein_carnaval",
                       lora="otro_lora", fuerza_lora=0.9)
    with TestClient(crear_app(aj)) as c:
        estado = esperar_comprobado(c)
        assert estado["avisos"] == []
        assert estado["modelo"]["familia"] == "FLUX.2 Klein 4B"
        h = entrar(c)
        id_ = c.post("/api/crear", json={"prompt": "Una murga de pulpos", "estilo": "libre", "formato": "cuadrado"},
                     headers=h).json()["id"]
        assert esperar_fin(c, id_, h)["estado"] == "hecho"
    enviado = comfy_app.state.recibidos[-1]
    assert enviado["64"]["class_type"] == "SamplerCustomAdvanced"
    assert enviado["70"]["inputs"] == {"unet_name": "mi_klein_carnaval.safetensors", "weight_dtype": "fp8_e4m3fn"}
    assert enviado[workflow.LORA]["inputs"]["lora_name"] == "otro_lora.safetensors"
    assert enviado["74"]["inputs"]["text"] == "Una murga de pulpos"


def test_el_panel_avisa_si_el_modelo_no_es_de_la_familia(tmp_path, monkeypatch, comfy_falso):
    url, comfy_app = comfy_falso
    safetensors(tmp_path / "unet" / "mi_klein_carnaval.safetensors", MODELO_KLEIN)
    safetensors(tmp_path / "loras" / "otro_lora.safetensors", LORA_SDXL)
    comfy_app.state.carpetas = {"diffusion_models": [str(tmp_path / "unet")], "loras": [str(tmp_path / "loras")]}
    aj = con_mi_modelo(tmp_path, monkeypatch, url, base="z-image-turbo", modelo="mi_klein_carnaval",
                       lora="otro_lora")
    with TestClient(crear_app(aj)) as c:
        avisos = esperar_comprobado(c)["avisos"]
        assert any("es FLUX.2 Klein 4B" in a and 'base = "flux2-klein-4b"' in a for a in avisos)
        assert any("parece de SDXL" in a for a in avisos)
        h = entrar(c)
        id_ = c.post("/api/crear", json={"prompt": "Una murga", "estilo": "libre", "formato": "cuadrado"},
                     headers=h).json()["id"]
        error = esperar_fin(c, id_, h)
        assert error["estado"] == "error" and "Parece un modelo FLUX.2 Klein 4B" in error["error"]


def test_la_prueba_avisa_antes_de_pintar(tmp_path, monkeypatch, comfy_falso):
    url, comfy_app = comfy_falso
    safetensors(tmp_path / "unet" / "mi_klein_carnaval.safetensors", MODELO_KLEIN)
    comfy_app.state.carpetas = {"diffusion_models": [str(tmp_path / "unet")]}
    aj = con_mi_modelo(tmp_path, monkeypatch, url, base="z-image-turbo", modelo="mi_klein_carnaval")
    antes = len(comfy_app.state.recibidos)
    with pytest.raises(NoSePuede, match="FLUX.2 Klein 4B"):
        asyncio.run(Prueba(aj, ["una murga"], [], interprete=False, salida=lambda *_: None,
                           carpeta=tmp_path / "p").ejecutar())
    assert len(comfy_app.state.recibidos) == antes  # no ha pintado nada


def test_la_prueba_para_en_el_primer_error(tmp_path, monkeypatch, comfy_falso):
    url, comfy_app = comfy_falso  # sin carpetas: no puede mirar la familia antes y falla al pintar
    aj = con_mi_modelo(tmp_path, monkeypatch, url, base="z-image-turbo", modelo="mi_klein_carnaval",
                       lora="otro_lora")
    lineas = []
    with pytest.raises(NoSePuede, match="No ha salido ninguna imagen") as e:
        asyncio.run(Prueba(aj, ["una", "dos", "tres"], [0.5], interprete=False, salida=lineas.append,
                           carpeta=tmp_path / "p").ejecutar())
    assert "Parece un modelo FLUX.2 Klein 4B" in str(e.value)
    assert len(comfy_app.state.recibidos) == 3  # una por columna, no nueve


def test_la_prueba_con_klein(tmp_path, monkeypatch, comfy_falso):
    url, comfy_app = comfy_falso
    aj = con_mi_modelo(tmp_path, monkeypatch, url, base="flux2-klein-4b", lora="otro_lora")
    prueba = Prueba(aj, ["una murga", "un pulpo"], [0.5, 1.0], interprete=False, salida=lambda *_: None,
                    carpeta=tmp_path / "p")
    ruta = asyncio.run(prueba.ejecutar())
    assert ruta.exists() and [c.titulo for c in prueba.cols] == ["Sin LoRA", "LoRA 0.5", "LoRA 1"]
    assert all(wf["62"]["inputs"]["steps"] == 4 for wf in comfy_app.state.recibidos[-6:])


def test_klein_edita_tu_foto(tmp_path, monkeypatch, comfy_falso):
    """Con FLUX.2 Klein la foto va de referencia (ReferenceLatent), como en su plantilla oficial de edición."""
    url, comfy_app = comfy_falso
    aj = con_mi_modelo(tmp_path, monkeypatch, url, base="flux2-klein-4b")
    aj.revisar_antes = True
    with TestClient(crear_app(aj)) as c:
        info = c.get("/api/info").json()
        assert info["fotos"] is True and info["fuerzas"] == []  # editar no tiene "cuánto transformo"
        h = entrar(c)
        f = c.post("/api/fotos", json={"datos": foto_base64()}, headers=h).json()
        r = c.post("/api/crear", json={"prompt": "Conviérteme en reina del carnaval", "estilo": "carnaval",
                                       "foto": f["id"]}, headers=h)
        assert r.status_code == 200, r.text
        t = esperar_fin(c, r.json()["id"], h)
        assert t["estado"] == "hecho" and t["publico"]
        assert c.get("/api/panel/estado", headers=PROFE).json()["por_revisar"] == 1  # pasa por tu revisión
    enviado = comfy_app.state.recibidos[-1]
    assert enviado["9001"]["class_type"] == "LoadImage"
    assert enviado["9002"]["inputs"] == {"pixels": ["9001", 0], "vae": ["72", 0]}
    assert enviado["9003"] == {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["74", 0], "latent": ["9002", 0]}}
    assert enviado["9004"]["inputs"] == {"conditioning": ["76", 0], "latent": ["9002", 0]}
    assert enviado["63"]["inputs"]["positive"] == ["9003", 0] and enviado["63"]["inputs"]["negative"] == ["9004", 0]
    assert (enviado["66"]["inputs"]["width"], enviado["66"]["inputs"]["height"]) == (f["ancho"], f["alto"])
    assert enviado["62"]["inputs"]["width"] == f["ancho"]
    texto = enviado["74"]["inputs"]["text"]
    assert texto.startswith(workflow.FOTO_DE_REFERENCIA) and "Conviérteme en reina del carnaval" in texto
