# 🎭 Estudio de imágenes — CarnaLab 2026

**II Congreso Internacional de Profesionalización del Carnaval** · Santa Cruz de Tenerife.
Un estudio del **CIFP Las Indias**.

El alumnado escribe una idea en el móvil y recibe una imagen generada por **ComfyUI**
en el PC del profesor. Todo funciona dentro de la WiFi del aula.

- 📱 **Alumnado**: escanea el QR, pone su alias y crea. Sin instalar nada.
  - **Carnavales del mundo × técnicas**: combina Venecia, Río, Cádiz, Oruro… con acuarela, cómic, 3D…
  - **Botones de detalles** (lugar, luz, plano, ambiente) que enriquecen la idea.
  - **Foto como base**: transforma una foto propia. Es **privada** salvo que la persona marque compartirla.
  - **Galería de la clase** con votos ❤️ (nadie puede votarse a sí mismo).
- 🎛️ **Panel del profesor**: abre y cierra el estudio, controla la cola, modera, y lanza **retos con cuenta atrás**.
- 📺 **Proyector**: galería en directo con el QR siempre visible, cuenta atrás del reto, votación en vivo,
  **podio** de ganadoras y, de vez en cuando, las más votadas.

Las decisiones de diseño están en [`docs/DIRECTRICES.md`](docs/DIRECTRICES.md).

---

## Descarga para Windows (recomendado: sin instalar nada)

1. Descarga **[`descargas/EstudioCarnaLab.zip`](descargas/EstudioCarnaLab.zip)** (botón *Download raw*)
   y descomprímelo. Lleva dentro Python y todo lo necesario.
2. Si tienes abierta una versión anterior del estudio, **cierra su ventana negra**.
3. **La primera vez**: clic derecho en `1-PERMITIR-FIREWALL.bat` → *Ejecutar como administrador*.
4. Arranca ComfyUI y haz doble clic en **`2-INICIAR-ESTUDIO.bat`**.

La versión en marcha aparece en la ventana negra y en la cabecera del panel.

## Instalación desde el código (alternativa)

