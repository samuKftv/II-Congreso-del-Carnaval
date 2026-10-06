// Utilidades compartidas por el alumnado, el panel y el proyector.

const almacen = {
  leer(clave) {
    try { return localStorage.getItem(clave); } catch { return null; }
  },
  guardar(clave, valor) {
    try {
      if (valor == null) localStorage.removeItem(clave);
      else localStorage.setItem(clave, valor);
    } catch { /* navegación privada: seguimos sin recordar */ }
  },
};

class ErrorApi extends Error {
  constructor(mensaje, estado, cuerpo) {
    super(mensaje);
    this.estado = estado;
    this.cuerpo = cuerpo;
  }
}

async function api(ruta, { metodo = 'GET', datos, cabeceras = {} } = {}) {
  const opciones = { method: metodo, headers: { ...cabeceras } };
  if (datos !== undefined) {
    opciones.headers['Content-Type'] = 'application/json';
    opciones.body = JSON.stringify(datos);
  }
  let respuesta;
  try {
    respuesta = await fetch(ruta, opciones);
  } catch {
    throw new ErrorApi('No hay conexión con el estudio. Revisa la WiFi.', 0);
  }
  let cuerpo = null;
  try { cuerpo = await respuesta.json(); } catch { /* sin cuerpo */ }
  if (!respuesta.ok) {
    const detalle = cuerpo && typeof cuerpo.detail === 'string' ? cuerpo.detail : `Error ${respuesta.status}`;
    throw new ErrorApi(detalle, respuesta.status, cuerpo);
  }
  return cuerpo;
}

function el(etiqueta, props = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(props)) {
    if (clave === 'class') nodo.className = valor;
    else if (clave === 'style' && typeof valor === 'object') {
      for (const [propiedad, v] of Object.entries(valor)) {
        if (propiedad.startsWith('--')) nodo.style.setProperty(propiedad, v);
        else nodo.style[propiedad] = v;
      }
    }
    else if (clave.startsWith('on')) nodo.addEventListener(clave.slice(2), valor);
    else if (valor === true) nodo.setAttribute(clave, '');
    else if (valor !== false && valor != null) nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos.flat()) {
    if (hijo != null) nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return nodo;
}

let temporizadorAviso;
function aviso(texto, error = false) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = texto;
  toast.classList.toggle('error', error);
  toast.classList.add('visible');
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => toast.classList.remove('visible'), 3800);
}

function confeti(cantidad = 90) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const raiz = getComputedStyle(document.documentElement);
  const colores = ['--magenta', '--amarillo', '--cian', '--naranja', '--deco-1', '--deco-2']
    .map((v) => raiz.getPropertyValue(v).trim()).filter(Boolean);
  for (let i = 0; i < cantidad; i++) {
    const trozo = el('div', { class: 'confeti' });
    trozo.style.left = Math.random() * 100 + 'vw';
    trozo.style.background = colores[i % colores.length];
    trozo.style.setProperty('--dx', (Math.random() * 40 - 20) + 'vw');
    trozo.style.setProperty('--giro', (Math.random() * 1080 - 540) + 'deg');
    trozo.style.setProperty('--dur', (2 + Math.random() * 1.6) + 's');
    trozo.style.animationDelay = Math.random() * 0.4 + 's';
    if (Math.random() < 0.3) trozo.style.borderRadius = '50%';
    document.body.append(trozo);
    setTimeout(() => trozo.remove(), 4500);
  }
}

function tiempoLegible(segundos) {
  if (segundos < 60) return `${Math.max(1, Math.round(segundos))} s`;
  const minutos = Math.round(segundos / 60);
  return minutos === 1 ? '1 minuto' : `${minutos} minutos`;
}

const NOMBRES_FORMATO = { cuadrado: 'Cuadrado', vertical: 'Vertical', horizontal: 'Horizontal' };
function nombreFormato(id) {
  return NOMBRES_FORMATO[id] || id.charAt(0).toUpperCase() + id.slice(1);
}
