# Directrices — Estudio de imágenes de CarnaLab 2026

App web para que el alumnado escriba un prompt desde su móvil o portátil y reciba
una imagen generada con ComfyUI en el PC del profesor.

## 1. Contexto fijado

| Tema | Decisión |
|---|---|
| PC de render | Windows 11 · RTX 5070 12 GB · 32 GB RAM |
| Modelo | Z-Image Turbo en ComfyUI (9 pasos, CFG 1) |
| Red | WiFi del aula. Sin acceso desde fuera ni túneles |
| Usuarios | Alumnado mayor de edad |
| Identidad visual | **CarnaLab 2026 · II Congreso Internacional de Profesionalización del Carnaval** (Santa Cruz de Tenerife). Colores y cartel del congreso, logo del **CIFP Las Indias** |

## 2. Arquitectura

```
Móvil / portátil ──WiFi──▶ App "Estudio" (PC profe, puerto 8080) ──▶ ComfyUI (127.0.0.1:8188) ──▶ GPU
```

- **ComfyUI no se expone nunca a la red.** Sigue escuchando solo en `127.0.0.1`.
  La app es la única que habla con él.
- La app recibe **solo** texto, estilo y formato. Los mete en un workflow fijo
  (`config/workflow_api.json`, exportado de ComfyUI en formato API) y devuelve la imagen.
- **Cola propia**: la app envía a ComfyUI un trabajo cada vez. Así puede mostrar la
  posición de cada uno, cancelar y repartir los turnos de forma justa.
- **Una imagen en cola por persona**: hasta que no termina la suya, nadie puede
  volver a pulsar "Crear". Los turnos se reparten solos.
- Tiempo estimado de espera calculado con la **duración real** de las últimas imágenes.

## 3. Alumnado: una pantalla, cero ajustes técnicos

1. **Entrada**: escanean el QR que se proyecta, escriben su alias y ya están dentro.
2. **Crear**: caja de texto grande, botón "Inspírame", tarjetas de estilo y tres formatos
   (cuadrado, vertical y horizontal).
3. **Esperar**: "Tienes 3 personas delante · ~30 s", barra de progreso y la imagen
   apareciendo poco a poco (si ComfyUI tiene activada la vista previa).
4. **Resultado**: imagen grande con los botones Descargar · Otra versión · Nueva idea.
5. **Mis creaciones**: su galería personal.

Pasos, CFG, sampler y semilla los fija el workflow. El alumnado no los ve.

## 4. Profesor

- **Panel** (`/panel`):
  - abrir y cerrar el estudio;
  - ver la cola y cancelar trabajos;
  - ver todas las imágenes con su alias y prompt;
  - **revisar cada imagen antes de que sea pública** (✅ Publicar / ❌ Rechazar), retirarla después
    y pausar un alias;
  - consultar el estado de ComfyUI.
- Desde el **propio PC** (`localhost`) el panel entra sin contraseña. Desde otro
  dispositivo pide la clave de `config/ajustes.toml`.
- **Modo proyector** (`/proyector`): pantalla del aula con el QR de acceso siempre visible. El panel
  elige qué enseña: **mosaico** (por defecto), **galería** o **ganadoras** del concurso.

## 5. Seguridad y privacidad (adultos, evento público)

- Acceso con **código del aula y alias**. El QR ya lleva el código dentro. No se piden
  emails ni nombres reales.
- **Dos barreras**:
  1. **Filtro de palabras** configurable (`config/ajustes.toml`) antes de encolar.
  2. **Revisión del profesor**: con `revisar_antes = true` (por defecto) ninguna imagen sale en el
     proyector, el mosaico ni la galería hasta que el profesor la aprueba en el panel. Su autor sí la ve
     en su móvil, con el aviso de que está en revisión.
- Con CFG 1, Z-Image Turbo **ignora el prompt negativo**, así que el filtro y la revisión son las
  herramientas de moderación.
- Las imágenes se guardan **solo en el PC del profesor** (`datos/`).

## 6. Idioma

Se escribe **en español**. El codificador de texto de Z-Image (Qwen3-4B) es
multilingüe. Las "recetas" de estilo que se añaden por dentro van en inglés para
que sean más fiables. Si en las pruebas el español rinde peor, se añadirá traducción.

## 7. Tecnología

- **Python 3.11+ con FastAPI**. Página web en HTML, CSS y JS sin compilación.
- **Sin dependencias de Internet** en el navegador: ni fuentes ni librerías externas.
  Funciona aunque la WiFi del aula no tenga salida a Internet.
