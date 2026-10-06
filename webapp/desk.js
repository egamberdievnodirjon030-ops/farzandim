/* =====================================================================
   Boshqaruv paneli — kompyuter versiyasi (kurs koordinatori va super-admin)
   Kirish: botdagi «💻 Kompyuter versiyasi» → bir martalik havola → seans cookie (X-Desk sarlavhasi bilan).
   ===================================================================== */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
/* bot hisobotlaridagi xavfsiz teglar (<b>, <i>, <code>, <u>) — qolgani matn sifatida */
const safeHtml = s => esc(s).replace(/&lt;(\/?)(b|i|u|code)&gt;/g, '<$1$2>');
const DEV = new URLSearchParams(location.search).has('dev');
/* Telegram orqali kirish seansi — telefon/brauzer ilovasi bilan umumiy (bir xil manba: localStorage) */
const appToken = { get() { try { return localStorage.getItem('appToken'); } catch (_) { return null; } },
  set(v) { try { v ? localStorage.setItem('appToken', v) : localStorage.removeItem('appToken'); } catch (_) { /* */ } } };
function authHeaders(h) { const tk = appToken.get(); if (tk) h.Authorization = 'Bearer ' + tk; return h; }
const S = { me: null, course: null, stu: null, stuCourse: null, timers: [], badges: { unread: 0, requests: 0 } };

/* ---------------------------------------------------------------- belgilar */
const P = {
  poll: '<path d="M9 3h6v3H9zM9 4.5H6a1 1 0 0 0-1 1V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5.5a1 1 0 0 0-1-1h-3M8.5 12l2 2 4-4M8.5 17h7"/>',
  book: '<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H20v15H5.5A1.5 1.5 0 0 0 4 19.5zM4 19.5A1.5 1.5 0 0 0 5.5 21H20v-3M8 7h8M8 10.5h6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  auto: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M12 7h4.5M12 11h6M12 15h5.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  panel: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  chat: '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.9-.9L3 21l1.9-5.1A8.4 8.4 0 1 1 21 11.5z"/>',
  req: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/>',
  mega: '<path d="M3 11v3a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
  chart: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
  building: '<path d="M3 21h18"/><path d="M5 21V8l7-5 7 5v13"/><path d="M9 21v-6h6v6"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
  send: '<path d="m22 2-7 20-4-9-9-4 20-7z"/><path d="M22 2 11 13"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  ok: '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m22 4-10 10-3-3"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  db: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.7-4 3-9 3s-9-1.3-9-3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5"/>',
  telegram: '<path d="m22 3-9.5 17.5-2.8-7.7L2 10.2z"/><path d="M22 3 9.7 12.8"/>',
  // ko'rsatkichlar: har bir ma'lumot turi — o'z belgisi
  dollar: '<circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/>',
  receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1z"/><path d="M15 8h-4.5a1.75 1.75 0 0 0 0 3.5h3a1.75 1.75 0 0 1 0 3.5H9"/><path d="M12 6.5v11"/>',
  cap: '<path d="M21.4 10.9a1 1 0 0 0 0-1.8L12.8 5.2a2 2 0 0 0-1.7 0L2.6 9.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.7 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
  bookx: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/><path d="m14.5 7-5 5M9.5 7l5 5"/>',
  calx: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M14 14l-4 4M10 14l4 4"/>',
  flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1.1-2.1-.2-4.1 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1z"/>',
  up: '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
  down: '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  userx: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m17 8 5 5M22 8l-5 5"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  server: '<rect x="2" y="3" width="20" height="7" rx="2"/><rect x="2" y="14" width="20" height="7" rx="2"/><path d="M6 6.5h.01M6 17.5h.01"/>',
  target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
};
const ic = n => `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ''}</svg>`;

/* ---------------------------------------------------------------- formatlash */
const MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'];
const DAYS = ['yakshanba', 'dushanba', 'seshanba', 'chorshanba', 'payshanba', 'juma', 'shanba'];
const num = (x, d = 1) => Number(x || 0).toLocaleString('ru-RU', { maximumFractionDigits: d });
const money = x => `${Math.round(Number(x || 0)).toLocaleString('ru-RU')}\u00a0so‘m`;
const mln = x => Number(x || 0) >= 1e6 ? `${num(Number(x) / 1e6, 1)}<small> mln so‘m</small>` : `${num(x, 0)}<small> so‘m</small>`;
const mlnPlain = x => Number(x || 0) >= 1e6 ? `${num(Number(x) / 1e6, 1)} mln` : num(x, 0);
// GPA yaxlitlanmaydi — 2 xonagacha kesiladi (2,599 → 2,59)
const limNum = x => String(x).replace('.', ',');  // chegara aynan: 2.6 → 2,6
const gpaFmt = g => (Math.floor(Number(g) * 100 + 1e-6) / 100).toFixed(2).replace('.', ',');
const pairs = h => `${num(Number(h || 0) / 2)} para (${num(h)} soat)`;
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
function fmtPhone(p) {
  const d = String(p || '').replace(/\D/g, '');
  if (d.length === 12 && d.startsWith('998')) return `+998 ${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8, 10)} ${d.slice(10)}`;
  return p ? String(p) : '';
}
function todayLabel() { const d = new Date(); return `${d.getDate()}-${MONTHS[d.getMonth()]}, ${DAYS[d.getDay()]}`; }
function parseDate(iso) { if (!iso) return null; const d = new Date(String(iso).replace(' ', 'T')); return isNaN(d) ? null : d; }
function when(iso, withTime = true) {
  const d = parseDate(iso); if (!d) return '';
  const t = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  const now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1);
  const same = (a, b) => a.toDateString() === b.toDateString();
  const day = same(d, now) ? 'Bugun' : same(d, y) ? 'Kecha' : `${d.getDate()}-${MONTHS[d.getMonth()]}${d.getFullYear() !== now.getFullYear() ? ' ' + d.getFullYear() : ''}`;
  return withTime ? `${day}, ${t}` : day;
}
function shortWhen(iso) {
  const d = parseDate(iso); if (!d) return '';
  const now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1);
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  if (d.toDateString() === y.toDateString()) return 'Kecha';
  return `${d.getDate()}-${MONTHS[d.getMonth()]}`;
}
const initials = n => String(n || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
const LANG = { uz: 'o‘zbek', ru: 'rus', en: 'ingliz' };

/* ---------------------------------------------------------------- mavzu: avtomatik / kunduzgi / tungi */
const MQ = matchMedia('(prefers-color-scheme: dark)');
const THEME_NAMES = { auto: 'Avtomatik', light: 'Kunduzgi', dark: 'Tungi' };
function themePref() { try { return localStorage.getItem('desk-theme') || 'auto'; } catch (_) { return 'auto'; } }
function applyTheme() {
  const p = themePref();
  document.documentElement.dataset.theme = p === 'dark' || (p === 'auto' && MQ.matches) ? 'dark' : 'light';
  const b = document.querySelector('[data-act="theme"]');
  if (b) { b.innerHTML = ic({ auto: 'auto', light: 'sun', dark: 'moon' }[p]); b.title = `Mavzu: ${THEME_NAMES[p]}`; }
}
MQ.addEventListener('change', applyTheme);
applyTheme();

/* ---------------------------------------------------------------- API */
async function api(path, { method = 'GET', json, body, raw, course } = {}) {
  const h = authHeaders({ 'X-Desk': '1' });
  if (DEV) h['X-Dev-User'] = '1';
  if (course) h['X-Course-Temp'] = course;  // bir martalik (masalan, boshqa kurs talabasi kartasi) — faol kurs o'zgarmaydi
  else if (S.course && S.me && S.me.role === 'super') h['X-Course'] = S.course;
  if (json !== undefined) { h['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  const r = await fetch(path, { method, headers: h, body, credentials: 'same-origin' });
  if (r.status === 401) { renderLogin(); const e = new Error('auth'); e.status = 401; throw e; }
  if (raw) { if (!r.ok) throw new Error('http ' + r.status); return r; }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(d.error || 'http ' + r.status); e.status = r.status; e.data = d; throw e; }
  return d;
}

/* ---------------------------------------------------------------- umumiy UI */
function toast(msg, err = false) {
  const t = document.createElement('div');
  t.className = 'toast' + (err ? ' err' : '');
  t.innerHTML = `${ic(err ? 'alert' : 'ok')}<span>${esc(msg)}</span>`;
  $('#toasts').append(t);
  setTimeout(() => t.remove(), err ? 6000 : 3500);
}
function dialog({ title, text = '', fields = [], ok = 'Saqlash', danger = false }) {
  return new Promise(res => {
    const d = $('#dlg');
    d.innerHTML = `<form method="dialog"><h3>${esc(title)}</h3>${text ? `<p>${text}</p>` : ''}
      ${fields.map(f => `<label class="field"><span>${esc(f.label)}</span>
        <input class="input" name="${f.name}" value="${esc(f.value || '')}" ${f.type ? `type="${f.type}"` : ''} ${f.required ? 'required' : ''}
          ${f.pattern ? `pattern="${f.pattern}"` : ''} placeholder="${esc(f.placeholder || '')}" autocomplete="off">
        ${f.hint ? `<small class="hint">${f.hint}</small>` : ''}</label>`).join('')}
      <div class="row"><button class="btn" value="cancel" formnovalidate>Bekor qilish</button>
        <button class="btn ${danger ? 'danger solid' : 'primary'}" value="ok">${esc(ok)}</button></div></form>`;
    d.returnValue = '';
    d.onclose = () => res(d.returnValue === 'ok' ? Object.fromEntries(new FormData(d.querySelector('form'))) : null);
    d.showModal();
    (d.querySelector('input') || d.querySelector('.btn.primary, .btn.solid'))?.focus();
  });
}
/* Kurs koordinatoriga guruhlar biriktirish: belgilanganlar va qo'lda yozilganlar saqlanadi (null — bekor qilindi) */
function groupsDialog(name, uid, info) {
  return new Promise(res => {
    const d = $('#dlg');
    const free = info.groups.filter(g => !g.owner || g.owner === uid), busy = info.groups.filter(g => g.owner && g.owner !== uid);
    d.innerHTML = `<form method="dialog" class="grp-dlg"><h3>${esc(name)} — guruhlar</h3>
      <p>Fayl yuklaganda (davomat, baholar, buxgalteriya hisoboti…) faqat shu guruhlar talabalari tanilinadi. Hech biri belgilanmasa — butun kurs.</p>
      ${free.length ? `<div class="grp-list">${free.map(g => `<label><input type="checkbox" name="g" value="${esc(g.name)}" ${g.owner === uid ? 'checked' : ''}> ${esc(g.name)} <span class="hint">${g.students}</span></label>`).join('')}</div>`
        : '<p class="hint">Kursda biriktirilmagan guruh yo‘q.</p>'}
      ${(info.coordinators.find(c => c.user_id === uid) || {}).is_super ? '<p class="hint" style="color:var(--bordo-700, #8a1c2b)"><b>Bu foydalanuvchi super-admin</b> (.env — SUPERADMIN_IDS): u baribir butun kursni ko‘radi, guruhlar unga amal qilmaydi.</p>' : ''}
      ${busy.length ? `<p class="hint">Boshqa koordinatorlarda: ${busy.map(g => `${esc(g.name)} (${esc(g.owner_label)})`).join(', ')}</p>` : ''}
      <label class="field"><span>Yana guruhlar (vergul bilan)</span><input class="input" name="extra" placeholder="Masalan: XM-21, XM-22" autocomplete="off">
        <small class="hint">Talabalar hali yuklanmagan guruhlar uchun.</small></label>
      <div class="row"><button class="btn" value="cancel" formnovalidate>Bekor qilish</button><button class="btn primary" value="ok">Saqlash</button></div></form>`;
    d.returnValue = '';
    d.onclose = () => {
      if (d.returnValue !== 'ok') return res(null);
      const f = new FormData(d.querySelector('form'));
      res([...f.getAll('g'), ...String(f.get('extra') || '').split(/[,;\n]+/).map(x => x.trim()).filter(Boolean)]);
    };
    d.showModal();
  });
}
const confirmDlg = (title, text, ok, danger = false) => dialog({ title, text, ok, danger }).then(Boolean);
const emptyBox = (icon, title, text = '', action = '') =>
  `<div class="empty">${ic(icon)}<b>${esc(title)}</b>${text ? `<div>${text}</div>` : ''}${action ? `<div style="margin-top:14px">${action}</div>` : ''}</div>`;
const skel = (h = 120, n = 1) => Array.from({ length: n }, () => `<div class="skel" style="height:${h}px;margin-bottom:16px"></div>`).join('');
const main = () => $('#main');
const PAGE_IC = { 'Kurs holati': 'panel', 'Talabalar': 'users', 'Xabarlar': 'chat', 'Bog‘lanish so‘rovlari': 'req', 'So‘rovlar': 'req',
  'E’lon yuborish': 'mega', 'Rasmiy hujjat yuborish': 'file', 'So‘rovnomalar': 'poll', 'So‘rovnoma': 'poll', 'Yangi so‘rovnoma': 'poll',
  'Ma’lumot va hisobot': 'upload', 'Barcha kurslar': 'chart', 'Kurslar va koordinatorlar': 'building', 'Ichki nizomlar': 'book',
  'Tizim': 'shield', 'Xatolik': 'alert' };
function head(title, sub, actions = '') {
  const pi = PAGE_IC[title];
  return `<header class="ph">${pi ? `<span class="ph-ic" aria-hidden="true">${ic(pi)}</span>` : ''}<div class="ph-t"><h1>${esc(title)}</h1><p>${sub}</p></div><div class="ph-act">${actions}</div></header>`;
}
/* bo'lim sarlavhasi belgisi bilan: H('dollar', 'Kontrakt', 'money') */
const H = (icon, title, c = 'people') => `<h2><span class="h-ic c-${c}" aria-hidden="true">${ic(icon)}</span>${title}</h2>`;
/* Ko'rsatkich kartochkasi: belgi (ma'lumot turi rangida) · nom · holat (belgi + so'z, faqat rang emas) · qiymat · izoh.
   Qiymat matni doim asosiy siyoh rangida; holatni yonidagi belgili yorliq aytadi. */
function kpi({ href, icon, c = 'people', label, value, unit = '', sub = '', state = null, meter = null, title = '' }) {
  const tag = href ? 'a' : 'div';
  const st = state === 'bad' ? `<span class="st bad">${ic('alert')}e’tibor</span>`
    : state === 'warn' ? `<span class="st warn">${ic('alert')}qarz bor</span>`
    : state === 'ok' ? `<span class="st ok">${ic('check')}joyida</span>` : '';
  return `<${tag} class="kpi c-${c}"${href ? ` href="${href}"` : ''}${title ? ` title="${esc(title)}"` : ''}>
    <div class="kpi-top"><span class="kpi-ic c-${c}" aria-hidden="true">${ic(icon)}</span><span class="kpi-k">${label}</span>${st}</div>
    <div class="kpi-v num">${value}${unit ? `<small>${unit}</small>` : ''}</div>
    ${meter != null ? `<div class="meter c-${c}"><i style="width:${Math.max(0, Math.min(100, meter))}%"></i></div>` : ''}
    <div class="kpi-s">${sub}</div></${tag}>`;
}
/* pul: ixcham (83,6 mln), to'liq summa — sarlavha (title) va izohda */
const moneyShort = x => { const v = Number(x || 0); return v >= 1e9 ? [num(v / 1e9, 2), 'mlrd so‘m'] : v >= 1e6 ? [num(v / 1e6, 1), 'mln so‘m'] : [num(v, 0), 'so‘m']; };
const probState = (n, w = 'bad') => (n ? w : 'ok');
const myGroups = () => (S.me.staff && S.me.staff.groups) || [];
const courseSub = () => `${S.me.staff.title ? esc(S.me.staff.title) + ', ' : ''}${myGroups().length ? 'guruhlar: ' + esc(myGroups().join(', ')) + ', ' : ''}${todayLabel()}`;
function view(html) { main().innerHTML = `<div class="wrap">${html}</div>`; }
function clearTimers() { S.timers.forEach(clearInterval); S.timers = []; S.inboxRefresh = null; }
async function download(path) {
  const r = await api(path, { raw: true });
  const cd = r.headers.get('Content-Disposition') || '';
  const name = decodeURIComponent((cd.match(/filename="?([^"]+)"?/) || [])[1] || 'hisobot');
  const url = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  return name;
}

/* ---------------------------------------------------------------- kirish sahifasi */
function renderLogin(msg = '') {
  clearTimers(); clearTimeout(LOGIN.timer); LOGIN.code = null;
  document.title = 'Kirish — Boshqaruv paneli';
  $('#app').className = '';
  $('#app').innerHTML = `<div class="login"><main class="card"><img class="seal-img" src="/static/jidu-seal.webp" alt="" width="60" height="60">
    <h1>Boshqaruv paneli</h1><p>${msg ? esc(msg) : 'Kurs koordinatori va super-admin uchun kompyuter versiyasi.'}</p>
    <div id="login-box"><button class="btn primary lg" data-act="tg-login">${ic('telegram')} Telegram orqali kirish</button>
      <p class="hint" style="margin:12px 0 0">Ekranda 2 xonali raqam chiqadi — botda shu raqamni tanlaysiz. Parol kerak emas.</p></div>
    <details class="alt"><summary>Boshqa usul: botdagi havola</summary><ol><li>Telegram’da botni oching.</li>
      <li><b>«💻 Kompyuter versiyasi»</b> tugmasini bosing yoki <b>/kompyuter</b> buyrug‘ini yuboring.</li>
      <li>Bot yuborgan tugmani shu kompyuterda bosing — panel ochiladi.</li></ol></details></main></div>`;
  const saved = !msg && loginSaved();
  if (saved) showPin(saved);
}
/* Telegram orqali kirish: kod + 2 xonali raqam → botda tasdiqlash → seans (appauth.py) */
const LOGIN = { code: null, timer: null, until: 0 };
function loginSaved(v) {
  try {
    if (v === undefined) { const x = JSON.parse(sessionStorage.getItem('jiduLogin') || 'null'); return x && x.until > Date.now() ? x : null; }
    v ? sessionStorage.setItem('jiduLogin', JSON.stringify(v)) : sessionStorage.removeItem('jiduLogin');
  } catch (_) { return null; }
}
async function startTgLogin() {
  const os = /Windows/.test(navigator.userAgent) ? 'Windows' : /Mac OS/.test(navigator.userAgent) ? 'Mac' : /Linux/.test(navigator.userAgent) ? 'Linux' : 'Kompyuter';
  const r = await fetch('/api/app/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ device: `${os} — kompyuter` }) });
  if (!r.ok) { toast(r.status === 429 ? 'Urinishlar ko‘p. Birozdan so‘ng qayta urinib ko‘ring.' : 'Server bilan bog‘lanib bo‘lmadi', true); return; }
  const d = await r.json();
  const v = { code: d.code, pin: d.pin, url: d.url, until: Date.now() + d.expires_in * 1000 };
  loginSaved(v); showPin(v);
}
function showPin(v) {
  LOGIN.code = v.code; LOGIN.until = v.until;
  $('#login-box').innerHTML = `<p style="margin:0 0 6px">Telegram’da botni oching va shu raqamni tanlang:</p>
    <div class="login-pin">${esc(v.pin)}</div>
    <a class="btn primary lg" href="${esc(v.url)}" target="_blank" rel="noopener">${ic('telegram')} Telegram’ni ochish</a>
    <p class="hint" style="margin:12px 0 0;text-align:center">Tasdiqlashingiz kutilmoqda… · <a href="#" data-act="tg-cancel">Bekor qilish</a></p>`;
  pollTg(v.code);
}
async function pollTg(code) {
  clearTimeout(LOGIN.timer);
  if (LOGIN.code !== code) return;
  const end = m => { LOGIN.code = null; loginSaved(null); renderLogin(m); };
  if (Date.now() > LOGIN.until) return end('Kirish vaqti tugadi. Qaytadan urinib ko‘ring.');
  let st = { state: 'pending' };
  try { const r = await fetch('/api/app/login/' + encodeURIComponent(code), { cache: 'no-store' }); if (r.ok) st = await r.json(); } catch (_) { /* tarmoq */ }
  if (LOGIN.code !== code) return;
  if (st.state === 'approved') { LOGIN.code = null; loginSaved(null); appToken.set(st.token); location.reload(); return; }
  if (st.state === 'cancelled') return end('Kirish bekor qilindi.');
  if (st.state === 'expired' || st.state === 'used') return end('Kirish vaqti tugadi. Qaytadan urinib ko‘ring.');
  LOGIN.timer = setTimeout(() => pollTg(code), document.hidden ? 4000 : 1500);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden && LOGIN.code) pollTg(LOGIN.code); });
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act="tg-login"],[data-act="tg-cancel"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (b.dataset.act === 'tg-cancel') { loginSaved(null); renderLogin(); return; }
  b.disabled = true; await startTgLogin(); b.disabled = false;
}, true);

