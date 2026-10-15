"""Prueba de tu modelo y tu LoRA (5-PROBAR-MI-MODELO.bat).

Pinta las mismas ideas, con la misma semilla, sin LoRA y con varias fuerzas, y lo junta todo en una hoja
para comparar de un vistazo. También mide los segundos por imagen, que es lo que decide cuánto espera la gente.

Uso:  python -m app.probar_modelo ["otra idea" ...] [--fuerzas 0.6,0.8,1] [--sin-interprete]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import arquitectura, config, workflow
from .comfy import ComfyUI, ErrorComfy
from .interprete import Interprete
from .moderacion import Filtro

CARPETA = "prueba-mi-modelo"
FUERZAS = [0.6, 0.8, 1.0]
CELDA = 400
CABECERA = 64
MARGEN = 300  # columna de la izquierda con las ideas


class NoSePuede(Exception):
    pass


@dataclass
class Columna:
    titulo: str
    wf: dict
    imagenes: list[Image.Image | None] = field(default_factory=list)
    segundos: list[float] = field(default_factory=list)


def columnas(aj: config.Ajustes, fuerzas: list[float]) -> list[Columna]:
    base = aj.workflow
    if aj.lora:
        lista = [Columna("Sin LoRA", workflow.con_mi_modelo(base, aj.modelo))]
        lista += [Columna(f"LoRA {f:g}", workflow.con_mi_modelo(base, aj.modelo, aj.lora, f))
                  for f in sorted(set(fuerzas) | {aj.fuerza_lora})]
    elif aj.modelo:
        lista = [Columna("Modelo original", base), Columna("Tu modelo", workflow.con_mi_modelo(base, aj.modelo))]
    else:  # sin modelo ni LoRA propios: una columna con el modelo del workflow (para comparar familias)
        lista = [Columna(arquitectura.nombre(arquitectura.familia_workflow(base)), base)]
    for c in lista:
        c.wf = workflow.ajustar(c.wf, aj.pasos, aj.cfg)
        if aj.ligero:
            c.wf = workflow.aligerar(c.wf)
    return lista


def _fuente(tamano: int, titulo: bool = False):
    """Una letra con eñes y tildes: la del cartel para los títulos y la de Windows para el texto."""
    rutas = [config.RAIZ / "app" / "static" / "fuentes" / "Righteous-Regular.ttf"] if titulo else []
    rutas += [Path(r"C:\Windows\Fonts\segoeui.ttf"), Path(r"C:\Windows\Fonts\arial.ttf"),
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for ruta in rutas:
        if ruta.exists():
            return ImageFont.truetype(str(ruta), tamano)
    return ImageFont.load_default(size=tamano)


def _envolver(texto: str, fuente, ancho: int) -> list[str]:
    lineas, linea = [], ""
    for palabra in texto.split():
        prueba = f"{linea} {palabra}".strip()
        if fuente.getlength(prueba) > ancho and linea:
            lineas.append(linea)
            linea = palabra
        else:
            linea = prueba
    return lineas + [linea] if linea else lineas


def hoja(ideas: list[str], cols: list[Columna], aj: config.Ajustes) -> Image.Image:
    """Una fila por idea y una columna por variante."""
    ancho, alto = MARGEN + CELDA * len(cols), CABECERA + CELDA * len(ideas)
    im = Image.new("RGB", (ancho, alto), aj.colores.get("fondo", "#1d1f4f"))
    d = ImageDraw.Draw(im)
    titulos, texto = _fuente(30, titulo=True), _fuente(20)
    crema = aj.colores.get("secundario", "#f6e7c8")
    nombre = (aj.lora or aj.modelo or "").replace("\\", "/").rsplit("/", 1)[-1]
    d.text((16, CABECERA // 2), nombre[:28], font=texto, fill=crema, anchor="lm")
    for j, c in enumerate(cols):
        d.text((MARGEN + j * CELDA + CELDA // 2, CABECERA // 2), c.titulo, font=titulos, fill=crema, anchor="mm")
    for i, idea in enumerate(ideas):
        y = CABECERA + i * CELDA
        for n, linea in enumerate(_envolver(idea, texto, MARGEN - 32)[:12]):
            d.text((16, y + 16 + n * 26), linea, font=texto, fill="white")
        for j, c in enumerate(cols):
            x = MARGEN + j * CELDA
            imagen = c.imagenes[i] if i < len(c.imagenes) else None
            if imagen is None:
                d.rectangle([x + 4, y + 4, x + CELDA - 4, y + CELDA - 4], outline="#c0392b", width=3)
                d.text((x + CELDA // 2, y + CELDA // 2), "error", font=titulos, fill="#c0392b", anchor="mm")
            else:
                im.paste(ImageOps.fit(imagen.convert("RGB"), (CELDA - 8, CELDA - 8)), (x + 4, y + 4))
    return im


class Prueba:
    def __init__(self, aj: config.Ajustes, ideas: list[str], fuerzas: list[float], interprete: bool = True,
                 salida=print, carpeta: Path | None = None):
        self.aj, self.ideas, self.salida = aj, ideas, salida
        self.cols = columnas(aj, fuerzas)
        self.comfy = ComfyUI(aj.comfy_url)
        self.usar_interprete = interprete and aj.interprete_activado
        self.carpeta = carpeta or config.RAIZ / CARPETA / datetime.now().strftime("%Y-%m-%d_%H-%M")

    async def _prompts(self) -> list[str]:
        estilo = self.aj.estilos.get(self.aj.estilo_sencillo) if self.aj.sencillo else self.aj.estilos.get("libre")
        # Las ideas de Inspírame llevan su prompt optimizado: van tal cual, como en el estudio
        listos = [self.aj.prompts_ideas.get(config.normalizar(i)) for i in self.ideas]
        textos = list(self.ideas)
        if self.usar_interprete and not all(listos):
            ia = Interprete(self.aj.interprete_url, self.aj.interprete_modelo, Filtro(self.aj.palabras_prohibidas),
                            self.aj.interprete_grafica)
            try:
                if await ia.comprobar():
                    self.salida("  El intérprete convierte las ideas (como en el evento):")
                    for i, idea in enumerate(self.ideas):
                        if listos[i]:
                            continue
                        if descripcion := await ia.interpretar(idea):
                            textos[i] = descripcion
                            self.salida(f"   · {idea}\n     → {descripcion}")
                else:
                    self.salida(f"  Intérprete: {ia.detalle}. Se pintan las ideas tal cual.")
            finally:
                await ia.cerrar()
        textos = [listo or t for t, listo in zip(textos, listos)]
        textos = [estilo.aplicar(t) if estilo else t for t in textos]
        if any(listos):
            self.salida(f"  {sum(map(bool, listos))} de {len(listos)} ideas son de Inspírame: van con su prompt optimizado.")
        return [workflow.con_palabra_clave(t, self.aj.palabra_clave) for t in textos]

    async def ejecutar(self) -> Path:
        try:
            return await self._ejecutar()
        finally:
            await self.comfy.cerrar()

    async def _ejecutar(self) -> Path:
        if await self.comfy.estado() is None:
            raise NoSePuede("No encuentro ComfyUI. Arráncalo y vuelve a probar.")
        validas = []
        for c in self.cols:
            faltan = await self.comfy.comprobar(c.wf)
            if faltan:
                self.salida(f"  ✗ «{c.titulo}» no se puede pintar:")
                for f in faltan:
                    self.salida(f"      {f}")
            else:
                validas.append(c)
        if not validas or (len(self.cols) > 1 and not any(c is not self.cols[0] for c in validas)):
            raise NoSePuede("Copia los archivos que faltan en ComfyUI, vuelve a abrirlo y repite la prueba.")
        self.cols = validas
        # ¿Tu modelo y tu LoRA son de la familia del workflow? Si no, todas saldrían con error
        avisos, familias = await arquitectura.revisar(self.comfy, self.cols[-1].wf, bool(self.aj.modelo), bool(self.aj.lora))
        if familias.get("modelo") or familias.get("lora"):
            partes = [f"{q} {arquitectura.nombre(familias[q])}" for q in ("modelo", "lora") if familias.get(q)]
            self.salida(f"  Familia: {', '.join(partes)} · workflow {arquitectura.nombre(familias['workflow'])}")
        if avisos:
            raise NoSePuede("\n  ".join(avisos))

        prompts = await self._prompts()
        formato = self.aj.formatos.get(self.aj.formato_sencillo) or next(iter(self.aj.formatos.values()))
        semillas = [random.randint(1, 2**50) for _ in self.ideas]  # la misma en cada columna: solo cambia el LoRA
        self.carpeta.mkdir(parents=True, exist_ok=True)
        total, hechas = len(self.cols) * len(self.ideas), 0
        self.salida(f"\n  Pintando {total} imágenes de {formato.ancho}×{formato.alto}…")
        errores = []
        for j, c in enumerate(self.cols):
            nodos = workflow.localizar(c.wf, self.aj.nodo_prompt, self.aj.nodo_tamano)
            for i, prompt in enumerate(prompts):
                hechas += 1
                if i and not c.segundos:  # la primera de la columna falló: las demás fallarían igual
                    c.imagenes.append(None)
                    continue
                wf = workflow.preparar(c.wf, nodos, prompt, formato.ancho, formato.alto, semillas[i],
                                       "congreso_carnaval/prueba")
                inicio = time.monotonic()
                try:
                    datos = (await self.comfy.generar(wf, lambda *_: None, lambda *_: None, self.aj.tiempo_maximo))[0]
                except ErrorComfy as e:
                    c.imagenes.append(None)
                    errores.append(f"{c.titulo}: {e}")
                    self.salida(f"  [{hechas}/{total}] {c.titulo} · ERROR: {e}")
                    continue
                segundos = time.monotonic() - inicio
                c.segundos.append(segundos)
                imagen = Image.open(BytesIO(datos))
                imagen.load()
                imagen.save(self.carpeta / f"{j + 1}-{c.titulo.replace(' ', '_')}-idea{i + 1}.png")
                c.imagenes.append(imagen)
                negra = max(alto for _, alto in imagen.convert("RGB").getextrema()) < 12
                self.salida(f"  [{hechas}/{total}] {c.titulo} · {self.ideas[i][:50]} · {segundos:.1f} s"
                            + ("  ⚠ ¡SALE NEGRA!" if negra else ""))
                if negra:
                    errores.append(f"{c.titulo}: la imagen sale negra (suele ser un VAE o un modelo de otra familia)")

        if not any(c.segundos for c in self.cols):
            raise NoSePuede("No ha salido ninguna imagen:\n  " + "\n  ".join(errores))
        ruta = self.carpeta / "hoja.jpg"
        hoja(self.ideas, self.cols, self.aj).save(ruta, "JPEG", quality=88)
        self.resumen(ruta)
        return ruta

    def resumen(self, ruta: Path):
        # La primera imagen de cada columna carga el modelo o el LoRA: no cuenta para la media
        tiempos = {c.titulo: c.segundos[1:] or c.segundos for c in self.cols if c.segundos}
        linea = "=" * 64
        self.salida(f"\n{linea}\n  RESULTADO DE LA PRUEBA\n{linea}")
        for titulo, s in tiempos.items():
            self.salida(f"  {titulo:<16} {statistics.median(s):5.1f} s por imagen")
        if tiempos:
            media = statistics.median([x for s in tiempos.values() for x in s])
            self.salida(f"\n  En 10 minutos salen unas {int(600 / media)} imágenes ({media:.1f} s cada una).")
        self.salida(f"\n  La hoja para comparar: {ruta}")
        self.salida("  Cada fila es una idea con la misma semilla: solo cambia el LoRA.")
        self.salida("  Elige la fuerza que respete la idea y tenga tu estilo, y ponla en")
        self.salida("  config/ajustes.toml > [mi_modelo] > fuerza_lora.")
        self.salida(linea)


def main():
    p = argparse.ArgumentParser(description="Compara tu modelo y tu LoRA con la misma idea y la misma semilla.")
    p.add_argument("ideas", nargs="*", help="ideas para probar (si no, cuatro de las de Inspírame)")
    p.add_argument("--fuerzas", default=",".join(f"{f:g}" for f in FUERZAS), help="fuerzas del LoRA, p. ej. 0.6,0.8,1")
    p.add_argument("--sin-interprete", action="store_true", help="pintar las ideas tal cual")
    a = p.parse_args()
    try:
        aj = config.cargar()
        fuerzas = [float(f) for f in a.fuerzas.replace(" ", "").split(",") if f]
        ideas = a.ideas or aj.ideas[:4] or ["La reina del carnaval con un traje gigante inspirado en el Teide"]
        linea = "=" * 64
        print(f"\n{linea}\n  PRUEBA DE TU MODELO\n{linea}")
        print(f"  Workflow: {arquitectura.nombre(arquitectura.familia_workflow(aj.workflow))}")
        print(f"  Modelo: {aj.modelo or '(el del workflow)'}")
        if aj.lora:
            print(f"  LoRA:   {aj.lora} · fuerzas {', '.join(f'{f:g}' for f in sorted(set(fuerzas) | {aj.fuerza_lora}))}")
        if aj.palabra_clave:
            print(f"  Palabra clave: {aj.palabra_clave}")
        prueba = Prueba(aj, ideas, fuerzas, interprete=not a.sin_interprete)
        ruta = asyncio.run(prueba.ejecutar())
    except (NoSePuede, workflow.ErrorWorkflow, ValueError, OSError) as e:
        print(f"\nNo se puede hacer la prueba:\n  {e}\n")
        sys.exit(1)
    if sys.platform == "win32":
        os.startfile(ruta)  # abre la hoja en el visor de fotos


if __name__ == "__main__":
    main()
