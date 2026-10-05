@echo off
cd /d "%~dp0"
title Estudio de imagenes - II Congreso del Carnaval
if not exist ".venv\Scripts\python.exe" goto noinstalado
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m app
pause
exit /b 0

:noinstalado
echo Primero ejecuta instalar.bat
pause
exit /b 1
