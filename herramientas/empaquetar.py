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

Para parar el estudio, cierra la ventana negra.
Las imágenes se guardan en la carpeta "datos".
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
    shutil.copy(RAIZ / "README.md", obra / "README.md")

    # 4. Lanzadores e instrucciones
    escribir_windows(obra / "2-INICIAR-ESTUDIO.bat", INICIAR)
    escribir_windows(obra / "1-PERMITIR-FIREWALL.bat", FIREWALL)
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
