@echo off
setlocal
cd /d "%~dp0"
title Instalar el Estudio de imagenes

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY goto sinpython

echo.
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
echo No encuentro Python 3.11 o superior.
echo Instalalo desde https://www.python.org/downloads/
echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
echo Despues vuelve a ejecutar instalar.bat
pause
exit /b 1

:error
echo.
echo Algo ha fallado durante la instalacion. Revisa los mensajes de arriba.
pause
exit /b 1