/* ---------------------------------------------------------------- karkas: yon menyu */
const NAV_COURSE = [['#/panel', 'panel', 'Kurs holati'], ['#/students', 'users', 'Talabalar'], ['#/inbox', 'chat', 'Xabarlar', 'unread'],
  ['#/requests', 'req', 'So‘rovlar', 'requests'], ['#/announce', 'mega', 'E’lon yuborish'], ['#/docs', 'file', 'Hujjat yuborish'], ['#/surveys', 'poll', 'So‘rovnomalar'], ['#/files', 'upload', 'Ma’lumot va hisobot']];
const NAV_SUPER = [['#/super', 'chart', 'Barcha kurslar'], ['#/super/courses', 'building', 'Kurslar va koordinatorlar'], ['#/super/regs', 'book', 'Ichki nizomlar'], ['#/super/system', 'shield', 'Tizim']];

function renderShell() {
  const me = S.me, sup = me.role === 'super';
  const courses = me.staff.courses || [];
  const navItem = ([href, icon, label, badge]) =>
    `<a href="${href}" data-nav="${href}" title="${label}">${ic(icon)}<span>${label}</span>${badge ? `<i class="badge" data-badge="${badge}" hidden></i>` : ''}</a>`;
  $('#app').className = 'app';
  $('#app').innerHTML = `
    <aside class="side">
      <div class="brand"><img class="seal-img" src="/static/jidu-seal.webp" alt="" width="42" height="42"><div><b>JIDU</b><span>Boshqaruv paneli</span></div></div>
      <div class="course-box">${sup && courses.length
        ? `<small>Joriy kurs</small><select id="course" aria-label="Joriy kurs">${courses.map(c => `<option value="${esc(c.key)}" ${c.key === S.course ? 'selected' : ''}>${esc(c.title)}</option>`).join('')}</select>`
        : `<small>Kurs</small><strong>${esc(me.staff.title || 'Kurs')}</strong>`}</div>
      <nav class="nav" aria-label="Bo‘limlar">
        ${sup ? `<h6>Universitet</h6>${NAV_SUPER.map(navItem).join('')}<h6>Joriy kurs</h6>` : ''}
        ${NAV_COURSE.map(navItem).join('')}
      </nav>
      <div class="me"><span class="av">${esc(initials(me.user.name))}</span>
        <div><b>${esc(me.user.name)}</b><span>${sup ? 'Super-admin' : 'Kurs koordinatori'}</span></div>
        <button data-act="theme" aria-label="Mavzu">${ic('auto')}</button>
        <button data-act="logout" title="Chiqish" aria-label="Chiqish">${ic('logout')}</button></div>
    </aside>
    <main class="main" id="main"></main>
    <div class="scrim" id="scrim"></div>
    <aside class="drawer" id="drawer" aria-hidden="true"><header><b>Talaba</b>
      <button class="btn ghost sm" data-act="close-drawer" aria-label="Yopish">${ic('x')}</button></header><div class="body" id="dbody"></div></aside>`;
  $('#course')?.addEventListener('change', e => { S.course = e.target.value; S.stu = null; S.me.staff.course = S.course;
    S.me.staff.title = courses.find(c => c.key === S.course)?.title || ''; refreshBadges();
    if (!location.hash.startsWith('#/super') && location.hash !== '#/panel') location.hash = '#/panel'; else route(); });
  paintBadges(); applyTheme();
}
function markNav() {
  const h = location.hash.split('?')[0] || '#/';
  $$('.nav a').forEach(a => {
    const n = a.dataset.nav;
    a.classList.toggle('on', h === n || (n !== '#/super' && h.startsWith(n + '/')) || (n === '#/students' && h.startsWith('#/student')));
  });
}
function paintBadges() {
  for (const [k, v] of Object.entries(S.badges)) {
    const b = $(`[data-badge="${k}"]`);
    if (b) { b.hidden = !v; b.textContent = v > 99 ? '99+' : v; }
  }
}
async function refreshBadges() {
  try {
    const [ib, rq] = await Promise.all([api('/api/staff/inbox'), api('/api/staff/requests')]);
    S.badges.unread = ib.items.reduce((s, i) => s + (i.unread || 0), 0);
    S.badges.requests = rq.items.length;
    paintBadges();
  } catch (e) { /* jim */ }
}

/* ---------------------------------------------------------------- yo'naltirish */
async function route() {
  clearTimers(); closeDrawer();
  const [path, qs] = (location.hash.slice(1) || '/').split('?');
  const q = new URLSearchParams(qs || '');
  const parts = path.split('/').filter(Boolean);
  const sup = S.me.role === 'super';
  if (!parts.length) { location.replace(sup ? '#/super' : '#/panel'); return; }
  markNav();
  const pages = { panel: pPanel, students: pStudents, inbox: pInbox, requests: pRequests, announce: pAnnounce, docs: pDocs, files: pFiles, surveys: pSurveys };
  try {
    if (parts[0] === 'super') {
      if (!sup) { location.replace('#/panel'); return; }
      await ({ courses: pSuperCourses, system: pSuperSystem, regs: pSuperRegs }[parts[1]] || pSuperOverview)(parts, q);
    } else if (parts[0] === 'student' && parts[1]) {
      await pStudents(parts, q); openStudent(Number(parts[1]));
    } else {
      await (pages[parts[0]] || pPanel)(parts, q);
    }
  } catch (e) {
    if (e.status === 401) return;
    console.error(e);
    view(head('Xatolik', courseSub()) + `<div class="sec">${emptyBox('alert', 'Ma’lumotni yuklab bo‘lmadi', 'Internet ulanishini tekshiring va sahifani yangilang.',
      `<button class="btn primary" data-act="reload">${ic('refresh')} Qayta urinish</button>`)}</div>`);
  }
}

