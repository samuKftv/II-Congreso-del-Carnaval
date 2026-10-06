@echo off
setlocal
cd /d "%~dp0"
title Instalar el Estudio de imagenes

call :buscarpython
if defined PY goto instalar

echo.
echo No encuentro Python 3.11 o superior en este PC.
echo Puedo instalarlo ahora (Python 3.12, gratuito y oficial). Tarda un par de minutos.
echo.
choice /c SN /m "Instalar Python ahora"
if errorlevel 2 goto sinpython

echo.
echo Instalando Python 3.12 ...
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :buscarpython
if not defined PY goto sinpython

:instalar
echo.
echo Usando Python: %PY%
echo Creando el entorno de Python en .venv ...
%PY% -m venv .venv
if errorlevel 1 goto error

echo Instalando dependencias ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo ============================================================
echo   Instalacion terminada.
echo   1. Ejecuta UNA VEZ abrir_firewall.bat como administrador.
echo   2. Para usar el estudio, haz doble clic en iniciar.bat
echo ============================================================
pause
exit /b 0

:sinpython
echo.
echo Sin Python no puedo seguir.
echo Instalalo a mano desde https://www.python.org/downloads/
echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
echo Despues vuelve a ejecutar instalar.bat
pause
exit /b 1

:error
echo.
echo Algo ha fallado durante la instalacion. Revisa los mensajes de arriba.
pause
exit /b 1

:buscarpython
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=py -3"
if defined PY exit /b 0
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
if defined PY exit /b 0
for %%V in (314 313 312 311) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe""
)
exit /b 0
