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
     `denoise` 0,5 / 0,68 / 0,82. **Privada por defecto**: solo sale en el proyector y la galería si la
     persona marca compartirla.
   - **Votos**: uno por persona e imagen, sin votarse a sí mismo; solo imágenes públicas y no ocultas.
   - **Retos**: fases *creando* (cuenta atrás) → *votando* → *podio* → *cerrado*. Participa lo creado
     en la fase *creando*. El paso a votación es automático al acabar el tiempo.
   - **Identidad**: colores, cartel y técnica "Cartel CarnaLab" sacados del cartel del congreso;
     logo del CIFP Las Indias en versión clara; Canarias como primer carnaval y ideas sobre los
     oficios del carnaval (#CarnavalEmplea).
3. **Tercera versión** ✅ (concurso de toda la sesión):
   - **Revisión antes de publicar**: cada imagen nace `pendiente`; el profesor la pasa a `aprobada` o
     `rechazada` desde la bandeja del panel. Las imágenes que antes se "ocultaban" pasan a `rechazada`.
   - **Mosaico gigante**: cada imagen aprobada es una pieza de una rejilla con la forma del cartel, en un
     hueco aleatorio pero fijo. Los huecos vacíos enseñan el cartel en oscuro y cada 30 s el cartel
     aparece encima de todas las piezas. La pieza nueva sale primero en grande con su autor y luego vuela
     a su hueco. Al completarse, el mosaico crece (192 → 300 → 432… piezas). Las piezas usan teselas de
     160 px para que el proyector aguante miles.
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
5. **Después**: descarga en ZIP de la galería, exportar el podio como imagen.
