import json

import pytest

from app import workflow
from app.config import RAIZ


def plantilla():
    return json.loads((RAIZ / "config" / "workflow_api.json").read_text(encoding="utf-8"))


def test_localiza_nodos_del_workflow_z_image():
    nodos = workflow.localizar(plantilla())
    assert nodos.prompt == "6"  # el positivo, no el negativo (7)
    assert nodos.tamano == "13"
    assert nodos.semillas == [("3", "seed")]
    assert nodos.guardar == ["9"]


def test_preparar_rellena_sin_tocar_la_plantilla():
    wf = plantilla()
    nodos = workflow.localizar(wf)
    listo = workflow.preparar(wf, nodos, "un gato", 832, 1216, 1234, "prueba/x")
    assert listo["6"]["inputs"]["text"] == "un gato"
    assert (listo["13"]["inputs"]["width"], listo["13"]["inputs"]["height"]) == (832, 1216)
    assert listo["3"]["inputs"]["seed"] == 1234
    assert listo["9"]["inputs"]["filename_prefix"] == "prueba/x"
    assert wf["6"]["inputs"]["text"] != "un gato"


def test_sigue_enlaces_intermedios_hasta_el_texto():
    wf = plantilla()
    # Positivo -> nodo intermedio -> CLIPTextEncode
    wf["20"] = {"class_type": "ConditioningSetTimestepRange", "inputs": {"conditioning": ["6", 0], "start": 0.0, "end": 1.0}}
    wf["3"]["inputs"]["positive"] = ["20", 0]
    assert workflow.localizar(wf).prompt == "6"


def test_nodo_indicado_en_ajustes_tiene_prioridad():
    assert workflow.localizar(plantilla(), nodo_prompt="7").prompt == "7"


def test_error_claro_si_no_hay_prompt():
    wf = {"1": {"class_type": "SaveImage", "inputs": {"filename_prefix": "x", "images": ["2", 0]}}}
    with pytest.raises(workflow.ErrorWorkflow, match="nodo_prompt"):
        workflow.localizar(wf)


def test_avisos_si_falta_tamano_o_guardado():
    wf = {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 0]}}}
    nodos = workflow.localizar(wf)
    avisos = workflow.avisos(wf, nodos)
    assert len(avisos) == 3
