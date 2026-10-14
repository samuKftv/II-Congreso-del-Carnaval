// Panel del profesor.

const $ = (id) => document.getElementById(id);
const PAGINA = 60;

let clave = almacen.leer('estudio.clave') || '';
let ultimoEstado = null;
let imagenes = [];
let hayMas = false;
let info = null;
let arrancado = false;
let urlQr = '';

function cabeceras() {
  return clave ? { 'X-Clave': encodeURIComponent(clave) } : {};
}

async function apiProfe(ruta, opciones = {}) {
  try {
    return await api(ruta, { ...opciones, cabeceras: cabeceras() });
  } catch (e) {
    if (e.estado === 401) pedirClave();
    throw e;
  }
}

function pedirClave() {
  $('contenido').hidden = true;
  $('login').hidden = false;
  $('login-nota').textContent = ultimoEstado && !ultimoEstado.panel_remoto
    ? 'Desde otro dispositivo hace falta una clave_profesor en config/ajustes.toml (distinta de la de ejemplo).'
    : 'Escribe la clave del profesor de config/ajustes.toml.';
}

$('login').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  clave = $('clave').value;
  try {
    await apiProfe('/api/panel/estado');
    almacen.guardar('estudio.clave', clave);
    $('login').hidden = true;
    iniciar();
  } catch (e) {
    aviso(e.message, true);
  }
});

async function iniciar() {
  try {
    info = await api('/api/info');
    $('evento').textContent = `${info.evento} · ${info.subtitulo} · versión ${info.version}`;
    await refrescarEstado();
  } catch {
    return;
  }
  $('contenido').hidden = false;
  cargarImagenes(true);
  cargarRevision();
  if (arrancado) return;
  arrancado = true;
  setInterval(() => refrescarEstado().catch(() => {}), 1500);
  setInterval(() => cargarImagenes(false), 5000);
  setInterval(cargarRevision, 2000);
}

// --- Estado ---

async function refrescarEstado() {
  const e = await apiProfe('/api/panel/estado');
  ultimoEstado = e;

  const boton = $('interruptor');
  boton.className = `interruptor ${e.abierto ? 'abierto' : 'cerrado'}`;
  boton.replaceChildren(e.abierto ? '🟢 ABIERTO' : '🌙 CERRADO',
    el('small', {}, e.abierto ? 'Pulsa para cerrar' : 'Pulsa para abrir'));

  if (e.comfy.ok) {
    $('comfy-estado').replaceChildren(el('span', { class: 'punto ok' }), 'Conectado');
    const g = e.comfy.gpu;
    $('comfy-detalle').textContent = g
      ? `${g.nombre} · ${(g.vram_libre / 2 ** 30).toFixed(1)} de ${(g.vram_total / 2 ** 30).toFixed(1)} GB libres`
      : e.comfy.url;
  } else {
    $('comfy-estado').replaceChildren(el('span', { class: 'punto mal' }), 'Sin conexión');
    $('comfy-detalle').textContent = e.comfy.auto
      ? 'Arranca ComfyUI. La app lo busca sola en los puertos 8188 (portable) y 8000 (Desktop).'
      : `Arranca ComfyUI. La app lo busca en ${e.comfy.url} (config/ajustes.toml).`;
  }

  const m = e.modelo || {};
  const sinRuta = (nombre) => nombre.split(/[\\/]/).pop();
  const linea = [el('b', {}, '🎨 Modelo: '), sinRuta(m.modelo || 'el del workflow')];
  if (m.lora) linea.push(` + LoRA ${sinRuta(m.lora)} (fuerza ${m.fuerza})`);
  if (m.palabra_clave) linea.push(` · palabra clave «${m.palabra_clave}»`);
  $('modelo').replaceChildren(...linea);

  const ia = e.interprete || { activado: false };
  $('interprete').hidden = !ia.activado;
  if (ia.activado) {
    $('interprete').replaceChildren(el('span', { class: `punto ${ia.ok ? 'ok' : 'mal'}` }),
      el('b', {}, '🧠 Intérprete de ideas: '), ia.ok ? `listo (${ia.modelo})` : `${ia.detalle}. Las ideas se pintan tal cual.`);
  }

  $('n-cola').textContent = e.cola.length;
  $('n-media').textContent = e.media.toFixed(1);
  $('n-hechas').textContent = e.estadisticas.hechas;
  $('n-personas').textContent = e.estadisticas.personas;
  $('url').textContent = e.url_alumnado;
  if (e.url_alumnado !== urlQr) {
    urlQr = e.url_alumnado;
    $('qr').src = `/qr.svg?v=${encodeURIComponent(urlQr)}`;
  }
  pintarDirecciones(e);
  const red = e.internet || { activado: false };
  $('internet').hidden = !red.activado;
  if (red.activado) {
    $('internet').replaceChildren(el('span', { class: `punto ${red.listo ? 'ok' : 'mal'}` }),
      el('b', {}, '🌍 Por internet: '), red.listo
        ? 'listo. El público entra con sus datos móviles o con cualquier WiFi.'
        : `${red.detalle}. Mientras tanto, el QR usa la WiFi.`);
    if (red.listo) $('bloque-direccion').hidden = true;
  }
  $('codigo').textContent = e.codigo ? `Código del aula: ${e.codigo}` : 'Sin código de acceso';

  $('avisos').replaceChildren(...e.avisos.map((a) =>
    el('div', { class: 'aviso seccion' }, el('span', { class: 'icono' }, '⚠️'), el('span', {}, a))));

  pintarCola(e.cola);
  pintarBloqueados(e.bloqueados);
  pintarReto(e.reto);
  pintarConcurso(e.concurso);
  $('simulacro').hidden = !e.simulacro;
  document.title = e.por_revisar ? `(${e.por_revisar}) 🛂 Panel del profesor` : 'Panel del profesor';
}

