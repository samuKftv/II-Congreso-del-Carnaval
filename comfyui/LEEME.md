# Pruebas en ComfyUI

Workflows para probar directamente en ComfyUI, antes de llevarlos a la app. Para abrir uno,
arrastra el archivo `.json` a la ventana de ComfyUI.

| Archivo | Para qué |
|---|---|
| **`reina_tenerife_referencia.json`** | Crear reinas del Carnaval de Tenerife **rediseñando la foto de una reina real** con una idea |
| `referencias_flux2_klein.json` | Combinar varias imágenes: una persona, un disfraz y un estilo |

## Modelos (sirven para los dos)

Los dos usan **FLUX.2 [Klein] 4B**, que entiende imágenes de referencia, es rápido (4 pasos) y cabe
sin problema en 12 GB. Comparte el codificador de texto con Z-Image Turbo, así que solo hay que
descargar unos 4 GB:

| Archivo | Carpeta de ComfyUI |
|---|---|
| [flux-2-klein-4b-fp8.safetensors](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors) (3,8 GB) | `models/diffusion_models` |
| [flux2-vae.safetensors](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors) (320 MB) | `models/vae` |
| `qwen_3_4b.safetensors` (ya lo tienes, es el de Z-Image) | `models/text_encoders` |

Si al abrir un workflow algún nodo sale en rojo, actualiza ComfyUI: FLUX.2 Klein necesita una
versión de 2026.

## 👑 Reina del Carnaval de Tenerife (`reina_tenerife_referencia.json`)

Los modelos saben poco de cómo es de verdad una reina de Santa Cruz: suelen pintar trajes de samba
genéricos. Este workflow **parte de la foto de una reina real y la rediseña con la idea**.

> **Por qué así:** FLUX.2 [Klein] es un modelo de **edición**. Copia muy bien lo que ve en una foto
> (la estructura, el tamaño, el acabado), pero **no aprende un estilo** para inventar desde cero
> "algo parecido". Si se le pide una reina nueva "al estilo de las fotos", casi no les hace caso.
> Si se le pide **cambiar el traje de la foto**, el resultado sí parece una reina de Tenerife.

**Cómo funciona:**

1. **Foto:** una reina con el **traje entero, de frente, ocupando casi toda la foto**. Si sale mucho
   público o escenario alrededor, recórtala antes. El resultado tiene la misma forma que la foto
   (vertical u horizontal).
2. **Idea:** solo el **tema del traje**, mejor en inglés: *"the Teide volcano with lava and stars"*,
   *"a peacock"*, *"the Canary Islands sea"*…
3. **Run** genera **tres imágenes con la misma idea y la misma semilla**:
   - **① Misma estructura, tema nuevo:** conserva la forma del traje de la foto y cambia colores,
     adornos y figuras. Es la más fiel.
   - **② Traje nuevo, mismo estilo:** un traje distinto, pero construido y decorado igual que el de
     la foto. Tiene más libertad.
   - **③ Sin foto:** solo con texto, para comparar.

Las tres recetas son los nodos *Receta*: se pueden retocar, y **{idea}** es donde entra la idea.
Todas piden **otra cara** para no copiar a la reina real.

**Consejos:**

- **¿Se parece demasiado a la foto?** Quédate con la ②. **¿Se aleja demasiado?** Con la ①.
- **Para tener variedad, cambia de foto:** cada reina da otra estructura. Tener 5 o 6 fotos distintas
  da mucho juego.
- Si la idea no se nota, ponla más concreta y visual (*"a volcano: black lava rocks, red and orange
  flames, smoke"* en vez de *"fire"*).
- Usa fotos que tengáis derecho a usar: de la organización, de prensa con permiso o propias.

### ¿Y si quiero que lo sepa siempre, sin pasarle fotos?

Para eso se entrena un **LoRA**: un pequeño complemento del modelo hecho con unas 20 o 30 fotos de
trajes de reina. Después, Z-Image Turbo sabría pintar reinas de Tenerife solo con escribirlo, y la app
podría usarlo directamente. Hacen falta las fotos, una herramienta de entrenamiento y una o dos horas
de la gráfica. Es la forma de que **invente reinas nuevas desde cero** con sentido, cosa que las
fotos de referencia no consiguen.

## Combinar varias imágenes (`referencias_flux2_klein.json`)

Crea una imagen a partir de **varias imágenes de referencia**. Por ejemplo: *"pon a la persona de la
imagen 1 el disfraz de la imagen 2, con el estilo de la imagen 3"*.

1. **Imagen 1 · Base:** la persona o la escena. El resultado tendrá su mismo tamaño.
2. **Imagen 2:** el disfraz, el objeto o el personaje.
3. **Imagen 3:** el estilo, por ejemplo `config/cartel.jpg` de la app.
4. Escribe la instrucción nombrando las imágenes (*image 1, image 2, image 3*) y pulsa **Run**.

**Con menos imágenes:** salta con **Ctrl+B** los nodos *Referencia 3* (y *Referencia 2* si solo usas una).

## Otra opción: copiar la postura o la forma

Si lo que quieres es que Z-Image Turbo **copie la postura, los contornos o la profundidad** de una foto
(no su contenido), abre en ComfyUI la plantilla oficial **"Z-Image-Turbo Fun Union ControlNet"**
(*Workflow → Browse Templates*). Necesita un archivo más:
[Z-Image-Turbo-Fun-Controlnet-Union.safetensors](https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union/resolve/main/Z-Image-Turbo-Fun-Controlnet-Union.safetensors)
(2,9 GB), en `models/model_patches`.
