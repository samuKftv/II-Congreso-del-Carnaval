# 🎭 Estudio de imágenes — CarnaLab 2026

**II Congreso Internacional de Profesionalización del Carnaval** · Santa Cruz de Tenerife.
Un estudio del **CIFP Las Indias**.

El alumnado escribe una idea en el móvil y recibe una imagen generada por **ComfyUI**
en el PC del profesor. Todo funciona dentro de la WiFi del aula.

- 📱 **Alumnado**: escanea el QR, pone su alias y crea. Sin instalar nada.
  - **Carnavales del mundo × técnicas**: combina Venecia, Río, Cádiz, Oruro… con acuarela, cómic, 3D…
  - **Botones de detalles** (lugar, luz, plano, ambiente) que enriquecen la idea.
  - **Foto como base**: transforma una foto propia. Es **privada** salvo que la persona marque compartirla.
  - **❤️ Votar** de una en una, deslizando como en una app de citas, también mientras esperan su turno.
    Nadie puede votarse a sí mismo.
  - **Intérprete de ideas** (opcional): una IA de texto en tu PC entiende ideas cortas, raras o en español
    y las convierte en una descripción detallada antes de pintarlas.
- 🎛️ **Panel del profesor**: abre y cierra el estudio, controla la cola, **aprueba cada imagen antes de que
  salga en público** y lanza **retos con cuenta atrás**.
- 📺 **Proyector**: un **mosaico gigante con la forma del cartel** que se completa con las imágenes aprobadas,
  con el QR siempre visible, las más votadas en directo y el **podio** de ganadoras.

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

## Concurso: el mosaico de CarnaLab

El estudio funciona como un concurso durante toda la sesión:

1. **El alumnado crea** desde el móvil. Su imagen le llega al momento, con el aviso
   *"El jurado está revisando tu imagen"*.
2. **Tú decides qué sale**: en el panel, la bandeja **🛂 Por revisar** enseña cada imagen nueva con su
   autor y su idea. **✅ Publicar** la manda al mosaico; **❌ Rechazar** la deja fuera;
   **🚫 Rechazar y pausar** además corta el acceso de esa persona. La pestaña del navegador muestra
   cuántas esperan, por ejemplo *(3) Panel del profesor*.
3. **El mosaico crece en el proyector**: la imagen aprobada sale en grande con su autor y vuela a su hueco.
   Los huecos libres enseñan el cartel en oscuro y, cada medio minuto, el cartel aparece entero encima de
   todas las piezas. Cuando se llena, se hace más grande.
4. **Todo el mundo vota** desde el móvil con el botón **❤️ Votar**: las imágenes salen de una en una,
   deslizar a la derecha (o tocar dos veces) es *me gusta*, a la izquierda pasa a otra. También se vota
   mientras se espera turno. Las tres más votadas llevan medalla en el
   mosaico y salen en el lateral del proyector.
5. **Al final**, en el panel, **📺 Proyector → 🏆 Ganadoras**: se cierra la votación y el proyector
   enseña el podio con confeti. **🧩 Mosaico** vuelve atrás y reabre la votación.

> Si quieres que las imágenes se publiquen solas, apaga **Revisión antes de publicar** en el panel o pon
> `revisar_antes = false` en `[moderacion]` de `ajustes.toml`. Puedes retirar cualquier imagen después,
> en *Imágenes creadas*.
>
> Para moderar desde el móvil mientras das la charla, pon una `clave_profesor` propia en `ajustes.toml`
> y abre `http://<IP del PC>:8080/panel` en tu teléfono.

## Pensada para el móvil

El público solo usa el móvil, así que la app está hecha para él y para una WiFi con 100 teléfonos:

- **Ligera**: la primera carga pesa unos 90 KB. Textos y datos van comprimidos, y el cartel, el logo y la
  fuente se envían en versiones reducidas.
- **Imágenes ligeras**: en el móvil se ve un WebP mucho más ligero que el PNG original. El PNG sigue
  disponible en ⬇️ Descargar, a calidad completa.
- **A mano con el pulgar**: ❤️ Votar y Mías se quedan arriba al bajar por la pantalla, y ✨ Crear se
  queda abajo. Los botones miden al menos 44 px, el iPhone no hace zoom al escribir y se respetan la
  muesca y la barra de inicio.
- **Fluida en móviles sencillos**: sin desenfoques costosos y sin el retraso de 300 ms al tocar.
- **Si bloquean el móvil** mientras esperan, al volver se pone al día al momento.
- **iPhone**: se explica cómo guardar la imagen en Fotos (mantener el dedo sobre ella).

## Modelo de imágenes

Recomendado para una RTX 5070 de 12 GB y 100 personas: **Z-Image Turbo**, el que ya usas.

- Es de los modelos rápidos (9 pasos) con mejor calidad: personas, disfraces, luces y texto. Además
  entiende frases largas, que es justo lo que le da el intérprete de ideas.
- **Cárgalo en fp8** (ya viene así: `ligero = true` en `[comfyui]` de `ajustes.toml`). El modelo normal
  ocupa 12 GB y no cabe entero en tu gráfica, así que ComfyUI va pasando trozos y tarda más. En fp8
  ocupa la mitad, cabe entero y va bastante más rápido, con una diferencia de calidad casi imperceptible.
  No hace falta descargar nada: la app le pide a ComfyUI que cargue el mismo archivo en fp8.
- **Compruébalo con el simulacro**: lanza uno con `ligero = true` y otro con `ligero = false`, y compara
  los "s por imagen".

