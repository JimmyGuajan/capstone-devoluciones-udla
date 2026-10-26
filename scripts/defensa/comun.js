const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const fmt = (n, d = 0) => n.toLocaleString('de-DE', {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = (n, d = 1) => fmt(n, d) + ' %';
const sgn = (n, d = 0) => (n > 0 ? '+' : n < 0 ? '−' : '') + fmt(Math.abs(n), d);
const MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const etiqueta = iso => { const [y, m] = iso.split('-'); return MES[+m - 1] + ' ' + y; };
const corta = iso => { const [y, m] = iso.split('-'); return MES[+m - 1] + (m === '01' ? ' ' + y.slice(2) : ''); };

/* Todo lo que depende del ancho se registra aquí y se redibuja al cambiar el tamaño. */
const redibujables = [];
function registrar(fn) { redibujables.push(fn); fn(); }
let _t; addEventListener('resize', () => { clearTimeout(_t); _t = setTimeout(() => redibujables.forEach(f => f()), 120); });

/* Un SVG no tiene offsetParent: la visibilidad se mide con sus rectángulos de dibujo. */
const visible = el => el.getClientRects().length > 0;
const ancho = el => Math.max(300, Math.round(el.getBoundingClientRect().width || el.parentElement.clientWidth));
function escala(max) {
  for (const base of [1, 2, 5, 10, 20, 50, 100, 200, 250, 500, 1000, 2000, 5000]) {
    if (max / base <= 6) return [Math.ceil(max / base) * base, base];
  }
  return [max, max / 5];
}
const corridas = a => {            // tramos contiguos sin valores nulos
  const r = []; let c = [];
  a.forEach((v, i) => { if (v == null) { if (c.length) r.push(c); c = []; } else c.push(i); });
  if (c.length) r.push(c); return r;
};

/* Lineas con puntos, bandas, linea de referencia y mes seleccionable. */
function lineas(el, c) {
  const W = ancho(el), H = c.alto || (W < 520 ? 240 : 300), L = c.izq || 44, R = 12, T = 14, B = 30, n = c.etiquetas.length;
  const vs = [];
  c.series.forEach(s => s.valores.forEach(v => v != null && vs.push(v)));
  (c.bandas || []).forEach(b => b.hi.forEach(v => v != null && vs.push(v)));
  if (c.ref) vs.push(c.ref.y);
  const [tope, paso] = escala(Math.max(...vs) * 1.06);
  const x = i => L + (W - L - R) * (i + .5) / n, y = v => T + (H - T - B) * (1 - v / tope);
  const yf = c.yfmt || (v => fmt(v));
  let s = '';
  for (let v = 0; v <= tope + 1e-9; v += paso)
    s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 7}" y="${y(v) + 3.5}" text-anchor="end">${yf(v)}</text>`;
  const w = (W - L - R) / n;
  if (c.sel != null) s += `<rect class="sel" x="${x(c.sel) - w / 2}" y="${T}" width="${w}" height="${H - T - B}" rx="6"/>`;
  (c.bandas || []).forEach(b => corridas(b.hi).forEach(r => {
    const up = r.map(i => `${x(i)},${y(b.hi[i])}`), dn = r.map(i => `${x(i)},${y(b.lo[i])}`).reverse();
    s += `<polygon class="band ${b.cls}" points="${up.concat(dn).join(' ')}"/>`;
  }));
  if (c.ref) s += `<line class="ref" x1="${L}" x2="${W - R}" y1="${y(c.ref.y)}" y2="${y(c.ref.y)}"/><text class="reft" x="${W - R}" y="${y(c.ref.y) - 5}" text-anchor="end">${c.ref.texto}</text>`;
  c.series.forEach(se => {
    corridas(se.valores).forEach(r => {
      s += `<polyline class="ln l${se.k} ${se.trazo || ''}" points="${r.map(i => `${x(i)},${y(se.valores[i])}`).join(' ')}"/>`;
    });
    if (se.puntos !== false) se.valores.forEach((v, i) => {
      if (v == null) return;
      const r = i === c.sel ? 5.5 : 3.6;
      s += `<circle class="pt l${se.k} ${se.hueco && se.hueco.includes(i) ? 'hueco' : 'f' + se.k}" cx="${x(i)}" cy="${y(v)}" r="${r}"/>`;
    });
  });
  const salto = Math.ceil(n / Math.max(1, Math.floor((W - L) / 44)));
  c.etiquetas.forEach((e, i) => {
    if (i % salto === 0 || i === c.sel) s += `<text class="xl ${i === c.sel ? 'on' : ''}" x="${x(i)}" y="${H - 9}" text-anchor="middle">${e}</text>`;
    s += `<rect class="hit" data-i="${i}" x="${x(i) - w / 2}" y="${T}" width="${w}" height="${H - T}"><title>${c.titulo ? c.titulo(i) : e}</title></rect>`;
  });
  el.setAttribute('viewBox', `0 0 ${W} ${H}`); el.innerHTML = s;
  if (c.alSel) $$('.hit', el).forEach(r => r.onclick = () => c.alSel(+r.dataset.i));
}

/* Columnas con una linea opcional encima. */
function columnas(el, c) {
  const W = ancho(el), H = c.alto || (W < 520 ? 220 : 270), L = 44, R = 10, T = 14, B = 30, n = c.etiquetas.length;
  const vs = c.valores.concat(c.linea ? c.linea.valores : []).concat(c.ref ? [c.ref.y] : []).filter(v => v != null);
  const [tope, paso] = escala(Math.max(...vs) * 1.06);
  const x = i => L + (W - L - R) * (i + .5) / n, y = v => T + (H - T - B) * (1 - v / tope), w = (W - L - R) / n;
  let s = '';
  for (let v = 0; v <= tope + 1e-9; v += paso)
    s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 7}" y="${y(v) + 3.5}" text-anchor="end">${fmt(v)}</text>`;
  c.valores.forEach((v, i) => {
    const sel = c.sel === i;
    s += `<rect class="colb f${c.k || 1}" x="${x(i) - w * .36}" y="${y(v)}" width="${w * .72}" height="${y(0) - y(v)}" rx="2" opacity="${c.sel == null || sel ? .92 : .45}"/>`;
  });
  if (c.linea) s += `<polyline class="ln l${c.linea.k} ${c.linea.trazo || ''}" points="${c.linea.valores.map((v, i) => `${x(i)},${y(v)}`).join(' ')}"/>`;
  if (c.ref) s += `<line class="ref" x1="${L}" x2="${W - R}" y1="${y(c.ref.y)}" y2="${y(c.ref.y)}"/><text class="reft" x="${W - R}" y="${y(c.ref.y) - 5}" text-anchor="end">${c.ref.texto}</text>`;
  if (c.etiquetasValor) c.valores.forEach((v, i) => { s += `<text x="${x(i)}" y="${y(v) - 6}" text-anchor="middle" style="fill:var(--ink);font-weight:600">${c.etiquetasValor(v)}</text>`; });
  const salto = Math.ceil(n / Math.max(1, Math.floor((W - L) / 40)));
  c.etiquetas.forEach((e, i) => {
    if (i % salto === 0) s += `<text class="xl" x="${x(i)}" y="${H - 9}" text-anchor="middle">${e}</text>`;
    s += `<rect class="hit" data-i="${i}" x="${x(i) - w / 2}" y="${T}" width="${w}" height="${H - T}"><title>${c.titulo ? c.titulo(i) : e}</title></rect>`;
  });
  el.setAttribute('viewBox', `0 0 ${W} ${H}`); el.innerHTML = s;
  if (c.alSel) $$('.hit', el).forEach(r => r.onclick = () => c.alSel(+r.dataset.i));
}

