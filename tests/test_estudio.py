"""Flujo completo contra el ComfyUI simulado."""

import base64
import io
import time

from fastapi.testclient import TestClient
from PIL import Image

from app.main import crear_app
from tests.conftest import preparar_ajustes, puerto_libre

PROFE = {"X-Clave": "secreta"}


def entrar(c, alias="Ana"):
    r = c.post("/api/entrar", json={"alias": alias, "codigo": "CARNAVAL"})
    assert r.status_code == 200, r.text
    return {"X-Token": r.json()["token"]}


def esperar_fin(c, id_, h, limite=10):
    fin = time.time() + limite
    while time.time() < fin:
        t = c.get(f"/api/trabajos/{id_}", headers=h).json()
        if t["estado"] in ("hecho", "error", "cancelado"):
            return t
        time.sleep(0.05)
    raise AssertionError(f"El trabajo no terminó: {t}")


def test_flujo_completo(ajustes, comfy_falso):
    _, comfy_app = comfy_falso
    with TestClient(crear_app(ajustes)) as c:
        info = c.get("/api/info").json()
        assert info["requiere_codigo"] and len(info["estilos"]) > 5

        h = entrar(c)
        r = c.post("/api/crear", json={"prompt": "Un gato con antifaz", "estilo": "cartel", "formato": "vertical"}, headers=h)
        assert r.status_code == 200, r.text
        id_ = r.json()["id"]

        # Una imagen en marcha por persona
        r = c.post("/api/crear", json={"prompt": "Otra cosa", "estilo": "foto", "formato": "cuadrado"}, headers=h)
        assert r.status_code == 409 and r.json()["id"] == id_

        t = esperar_fin(c, id_, h)
        assert t["estado"] == "hecho"
        im = Image.open(io.BytesIO(c.get(t["imagen"]).content))
        assert im.size == (832, 1216)
        assert c.get(t["mini"]).headers["content-type"] == "image/webp"
        assert "attachment" in c.get(t["imagen"] + "?descargar=1").headers["content-disposition"]

        enviado = comfy_app.state.recibidos[-1]
        assert enviado["6"]["inputs"]["text"] == ajustes.estilos["cartel"].aplicar("Un gato con antifaz")

        assert [x["id"] for x in c.get("/api/mis-creaciones", headers=h).json()] == [id_]
        assert c.get("/api/galeria").json()["imagenes"][0]["id"] == id_

        # Panel: requiere clave desde fuera del PC
        assert c.get("/api/panel/estado").status_code == 401
        estado = c.get("/api/panel/estado", headers=PROFE).json()
        assert estado["comfy"]["ok"] and estado["comfy"]["gpu"]["nombre"] == "cuda:0 NVIDIA GeForce RTX 5070"
        assert estado["estadisticas"]["hechas"] == 1

        # Retirar del proyector
        r = c.post("/api/panel/revisar", json={"ids": [id_], "decision": "rechazada"}, headers=PROFE)
        assert r.json()["cambiadas"] == 1
        assert c.get("/api/galeria").json()["imagenes"] == []
        assert c.get("/api/panel/imagenes", headers=PROFE).json()[0]["revision"] == "rechazada"