// --- Revisión antes de publicar ---

let candidatas = [];
let concurso = null;

async function cargarRevision() {
  let r;
  try { r = await apiProfe('/api/panel/revision?limite=40'); } catch { return; }
  const firma = r.imagenes.map((t) => t.id).join('|');
  $('n-revision').textContent = r.total;
  $('seccion-revision').classList.toggle('vacia', !r.total);
  if (firma === $('revision').dataset.firma) return;
  $('revision').dataset.firma = firma;
  candidatas = r.imagenes;
  pintarRevision();
}

function pintarRevision() {
  $('publicar-todas').hidden = candidatas.length < 2;
  $('publicar-todas').textContent = `✅ Publicar las ${candidatas.length} que ves`;
  if (!candidatas.length) {
    $('revision').replaceChildren(el('div', { class: 'todo-revisado', style: { gridColumn: '1 / -1' } },
      el('span', {}, '✨'), el('span', {}, concurso && !concurso.revisar_antes
        ? 'Las imágenes nuevas se publican solas. Puedes retirarlas abajo, en «Imágenes creadas».'
        : 'Todo revisado. Las imágenes nuevas aparecerán aquí antes de salir en la pantalla.')));
    return;
  }
  $('revision').replaceChildren(...candidatas.map((t) =>
    el('div', { class: 'candidata' },
      el('img', { src: t.mini, alt: t.prompt, onclick: () => ampliar(t) }),
      el('div', { class: 'info' }, el('b', {}, t.alias),
        el('span', { title: t.prompt }, `${emojiTema(t.tema)}${emojiEstilo(t.estilo)} ${t.prompt}`),
        t.prompt_ia ? el('small', { class: 'ia', title: t.prompt_ia }, `🧠 ${t.prompt_ia}`) : null),
      el('div', { class: 'decidir' },
        el('button', { class: 'boton boton-si', type: 'button', onclick: () => revisar([t.id], 'aprobada') }, '✅ Publicar'),
        el('button', { class: 'boton boton-peligro', type: 'button', onclick: () => revisar([t.id], 'rechazada') }, '❌ Rechazar')),
      el('button', { class: 'pausar', type: 'button', onclick: () => rechazarYPausar(t) }, `🚫 Rechazar y pausar a ${t.alias}`))));
}

