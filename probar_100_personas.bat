@echo off
setlocal
cd /d "%~dp0"
title Simulacro - 100 personas virtuales
if not exist ".venv\Scripts\python.exe" goto noinstalado
set PYTHONIOENCODING=utf-8
echo.
echo  SIMULACRO: 100 personas virtuales usan el estudio a la vez durante 10 minutos.
echo  Antes: cierra la ventana negra del estudio normal y arranca ComfyUI.
echo  Todo se guarda aparte, en "datos-simulacro": tus datos de verdad no se tocan.
echo.
choice /c SN /m "Quieres que las imagenes se publiquen solas? (N = las apruebas tu en el panel)"
if errorlevel 2 (set "PUBLICAR=") else (set "PUBLICAR=--publicar")
if exist "datos-simulacro" rmdir /s /q "datos-simulacro"
set "ESTUDIO_DATOS=%~dp0datos-simulacro"
start "Estudio (SIMULACRO)" ".venv\Scripts\python.exe" -m app
".venv\Scripts\python.exe" -m app.simulacro --personas 100 --minutos 10 %PUBLICAR%
echo.
echo  Cuando acabes, cierra tambien la ventana "Estudio (SIMULACRO)".
pause
exit /b 0

:noinstalado
echo Primero ejecuta instalar.bat
pause
exit /b 1