/* ================================================================ kurs holati (panel) */
function tone(v, bad = 'bordo') { return v ? bad : 'ok'; }
async function pPanel() {
  document.title = 'Kurs holati — Boshqaruv paneli';
  view(head('Kurs holati', courseSub()) + skel(110) + skel(360));
  const [d, ib, rq] = await Promise.all([api('/api/staff/panel'), api('/api/staff/inbox'), api('/api/staff/requests')]);
  const cover = pct(d.linked, d.total);
  const unread = ib.items.reduce((a, i) => a + (i.unread || 0), 0);
  const share = n => (d.total ? `${pct(n, d.total)}% talabalar` : '');
  const [km, ku] = moneyShort(d.kontrakt.sum), [tm, tu] = moneyShort(d.trimestr.sum);
  const band = (d.scope ? `<p class="hint scope">${ic('info')}${esc(d.scope.replace(/^\s*ℹ️?\s*/u, ''))}</p>` : '') + `<section class="kpis" aria-label="Asosiy ko‘rsatkichlar">
    ${kpi({ href: '#/students', icon: 'users', c: 'people', label: 'Talabalar', value: num(d.total, 0), unit: 'ta',
      sub: `${ic('link')} ota-onasi ulangan: <b>${d.linked}</b> · ${cover}%`, meter: cover })}
    ${kpi({ href: '#/students?f=att', icon: 'calx', c: 'att', label: 'Davomat muammosi', value: d.att, unit: 'ta', state: probState(d.att),
      sub: d.att ? `chegaraga yetganlar · ${share(d.att)}` : 'chegaraga yetgan talaba yo‘q' })}
    ${kpi({ href: '#/students?f=acad', icon: 'bookx', c: 'acad', label: 'Akademik qarz', value: d.acad, unit: 'ta', state: probState(d.acad),
      sub: 'qarzdorlar ro‘yxati bo‘yicha' })}
    ${kpi({ href: '#/students?f=gpa', icon: 'cap', c: 'gpa', label: 'GPA past', value: d.gpa, unit: 'ta', state: probState(d.gpa),
      sub: `${limNum(d.gpa_min)} dan past — kursdan o‘tmaydi` })}
    ${kpi({ href: '#/students?f=prob', icon: 'flame', c: 'risk', label: '3+ masalali', value: d.multi, unit: 'ta', state: probState(d.multi),
      sub: 'birinchi navbatda e’tibor' })}
    ${kpi({ href: '#/students?f=kontrakt', icon: 'dollar', c: 'money', label: 'Kontrakt qarzi', value: km, unit: ku, state: probState(d.kontrakt.count, 'warn'),
      sub: `${d.kontrakt.count} ta talaba${d.kontrakt.count ? ` · o‘rtacha ${mlnPlain(d.kontrakt.sum / d.kontrakt.count)}` : ''}`, title: money(d.kontrakt.sum) })}
    ${kpi({ href: '#/students?f=trimestr', icon: 'receipt', c: 'money2', label: 'Trimestr qarzi', value: tm, unit: tu, state: probState(d.trimestr.count, 'warn'),
      sub: `${d.trimestr.count} ta talaba${d.trimestr.count ? ` · o‘rtacha ${mlnPlain(d.trimestr.sum / d.trimestr.count)}` : ''}`, title: money(d.trimestr.sum) })}
    ${kpi({ href: '#/inbox', icon: 'inbox', c: 'msg', label: 'Javobsiz xabarlar', value: unread, unit: 'ta', state: unread ? 'bad' : 'ok',
      sub: `${ic('req')} bog‘lanish so‘rovlari: <b>${rq.items.length}</b>` })}
  </section>`;
  const top = d.top.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Talaba</th><th>Masalalar</th><th class="r">Davomat</th></tr></thead>
    <tbody>${d.top.map(r => `<tr class="click" data-student="${r.id}"><td class="name"><b>${esc(r.name)}</b><span>${esc(r.group)}${r.hemis_id ? ', HEMIS ' + esc(r.hemis_id) : ''}</span></td>
      <td><div class="wrapc">${issueChips(r)}</div></td><td class="r">${r.percent != null ? r.percent + '%' : '<span class="dash">—</span>'}</td></tr>`).join('')}</tbody></table></div>`
    : emptyBox('ok', 'Muammoli talaba yo‘q', 'Davomat, baholar va to‘lovlar bo‘yicha e’tibor talab qiladigan holat topilmadi.');
  const fresh = ib.items.filter(i => i.unread).slice(0, 6);
  const msgs = fresh.length ? `<ul class="list">${fresh.map(i => `<li><a href="#/inbox/${i.sid}/${i.pid}"><span class="av-s">${esc(initials(i.parent))}</span>
      <div class="t"><b>${esc(i.parent)} <span class="chip bordo" style="height:20px;margin-left:4px">${i.unread}</span></b><p>${esc(i.student)}: ${esc(i.last)}</p></div><time>${when(i.at)}</time></a></li>`).join('')}</ul>`
    : `<div class="pad"><div class="note ok">${ic('ok')}<span>Javob kutayotgan xabar yo‘q.</span></div></div>`;
  view(head('Kurs holati', courseSub(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + band + dynSection(d.dynamics) + `
    <div class="grid-2">
      <section class="sec"><header>${H('target', 'E’tibor talab qiladigan talabalar', 'risk')}<a href="#/students?f=prob">Barchasi ${ic('arrow')}</a></header>${top}</section>
      <div class="stack">
        <section class="sec"><header>${H('chat', 'Yangi xabarlar', 'msg')}<a href="#/inbox">Xabarlar ${ic('arrow')}</a></header>${msgs}</section>
        <section class="sec"><header>${H('req', 'Bog‘lanish so‘rovlari', 'people')}</header><div class="pad">${rq.items.length
          ? `<div class="note warn">${ic('req')}<span><b>${rq.items.length} ta</b> ota-ona farzandini bog‘lashni so‘rayapti.</span></div>
             <div style="margin-top:12px"><a class="btn primary" href="#/requests">Ko‘rib chiqish</a></div>`
          : `<div class="note ok">${ic('ok')}<span>Kutilayotgan so‘rov yo‘q.</span></div>`}</div></section>
        <section class="sec"><header>${H('download', 'Hisobot', 'people')}</header><div class="pad actions">
          <button class="btn" data-act="export" data-fmt="x">${ic('download')} Excel yuklab olish</button>
          <button class="btn" data-act="export" data-fmt="p">${ic('file')} PDF yuklab olish</button></div></section>
      </div>
    </div>
    <p class="foot">${ic('clock')} Ma’lumotlar oxirgi marta yangilangan: ${d.updated ? when(d.updated) : 'hali yuklanmagan'}.</p>`);
}
/* Dinamika: kichik grafik (sparkline) — oxirgi nuqta ajratib ko'rsatiladi */
function spark(points, cls) {
  const v = points.map(p => p.value), W = 120, H = 34, P = 3;
  if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const xy = v.map((y, i) => [P + i * (W - 2 * P) / (v.length - 1), H - P - (y - lo) * (H - 2 * P) / span]);
  const d = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join('');
  const [lx, ly] = xy[xy.length - 1];
  return `<svg class="spark ${cls}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${points.map(p => p.label + ': ' + p.value).join(', ')}">
    <path d="${d}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${lx}" cy="${ly}" r="3" fill="currentColor"/></svg>`;
}
function dynVal(it, v) { return v == null ? '—' : it.unit === '%' ? `${v}%` : it.unit === 'so\'m' ? moneyShort(v).join(' ') : `${v} ta`; }
function dynDelta(it) {
  const d = it.delta;
  if (d == null) return { cls: 'flat', txt: 'taqqoslash uchun ma’lumot kam' };
  if (!d) return { cls: 'flat', txt: 'o‘zgarmadi' };
  const good = (d > 0) === (it.better === 'up');
  const mag = it.unit === '%' ? `${Math.abs(Math.round(d * 10) / 10)} p.p.` : dynVal(it, Math.abs(d));
  return { cls: good ? 'good' : 'bad', txt: mag, dir: d > 0 ? 'up' : 'down' };
}
function dynSection(items) {
  if (!items || !items.length) return '';
  const meta = it => it.unit === '%' ? ['activity', 'att'] : it.unit === 'so\'m' ? (/trimestr/i.test(it.title) ? ['receipt', 'money2'] : ['dollar', 'money'])
    : /chegara/i.test(it.title) ? ['userx', 'risk'] : ['chart', 'people'];
  return `<section class="dyn" aria-label="Dinamika">${items.map(it => { const dl = dynDelta(it); const [mi, mc] = meta(it); return `<div class="dyn-card">
    <div class="k"><span class="h-ic sm c-${mc}" aria-hidden="true">${ic(mi)}</span>${esc(it.title)}</div>
    <div class="row"><div><div class="v num">${esc(dynVal(it, it.value))}</div>
      <div class="d ${dl.cls}" title="${esc(it.caption)}">${dl.dir ? ic(dl.dir) : ''}${esc(dl.txt)}</div></div>${spark(it.points, dl.cls)}</div>
    <div class="s">${it.note ? esc(it.note) + ' · ' : ''}${esc(it.caption)}</div></div>`; }).join('')}</section>`;
}
function issueChips(r) {
  const out = [];
  if (r.flags.att) out.push(`<span class="chip bordo">${ic('calx')}${esc(r.action || 'Davomat')}</span>`);
  if (r.flags.acad) out.push(`<span class="chip bordo" title="${esc(r.debts.join(', '))}">${ic('bookx')}Akademik: ${r.debts.length} fan</span>`);
  if (r.flags.gpa) out.push(`<span class="chip bordo" title="Kursdan kursga o‘tmaydi">${ic('cap')}GPA ${gpaFmt(r.gpa)}</span>`);
  if (r.flags.kontrakt) out.push(`<span class="chip warn" title="Kontrakt qarzi: ${money(r.kontrakt)}">${ic('dollar')}${mlnPlain(r.kontrakt)} so‘m</span>`);
  if (r.flags.trimestr) out.push(`<span class="chip warn" title="Trimestr qarzi: ${money(r.trimestr)}">${ic('receipt')}${mlnPlain(r.trimestr)} so‘m</span>`);
  return out.join('') || '<span class="dash">—</span>';
}

/* ================================================================ talabalar */
const FILTERS = [['', 'Hammasi', 'users'], ['prob', 'Muammoli', 'flame'], ['att', 'Davomat', 'calx'], ['acad', 'Akademik qarz', 'bookx'],
  ['gpa', 'GPA past', 'cap'], ['kontrakt', 'Kontrakt', 'dollar'], ['trimestr', 'Trimestr', 'receipt']];
const COL_IC = {};  // ustun sarlavhalarida belgi yo'q — jadval ekranga sig'sin (belgilar kataklarda)
const COLS = [['name', 'Talaba'], ['group', 'Guruh'], ['percent', 'Davomat'], ['action', 'Chora'],
  ['debts', 'Akademik qarz'], ['gpa', 'GPA', 'r'], ['kontrakt', 'Kontrakt', 'r'], ['trimestr', 'Trimestr', 'r'], ['problems', 'Masala', 'r']];
const norm = s => String(s || '').toLowerCase().replace(/[‘’ʻʼ'`]/g, '').replace(/\s+/g, ' ').trim();
async function loadStudents(force = false) {
  if (!force && S.stu && S.stuCourse === S.course) return S.stu;
  const d = await api('/api/staff/students?limit=3000');
  S.stu = { rows: d.items }; S.stuCourse = S.course;
  return S.stu;
}
function matchFilter(r, f) { return !f || (f === 'prob' ? r.problems > 0 : r.flags[f]); }
async function loadAllStudents(force = false) {
  if (!force && S.stuAll) return S.stuAll;
  const d = await api('/api/super/students');
  S.stuAll = { rows: d.items };
  return S.stuAll;
}
async function pStudents(parts, q) {
  document.title = 'Talabalar — Boshqaruv paneli';
  const sup = S.me.role === 'super';
  const st = S.stuState = S.stuState || { f: '', q: '', g: '', c: '', all: false, sort: 'problems', dir: -1 };
  if (q && q.has('f')) { st.f = q.get('f'); if (st.f === 'acad') { st.sort = 'debts'; st.dir = -1; } }
  if (q && q.has('q')) st.q = q.get('q');
  if (q && q.has('all')) st.all = q.get('all') === '1';
  if (!sup) st.all = false;
  if (st.all ? !S.stuAll : (!S.stu || S.stuCourse !== S.course)) view(head('Talabalar', courseSub()) + skel(52) + skel(480));
  const { rows } = st.all ? await loadAllStudents() : await loadStudents();
  const groups = [...new Set(rows.filter(r => !st.c || r.course === st.c).map(r => r.group).filter(Boolean))].sort();
  const courses = st.all ? [...new Map(rows.map(r => [r.course, r.course_title])).entries()] : [];
  const cols = st.all ? [COLS[0], ['course_title', 'Kurs'], ...COLS.slice(1)] : COLS;
  view(head('Talabalar', st.all ? `Barcha kurslar, ${todayLabel()}` : courseSub(), `${st.all ? '' : `<button class="btn" data-act="export" data-fmt="x">${ic('download')} Excel</button>`}
      <button class="btn" data-act="reload-students">${ic('refresh')} Yangilash</button>`) + `
    ${sup ? `<div class="seg" id="scope" style="margin-bottom:14px"><button data-s="0" class="${st.all ? '' : 'on'}">Joriy kurs</button><button data-s="1" class="${st.all ? 'on' : ''}">Barcha kurslar</button></div>` : ''}
    <div class="toolbar">
      <div class="search">${ic('search')}<input class="input" id="q" type="search" placeholder="Ism, guruh yoki HEMIS ID" value="${esc(st.q)}" aria-label="Qidirish"></div>
      <div class="seg" id="flt">${FILTERS.map(([k, l, i]) => `<button data-f="${k}" class="${st.f === k ? 'on' : ''}">${ic(i)}${l}<span class="n">${rows.filter(r => matchFilter(r, k)).length}</span></button>`).join('')}</div>
      ${st.all ? `<select class="select" id="crs" aria-label="Kurs"><option value="">Barcha kurslar</option>${courses.map(([k, t]) => `<option value="${esc(k)}" ${k === st.c ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select>` : ''}
      <select class="select" id="grp" aria-label="Guruh"><option value="">Barcha guruhlar</option>${groups.map(g => `<option ${g === st.g ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select>
      <span class="grow"></span><span class="count" id="cnt"></span>
    </div>
    <section class="sec"><div class="tbl-wrap" id="tw"></div></section>`);
  const draw = () => {
    const qq = norm(st.q);
    let list = rows.filter(r => matchFilter(r, st.f) && (!st.g || r.group === st.g) && (!st.all || !st.c || r.course === st.c) &&
      (!qq || norm(r.name).includes(qq) || norm(r.group).includes(qq) || norm(r.hemis_id) === qq));
    const key = st.sort, dir = st.dir;
    const val = r => key === 'debts' ? r.debts.length : key === 'action' ? (r.action || '') : r[key];
    list = list.slice().sort((a, b) => {
      const x = val(a), y = val(b);
      if (x == null && y == null) return a.name.localeCompare(b.name);
      if (x == null) return 1; if (y == null) return -1;
      const c = typeof x === 'string' ? x.localeCompare(y) : x - y;
      return c * dir || a.name.localeCompare(b.name);
    });
    $('#cnt').textContent = `${list.length} ta talaba`;
    $('#tw').innerHTML = list.length ? `<table class="tbl"><thead><tr>${cols.map(([k, l, c]) =>
      `<th class="sort ${c || ''}" data-sort="${k}" aria-sort="${key === k ? (dir > 0 ? 'ascending' : 'descending') : 'none'}">${COL_IC[k] ? `<span class="th-i">${ic(COL_IC[k])}</span>` : ''}${l}${key === k ? `<span class="arr">${dir > 0 ? '▲' : '▼'}</span>` : ''}</th>`).join('')}</tr></thead>
      <tbody>${list.map(r => stuRow(r, st.all)).join('')}</tbody></table>`
      : emptyBox('search', 'Hech kim topilmadi', 'Qidiruv so‘zini yoki filtrni o‘zgartiring.');
  };
  draw();
  $('#q').addEventListener('input', e => { st.q = e.target.value; draw(); });
  $('#grp').addEventListener('change', e => { st.g = e.target.value; draw(); });
  $('#crs')?.addEventListener('change', e => { st.c = e.target.value; st.g = ''; route(); });
  $('#scope')?.addEventListener('click', e => { const b = e.target.closest('[data-s]'); if (!b) return; st.all = b.dataset.s === '1'; st.c = ''; st.g = ''; route(); });
  $('#flt').addEventListener('click', e => { const b = e.target.closest('[data-f]'); if (!b) return; st.f = b.dataset.f; if (st.f === 'acad') { st.sort = 'debts'; st.dir = -1; } $$('#flt button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
  $('#tw').addEventListener('click', e => { const th = e.target.closest('[data-sort]'); if (!th) return;
    const k = th.dataset.sort; st.dir = st.sort === k ? -st.dir : (['name', 'group', 'action'].includes(k) ? 1 : -1); st.sort = k; draw(); });
}
function pctCell(p) {
  if (p == null) return '<span class="dash">—</span>';
  const c = p >= 90 ? 'var(--ok)' : p >= 75 ? 'var(--warn)' : 'var(--bordo-600)';
  return `<div class="pct"><span class="bar"><i style="width:${p}%;background:${c}"></i></span><b>${p}%</b></div>`;
}
function stuRow(r, all = false) {
  const dash = '<span class="dash">—</span>';
  return `<tr class="click" data-student="${r.id}"${all ? ` data-course="${esc(r.course)}"` : ''}>
    <td class="name"><b>${esc(r.name)}</b><span>${r.hemis_id ? 'HEMIS ' + esc(r.hemis_id) : ''}</span></td>${all ? `<td class="nowrap">${esc(r.course_title)}</td>` : ''}
    <td class="nowrap">${esc(r.group)}</td>
    <td>${pctCell(r.percent)}${r.counted_hours ? `<div class="sub-l">sababsiz ${num(r.counted_hours / 2)} para</div>` : ''}</td>
    <td>${r.action ? `<span class="chip bordo act">${esc(r.action)}</span>` : dash}</td>
    <td>${r.debts.length ? `<div class="debts" title="${esc(r.debts.join(', '))}"><span class="chip bordo">${r.debts.length} fan</span><span class="sub">${esc(r.debts.join(', '))}</span></div>` : dash}</td>
    <td class="r">${r.gpa != null ? (r.flags.gpa ? `<span class="gpa-low" title="Kursdan kursga o‘tmaydi">${ic('alert')}${gpaFmt(r.gpa)}</span>` : gpaFmt(r.gpa)) : dash}</td>
    <td class="r nowrap">${r.kontrakt ? `<span class="money" title="Kontrakt qarzi: ${money(r.kontrakt)}">${ic('dollar')}${mlnPlain(r.kontrakt)}</span>` : dash}</td>
    <td class="r nowrap">${r.trimestr ? `<span class="money" title="Trimestr qarzi: ${money(r.trimestr)}">${ic('receipt')}${mlnPlain(r.trimestr)}</span>` : dash}</td>
    <td class="r"><span class="cnt ${r.problems >= 3 ? 'bordo' : r.problems ? '' : 'zero'}">${r.problems || 0}</span></td></tr>`;
}

/* ---------------------------------------------------------------- talaba kartasi (yon panel) */
function closeDrawer() {
  $('#drawer')?.classList.remove('on'); $('#scrim')?.classList.remove('on');
  $('#drawer')?.setAttribute('aria-hidden', 'true');
}
async function openStudent(id, course = null) {
  const dr = $('#drawer'); if (!dr) return;
  $('#dbody').innerHTML = skel(170) + skel(90, 2);
  dr.classList.add('on'); $('#scrim').classList.add('on'); dr.setAttribute('aria-hidden', 'false');
  let d;
  try { d = await api(`/api/staff/student/${id}`, { course }); } catch (e) { $('#dbody').innerHTML = emptyBox('alert', 'Talaba ma’lumotini yuklab bo‘lmadi'); return; }
  const c = d.child, a = d.attendance, k = d.pays.kontrakt || {}, t = d.pays.trimestr || {};
  const payLine = (label, p) => p.state === 'grant' ? `<span>${label}</span><b>Davlat granti</b>`
    : p.state === 'none' ? `<span>${label}</span><b class="dash">ma’lumot yo‘q</b>`
    : p.state === 'clear' ? `<span>${label}</span><b style="color:var(--ok)">qarz yo‘q</b>`
    : `<span>${label}</span><b style="color:var(--warn)">${money(p.debt)}${p.days_left != null ? ` · ${p.days_left >= 0 ? p.days_left + ' kun qoldi' : 'muddat o‘tgan'}` : ''}</b>`;
  const ladder = a ? `<div class="ladder">${a.levels.map((l, i) => `<div class="${i <= a.level ? 'hit' : i === a.level + 1 ? 'next' : ''}">
      <b>${num(l.hours / 2)} para</b>${esc(l.action)}</div>`).join('')}</div>` : '';
  $('#dbody').innerHTML = `
    <div class="idc"><small>Jahon iqtisodiyoti va diplomatiya universiteti</small><h3>${esc(c.name)}</h3>
      <dl><dt>Guruh</dt><dd>${esc(c.group)}</dd><dt>Kurs</dt><dd>${esc(c.year ? c.year + '-kurs' : '—')}</dd><dt>Fakultet</dt><dd>${esc(c.faculty || '—')}</dd></dl>
      <div class="tags">${c.hemis_id ? `<span>HEMIS ${esc(c.hemis_id)}</span>` : ''}${c.payment_form ? `<span>${esc(c.payment_form)}</span>` : ''}</div></div>
    ${d.issues && d.issues.length ? `<div class="note bordo">${ic('alert')}<span><b>${d.issues.length} ta masala:</b><br>${d.issues.map(safeHtml).join('<br>')}</span></div>`
      : `<div class="note ok">${ic('ok')}<span>Hammasi joyida — davomat, baholar va to‘lovlar bo‘yicha masala yo‘q.</span></div>`}
    <div class="mini">
      <div><div class="k">Davomat</div><div class="v">${a && a.percent != null ? a.percent + '%' : '—'}</div><div class="s">${a ? 'sababsiz: ' + pairs(a.counted_hours) : 'ma’lumot yo‘q'}</div></div>
      <div><div class="k">GPA${d.gpa_low ? ` <span class="chip bordo" style="height:20px">${limNum(d.gpa_min)} dan past — kursdan o‘tmaydi</span>` : ''}</div><div class="v">${d.gpa != null ? gpaFmt(d.gpa) : '—'}<small style="font-size:14px;color:var(--muted)"> / 5</small></div><div class="s">${d.academic.count ? d.academic.count + ' ta akademik qarz' : 'akademik qarz yo‘q'}</div></div>
    </div>
    ${a ? `<div class="box"><h4>Dars qoldirish chegaralari</h4><div class="kv"><span>Sababsiz</span><b>${pairs(a.counted_hours)}</b>
      <span>Sababli</span><b>${pairs(a.excused_hours)}</b>${a.next ? `<span>Keyingi chegaragacha</span><b>${pairs(a.next.left_hours)}</b>` : ''}</div>${ladder}</div>` : ''}
    ${d.academic.count ? `<div class="box"><h4>Akademik qarzlar — ${d.academic.count} ta fan</h4><div class="kv">${d.academic.debts.map(x =>
      `<span>${esc(x.subject)}${x.semester ? ` (${esc(x.semester)}-semestr)` : ''}</span><b style="color:var(--bordo-600)">${x.source === 'hemis'
        ? `${x.credits ? num(x.credits) + ' kredit · ' : ''}HEMIS ro‘yxati` : `${x.score != null ? num(x.score) + ' ball' : ''} «${esc(x.grade || 2)}»`}</b>`).join('')}</div></div>` : ''}
    <div class="box"><h4>To‘lovlar</h4><div class="kv">${payLine('Kontrakt', k)}${payLine('Trimestr', t)}</div></div>
    ${d.trend ? `<div class="box"><h4>Dinamika</h4><div>${safeHtml(String(d.trend).replace(/^📈\s*/, ''))}</div></div>` : ''}
    <div class="box"><h4>Ota-onalar</h4>${d.parents.length ? d.parents.map(p => `<div class="parent">
        <div class="t"><b>${esc(p.tg_name || 'Ota-ona')}</b><span>${esc(fmtPhone(p.phone))}${p.lang && p.lang !== 'uz' ? `, ${LANG[p.lang]} tilida` : ''}${p.active ? '' : ', botdan chiqqan'}</span></div>
        ${p.active ? `<a class="btn sm" href="#/inbox/${id}/${p.tg_id}"${course ? ` data-course="${esc(course)}"` : ''}>${ic('chat')} Yozish</a>` : ''}</div>`).join('')
      : `<div class="hint">Ota-onasi hali botga ulanmagan.</div>`}</div>`;
  $('#drawer header b').textContent = c.name;
}

/* ================================================================ xabarlar */
async function pInbox(parts) {
  document.title = 'Xabarlar — Boshqaruv paneli';
  const sid = Number(parts[1]) || null, pid = Number(parts[2]) || null;
  view(head('Xabarlar', courseSub()) + `<div class="split"><div class="threads"><div class="search">${ic('search')}
      <input class="input" id="q" type="search" placeholder="Ota-ona yoki talaba" aria-label="Suhbatlarni qidirish"></div><ul class="list" id="tl"></ul></div>
    <section class="convo" id="cv">${emptyBox('chat', 'Suhbatni tanlang', 'Chap tomondagi ro‘yxatdan ota-onani tanlang.')}</section></div>`);
  let items = [], filter = '';
  const drawList = () => {
    const f = norm(filter);
    const list = items.filter(i => !f || norm(i.parent).includes(f) || norm(i.student).includes(f));
    $('#tl').innerHTML = list.length ? list.map(i => `<li><a href="#/inbox/${i.sid}/${i.pid}" class="${i.sid === sid && i.pid === pid ? 'on' : ''}">
        <span class="av">${esc(initials(i.parent))}</span><div class="t"><b><span>${esc(i.parent)}</span><time>${shortWhen(i.at)}</time></b>
        <span>${esc(i.student)}, ${esc(i.group || '')}</span><p class="${i.unread ? 'unread' : ''}">${i.last_sender === 'staff' ? 'Siz: ' : ''}${esc(i.last)}</p></div>
        ${i.unread ? `<i class="badge" style="margin-top:8px">${i.unread}</i>` : ''}</a></li>`).join('')
      : `<li>${emptyBox('chat', items.length ? 'Topilmadi' : 'Hali xabar yo‘q', items.length ? '' : 'Ota-onalar ilova yoki bot orqali yozgan savollar shu yerda ko‘rinadi.')}</li>`;
  };
  const loadList = async () => { items = (await api('/api/staff/inbox')).items; drawList(); };
  $('#q').addEventListener('input', e => { filter = e.target.value; drawList(); });
  await loadList();
  if (sid && pid) {
    await openThread(sid, pid);
    items.forEach(i => { if (i.sid === sid && i.pid === pid) i.unread = 0; });
    drawList(); refreshBadges();
  }
  S.inboxRefresh = async () => { try { await loadList(); if (sid && pid) await openThread(sid, pid, true); refreshBadges(); } catch (e) { /* jim */ } };
  S.timers.push(setInterval(S.inboxRefresh, 20000));
}
async function openThread(sid, pid, quiet = false) {
  const cv = $('#cv'); if (!cv) return;
  const d = await api(`/api/staff/thread/${sid}/${pid}`);
  const box = $('#msgs');
  const atBottom = !box || box.scrollHeight - box.scrollTop - box.clientHeight < 60;
  const draft = $('#reply')?.value || '';
  let lastDay = '';
  const msgs = d.messages.map(m => {
    const day = when(m.at, false);
    const sep = day !== lastDay ? `<div class="day">${esc(day)}</div>` : '';
    lastDay = day;
    const t = parseDate(m.at)?.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) || '';
    return sep + `<div class="bub ${m.sender === 'staff' ? 'out' : 'in'}">${m.sender === 'staff' && m.author ? `<em>${esc(m.author)}</em>` : ''}${esc(m.text)}<small>${t}</small></div>`;
  }).join('');
  const lang = d.lang && d.lang !== 'uz' ? `<div class="note warn langhint" style="margin:12px 20px 0">${ic('info')}<span>Ota-ona <b>${LANG[d.lang]}</b> tilida — javobni ${LANG[d.lang]} tilida yozing.</span></div>` : '';
  cv.innerHTML = `<header><span class="av" style="width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:var(--bordo-600);color:#fff;font-weight:700">${esc(initials(d.parent))}</span>
      <div class="t"><b>${esc(d.parent || 'Ota-ona')}</b><span>${esc(d.student)}, ${esc(d.group || '')}${d.phone ? ' — ' + esc(fmtPhone(d.phone)) : ''}</span></div>
      <button class="btn sm" data-student="${sid}">${ic('users')} Talaba kartasi</button></header>${lang}
    <div class="msgs" id="msgs">${msgs || emptyBox('chat', 'Xabarlar yo‘q')}</div>
    <form class="composer" id="cf"><textarea class="textarea" id="reply" rows="1" placeholder="Javob yozing… (Ctrl+Enter — yuborish)" aria-label="Javob">${esc(draft)}</textarea>
      <button class="btn primary" type="submit">${ic('send')} Yuborish</button></form>`;
  const nb = $('#msgs');
  if (!quiet || atBottom) nb.scrollTop = nb.scrollHeight;
  const ta = $('#reply');
  const fit = () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 180) + 'px'; };
  ta.addEventListener('input', fit); fit();
  ta.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $('#cf').requestSubmit(); } });
  $('#cf').addEventListener('submit', async e => {
    e.preventDefault();
    const text = ta.value.trim(); if (!text) return;
    const btn = e.submitter || $('#cf button'); btn.disabled = true;
    try {
      await api(`/api/staff/thread/${sid}/${pid}`, { method: 'POST', json: { text } });
      ta.value = ''; toast('Javob yuborildi — ota-onaga bot xabari bo‘lib boradi');
      await openThread(sid, pid); refreshBadges();
    } catch (err) { toast('Javob yuborilmadi: ' + (err.data?.error || err.message), true); btn.disabled = false; }
  });
  if (!quiet) ta.focus();
}