1. Doble clic en **`instalar.bat`**. Si no tienes Python, te ofrece instalarlo:
   pulsa **S**. Si eso falla, instálalo a mano desde
   [python.org](https://www.python.org/downloads/) marcando **"Add python.exe to PATH"**
   y vuelve a ejecutar `instalar.bat`.
2. Clic derecho en **`abrir_firewall.bat`** → **Ejecutar como administrador**.
   Así los móviles pueden llegar al PC por el puerto 8080.
3. **Tu workflow**: en ComfyUI abre el workflow de Z-Image Turbo que usas y elige
   *Workflow → Exportar (API)*. Guarda el archivo como **`config/workflow_api.json`**
   (sustituye al que viene).
   > El que viene es el ejemplo oficial de Z-Image Turbo y usa los archivos
   > `z_image_turbo_bf16.safetensors`, `qwen_3_4b.safetensors` y `ae.safetensors`.
   > Si los tuyos se llaman igual, puedes saltarte este paso.

## Cada sesión

1. Arranca **ComfyUI** como siempre.
2. Doble clic en **`2-INICIAR-ESTUDIO.bat`** (o `iniciar.bat` si instalaste desde el código).
   Se abre el **panel del profesor** en el navegador.
3. La primera vez, pulsa **"Generar miniaturas"** en el panel. Así las tarjetas de
   técnicas y carnavales mostrarán imágenes reales hechas con tu modelo (unas 20 imágenes).
4. Pulsa **"Abrir proyector"** y llévalo a la pantalla del aula.
5. El alumnado escanea el QR. **Deja abierta la ventana negra** mientras dure la sesión.

## Retos

1. En el panel, escribe el tema (o pulsa una de las ideas), elige la duración y pulsa **🏁 Lanzar reto**.
2. Móviles y proyector muestran el reto y la cuenta atrás. Todo lo que se cree mientras tanto participa.
3. Al acabar el tiempo (o con **⏹ Terminar y votar**), los móviles pasan a votar y el proyector enseña
   las candidatas con sus votos en directo.
4. **🏆 Mostrar podio** lleva las tres más votadas al proyector, con confeti.
5. **✓ Cerrar reto** devuelve el proyector a la galería normal.

## Identidad del congreso

Ya viene configurada con el cartel de CarnaLab 2026 (en `[evento]` y `[colores]` de `ajustes.toml`):

- **Cartel** (`config/cartel.jpg`): en la pantalla de entrada y en el proyector mientras no hay imágenes.
- **Logo del CIFP Las Indias** (`config/logo-las-indias.png`): versión clara del logo para que se lea
  sobre el azul del cartel. Sale en la entrada, en la cabecera y en el proyector.
- **Colores** sacados del cartel: azul marino, coral, crema y aguamarina.
- **Tipografía de los títulos**: Righteous (licencia libre SIL OFL, en `app/static/fuentes/`).
- **Técnica "Cartel CarnaLab"**: imita el estilo del cartel (cubista, colores planos, máscaras y trompetas).

Para cambiar algo, edita esas rutas y colores. Si borras una línea de `[colores]`, se usa el color
original de la app.

## Pruebas en ComfyUI

La carpeta [`comfyui/`](comfyui/LEEME.md) tiene workflows para probar directamente en ComfyUI,
antes de llevarlos a la app:

- **`reina_tenerife_referencia.json`**: enseña al modelo **cómo es una reina del Carnaval de Tenerife**
  con 1 o 2 fotos reales y compara el resultado **sin y con referencias**.
- **`referencias_flux2_klein.json`**: crea una imagen a partir de **varias imágenes de referencia**
  (persona + disfraz + estilo) con FLUX.2 [Klein] 4B.

## Configuración (`config/`)

| Archivo | Para qué |
|---|---|
| `ajustes.toml` | Nombre del evento, puerto, código del aula, clave del profesor, dirección de ComfyUI, formatos, palabras bloqueadas |
| `estilos.json` | Técnicas (`estilos`), carnavales del mundo (`temas`), ideas de *Inspírame* y botones de detalles. Cada uno con nombre, emoji, colores y la "receta" que se añade al prompt |
| `workflow_api.json` | El workflow de ComfyUI en formato API |

Después de cambiar algo, cierra la ventana negra del estudio y vuelve a abrirlo.

La app encuentra sola en el workflow el texto del prompt, el tamaño, la semilla y el
nodo *Save Image*. Si usas un workflow raro y no los encuentra, el panel te avisará.
En ese caso, indica los números de nodo en `nodo_prompt` y `nodo_tamano`.

## Si algo falla

| Problema | Solución |
|---|---|
| Los móviles no cargan la página | El PC y los móviles deben estar en la **misma red**. Ejecuta `1-PERMITIR-FIREWALL.bat` (o `abrir_firewall.bat`) como administrador. Si sigue sin ir, la WiFi puede tener **aislamiento de clientes**: pide a informática que lo desactive. |
| El QR muestra una IP rara | Escribe la IP correcta del PC en `direccion` (`ajustes.toml`). La ves con `ipconfig` en una terminal. |
| El panel dice "ComfyUI: sin conexión" | Comprueba que ComfyUI está arrancado. La app lo busca sola en los puertos **8188** (portable) y **8000** (Desktop); si lo tienes en otro, escribe su dirección en `url` de `[comfyui]`. |
| Las imágenes dan error | Mira la ventana de ComfyUI: suele ser un modelo que falta o un nombre de archivo distinto en el workflow. |
| Quiero ver la imagen formándose | Arranca ComfyUI con `--preview-method auto`. Sin esa opción solo se ve la barra de progreso. |
| Quiero empezar de cero | Cierra la app y borra la carpeta `datos/` (imágenes, fotos, votos e historial). |
| La opción de foto no aparece | Tu workflow necesita un `KSampler` y un `VAE Decode` normales. Con el de Z-Image Turbo funciona. |

## Datos

Todo se guarda en `datos/`, solo en este PC:
- `estudio.db`: historial;
- `imagenes/`: los PNG originales;
- `miniaturas/`: las versiones ligeras para galerías;
- `estilos/`: las tarjetas de técnicas y carnavales;
- `fotos/`: las fotos que sube el alumnado para transformarlas.

ComfyUI guarda además una copia de cada foto en su carpeta `input/` (archivos `estudio_*.jpg`).
**Al terminar el evento, borra `datos/fotos/` y esos archivos** si no quieres conservarlos.

No se piden nombres reales ni emails: solo un alias.

## Desarrollo

```bash
pip install -r requirements.txt pytest python-multipart
python -m pytest            # pruebas con un ComfyUI simulado (sin GPU)
python -m tests.comfy_falso # ComfyUI falso en :8188 para probar la interfaz
python -m app               # arranca el estudio
python herramientas/empaquetar.py  # genera dist/EstudioCarnaLab-v<versión>.zip para Windows
```
