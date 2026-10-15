"""Crea el ZIP portátil para Windows: Python oficial + dependencias + la app, sin instalar nada.

Uso:  python herramientas/empaquetar.py
Sale: dist/EstudioCarnaLab-v<versión>.zip

El Python es el paquete oficial de la Python Software Foundation publicado en NuGet
(el mismo intérprete que python.org, con sus DLL de Visual C++).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from app import VERSION  # noqa: E402

PYTHON = "3.13.16"
NUGET = f"https://api.nuget.org/v3-flatcontainer/python/{PYTHON}/python.{PYTHON}.nupkg"
NOMBRE = "EstudioCarnaLab"
DIST = RAIZ / "dist"
CACHE = DIST / "cache"
SOBRA_DE_PYTHON = ("include/", "libs/", "Lib/idlelib/", "Lib/tkinter/", "Lib/turtledemo/", "Lib/ensurepip/")

INICIAR = r"""@echo off
cd /d "%~dp0"
title CarnaLab 2026 - Estudio de imagenes
set PYTHONIOENCODING=utf-8
"%~dp0python\python.exe" -m app
echo.
pause
"""

FIREWALL = r"""@echo off
setlocal
cd /d "%~dp0"
title Permitir el Estudio de imagenes en el Firewall
net session >nul 2>&1
if errorlevel 1 goto noadmin

netsh advfirewall firewall delete rule name="Estudio de imagenes" >nul 2>&1
netsh advfirewall firewall add rule name="Estudio de imagenes" dir=in action=allow protocol=TCP localport=8080 profile=any
if errorlevel 1 goto error
rem Si se cerro el aviso del Firewall sin pulsar "Permitir", Windows bloquea a Python: lo cambiamos.
netsh advfirewall firewall delete rule name=all program="%~dp0python\python.exe" >nul 2>&1
netsh advfirewall firewall add rule name="Estudio de imagenes (Python)" dir=in action=allow program="%~dp0python\python.exe" profile=any >nul

echo.
echo Listo: los moviles de la WiFi ya pueden entrar al estudio (puerto 8080).
pause
exit /b 0

:noadmin
echo Haz clic derecho sobre este archivo y elige "Ejecutar como administrador".
pause
exit /b 1

:error
echo No se ha podido crear la regla del Firewall.
pause
exit /b 1
"""

SIMULACRO = r"""@echo off
setlocal
cd /d "%~dp0"
title Simulacro - 100 personas virtuales
set PYTHONIOENCODING=utf-8
echo.
echo  SIMULACRO: 100 personas virtuales usan el estudio a la vez durante 10 minutos.
echo  Piden ideas a tu ComfyUI de verdad, esperan su turno, miran la galeria y votan.
echo.
echo  Antes de seguir:
echo   - Cierra la ventana negra del estudio normal (si esta abierta).
echo   - Arranca ComfyUI.
echo  Todo se guarda aparte, en la carpeta "datos-simulacro": tus datos de verdad no se tocan.
echo.
choice /c SN /m "Quieres que las imagenes se publiquen solas? (N = las apruebas tu en el panel)"
if errorlevel 2 (set "PUBLICAR=") else (set "PUBLICAR=--publicar")
if exist "datos-simulacro" rmdir /s /q "datos-simulacro"
set "ESTUDIO_DATOS=%~dp0datos-simulacro"
start "Estudio (SIMULACRO)" "%~dp0python\python.exe" -m app
"%~dp0python\python.exe" -m app.simulacro --personas 100 --minutos 10 %PUBLICAR%
echo.
echo  Cuando acabes, cierra tambien la ventana "Estudio (SIMULACRO)".
echo  La carpeta "datos-simulacro" se puede borrar.
pause
"""

LEEME = f"""ESTUDIO DE IMÁGENES · CarnaLab 2026 (versión {VERSION})
CIFP Las Indias

No hace falta instalar nada: todo va dentro de esta carpeta, también Python.
Si Windows avisa "Windows protegió su PC", pulsa "Más información" > "Ejecutar de todas formas".

