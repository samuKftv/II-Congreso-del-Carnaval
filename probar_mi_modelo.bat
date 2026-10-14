@echo off
setlocal
cd /d "%~dp0"
title Prueba de tu modelo y tu LoRA
if not exist ".venv\Scripts\python.exe" goto noinstalado
set PYTHONIOENCODING=utf-8
echo.
echo  PRUEBA DE TU MODELO Y TU LORA
echo  Pinta 4 ideas sin LoRA y con varias fuerzas (0.6, 0.8 y 1), con la misma
echo  semilla, y lo junta todo en una hoja para comparar. Tarda unos minutos.
echo.
echo  Antes de seguir:
echo   - Escribe tu modelo y tu LoRA en config\ajustes.toml, apartado [mi_modelo].
echo   - Arranca ComfyUI.
echo  Si quieres probar tus propias ideas, escribelas despues del nombre de este
echo  archivo en una ventana de comandos, entre comillas.
echo.
pause
".venv\Scripts\python.exe" -m app.probar_modelo %*
echo.
pause
exit /b 0

:noinstalado
echo Primero ejecuta instalar.bat
pause
exit /b 1