/* ================================================================ bog'lanish so'rovlari */
async function pRequests() {
  document.title = 'So‘rovlar — Boshqaruv paneli';
  view(head('So‘rovlar', courseSub()) + skel(300));
  const d = await api('/api/staff/requests');
  view(head('Bog‘lanish so‘rovlari', courseSub(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + `
    <p class="hint" style="margin:-10px 0 18px">Telefon raqami bazada topilmagan ota-onalar farzandini qo‘lda bog‘lashni so‘raydi. Ota-ona yozgan ma’lumotni talaba ma’lumoti bilan solishtiring. Talaba o‘zi tasdiqlagan so‘rovlar yuqorida — kim tasdiqlaganini tekshiring; yakuniy tasdiq sizda.</p>
    <section class="sec">${d.items.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Ota-ona</th><th>So‘ralgan talaba</th><th>Ota-ona yozgan</th><th>Talaba tasdig‘i</th><th>Vaqt</th><th class="r">Qaror</th></tr></thead>
      <tbody>${d.items.map(r => `<tr>
        <td class="name"><b>${esc(r.parent_name || 'Ota-ona')}</b><span>${esc(fmtPhone(r.phone))}${r.lang !== 'uz' ? `, ${LANG[r.lang]} tilida` : ''}</span>
          ${r.blocked ? '<div><span class="chip bordo">talaba deb bloklangan</span></div>' : ''}</td>
        <td class="name">${r.student ? `<b>${esc(r.student.name)}</b><span>${esc(r.student.group)}${r.student.hemis_id ? ', HEMIS ' + esc(r.student.hemis_id) : ''}</span>` : '<span class="dash">topilmadi</span>'}</td>
        <td>${esc(r.note)}</td><td style="max-width:240px">${r.student_ok ? `<span class="chip ok" title="${esc(when(r.student_ok.at))}">✅ Talaba tasdiqladi</span><div class="small" style="margin-top:4px">${esc(r.student_ok.tg_name || '—')}</div><div class="small muted">${esc(fmtPhone(r.student_ok.phone))}</div>${r.student_ok.source === 'parent' ? '<div style="margin-top:4px"><span class="chip warn" title="Raqam bazada yo‘q — uni ota-ona kiritgan. Talabaniki ekanini tekshiring">⚠️ raqamni ota-ona kiritgan</span></div>' : ''}` : r.student_can_confirm ? `<span class="dash">⏳ hali tasdiqlamagan</span>${r.claimed_phone ? `<div class="small muted">ota-ona kiritgan: ${esc(fmtPhone(r.claimed_phone))}</div>` : ''}` : '<span class="dash">talaba raqami bazada yo‘q</span>'}</td><td style="white-space:nowrap">${when(r.at)}</td>
        <td class="r" style="white-space:nowrap"><button class="btn sm primary" data-act="req" data-id="${r.id}" data-ok="1" ${r.blocked ? 'disabled title="Avval botda /bloklar orqali ruxsat bering"' : ''}>${ic('ok')} Tasdiqlash</button>
          <button class="btn sm danger" data-act="req" data-id="${r.id}" data-ok="0">Rad etish</button></td></tr>`).join('')}</tbody></table></div>`
      : emptyBox('req', 'Kutilayotgan so‘rov yo‘q', 'Yangi so‘rov kelganda bot sizga ham xabar beradi.')}</section>`);
}

/* ================================================================ e'lon */
const SEC_RX = /^[ \t]*(?:-{2,}|#)[ \t]*(uz|ru|en)[ \t]*$|^[ \t]*(🇺🇿|🇷🇺|🇬🇧)[ \t]*$/gmiu;
const FLAG = { '🇺🇿': 'uz', '🇷🇺': 'ru', '🇬🇧': 'en' };
function sections(text) {  // serverdagi loc.sections bilan bir xil
  const marks = [...String(text || '').matchAll(SEC_RX)];
  if (!marks.length) return { uz: String(text || '').trim() };
  const out = { uz: text.slice(0, marks[0].index).trim() };
  marks.forEach((m, i) => {
    const lang = (m[1] || FLAG[m[2]] || 'uz').toLowerCase();
    const end = i + 1 < marks.length ? marks[i + 1].index : text.length;
    out[lang] = text.slice(m.index + m[0].length, end).trim();
  });
  return Object.fromEntries(Object.entries(out).filter(([, v]) => v));
}
async function pAnnounce() {
  document.title = 'E’lon — Boshqaruv paneli';
  const { rows } = await loadStudents();
  const groups = [...new Set(rows.map(r => r.group).filter(Boolean))].sort();
  const sel = new Set();
  let tab = 'uz';
  view(head('E’lon yuborish', courseSub()) + `<div class="cols">
    <section class="sec"><header>${H('edit', 'Matn', 'people')}</header><div class="pad">
      <label class="field"><span>E’lon</span><textarea class="textarea" id="txt" rows="12" placeholder="Ota-onalar yig‘ilishi shanba kuni soat 10:00 da bo‘lib o‘tadi.
---ru
Родительское собрание состоится в субботу в 10:00."></textarea>
        <small class="hint">Rus va ingliz tilidagi ota-onalar uchun alohida qatorga <b>---ru</b> yoki <b>---en</b> yozib, tarjimani qo‘shing — har bir ota-ona o‘z tilidagi qismni oladi.</small></label>
      ${S.me.role === 'super' ? `<div class="field"><span>Qaysi kurslarga</span><div class="seg" id="scopeA"><button data-a="0" class="on">«${esc(S.me.staff.title || 'Joriy kurs')}» kursi</button><button data-a="1">Barcha kurslar</button></div></div>` : ''}
      <div class="field" id="grpField"><span>Kimga</span><div class="groups" id="grps"><button data-g="" class="on">${myGroups().length ? 'Barcha guruhlarim' : 'Butun kurs'}</button>${groups.map(g => `<button data-g="${esc(g)}">${esc(g)}</button>`).join('')}</div></div>
      <button class="btn primary" id="send">${ic('send')} E’lonni yuborish</button></div></section>
    <section class="sec"><header>${H('chat', 'Ota-ona nimani ko‘radi', 'msg')}</header><div class="pad">
      <div class="tabs" id="tabs"><button data-l="uz" class="on">O‘zbekcha</button><button data-l="ru">Русский</button><button data-l="en">English</button></div>
      <div class="tg"><div class="bub" id="pv"></div></div><div id="pvn" style="margin-top:12px"></div></div></section></div>`);
  const draw = () => {
    const text = $('#txt').value, sec = sections(text), own = sec[tab];
    const shown = own || sec.uz || '';
    $('#pv').innerHTML = shown ? `📢 ${esc(shown)}` : '<span class="dash">Matn hali yozilmagan</span>';
    $('#pvn').innerHTML = tab === 'uz' || own || !text.trim() ? '' : `<div class="note warn">${ic('info')}<span>${tab === 'ru'
      ? 'Ruscha qism yozilmagan — rus tilidagi ota-onalar o‘zbekcha matnni kirill harflarida oladi.'
      : 'Inglizcha qism yozilmagan — ingliz tilidagi ota-onalar o‘zbekcha matnni oladi.'}</span></div>`;
  };
  $('#txt').addEventListener('input', draw); draw();
  $('#tabs').addEventListener('click', e => { const b = e.target.closest('[data-l]'); if (!b) return; tab = b.dataset.l; $$('#tabs button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
  $('#grps').addEventListener('click', e => {
    const b = e.target.closest('[data-g]'); if (!b) return;
    const g = b.dataset.g;
    if (!g) sel.clear(); else sel.has(g) ? sel.delete(g) : sel.add(g);
    $$('#grps button').forEach(x => x.classList.toggle('on', x.dataset.g ? sel.has(x.dataset.g) : !sel.size));
  });
  let allCourses = false;
  $('#scopeA')?.addEventListener('click', e => {
    const b = e.target.closest('[data-a]'); if (!b) return;
    allCourses = b.dataset.a === '1';
    $$('#scopeA button').forEach(x => x.classList.toggle('on', x === b));
    $('#grpField').style.display = allCourses ? 'none' : '';  // guruhlar — faqat bitta kurs ichida
  });
  $('#send').addEventListener('click', async e => {
    const btn = e.currentTarget;  // kutishdan (await) keyin e.currentTarget bo'sh bo'ladi — oldindan olinadi
    const text = $('#txt').value.trim();
    if (!text) { toast('Avval e’lon matnini yozing', true); $('#txt').focus(); return; }
    const course = S.me.staff.title || 'joriy kurs';
    const who = allCourses ? '<b>barcha kurslarning</b> ota-onalariga' : sel.size ? `«${esc(course)}» kursining <b>${esc([...sel].join(', '))}</b> guruh${sel.size > 1 ? 'lar' : ''}i ota-onalariga` : `«<b>${esc(course)}</b>» kursining butun ota-onalariga`;
    if (!await confirmDlg('E’lonni yuborasizmi?', `E’lon ${who} Telegram orqali yuboriladi. Yuborilgan e’lonni qaytarib bo‘lmaydi.`, 'Yuborish')) return;
    btn.disabled = true;
    try {
      const r = allCourses ? await api('/api/super/announce', { method: 'POST', json: { text } })
        : await api('/api/staff/announce', { method: 'POST', json: { text, groups: [...sel] } });
      toast(r.recipients ? `E’lon yuborildi: ${r.sent} ta ota-onaga (jami ${r.recipients})${allCourses ? ', barcha kurslar' : r.course ? ', «' + r.course + '»' : ''}`
        : `Bu ${allCourses ? 'kurslarda' : 'kursda'} botga ulangan ota-ona yo‘q — e’lon hech kimga yuborilmadi`, !r.recipients);
      $('#txt').value = ''; draw();
    } catch (err) { toast('E’lon yuborilmadi: ' + err.message, true); }
    $('#send').disabled = false;
  });
}

/* ================================================================ ma'lumot yuklash va hisobot */
const KINDS = [['auto', 'Turini bot aniqlasin'], ['students', 'Talabalar'], ['attendance', 'Davomat (kunlik)'], ['attendance_stats', 'Davomat (HEMIS statistikasi)'],
  ['schedule', 'Dars jadvali'], ['grades', 'Baholar'], ['enroll', 'Tanlov fanlari va 2-til: kim o‘qiydi'], ['elsched', 'Tanlov fanlari va 2-til: jadval'],
  ['debts', 'Kontrakt qarzdorligi'], ['debts_t', 'Trimestr qarzdorligi'], ['acad_debts', 'Akademik qarzdorlar (HEMIS ro‘yxati)'], ['phones', 'Talaba telefonlari'], ['translations', 'Tarjimalar']];
const SECTIONS_EXP = [['all', 'To‘liq hisobot'], ['prob', 'Muammoli talabalar'], ['att', 'Davomati past talabalar'], ['acad', 'Akademik qarzdorlar'],
  ['kontrakt', 'Kontrakt qarzdorlari'], ['trimestr', 'Trimestr qarzdorlari']];
async function pFiles() {
  document.title = 'Ma’lumot va hisobot — Boshqaruv paneli';
  view(head('Ma’lumot va hisobot', courseSub()) + `<div class="cols">
    <section class="sec"><header>${H('upload', 'Excel fayllarni yuklash', 'att')}</header><div class="pad">
      <label class="dz" id="dz"><input type="file" id="files" accept=".xlsx,.xlsm" multiple hidden>
        <span class="ic">${ic('upload')}</span><b>Fayllarni shu yerga tashlang</b><span>yoki bosib tanlang — .xlsx, bir nechta faylni birga</span></label>
      <div class="toolbar" style="margin:16px 0 0"><label class="field" style="margin:0;flex:1"><span>Fayl turi</span>
        <select class="select" id="kind">${KINDS.map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select></label></div>
      <label class="switch" style="margin-top:14px"><span><b style="font-weight:600">Ota-onalarga xabar yubormaslik</b><br><span class="hint">Eski ma’lumotni qayta yuklaganda yoki tuzatish kiritganda</span></span><input type="checkbox" id="silent"></label>
      <ul class="queue" id="queue"></ul>
      <p class="hint" style="margin-top:14px">HEMIS va buxgalteriya fayllari o‘zgartirilmasdan yuklanadi. Namunalar: botda «📑 Shablonlar».</p></div></section>
    <section class="sec"><header>${H('download', 'Hisobot', 'people')}</header><div class="pad">
      <div class="radio" style="margin-bottom:14px"><label><input type="radio" name="fmt" value="x" checked><span><b>Excel</b><span>har bo‘lim alohida varaqda, jami — formulalar bilan</span></span></label>
        <label><input type="radio" name="fmt" value="p"><span><b>PDF</b><span>dekanat yig‘ilishi va rahbariyat uchun</span></span></label></div>
      <label class="field"><span>Bo‘lim</span><select class="select" id="sec">${SECTIONS_EXP.map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select></label>
      <div class="actions"><button class="btn primary" id="dl">${ic('download')} Yuklab olish</button>
        <button class="btn" id="tgsend">${ic('telegram')} Telegram chatimga yuborish</button></div></div></section></div>
    <section class="sec" style="margin-top:22px"><header>${H('layers', 'Yuklangan fayllar', 'people')}<span class="hint">${S.me.role === 'super' ? 'barcha koordinatorlar' : 'siz yuklaganlar'}</span></header><div id="imports">${skel(80)}</div></section>`);
  loadImports();
  const dz = $('#dz');
  ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('over'); }));
  dz.addEventListener('drop', e => upload([...e.dataTransfer.files]));
  $('#files').addEventListener('change', e => { upload([...e.target.files]); e.target.value = ''; });
  const expPath = () => `fmt=${$('input[name=fmt]:checked').value}&s=${$('#sec').value}`;
  $('#dl').addEventListener('click', async e => {
    e.currentTarget.disabled = true;
    try { toast('Hisobot yuklab olindi: ' + await download('/api/staff/export?' + expPath())); } catch (err) { toast('Hisobot tayyorlanmadi', true); }
    $('#dl').disabled = false;
  });
  $('#tgsend').addEventListener('click', async e => {
    e.currentTarget.disabled = true;
    try { await api('/api/staff/export/send?' + expPath(), { method: 'POST' }); toast('Hisobot Telegram chatingizga yuborildi'); } catch (err) { toast('Yuborilmadi', true); }
    $('#tgsend').disabled = false;
  });
}
async function upload(files, force = null) {
  files = files.filter(f => /\.xls[xm]$/i.test(f.name));
  if (!files.length) { toast('Faqat .xlsx fayllarni yuklash mumkin', true); return; }
  const q = $('#queue');
  for (const file of files) {
    const li = document.createElement('li');
    li.innerHTML = `<div class="qh"><span class="spin"></span><b>${esc(file.name)}</b><span class="chip muted">yuklanmoqda</span></div>`;
    q.prepend(li);
    const fd = new FormData();
    fd.append('file', file); fd.append('kind', force || $('#kind').value);
    if (force) fd.append('force', '1');
    if ($('#silent').checked) fd.append('caption', 'jim');
    let r;
    try { r = await api('/api/staff/import', { method: 'POST', body: fd }); }
    catch (err) { li.innerHTML = `<div class="qh">${ic('alert')}<b>${esc(file.name)}</b><span class="chip bordo">xato</span></div><div class="rep">${esc(err.data?.error || err.message)}</div>`; continue; }
    if (r.state === 'confirm') {
      li.innerHTML = `<div class="qh">${ic('alert')}<b>${esc(file.name)}</b><span class="chip warn">turi mos emas</span></div>
        <div class="rep">Faylda «${esc(r.detected_title)}» fayliga xos ustunlar bor, siz «${esc(r.kind_title)}» ni tanladingiz.
        <div class="row"><button class="btn sm primary" data-re="${esc(r.detected)}">«${esc(r.detected_title)}» sifatida yuklash</button>
        <button class="btn sm" data-re="${esc($('#kind').value)}">Baribir yuklash</button></div></div>`;
      li.querySelectorAll('[data-re]').forEach(b => b.addEventListener('click', () => { li.remove(); upload([file], b.dataset.re); }));
      continue;
    }
    if (r.state === 'choose') {
      li.innerHTML = `<div class="qh">${ic('alert')}<b>${esc(file.name)}</b><span class="chip warn">tur aniqlanmadi</span></div>
        <div class="rep">Fayl turini ro‘yxatdan tanlang va faylni qayta yuklang.</div>`;
      continue;
    }
    const good = r.state === 'done';
    li.innerHTML = `<div class="qh">${ic(good ? 'ok' : 'alert')}<b>${esc(file.name)}</b><span class="chip ${good ? 'ok' : 'bordo'}">${esc(r.kind_title || '')}</span></div>
      <div class="rep">${safeHtml(r.report)}</div>`;
    S.stu = null;
  }
  refreshBadges(); loadImports();
}
/* Yuklangan fayllar: o'chirilsa — shu fayldan kelgan ma'lumot, ota-onalarga ketgan bildirishnoma va xabarlar ham */
async function loadImports() {
  const box = document.getElementById('imports'); if (!box) return;
  let d; try { d = await api('/api/staff/imports'); } catch (e) { box.innerHTML = `<div class="pad hint">Ro‘yxat yuklanmadi</div>`; return; }
  box.innerHTML = d.items.length ? `<div class="tbl-wrap" style="max-height:420px"><table class="tbl"><thead><tr><th>Fayl</th><th>Turi</th><th class="r">Yozuvlar</th><th class="r">Ota-onalarga xabar</th><th>Kim, qachon</th><th></th></tr></thead><tbody>
    ${d.items.map(x => `<tr><td class="name"><b>${esc(x.file_name || '—')}</b></td><td>${esc(x.kind_title)}</td><td class="r">${x.deletable ? x.rows : '<span class="dash">—</span>'}</td><td class="r">${x.parents || '<span class="dash">—</span>'}</td>
      <td>${esc(x.by || '')}${x.by ? ', ' : ''}${when(x.at)}</td>
      <td class="r">${x.deletable ? `<button class="btn sm ghost" data-act="imp-del" data-id="${x.id}" data-name="${esc(x.file_name || '')}" data-rows="${x.rows}" data-parents="${x.parents}" data-kind="${esc(x.kind)}" data-linked="${x.linked_parents || 0}" title="O‘chirish" aria-label="O‘chirish">${ic('x')}</button>` : '<span class="hint" title="Talabalar telefonlari va tarjimalar fayllari o‘chirilmaydi">o‘chirilmaydi</span>'}</td></tr>`).join('')}</tbody></table></div>`
    : `<div class="pad">${emptyBox('upload', 'Hali fayl yuklanmagan', '')}</div>`;
}
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act="imp-del"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const stu = b.dataset.kind === 'students';
  const text = stu
    ? (Number(b.dataset.rows) ? `<b>${esc(b.dataset.name)}</b> — talabalar ro‘yxati. Shu fayl orqali kelgan <b>${b.dataset.rows} ta talaba</b> va ularning barcha ma’lumotlari (davomat, baholar, to‘lovlar, hujjatlar, yozishmalar) o‘chadi; <b>${b.dataset.linked} ta ota-ona</b> ulardan uziladi. Keyingi fayllarda qayta kelgan talabalar qoladi. Buni qaytarib bo‘lmaydi.`
      : `<b>${esc(b.dataset.name)}</b> dagi talabalarning hammasi keyingi fayllarda qayta kelgan — o‘chiriladigan talaba yo‘q. Fayl faqat ro‘yxatdan olib tashlanadi.`)
    : `<b>${esc(b.dataset.name)}</b> dan kelgan ${b.dataset.rows} ta yozuv o‘chiriladi.${Number(b.dataset.parents) ? ` ${b.dataset.parents} ta ota-onaga ketgan bildirishnomalar ilovadan, xabarlar Telegram chatidan (48 soat ichida) ham o‘chiriladi.` : ''} Buni qaytarib bo‘lmaydi.`;
  if (!await confirmDlg(stu ? 'Talabalar ro‘yxatini o‘chirasizmi?' : 'Faylni tizimdan o‘chirasizmi?', text, 'O‘chirish', true)) return;
  b.disabled = true;
  try {
    const r = await api(`/api/staff/imports/${b.dataset.id}`, { method: 'DELETE' });
    toast(`O‘chirildi: ${r.students ? r.students + ' ta talaba, ' : ''}${r.rows} ta yozuv, ${r.notifications} ta bildirishnoma, ${r.messages} ta Telegram xabar` + (r.messages_failed ? ` (${r.messages_failed} tasini Telegram o‘chirishga ruxsat bermadi)` : ''));
    S.stu = null; loadImports(); refreshBadges();
  } catch (err) { toast(err.status === 403 ? 'Faqat o‘zingiz yuklagan faylni o‘chira olasiz' : 'O‘chirilmadi', true); b.disabled = false; }
}, true);


/* ================================================================ rasmiy hujjat yuborish */
const DOC_KINDS = [['tushuntirish', 'Tushuntirish xati', 'dekan nomiga'], ['ogohlantirish', 'Dekan ogohlantirishi', 'intizomiy'],
  ['hayfsan', 'Hayfsan', 'buyruq'], ['boshqa', 'Rasmiy hujjat', 'boshqa turdagi']];
async function pDocs() {
  document.title = 'Hujjat yuborish — Boshqaruv paneli';
  if (S.docJob && S.docJob.course !== S.course) S.docJob = null;
  const j = S.docJob;
  if (!j) {
    view(head('Rasmiy hujjat yuborish', courseSub()) + `<div class="cols">
      <section class="sec"><header>${H('file', 'PDF hujjat', 'acad')}</header><div class="pad">
        <label class="dz" id="dz"><input type="file" id="pdf" accept="application/pdf,.pdf" hidden>
          <span class="ic">${ic('file')}</span><b>PDF faylni shu yerga tashlang</b><span>yoki bosib tanlang — buyruq, ogohlantirish, hayfsan</span></label>
        <div id="dzs" style="margin-top:14px"></div></div></section>
      <section class="sec"><header>${H('info', 'Qanday ishlaydi', 'people')}</header><div class="pad"><ol class="steps-l">
        <li>Hujjat o‘qiladi va undagi talabalar avtomatik topiladi — kerak bo‘lsa qo‘lda qo‘shasiz.</li>
        <li>Har bir talaba uchun alohida nusxa tayyorlanadi: boshqa talabalarning F.I.Sh., guruhi va ID si qora rang bilan yopiladi.</li>
        <li>Nusxalarni ko‘rib chiqasiz, hujjat turini tanlaysiz va yuborasiz.</li>
        <li>Ota-onaga qisqa xabar boradi, hujjat ilovaning o‘zida ochiladi.</li></ol></div></section></div>`);
    const dz = $('#dz');
    ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('over'); }));
    dz.addEventListener('drop', e => e.dataTransfer.files[0] && uploadPdf(e.dataTransfer.files[0]));
    $('#pdf').addEventListener('change', e => e.target.files[0] && uploadPdf(e.target.files[0]));
    return;
  }
  const n = j.sel.size;
  view(head('Rasmiy hujjat yuborish', courseSub(), `<button class="btn" data-act="doc-reset">${ic('file')} Boshqa hujjat</button>`) + `<div class="cols">
    <section class="sec"><header>${H('users', 'Talabalar', 'people')}<span class="count" id="dcount">${n} ta tanlandi</span></header><div class="pad">
      <div class="note ${j.readable ? '' : 'warn'}" style="margin-bottom:12px">${ic(j.readable ? 'file' : 'alert')}<span><b>${esc(j.file_name)}</b><br>${j.readable
        ? `${j.pages} sahifa · hujjatda ${j.found.filter(x => x.auto).length} ta talaba topildi`
        : 'Hujjat matnini o‘qib bo‘lmadi — nusxalar asl holida yuboriladi (boshqa talabalar yopilmaydi).'}</span></div>
      ${j.found.length ? `<table class="tbl"><tbody>${j.found.map(x => `<tr><td style="width:36px"><input type="checkbox" class="dsel" data-id="${x.id}" ${j.sel.has(x.id) ? 'checked' : ''} aria-label="Tanlash"></td>
        <td class="name"><b>${esc(x.name)}</b><span>${esc(x.group)}${x.hemis_id ? ', HEMIS ' + esc(x.hemis_id) : ''}${x.auto ? '' : ' · qo‘lda qo‘shilgan'}</span>${x.note ? `<span style="display:block;color:var(--bordo-600);font-weight:600;white-space:normal">⚠️ ${esc(x.note)}</span>` : ''}</td>
        <td class="r"><button class="btn sm" data-act="doc-pv" data-id="${x.id}">Ko‘rish</button></td></tr>`).join('')}</tbody></table>`
        : emptyBox('users', 'Hujjatda talaba topilmadi', 'Pastdagi qidiruv orqali qo‘shing.')}
      <div class="search" style="margin-top:14px">${ic('search')}<input class="input" id="dq" style="width:100%" placeholder="Talabani qo‘shish: familiya yoki HEMIS ID" autocomplete="off"></div>
      <div id="dres"></div>
      <div class="field" style="margin-top:18px"><span>Hujjat turi</span><div class="radio four">${DOC_KINDS.map(([k, l, h]) =>
        `<label><input type="radio" name="dtype" value="${k}" ${j.dtype === k ? 'checked' : ''}><span><b>${l}</b><span>${h}</span></span></label>`).join('')}</div></div>
      <label class="field"><span>Izoh (ixtiyoriy)</span><input class="input" id="dcomment" value="${esc(j.comment || '')}" placeholder="Masalan: buyruq № 45, 28.09.2026"></label>
      <button class="btn primary" data-act="doc-send" id="dsend" ${n ? '' : 'disabled'}>${ic('send')} Yuborish — ${n} ta talaba</button></div></section>
    <section class="sec"><header><h2 id="pvh">Ota-ona ko‘radigan nusxa</h2></header><div class="pad" id="pv">${emptyBox('file', 'Talabani tanlang', '«Ko‘rish» tugmasini bosing — nusxa shu yerda ochiladi.')}</div></section></div>`);
  $$('.dsel').forEach(cb => cb.addEventListener('change', () => {
    const id = Number(cb.dataset.id); cb.checked ? j.sel.add(id) : j.sel.delete(id);
    $('#dcount').textContent = `${j.sel.size} ta tanlandi`;
    $('#dsend').disabled = !j.sel.size; $('#dsend').innerHTML = `${ic('send')} Yuborish — ${j.sel.size} ta talaba`;
  }));
  $$('input[name=dtype]').forEach(r => r.addEventListener('change', () => { j.dtype = r.value; }));
  $('#dcomment').addEventListener('input', e => { j.comment = e.target.value; });
  let tmr;
  $('#dq').addEventListener('input', e => {
    clearTimeout(tmr); const q = e.target.value.trim();
    tmr = setTimeout(async () => {
      if (q.length < 2) { $('#dres').innerHTML = ''; return; }
      const r = await api(`/api/staff/students?q=${encodeURIComponent(q)}&limit=8`);
      $('#dres').innerHTML = r.items.length ? `<ul class="list" style="margin-top:8px">${r.items.map(x => `<li><div><div class="t"><b>${esc(x.name)}</b><p>${esc(x.group)}</p></div>
        <button class="btn sm" data-act="doc-add" data-st='${esc(JSON.stringify({ id: x.id, name: x.name, group: x.group, hemis_id: x.hemis_id }))}'>${ic('plus')} Qo‘shish</button></div></li>`).join('')}</ul>`
        : `<p class="hint">Topilmadi</p>`;
    }, 300);
  });
  const first = j.found.find(x => j.sel.has(x.id));
  if (first) docPreview(first.id);
}
async function uploadPdf(file) {
  if (!/\.pdf$/i.test(file.name)) { toast('Faqat PDF fayl yuklash mumkin', true); return; }
  $('#dzs').innerHTML = `<div class="note"><span class="spin"></span><span>«${esc(file.name)}» o‘qilmoqda — talabalar qidirilmoqda…</span></div>`;
  const fd = new FormData(); fd.append('file', file);
  try {
    const d = await api('/api/staff/docs', { method: 'POST', body: fd });
    S.docJob = { token: d.token, course: S.course, file_name: d.file_name, pages: d.pages, readable: d.readable, dtype: d.dtype, comment: '',
      found: d.found.map(x => ({ ...x, auto: true })), sel: new Set(d.found.filter(x => x.select !== false).map(x => x.id)) };
    pDocs();
  } catch (err) {
    $('#dzs').innerHTML = `<div class="note bordo">${ic('alert')}<span>${err.data?.error === 'not_pdf' ? 'Bu PDF fayl emas.' : err.data?.error === 'too_big' ? 'Fayl 20 MB dan katta.' : 'Hujjatni o‘qib bo‘lmadi.'}</span></div>`;
  }
}
async function docPreview(sid) {
  const j = S.docJob, pv = $('#pv'); if (!j || !pv) return;
  const x = j.found.find(y => y.id === sid);
  $('#pvh').textContent = `${x ? x.name : ''} — ota-onasi ko‘radigan nusxa`;
  pv.innerHTML = skel(360);
  let info;
  try { info = await api(`/api/staff/docs/${j.token}/${sid}`); }
  catch (e) { pv.innerHTML = emptyBox('alert', e.status === 410 ? 'Hujjat seansi tugadi (30 daqiqa) — faylni qayta yuklang' : 'Nusxani tayyorlab bo‘lmadi'); return; }
  const notes = !info.checked ? [['warn', 'Hujjat tekshirilmadi — asl holida yuboriladi']]
    : [[info.boxes ? 'ok' : '', info.boxes ? `Yopilgan joylar: ${info.boxes}` : 'Yopiladigan boshqa talaba yo‘q']]
      .concat(info.found ? [] : [['warn', 'Talabaning o‘zi hujjatda topilmadi — to‘g‘ri talaba tanlanganini tekshiring']])
      .concat(info.ambiguous ? [['warn', 'Ismi o‘xshash talaba bor — nusxani diqqat bilan tekshiring']] : []);
  pv.innerHTML = notes.map(([c, t]) => `<div class="note ${c}" style="margin-bottom:8px">${ic(c === 'warn' ? 'alert' : c === 'ok' ? 'shield' : 'info')}<span>${esc(t)}</span></div>`).join('')
    + `<div class="docview">${Array.from({ length: info.pages }, (_, i) => `<figure data-pn="${i}"><div class="skel" style="aspect-ratio:.707"></div></figure>`).join('')}</div>`;
  for (let i = 0; i < info.pages; i++) {
    try {
      const url = URL.createObjectURL(await (await api(`/api/staff/docs/${j.token}/${sid}/page/${i}?w=1100`, { raw: true })).blob());
      const f = pv.querySelector(`[data-pn="${i}"]`); if (f) f.innerHTML = `<img src="${url}" alt="${i + 1}-sahifa">`;
    } catch (e) { /* */ }
  }
}

/* ================================================================ real vaqt: yangi xabar va so'rovlar darhol */
const LIVE = { ctrl: null, retry: 2000 };
async function connectLive() {
  if (LIVE.ctrl) return;
  const ctrl = new AbortController(); LIVE.ctrl = ctrl;
  try {
    const h = authHeaders({ 'X-Desk': '1' }); if (DEV) h['X-Dev-User'] = '1';
    const r = await fetch('/api/events', { headers: h, signal: ctrl.signal, credentials: 'same-origin', cache: 'no-store' });
    if (!r.ok || !r.body) throw new Error('http ' + r.status);
    LIVE.retry = 2000;
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        let type = 'message', data = '';
        for (const l of chunk.split('\n')) { if (l.startsWith('event:')) type = l.slice(6).trim(); else if (l.startsWith('data:')) data += l.slice(5).trim(); }
        if (type !== 'hello' && data) { try { onLive(JSON.parse(data)); } catch (_) { /* */ } }
      }
    }
  } catch (e) { if (ctrl.signal.aborted) return; }
  LIVE.ctrl = null;
  setTimeout(connectLive, LIVE.retry); LIVE.retry = Math.min(LIVE.retry * 2, 30000);
}
function onLive(ev) {
  const m = String(ev.route || '').split('/').filter(Boolean);  // /staff/chat/<kurs>/<talaba>/<ota-ona> yoki /staff/requests
  const target = m[1] === 'chat' ? { hash: `#/inbox/${m[3]}/${m[4]}`, course: decodeURIComponent(m[2] || '') } : m[1] === 'requests' ? { hash: '#/requests', course: ev.course } : null;
  const same = !ev.course || ev.course === S.course;
  refreshBadges();
  if (ev.type === 'message' && same && S.inboxRefresh) S.inboxRefresh();
  if (ev.type === 'request' && same && location.hash.startsWith('#/requests')) route();
  if (same && (location.hash === '#/panel' || location.hash === '')) route();  // kurs holati: yangi xabar/so'rov ro'yxatda ham
  const text = ev.type === 'request' ? `Yangi bog‘lash so‘rovi: ${ev.text || ''}` : ev.type === 'message' ? `Yangi xabar — ${ev.text || ''}` : String(ev.text || '');
  const t = document.createElement('a');
  t.className = 'toast live'; t.href = target ? target.hash : '#/panel';
  t.innerHTML = `${ic(ev.type === 'request' ? 'req' : 'chat')}<span>${esc(text.replace(/<[^>]+>/g, '').slice(0, 160))}</span><b>Ochish</b>`;
  t.addEventListener('click', () => { if (target && target.course) switchCourse(target.course); t.remove(); });
  $('#toasts').append(t);
  setTimeout(() => t.remove(), 9000);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden && S.me && !LIVE.ctrl) connectLive(); });

/* ================================================================ super-admin */
async function pSuperOverview() {
  document.title = 'Barcha kurslar — Boshqaruv paneli';
  view(head('Barcha kurslar', todayLabel()) + skel(110) + skel(320));
  const d = await api('/api/super/overview');
  const tot = d.courses.reduce((a, c) => ({ total: a.total + c.total, linked: a.linked + c.linked, prob: a.prob + c.prob, multi: a.multi + c.multi,
    k: a.k + c.kontrakt.sum, t: a.t + c.trimestr.sum }), { total: 0, linked: 0, prob: 0, multi: 0, k: 0, t: 0 });
  const kc = d.courses.reduce((a, c) => a + c.kontrakt.count, 0), tc = d.courses.reduce((a, c) => a + c.trimestr.count, 0);
  const [km, ku] = moneyShort(tot.k), [tm, tu] = moneyShort(tot.t);
  const cover = pct(tot.linked, tot.total);
  const moneyCell = (m, icon) => m.count ? `<span class="mcell" title="${money(m.sum)}">${ic(icon)}<b>${mlnPlain(m.sum)}</b><small>${m.count} ta talaba</small></span>` : '<span class="dash">—</span>';
  const countCell = (n, icon, cls) => n ? `<span class="icnt ${cls}">${ic(icon)}${n}</span>` : '<span class="dash">0</span>';
  view(head('Barcha kurslar', todayLabel(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + `
    <section class="kpis k3" aria-label="Universitet bo‘yicha ko‘rsatkichlar">
      ${kpi({ href: '#/super/courses', icon: 'layers', c: 'people', label: 'Kurslar', value: d.courses.length, unit: 'ta', sub: `${ic('users')} kurs koordinatorlari: <b>${d.coordinators}</b>` })}
      ${kpi({ icon: 'users', c: 'people', label: 'Talabalar', value: num(tot.total, 0), unit: 'ta', sub: `${ic('link')} ota-onasi ulangan: <b>${num(tot.linked, 0)}</b> · ${cover}%`, meter: cover })}
      ${kpi({ icon: 'flame', c: 'risk', label: 'Muammoli talabalar', value: tot.prob, unit: 'ta', state: probState(tot.multi), sub: `3 va undan ko‘p masala: <b>${tot.multi}</b>` })}
      ${kpi({ icon: 'dollar', c: 'money', label: 'Kontrakt qarzi', value: km, unit: ku, state: probState(kc, 'warn'), sub: `${kc} ta talaba`, title: money(tot.k) })}
      ${kpi({ icon: 'receipt', c: 'money2', label: 'Trimestr qarzi', value: tm, unit: tu, state: probState(tc, 'warn'), sub: `${tc} ta talaba`, title: money(tot.t) })}
      ${kpi({ href: '#/super/system', icon: 'server', c: 'sys', label: 'Tizim', value: d.errors_24h ? d.errors_24h : 'Barqaror', unit: d.errors_24h ? 'ta xato' : '',
        state: d.errors_24h ? 'bad' : 'ok', sub: `${ic('db')} zaxira: ${d.last_backup ? when(d.last_backup) : 'hali olinmagan'}` })}
    </section>
    <section class="sec"><header>${H('layers', 'Kurslar kesimida', 'people')}<a href="#/super/courses">Kurslarni boshqarish ${ic('arrow')}</a></header>
      ${d.courses.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl courses"><thead><tr><th>Kurs</th><th>Kurs koordinatorlari</th><th class="r">Talabalar</th><th>Ota-onasi ulangan</th>
        <th class="r">Muammoli</th><th class="r">Davomat</th><th class="r">Akademik</th><th class="r">Kontrakt qarzi</th><th class="r">Trimestr qarzi</th><th></th></tr></thead><tbody>
        ${d.courses.map(c => `<tr><td class="name"><div class="cname"><span class="h-ic sm c-people" aria-hidden="true">${ic('layers')}</span><b>${esc(c.title)}</b></div></td>
          <td>${c.admins.length ? `<div class="people">${c.admins.map(a => `<span class="person"><span class="av-s">${/^\p{L}/u.test(a.label) && !/^ID\b/.test(a.label) ? esc(initials(a.label)) : ic('users')}</span>${esc(a.label)}</span>`).join('')}</div>` : `<span class="chip warn">${ic('alert')}tayinlanmagan</span>`}</td>
          <td class="r">${c.total}</td><td>${pctCell(c.total ? pct(c.linked, c.total) : null)}</td>
          <td class="r">${countCell(c.prob, 'flame', c.multi ? 'bad' : '')}</td><td class="r">${countCell(c.att, 'calx', 'bad')}</td><td class="r">${countCell(c.acad, 'bookx', 'bad')}</td>
          <td class="r">${moneyCell(c.kontrakt, 'dollar')}</td><td class="r">${moneyCell(c.trimestr, 'receipt')}</td>
          <td class="r"><button class="btn sm" data-act="enter" data-key="${esc(c.key)}">Kirish ${ic('arrow')}</button></td></tr>`).join('')}</tbody></table></div>`
        : emptyBox('building', 'Hali kurs yo‘q', '', `<a class="btn primary" href="#/super/courses">${ic('plus')} Kurs yaratish</a>`)}</section>`);
}
async function pSuperCourses() {
  document.title = 'Kurslar va koordinatorlar — Boshqaruv paneli';
  const d = await api('/api/super/courses');
  view(head('Kurslar va koordinatorlar', todayLabel(), `<button class="btn primary" data-act="new-course">${ic('plus')} Yangi kurs</button>`) + `
    <p class="hint" style="margin:-10px 0 18px">Har bir kurs — alohida ma’lumotlar bazasi. Kurs koordinatori faqat o‘z kursini ko‘radi. Kursda bir nechta koordinator bo‘lsa, har biriga guruhlarini biriktiring — fayl yuklaganda (buxgalteriya hisoboti ham) faqat o‘z guruhlari talabalari tanilinadi. O‘zgarishlar botni qayta ishga tushirmasdan kuchga kiradi.</p>
    <section class="sec">${d.courses.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Kurs</th><th class="r">Talabalar</th><th class="r">Ota-onalar</th><th>Kurs koordinatorlari</th><th></th></tr></thead><tbody>
      ${d.courses.map(c => `<tr><td class="name"><b>${esc(c.title)}</b><span>data/${esc(c.key)}/</span></td><td class="r">${c.students}</td><td class="r">${c.parents}</td>
        <td><div class="coords">${c.admins.map(a => `<div class="coord"><span class="chip">${esc(a.label)}<button data-act="del-coord" data-uid="${a.user_id}" data-name="${esc(a.label)}" data-course="${esc(c.title)}" title="Olib tashlash" aria-label="Olib tashlash">${ic('x')}</button></span>
            <button class="btn sm ghost" data-act="coord-groups" data-uid="${a.user_id}" data-key="${esc(c.key)}" data-name="${esc(a.label)}">${ic('users')} ${a.groups.length ? esc(a.groups.join(', ')) : 'Guruhlar: butun kurs'}</button></div>`).join('')
          || '<span class="chip warn">tayinlanmagan — xabarlar super-adminga boradi</span>'}</div></td>
        <td class="r" style="white-space:nowrap"><button class="btn sm" data-act="add-coord" data-key="${esc(c.key)}" data-title="${esc(c.title)}">${ic('plus')} Koordinator qo‘shish</button>
          <button class="btn sm ghost" data-act="rename" data-key="${esc(c.key)}" data-title="${esc(c.title)}" title="Nomini o‘zgartirish" aria-label="Nomini o‘zgartirish">${ic('edit')}</button></td></tr>`).join('')}
      </tbody></table></div>` : emptyBox('building', 'Hali kurs yo‘q', 'Birinchi kursni yarating va unga kurs koordinatorini tayinlang.')}</section>`);
}
async function pSuperSystem() {
  document.title = 'Tizim — Boshqaruv paneli';
  view(head('Tizim', todayLabel()) + skel(160) + skel(300));
  const [o, e, pt] = await Promise.all([api('/api/super/overview'), api('/api/super/errors'), api('/api/super/pair_times')]);
  view(head('Tizim', todayLabel(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + `<div class="cols">
    <section class="sec"><header>${H('db', 'Zaxira nusxa', 'sys')}</header><div class="pad">
      <div class="kv" style="margin-bottom:14px"><span>Oxirgi zaxira nusxa</span><b>${o.last_backup ? when(o.last_backup) : 'hali olinmagan'}</b>
        <span>Avtomatik</span><b>har kuni 03:00, 14 kun saqlanadi</b><span>Shifrlash</span><b>AES-256</b></div>
      <button class="btn primary" data-act="backup">${ic('db')} Hozir zaxira nusxa olish</button>
      <p class="hint">Barcha kurs bazalari va umumiy ro‘yxat bitta shifrlangan arxivga yig‘iladi va Telegram chatingizga yuboriladi.</p>
      <div id="bk"></div></div></section>
    <section class="sec"><header>${H('alert', 'Xatolar jurnali', 'risk')}<span class="chip ${e.count_24h ? 'bordo' : 'ok'}">so‘nggi 24 soatda: ${e.count_24h}</span></header><div class="pad">
      ${e.tail.trim() ? `<pre class="log">${esc(e.tail)}</pre>` : `<div class="note ok">${ic('ok')}<span>Jurnal bo‘sh — tizim xatosiz ishlayapti.</span></div>`}
      <p class="hint">To‘liq jurnal serverda: logs/errors.log. Yangi tizim xatosi haqida bot sizga darhol xabar beradi.</p></div></section></div>
    <section class="sec" style="margin-top:22px"><header>${H('clock', 'Juftlik vaqtlari', 'att')}${Object.keys(pt.times).length ? '<span class="chip ok">kiritilgan</span>' : '<span class="chip warn">kiritilmagan</span>'}</header><div class="pad">
      <p class="hint" style="margin-top:0">Dars jadvalida har bir juftlikning boshlanish va tugash vaqti ko‘rsatiladi (ota-ona ilovasida ham). HEMIS jadvalida vaqt bo‘lsa, o‘sha ustun turadi. Bo‘sh qoldirilgan juftlik — faqat raqami bilan.</p>
      <div class="ptimes">${Array.from({ length: 8 }, (_, i) => { const v = pt.times[String(i + 1)] || ['', ''];
        return `<div><b>${i + 1}-juftlik</b><input class="input" type="time" data-pt="${i + 1}" data-k="0" value="${esc(v[0])}" aria-label="${i + 1}-juftlik boshlanishi"><span>—</span>
          <input class="input" type="time" data-pt="${i + 1}" data-k="1" value="${esc(v[1])}" aria-label="${i + 1}-juftlik tugashi"></div>`; }).join('')}</div>
      <div class="toolbar" style="margin:16px 0 0"><button class="btn primary" data-act="pt-save">${ic('clock')} Saqlash</button>
        <button class="btn" data-act="pt-sample">Namuna bilan to‘ldirish</button><span class="hint">Namuna — 80 daqiqalik juftlik va 10 daqiqa tanaffus; JIDU jadvaliga moslab, keyin saqlang.</span></div></div></section>`);
}

/* ================================================================ so'rovnomalar (kurs koordinatori) */
const SV_KINDS = [['single', 'Bitta javob'], ['multi', 'Bir nechta javob'], ['scale', 'Baho 1–5'], ['text', 'Erkin javob']];
function svNew() {
  return { title: '', description: '', groups: new Set(), closes: '', anonymous: false, all: false,
    questions: [{ kind: 'single', text: '', options: ['', ''], required: true }] };
}
async function pSurveys(parts) {
  if (parts[1] === 'new') return pSurveyBuilder();
  if (parts[1]) return pSurveyResults(Number(parts[1]));
  document.title = 'So‘rovnomalar — Boshqaruv paneli';
  view(head('So‘rovnomalar', courseSub()) + skel(240));
  const d = await api('/api/staff/surveys');
  view(head('So‘rovnomalar', courseSub(), `<a class="btn primary" href="#/surveys/new">${ic('plus')} Yangi so‘rovnoma</a>`) + `
    <p class="hint" style="margin:-10px 0 18px">Ota-onalar so‘rovnomani ilovada — bosh sahifadagi ko‘zga tashlanadigan kartochkadan to‘ldiradi; e’lon qilinganda bot orqali xabar boradi.${myGroups().length ? ' Faqat guruhlaringiz: ' + esc(myGroups().join(', ')) + '.' : ''}</p>
    <section class="sec">${d.items.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>So‘rovnoma</th><th>Kimga</th><th class="r">Javoblar</th><th>Holat</th></tr></thead><tbody>
      ${d.items.map(x => { const p = x.eligible ? Math.round(100 * x.answered / x.eligible) : 0; return `<tr class="click" onclick="location.hash='#/surveys/${x.id}'"><td class="name"><b>${esc(x.title)}</b><span>${when(x.created_at)}</span></td>
        <td>${x.groups.length ? esc(x.groups.join(', ')) : 'butun kurs'}</td>
        <td class="r"><b>${x.answered}</b> / ${x.eligible}<div class="meter" style="margin-top:4px"><i style="width:${p}%"></i></div></td>
        <td>${x.open ? '<span class="chip ok">ochiq</span>' : '<span class="chip muted">yopilgan</span>'}</td></tr>`; }).join('')}</tbody></table></div>`
      : emptyBox('poll', 'Hali so‘rovnoma yo‘q', 'Ota-onalar fikrini bilish uchun birinchi so‘rovnomani tuzing.', `<a class="btn primary" href="#/surveys/new">${ic('plus')} Yangi so‘rovnoma</a>`)}</section>`);
}
async function pSurveyBuilder() {
  document.title = 'Yangi so‘rovnoma — Boshqaruv paneli';
  S.sv = S.sv || svNew();
  let groups = [];
  try { groups = [...new Set((await loadStudents()).rows.map(r => r.group).filter(Boolean))].sort(); } catch (_) { /* */ }
  S.svGroups = groups;
  drawSurveyBuilder();
}
function drawSurveyBuilder() {
  const v = S.sv, sup = S.me.role === 'super';
  const qHtml = (q, i) => `<div class="svq" data-i="${i}">
    <div class="svq-head"><b>${i + 1}.</b><select class="input" data-f="kind" aria-label="Savol turi">${SV_KINDS.map(([k, l]) => `<option value="${k}" ${q.kind === k ? 'selected' : ''}>${l}</option>`).join('')}</select>
      <label class="svq-req"><input type="checkbox" data-f="required" ${q.required ? 'checked' : ''}> majburiy</label>
      <button class="btn sm ghost" data-act="sv-up" data-i="${i}" title="Yuqoriga" ${i ? '' : 'disabled'}>↑</button>
      <button class="btn sm ghost" data-act="sv-del" data-i="${i}" title="Savolni o‘chirish" aria-label="Savolni o‘chirish">${ic('x')}</button></div>
    <input class="input" data-f="text" value="${esc(q.text)}" placeholder="Savol matni" maxlength="500" style="width:100%">
    ${q.kind === 'single' || q.kind === 'multi' ? `<div class="svq-opts">${q.options.map((o, j) => `<div class="svq-opt"><span>${q.kind === 'single' ? '○' : '☐'}</span>
        <input class="input" data-f="opt" data-j="${j}" value="${esc(o)}" placeholder="${j + 1}-variant" maxlength="200">
        <button class="btn sm ghost" data-act="sv-opt-del" data-i="${i}" data-j="${j}" aria-label="Variantni o‘chirish" ${q.options.length > 2 ? '' : 'disabled'}>${ic('x')}</button></div>`).join('')}
      <button class="btn sm" data-act="sv-opt-add" data-i="${i}">${ic('plus')} Variant</button></div>`
    : q.kind === 'scale' ? '<p class="hint">Ota-ona 1 dan 5 gacha baho beradi (1 — yomon, 5 — a’lo); natijada o‘rtacha baho ko‘rsatiladi.</p>'
    : '<p class="hint">Ota-ona o‘z so‘zlari bilan yozadi.</p>'}</div>`;
  view(head('Yangi so‘rovnoma', courseSub(), `<a class="btn" href="#/surveys">Bekor qilish</a>`) + `<div class="grid-2" id="svb">
    <section class="sec"><header>${H('poll', 'Savollar', 'gpa')}</header><div class="pad">
      <label class="field"><span>Sarlavha</span><input class="input" data-g="title" value="${esc(v.title)}" placeholder="Masalan: Ota-onalar yig‘ilishi vaqti" maxlength="200"></label>
      <label class="field"><span>Izoh (ixtiyoriy)</span><textarea class="input" data-g="description" rows="2" maxlength="2000" placeholder="Nima uchun so‘rayapmiz, qachongacha">${esc(v.description)}</textarea></label>
      ${v.questions.map(qHtml).join('')}
      <div class="toolbar" style="margin-top:12px">${SV_KINDS.map(([k, l]) => `<button class="btn sm" data-act="sv-add" data-kind="${k}">${ic('plus')} ${l}</button>`).join('')}</div>
    </div></section>
    <div class="stack"><section class="sec"><header>${H('users', 'Kimga va qachongacha', 'people')}</header><div class="pad">
      <div class="field"><span>Guruhlar ${myGroups().length ? '(faqat sizning guruhlaringiz)' : ''}</span>
        <div class="groups">${S.svGroups.length ? S.svGroups.map(g => `<button data-act="sv-grp" data-g="${esc(g)}" class="${v.groups.has(g) ? 'on' : ''}">${esc(g)}</button>`).join('') : '<span class="hint">Talabalar hali yuklanmagan</span>'}</div>
        <small class="hint">Hech biri tanlanmasa — ${myGroups().length ? 'barcha guruhlaringiz' : 'butun kurs'}.</small></div>
      <label class="field"><span>Yopilish sanasi (ixtiyoriy)</span><input class="input" type="date" data-g="closes" value="${esc(v.closes)}"></label>
      <label class="switch" style="margin-top:8px"><span><b style="font-weight:600">Anonim</b><br><span class="hint">Natijalarda ota-ona va talaba ismi ko‘rsatilmaydi</span></span><input type="checkbox" data-g="anonymous" ${v.anonymous ? 'checked' : ''}></label>
      ${sup ? `<label class="switch" style="margin-top:8px"><span><b style="font-weight:600">Barcha kurslarga</b><br><span class="hint">Universitet miqyosidagi so‘rovnoma</span></span><input type="checkbox" data-g="all" ${v.all ? 'checked' : ''}></label>` : ''}
      <button class="btn primary" style="margin-top:16px;width:100%" data-act="sv-publish">${ic('send')} E’lon qilish va ota-onalarga yuborish</button>
      <p class="hint">E’lon qilingach savollarni o‘zgartirib bo‘lmaydi. Ota-onalar javobini so‘rovnoma yopilguncha o‘zgartirishi mumkin.</p>
    </div></section></div></div>`);
}
document.addEventListener('input', e => {
  if (!S.sv || !e.target.closest('#svb')) return;
  const el = e.target, v = S.sv;
  if (el.dataset.g) { v[el.dataset.g] = el.type === 'checkbox' ? el.checked : el.value; return; }
  const box = el.closest('.svq'); if (!box) return;
  const q = v.questions[Number(box.dataset.i)], f = el.dataset.f;
  if (f === 'text') q.text = el.value;
  else if (f === 'opt') q.options[Number(el.dataset.j)] = el.value;
  else if (f === 'required') q.required = el.checked;
});
document.addEventListener('change', e => {
  if (!S.sv || !e.target.closest('#svb')) return;
  const el = e.target;
  if (el.dataset.f === 'kind') {
    const q = S.sv.questions[Number(el.closest('.svq').dataset.i)];
    q.kind = el.value; if ((q.kind === 'single' || q.kind === 'multi') && q.options.length < 2) q.options = ['', ''];
    drawSurveyBuilder();
  } else if (el.dataset.g && el.type === 'checkbox') S.sv[el.dataset.g] = el.checked;
});
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act^="sv-"]');
  if (!b || !S.sv) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const v = S.sv, i = Number(b.dataset.i), act = b.dataset.act;
  if (act === 'sv-add') v.questions.push({ kind: b.dataset.kind, text: '', options: ['', ''], required: true });
  else if (act === 'sv-del') { v.questions.splice(i, 1); if (!v.questions.length) v.questions.push({ kind: 'single', text: '', options: ['', ''], required: true }); }
  else if (act === 'sv-up' && i > 0) [v.questions[i - 1], v.questions[i]] = [v.questions[i], v.questions[i - 1]];
  else if (act === 'sv-opt-add') v.questions[i].options.push('');
  else if (act === 'sv-opt-del') v.questions[i].options.splice(Number(b.dataset.j), 1);
  else if (act === 'sv-grp') { v.groups.has(b.dataset.g) ? v.groups.delete(b.dataset.g) : v.groups.add(b.dataset.g); }
  else if (act === 'sv-publish') {
    const qs = v.questions.map(q => ({ ...q, text: q.text.trim(), options: q.options.map(o => o.trim()).filter(Boolean) }));
    if (v.title.trim().length < 3) return toast('Sarlavhani yozing', true);
    const bad = qs.findIndex(q => !q.text || ((q.kind === 'single' || q.kind === 'multi') && q.options.length < 2));
    if (bad >= 0) return toast(`${bad + 1}-savol to‘liq emas: matn va kamida ikkita variant kerak`, true);
    const who = v.groups.size ? [...v.groups].join(', ') + ' guruhlari' : (myGroups().length ? 'barcha guruhlaringiz' : 'butun kurs');
    if (!await confirmDlg('So‘rovnomani e’lon qilasizmi?', `«${esc(v.title)}» — ${qs.length} ta savol, ${esc(v.all ? 'barcha kurslar' : who)} ota-onalariga yuboriladi.`, 'E’lon qilish')) return;
    b.disabled = true;
    try {
      const r = await api('/api/staff/surveys', { method: 'POST', json: { title: v.title, description: v.description, questions: qs, groups: [...v.groups],
        closes_at: v.closes || null, anonymous: v.anonymous, all_courses: v.all } });
      S.sv = null; toast(`E’lon qilindi — ${r.sent} / ${r.recipients} ota-onaga yuborildi`);
      location.hash = `#/surveys/${r.id}`;
    } catch (err) { toast('E’lon qilinmadi: ' + (err.data?.error || err.message), true); b.disabled = false; }
    return;
  }
  drawSurveyBuilder();
}, true);
async function pSurveyResults(id) {
  document.title = 'So‘rovnoma natijalari — Boshqaruv paneli';
  view(head('So‘rovnoma', courseSub()) + skel(300));
  const d = await api(`/api/staff/surveys/${id}`);
  const pct = d.eligible ? Math.round(100 * d.answered / d.eligible) : 0;
  const qBox = (q, i) => {
    let body;
    if (q.options) {
      const tot = q.options.reduce((a, o) => a + o.count, 0) || 1;
      body = q.options.map(o => `<div class="bar-row"><span class="lbl">${esc(o.label)}</span><div class="bar"><i style="width:${Math.round(100 * o.count / tot)}%"></i></div><b class="num">${o.count}</b><span class="hint num">${Math.round(100 * o.count / tot)}%</span></div>`).join('')
        + (q.average != null ? `<p class="hint" style="margin:8px 0 0">O‘rtacha baho: <b>${String(q.average).replace('.', ',')}</b> / 5</p>` : '');
    } else {
      body = q.texts.length ? `<ul class="answers">${q.texts.map(x => `<li>${esc(x.text)}${x.student ? `<span class="hint"> — ${esc(x.student)}, ${esc(x.group || '')}</span>` : ''}</li>`).join('')}</ul>` : '<p class="hint">Hali javob yo‘q</p>';
    }
    return `<section class="sec"><header>${H('poll', `${i + 1}. ${esc(q.text)}`, 'gpa')}<span class="hint">${q.answered} ta javob</span></header><div class="pad">${body}</div></section>`;
  };
  view(head(d.title, `${d.groups.length ? esc(d.groups.join(', ')) : 'butun kurs'} · ${when(d.created_at)}${d.closes_at ? ' · ' + esc(d.closes_at) + ' gacha' : ''}`,
    `<button class="btn" data-act="svr-export" data-id="${id}">${ic('download')} Excel</button>
     ${d.open ? `<button class="btn" data-act="svr-close" data-id="${id}">Yopish</button>` : '<span class="chip muted">yopilgan</span>'}
     <button class="btn ghost" data-act="svr-del" data-id="${id}" title="O‘chirish" aria-label="O‘chirish">${ic('x')}</button>`) + `
    <section class="band" style="--cols:3"><div><div class="k">Javob berganlar</div><div class="v navy">${d.answered}</div><div class="s">${d.eligible} ta ota-onadan</div></div>
      <div><div class="k">Qatnashish</div><div class="v ${pct >= 50 ? 'ok' : 'warn'}">${pct}%</div><div class="meter"><i style="width:${pct}%"></i></div></div>
      <div><div class="k">Holat</div><div class="v" style="font-size:20px">${d.open ? 'ochiq' : 'yopilgan'}</div><div class="s">${d.anonymous ? 'anonim' : 'ismlar ko‘rinadi'}</div></div></section>
    ${d.description ? `<p class="hint" style="white-space:pre-line">${esc(d.description)}</p>` : ''}
    <div class="stack">${d.questions.map(qBox).join('')}</div>`);
}
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act^="svr-"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const id = b.dataset.id, act = b.dataset.act;
  try {
    if (act === 'svr-export') toast('Yuklab olindi: ' + await download(`/api/staff/surveys/${id}/export`));
    else if (act === 'svr-close') { if (!await confirmDlg('So‘rovnomani yopasizmi?', 'Ota-onalar endi javob bera olmaydi; natijalar saqlanadi.', 'Yopish')) return; await api(`/api/staff/surveys/${id}/close`, { method: 'POST' }); toast('Yopildi'); route(); }
    else if (act === 'svr-del') { if (!await confirmDlg('So‘rovnomani o‘chirasizmi?', 'Barcha javoblar ham o‘chadi. Buni qaytarib bo‘lmaydi.', 'O‘chirish', true)) return; await api(`/api/staff/surveys/${id}`, { method: 'DELETE' }); toast('O‘chirildi'); location.hash = '#/surveys'; }
  } catch (err) { toast('Bajarilmadi', true); }
}, true);

/* ================================================================ ichki nizomlar (super-admin) */
async function pSuperRegs() {
  document.title = 'Ichki nizomlar — Boshqaruv paneli';
  view(head('Ichki nizomlar', todayLabel()) + skel(260));
  const d = await api('/api/regulations');
  view(head('Ichki nizomlar', todayLabel()) + `<p class="hint" style="margin:-10px 0 18px">Barcha kurslar ota-onalari ilovada — bosh sahifadagi «Ichki nizomlar» tugmasidan ko‘radi. PDF ilovaning o‘zida sahifalab ochiladi; havola — brauzerda. Nomni uch tilda yozish mumkin: alohida qatordan <code>---ru</code> va <code>---en</code>.</p>
    <div class="grid-2"><section class="sec"><header>${H('book', 'Nizomlar', 'acad')}<span class="hint">${d.items.length} ta</span></header>
      ${d.items.length ? `<ul class="list">${d.items.map(r => `<li style="display:flex;align-items:flex-start;gap:12px"><div class="t" style="flex:1"><b>${ic(r.kind === 'pdf' ? 'file' : 'book')} ${esc(r.title)}</b>${r.description ? `<p>${esc(r.description)}</p>` : ''}<p>${r.kind === 'pdf' ? `<button class="btn sm" data-act="reg-pdf" data-id="${r.id}">${ic('download')} PDF</button>` : `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.url)}</a>`}</p></div>
        <button class="btn sm ghost" data-act="reg-del" data-id="${r.id}" data-title="${esc(r.title)}" aria-label="O‘chirish">${ic('x')}</button></li>`).join('')}</ul>`
        : `<div class="pad">${emptyBox('book', 'Hali nizom yo‘q', 'O‘ng tomondagi shakl orqali PDF yoki havola qo‘shing.')}</div>`}</section>
    <section class="sec"><header>${H('plus', 'Yangi nizom', 'people')}</header><form class="pad" id="regForm">
      <label class="field"><span>Nomi</span><textarea class="input" name="title" rows="2" required minlength="3" placeholder="Masalan: Talabalar odob-axloq qoidalari"></textarea></label>
      <label class="field"><span>Qisqa izoh (ixtiyoriy)</span><input class="input" name="description" maxlength="1000"></label>
      <label class="field"><span>PDF fayl</span><input class="input" type="file" name="file" accept="application/pdf"></label>
      <label class="field"><span>yoki havola</span><input class="input" type="url" name="url" placeholder="https://uwed.uz/..."></label>
      <label class="switch" style="margin-top:6px"><span><b style="font-weight:600">Ota-onalarga xabar berish</b><br><span class="hint">Barcha kurslar ota-onalariga qisqa bildirishnoma</span></span><input type="checkbox" name="notify"></label>
      <button class="btn primary" style="margin-top:14px">${ic('plus')} Qo‘shish</button></form></section></div>`);
}
document.addEventListener('submit', async e => {
  if (e.target.id !== 'regForm') return;
  e.preventDefault(); e.stopImmediatePropagation();
  const f = e.target, fd = new FormData(f), file = fd.get('file');
  if (file && file.size === 0) fd.delete('file');
  if (!fd.get('file') && !String(fd.get('url') || '').trim()) return toast('PDF fayl tanlang yoki havola yozing', true);
  fd.set('notify', f.notify.checked ? '1' : '0');
  const b = f.querySelector('button'); b.disabled = true;
  try { const r = await api('/api/super/regulations', { method: 'POST', body: fd }); toast(r.recipients ? `Qo‘shildi — ${r.sent} / ${r.recipients} ota-onaga xabar` : 'Qo‘shildi'); route(); }
  catch (err) { toast({ title: 'Nomini yozing', not_pdf: 'Fayl PDF emas', too_big: 'Fayl 20 MB dan katta', url: 'Havola https:// bilan boshlansin' }[err.data?.error] || 'Qo‘shilmadi', true); b.disabled = false; }
}, true);
document.addEventListener('click', async e => {
  const pdf = e.target.closest('[data-act="reg-pdf"]');
  if (pdf) { e.preventDefault(); e.stopImmediatePropagation(); try { await download(`/api/regulations/${pdf.dataset.id}/file`); } catch (_) { toast('Yuklab bo‘lmadi', true); } return; }
  const b = e.target.closest('[data-act="reg-del"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (!await confirmDlg('Nizomni o‘chirasizmi?', `«${esc(b.dataset.title)}» ota-onalar ro‘yxatidan olib tashlanadi.`, 'O‘chirish', true)) return;
  try { await api(`/api/super/regulations/${b.dataset.id}`, { method: 'DELETE' }); toast('O‘chirildi'); route(); } catch (err) { toast('Bajarilmadi', true); }
}, true);

/* ================================================================ amallar (hodisalar) */
document.addEventListener('click', async e => {
  const st = e.target.closest('[data-student]');
  const ac = e.target.closest('a[data-course]');
  if (ac && ac.dataset.course !== S.course) switchCourse(ac.dataset.course);  // «Yozish» boshqa kursdagi talabaga
  if (st && !e.target.closest('a')) { openStudent(Number(st.dataset.student), st.dataset.course || null); return; }
  const b = e.target.closest('[data-act]');
  if (!b) { if (e.target.id === 'scrim') closeDrawer(); return; }
  const act = b.dataset.act;
  if (act === 'theme') {
    const order = ['auto', 'light', 'dark'], next = order[(order.indexOf(themePref()) + 1) % 3];
    try { localStorage.setItem('desk-theme', next); } catch (_) { /* */ }
    applyTheme(); toast(`Mavzu: ${THEME_NAMES[next]}`);
  } else if (act === 'doc-pv') docPreview(Number(b.dataset.id));
  else if (act === 'doc-reset') { S.docJob = null; pDocs(); }
  else if (act === 'doc-add') {
    const j = S.docJob; if (!j) return; const x = JSON.parse(b.dataset.st);
    if (!j.found.some(y => y.id === x.id)) j.found.push({ ...x, auto: false });
    j.sel.add(x.id); pDocs();
  } else if (act === 'doc-send') {
    const j = S.docJob; if (!j) return;
    const title = (DOC_KINDS.find(k => k[0] === j.dtype) || DOC_KINDS[3])[1];
    if (!await confirmDlg('Hujjatni yuborasizmi?', `«${esc(title)}» <b>${j.sel.size} ta</b> talabaning ota-onalariga yuboriladi. Har biri faqat o‘z farzandining nusxasini oladi.`, 'Yuborish')) return;
    b.disabled = true; b.innerHTML = '<span class="spin"></span> Yuborilmoqda…';
    try {
      const r = await api('/api/staff/docs/send', { method: 'POST', json: { token: j.token, sids: [...j.sel], dtype: j.dtype, comment: j.comment || '' } });
      S.docJob = null;
      view(head(`${r.title.replace(/^\S+\s/, '')} yuborildi`, courseSub(), `<a class="btn primary" href="#/docs" data-act="doc-reset">${ic('file')} Yana hujjat yuborish</a>`) + `<section class="sec"><div class="tbl-wrap" style="max-height:none"><table class="tbl">
        <thead><tr><th>Talaba</th><th>Guruh</th><th>Ota-onalarga</th><th class="r">Yopilgan joylar</th></tr></thead><tbody>${r.items.map(x => `<tr><td class="name"><b>${esc(x.student)}</b></td><td>${esc(x.group)}</td>
        <td>${x.parents ? `<span class="chip ${x.sent ? 'ok' : 'warn'}">yetkazildi: ${x.sent}/${x.parents}</span>` : '<span class="chip muted">ota-ona hali ulanmagan — ulangach ilovada ko‘radi</span>'}</td>
        <td class="r">${x.boxes || '<span class="dash">—</span>'}</td></tr>`).join('')}</tbody></table></div></section>`);
      toast('Hujjat yuborildi');
    } catch (err) { toast(err.status === 410 ? 'Hujjat seansi tugadi — faylni qayta yuklang' : 'Yuborilmadi', true); b.disabled = false; b.innerHTML = `${ic('send')} Yuborish`; }
  } else if (act === 'pt-sample') {
    const sample = [['08:30', '09:50'], ['10:00', '11:20'], ['11:30', '12:50'], ['13:30', '14:50'], ['15:00', '16:20'], ['16:30', '17:50']];
    sample.forEach(([a, z], i) => { $(`[data-pt="${i + 1}"][data-k="0"]`).value = a; $(`[data-pt="${i + 1}"][data-k="1"]`).value = z; });
    toast('Namuna kiritildi — JIDU jadvaliga moslab, «Saqlash»ni bosing');
  } else if (act === 'pt-save') {
    const times = {};
    for (let i = 1; i <= 8; i++) { const a = $(`[data-pt="${i}"][data-k="0"]`).value, z = $(`[data-pt="${i}"][data-k="1"]`).value; if (a || z) times[i] = [a, z]; }
    try { await api('/api/super/pair_times', { method: 'POST', json: { times } }); toast('Juftlik vaqtlari saqlandi — jadvallarda darhol ko‘rinadi'); route(); }
    catch (err) { toast(`${(err.data?.error || '').replace('time:', '')}-juftlik vaqti noto‘g‘ri: boshlanishi tugashidan oldin bo‘lsin`, true); }
  } else if (act === 'close-drawer') closeDrawer();
  else if (act === 'reload') route();
  else if (act === 'reload-students') { S.stu = null; S.stuAll = null; route(); }
  else if (act === 'logout') {
    if (!await confirmDlg('Chiqasizmi?', 'Qayta kirish Telegram orqali tasdiqlanadi.', 'Chiqish')) return;
    try { await api('/api/desk/logout', { method: 'POST' }); } catch (err) { /* jim */ }
    appToken.set(null);
    if (LIVE.ctrl) { LIVE.ctrl.abort(); LIVE.ctrl = null; }
    renderLogin('Siz paneldan chiqdingiz.');
  } else if (act === 'export') {
    b.disabled = true;
    try { toast('Hisobot yuklab olindi: ' + await download(`/api/staff/export?fmt=${b.dataset.fmt}&s=all`)); } catch (err) { toast('Hisobot tayyorlanmadi', true); }
    b.disabled = false;
  } else if (act === 'req') {
    const approve = b.dataset.ok === '1';
    if (!approve && !await confirmDlg('So‘rovni rad etasizmi?', 'Ota-onaga so‘rov tasdiqlanmagani va kurs koordinatori bilan bevosita bog‘lanish kerakligi haqida xabar boradi.', 'Rad etish', true)) return;
    b.disabled = true;
    try { const r = await api(`/api/staff/requests/${b.dataset.id}`, { method: 'POST', json: { approve } }); toast(r.message.replace(/^[✅❌]\s*/, '') + ' — ota-onaga xabar yuborildi'); }
    catch (err) { toast(err.data?.error || 'Bajarilmadi', true); }
    refreshBadges(); route();
  } else if (act === 'enter') {
    S.course = b.dataset.key; S.stu = null;
    const c = S.me.staff.courses.find(x => x.key === S.course); S.me.staff.course = S.course; S.me.staff.title = c ? c.title : '';
    const sel = $('#course'); if (sel) sel.value = S.course;
    refreshBadges(); location.hash = '#/panel';
  } else if (act === 'new-course') {
    const v = await dialog({ title: 'Yangi kurs', text: 'Kurs uchun alohida papka va ma’lumotlar bazasi yaratiladi.', ok: 'Yaratish',
      fields: [{ name: 'title', label: 'Kurs nomi', placeholder: 'Masalan: 2-kurs yoki 3-kurs, Xalqaro munosabatlar', required: true }] });
    if (!v) return;
    try { await api('/api/super/courses', { method: 'POST', json: v }); toast('Kurs yaratildi — endi unga kurs koordinatorini tayinlang'); await reloadMe(); route(); }
    catch (err) { toast('Kurs yaratilmadi', true); }
  } else if (act === 'rename') {
    const v = await dialog({ title: 'Kurs nomini o‘zgartirish', ok: 'Saqlash', fields: [{ name: 'title', label: 'Kurs nomi', value: b.dataset.title, required: true }] });
    if (!v) return;
    try { await api(`/api/super/courses/${encodeURIComponent(b.dataset.key)}`, { method: 'POST', json: v }); toast('Kurs nomi saqlandi'); await reloadMe(); route(); }
    catch (err) { toast('Saqlanmadi', true); }
  } else if (act === 'add-coord') {
    const v = await dialog({ title: `«${b.dataset.title}» kursiga koordinator`, ok: 'Tayinlash',
      text: 'Koordinator avval botni ochib, /start bosgan bo‘lishi kerak — aks holda bot unga xabar yubora olmaydi.',
      fields: [{ name: 'user_id', label: 'Telegram ID', required: true, pattern: '\\d{5,15}', placeholder: 'Masalan: 123456789',
        hint: 'ID ni @userinfobot orqali bilish mumkin.' }, { name: 'name', label: 'Ism (ota-onalarga ko‘rinadi)', placeholder: 'Masalan: Karimova Nilufar' }] });
    if (!v) return;
    try {
      const r = await api(`/api/super/courses/${encodeURIComponent(b.dataset.key)}/coordinators`, { method: 'POST', json: v });
      toast(r.notified ? 'Kurs koordinatori tayinlandi va xabardor qilindi' : 'Tayinlandi, lekin bu foydalanuvchi botni hali ochmagan — unga bot havolasini yuboring', !r.notified);
      if (r.old) toast(`Oldin «${r.old}» kursida edi — endi shu kursda`);
      route();
    } catch (err) { toast('Tayinlanmadi: ' + (err.data?.error || err.message), true); }
  } else if (act === 'coord-groups') {
    const uid = Number(b.dataset.uid);
    let info; try { info = await api(`/api/super/courses/${encodeURIComponent(b.dataset.key)}/groups`); } catch (err) { toast('Guruhlar yuklanmadi', true); return; }
    const groups = await groupsDialog(b.dataset.name, uid, info);
    if (!groups) return;
    try {
      const r = await api(`/api/super/coordinators/${uid}/groups`, { method: 'POST', json: { groups } });
      toast(r.saved.length ? `Biriktirildi: ${r.saved.join(', ')}` : 'Guruhlar olib tashlandi — butun kurs');
      if (r.taken.length) toast('Boshqa koordinatorniki, qo‘shilmadi: ' + r.taken.map(x => `${x.name} (${x.owner})`).join(', '), true);
      route();
    } catch (err) { toast('Saqlanmadi', true); }
  } else if (act === 'del-coord') {
    if (!await confirmDlg('Kurs koordinatorini olib tashlaysizmi?', `<b>${esc(b.dataset.name)}</b> «${esc(b.dataset.course)}» kurs koordinatorlari ro‘yxatidan chiqariladi. Kurs ma’lumotlari o‘chmaydi.`, 'Olib tashlash', true)) return;
    try { await api(`/api/super/coordinators/${b.dataset.uid}`, { method: 'DELETE' }); toast('Olib tashlandi'); route(); } catch (err) { toast('Bajarilmadi', true); }
  } else if (act === 'backup') {
    b.disabled = true; b.innerHTML = '<span class="spin"></span> Tayyorlanmoqda…';
    try { const r = await api('/api/super/backup', { method: 'POST' }); $('#bk').innerHTML = `<div class="note ok" style="margin-top:14px">${ic('ok')}<span style="white-space:pre-wrap">${safeHtml(r.report)}</span></div>`;
      toast(r.sent ? 'Zaxira nusxa Telegram chatingizga yuborildi' : 'Zaxira nusxa olindi'); }
    catch (err) { toast('Zaxira nusxa olinmadi', true); }
    b.disabled = false; b.innerHTML = `${ic('db')} Hozir zaxira nusxa olish`;
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeDrawer();
  if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '')) { const q = $('#q'); if (q) { e.preventDefault(); q.focus(); } }
});
function switchCourse(key) {
  if (!key || key === S.course || S.me.role !== 'super') return;
  S.course = key; S.stu = null; S.docJob = null;
  const c = (S.me.staff.courses || []).find(x => x.key === key);
  S.me.staff.course = key; S.me.staff.title = c ? c.title : '';
  const sel = $('#course'); if (sel) sel.value = key;
  refreshBadges();
}
async function reloadMe() {
  const me = await api('/api/me');
  S.me.staff.courses = me.staff.courses;
  const cur = S.course;
  renderShell(); S.course = cur; const sel = $('#course'); if (sel) sel.value = cur; markNav();
}

/* ================================================================ ishga tushirish */
(async function boot() {
  try { S.me = await api('/api/me'); } catch (e) {
    if (e.status !== 401) $('#app').innerHTML = `<div class="boot">Server bilan bog‘lanib bo‘lmadi. Sahifani yangilang.</div>`;
    return;
  }
  // ota-ona — o'zining kompyuter versiyasiga (asosiy sahifa keng ekranda shunday ochiladi)
  if (!['staff', 'super'].includes(S.me.role)) { location.replace('/' + (DEV ? '?dev' : '')); return; }
  S.course = S.me.staff.course;
  renderShell();
  window.addEventListener('hashchange', route);
  await route();
  refreshBadges();
  connectLive();
  setInterval(refreshBadges, 60000);
})();
