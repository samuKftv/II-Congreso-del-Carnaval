// Pantalla del alumnado: entrar, crear, esperar turno y ver el resultado.

const $ = (id) => document.getElementById(id);
const PANTALLAS = ['entrada', 'crear', 'espera', 'resultado', 'fallo'];

const estado = {
  info: null,
  token: almacen.leer('estudio.token'),
  estilo: almacen.leer('estudio.estilo'),
  formato: almacen.leer('estudio.formato'),
  ultimoPedido: leerUltimoPedido(),
  trabajo: null,
  previewVersion: 0,
  sondeo: null,
};

function leerUltimoPedido() {
  try { return JSON.parse(almacen.leer('estudio.ultimo')) || null; } catch { return null; }
}

function cabeceras() {
  return { 'X-Token': estado.token || '' };
}

function mostrar(pantalla) {
  for (const p of PANTALLAS) $(p).hidden = p !== pantalla;
  window.scrollTo({ top: 0 });
}

// --- Arranque ---

async function iniciar() {
  const codigoUrl = new URLSearchParams(location.search).get('c');
  if (codigoUrl) almacen.guardar('estudio.codigo', codigoUrl);

  try {
    estado.info = await api('/api/info');
  } catch (e) {
    aviso(e.message, true);
    setTimeout(iniciar, 3000);
    return;
  }
  pintarMarca();
  pintarEstilos();
  pintarFormatos();
  pintarEstadoEstudio();

  if (estado.token) {
    try {
      const yo = await api('/api/yo', { cabeceras: cabeceras() });
      entrarCon(yo.alias);
      if (yo.activos.length) esperar(yo.activos[0]);
      return;
    } catch (e) {
      if (e.estado !== 401) { aviso(e.message, true); setTimeout(iniciar, 3000); return; }
      olvidarSesion();
    }
  }
  mostrarEntrada();
}

function pintarMarca() {
  const { evento, subtitulo } = estado.info;
  document.title = `${subtitulo} · ${evento}`;
  document.querySelectorAll('[data-evento]').forEach((n) => (n.textContent = evento));
  document.querySelectorAll('[data-subtitulo]').forEach((n) => (n.textContent = subtitulo));
}

// --- Entrada ---

function mostrarEntrada() {
  const codigo = almacen.leer('estudio.codigo');
  $('bloque-codigo').hidden = !estado.info.requiere_codigo || !!codigo;
  $('codigo').value = codigo || '';
  $('alias').value = almacen.leer('estudio.alias') || '';
  mostrar('entrada');
}

$('form-entrada').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const boton = ev.submitter || ev.target.querySelector('button');
  boton.disabled = true;
  try {
    const r = await api('/api/entrar', {
      metodo: 'POST',
      datos: { alias: $('alias').value, codigo: $('codigo').value || almacen.leer('estudio.codigo') || '' },
    });
    estado.token = r.token;
    almacen.guardar('estudio.token', r.token);
    almacen.guardar('estudio.alias', r.alias);
    entrarCon(r.alias);
    confeti(50);
  } catch (e) {
    if (e.estado === 403) {
      almacen.guardar('estudio.codigo', null);
      $('bloque-codigo').hidden = false;
      $('codigo').focus();
    }
    aviso(e.message, true);
  } finally {
    boton.disabled = false;
  }
});

function olvidarSesion() {
  estado.token = null;
  almacen.guardar('estudio.token', null);
}

function salir(mensaje) {
  clearTimeout(estado.sondeo);
  olvidarSesion();
  mostrarEntrada();
  if (mensaje) aviso(mensaje, true);
}

function entrarCon(alias) {
  $('saludo-alias').textContent = alias;
  if (estado.ultimoPedido && !$('prompt').value) $('prompt').value = estado.ultimoPedido.prompt;
  actualizarContador();
  mostrar('crear');
}

// --- Crear ---