async function revisar(ids, decision) {
  candidatas = candidatas.filter((t) => !ids.includes(t.id));  // fuera de la bandeja al momento
  $('revision').dataset.firma = candidatas.map((t) => t.id).join('|');
  pintarRevision();
  imagenes.forEach((t) => { if (ids.includes(t.id)) t.revision = decision; });
  pintarImagenes();
  try {
    const r = await apiProfe('/api/panel/revisar', { metodo: 'POST', datos: { ids, decision } });
    $('n-revision').textContent = r.por_revisar;
    if (ids.length > 1) aviso(`✅ ${r.cambiadas} imágenes publicadas`);
  } catch (e) { aviso(e.message, true); }
  cargarRevision();
}

async function rechazarYPausar(t) {
  if (!confirm(`¿Rechazar esta imagen y pausar el acceso de "${t.alias}"? Se cancelarán sus imágenes en cola.`)) return;
  await revisar([t.id], 'rechazada');
  try {
    await apiProfe('/api/panel/bloquear', { metodo: 'POST', datos: { token: t.token, valor: true } });
    aviso(`${t.alias} está en pausa`);
    refrescarEstado();
  } catch (e) { aviso(e.message, true); }
}

$('publicar-todas').addEventListener('click', () => {
  if (!candidatas.length) return;
  if (!confirm(`¿Publicar las ${candidatas.length} imágenes de la bandeja? Comprueba antes que todas están bien.`)) return;
  revisar(candidatas.map((t) => t.id), 'aprobada');
});

$('revisar-antes').addEventListener('change', async (ev) => {
  const valor = ev.target.checked;
  if (!valor && !confirm('Sin revisión, las imágenes nuevas saldrán en la pantalla nada más crearse. ¿Seguro?')) {
    ev.target.checked = true;
    return;
  }
  try {
    pintarConcurso(await apiProfe('/api/panel/moderacion', { metodo: 'POST', datos: { valor } }));
    aviso(valor ? '🛂 Las imágenes nuevas esperarán tu aprobación' : 'Las imágenes nuevas se publicarán solas');
  } catch (e) { aviso(e.message, true); }
});

// --- Proyector ---

const NOTAS_VISTA = {
  mosaico: 'Las imágenes aprobadas van completando un mosaico gigante con forma de cartel. Se vota desde el móvil.',
  galeria: 'La última imagen en grande y las anteriores debajo. De vez en cuando, las más votadas.',
  podio: '🔒 Votación cerrada. Se ven las 3 más votadas. Vuelve al mosaico para reabrirla.',
};