| Modelo | Velocidad | Calidad | ¿Para el evento? |
|---|---|---|---|
| **Z-Image Turbo en fp8** | Rápido | Muy buena | ✅ Recomendado |
| Z-Image Turbo en bf16 (normal) | Más lento en 12 GB | Muy buena | Solo si en el simulacro va igual |
| FLUX.2 [Klein] 4B | El más rápido (4 pasos) | Buena, algo menos detalle | Plan B si el simulacro va justo (habría que adaptar el workflow) |
| SDXL con LoRA rápida | Rápido | Entiende peor las frases | ❌ |
| FLUX.1 dev, Qwen-Image | Lentos en 12 GB | Muy buena | ❌ Demasiado grandes para 100 personas |

Si aun así va justo, baja el tamaño en `[formatos]` (por ejemplo `cuadrado = [768, 768]`).

## Intérprete de ideas (recomendado)

La gente escribe ideas cortas, raras o en español ("un pulpo pirata", "conviérteme en reina"). El modelo
de imágenes entiende mucho mejor una descripción detallada en inglés. El intérprete hace esa traducción:

> *un pulpo pirata* → *A cheerful giant purple octopus dressed as a pirate captain, with a tricorn hat
> trimmed in gold, an eye patch and a tiny wooden sword…*

1. Una sola vez, con internet: doble clic en **`4-INSTALAR-INTERPRETE.bat`** (o `instalar_interprete.bat`).
   Instala [Ollama](https://ollama.com) y el modelo **qwen2.5:3b** (unos 2 GB).
2. Abre el estudio. En el panel, junto a ComfyUI, verás **🧠 Intérprete de ideas: listo**.

- Funciona **sin internet** y en el **procesador**, así que no le quita memoria a la gráfica.
- Trabaja **por adelantado** mientras la gente espera en la cola. Si no le da tiempo o Ollama está
  cerrado, la idea se pinta tal cual: nunca frena la cola.
- El alumnado sigue viendo su idea original. En el panel, debajo de cada imagen, ves en azul
  **🧠 lo que entendió**.
- El simulacro te dice en cuántas imágenes llegó a tiempo. Si llega a pocas, tu procesador va justo:
  puedes probar otro modelo más pequeño en `[interprete]` de `ajustes.toml` (por ejemplo `qwen2.5:1.5b`,
  después de `ollama pull qwen2.5:1.5b`) o desactivarlo con `activado = false`.

## Probar con 100 personas (simulacro)

Antes del evento, comprueba cómo responde **tu PC con tu ComfyUI de verdad**:

1. Cierra la ventana negra del estudio normal y arranca ComfyUI.
2. Doble clic en **`3-PROBAR-CON-100-PERSONAS.bat`** (o `probar_100_personas.bat` si instalaste desde el código).
   Te pregunta si las imágenes se publican solas o si quieres practicar de jurado.
3. Se abre un estudio aparte, con su panel, y **100 personas virtuales** ("Prueba 001"…) lo usan durante
   10 minutos: piden ideas, esperan su turno, miran la galería y votan. Abre el **proyector** para ver
   cómo se llena el mosaico. Puedes entrar también con tu móvil para ver la espera desde dentro.
4. La ventana del simulacro informa cada 10 s y al final enseña un **resumen**: segundos por imagen,
   imágenes por hora, cuánto esperaría la última persona si todas pidieran a la vez y si hubo errores.

Todo se guarda en `datos-simulacro/`, que se borra al empezar cada simulacro: **tus datos de verdad no se
tocan**. El panel lo indica con la etiqueta *🧪 SIMULACRO*.

El simulacro prueba tu PC, pero no la WiFi del recinto. Para eso, el día antes, entra en la red del
recinto con 3 o 4 móviles y comprueba que abren el QR.

## Retos

1. En el panel, escribe el tema (o pulsa una de las ideas), elige la duración y pulsa **🏁 Lanzar reto**.
2. Móviles y proyector muestran el reto y la cuenta atrás. Todo lo que se cree mientras tanto participa
   (con la revisión activada, cuando lo apruebas).
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

- **`reina_tenerife_referencia.json`**: crea reinas del Carnaval de Tenerife **rediseñando la foto de
  una reina real** con una idea (misma estructura o traje nuevo del mismo estilo) y lo compara con el
  resultado sin foto.
- **`referencias_flux2_klein.json`**: crea una imagen a partir de **varias imágenes de referencia**
  (persona + disfraz + estilo) con FLUX.2 [Klein] 4B.

## Configuración (`config/`)

| Archivo | Para qué |
|---|---|
| `ajustes.toml` | Nombre del evento, puerto, código del aula, clave del profesor, dirección de ComfyUI, modelo en fp8 (`ligero`), intérprete de ideas, formatos, revisión antes de publicar, palabras bloqueadas |
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
| El panel dice "Intérprete: Ollama no está abierto" | Abre Ollama desde el menú Inicio (icono de la llama junto al reloj). Si dice "falta el modelo", ejecuta `4-INSTALAR-INTERPRETE.bat`. Mientras tanto, las ideas se pintan tal cual. |
| Quiero ver la imagen formándose | Arranca ComfyUI con `--preview-method auto`. Sin esa opción solo se ve la barra de progreso. |
| Quiero empezar de cero | Cierra la app y borra la carpeta `datos/` (imágenes, fotos, votos e historial). |
| La opción de foto no aparece | Tu workflow necesita un `KSampler` y un `VAE Decode` normales. Con el de Z-Image Turbo funciona. |

## Datos

Todo se guarda en `datos/`, solo en este PC:
- `estudio.db`: historial;
- `imagenes/`: los PNG originales;
- `vistas/`: las versiones WebP que se ven en los móviles;
- `miniaturas/`: las versiones ligeras para galerías;
- `teselas/`: las piezas pequeñas del mosaico;
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
