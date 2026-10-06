@echo off
setlocal
cd /d "%~dp0"
title Permitir el Estudio de imagenes en el Firewall
net session >nul 2>&1
if errorlevel 1 goto noadmin

rem 1. Abrir el puerto de la app en todas las redes (privadas y publicas).
netsh advfirewall firewall delete rule name="Estudio de imagenes" >nul 2>&1
netsh advfirewall firewall add rule name="Estudio de imagenes" dir=in action=allow protocol=TCP localport=8080 profile=any
if errorlevel 1 goto error

rem 2. Si al arrancar la app se cerro el aviso del Firewall sin pulsar "Permitir",
rem    Windows crea una regla que BLOQUEA a Python y gana a la anterior. La cambiamos.
if not exist .venv\Scripts\python.exe goto fin
set "PYBASE="
for /f "delims=" %%P in ('.venv\Scripts\python.exe -c "import sys; print(sys._base_executable)"') do set "PYBASE=%%P"
call :permitir "%~dp0.venv\Scripts\python.exe"
if defined PYBASE call :permitir "%PYBASE%"

:fin
echo.
echo Listo: los moviles de la WiFi ya pueden entrar al puerto 8080 de este PC.
echo Si el estudio estaba abierto, cierralo y vuelve a abrir iniciar.bat
pause
exit /b 0

:permitir
netsh advfirewall firewall delete rule name=all program=%1 >nul 2>&1
netsh advfirewall firewall add rule name="Estudio de imagenes (Python)" dir=in action=allow program=%1 profile=any >nul
exit /b 0

:noadmin
echo Haz clic derecho sobre abrir_firewall.bat y elige "Ejecutar como administrador".
pause
exit /b 1

:error
echo No se ha podido crear la regla del Firewall.
pause
exit /b 1