function pintarConcurso(c) {
  const antes = concurso;
  concurso = c;
  document.querySelectorAll('[data-vista]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.vista === c.vista)));
  $('nota-vista').textContent = NOTAS_VISTA[c.vista] || '';
  if (document.activeElement !== $('revisar-antes')) $('revisar-antes').checked = c.revisar_antes;
  $('texto-revisar').textContent = c.revisar_antes ? 'Revisión antes de publicar: sí' : 'Revisión antes de publicar: no';
  $('nota-revision').textContent = c.revisar_antes
    ? 'Las imágenes nuevas esperan aquí. Solo salen en la pantalla, el mosaico y la galería cuando pulsas ✅ Publicar. Quien la crea la ve en su móvil.'
    : '⚠️ Sin revisión: las imágenes nuevas salen en la pantalla nada más crearse.';
  if (!antes || antes.revisar_antes !== c.revisar_antes) pintarRevision();
}

document.querySelectorAll('[data-vista]').forEach((b) => b.addEventListener('click', async () => {
  const vista = b.dataset.vista;
  if (concurso && vista === concurso.vista) return;
  if (vista === 'podio' && !confirm('¿Cerrar la votación y mostrar las ganadoras en el proyector?')) return;
  try {
    pintarConcurso(await apiProfe('/api/panel/proyector', { metodo: 'POST', datos: { vista } }));
    if (vista === 'podio') aviso('🏆 ¡Ganadoras en pantalla! La votación está cerrada.');
    else if (concurso && vista === 'mosaico') aviso('🧩 Mosaico en pantalla. La votación está abierta.');
  } catch (e) { aviso(e.message, true); }
}));

// --- Retos ---

const IDEAS_RETO = ['Tu disfraz soñado', 'Diseña el traje de la próxima reina', 'El taller de un artesano del carnaval',
  'Una máscara imposible', 'El carnaval en el espacio', 'Una carroza para CarnaLab'];
let finReto = null;

$('ideas-reto').replaceChildren(...IDEAS_RETO.map((idea) =>
  el('button', { type: 'button', onclick: () => ($('reto-titulo').value = idea) }, idea)));

const FASES = {
  creando: ['✏️ Creando', [['⏹ Terminar y votar', 'votando', 'boton-principal'], ['✕ Cancelar reto', 'cerrado', 'boton-peligro']]],
  votando: ['🗳️ Votando', [['🏆 Mostrar podio', 'podio', 'boton-principal'], ['✕ Cancelar reto', 'cerrado', 'boton-peligro']]],
  podio: ['🏆 Podio', [['✓ Cerrar reto y volver a la galería', 'cerrado', 'boton-principal']]],
};

function pintarReto(r) {
  $('reto-nuevo').hidden = !!r;
  $('reto-activo').hidden = !r;
  if (!r) { finReto = null; return; }
  const [nombreFase, acciones] = FASES[r.fase] || [r.fase, []];
  $('reto-nombre').textContent = `«${r.titulo}»`;
  $('reto-fase').textContent = nombreFase;
  $('reto-cuenta').textContent = `${r.imagenes} ${r.imagenes === 1 ? 'imagen participa' : 'imágenes participan'}`;
  finReto = r.fase === 'creando' && r.quedan != null ? Date.now() + r.quedan * 1000 : null;
  pintarRelojReto();
  const firma = r.fase;
  if ($('reto-acciones').dataset.firma !== firma) {
    $('reto-acciones').dataset.firma = firma;
    $('reto-acciones').replaceChildren(...acciones.map(([texto, fase, clase]) =>
      el('button', { class: `boton ${clase}`, type: 'button', onclick: () => cambiarFase(fase) }, texto)));
  }
}

function pintarRelojReto() {
  if (!finReto) { $('reto-reloj').textContent = ''; return; }
  const s = Math.max(0, Math.round((finReto - Date.now()) / 1000));
  $('reto-reloj').textContent = `⏱ ${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
setInterval(pintarRelojReto, 1000);

$('lanzar-reto').addEventListener('click', async () => {
  const titulo = $('reto-titulo').value.trim();
  if (!titulo) { aviso('Escribe el tema del reto', true); $('reto-titulo').focus(); return; }
  try {
    await apiProfe('/api/panel/reto', { metodo: 'POST', datos: { titulo, minutos: Number($('reto-minutos').value) } });
    $('reto-titulo').value = '';
    aviso('🏁 ¡Reto lanzado! Ya aparece en los móviles y en el proyector.');
    refrescarEstado();
  } catch (e) { aviso(e.message, true); }
});

async function cambiarFase(fase) {
  if (fase === 'cerrado' && !confirm('¿Cerrar el reto? Las imágenes se quedan en la galería.')) return;
  try {
    await apiProfe('/api/panel/reto/fase', { metodo: 'POST', datos: { fase } });
    refrescarEstado();
  } catch (e) { aviso(e.message, true); }
}

function pintarCola(cola) {
  if (!cola.length) {
    $('cola').replaceChildren(el('p', { class: 'vacio' }, 'No hay nadie esperando.'));
    return;
  }
  $('cola').replaceChildren(...cola.map((t, i) => {
    const generando = t.estado === 'generando';
    const progreso = generando && t.pasos ? Math.round((100 * t.paso) / t.pasos) : 0;
    return el('div', { class: 'fila' },
      el('div', { class: `pos ${generando ? 'ahora' : ''}` }, generando ? '🎨' : i),
      el('div', {},
        el('div', { class: 'quien' }, t.miniatura_estilo ? `🖼️ Miniatura · ${t.estilo}` : t.alias),
        el('div', { class: 'que' }, `${t.con_foto ? '📷 ' : ''}${emojiTema(t.tema)}${emojiEstilo(t.estilo)} ${t.prompt}`),
        generando ? el('div', { class: 'mini-barra' }, el('div', { style: { width: `${progreso}%` } })) : null),
      el('button', {
        class: 'boton boton-peligro icono-boton', type: 'button', title: 'Cancelar',
        onclick: () => cancelar(t.id),
      }, '✕ Cancelar'));
  }));
}

function pintarDirecciones(e) {
  const selector = $('direccion');
  $('bloque-direccion').hidden = e.direccion_fija || e.direcciones.length < 2;
  if (document.activeElement === selector) return;
  const opciones = e.direcciones.join('|');
  if (selector.dataset.opciones !== opciones) {
    selector.replaceChildren(...e.direcciones.map((d) => el('option', { value: d }, d)));
    selector.dataset.opciones = opciones;
  }
  selector.value = e.direccion;
}

$('direccion').addEventListener('change', async (ev) => {
  try {
    await apiProfe('/api/panel/direccion', { metodo: 'POST', datos: { direccion: ev.target.value } });
    ev.target.blur();
    await refrescarEstado();
    aviso('QR actualizado: vuelve a escanearlo con el móvil.');
  } catch (e) { aviso(e.message, true); }
});

function emojiEstilo(id) {
  const e = info && info.estilos.find((x) => x.id === id);
  return e ? e.emoji : '';
}

function emojiTema(id) {
  const t = id && info && info.temas.find((x) => x.id === id);
  return t ? `${t.emoji} ` : '';
}

function pintarBloqueados(lista) {
  $('seccion-bloqueados').hidden = !lista.length;
  $('bloqueados').replaceChildren(...lista.map((p) =>
    el('div', { class: 'fila', style: { gridTemplateColumns: '1fr auto' } },
      el('div', { class: 'quien' }, `🚫 ${p.alias}`),
      el('button', { class: 'boton boton-secundario icono-boton', type: 'button', onclick: () => bloquear(p.token, false, p.alias) },
        'Quitar pausa'))));
}

// --- Acciones ---

$('interruptor').addEventListener('click', async () => {
  if (!ultimoEstado) return;
  try {
    await apiProfe('/api/panel/abierto', { metodo: 'POST', datos: { valor: !ultimoEstado.abierto } });
    await refrescarEstado();
  } catch (e) { aviso(e.message, true); }
});

async function cancelar(id) {
  try {
    await apiProfe(`/api/panel/cancelar/${id}`, { metodo: 'POST' });
    aviso('Trabajo cancelado');
    refrescarEstado();
  } catch (e) { aviso(e.message, true); }
}

async function bloquear(token, valor, alias) {
  if (valor && !confirm(`¿Pausar el acceso de "${alias}"? Se cancelarán sus imágenes en cola.`)) return;
  try {
    await apiProfe('/api/panel/bloquear', { metodo: 'POST', datos: { token, valor } });
    aviso(valor ? `${alias} está en pausa` : `${alias} puede volver a crear`);
    refrescarEstado();
  } catch (e) { aviso(e.message, true); }
}

$('copiar').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(ultimoEstado.url_alumnado);
    aviso('Enlace copiado');
  } catch {
    aviso(ultimoEstado.url_alumnado);
  }
});

$('miniaturas').addEventListener('click', async () => {
  try {
    const r = await apiProfe('/api/panel/miniaturas', { metodo: 'POST' });
    aviso(`${r.encoladas} miniaturas en cola. Aparecerán solas en la pantalla del alumnado.`);
    refrescarEstado();
  } catch (e) { aviso(e.message, true); }
});

// --- Imágenes ---

async function cargarImagenes(reiniciar) {
  try {
    const nuevas = await apiProfe(`/api/panel/imagenes?limite=${PAGINA}`);
    if (reiniciar) {
      imagenes = nuevas;
      hayMas = nuevas.length === PAGINA;
    } else {
      const porId = new Map(nuevas.map((t) => [t.id, t]));
      imagenes = imagenes.map((t) => porId.get(t.id) || t);
      const conocidas = new Set(imagenes.map((t) => t.id));
      imagenes = nuevas.filter((t) => !conocidas.has(t.id)).concat(imagenes);
    }
    pintarImagenes();
  } catch { /* reintento en la próxima vuelta */ }
}

$('mas').addEventListener('click', async () => {
  const ultima = imagenes[imagenes.length - 1];
  if (!ultima) return;
  try {
    const mas = await apiProfe(`/api/panel/imagenes?limite=${PAGINA}&antes=${ultima.fin}`);
    imagenes = imagenes.concat(mas);
    hayMas = mas.length === PAGINA;
    pintarImagenes();
  } catch (e) { aviso(e.message, true); }
});

function pintarImagenes() {
  $('mas').hidden = !hayMas;
  if (!imagenes.length) {
    $('imagenes').replaceChildren(el('p', { class: 'vacio' }, 'Todavía no hay imágenes.'));
    return;
  }
  $('imagenes').replaceChildren(...imagenes.map((t) => {
    const publicada = t.revision === 'aprobada';
    const botones = t.revision === 'pendiente'
      ? [['✅ Publicar', 'aprobada', 'boton-si'], ['❌ Rechazar', 'rechazada', 'boton-peligro']]
      : publicada ? [['❌ Retirar', 'rechazada', 'boton-secundario']] : [['✅ Publicar', 'aprobada', 'boton-secundario']];
    return el('div', { class: `obra ${t.revision === 'rechazada' ? 'oculta' : ''}` },
      t.revision === 'rechazada' ? el('span', { class: 'etiqueta-oculta' }, '❌ Retirada') : null,
      t.revision === 'pendiente' && t.publico ? el('span', { class: 'etiqueta-pendiente' }, '⏳ Por revisar') : null,
      t.publico ? null : el('span', { class: 'etiqueta-privada' }, '🔒 Privada'),
      el('img', { src: t.mini, alt: t.prompt, loading: 'lazy', onclick: () => ampliar(t) }),
      el('div', { class: 'info' }, el('b', {}, `${t.alias}${t.votos ? ` · ❤️ ${t.votos}` : ''}`),
        el('span', { title: t.prompt }, `${emojiTema(t.tema)}${emojiEstilo(t.estilo)} ${t.prompt}`)),
      el('div', { class: 'acciones' },
        t.publico ? botones.map(([texto, decision, clase]) =>
          el('button', { class: `boton ${clase}`, type: 'button', onclick: () => revisar([t.id], decision) }, texto)) : null,
        t.revision === 'pendiente' && t.publico ? null
          : el('button', { class: 'boton boton-peligro', type: 'button', onclick: () => bloquear(t.token, true, t.alias) }, '🚫 Pausar')));
  }));
}

function ampliar(t) {
  const visor = el('div', { class: 'visor', onclick: () => visor.remove() },
    el('div', {}, el('img', { src: t.vista || t.imagen, alt: t.prompt }), el('p', {}, `${t.alias}: ${t.prompt}`),
      t.prompt_ia ? el('p', { class: 'ia' }, `🧠 Lo que entendió el intérprete: ${t.prompt_ia}`) : null));
  document.body.append(visor);
}

iniciar();
