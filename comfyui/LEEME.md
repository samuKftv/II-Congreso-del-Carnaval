# Prueba de imágenes de referencia en ComfyUI

Workflow para probar en ComfyUI cómo sale una imagen nueva a partir de **varias imágenes de
referencia**: una persona, un disfraz y un estilo, por ejemplo el cartel de CarnaLab.

Archivo: **`referencias_flux2_klein.json`**. Arrástralo a la ventana de ComfyUI para abrirlo.

## Por qué FLUX.2 [Klein] 4B

- **Entiende varias imágenes a la vez.** Le puedes pedir *"pon a la persona de la imagen 1 el disfraz
  de la imagen 2, con el estilo de la imagen 3"*. Z-Image Turbo no admite esto: solo puede partir de
  una foto, que es lo que hace ya la app con "Usar una foto".
- **Es rápido:** 4 pasos.
- **Cabe sin problema en tus 12 GB.**
- **Usa el mismo codificador de texto que Z-Image Turbo** (`qwen_3_4b.safetensors`), así que solo
  hay que descargar unos 4 GB.

## Archivos que hay que descargar

| Archivo | Carpeta de ComfyUI |
|---|---|
| [flux-2-klein-4b-fp8.safetensors](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors) (3,8 GB) | `models/diffusion_models` |
| [flux2-vae.safetensors](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors) (320 MB) | `models/vae` |
| `qwen_3_4b.safetensors` (ya lo tienes, es el de Z-Image) | `models/text_encoders` |

Si al abrir el workflow algún nodo sale en rojo, actualiza ComfyUI: FLUX.2 Klein necesita una versión
de 2026.

## Cómo probar

1. Carga una imagen en cada **Load Image**:
   - **Imagen 1 · Base:** la persona o la escena. El resultado tendrá su mismo tamaño.
   - **Imagen 2:** el disfraz, el objeto o el personaje.
   - **Imagen 3:** el estilo, por ejemplo `config/cartel.jpg` de la app.
2. En **Qué hacer con las referencias** escribe la instrucción nombrando las imágenes
   (*image 1, image 2, image 3*). Funciona mejor en inglés.
3. Pulsa **Run**.

**Con menos imágenes:** selecciona los dos nodos *Referencia 3* (positivo y negativo) y pulsa
**Ctrl+B** para saltarlos. Para quedarte solo con una imagen, haz lo mismo con los de la *Referencia 2*.

Ejemplos de instrucciones:

- *Dress the person from image 1 in the carnival costume from image 2, keeping their face and pose.*
- *Make image 1 look like the poster of image 3: flat cubist style, navy blue, coral, aqua and cream.*
- *Put the mask from image 2 on the person in image 1, at a carnival parade at night.*

## Cómo está montado

```
Imagen 1 ─┐                                   ┌─ Referencia 1 ─ Referencia 2 ─ Referencia 3 ─┐
Imagen 2 ─┼─ escalar a 1 MP ─ VAE Encode ─────┤                                              ├─ CFGGuider ─┐
Imagen 3 ─┘                                   └─ (lo mismo para el negativo) ────────────────┘             │
Instrucción (CLIP Text Encode) ─ positivo / ConditioningZeroOut ─ negativo                                 │
Tamaño de la imagen 1 ─ Flux2Scheduler (4 pasos) + EmptyFlux2LatentImage ─ SamplerCustomAdvanced ◀────────┘
                                                                              └─ VAE Decode ─ Save Image
```

## Otra opción: copiar la postura o la forma

Si lo que quieres es que Z-Image Turbo **copie la postura, los contornos o la profundidad** de una
foto (no su contenido), abre en ComfyUI la plantilla oficial **"Z-Image-Turbo Fun Union ControlNet"**
(*Workflow → Browse Templates*). Necesita un archivo más:
[Z-Image-Turbo-Fun-Controlnet-Union.safetensors](https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union/resolve/main/Z-Image-Turbo-Fun-Controlnet-Union.safetensors)
(2,9 GB), en `models/model_patches`.
