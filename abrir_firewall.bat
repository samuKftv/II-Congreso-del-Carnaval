@echo off
title Permitir el Estudio de imagenes en el Firewall
net session >nul 2>&1
if errorlevel 1 goto noadmin

netsh advfirewall firewall delete rule name="Estudio de imagenes" >nul 2>&1
netsh advfirewall firewall add rule name="Estudio de imagenes" dir=in action=allow protocol=TCP localport=8080
if errorlevel 1 goto error
echo.
echo Listo: los moviles de la WiFi ya pueden entrar al puerto 8080 de este PC.
pause
exit /b 0

:noadmin
echo Haz clic derecho sobre abrir_firewall.bat y elige "Ejecutar como administrador".
pause
exit /b 1

:error
echo No se ha podido crear la regla del Firewall.
pause
exit /b 1