- **SQLite** para el historial: sobrevive a reinicios.
- **Windows**: ZIP portátil (`descargas/EstudioCarnaLab.zip`) con Python 3.13 oficial y las
  dependencias ya compiladas: descomprimir y doble clic. Se genera con `herramientas/empaquetar.py`.
  Alternativa desde el código: `instalar.bat` (una vez) e `iniciar.bat` (cada sesión).
- **ComfyUI**: se busca solo en los puertos 8188 (portable) y 8000 (Desktop), sin pasar por el
  proxy de la red del centro.
- Al arrancar se comprueba que el puerto 8080 está libre y se avisa si hay otro estudio abierto.
- **Configuración editable** sin tocar código: `config/ajustes.toml`,
  `config/estilos.json` y `config/workflow_api.json`.

## 8. Comprobaciones antes del evento

1. ComfyUI arrancado y generando con el workflow del evento.
2. El PC conectado a la **misma red** que la WiFi del aula (mejor por cable).
3. Permitir la app en el **Firewall de Windows** (puerto 8080).
4. Comprobar que la WiFi **no aísla a los clientes** (*AP/client isolation*). Si lo
   hace, los móviles no verán el PC: hay que pedir a informática que lo desactive o
   usar un router propio.
5. Prueba con 3 o 4 móviles a la vez.

## 9. Fases

