# 🎭 Estudio de imágenes — II Congreso del Carnaval

El alumnado escribe una idea en el móvil y recibe una imagen generada por **ComfyUI**
en el PC del profesor. Todo funciona dentro de la WiFi del aula.

- 📱 **Alumnado**: escanea el QR, pone su alias y crea. Sin instalar nada.
- 🎛️ **Panel del profesor**: abre y cierra el estudio, controla la cola y modera imágenes y personas.
- 📺 **Proyector**: galería en directo con el QR de acceso siempre visible.

Las decisiones de diseño están en [`docs/DIRECTRICES.md`](docs/DIRECTRICES.md).

---

## Instalación (una sola vez, en el PC con ComfyUI)

1. **Python 3.11 o superior** desde [python.org](https://www.python.org/downloads/).
   Durante la instalación, marca **"Add python.exe to PATH"**.
2. Doble clic en **`instalar.bat`**.
3. Clic derecho en **`abrir_firewall.bat`** → **Ejecutar como administrador**.
   Así los móviles pueden llegar al PC por el puerto 8080.
4. **Tu workflow**: en ComfyUI abre el workflow de Z-Image Turbo que usas y elige
   *Workflow → Exportar (API)*. Guarda el archivo como **`config/workflow_api.json`**
   (sustituye al que viene).
   > El que viene es el ejemplo oficial de Z-Image Turbo y usa los archivos
   > `z_image_turbo_bf16.safetensors`, `qwen_3_4b.safetensors` y `ae.safetensors`.
   > Si los tuyos se llaman igual, puedes saltarte este paso.

## Cada sesión

1. Arranca **ComfyUI** como siempre.
2. Doble clic en **`iniciar.bat`**. Se abre el **panel del profesor** en el navegador.
3. La primera vez, pulsa **"Generar miniaturas"** en el panel. Así las tarjetas de
   estilo mostrarán imágenes reales hechas con tu modelo.
4. Pulsa **"Abrir proyector"** y llévalo a la pantalla del aula.
5. El alumnado escanea el QR. **Deja abierta la ventana negra** mientras dure la sesión.

## Configuración (`config/`)

| Archivo | Para qué |
|---|---|
| `ajustes.toml` | Nombre del evento, puerto, código del aula, clave del profesor, dirección de ComfyUI, formatos, palabras bloqueadas |
| `estilos.json` | Estilos (nombre, emoji, colores y la "receta" que se añade al prompt) e ideas del botón *Inspírame* |
| `workflow_api.json` | El workflow de ComfyUI en formato API |

Después de cambiar algo, cierra la ventana de la app y vuelve a abrir `iniciar.bat`.

La app encuentra sola en el workflow el texto del prompt, el tamaño, la semilla y el
nodo *Save Image*. Si usas un workflow raro y no los encuentra, el panel te avisará.
En ese caso, indica los números de nodo en `nodo_prompt` y `nodo_tamano`.

## Si algo falla

| Problema | Solución |
|---|---|
| Los móviles no cargan la página | El PC y los móviles deben estar en la **misma red**. Ejecuta `abrir_firewall.bat` como administrador. Si sigue sin ir, la WiFi puede tener **aislamiento de clientes**: pide a informática que lo desactive. |
| El QR muestra una IP rara | Escribe la IP correcta del PC en `direccion` (`ajustes.toml`). La ves con `ipconfig` en una terminal. |
| El panel dice "ComfyUI: sin conexión" | Comprueba que ComfyUI está arrancado. **ComfyUI Desktop** suele usar el puerto **8000**: cambia `url` en `[comfyui]`. |
| Las imágenes dan error | Mira la ventana de ComfyUI: suele ser un modelo que falta o un nombre de archivo distinto en el workflow. |
| Quiero ver la imagen formándose | Arranca ComfyUI con `--preview-method auto`. Sin esa opción solo se ve la barra de progreso. |
| Quiero empezar de cero | Cierra la app y borra la carpeta `datos/` (imágenes e historial). |

## Datos

Todo se guarda en `datos/`, solo en este PC:
- `estudio.db`: historial;
- `imagenes/`: los PNG originales;
- `miniaturas/`: las versiones ligeras para galerías;
- `estilos/`: las tarjetas de estilo.

No se piden nombres reales ni emails: solo un alias.

## Desarrollo

```bash
pip install -r requirements.txt pytest
python -m pytest            # pruebas con un ComfyUI simulado (sin GPU)
python -m tests.comfy_falso # ComfyUI falso en :8188 para probar la interfaz
python -m app               # arranca el estudio
```
