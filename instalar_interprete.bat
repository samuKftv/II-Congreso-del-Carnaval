@echo off
setlocal
cd /d "%~dp0"
title Instalar el interprete de ideas
echo.
echo  INTERPRETE DE IDEAS
echo  Una IA de texto pequena (Ollama + qwen2.5:3b, unos 2 GB) que convierte cada idea
echo  del alumnado en una descripcion detallada antes de pintarla.
echo  Hace falta internet solo para instalarlo. En el evento funciona sin internet.
echo.
set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%OLLAMA%" goto modelo
where ollama >nul 2>&1
if not errorlevel 1 (
  set "OLLAMA=ollama"
  goto modelo
)
echo  Instalando Ollama...
winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
if not exist "%OLLAMA%" goto sinollama

:modelo
rem Ollama tiene que estar en marcha para descargar el modelo
"%OLLAMA%" list >nul 2>&1
if errorlevel 1 (
  start "Ollama" /min "%OLLAMA%" serve
  timeout /t 6 /nobreak >nul
)
echo  Descargando el modelo qwen2.5:3b (unos 2 GB, puede tardar unos minutos)...
"%OLLAMA%" pull qwen2.5:3b
if errorlevel 1 goto error
echo.
echo  Listo. Cierra y vuelve a abrir el estudio: en el panel, junto a ComfyUI,
echo  pondra "Interprete de ideas: listo".
echo  Ollama se abre solo al encender el PC (icono de la llama junto al reloj).
pause
exit /b 0

:sinollama
echo.
echo  No se ha podido instalar Ollama automaticamente.
echo  Descargalo de https://ollama.com/download , instalalo y vuelve a abrir este archivo.
pause
exit /b 1

:error
echo.
echo  No se ha podido descargar el modelo. Comprueba la conexion a internet y vuelve a probar.
pause
exit /b 1