function pintarEstilos() {
  const contenedor = $('estilos');
  const estilos = estado.info.estilos;
  if (!estilos.some((e) => e.id === estado.estilo)) estado.estilo = estilos[0].id;
  contenedor.replaceChildren(...estilos.map((e) => {
    const fondo = e.miniatura
      ? el('img', { src: e.miniatura, alt: '', loading: 'lazy' })
      : el('div', { class: 'fondo', style: { background: `linear-gradient(135deg, ${e.colores[0]}, ${e.colores[1]})` } }, e.emoji);
    return el('button', {
      class: 'estilo', type: 'button', 'aria-pressed': String(e.id === estado.estilo), 'data-id': e.id,
      onclick: () => elegir('estilo', e.id),
    }, fondo, el('span', { class: 'nombre' }, e.miniatura ? `${e.emoji} ${e.nombre}` : e.nombre));
  }));
}

function pintarFormatos() {
  const formatos = estado.info.formatos;
  if (!formatos.some((f) => f.id === estado.formato)) estado.formato = formatos[0].id;
  $('formatos').replaceChildren(...formatos.map((f) => {
    const lado = 38 / Math.max(f.ancho, f.alto);
    const forma = el('span', { class: 'marco' },
      el('span', { class: 'forma', style: { width: `${f.ancho * lado}px`, height: `${f.alto * lado}px` } }));
    return el('button', {
      class: 'formato', type: 'button', 'aria-pressed': String(f.id === estado.formato), 'data-id': f.id,
      onclick: () => elegir('formato', f.id),
    }, forma, nombreFormato(f.id));
  }));
}

function elegir(tipo, id) {
  estado[tipo] = id;
  almacen.guardar(`estudio.${tipo}`, id);
  const contenedor = tipo === 'estilo' ? $('estilos') : $('formatos');
  contenedor.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.id === id)));
}

function pintarEstadoEstudio() {
  const { abierto, comfy_ok, en_cola, media } = estado.info;
  let caja;
  if (!abierto) {
    caja = el('div', { class: 'aviso aviso-rojo' }, el('span', { class: 'icono' }, '🌙'),
      el('span', {}, 'El estudio está cerrado ahora mismo. Ve pensando tu idea: aquí verás cuándo abre.'));
  } else if (!comfy_ok) {
    caja = el('div', { class: 'aviso' }, el('span', { class: 'icono' }, '🔌'),
      el('span', {}, 'El ordenador de render se está preparando. Puedes enviar tu idea y esperará su turno.'));
  } else if (en_cola > 0) {
    caja = el('div', { class: 'aviso aviso-info' }, el('span', { class: 'icono' }, '⏳'),
      el('span', {}, `Hay ${en_cola} ${en_cola === 1 ? 'imagen' : 'imágenes'} en cola · cada una tarda unos ${tiempoLegible(media)}.`));
  } else {
    caja = el('div', { class: 'aviso aviso-info' }, el('span', { class: 'icono' }, '🟢'),
      el('span', {}, '¡Estudio abierto y sin cola! Tu imagen saldrá enseguida.'));
  }
  $('estado-estudio').replaceChildren(caja);
  $('boton-crear').disabled = !abierto;
}

async function refrescarInfo() {
  if ($('crear').hidden) return;
  try {
    const info = await api('/api/info');
    const miniaturasCambiadas = JSON.stringify(info.estilos) !== JSON.stringify(estado.info.estilos);
    estado.info = info;
    pintarEstadoEstudio();
    if (miniaturasCambiadas) pintarEstilos();
  } catch { /* lo intentamos en la próxima vuelta */ }
}
setInterval(refrescarInfo, 8000);

function actualizarContador() {
  const max = estado.info ? estado.info.max_caracteres : 400;
  $('prompt').maxLength = max;
  $('contador').textContent = `${$('prompt').value.length}/${max}`;
}
$('prompt').addEventListener('input', actualizarContador);

$('inspirame').addEventListener('click', () => {
  const ideas = estado.info.ideas.filter((i) => i !== $('prompt').value);
  if (!ideas.length) return;
  const idea = ideas[Math.floor(Math.random() * ideas.length)];
  const caja = $('prompt');
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    caja.value = idea;
    actualizarContador();
    return;
  }
  let i = 0;
  clearInterval(caja._escribiendo);
  caja._escribiendo = setInterval(() => {
    caja.value = idea.slice(0, ++i);
    actualizarContador();
    if (i >= idea.length) clearInterval(caja._escribiendo);
  }, 18);
});