/* Barras horizontales en HTML. Con `divergente` se centran en cero. */
function barras(el, items, o = {}) {
  let max = o.max ?? Math.max(...items.map(i => Math.abs(i.valor)));
  if (o.ref != null) max = Math.max(max, o.ref * 1.12);   // la referencia siempre cabe en la escala
  el.className = 'bars';
  el.innerHTML = items.map(i => {
    const a = Math.abs(i.valor) / max * (o.divergente ? 50 : 100);
    const pos = o.divergente ? (i.valor >= 0 ? `left:50%;width:${a}%` : `left:${50 - a}%;width:${a}%`) : `left:0;width:${a}%`;
    const ref = o.ref != null ? `<span class="refl" style="left:${o.ref / max * 100}%"></span>` : '';
    return `<div class="bar"><span class="nom" title="${i.nombre}">${i.nombre}</span>
      <span class="pista">${o.divergente ? '<span class="cero"></span>' : ''}<span class="rel" style="${pos};background:var(--c${i.k || 1})"></span>${ref}</span>
      <span class="val">${i.texto ?? fmt(i.valor, o.dec || 0)}</span></div>`;
  }).join('');
}

function pastillas(el, etiquetas, sel, alSel) {
  el.innerHTML = etiquetas.map((e, i) => `<button type="button" data-i="${i}" aria-pressed="${i === sel}">${e}</button>`).join('');
  $$('button', el).forEach(b => b.onclick = () => alSel(+b.dataset.i));
}

/* Modo claro / oscuro: respeta la preferencia del sistema hasta que la persona elige. */
(function () {
  const raiz = document.documentElement, btn = $('#tema'), sis = matchMedia('(prefers-color-scheme: dark)');
  const actual = () => raiz.getAttribute('data-theme') || (sis.matches ? 'dark' : 'light');
  const pintar = () => { const t = actual(); btn.textContent = t === 'dark' ? '☀ Claro' : '☾ Oscuro'; btn.setAttribute('aria-pressed', t === 'dark'); };
  btn.onclick = () => {
    const n = actual() === 'dark' ? 'light' : 'dark';
    raiz.setAttribute('data-theme', n);
    try { localStorage.setItem('tema', n); } catch (e) {}
    pintar();
  };
  if (sis.addEventListener) sis.addEventListener('change', () => { if (!raiz.getAttribute('data-theme')) pintar(); });
  pintar();
})();