LA PRIMERA VEZ
 1. Si tienes abierta una versión anterior del estudio, cierra su ventana negra.
 2. Clic derecho en "1-PERMITIR-FIREWALL.bat" > "Ejecutar como administrador".
 3. Si tu workflow de ComfyUI no es el de ejemplo de Z-Image Turbo, copia tu
    workflow_api.json a la carpeta "config" (sustituye al que hay).

CADA VEZ
 1. Arranca ComfyUI (la app lo busca sola en los puertos 8188 y 8000).
 2. Doble clic en "2-INICIAR-ESTUDIO.bat". Se abre el panel del profesor.
 3. El alumnado escanea el QR del panel o del proyector.
 4. La primera vez, pulsa "Generar miniaturas" en el panel.

INTERPRETE DE IDEAS (recomendado)
 Doble clic en "4-INSTALAR-INTERPRETE.bat" (una sola vez, con internet).
 Instala Ollama y una IA de texto pequeña que convierte cada idea, aunque sea
 corta o rara, en una descripción detallada de una escena del Carnaval de
 Santa Cruz de Tenerife antes de pintarla. Va en el procesador y no le quita
 memoria a la gráfica. En el panel, junto a ComfyUI, verás "Intérprete de
 ideas: listo · ha mejorado N de M ideas". Si no está, las ideas se pintan
 tal cual, con la ambientación de carnaval (trajes, plumas, confeti, luces).

SI LA WIFI DEL RECINTO NO DEJA (modo internet)
 Muchas WiFi abiertas aíslan los móviles y no pueden llegar a este PC.
 Entonces usa "2-INICIAR-ESTUDIO-POR-INTERNET.bat" en vez del normal: el
 estudio recibe una dirección pública https (un túnel gratuito de Cloudflare)
 y el público entra con sus datos móviles o con cualquier WiFi. Este PC solo
 necesita internet: la WiFi del recinto o los datos de tu móvil.
 Ábrelo una vez ANTES del evento, con internet, para que descargue cloudflared.

CONCURSO
 Cada imagen nueva espera en "Por revisar" del panel hasta que pulsas
 "Publicar". Entonces entra en el mosaico gigante del proyector y se puede
 votar. Al final: Proyector > Ganadoras (cierra la votación y enseña el podio).

TU PROPIO MODELO Y TU LORA
 1. Copia tu modelo en ComfyUI\\models\\diffusion_models y tu LoRA en
    ComfyUI\\models\\loras. Vuelve a abrir ComfyUI.
 2. Abre config\\ajustes.toml con el Bloc de notas y, en el apartado
    [mi_modelo], di de qué modelo sale el tuyo (base = "flux2-klein-4b" o
    "z-image-turbo"), escribe sus nombres (modelo = "...", lora = "...") y la
    palabra clave del LoRA si entrenaste con una.
    FLUX.2 Klein 4B necesita además flux2-vae.safetensors en ComfyUI\\models\\vae.
    Si ComfyUI dice "mat1 and mat2 shapes cannot be multiplied", la base no
    es la de tu modelo: el panel te dice cuál poner.
 3. Doble clic en "5-PROBAR-MI-MODELO.bat". Pinta 4 ideas sin LoRA y con
    fuerzas 0.6, 0.8 y 1, con la misma semilla, y abre una hoja para
    compararlas. Escribe la fuerza que más te guste en fuerza_lora.
 4. Abre el estudio como siempre. En el panel, junto a ComfyUI, verás
    "Modelo: ... + LoRA ...". Si falta algún archivo, el panel te lo dice.
 Si tu modelo es de otra familia (por ejemplo, SDXL o FLUX.1), monta en
 ComfyUI un workflow que funcione con él, expórtalo con "Exportar (API)" y
 guárdalo como config\\workflow_api.json, con base = "auto". El LoRA y la
 palabra clave se siguen poniendo en [mi_modelo].
 Después, mide con el simulacro cuánto tarda por imagen.

PROBAR CON 100 PERSONAS (SIMULACRO)
 Cierra el estudio, arranca ComfyUI y haz doble clic en "3-PROBAR-CON-100-PERSONAS.bat".
 100 personas virtuales usan el estudio durante 10 minutos con tu ComfyUI de
 verdad. Abre el proyector para ver el mosaico y practica de jurado en el panel.
 Al final sale un resumen: segundos por imagen y cuánto esperaría la gente.
 Usa la carpeta "datos-simulacro": no toca tus datos de verdad.