$('boton-crear').addEventListener('click', () => crear());

async function crear(pedido) {
  pedido = pedido || { prompt: $('prompt').value.trim(), estilo: estado.estilo, formato: estado.formato };
  if (pedido.prompt.length < 3) {
    aviso('Primero escribe qué quieres crear ✍️', true);
    mostrar('crear');
    return;
  }
  const botones = [$('boton-crear'), $('otra'), $('reintentar')];
  botones.forEach((b) => (b.disabled = true));
  try {
    const trabajo = await api('/api/crear', { metodo: 'POST', datos: pedido, cabeceras: cabeceras() });
    estado.ultimoPedido = pedido;
    almacen.guardar('estudio.ultimo', JSON.stringify(pedido));
    esperar(trabajo);
  } catch (e) {
    if (e.estado === 401) return salir(e.message);
    if (e.estado === 409 && e.cuerpo && e.cuerpo.id) {
      aviso(e.message);
      return esperar({ id: e.cuerpo.id, estado: 'cola', prompt: pedido.prompt });
    }
    if (e.estado === 423) {
      estado.info.abierto = false;
      pintarEstadoEstudio();
    }
    aviso(e.message, true);
  } finally {
    botones.forEach((b) => (b.disabled = false));
    if (estado.info && !estado.info.abierto) $('boton-crear').disabled = true;
  }
}

// --- Espera ---

function esperar(trabajo) {
  estado.trabajo = trabajo;
  estado.previewVersion = 0;
  $('espera-idea').textContent = trabajo.prompt || '';
  $('preview').hidden = true;
  $('preview').removeAttribute('src');
  $('lienzo').style.aspectRatio = trabajo.ancho && trabajo.alto ? `${trabajo.ancho} / ${trabajo.alto}` : '1';
  pintarEspera(trabajo);
  mostrar('espera');
  clearTimeout(estado.sondeo);
  sondear();
}

async function sondear() {
  const actual = estado.trabajo;
  if (!actual) return;
  try {
    const t = await api(`/api/trabajos/${actual.id}`, { cabeceras: cabeceras() });
    if (!estado.trabajo || estado.trabajo.id !== t.id) return;
    estado.trabajo = t;
    if (t.estado === 'hecho') return terminar(t);
    if (t.estado === 'error') return fallo(t.error);
    if (t.estado === 'cancelado') {
      estado.trabajo = null;
      aviso('Tu imagen se ha cancelado.');
      return mostrar('crear');
    }
    pintarEspera(t);
  } catch (e) {
    if (e.estado === 401) return salir(e.message);
    if (e.estado === 404) { estado.trabajo = null; return mostrar('crear'); }
    // Sin conexión: seguimos intentándolo.
  }
  estado.sondeo = setTimeout(sondear, 1000);
}

function pintarEspera(t) {
  const generando = t.estado === 'generando';
  $('espera-cola').hidden = generando;
  $('espera-generando').hidden = !generando;
  if (t.ancho && t.alto) $('lienzo').style.aspectRatio = `${t.ancho} / ${t.alto}`;
  if (t.prompt) $('espera-idea').textContent = t.prompt;

  if (!generando) {
    const delante = t.delante ?? 0;
    $('delante').textContent = delante;
    $('espera-titulo').textContent =
      delante === 0 ? '¡Eres la siguiente persona!' : delante === 1 ? '¡Solo queda una persona!' : '¡Ya queda menos!';
    $('espera-tiempo').textContent = t.comfy_ok === false
      ? 'Esperando a que el ordenador de render esté listo…'
      : t.segundos ? `Tu imagen estará lista en unos ${tiempoLegible(t.segundos)}` : '';
    return;
  }

  const fraccion = t.pasos ? t.paso / t.pasos : 0;
  $('barra').style.width = `${Math.max(4, Math.round(fraccion * 100))}%`;
  $('espera-paso').textContent = t.pasos ? `Paso ${t.paso} de ${t.pasos}` : 'Preparando el lienzo…';
  $('preview').style.filter = `blur(${Math.round((1 - fraccion) * 8)}px) saturate(1.2)`;
  if (t.preview && t.preview !== estado.previewVersion) {
    estado.previewVersion = t.preview;
    const img = new Image();
    img.onload = () => {
      $('preview').src = img.src;
      $('preview').hidden = false;
    };
    img.src = `/img/${t.id}/preview?v=${t.preview}`;
  }
}

