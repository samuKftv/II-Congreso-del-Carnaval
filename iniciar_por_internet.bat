@echo off
setlocal
cd /d "%~dp0"
title CarnaLab 2026 - Estudio POR INTERNET
set PYTHONIOENCODING=utf-8
echo.
echo  MODO INTERNET: el publico entra con sus datos moviles o con cualquier WiFi.
echo  Este PC solo necesita tener internet (la WiFi del recinto o los datos de tu movil).
echo.
if exist "cloudflared.exe" goto arrancar
where cloudflared >nul 2>&1
if not errorlevel 1 goto arrancar
echo  Descargando cloudflared, el tunel gratuito de Cloudflare (unos 60 MB, solo la primera vez)...
curl.exe -L --fail -o "cloudflared.exe" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
if errorlevel 1 goto sindescarga

:arrancar
set "ESTUDIO_INTERNET=1"
".venv\Scripts\python.exe" -m app
echo.
pause
exit /b 0

:sindescarga
if exist "cloudflared.exe" del "cloudflared.exe"
echo.
echo  No se ha podido descargar cloudflared. Comprueba que el PC tiene internet
echo  (si la WiFi tiene pagina de bienvenida, abre el navegador y aceptala) y vuelve a probar.
pause
exit /b 1
