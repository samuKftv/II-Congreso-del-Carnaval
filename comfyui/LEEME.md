# Pruebas en ComfyUI

Workflows para probar directamente en ComfyUI, antes de llevarlos a la app. Para abrir uno,
arrastra el archivo `.json` a la ventana de ComfyUI.

| Archivo | Para qué |
|---|---|
| **`reina_tenerife_referencia.json`** | Enseñar al modelo **cómo es una reina del Carnaval de Tenerife** con 1 o 2 fotos reales |
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
genéricos. Este workflow **le enseña el estilo con fotos reales**, sin entrenar nada.

**Cómo funciona:**

1. **Fotos de reina A y B:** 1 o 2 fotos de trajes de reina. Mejor si se ve el traje completo, de
   frente y con buena luz. Con **dos trajes distintos** el modelo aprende el estilo en vez de copiar
   un traje concreto.
2. **Texto fijo:** describe cómo es una reina de Tenerife (estructura gigante a la espalda, lentejuelas,
   pedrería, espejos y plumas, tocado, escenario de la gala). Además pide **copiar solo el traje, no la
   persona**, para no reproducir la cara de la reina real.
3. **Idea:** lo que pediría el alumno, por ejemplo *"a carnival queen inspired by volcanoes"*. Funciona
   mejor en inglés.
4. **Run** genera **dos imágenes con la misma idea y la misma semilla**:
   - **SIN referencias:** lo que sabe el modelo por sí solo.
   - **CON referencias:** después de ver las fotos.

Comparándolas se ve si las fotos ayudan y cuánto.

**Con una sola foto:** selecciona los dos nodos *Referencia B* y pulsa **Ctrl+B** para saltarlos.

**Consejos:**

- Si el resultado copia demasiado la foto, usa dos fotos distintas o pon una idea más concreta.
- Si no se parece lo suficiente, prueba con fotos donde el traje se vea entero y ocupe toda la imagen.
- Usa fotos que tengáis derecho a usar: de la organización, de prensa con permiso o propias.

### ¿Y si quiero que lo sepa siempre, sin pasarle fotos?

Para eso se entrena un **LoRA**: un pequeño complemento del modelo hecho con unas 20 o 30 fotos de
trajes de reina. Después, Z-Image Turbo sabría pintar reinas de Tenerife solo con escribirlo, y la app
podría usarlo directamente. Hacen falta las fotos, una herramienta de entrenamiento y una o dos horas
de la gráfica. Si las fotos de referencia dan buen resultado, este es el siguiente paso natural.

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