$('cancelar').addEventListener('click', async () => {
  const t = estado.trabajo;
  if (!t) return mostrar('crear');
  clearTimeout(estado.sondeo);
  estado.trabajo = null;
  try { await api(`/api/trabajos/${t.id}/cancelar`, { metodo: 'POST', cabeceras: cabeceras() }); } catch { /* da igual */ }
  aviso('Imagen cancelada.');
  mostrar('crear');
});

// --- Resultado ---

function terminar(t) {
  estado.trabajo = null;
  const img = new Image();
  img.onload = () => {
    $('obra').src = img.src;
    $('obra').alt = t.prompt;
    $('resultado-idea').textContent = t.prompt;
    $('descargar').href = `${t.imagen}?descargar=1`;
    mostrar('resultado');
    confeti();
    if (navigator.vibrate) navigator.vibrate(80);
  };
  img.onerror = () => fallo('La imagen se ha creado pero no se ha podido descargar. Mírala en "Mis imágenes".');
  img.src = t.imagen;
}

function fallo(mensaje) {
  estado.trabajo = null;
  $('fallo-texto').textContent = mensaje || 'Algo ha fallado en el ordenador de render.';
  mostrar('fallo');
}

$('otra').addEventListener('click', () => crear(estado.ultimoPedido));
$('reintentar').addEventListener('click', () => crear(estado.ultimoPedido));
$('editar').addEventListener('click', () => mostrar('crear'));
$('volver').addEventListener('click', () => mostrar('crear'));

// --- Mis imágenes ---

$('abrir-galeria').addEventListener('click', async () => {
  $('galeria').hidden = false;
  $('rejilla').replaceChildren(el('p', { class: 'vacio', style: { gridColumn: '1 / -1' } }, 'Cargando…'));
  try {
    const lista = await api('/api/mis-creaciones', { cabeceras: cabeceras() });
    if (!lista.length) {
      $('rejilla').replaceChildren(el('div', { class: 'vacio', style: { gridColumn: '1 / -1' } },
        el('div', {}, '🎨'), 'Aún no has creado ninguna imagen. ¡Estrena el estudio!'));
      return;
    }
    $('rejilla').replaceChildren(...lista.map((t) =>
      el('button', { type: 'button', 'aria-label': t.prompt, onclick: () => abrirVisor(t) },
        el('img', { src: t.mini, alt: '', loading: 'lazy' }))));
  } catch (e) {
    if (e.estado === 401) { $('galeria').hidden = true; return salir(e.message); }
    aviso(e.message, true);
  }
});
$('cerrar-galeria').addEventListener('click', () => ($('galeria').hidden = true));

function abrirVisor(t) {
  $('visor-img').src = t.imagen;
  $('visor-img').alt = t.prompt;
  $('visor-idea').textContent = t.prompt;
  $('visor-descargar').href = `${t.imagen}?descargar=1`;
  $('visor-usar').onclick = () => {
    $('prompt').value = t.prompt;
    actualizarContador();
    if (estado.info.estilos.some((e) => e.id === t.estilo)) elegir('estilo', t.estilo);
    if (estado.info.formatos.some((f) => f.id === t.formato)) elegir('formato', t.formato);
    $('visor').hidden = true;
    $('galeria').hidden = true;
    if (!estado.trabajo) mostrar('crear');
  };
  $('visor').hidden = false;
}
$('cerrar-visor').addEventListener('click', () => ($('visor').hidden = true));

document.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Escape') return;
  if (!$('visor').hidden) $('visor').hidden = true;
  else if (!$('galeria').hidden) $('galeria').hidden = true;
});

iniciar();