Para parar el estudio, cierra la ventana negra.
Las imágenes se guardan en la carpeta "datos".
En la carpeta "comfyui" hay workflows para probar en ComfyUI (imágenes de referencia).
Más ayuda: README.md
"""


def descargar(url: str, destino: Path):
    if destino.exists():
        return
    print(f"Descargando {url}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r, open(destino.with_suffix(".tmp"), "wb") as f:
        shutil.copyfileobj(r, f)
    destino.with_suffix(".tmp").rename(destino)


def escribir_windows(ruta: Path, texto: str):
    ruta.write_bytes(texto.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def main():
    obra = DIST / NOMBRE
    shutil.rmtree(obra, ignore_errors=True)
    obra.mkdir(parents=True)

    # 1. Python oficial para Windows
    nupkg = CACHE / f"python.{PYTHON}.nupkg"
    descargar(NUGET, nupkg)
    with zipfile.ZipFile(nupkg) as z:
        for info in z.infolist():
            if not info.filename.startswith("tools/") or info.is_dir():
                continue
            relativo = info.filename[len("tools/"):]
            if relativo.startswith(SOBRA_DE_PYTHON):
                continue
            destino = obra / "python" / relativo
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(z.read(info))

    # 2. Dependencias ya compiladas para Windows 64 bits
    ruedas = CACHE / f"ruedas-cp{PYTHON.replace('.', '')[:3]}"
    subprocess.run(
        [sys.executable, "-m", "pip", "download", "--quiet", "--only-binary=:all:",
         "--platform", "win_amd64", "--python-version", PYTHON[:4], "--implementation", "cp",
         "-d", str(ruedas), "-r", str(RAIZ / "herramientas" / "requisitos-windows.txt")],
        check=True,
    )
    site = obra / "python" / "Lib" / "site-packages"
    for rueda in sorted(ruedas.glob("*.whl")):
        with zipfile.ZipFile(rueda) as z:
            z.extractall(site)

    # 3. La app
    sin_cache = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(RAIZ / "app", obra / "app", ignore=sin_cache)
    shutil.copytree(RAIZ / "config", obra / "config", ignore=sin_cache)
    shutil.copytree(RAIZ / "docs", obra / "docs", ignore=sin_cache)
    shutil.copytree(RAIZ / "comfyui", obra / "comfyui", ignore=sin_cache)
    shutil.copy(RAIZ / "README.md", obra / "README.md")

    # 4. Lanzadores e instrucciones
    escribir_windows(obra / "2-INICIAR-ESTUDIO.bat", INICIAR)
    escribir_windows(obra / "1-PERMITIR-FIREWALL.bat", FIREWALL)
    internet = (RAIZ / "iniciar_por_internet.bat").read_text(encoding="ascii")
    escribir_windows(obra / "2-INICIAR-ESTUDIO-POR-INTERNET.bat",
                     internet.replace('".venv\\Scripts\\python.exe"', '"%~dp0python\\python.exe"'))
    escribir_windows(obra / "3-PROBAR-CON-100-PERSONAS.bat", SIMULACRO)
    escribir_windows(obra / "4-INSTALAR-INTERPRETE.bat", (RAIZ / "instalar_interprete.bat").read_text(encoding="ascii"))
    mi_modelo = (RAIZ / "probar_mi_modelo.bat").read_text(encoding="ascii")
    escribir_windows(obra / "5-PROBAR-MI-MODELO.bat",
                     mi_modelo.replace('".venv\\Scripts\\python.exe"', '"%~dp0python\\python.exe"'))
    escribir_windows(obra / "LEEME.txt", LEEME)

    # 5. ZIP con una carpeta dentro
    zip_final = DIST / f"{NOMBRE}-v{VERSION}.zip"
    zip_final.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_final, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for archivo in sorted(obra.rglob("*")):
            if archivo.is_file():
                z.write(archivo, Path(NOMBRE) / archivo.relative_to(obra))
    print(f"Listo: {zip_final} ({zip_final.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
