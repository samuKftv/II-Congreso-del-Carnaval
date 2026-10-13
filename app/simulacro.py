"""Simulacro: muchas personas virtuales usan el estudio a la vez para ver cómo responde tu PC.

Uso, con el estudio abierto sobre la carpeta de prueba (3-PROBAR-CON-100-PERSONAS.bat lo hace todo):
    python -m app.simulacro [--personas 100] [--minutos 10] [--publicar]

Cada persona virtual entra con un alias "Prueba 001", pide una idea a tu ComfyUI, espera su turno
mirando el móvil (como un móvil de verdad), mira la galería, vota y vuelve a pedir otra.
Sin --publicar, las imágenes esperan en el panel a que las apruebes tú: así practicas de jurado.
Al terminar (o con Ctrl+C) cancelan lo que les quede en cola y se enseña un resumen.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time

import httpx

from . import config


class NoSePuede(Exception):
    """El simulacro no puede empezar (el estudio no está listo o usa los datos de verdad)."""


def minutos(segundos: float) -> str:
    segundos = max(0, round(segundos))
    return f"{segundos // 60}:{segundos % 60:02d}"


class Simulacro:
    def __init__(self, url: str, personas: int, segundos: float, publicar: bool, aj: config.Ajustes,
                 salida=print, llegada: float = 120):
        self.url, self.personas, self.segundos, self.publicar = url.rstrip("/"), personas, segundos, publicar
        self.codigo = aj.codigo
        self.ideas = aj.ideas or ["Una máscara de carnaval con plumas de colores"]
        self.estilos, self.temas = list(aj.estilos), list(aj.temas)
        self.formatos = list(aj.formatos)
        self.salida = salida
        self.llegada = min(llegada, segundos / 3)  # la gente no llega toda a la vez
        self.respuestas: list[float] = []  # tiempo de respuesta del servidor
        self.errores = 0
        self.esperas: list[float] = []     # de pedir la imagen a tenerla
        self.hechas = 0
        self.dentro = 0
        self.activos: dict[str, str] = {}  # token -> trabajo en cola
        self.inicio = time.time()
        self.media = 0.0
        self.pendientes_al_final = 0

    def cliente(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.url, timeout=60, trust_env=False)

    async def pedir(self, c: httpx.AsyncClient, metodo: str, ruta: str, **kw) -> httpx.Response | None:
        t0 = time.perf_counter()
        try:
            r = await c.request(metodo, ruta, **kw)
        except httpx.HTTPError:
            self.errores += 1
            return None
        self.respuestas.append(time.perf_counter() - t0)
        if r.status_code >= 500:
            self.errores += 1
        return r

    # --- Antes de empezar ---

    async def comprobar(self) -> dict:
        async with self.cliente() as c:
            for intento in range(60):  # el estudio y su conexión con ComfyUI pueden estar arrancando todavía
                try:
                    r = await c.get("/api/panel/estado")
                except httpx.HTTPError:
                    await asyncio.sleep(1)
                    continue
                if r.status_code != 200 or r.json()["comfy"]["ok"] or intento >= 20:
                    break
                await asyncio.sleep(1)
            else:
                raise NoSePuede(f"No encuentro el estudio en {self.url}. ¿Está abierta su ventana negra?")
        if r.status_code == 401:
            raise NoSePuede("El simulacro tiene que ejecutarse en el mismo PC que el estudio.")
        e = r.json()
        if not e.get("simulacro"):
            raise NoSePuede("El estudio abierto está usando los datos de verdad. Cierra su ventana negra y "
                            "arranca la prueba con 3-PROBAR-CON-100-PERSONAS.bat, que usa una carpeta aparte.")
        if not e["abierto"]:
            raise NoSePuede("El estudio está cerrado: ábrelo en el panel y vuelve a lanzar el simulacro.")
        if not e["comfy"]["ok"]:
            raise NoSePuede("El estudio no encuentra ComfyUI. Arráncalo y espera a que el panel diga «Conectado».")
        return e

    # --- Personas virtuales ---

    def pedido(self) -> dict:
        p = {"prompt": random.choice(self.ideas), "estilo": random.choice(self.estilos),
             "formato": random.choice(self.formatos)}
        if self.temas and random.random() < 0.5:
            p["tema"] = random.choice(self.temas)
        return p

    async def mirar(self, c: httpx.AsyncClient, h: dict, fin: float, galeria: bool, segundos: float):
        """Lo que hace el móvil mientras tanto: refrescar el estado y la galería, y votar alguna."""
        hasta = min(fin, time.time() + segundos)
        while time.time() < hasta:
            await self.pedir(c, "GET", "/api/info")
            if galeria:
                g = await self.pedir(c, "GET", "/api/galeria?limite=60&orden=recientes", headers=h)
                if g is not None and g.status_code == 200 and random.random() < 0.3:
                    candidatas = [t for t in g.json()["imagenes"] if not t.get("mia") and not t.get("votado")]
                    if candidatas:
                        await self.pedir(c, "POST", f"/api/trabajos/{random.choice(candidatas)['id']}/voto",
                                         json={"valor": True}, headers=h)
            await asyncio.sleep(min(8, max(0.1, hasta - time.time())))

    async def persona(self, numero: int, fin: float):
        await asyncio.sleep(random.uniform(0, self.llegada))
        if time.time() >= fin:
            return
        async with self.cliente() as c:
            r = await self.pedir(c, "POST", "/api/entrar", json={"alias": f"Prueba {numero:03d}", "codigo": self.codigo})
            if r is None or r.status_code != 200:
                return
            token = r.json()["token"]
            h = {"X-Token": token}
            self.dentro += 1
            galeria = random.random() < 0.5
            while time.time() < fin:
                r = await self.pedir(c, "POST", "/api/crear", json=self.pedido(), headers=h)
                if r is None or r.status_code not in (200, 409):
                    await asyncio.sleep(5)
                    continue
                id_, t0 = r.json()["id"], time.time()
                self.activos[token] = id_
                vuelta = 0
                while time.time() < fin:
                    await asyncio.sleep(1)  # como el móvil: pregunta cada segundo cómo va
                    t = await self.pedir(c, "GET", f"/api/trabajos/{id_}", headers=h)
                    vuelta += 1
                    if vuelta % 8 == 0:
                        await self.pedir(c, "GET", "/api/info")
                    if t is None or t.status_code != 200:
                        continue
                    estado = t.json()["estado"]
                    if estado == "hecho":
                        self.hechas += 1
                        self.esperas.append(time.time() - t0)
                        await self.pedir(c, "GET", t.json()["imagen"])
                    if estado in ("hecho", "error", "cancelado"):
                        self.activos.pop(token, None)
                        break
                await self.mirar(c, h, fin, galeria, random.uniform(20, 60))  # la mira y piensa otra idea

    # --- Jurado automático e informe ---

    async def jurado(self, fin: float):
        async with self.cliente() as c:
            while time.time() < fin:
                r = await self.pedir(c, "GET", "/api/panel/revision?limite=200")
                if r is not None and r.status_code == 200 and r.json()["imagenes"]:
                    ids = [t["id"] for t in r.json()["imagenes"]]
                    await self.pedir(c, "POST", "/api/panel/revisar", json={"ids": ids, "decision": "aprobada"})
                await asyncio.sleep(4)

    async def informe(self, fin: float):
        async with self.cliente() as c:
            while time.time() < fin:
                await asyncio.sleep(min(10, max(0.5, fin - time.time())))
                r = await self.pedir(c, "GET", "/api/panel/estado")
                if r is None or r.status_code != 200:
                    self.salida(f"[{minutos(time.time() - self.inicio)}] el estudio no responde")
                    continue
                e = r.json()
                self.media = e["media"] or self.media
                partes = [
                    f"[{minutos(time.time() - self.inicio)}] personas {self.dentro}/{self.personas}",
                    f"en cola {len(e['cola'])}",
                    f"hechas {self.hechas}",
                    f"{e['media']:.1f} s por imagen" if e["media"] else "midiendo la velocidad...",
                ]
                if self.esperas:
                    partes.append(f"espera media {minutos(statistics.mean(self.esperas))} (máx {minutos(max(self.esperas))})")
                if e["por_revisar"]:
                    partes.append(f"por revisar {e['por_revisar']}")
                if not e["comfy"]["ok"]:
                    partes.append("¡ComfyUI NO RESPONDE!")
                partes.append(f"errores {self.errores}")
                self.salida(" · ".join(partes))

    # --- Al terminar ---

    async def recoger(self):
        """Cancela lo que las personas virtuales tengan en cola para no dejar la gráfica trabajando."""
        if not self.activos:
            return
        self.pendientes_al_final = len(self.activos)
        async with self.cliente() as c:
            for token, id_ in list(self.activos.items()):
                try:
                    await c.post(f"/api/trabajos/{id_}/cancelar", headers={"X-Token": token})
                except httpx.HTTPError:
                    pass
        self.activos.clear()

    def resumen(self) -> dict:
        duracion = time.time() - self.inicio
        r = sorted(self.respuestas) or [0.0]
        datos = {
            "personas": self.dentro, "duracion": duracion, "hechas": self.hechas, "errores": self.errores,
            "media": self.media, "espera_media": statistics.mean(self.esperas) if self.esperas else None,
            "espera_max": max(self.esperas) if self.esperas else None,
            "respuesta_media": statistics.mean(r), "respuesta_max": r[-1],
        }
        linea = "=" * 72
        s = [f"\n{linea}", "  RESUMEN DEL SIMULACRO", linea,
             f"  Personas virtuales: {self.dentro} · duración {minutos(duracion)} · imágenes terminadas: {self.hechas}"]
        if self.media:
            por_hora = 3600 / self.media
            s.append(f"  Tu PC tarda {self.media:.1f} s por imagen: unas {por_hora:.0f} imágenes por hora.")
            s.append(f"  Si 100 personas pidieran a la vez, la última esperaría unos {self.media * 100 / 60:.0f} min.")
        if self.esperas:
            s.append(f"  Espera de las que terminaron (cola + imagen): media {minutos(datos['espera_media'])}, "
                     f"máxima {minutos(datos['espera_max'])}.")
        if self.pendientes_al_final:
            s.append(f"  Al acabar quedaban {self.pendientes_al_final} imágenes en cola (se han cancelado).")
        s.append(f"  Servidor: respondió en {datos['respuesta_media'] * 1000:.0f} ms de media "
                 f"(la más lenta, {datos['respuesta_max']:.1f} s) · errores: {self.errores}.")
        s.append(linea)
        if self.errores:
            s.append("  ⚠ Hubo errores: mira la ventana negra del estudio y la de ComfyUI.")
        if not self.media:
            s.append("  ⚠ No ha dado tiempo a terminar ninguna imagen: ¿ComfyUI está generando?")
        elif self.media <= 10:
            s.append("  ✔ Va bien. En los momentos de más jaleo habrá cola, pero cada móvil enseña su turno")
            s.append("    y cuánto le queda, y la imagen no se pierde aunque bloqueen el móvil.")
        elif self.media <= 15:
            s.append("  ✔ Aceptable. Si mucha gente pide a la vez, la espera puede pasar de 15 minutos.")
            s.append("    Para acelerar, en config/ajustes.toml baja los [formatos] (por ejemplo")
            s.append("    cuadrado = [768, 768]) y vuelve a probar.")
        else:
            s.append("  ⚠ Va justo para 100 personas. Para acelerar, en config/ajustes.toml baja los")
            s.append("    [formatos] (por ejemplo cuadrado = [768, 768]) y vuelve a probar.")
        s.append(linea)
        self.salida("\n".join(s))
        return datos

    async def ejecutar(self) -> dict:
        await self.comprobar()
        self.inicio = time.time()
        fin = self.inicio + self.segundos
        self.salida(f"Simulacro en marcha: {self.personas} personas durante {minutos(self.segundos)}. "
                    + ("Las imágenes se publican solas." if self.publicar
                       else "Las imágenes esperan en el panel: apruébalas en «Por revisar»."))
        self.salida("Abre el proyector para ver el mosaico. Ctrl+C para parar antes de tiempo.\n")
        tareas = [self.persona(i + 1, fin) for i in range(self.personas)] + [self.informe(fin)]
        if self.publicar:
            tareas.append(self.jurado(fin))
        try:
            await asyncio.gather(*tareas)
        finally:
            await self.recoger()
        return self.resumen()


def main():
    aj = config.cargar()
    parser = argparse.ArgumentParser(description="Simulacro con personas virtuales contra el estudio.")
    parser.add_argument("--personas", type=int, default=100)
    parser.add_argument("--minutos", type=float, default=10)
    parser.add_argument("--publicar", action="store_true", help="publica solas las imágenes (sin jurado)")
    parser.add_argument("--url", default=f"http://127.0.0.1:{aj.puerto}")
    a = parser.parse_args()
    simulacro = Simulacro(a.url, max(1, a.personas), max(0.5, a.minutos) * 60, a.publicar, aj)
    try:
        asyncio.run(simulacro.ejecutar())
    except NoSePuede as e:
        print(f"\nNo se puede hacer el simulacro:\n  {e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nParando: cancelo las imágenes que quedaban en cola...")
        asyncio.run(simulacro.recoger())
        simulacro.resumen()


if __name__ == "__main__":
    main()