1. **Primera versión** ✅: todo lo descrito arriba.
2. **Segunda versión** ✅:
   - **Carnavales del mundo × técnicas**: se combinan; la receta del carnaval describe el lugar y la
     tradición, la técnica cómo se pinta.
   - **Botones de detalles** (lugar, luz, plano, ambiente): enseñan a construir un buen prompt.
     (En la cuarta versión se añade un intérprete de ideas que va en el procesador, sin tocar la VRAM.)
   - **Foto como base (img2img)**: la foto se reduce en el móvil, se ajusta a ~1 MP y se usa con
     `denoise` 0,5 / 0,68 / 0,82. (Desde la 11.ª versión es pública y pasa por la revisión del profesor.)
   - **Votos**: uno por persona e imagen, sin votarse a sí mismo; solo imágenes públicas y no ocultas.
   - **Retos**: fases *creando* (cuenta atrás) → *votando* → *podio* → *cerrado*. Participa lo creado
     en la fase *creando*. El paso a votación es automático al acabar el tiempo.
   - **Identidad**: colores, cartel y técnica "Cartel CarnaLab" sacados del cartel del congreso;
     logo del CIFP Las Indias en versión clara; Canarias como primer carnaval y ideas sobre los
     oficios del carnaval (#LABCIFPLasIndias).
3. **Tercera versión** ✅ (concurso de toda la sesión):
   - **Revisión antes de publicar**: cada imagen nace `pendiente`; el profesor la pasa a `aprobada` o
     `rechazada` desde la bandeja del panel. Las imágenes que antes se "ocultaban" pasan a `rechazada`.
   - **Mosaico gigante**: cada imagen aprobada es una pieza de una rejilla con la forma del cartel, en un
     hueco aleatorio pero fijo. Los huecos vacíos enseñan el cartel en oscuro y cada 30 s el cartel
     aparece encima de todas las piezas. La pieza nueva sale primero en grande con su autor y luego vuela
     a su hueco. Las piezas usan teselas de 160 px.
   - **Mosaico con tope** (desde la versión 3.5): como mucho `piezas_mosaico` (150) piezas, en la rejilla
     con forma de cartel más grande que quepa con piezas casi cuadradas (con 150: 10 × 15). La pieza número n
     va siempre al hueco n módulo huecos, así que, cuando se llena, cada nueva sustituye a la más antigua.
     Sin panel lateral: el cartel ocupa todo el alto de la pantalla.
   - **Ganadoras**: al mostrar el podio del concurso se **cierra la votación**; al volver al mosaico se
     reabre.
4. **Cuarta versión** ✅:
   - **Votar de una en una**: botón ❤️ Votar siempre a mano, tarjetas grandes (deslizar a la derecha o
     tocar dos veces = me gusta; a la izquierda = otra), también en la pantalla de espera y en el
     resultado. Las imágenes salen en orden aleatorio, sin las propias ni las ya votadas, para que todas
     se vean.
   - **Intérprete de ideas** (opcional, Ollama + qwen2.5:3b): convierte la idea en una descripción en
     inglés de 40–70 palabras sin cambiar lo que se pidió; las recetas de técnica y carnaval se aplican
     encima. Va en el procesador (`num_gpu = 0`) y trabaja por adelantado sobre la cola: elige la
     primera idea que le dé tiempo a terminar antes de que llegue su turno, y si no llega, se pinta la
     idea tal cual. Lo que devuelve pasa también por el filtro de palabras.
5. **Quinta versión** ✅ (100 móviles en una WiFi):
   - Gzip para HTML, JS, CSS y JSON; cartel y logo reducidos a WebP; fuente en WOFF2. La primera carga
     baja de unos 320 KB a unos 90 KB.
   - Vista WebP de 1280 px para ver la imagen en el móvil (el PNG queda solo para descargar).
   - Barra superior fija con ❤️ Votar y Mías; zonas seguras (`env(safe-area-inset-*)`);
     `touch-action: manipulation`; sin `backdrop-filter`; puesta al día al volver a la pestaña;
     consejo de guardado en iPhone.
   - Modelo de difusión en fp8 (`ligero = true`): Z-Image Turbo en bf16 (12 GB) no cabe entero en
     12 GB de VRAM.
6. **Sexta versión** ✅ (modo internet):
   - Túnel rápido de Cloudflare (`cloudflared tunnel --url`), lanzado y vigilado por la app. El QR usa la
     dirección https pública y, si el túnel se corta, se reabre solo con una dirección nueva.
   - **Seguridad**: una petición solo cuenta como "este PC" si llega de 127.0.0.1 **y no trae cabeceras
     de intermediario** (`Cf-Connecting-Ip`, `X-Forwarded-For`…). Así el panel no queda abierto a internet.
   - Por https, los móviles preguntan por su imagen cada 2 s en vez de cada 1 s.
7. **Séptima versión** ✅ (sencillez para el día del congreso):
   - Logo del CIFP Las Indias en su versión clara (crema), sin placa.
   - Proyector sin el rótulo "Estudio de imágenes": el nombre del congreso va grande, en negro sobre una
     franja crema, y el hashtag del evento es #LABCIFPLasIndias.
   - Proyector: solo el QR (sin enlace ni código); con el mosaico, el lateral y el cartel van juntos y
     centrados, sin chips de estado.
   - Entrada sin código de aula por defecto y nombre opcional (si se deja vacío, uno de carnaval).
   - Móvil en modo sencillo: pestañas grandes ✨ Crear / ❤️ Votar; Crear es solo la idea, Inspírame y el
     botón; técnica y formato fijos (`[alumnado]`); votar es una pestaña, no una ventana encima.
8. **Octava versión** ✅ (modelo y LoRA propios):
   - `[mi_modelo]` en `ajustes.toml`: `modelo` sustituye el archivo del cargador del workflow
     (`unet_name` o `ckpt_name`); `lora` añade un `LoraLoader` (nodo 9100) justo detrás del cargador del
     modelo y del CLIP, y todo lo que tiraba de ellos pasa a tirar del LoRA. Si el texto no viene de un
     CLIP, se usa `LoraLoaderModelOnly`. `palabra_clave` se antepone al prompt al enviarlo (no se guarda
     en la idea).
   - Comprobación con `/object_info` de ComfyUI al conectar (y cada 20 s mientras falte algo): nodos que
     no existen y archivos que no están, con la carpeta donde van. Los nombres que solo cambian en la
     subcarpeta, la barra o la extensión se corrigen solos.
   - `5-PROBAR-MI-MODELO.bat` (`python -m app.probar_modelo`): las mismas ideas y semillas sin LoRA y con
     varias fuerzas (o modelo original frente al tuyo), en una hoja JPG, con los segundos por imagen.
9. **Novena versión** ✅ (FLUX.2 Klein 4B):
   - `[mi_modelo] base`: `z-image-turbo` (el workflow de `[comfyui]`), `flux2-klein-4b` (plantilla oficial en
     `config/plantillas/flux2_klein_4b.json`: SamplerCustomAdvanced + CFGGuider 1 + Flux2Scheduler 4 pasos +
     EmptyFlux2LatentImage, CLIPLoader `qwen_3_4b` tipo `flux2`, VAE `flux2-vae`), `flux2-klein-4b-base`
     (20 pasos, guía 5, negativo vacío) y `auto` (por el nombre del archivo, solo con el workflow normal).
     `pasos` y `cfg` en `[mi_modelo]` los cambian.
   - El workflow se entiende también con SamplerCustomAdvanced + guía: prompt por `guider.positive`, modelo por
     `guider.model`, y el tamaño va al lienzo y al planificador (`Nodos.tamanos`).
   - `app/arquitectura.py`: familia del modelo y del LoRA leyendo solo la cabecera del .safetensors (con las
     carpetas de `/internal/folder_paths`), como `model_detection.py` de ComfyUI; aviso en el panel si no
     encaja con el workflow; el error "mat1 and mat2" se traduce con la familia que espera esa dimensión.
   - `5-PROBAR-MI-MODELO.bat` avisa antes de pintar si no encajan, para cada columna en su primer error y
     avisa si una imagen sale negra.
10. **Décima versión** ✅ (prompts de carnaval):
    - Estilo `carnaval` ("Carnaval de Tenerife"), el de modo sencillo por defecto: añade la ambientación del
      Carnaval de Santa Cruz de Tenerife a cada idea, también cuando el intérprete no llega.
      `Estilo.aplicar` quita el punto final de la idea para no dejar "..".
    - Intérprete: lleva toda idea al carnaval (disfraz, carroza, murga, comparsa, gala), glosario del
      carnaval canario y cinco ejemplos (animal, persona, murga, oficio); 35-60 palabras.
    - `[interprete] esperar` (true): la gráfica espera hasta 25 s y el intérprete coge las ideas por orden
      de llegada, así que mientras se pinta una se interpreta la siguiente. `grafica` (false) deja a Ollama
      usar la GPU. El panel muestra cuántas ideas ha mejorado (`prompt_ia` no vacío).
11. **Undécima versión** ✅ (foto propia otra vez):
    - `[alumnado] fotos = true`. Las imágenes con foto son públicas como las demás y pasan por la bandeja
      "Por revisar"; desaparece la casilla "Compartir" del móvil (el servidor ignora `publico`).
    - FLUX.2 Klein edita la foto como su plantilla oficial: LoadImage → VAEEncode → ReferenceLatent en el
      positivo y el negativo de la CFGGuider, al tamaño de la foto; sin "fuerza" (`/api/info` manda
      `fuerzas: []`) y con "Using the reference photo, keep the same people, faces and pose." delante.
      Z-Image Turbo sigue con img2img (KSampler con denoise).
    - Proyector: el nombre del congreso y la línea de fecha y hashtag en negro, sin franja debajo.
12. **Duodécima versión** ✅ (prompts para FLUX.2):
    - `"ideas"` de `estilos.json` pasa a ser `{"idea", "prompt"}`: 32 ideas en español con su prompt en inglés
      (sujeto + acción + estilo + contexto, lo importante primero, sin negativos; `docs/PROMPTS.md`). Si la
      idea llega sin tocar (normalizada: mayúsculas, espacios, punto final) y sin foto, `prompt_final` y
      `prompt_ia` son ese prompt: no pasa por el intérprete ni por la receta. Siguen valiendo ideas en texto.
    - La receta `carnaval` añade el estilo ("Vibrant editorial photography…"); el intérprete pone lo
      importante primero y escribe frases, sin negativos.
    - Proyector: el nombre del congreso y la línea de fecha y hashtag vuelven a su estilo original.
    - Inspírame: si se pulsa Crear (o se toca el texto) mientras la idea se escribe letra a letra, se completa
      antes de enviarla, para que llegue entera y se reconozca.
    - `5-PROBAR-MI-MODELO.bat` sin modelo ni LoRA pinta con el modelo del workflow (una columna): sirve para
      comparar Z-Image Turbo con FLUX.2 Klein con las mismas ideas.
13. **Decimotercera versión** ✅ (estilo de dibujo):
    - El modelo y el LoRA propios son de **estilo de dibujo**, no de carnaval: los 32 prompts de Inspírame
      pasan a ser neutros (sin "photography", "bokeh", "cinematic"…) y el estilo lo pone la receta, igual que
      con las ideas interpretadas (`prompt_final = receta(prompt optimizado)`).
    - Estilo `carnaval-dibujo` ("Illustration of the Carnival of Santa Cruz de Tenerife…") y
      `[alumnado] estilo = "auto"`: `carnaval-dibujo` si hay `modelo` o `lora` en `[mi_modelo]`; si no, `carnaval`.
    - La cola espera (máx. 20 s) a la primera comprobación de archivos antes de pintar: si no, una imagen pedida
      nada más abrir el estudio salía con el nombre del modelo sin corregir. `modelo` y `lora` sin extensión
      reciben `.safetensors`.
14. **Decimocuarta versión** ✅ (moderar desde el móvil):
    - En pantallas estrechas, botón fijo "🛂 Por revisar N" que lleva a la bandeja (se oculta sin pendientes y
      se actualiza al publicar o rechazar). Quitada la nota de imágenes privadas.
15. **Después**: descarga en ZIP de la galería, exportar el podio como imagen.
