// Pantalla del alumnado: entrar, crear, esperar turno, ver el resultado, la galería y votar.

const $ = (id) => document.getElementById(id);
const PANTALLAS = ['entrada', 'crear', 'espera', 'resultado', 'fallo'];
const FUERZAS = { poco: ['🙂', 'Un poco'], bastante: ['😮', 'Bastante'], mucho: ['🤯', 'Mucho'] };

const estado = {
  info: null,
  token: almacen.leer('estudio.token'),
  estilo: almacen.leer('estudio.estilo'),
  tema: almacen.leer('estudio.tema') || '',
  formato: almacen.leer('estudio.formato'),
  fuerza: almacen.leer('estudio.fuerza') || 'bastante',
  foto: null,          // { id, ancho, alto, vista }
  ultimoPedido: leerUltimoPedido(),
  trabajo: null,
  previewVersion: 0,
  sondeo: null,
  pestana: 'recientes',
  finReto: null,
  enRevision: new Set(),   // mis imágenes que esperan al jurado
  resultadoId: null,       // la que se ve en la pantalla de resultado
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
  pintarTarjetas();
  pintarFormatos();
  pintarFuerzas();
  pintarDetalles();
  pintarEstadoEstudio();
  pintarReto();
  $('usar-foto').hidden = !estado.info.fotos;

  if (estado.token) {
    try {
      const yo = await api('/api/yo', { cabeceras: cabeceras() });
      entrarCon(yo.alias);
      api('/api/mis-creaciones', { cabeceras: cabeceras() })
        .then((mias) => mias.filter((t) => t.publico && t.revision === 'pendiente').forEach((t) => vigilarRevision(t.id)))
        .catch(() => {});
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
  const { evento, subtitulo, congreso, centro, logo, cartel } = estado.info;
  document.title = `${subtitulo} · ${evento}`;
  document.querySelectorAll('[data-evento]').forEach((n) => (n.textContent = evento));
  document.querySelectorAll('[data-subtitulo]').forEach((n) => (n.textContent = subtitulo));
  document.querySelectorAll('[data-congreso]').forEach((n) => { n.textContent = congreso; n.hidden = !congreso; });
  for (const id of ['logo-entrada', 'logo-cabecera']) {
    $(id).hidden = !logo;
    if (logo) { $(id).src = logo; $(id).alt = centro || evento; }
  }
  $('pie-centro').hidden = !logo;
  $('cartel-entrada').hidden = !cartel;
  if (cartel) { $('cartel-entrada').src = cartel; $('cartel-entrada').alt = `Cartel de ${evento}`; }
  $('mascara').hidden = !!cartel;
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
  cerrarVelos();
  mostrarEntrada();
  if (mensaje) aviso(mensaje, true);
}

function entrarCon(alias) {
  $('saludo-alias').textContent = alias;
  if (estado.ultimoPedido && !$('prompt').value) $('prompt').value = estado.ultimoPedido.prompt;
  actualizarContador();
  mostrar('crear');
}

// --- Crear: estilos, temas, formatos ---

function tarjeta(e, seleccionada, alElegir) {
  const fondo = e.miniatura
    ? el('img', { src: e.miniatura, alt: '', loading: 'lazy' })
    : el('div', { class: 'fondo', style: { background: `linear-gradient(135deg, ${e.colores[0]}, ${e.colores[1]})` } }, e.emoji);
  return el('button', {
    class: 'estilo', type: 'button', 'aria-pressed': String(seleccionada), 'data-id': e.id, onclick: alElegir,
  }, fondo, el('span', { class: 'nombre' }, e.miniatura ? `${e.emoji} ${e.nombre}` : e.nombre));
}

function pintarTarjetas() {
  const { estilos, temas } = estado.info;
  if (!estilos.some((e) => e.id === estado.estilo)) estado.estilo = estilos[0].id;
  if (estado.tema && !temas.some((t) => t.id === estado.tema)) estado.tema = '';
  $('estilos').replaceChildren(...estilos.map((e) => tarjeta(e, e.id === estado.estilo, () => elegir('estilo', e.id))));
  $('bloque-temas').hidden = !temas.length;
  const ninguno = { id: '', nombre: 'Sin carnaval', emoji: '🌍', colores: ['#3b2a5c', '#1f1536'] };
  $('temas').replaceChildren(...[ninguno, ...temas].map((t) => tarjeta(t, t.id === estado.tema, () => elegir('tema', t.id))));
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

function pintarFuerzas() {
  const fuerzas = estado.info.fuerzas;
  if (!fuerzas.includes(estado.fuerza)) estado.fuerza = fuerzas[Math.floor(fuerzas.length / 2)];
  $('fuerzas').replaceChildren(...fuerzas.map((id) => {
    const [cara, nombre] = FUERZAS[id] || ['✨', id];
    return el('button', {
      class: 'formato', type: 'button', 'aria-pressed': String(id === estado.fuerza), 'data-id': id,
      onclick: () => elegir('fuerza', id),
    }, el('span', { class: 'cara' }, cara), nombre);
  }));
}

function elegir(tipo, id) {
  estado[tipo] = id;
  almacen.guardar(`estudio.${tipo}`, id);
  const contenedor = { estilo: 'estilos', tema: 'temas', formato: 'formatos', fuerza: 'fuerzas' }[tipo];
  $(contenedor).querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.id === id)));
}