def test_validaciones_y_moderacion(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        assert c.post("/api/entrar", json={"alias": "Ana", "codigo": "otro"}).status_code == 403
        assert c.post("/api/entrar", json={"alias": "   ", "codigo": "carnaval"}).status_code == 422
        h = entrar(c)
        pedido = {"estilo": "foto", "formato": "cuadrado"}
        r = c.post("/api/crear", json={"prompt": "Una persona desnuda", **pedido}, headers=h)
        assert r.status_code == 422 and "no están permitidas" in r.json()["detail"]
        assert c.post("/api/crear", json={"prompt": "ab", **pedido}, headers=h).status_code == 422
        assert c.post("/api/crear", json={"prompt": "Un perro", "estilo": "x", "formato": "cuadrado"}, headers=h).status_code == 422
        assert c.post("/api/crear", json={"prompt": "Un perro", **pedido}, headers={"X-Token": "falso"}).status_code == 401


def test_estudio_cerrado_y_bloqueo(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        pedido = {"prompt": "Un perro bailando", "estilo": "foto", "formato": "cuadrado"}
        c.post("/api/panel/abierto", json={"valor": False}, headers=PROFE)
        assert c.post("/api/crear", json=pedido, headers=h).status_code == 423
        c.post("/api/panel/abierto", json={"valor": True}, headers=PROFE)

        token = h["X-Token"]
        c.post("/api/panel/bloquear", json={"token": token, "valor": True}, headers=PROFE)
        assert c.post("/api/crear", json=pedido, headers=h).status_code == 403
        assert c.get("/api/panel/estado", headers=PROFE).json()["bloqueados"][0]["alias"] == "Ana"
        c.post("/api/panel/bloquear", json={"token": token, "valor": False}, headers=PROFE)
        assert c.post("/api/crear", json=pedido, headers=h).status_code == 200


def test_error_de_comfy_llega_al_alumno(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        r = c.post("/api/crear", json={"prompt": "Esto FALLA seguro", "estilo": "libre", "formato": "cuadrado"}, headers=h)
        t = esperar_fin(c, r.json()["id"], h)
        assert t["estado"] == "error" and "out of memory" in t["error"]
        # Puede volver a intentarlo
        r = c.post("/api/crear", json={"prompt": "Un perro", "estilo": "libre", "formato": "cuadrado"}, headers=h)
        assert esperar_fin(c, r.json()["id"], h)["estado"] == "hecho"


def test_turnos_y_cancelar_en_cola(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        ana, luis = entrar(c, "Ana"), entrar(c, "Luis")
        pedido = {"prompt": "Un desfile de robots", "estilo": "foto", "formato": "cuadrado"}
        id_ana = c.post("/api/crear", json=pedido, headers=ana).json()["id"]
        t_luis = c.post("/api/crear", json=pedido, headers=luis).json()
        assert t_luis["delante"] == 1 and t_luis["segundos"] > 0
        assert c.post(f"/api/trabajos/{t_luis['id']}/cancelar", headers=luis).status_code == 200
        assert c.get(f"/api/trabajos/{t_luis['id']}", headers=luis).json()["estado"] == "cancelado"
        # Nadie ve trabajos ajenos
        assert c.get(f"/api/trabajos/{id_ana}", headers=luis).status_code == 404
        assert esperar_fin(c, id_ana, ana)["estado"] == "hecho"


def test_miniaturas_de_estilos_y_temas(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        n = c.post("/api/panel/miniaturas", headers=PROFE).json()["encoladas"]

        def tarjetas():
            info = c.get("/api/info").json()
            return info["estilos"] + info["temas"]

        fin = time.time() + 30
        while time.time() < fin and any(e["miniatura"] is None for e in tarjetas()):
            time.sleep(0.1)
        todas = tarjetas()
        assert n == len(todas) and all(e["miniatura"] for e in todas)
        assert c.get(todas[-1]["miniatura"]).headers["content-type"] == "image/webp"
        # No aparecen en el proyector ni cuentan como imágenes del alumnado
        assert c.get("/api/galeria").json()["imagenes"] == []


def test_sin_comfy_la_imagen_espera_en_cola(tmp_path, monkeypatch):
    ajustes = preparar_ajustes(tmp_path, monkeypatch, f"http://127.0.0.1:{puerto_libre()}")
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        t = c.post("/api/crear", json={"prompt": "Un perro", "estilo": "foto", "formato": "cuadrado"}, headers=h).json()
        time.sleep(0.5)
        t = c.get(f"/api/trabajos/{t['id']}", headers=h).json()
        assert t["estado"] == "cola" and t["comfy_ok"] is False
        assert c.get("/api/info").json()["comfy_ok"] is False


def test_qr_y_paginas(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        assert c.get("/qr.svg").headers["content-type"] == "image/svg+xml"
        for ruta in ("/", "/panel", "/proyector", "/static/alumno.js"):
            assert c.get(ruta).status_code == 200
        assert c.get("/img/../../config/ajustes.toml").status_code == 404


def test_elegir_direccion_del_qr(ajustes, monkeypatch):
    monkeypatch.setattr("app.main.direcciones_locales", lambda: ["192.168.1.50", "172.20.0.1"])
    with TestClient(crear_app(ajustes)) as c:
        e = c.get("/api/panel/estado", headers=PROFE).json()
        assert e["direcciones"] == ["192.168.1.50", "172.20.0.1"]
        assert e["url_alumnado"] == "http://192.168.1.50:8080/?c=carnaval"
        assert c.post("/api/panel/direccion", json={"direccion": "8.8.8.8"}, headers=PROFE).status_code == 422
        r = c.post("/api/panel/direccion", json={"direccion": "172.20.0.1"}, headers=PROFE)
        assert r.json()["url_alumnado"] == "http://172.20.0.1:8080/?c=carnaval"
        assert c.get("/api/info").json()["url"] == "http://172.20.0.1:8080/?c=carnaval"
        assert c.get("/api/galeria").json()["url"] == "http://172.20.0.1:8080/?c=carnaval"
        assert c.post("/api/panel/direccion", json={"direccion": "192.168.1.50"}).status_code == 401


def foto_base64(ancho=1200, alto=1600) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (ancho, alto), (30, 120, 200)).save(buffer, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def test_foto_como_base_privada_por_defecto(ajustes, comfy_falso):
    _, comfy_app = comfy_falso
    with TestClient(crear_app(ajustes)) as c:
        assert c.get("/api/info").json()["fotos"] is True
        h = entrar(c)
        assert c.post("/api/fotos", json={"datos": "data:image/jpeg;base64,AAAA"}, headers=h).status_code == 422
        f = c.post("/api/fotos", json={"datos": foto_base64()}, headers=h).json()
        assert (f["ancho"], f["alto"]) == (880, 1184)
        pedido = {"prompt": "Conviérteme en arlequín", "estilo": "foto", "tema": "venecia", "foto": f["id"]}
        assert c.post("/api/crear", json=pedido, headers=h).status_code == 422  # falta la fuerza
        r = c.post("/api/crear", json={**pedido, "fuerza": "mucho"}, headers=h)
        assert r.status_code == 200, r.text
        t = esperar_fin(c, r.json()["id"], h)
        assert t["estado"] == "hecho" and t["con_foto"] and not t["publico"]
        assert Image.open(io.BytesIO(c.get(t["imagen"]).content)).size == (880, 1184)

        enviado = comfy_app.state.recibidos[-1]
        assert enviado["9001"]["class_type"] == "LoadImage"
        assert enviado["3"]["inputs"]["latent_image"] == ["9002", 0] and enviado["3"]["inputs"]["denoise"] == 0.82
        assert "13" not in enviado  # el lienzo vacío sobra
        assert "Carnival of Venice" in enviado["6"]["inputs"]["text"]

        # Privada: ni proyector ni galería; sí en "mis imágenes"
        assert c.get("/api/galeria").json()["imagenes"] == []
        assert c.get("/api/mis-creaciones", headers=h).json()[0]["id"] == t["id"]

        # Compartida si la persona lo marca
        r = c.post("/api/crear", json={**pedido, "fuerza": "poco", "publico": True}, headers=h)
        esperar_fin(c, r.json()["id"], h)
        assert [x["id"] for x in c.get("/api/galeria").json()["imagenes"]] == [r.json()["id"]]


def test_votos(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        ana, luis = entrar(c, "Ana"), entrar(c, "Luis")
        r = c.post("/api/crear", json={"prompt": "Un dragón de carnaval", "estilo": "foto", "formato": "cuadrado"}, headers=ana)
        id_ = esperar_fin(c, r.json()["id"], ana)["id"]
        assert c.post(f"/api/trabajos/{id_}/voto", json={"valor": True}, headers=ana).status_code == 422  # la suya
        assert c.post(f"/api/trabajos/{id_}/voto", json={"valor": True}, headers=luis).json() == {"votos": 1, "votado": True}
        assert c.post(f"/api/trabajos/{id_}/voto", json={"valor": True}, headers=luis).json()["votos"] == 1  # solo un voto
        g = c.get("/api/galeria?ranking=true", headers=luis).json()
        assert g["imagenes"][0]["votos"] == 1 and g["imagenes"][0]["votado"] and not g["imagenes"][0]["mia"]
        assert g["ranking"][0]["id"] == id_
        assert c.get("/api/galeria", headers=ana).json()["imagenes"][0]["mia"] is True
        assert c.post(f"/api/trabajos/{id_}/voto", json={"valor": False}, headers=luis).json()["votos"] == 0
        # Imagen retirada: no se puede votar
        c.post("/api/panel/revisar", json={"ids": [id_], "decision": "rechazada"}, headers=PROFE)
        assert c.post(f"/api/trabajos/{id_}/voto", json={"valor": True}, headers=luis).status_code == 404


def test_reto_completo(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        ana, luis = entrar(c, "Ana"), entrar(c, "Luis")
        pedido = {"prompt": "Mi disfraz soñado", "estilo": "foto", "formato": "cuadrado"}
        fuera = esperar_fin(c, c.post("/api/crear", json=pedido, headers=ana).json()["id"], ana)["id"]

        r = c.post("/api/panel/reto", json={"titulo": "Tu disfraz soñado", "minutos": 10}, headers=PROFE).json()
        assert r["fase"] == "creando" and 590 <= r["quedan"] <= 600
        assert c.get("/api/info").json()["reto"]["titulo"] == "Tu disfraz soñado"
        dentro = esperar_fin(c, c.post("/api/crear", json=pedido, headers=ana).json()["id"], ana)["id"]
        assert [x["id"] for x in c.get("/api/galeria?ambito=reto").json()["imagenes"]] == [dentro]

        c.post(f"/api/trabajos/{dentro}/voto", json={"valor": True}, headers=luis)
        assert c.post("/api/panel/reto/fase", json={"fase": "votando"}, headers=PROFE).json()["fase"] == "votando"
        # Lo creado durante la votación ya no participa
        tarde = esperar_fin(c, c.post("/api/crear", json=pedido, headers=luis).json()["id"], luis)["id"]
        assert tarde not in [x["id"] for x in c.get("/api/galeria?ambito=reto").json()["imagenes"]]

        podio = c.post("/api/panel/reto/fase", json={"fase": "podio"}, headers=PROFE).json()["podio"]
        assert podio[0]["id"] == dentro and podio[0]["votos"] == 1 and fuera not in [x["id"] for x in podio]
        c.post("/api/panel/reto/fase", json={"fase": "cerrado"}, headers=PROFE)
        assert c.get("/api/galeria").json()["reto"] is None


def test_reto_pasa_solo_a_votacion(ajustes, monkeypatch):
    with TestClient(crear_app(ajustes)) as c:
        c.post("/api/panel/reto", json={"titulo": "Rápido", "minutos": 1}, headers=PROFE)
        real = time.time
        monkeypatch.setattr("app.main.time.time", lambda: real() + 61)
        assert c.get("/api/info").json()["reto"]["fase"] == "votando"


def test_identidad_del_congreso(tmp_path, monkeypatch, comfy_falso):
    ajustes = preparar_ajustes(tmp_path, monkeypatch, comfy_falso[0])
    with TestClient(crear_app(ajustes)) as c:  # la configuración del repositorio trae cartel, logo y colores
        info = c.get("/api/info").json()
        assert info["evento"] == "CarnaLab 2026" and "Profesionalización" in info["congreso"]
        assert c.get(info["logo"]).headers["content-type"] == "image/png"
        assert c.get(info["cartel"]).headers["content-type"] == "image/jpeg"
        css = c.get("/tema.css").text
        assert "--noche:#003060" in css and "--tinta:#003060" in css and "--deco-1:#3d86b3" in css
        assert 'fill="#003060"' in c.get("/qr.svg").text or "#003060" in c.get("/qr.svg").text

    ajustes.logo = ajustes.cartel = None
    ajustes.colores = {}
    with TestClient(crear_app(ajustes)) as c:
        info = c.get("/api/info").json()
        assert info["logo"] is None and info["cartel"] is None
        assert c.get("/logo").status_code == 404 and c.get("/cartel").status_code == 404
        assert c.get("/tema.css").text == ""


def test_comfy_auto_encuentra_el_puerto(comfy_falso, monkeypatch):
    import asyncio
    from app import comfy as modulo

    url_buena = comfy_falso[0]
    monkeypatch.setattr(modulo, "CANDIDATAS", [f"http://127.0.0.1:{puerto_libre()}", url_buena])

    async def probar():
        cliente = modulo.ComfyUI("auto")
        try:
            datos = await cliente.estado()
            return datos, cliente.url
        finally:
            await cliente.cerrar()

    datos, url = asyncio.run(probar())
    assert datos["devices"][0]["name"].startswith("cuda:0") and url == url_buena


def test_puerto_ocupado_avisa_de_otro_estudio(ajustes):
    import socket
    import threading

    import uvicorn

    from app.__main__ import puerto_ocupado

    puerto = puerto_libre()
    assert puerto_ocupado(puerto) is None
    servidor = uvicorn.Server(uvicorn.Config(crear_app(ajustes), host="0.0.0.0", port=puerto, log_level="warning"))
    servidor.install_signal_handlers = lambda: None
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.05)
    try:
        assert "Ya hay un Estudio abierto" in puerto_ocupado(puerto)
    finally:
        servidor.should_exit = True
        hilo.join(5)
    otro_puerto = puerto_libre()
    with socket.socket() as otro:
        otro.bind(("0.0.0.0", otro_puerto))
        otro.listen()
        assert "otro programa" in puerto_ocupado(otro_puerto)


def crear_y_esperar(c, h, prompt="Una máscara de plumas"):
    r = c.post("/api/crear", json={"prompt": prompt, "estilo": "foto", "formato": "cuadrado"}, headers=h)
    assert r.status_code == 200, r.text
    return esperar_fin(c, r.json()["id"], h)


def test_concurso_con_revision_previa(tmp_path, monkeypatch, comfy_falso):
    ajustes = preparar_ajustes(tmp_path, monkeypatch, comfy_falso[0], revisar_antes=True)
    with TestClient(crear_app(ajustes)) as c:
        assert c.get("/api/info").json()["concurso"] == {"vista": "mosaico", "votacion_abierta": True, "revisar_antes": True}
        ana, luis = entrar(c, "Ana"), entrar(c, "Luis")
        a1 = crear_y_esperar(c, ana, "Una reina del Teide")
        a2 = crear_y_esperar(c, ana, "Una murga de robots")
        l1 = crear_y_esperar(c, luis, "Un pulpo pirata")

        # Nada es público hasta que el profesor lo aprueba; su autor sí la ve
        assert a1["revision"] == "pendiente"
        assert [x["revision"] for x in c.get("/api/mis-creaciones", headers=ana).json()] == ["pendiente", "pendiente"]
        assert c.get("/api/galeria").json()["imagenes"] == [] and c.get("/api/galeria").json()["en_revision"] == 3
        assert c.get("/api/mosaico").json() == {"piezas": [], "en_revision": 3}
        assert c.post(f"/api/trabajos/{a1['id']}/voto", json={"valor": True}, headers=luis).status_code == 404

        # Bandeja del panel: de la más antigua a la más nueva
        rev = c.get("/api/panel/revision", headers=PROFE).json()
        assert rev["total"] == 3 and [x["id"] for x in rev["imagenes"]] == [a1["id"], a2["id"], l1["id"]]
        assert c.get("/api/panel/revision").status_code == 401
        assert c.get("/api/panel/estado", headers=PROFE).json()["por_revisar"] == 3

        # Aprobar en orden distinto al de creación: el mosaico sigue el orden de aprobación
        c.post("/api/panel/revisar", json={"ids": [l1["id"]], "decision": "aprobada"}, headers=PROFE)
        r = c.post("/api/panel/revisar", json={"ids": [a1["id"], "../x"], "decision": "aprobada"}, headers=PROFE).json()
        assert r == {"cambiadas": 1, "por_revisar": 1}
        c.post("/api/panel/revisar", json={"ids": [a2["id"]], "decision": "rechazada"}, headers=PROFE)
        assert c.post("/api/panel/revisar", json={"ids": [a2["id"]], "decision": "quizas"}, headers=PROFE).status_code == 422
        piezas = c.get("/api/mosaico").json()["piezas"]
        assert [p["id"] for p in piezas] == [l1["id"], a1["id"]]
        assert piezas[0]["alias"] == "Luis" and piezas[0]["mini"].endswith("/mini.webp")
        tesela = Image.open(io.BytesIO(c.get(piezas[0]["tesela"]).content))
        assert tesela.size == (160, 160)
        (ajustes.datos / "teselas" / f"{l1['id']}.webp").unlink()  # imagen antigua: se hace al pedirla
        assert c.get(piezas[0]["tesela"]).status_code == 200
        assert {x["id"] for x in c.get("/api/galeria").json()["imagenes"]} == {l1["id"], a1["id"]}
        assert c.get(f"/api/trabajos/{a2['id']}", headers=ana).json()["revision"] == "rechazada"

        # Votar; con las ganadoras en pantalla la votación se cierra
        assert c.post(f"/api/trabajos/{a1['id']}/voto", json={"valor": True}, headers=luis).json()["votos"] == 1
        assert c.post("/api/panel/proyector", json={"vista": "podio"}, headers=PROFE).json()["votacion_abierta"] is False
        r = c.post(f"/api/trabajos/{l1['id']}/voto", json={"valor": True}, headers=ana)
        assert r.status_code == 423 and "cerrada" in r.json()["detail"]
        g = c.get("/api/galeria?ranking=true").json()
        assert g["concurso"]["vista"] == "podio" and g["ranking"][0]["id"] == a1["id"]
        c.post("/api/panel/proyector", json={"vista": "mosaico"}, headers=PROFE)
        assert c.post(f"/api/trabajos/{l1['id']}/voto", json={"valor": True}, headers=ana).status_code == 200
        assert c.post("/api/panel/proyector", json={"vista": "otra"}, headers=PROFE).status_code == 422

        # Sin revisión previa, lo nuevo se publica solo
        assert c.post("/api/panel/moderacion", json={"valor": False}, headers=PROFE).json()["revisar_antes"] is False
        libre = crear_y_esperar(c, luis, "Un dragón de confeti")
        assert libre["revision"] == "aprobada" and c.get("/api/mosaico").json()["piezas"][-1]["id"] == libre["id"]


def test_galeria_por_paginas(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        ids = [crear_y_esperar(c, h, f"Imagen número {i}")["id"] for i in range(3)]
        primera = c.get("/api/galeria?limite=2").json()["imagenes"]
        assert [x["id"] for x in primera] == ids[:0:-1]
        resto = c.get(f"/api/galeria?limite=2&antes={primera[-1]['fin']}").json()["imagenes"]
        assert [x["id"] for x in resto] == [ids[0]]


def test_migracion_de_imagenes_ocultas(tmp_path):
    import sqlite3

    from app.db import BaseDatos

    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE trabajos (id TEXT PRIMARY KEY, token TEXT NOT NULL, alias TEXT NOT NULL, prompt TEXT NOT NULL,
            estilo TEXT NOT NULL, formato TEXT NOT NULL, prompt_final TEXT NOT NULL, semilla INTEGER NOT NULL,
            estado TEXT NOT NULL, creado REAL NOT NULL, inicio REAL, fin REAL, error TEXT,
            oculto INTEGER NOT NULL DEFAULT 0, miniatura_estilo TEXT);
        INSERT INTO trabajos VALUES ('a', 't', 'Ana', 'x', 'foto', 'cuadrado', 'x', 1, 'hecho', 1, 1, 2, NULL, 0, NULL);
        INSERT INTO trabajos VALUES ('b', 't', 'Ana', 'y', 'foto', 'cuadrado', 'y', 1, 'hecho', 1, 1, 3, NULL, 1, NULL);
    """)
    con.close()
    db = BaseDatos(ruta)
    assert {t["id"]: t["revision"] for t in db.galeria(10, panel=True)} == {"a": "aprobada", "b": "rechazada"}
    assert [t["id"] for t in db.galeria(10)] == ["a"]


def test_votar_de_una_en_una(ajustes):
    with TestClient(crear_app(ajustes)) as c:
        ana, luis, eva = entrar(c, "Ana"), entrar(c, "Luis"), entrar(c, "Eva")
        de_ana = [crear_y_esperar(c, ana, f"Idea de Ana {i}")["id"] for i in range(3)]
        de_luis = crear_y_esperar(c, luis, "Idea de Luis")["id"]
        r = c.get("/api/votar", headers=eva).json()
        assert r["abierta"] and {t["id"] for t in r["imagenes"]} == set(de_ana) | {de_luis}
        # Ni las propias ni las ya votadas
        assert {t["id"] for t in c.get("/api/votar", headers=ana).json()["imagenes"]} == {de_luis}
        c.post(f"/api/trabajos/{de_ana[0]}/voto", json={"valor": True}, headers=eva)
        assert de_ana[0] not in {t["id"] for t in c.get("/api/votar", headers=eva).json()["imagenes"]}
        assert c.get("/api/votar").status_code == 401
        # Durante un reto, solo las del reto
        c.post("/api/panel/reto", json={"titulo": "Rápido", "minutos": 0}, headers=PROFE)
        del_reto = crear_y_esperar(c, luis, "Para el reto")["id"]
        assert [t["id"] for t in c.get("/api/votar?ambito=reto", headers=eva).json()["imagenes"]] == [del_reto]
        c.post("/api/panel/proyector", json={"vista": "podio"}, headers=PROFE)
        assert c.get("/api/votar", headers=eva).json()["abierta"] is False


def test_ligero_para_el_movil(ajustes, comfy_falso):
    with TestClient(crear_app(ajustes)) as c:
        h = entrar(c)
        t = crear_y_esperar(c, h, "Un farolillo de papel")
        # La imagen para ver es un WebP ligero; el PNG sigue para descargar
        vista = c.get(t["vista"])
        assert vista.headers["content-type"] == "image/webp"
        assert Image.open(io.BytesIO(vista.content)).size == (1024, 1024)
        (ajustes.datos / "vistas" / f"{t['id']}.webp").unlink()  # imagen antigua: se hace al pedirla
        assert c.get(t["vista"]).status_code == 200
        # Cartel y logo reducidos
        cartel = c.get("/cartel?ancho=480")
        assert cartel.headers["content-type"] == "image/webp" and Image.open(io.BytesIO(cartel.content)).width == 480
        assert len(cartel.content) < (ajustes.cartel.stat().st_size / 2)
        assert Image.open(io.BytesIO(c.get("/logo?alto=120").content)).height == 120
        assert c.get("/cartel?ancho=123").headers["content-type"] == "image/jpeg"  # tamaños fijos: original
        # Textos comprimidos; imágenes tal cual
        assert c.get("/static/alumno.js", headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding") == "gzip"
        assert c.get("/api/info", headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding") == "gzip"
        assert "content-encoding" not in c.get(t["imagen"], headers={"Accept-Encoding": "gzip"}).headers
        # El modelo se carga en fp8
        assert comfy_falso[1].state.recibidos[-1]["16"]["inputs"]["weight_dtype"] == "fp8_e4m3fn"
