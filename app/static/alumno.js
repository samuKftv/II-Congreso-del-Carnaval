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
    $('reto').replaceChildren();
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
      el('button', { class: 'boton boton-principal', type: 'button', onclick: () => abrirClase('reto') }, 'Votar'),
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
    $('descargar').href = `${t.imagen}?descargar=1`;
    mostrar('resultado');
    confeti();
    if (navigator.vibrate) navigator.vibrate(80);
  };
  img.onerror = () => fallo('La imagen se ha creado pero no se ha podido descargar. Mírala en "Mías".');
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

$('abrir-clase').addEventListener('click', () => abrirClase());
$('cerrar-clase').addEventListener('click', () => {
  $('clase').hidden = true;
  clearInterval(sondeoClase);
});
document.querySelectorAll('[data-pestana]').forEach((b) =>
  b.addEventListener('click', () => abrirClase(b.dataset.pestana)));

function abrirClase(pestana = estado.pestana) {
  estado.pestana = pestana;
  document.querySelectorAll('[data-pestana]').forEach((b) =>
    b.setAttribute('aria-selected', String(b.dataset.pestana === pestana)));
  if ($('clase').hidden) $('rejilla-clase').replaceChildren(el('p', { class: 'vacio', style: { gridColumn: '1 / -1' } }, 'Cargando…'));
  $('clase').hidden = false;
  cargarClase();
  clearInterval(sondeoClase);
  sondeoClase = setInterval(cargarClase, 8000);
}

async function cargarClase() {
  const pestana = estado.pestana;
  const consulta = pestana === 'reto' ? 'ambito=reto&orden=votos' : pestana === 'votos' ? 'orden=votos' : 'orden=recientes';
  try {
    const g = await api(`/api/galeria?limite=60&${consulta}`, { cabeceras: cabeceras() });
    if (pestana !== estado.pestana || $('clase').hidden) return;
    if (!g.imagenes.length) {
      $('rejilla-clase').replaceChildren(el('div', { class: 'vacio', style: { gridColumn: '1 / -1' } },
        el('div', {}, pestana === 'reto' ? '🏁' : '🌟'),
        pestana === 'reto' ? 'Todavía no hay imágenes en este reto.' : 'Todavía no hay imágenes compartidas.'));
      return;
    }
    $('rejilla-clase').replaceChildren(...g.imagenes.map((t) => pieza(t, { votar: true })));
  } catch (e) {
    if (e.estado === 401) return salir(e.message);
  }
}

// Visor
function abrirVisor(t) {
  $('visor-img').src = t.imagen;
  $('visor-img').alt = t.prompt;
  $('visor-idea').textContent = t.prompt;
  $('visor-autor').textContent = t.mia ? '' : `🎨 ${t.alias}`;
  $('visor-descargar').href = `${t.imagen}?descargar=1`;
  const voto = $('visor-voto');
  voto.hidden = !t.publico;  // las privadas no se votan
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
  for (const id of ['visor', 'galeria', 'clase']) $(id).hidden = true;
  clearInterval(sondeoClase);
}

document.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Escape') return;
  const abierto = ['visor', 'galeria', 'clase'].find((id) => !$(id).hidden);
  if (abierto) $(abierto).hidden = true;
  if (abierto === 'clase') clearInterval(sondeoClase);
});

iniciar();