// --- Detalles para enriquecer la idea ---

function pintarDetalles() {
  const grupos = estado.info.detalles || [];
  $('detalles').hidden = !grupos.length;
  $('grupos-detalles').replaceChildren(...grupos.map((g) =>
    el('div', { class: 'grupo-detalles' }, el('b', {}, g.grupo),
      el('div', { class: 'chips' }, g.opciones.map((frase) =>
        el('button', { class: 'chip-detalle', type: 'button', 'data-frase': frase, 'aria-pressed': 'false',
          onclick: () => alternarDetalle(frase) }, frase))))));
  marcarDetalles();
}

function alternarDetalle(frase) {
  const caja = $('prompt');
  let texto = caja.value.trim();
  if (texto.toLowerCase().includes(frase.toLowerCase())) {
    const patron = new RegExp(`,?\\s*${frase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i');
    texto = texto.replace(patron, '').replace(/^\s*,\s*/, '').trim();
  } else {
    texto = texto ? `${texto.replace(/[\s,.]+$/, '')}, ${frase}` : frase;
  }
  caja.value = texto.slice(0, caja.maxLength > 0 ? caja.maxLength : 400);
  actualizarContador();
}

function marcarDetalles() {
  const texto = $('prompt').value.toLowerCase();
  document.querySelectorAll('.chip-detalle').forEach((b) =>
    b.setAttribute('aria-pressed', String(texto.includes(b.dataset.frase.toLowerCase()))));
}

// --- Foto como base ---

$('usar-foto').addEventListener('click', () => $('archivo-foto').click());

$('archivo-foto').addEventListener('change', async (ev) => {
  const archivo = ev.target.files[0];
  ev.target.value = '';
  if (!archivo) return;
  $('usar-foto').disabled = true;
  $('foto-base').hidden = false;
  $('foto-mini').removeAttribute('src');
  $('foto-texto').textContent = 'Preparando tu foto…';
  try {
    const vista = await reducirFoto(archivo, 1536);
    const r = await api('/api/fotos', { metodo: 'POST', datos: { datos: vista }, cabeceras: cabeceras() });
    estado.foto = { ...r, vista };
  } catch (e) {
    if (e.estado === 401) return salir(e.message);
    estado.foto = null;
    aviso(e.message || 'No he podido leer esa foto.', true);
  } finally {
    $('usar-foto').disabled = false;
    pintarFoto();
  }
});

$('quitar-foto').addEventListener('click', () => {
  estado.foto = null;
  pintarFoto();
});

async function reducirFoto(archivo, maximo) {
  let fuente;
  try {
    fuente = await createImageBitmap(archivo, { imageOrientation: 'from-image' });
  } catch {
    fuente = await new Promise((ok, mal) => {
      const img = new Image();
      img.onload = () => ok(img);
      img.onerror = () => mal(new Error('No he podido leer esa foto. Prueba con otra.'));
      img.src = URL.createObjectURL(archivo);
    });
  }
  const escala = Math.min(1, maximo / Math.max(fuente.width, fuente.height));
  const lienzo = document.createElement('canvas');
  lienzo.width = Math.round(fuente.width * escala);
  lienzo.height = Math.round(fuente.height * escala);
  lienzo.getContext('2d').drawImage(fuente, 0, 0, lienzo.width, lienzo.height);
  return lienzo.toDataURL('image/jpeg', 0.88);
}

function pintarFoto() {
  const hay = !!estado.foto;
  $('foto-base').hidden = !hay;
  if (hay) {
    $('foto-mini').src = estado.foto.vista;
    $('foto-texto').textContent = 'La transformaremos según tu idea';
  }
  $('usar-foto').textContent = hay ? '📷 Cambiar foto' : '📷 Usar una foto';
  $('etiqueta-idea').textContent = hay ? '¿En qué convertimos tu foto?' : '¿Qué quieres crear?';
  $('prompt').placeholder = hay ? 'Ej.: conviérteme en un arlequín veneciano con máscara dorada' : 'Describe tu imagen…';
  $('bloque-formato').hidden = hay;
  $('bloque-fuerza').hidden = !hay;
}

// --- Estado del estudio y reto ---

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

function pintarReto() {
  const r = estado.info.reto;
  $('clase').querySelector('[data-pestana="reto"]').hidden = !r;
  if (!r) {
    estado.finReto = null;
    $('reto').replaceChildren(...bandaConcurso());
    return;
  }
  let contenido;
  if (r.fase === 'creando') {
    estado.finReto = r.quedan != null ? Date.now() + r.quedan * 1000 : null;
    contenido = [
      el('span', { class: 'icono' }, '🏁'),
      el('div', {}, `RETO: «${r.titulo}»`,
        el('small', {}, estado.finReto ? 'Lo que crees ahora participa. Quedan ' : 'Lo que crees ahora participa.',
          estado.finReto ? el('span', { class: 'reloj', id: 'reloj-reto' }, relojReto()) : null)),
    ];
  } else if (r.fase === 'votando') {
    estado.finReto = null;
    contenido = [
      el('span', { class: 'icono' }, '🗳️'),
      el('div', {}, `¡A votar el reto «${r.titulo}»!`, el('small', {}, 'Elige tus favoritas con ❤️')),
      el('button', { class: 'boton boton-principal', type: 'button', onclick: () => abrirVotar() }, '❤️ Votar'),
    ];
  } else {
    estado.finReto = null;
    contenido = [
      el('span', { class: 'icono' }, '🏆'),
      el('div', {}, `Podio del reto «${r.titulo}»`, el('small', {}, '¡Mira la pantalla del aula!')),
    ];
  }
  $('reto').replaceChildren(el('div', { class: 'reto' }, contenido));
}

function bandaConcurso() {
  const c = estado.info.concurso;
  if (!c || c.vista === 'galeria') return [];
  if (c.vista === 'podio') {
    return [el('div', { class: 'reto' }, el('span', { class: 'icono' }, '🏆'),
      el('div', {}, '¡Ya tenemos ganadoras!', el('small', {}, 'Mira la pantalla del aula')),
      el('button', { class: 'boton boton-secundario', type: 'button', onclick: () => abrirClase('votos') }, 'Ver'))];
  }
  return [el('div', { class: 'reto' }, el('span', { class: 'icono' }, '🧩'),
    el('div', {}, 'Concurso CarnaLab',
      el('small', {}, c.revisar_antes
        ? 'Si el jurado la aprueba, tu imagen entra en el mosaico de la pantalla.'
        : 'Tus imágenes entran en el mosaico de la pantalla.')),
    el('button', { class: 'boton boton-principal', type: 'button', onclick: () => abrirVotar() }, '❤️ Votar'))];
}

function relojReto() {
  const s = Math.max(0, Math.round((estado.finReto - Date.now()) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

setInterval(() => {
  if (!estado.finReto || !$('reloj-reto')) return;
  $('reloj-reto').textContent = relojReto();
  if (Date.now() > estado.finReto + 1500) refrescarInfo();
}, 1000);

async function refrescarInfo() {
  if (!estado.info) return;
  try {
    const info = await api('/api/info');
    const tarjetasCambiadas = JSON.stringify([info.estilos, info.temas]) !== JSON.stringify([estado.info.estilos, estado.info.temas]);
    estado.info = info;
    pintarEstadoEstudio();
    pintarReto();
    if (tarjetasCambiadas) pintarTarjetas();
  } catch { /* lo intentamos en la próxima vuelta */ }
}
setInterval(refrescarInfo, 8000);

function actualizarContador() {
  const max = estado.info ? estado.info.max_caracteres : 400;
  $('prompt').maxLength = max;
  $('contador').textContent = `${$('prompt').value.length}/${max}`;
  marcarDetalles();
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

// --- Enviar ---

$('boton-crear').addEventListener('click', () => crear());

function pedidoActual() {
  const pedido = { prompt: $('prompt').value.trim(), estilo: estado.estilo, tema: estado.tema || '', formato: estado.formato };
  if (estado.foto) {
    Object.assign(pedido, { foto: estado.foto.id, fuerza: estado.fuerza, publico: $('compartir').checked, vista: estado.foto.vista });
  }
  return pedido;
}

async function crear(pedido) {
  pedido = pedido || pedidoActual();
  if (pedido.prompt.length < 3) {
    aviso('Primero escribe qué quieres crear ✍️', true);
    mostrar('crear');
    return;
  }
  const botones = [$('boton-crear'), $('otra'), $('reintentar')];
  botones.forEach((b) => (b.disabled = true));
  const { vista, ...datos } = pedido;
  try {
    const trabajo = await api('/api/crear', { metodo: 'POST', datos, cabeceras: cabeceras() });
    estado.ultimoPedido = pedido;
    almacen.guardar('estudio.ultimo', JSON.stringify(datos));
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
    if (pedido.foto && /ya no está/i.test(e.message)) {
      estado.foto = null;
      pintarFoto();
    }
    mostrar('crear');
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
  votadorEspera.activar();
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
    $('resultado-privada').hidden = t.publico;
    estado.resultadoId = t.id;
    pintarRevision(t);
    if (t.publico && t.revision === 'pendiente') vigilarRevision(t.id);
    $('descargar').href = `${t.imagen}?descargar=1`;
    mostrar('resultado');
    confeti();
    if (navigator.vibrate) navigator.vibrate(80);
  };
  img.onerror = () => fallo('La imagen se ha creado pero no se ha podido descargar. Mírala en "Mías".');
  img.src = t.imagen;
}

const TEXTOS_REVISION = {
  pendiente: '⏳ El jurado está revisando tu imagen. Cuando la apruebe, entrará en el mosaico gigante de la pantalla.',
  aprobada: '✅ ¡Aprobada! Ya está en el mosaico de la pantalla y se puede votar.',
  rechazada: '🙈 Esta imagen no saldrá en la pantalla. ¡Prueba con otra idea!',
};

function pintarRevision(t) {
  const aviso = $('resultado-revision');
  const c = estado.info.concurso;
  const mostrar = t.publico && (t.revision !== 'aprobada' || (c && c.revisar_antes));
  aviso.hidden = !mostrar;
  if (!mostrar) return;
  aviso.className = `aviso-revision ${t.revision}`;
  aviso.textContent = TEXTOS_REVISION[t.revision] || '';
}

// Avisa cuando el jurado decide sobre mis imágenes, aunque esté creando otra
function vigilarRevision(id) {
  estado.enRevision.add(id);
  if (estado.enRevision.size === 1) setTimeout(comprobarRevision, 5000);
}

async function comprobarRevision() {
  if (!estado.enRevision.size) return;
  try {
    const mias = await api('/api/mis-creaciones', { cabeceras: cabeceras() });
    for (const t of mias) {
      if (!estado.enRevision.has(t.id) || t.revision === 'pendiente') continue;
      estado.enRevision.delete(t.id);
      if (estado.resultadoId === t.id && !$('resultado').hidden) pintarRevision(t);
      if (t.revision === 'aprobada') {
        aviso('🎉 ¡Tu imagen ya está en el mosaico de la pantalla!');
        if (navigator.vibrate) navigator.vibrate([60, 40, 60]);
      }
    }
  } catch (e) {
    if (e.estado === 401) { estado.enRevision.clear(); return; }
  }
  if (estado.enRevision.size) setTimeout(comprobarRevision, 5000);
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

// --- Galerías ---

function pieza(t, { votar = false } = {}) {
  const hijos = [
    el('button', { class: 'abrir', type: 'button', 'aria-label': t.prompt, onclick: () => abrirVisor(t) },
      el('img', { src: t.mini, alt: '', loading: 'lazy' })),
  ];
  if (votar) {
    hijos.push(el('span', { class: 'autor' }, t.alias));
    if (t.mia) hijos.push(el('span', { class: 'insignia' }, 'Tuya'));
    hijos.push(botonCorazon(t));
  } else {
    if (!t.publico) hijos.push(el('span', { class: 'insignia' }, '🔒 Privada'));
    else if (t.revision === 'pendiente') hijos.push(el('span', { class: 'insignia revision' }, '⏳ En revisión'));
    else if (t.revision === 'rechazada') hijos.push(el('span', { class: 'insignia revision' }, '🙈 No publicada'));
    if (t.votos) hijos.push(el('span', { class: 'corazon', 'aria-label': `${t.votos} votos` }, `❤️ ${t.votos}`));
  }
  return el('div', { class: 'pieza' }, hijos);
}

function botonCorazon(t, clase = 'corazon') {
  const boton = el('button', {
    class: clase, type: 'button', 'aria-pressed': String(!!t.votado), disabled: !!t.mia, 'data-trabajo': t.id,
    'aria-label': t.mia ? `Tu imagen tiene ${t.votos} votos` : (t.votado ? 'Quitar mi voto' : 'Votar esta imagen'),
    onclick: () => votar(t, boton),
  }, textoCorazon(t, clase));
  return boton;
}

function textoCorazon(t, clase) {
  if (clase === 'corazon') return `${t.votado ? '❤️' : '🤍'} ${t.votos}`;
  if (t.mia) return `❤️ ${t.votos} ${t.votos === 1 ? 'voto' : 'votos'} · es tuya`;
  return t.votado ? `❤️ Te gusta · ${t.votos}` : `🤍 Me gusta · ${t.votos}`;
}

async function votar(t, boton) {
  if (t.mia) return;
  const nuevo = !t.votado;
  t.votado = nuevo;
  t.votos += nuevo ? 1 : -1;
  repintarCorazones(t);
  boton.classList.remove('late');
  void boton.offsetWidth;
  if (nuevo) boton.classList.add('late');
  try {
    const r = await api(`/api/trabajos/${t.id}/voto`, { metodo: 'POST', datos: { valor: nuevo }, cabeceras: cabeceras() });
    t.votos = r.votos;
  } catch (e) {
    t.votado = !nuevo;
    t.votos += nuevo ? -1 : 1;
    if (e.estado === 401) return salir(e.message);
    aviso(e.message, true);
  }
  repintarCorazones(t);
}

function repintarCorazones(t) {
  document.querySelectorAll(`[data-trabajo="${t.id}"]`).forEach((b) => {
    b.setAttribute('aria-pressed', String(!!t.votado));
    b.textContent = textoCorazon(t, b.classList.contains('corazon') ? 'corazon' : 'grande');
  });
}

// Mis imágenes
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
    $('rejilla').replaceChildren(...lista.map((t) => pieza(t)));
  } catch (e) {
    if (e.estado === 401) return salir(e.message);
    aviso(e.message, true);
  }
});
$('cerrar-galeria').addEventListener('click', () => ($('galeria').hidden = true));

// Galería de la clase
let sondeoClase = null;

$('abrir-votar').addEventListener('click', () => abrirVotar());
$('cerrar-clase').addEventListener('click', () => {
  $('clase').hidden = true;
  clearInterval(sondeoClase);
});
document.querySelectorAll('[data-pestana]').forEach((b) =>
  b.addEventListener('click', () => abrirClase(b.dataset.pestana)));

function abrirClase(pestana = estado.pestana) {
  if (pestana !== estado.pestana) listaClase = [];
  estado.pestana = pestana;
  document.querySelectorAll('[data-pestana]').forEach((b) =>
    b.setAttribute('aria-selected', String(b.dataset.pestana === pestana)));
  if ($('clase').hidden) $('rejilla-clase').replaceChildren(el('p', { class: 'vacio', style: { gridColumn: '1 / -1' } }, 'Cargando…'));
  $('clase').hidden = false;
  cargarClase();
  clearInterval(sondeoClase);
  sondeoClase = setInterval(cargarClase, 8000);
}

const PAGINA_CLASE = 60;
let listaClase = [];

function consultaClase(pestana) {
  return pestana === 'reto' ? 'ambito=reto&orden=votos' : pestana === 'votos' ? 'orden=votos' : 'orden=recientes';
}

async function cargarClase() {
  const pestana = estado.pestana;
  try {
    const g = await api(`/api/galeria?limite=${PAGINA_CLASE}&${consultaClase(pestana)}`, { cabeceras: cabeceras() });
    if (pestana !== estado.pestana || $('clase').hidden) return;
    $('nota-clase').textContent = g.concurso && !g.concurso.votacion_abierta
      ? '🔒 La votación está cerrada: ¡mira las ganadoras en la pantalla!'
      : 'Dale ❤️ a tus favoritas. Las más votadas salen en la pantalla.';
    let lista = g.imagenes;
    if (pestana === 'recientes' && listaClase.length > lista.length && lista.length) {
      // Conserva las que ya se habían cargado con "Ver más"
      const ultima = lista[lista.length - 1].fin;
      const ids = new Set(lista.map((t) => t.id));
      lista = lista.concat(listaClase.filter((t) => !ids.has(t.id) && t.fin < ultima));
    }
    pintarClase(lista, pestana, g.imagenes.length === PAGINA_CLASE);
  } catch (e) {
    if (e.estado === 401) return salir(e.message);
  }
}

function pintarClase(lista, pestana, hayMas) {
  listaClase = lista;
  $('mas-clase').hidden = !(pestana === 'recientes' && hayMas);
  if (!lista.length) {
    $('rejilla-clase').replaceChildren(el('div', { class: 'vacio', style: { gridColumn: '1 / -1' } },
      el('div', {}, pestana === 'reto' ? '🏁' : '🌟'),
      pestana === 'reto' ? 'Todavía no hay imágenes en este reto.' : 'Todavía no hay imágenes en la galería.'));
    return;
  }
  $('rejilla-clase').replaceChildren(...lista.map((t) => pieza(t, { votar: true })));
}

$('mas-clase').addEventListener('click', async () => {
  const ultima = listaClase[listaClase.length - 1];
  if (!ultima) return;
  try {
    const g = await api(`/api/galeria?limite=${PAGINA_CLASE}&orden=recientes&antes=${ultima.fin}`, { cabeceras: cabeceras() });
    if (estado.pestana !== 'recientes') return;
    pintarClase(listaClase.concat(g.imagenes), 'recientes', g.imagenes.length === PAGINA_CLASE);
  } catch (e) { aviso(e.message, true); }
});

// --- Votar de una en una ---
// Tarjetas grandes: deslizar a la derecha (o tocar dos veces) = me gusta; a la izquierda = otra.
// Están en su propia pantalla y también en la de espera, para votar mientras llega tu turno.

const saltadas = new Set();   // las que esta persona ha pasado sin votar (no vuelven hasta que lo pida)

function contarVoto() {
  const clave = `estudio.votos.${estado.token}`;
  const n = Number(almacen.leer(clave) || 0) + 1;
  almacen.guardar(clave, String(n));
  return n;
}

function votosDados() {
  return Number(almacen.leer(`estudio.votos.${estado.token}`) || 0);
}

class Votador {
  constructor(caja) {
    this.caja = caja;
    this.lista = [];
    this.actual = null;
    this.abierta = true;
    this.cargada = 0;
    this.ocupado = false;
  }

  async activar() {
    if (this.actual && this.caja.querySelector('.carta')) return;
    await this.cargar();
    this.siguiente();
  }

  async cargar() {
    const r = estado.info && estado.info.reto;
    const ambito = r && r.fase === 'votando' ? 'reto' : 'todo';
    try {
      const datos = await api(`/api/votar?ambito=${ambito}`, { cabeceras: cabeceras() });
      this.abierta = datos.abierta;
      this.total = datos.imagenes.length;
      this.lista = datos.imagenes.filter((t) => !saltadas.has(t.id));
      this.cargada = Date.now();
    } catch (e) {
      if (e.estado === 401) return salir(e.message);
    }
  }

  async siguiente() {
    this.actual = this.lista.shift() || null;
    if (!this.actual && Date.now() - this.cargada > 4000) {  // se acabaron: ¿han llegado nuevas?
      await this.cargar();
      this.actual = this.lista.shift() || null;
    }
    this.pintar();
    if (this.lista[0]) new Image().src = this.lista[0].mini;  // la siguiente, ya cargada
  }

  pintar() {
    if (!this.abierta) {
      return this.caja.replaceChildren(el('div', { class: 'votar-vacio' }, el('div', {}, '🔒'),
        'La votación está cerrada: ¡mira las ganadoras en la pantalla!'));
    }
    const t = this.actual;
    if (!t) {
      const vacio = this.total
        ? [el('div', {}, '🎉'), '¡Las has visto todas! Vuelve en un rato: siempre llegan nuevas.',
            el('button', { class: 'boton boton-secundario', type: 'button', onclick: () => { saltadas.clear(); this.activar(); } },
              '🔁 Ver otra vez las que pasé')]
        : [el('div', {}, '🎨'), 'Todavía no hay imágenes para votar. ¡Vuelve en un rato!'];
      this.caja.replaceChildren(el('div', { class: 'votar-vacio' }, vacio));
      clearTimeout(this.reintento);
      this.reintento = setTimeout(() => { if (!this.actual && !this.caja.closest('[hidden]')) this.activar(); }, 10000);
      return;
    }
    const carta = el('div', { class: 'carta', role: 'img', 'aria-label': `${t.alias}: ${t.prompt}` },
      el('img', { src: t.mini, alt: '' }),
      el('div', { class: 'pie-carta' }, el('b', {}, `🎨 ${t.alias}`), el('span', {}, t.prompt)),
      el('div', { class: 'sello sello-si' }, '❤️'),
      el('div', { class: 'sello sello-no' }, '⏭'));
    this.arrastre(carta);
    const n = votosDados();
    this.caja.replaceChildren(carta,
      el('div', { class: 'votar-botones' },
        el('button', { class: 'boton boton-secundario', type: 'button', onclick: () => this.saltar() }, '⏭ Otra'),
        el('button', { class: 'boton boton-principal', type: 'button', onclick: () => this.megusta() }, '❤️ Me gusta')),
      el('p', { class: 'votar-cuenta' }, n ? `Has dado ${n} ❤️` : 'Dale ❤️ a las que más te gusten'));
  }

  arrastre(carta) {
    let x0 = null;
    let dx = 0;
    let ultimoToque = 0;
    const sellos = () => {
      carta.querySelector('.sello-si').style.opacity = Math.max(0, Math.min(1, dx / 90));
      carta.querySelector('.sello-no').style.opacity = Math.max(0, Math.min(1, -dx / 90));
    };
    carta.addEventListener('pointerdown', (ev) => {
      x0 = ev.clientX;
      dx = 0;
      carta.classList.add('arrastrando');
      carta.setPointerCapture(ev.pointerId);
    });
    carta.addEventListener('pointermove', (ev) => {
      if (x0 === null) return;
      dx = ev.clientX - x0;
      carta.style.transform = `translateX(${dx}px) rotate(${dx / 18}deg)`;
      sellos();
    });
    const soltar = () => {
      if (x0 === null) return;
      x0 = null;
      carta.classList.remove('arrastrando');
      if (dx > 90) return this.megusta();
      if (dx < -90) return this.saltar();
      if (Math.abs(dx) < 8) {  // un toque: dos seguidos = me gusta
        if (Date.now() - ultimoToque < 350) return this.megusta();
        ultimoToque = Date.now();
      }
      dx = 0;
      carta.style.transform = '';
      sellos();
    };
    carta.addEventListener('pointerup', soltar);
    carta.addEventListener('pointercancel', soltar);
  }

  irse(direccion) {
    const carta = this.caja.querySelector('.carta');
    if (!carta) return Promise.resolve();
    carta.style.transform = `translateX(${direccion * 130}%) rotate(${direccion * 18}deg)`;
    carta.style.opacity = '0';
    return new Promise((fin) => setTimeout(fin, 260));
  }

  async megusta() {
    const t = this.actual;
    if (!t || this.ocupado) return;
    this.ocupado = true;
    const carta = this.caja.querySelector('.carta');
    if (carta) carta.append(el('div', { class: 'corazon-grande' }, '❤️'));
    if (navigator.vibrate) navigator.vibrate(30);
    try {
      await api(`/api/trabajos/${t.id}/voto`, { metodo: 'POST', datos: { valor: true }, cabeceras: cabeceras() });
      contarVoto();
    } catch (e) {
      if (e.estado === 401) return salir(e.message);
      if (e.estado === 423) this.abierta = false;
      else aviso(e.message, true);
    }
    await new Promise((fin) => setTimeout(fin, 350));
    await this.irse(1);
    this.ocupado = false;
    this.siguiente();
  }

  async saltar() {
    const t = this.actual;
    if (!t || this.ocupado) return;
    saltadas.add(t.id);
    this.ocupado = true;
    await this.irse(-1);
    this.ocupado = false;
    this.siguiente();
  }
}

const votadorGrande = new Votador($('votador-grande'));
const votadorEspera = new Votador($('votador-espera'));

function abrirVotar() {
  cerrarVelos();
  $('votar').hidden = false;
  votadorGrande.actual = null;
  votadorGrande.activar();
}

$('cerrar-votar').addEventListener('click', () => ($('votar').hidden = true));
$('votar-galeria').addEventListener('click', () => {
  $('votar').hidden = true;
  abrirClase('recientes');
});
$('resultado-votar').addEventListener('click', () => abrirVotar());

// Visor
function abrirVisor(t) {
  $('visor-img').src = t.imagen;
  $('visor-img').alt = t.prompt;
  $('visor-idea').textContent = t.prompt;
  $('visor-autor').textContent = t.mia ? '' : `🎨 ${t.alias}`;
  $('visor-descargar').href = `${t.imagen}?descargar=1`;
  const voto = $('visor-voto');
  voto.hidden = !t.publico || t.revision !== 'aprobada';  // solo se votan las que están en la galería
  if (!voto.hidden) {
    const nuevo = botonCorazon(t, 'boton boton-secundario boton-grande voto-grande');
    nuevo.id = 'visor-voto';
    voto.replaceWith(nuevo);
  }
  $('visor-usar').onclick = () => {
    $('prompt').value = t.prompt;
    actualizarContador();
    if (estado.info.estilos.some((e) => e.id === t.estilo)) elegir('estilo', t.estilo);
    elegir('tema', estado.info.temas.some((x) => x.id === t.tema) ? t.tema : '');
    if (estado.info.formatos.some((f) => f.id === t.formato)) elegir('formato', t.formato);
    cerrarVelos();
    if (!estado.trabajo) mostrar('crear');
  };
  $('visor').hidden = false;
}
$('cerrar-visor').addEventListener('click', () => ($('visor').hidden = true));

function cerrarVelos() {
  for (const id of ['visor', 'galeria', 'clase', 'votar']) $(id).hidden = true;
  clearInterval(sondeoClase);
}

document.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Escape') return;
  const abierto = ['visor', 'galeria', 'clase', 'votar'].find((id) => !$(id).hidden);
  if (abierto) $(abierto).hidden = true;
  if (abierto === 'clase') clearInterval(sondeoClase);
});

iniciar();
