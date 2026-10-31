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
const S = { me: null, course: null, stu: null, stuCourse: null, timers: [], badges: { unread: 0, requests: 0, chora: 0, tashrif: 0 } };

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
  cal: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M8 14h2M14 14h2M8 18h2"/>',
  chevl: '<path d="m15 18-6-6 6-6"/>', chevr: '<path d="m9 18 6-6-6-6"/>',
  chevd: '<path d="m6 9 6 6 6-6"/>', chevu: '<path d="m18 15-6-6-6 6"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 6.5 8.5 6.5 8.5-6.5"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  folder: '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/>',
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
const PAGE_IC = { 'Kurs holati': 'panel', 'Talabalar': 'users', 'Jadval va fanlar': 'cal', 'Chora ko‘rish': 'shield', 'Xabarlar': 'chat', 'Bog‘lanish so‘rovlari': 'req', 'So‘rovlar': 'req',
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
const NAV_COURSE = [['#/panel', 'panel', 'Kurs holati'], ['#/students', 'users', 'Talabalar'], ['#/subjects', 'cal', 'Jadval va fanlar'], ['#/chora', 'shield', 'Chora ko‘rish', 'chora'], ['#/tashrif', 'home', 'Tashriflar', 'tashrif'], ['#/inbox', 'chat', 'Xabarlar', 'unread'],
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
    const [ib, rq, ch, vt] = await Promise.all([api('/api/staff/inbox'), api('/api/staff/requests'),
      api('/api/staff/discipline/badge').catch(() => ({ new: 0 })), api('/api/staff/visits/badge').catch(() => null)]);
    S.badges.unread = ib.items.reduce((s, i) => s + (i.unread || 0), 0);
    S.badges.requests = rq.items.length;
    S.badges.chora = ch.new || 0;
    S.badges.tashrif = vt ? tashrifBadge(vt) : 0;
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
  const pages = { panel: pPanel, students: pStudents, subjects: pSubjects, chora: pChora, inbox: pInbox, requests: pRequests, announce: pAnnounce, docs: pDocs, files: pFiles, surveys: pSurveys,
    tashrif: typeof pTashrif === 'function' ? pTashrif : pPanel };
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
  const [d, ib, rq, ch, vt, sc] = await Promise.all([api('/api/staff/panel'), api('/api/staff/inbox'), api('/api/staff/requests'),
    api('/api/staff/discipline/badge').catch(() => null), api('/api/staff/visits/badge').catch(() => null),
    typeof socialSection === 'function' ? api('/api/staff/social').catch(() => null) : null]);
  const cover = pct(d.linked, d.total);
  const unread = ib.items.reduce((a, i) => a + (i.unread || 0), 0);
  const share = n => (d.total ? `${pct(n, d.total)}% talabalar` : '');
  const [km, ku] = moneyShort(d.kontrakt.sum), [tm, tu] = moneyShort(d.trimestr.sum);
  const band = (d.scope ? `<p class="hint scope">${ic('info')}${esc(d.scope.replace(/^\s*ℹ️?\s*/u, ''))}</p>` : '') + `<section class="kpis" aria-label="Asosiy ko‘rsatkichlar">
    ${kpi({ href: '#/students', icon: 'users', c: 'people', label: 'Talabalar', value: num(d.total, 0), unit: 'ta',
      sub: `${ic('link')} ota-onasi ulangan: <b>${d.linked}</b> · ${cover}%`, meter: cover })}
    ${kpi({ href: '#/students?f=att', icon: 'calx', c: 'att', label: 'Davomat muammosi', value: d.att, unit: 'ta', state: probState(d.att),
      title: d.handled ? `Chora ko‘rilgan (imzolangan asl nusxasi bilan) ${d.handled} ta talaba bu yerda hisoblanmaydi — ular «Chora ko‘rilganlar»da` : '',
      sub: (d.att ? `<span class="ln">chegaraga yetgan, chora kutilmoqda · ${share(d.att)}</span>` : '<span class="ln">chora kutayotgan talaba yo‘q</span>')
        + (d.handled ? `<span class="ln">${ic('shield')} chora ko‘rilgan: <b>${d.handled}</b> ta</span>` : '') })}
    ${ch ? kpi({ href: '#/chora?tab=hist', icon: 'shield', c: 'risk', label: 'Chora ko‘rilganlar', value: ch.kpi.students, unit: 'ta',
      state: ch.new ? 'bad' : 'ok', title: `O‘quv yilida jami ${ch.kpi.total} ta chora`,
      sub: `<span class="ln">ogohlantirish: <b>${ch.kpi.ogohlantirish}</b> · hayfsan: <b>${ch.kpi.hayfsan}</b></span>${ch.new ? `<span class="ln">chora kutilmoqda: <b>${ch.new}</b> ta</span>` : ''}` }) : ''}
    ${ch && ch.kpi.letters ? lettersKpi(ch.kpi.letters) : ''}
    ${vt && typeof tashrifKpi === 'function' ? tashrifKpi(vt) : ''}
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
  view(head('Kurs holati', courseSub(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + band + dynSection(d.dynamics)
    + (sc ? socialSection(sc, d.total) : '') + `
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
  if (r.handled) out.push(`<span class="chip ok" title="Davomat bo‘yicha chora ko‘rilgan, imzolangan asl nusxasi yuklangan: ${esc(r.handled.title)}${r.handled.number ? ' № ' + esc(r.handled.number) : ''}">${ic('shield')}chora ko‘rilgan</span>`);
  return out.join('') || '<span class="dash">—</span>';
}

/* ================================================================ talabalar */
const FILTERS = [['', 'Hammasi', 'users'], ['prob', 'Muammoli', 'flame'], ['att', 'Davomat', 'calx'], ['acad', 'Akademik qarz', 'bookx'],
  ['gpa', 'GPA past', 'cap'], ['kontrakt', 'Kontrakt', 'dollar'], ['trimestr', 'Trimestr', 'receipt'], ['chora', 'Chora ko‘rilgan', 'shield']];
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
function matchFilter(r, f) { return !f || (f === 'prob' ? r.problems > 0 : f === 'chora' ? (r.measures || []).length > 0 : r.flags[f]); }
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
    const val = r => key === 'debts' ? r.debts.length : key === 'action' ? measRank(r) : r[key];
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
    const k = th.dataset.sort; st.dir = st.sort === k ? -st.dir : (['name', 'group'].includes(k) ? 1 : -1); st.sort = k; draw(); });
}
/* «Chora» ustuni — talabaga rasman ko'rilgan choralar (chegaraga yetgani «Davomat» ustunida) */
const M_RANK = { hayfsan: 3, ogohlantirish: 2, boshqa: 1, xat: 0.5 };
const measRank = r => ((r.measures || []).length ? Math.max(...r.measures.map(m => M_RANK[m.measure] || 0)) * 10 + r.measures.length : null);
function measChips(ms) {
  if (!ms || !ms.length) return '<span class="dash">—</span>';
  return `<div class="wrapc">${ms.map(m => `<span class="chip ${(MEAS[m.measure] || MEAS.boshqa).c}" title="${esc(m.title)}${m.number ? ' № ' + esc(m.number) : ''}${m.date ? ', ' + dmy(m.date) : ''} — ${m.ground === 'tartib' ? 'ichki tartib' : m.ground === 'trimestr' ? 'trimestr qarzi' : 'davomat'}">${esc((MEAS[m.measure] || {}).s || m.title)}${m.ground === 'tartib' ? ' (tartib)' : ''}</span>`).join('')}</div>`;
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
    <td>${measChips(r.measures)}</td>
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
      : d.handled ? '' : `<div class="note ok">${ic('ok')}<span>Hammasi joyida — davomat, baholar va to‘lovlar bo‘yicha masala yo‘q.</span></div>`}
    ${d.handled ? `<div class="note ok">${ic('shield')}<span><b>Davomat bo‘yicha chora ko‘rilgan:</b> ${esc(d.handled.title)}${d.handled.number ? ' № ' + esc(d.handled.number) : ''}${d.handled.date ? ', ' + dmy(d.handled.date) : ''} — imzolangan asl nusxasi yuklangan. Talaba muammolilar ro‘yxatida emas, «Chora ko‘rilganlar»da (keyingi chegaradan oshsa — yana muammoli).</span></div>` : ''}
    <div class="mini">
      <div><div class="k">Davomat</div><div class="v">${a && a.percent != null ? a.percent + '%' : '—'}</div><div class="s">${a ? 'sababsiz: ' + pairs(a.counted_hours) : 'ma’lumot yo‘q'}</div></div>
      <div><div class="k">GPA${d.gpa_low ? ` <span class="chip bordo" style="height:20px">${limNum(d.gpa_min)} dan past — kursdan o‘tmaydi</span>` : ''}</div><div class="v">${d.gpa != null ? gpaFmt(d.gpa) : '—'}<small style="font-size:14px;color:var(--muted)"> / 5</small></div><div class="s">${d.academic.count ? d.academic.count + ' ta akademik qarz' : 'akademik qarz yo‘q'}</div></div>
    </div>
    ${a ? `<div class="box"><h4>Dars qoldirish chegaralari</h4><div class="kv"><span>Sababsiz</span><b>${pairs(a.counted_hours)}</b>
      <span>Sababli</span><b>${pairs(a.excused_hours)}</b>${a.next ? `<span>Keyingi chegaragacha</span><b>${pairs(a.next.left_hours)}</b>` : ''}</div>${ladder}</div>` : ''}
    ${d.academic.count ? `<div class="box"><h4>Akademik qarzlar — ${d.academic.count} ta fan</h4><div class="kv">${d.academic.debts.map(x =>
      `<span>${esc(x.subject)}${x.semester ? ` (${esc(x.semester)}-semestr)` : ''}</span><b style="color:var(--bordo-600)">${x.source === 'hemis'
        ? `${x.credits ? num(x.credits) + ' kredit · ' : ''}HEMIS ro‘yxati` : `${x.score != null ? num(x.score) + ' ball' : ''} «${esc(x.grade || 2)}»`}</b>`).join('')}</div></div>` : ''}
    ${d.measures && d.measures.length ? `<div class="box"><h4>Ko‘rilgan choralar (o‘quv yilida)</h4>${d.measures.map(m => `<div class="kv"><span><span class="chip ${(MEAS[m.measure] || MEAS.boshqa).c}">${esc(m.title)}</span>
      ${m.ground === 'davomat' ? `davomat, sababsiz ${pairs(m.hours)}` : m.ground === 'trimestr' ? `trimestr qarzi ${money(m.amount)}` : `ichki tartib: ${esc(m.rule || '')}`}
      ${m.files ? `<span class="chip ok">${ic('file')} ${m.files} ta hujjat</span>` : '<span class="chip warn">asl hujjat yo‘q</span>'}</span><b>${m.number ? '№ ' + esc(m.number) + ', ' : ''}${dmy(m.date)}</b></div>`).join('')}
      <div style="margin-top:10px"><button class="btn sm" data-chs="${id}">${ic('folder')} Hujjatlarni ochish</button></div></div>` : ''}
    <div class="box" id="stu-social">${skel(40)}</div>
    <div class="box" id="stu-home">${skel(60)}</div>
    ${d.subjects && d.subjects.length ? `<div class="box"><h4>Fanlar bo‘yicha davomat</h4><div class="subj-list">${d.subjects.map(subjRow).join('')}</div></div>` : ''}
    <div class="box"><h4>Haftalik jadval</h4><div id="stu-week">${skel(80)}</div></div>
    <div class="box"><h4>To‘lovlar</h4><div class="kv">${payLine('Kontrakt', k)}${payLine('Trimestr', t)}</div></div>
    ${d.trend ? `<div class="box"><h4>Dinamika</h4><div>${safeHtml(String(d.trend).replace(/^📈\s*/, ''))}</div></div>` : ''}
    <div class="box"><h4>Ota-onalar</h4>${d.parents.length ? d.parents.map(p => `<div class="parent">
        <div class="t"><b>${esc(p.tg_name || 'Ota-ona')}</b><span>${esc(fmtPhone(p.phone))}${p.lang && p.lang !== 'uz' ? `, ${LANG[p.lang]} tilida` : ''}${p.active ? '' : ', botdan chiqqan'}</span></div>
        ${p.active ? `<a class="btn sm" href="#/inbox/${id}/${p.tg_id}"${course ? ` data-course="${esc(course)}"` : ''}>${ic('chat')} Yozish</a>` : ''}</div>`).join('')
      : `<div class="hint">Ota-onasi hali botga ulanmagan.</div>`}</div>`;
  $('#drawer header b').textContent = c.name;
  loadStudentWeek(id, course, '');
  if (typeof loadStudentHome === 'function') loadStudentHome(id, course); else $('#stu-home')?.remove();
  if (typeof loadStudentSocial === 'function') loadStudentSocial(id, course); else $('#stu-social')?.remove();
}
/* fan qatori: nomi, davomat chizig'i va foizi, sababsiz/sababli */
function attTone(p) { return p == null ? '' : p >= 90 ? 'ok' : p >= 75 ? 'warn' : 'bad'; }
/* sababsiz qoldirish chegarasi (fan kreditining 25%): "3 / 5" va holat belgisi */
function limCell(x) {
  if (x.limit == null) return x.kelmadi ? `<span class="icnt bad">${x.kelmadi}</span>` : '<span class="dash">0</span>';
  return `<span class="lim-c ${x.state || ''}" title="Sababsiz qoldirilgan / chegara (para). Chegaraga yetsa — yakuniy nazoratga kiritilmaydi">${x.kelmadi || 0} / ${x.limit}</span>`;
}
function limChip(x) {
  return x.state === 'over' ? '<span class="chip bordo" title="Yakuniy nazoratga kiritilmaydi, akademik qarzdor hisoblanadi">Chegaradan oshdi</span>'
    : x.state === 'warn' ? `<span class="chip warn">${x.left} para qoldi</span>` : '';
}
/* chegara nimadan: fanga ajratilgan darslar (Manage) yoki kredit */
const limBasis = x => x.pairs ? `${num(x.pairs)} para ajratilgan` : `${num(x.credits)} kredit`;
const credSrc = x => x.pairs && x.credits_src !== 'manual' ? `Manage: fanga ${num(x.pairs)} para ajratilgan${x.held != null ? `, ${num(x.held)} tasi o‘tildi` : ''} — chegara 25%` : credSrcOf(x);
const credSrcOf = x => ({ manual: 'Kredit qo‘lda kiritilgan', grades: 'Kredit baholar faylidan', debts: 'Kredit qarzdorlar ro‘yxatidan',
  code: `Kredit Manage fan kodidan (${x.code || ''})`, manage: 'Kredit Manage’dan (talabaning fanlari)' })[x.credits_src] || '';
function subjRow(x) {
  return `<div class="subj${x.state === 'over' ? ' over' : ''}"><div class="sn"><b>${esc(x.subject)}</b><span>${x.total} ta dars${x.kelmadi ? ` · <em>${x.kelmadi} sababsiz</em>` : ''}${x.limit != null ? ` / chegara ${x.limit} para (${limBasis(x)})` : ''}${x.sababli ? ` · ${x.sababli} sababli` : ''}</span>${limChip(x)}</div>
    ${pctCell(x.pct)}</div>`;
}
/* talabaning haftalik jadvali (yon panelda): har bir darsda — shu kungi belgi va fan bo'yicha davomat */
async function loadStudentWeek(id, course, week) {
  const box = $('#stu-week'); if (!box) return;
  let d;
  try { d = await api(`/api/staff/student/${id}/schedule${week ? '?week=' + week : ''}`, { course }); }
  catch (e) { box.innerHTML = '<div class="hint">Jadvalni yuklab bo‘lmadi.</div>'; return; }
  const mark = s => s ? `<span class="chip ${s === 'keldi' ? 'ok' : s === 'kelmadi' ? 'bordo' : 'warn'}">${{ keldi: 'keldi', kelmadi: 'sababsiz', sababli: 'sababli', kechikdi: 'kechikdi' }[s] || s}</span>` : '';
  const days = d.days.filter(x => x.lessons.length);
  box.innerHTML = `<div class="wk-nav"><button class="btn sm ghost" data-wk="${d.prev}" aria-label="Oldingi hafta">${ic('chevl')}</button>
      <span>${esc(dayLabel(d.monday))} · ${d.week_type} hafta</span><button class="btn sm ghost" data-wk="${d.next}" aria-label="Keyingi hafta">${ic('chevr')}</button></div>
    ${days.length ? days.map(x => `<div class="wk-day${x.today ? ' today' : ''}"><h5>${esc(x.weekday)}${x.today ? ' · bugun' : ''}</h5>
      ${x.lessons.map(l => `<div class="wk-les"><span class="tm num">${l.pair ? l.pair + '-j' : ''}${l.start ? ' ' + esc(l.start) : ''}</span>
        <div class="wl"><b>${esc(l.subject)}</b><small>${[l.type, l.room, l.teacher].filter(Boolean).map(esc).join(' · ')}</small></div>
        <div class="wr">${mark(l.status)}${l.att ? `<span class="pc ${attTone(l.att.pct)}" title="Shu fan bo‘yicha davomat (semestr)">${l.att.pct}%</span>` : ''}</div></div>`).join('')}</div>`).join('')
      : '<div class="hint">Bu haftada dars yo‘q.</div>'}`;
  box.querySelectorAll('[data-wk]').forEach(b => b.addEventListener('click', () => loadStudentWeek(id, course, b.dataset.wk)));
}
const dayLabel = iso => { const d = parseDate(iso); return d ? `${d.getDate()}-${MONTHS[d.getMonth()]}` : ''; };

/* ================================================================ jadval va fanlar (guruh bo'yicha) */
async function pSubjects(parts, q) {
  document.title = 'Jadval va fanlar — Boshqaruv paneli';
  const st = S.subjState = S.subjState || { group: '', week: '' };
  if (q && q.has('group')) st.group = q.get('group');
  view(head('Jadval va fanlar', courseSub()) + skel(60) + skel(320));
  const qs = new URLSearchParams(); if (st.group) qs.set('group', st.group); if (st.group && st.week) qs.set('week', st.week);
  const d = await api('/api/staff/subjects' + (qs.toString() ? '?' + qs : ''));
  const sch = d.schedule, canCred = !myGroups().length;
  const grid = sch ? `<div class="wk-grid">${sch.days.map(x => `<section class="wk-col${x.today ? ' today' : ''}"><header><b>${esc(x.weekday)}</b><span>${dayLabel(x.date)}${x.today ? ' · bugun' : ''}</span></header>
      ${x.lessons.length ? x.lessons.map(l => `<article class="wk-card"><div class="tm num">${l.pair ? l.pair + '-juftlik' : ''}${l.start ? ` · ${esc(l.start)}–${esc(l.end || '')}` : ''}</div>
        <b>${esc(l.subject)}</b>${l.type ? `<span class="chip muted">${esc(l.type)}${l.subgroup ? ' ' + esc(l.subgroup) : ''}</span>` : ''}
        <small>${[l.room, l.teacher].filter(Boolean).map(esc).join(' · ')}</small>
        ${l.att ? `<div class="wk-att ${attTone(l.att.pct)}" title="Guruhning shu fan bo‘yicha davomati (semestr boshidan)"><span class="bar"><i style="width:${l.att.pct}%"></i></span><b>${l.att.pct}%</b>${l.att.kelmadi ? `<em>${l.att.kelmadi} sababsiz</em>` : ''}</div>` : ''}${l.att && l.att.over_students ? `<div class="wk-over" title="Sababsiz qoldirish chegarasiga yetgan talabalar (yakuniy nazoratga kiritilmaydi)">${ic('alert')}${l.att.over_students} talaba chegarada</div>` : ''}</article>`).join('')
        : '<div class="wk-free">Dars yo‘q</div>'}</section>`).join('')}</div>` : '';
  const subj = d.subjects.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Fan</th><th class="r">Darslar</th><th>Davomat</th>
      <th class="r">Sababsiz</th><th class="r">Sababli</th><th class="r">Qoldirgan talabalar</th><th class="r" title="Fan krediti va sababsiz qoldirish chegarasi (auditoriya soatining 25%)">Kredit · chegara</th><th class="r" title="Chegaraga yetgan — yakuniy nazoratga kiritilmaydi">Chegaradan oshgan</th></tr></thead><tbody>
      ${d.subjects.map(x => `<tr class="click" data-subj="${esc(x.key)}" data-name="${esc(x.subject)}"><td class="name"><b>${esc(x.subject)}</b></td><td class="r">${x.total}</td><td>${pctCell(x.pct)}</td>
        <td class="r">${x.kelmadi ? `<span class="icnt bad">${ic('calx')}${x.kelmadi}</span>` : '<span class="dash">0</span>'}</td><td class="r">${x.sababli || '<span class="dash">0</span>'}</td>
        <td class="r">${x.missed_students ? `${x.missed_students} / ${x.students}` : `<span class="dash">0 / ${x.students}</span>`}</td>
        <td class="r nowrap">${x.limit != null ? `<span title="${esc(credSrc(x))}">${x.pairs && x.credits_src !== 'manual' ? `${num(x.pairs)} para` : `${num(x.credits)} kr`} · <b>${x.limit} para</b></span>` : '<span class="dash">kredit yo‘q</span>'}${canCred ? ` <button class="btn sm ghost" data-cred="${esc(x.key)}" data-cv="${x.credits || ''}" data-cn="${esc(x.subject)}" title="Kreditni kiritish">${ic('edit')}</button>` : ''}</td>
        <td class="r">${x.over_students ? `<span class="icnt bad">${ic('alert')}${x.over_students}</span>` : '<span class="dash">0</span>'}${x.warn_students ? ` <span class="chip warn" title="1 para qoldi">+${x.warn_students}</span>` : ''}</td></tr>`).join('')}</tbody></table></div>`
    : emptyBox('cal', 'Davomat ma’lumoti yo‘q', 'Kunlik davomat (dars bo‘yicha) yuklanganda fanlar kesimi shu yerda ko‘rinadi.');
  view(head('Jadval va fanlar', courseSub(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + `
    <div class="toolbar"><select class="select" id="sg" aria-label="Guruh"><option value="">Barcha guruhlar — faqat fanlar kesimi</option>
      ${d.groups.map(g => `<option value="${esc(g.name)}" ${group_key(g.name) === group_key(st.group) ? 'selected' : ''}>${esc(g.name)} (${g.students} talaba)</option>`).join('')}</select>
      ${sch ? `<div class="seg"><button data-w="${sch.prev}">${ic('chevl')} Oldingi</button><button disabled class="on">${dayLabel(sch.monday)} · ${sch.week_type} hafta</button><button data-w="${sch.next}">Keyingi ${ic('chevr')}</button></div>` : ''}</div>
    ${st.group ? `<section class="sec"><header>${H('cal', `Haftalik jadval — ${esc(st.group)}`, 'att')}</header><div class="pad">${grid || emptyBox('cal', 'Jadval topilmadi', 'Bu guruh uchun dars jadvali hali yuklanmagan yoki Manage’dan olinmagan.')}</div></section>`
      : `<p class="hint scope">${ic('info')}Haftalik jadvalni ko‘rish uchun guruhni tanlang. Quyida — ${myGroups().length ? 'guruhlaringiz' : 'butun kurs'} bo‘yicha fanlar kesimidagi davomat (semestr boshidan).</p>`}
    <section class="sec" style="margin-top:18px"><header>${H('activity', `Fanlar kesimida davomat${st.group ? ' — ' + esc(st.group) : ''}`, 'att')}<span class="hint">semestr boshidan · fanni bosing — talabalar</span></header>${subj}
      <p class="hint scope lim-note">${ic('info')}Fanga ajratilgan auditoriya soatining 25% va undan ortig‘ini sababsiz qoldirgan talaba shu fandan yakuniy nazoratga kiritilmaydi (akademik qarzdor): 2 kredit — 2 para, 4 kredit — 5 para, 6 kredit — 7 para. Chegara avtomatik aniqlanadi: Manage’dagi fanga ajratilgan darslar sonidan (30 para → 7), bo‘lmasa kreditdan — fan kodi (CTIR25C4 → 4 kredit), baholar fayli yoki qarzdorlar ro‘yxati${canCred ? '; topilmasa yoki noto‘g‘ri bo‘lsa — ✎ tugmasi bilan kiriting' : ''}.</p></section>`);
  $('#sg').addEventListener('change', e => { st.group = e.target.value; st.week = ''; route(); });
  $$('[data-w]').forEach(b => b.addEventListener('click', () => { st.week = b.dataset.w; route(); }));
  $$('[data-subj]').forEach(r => r.addEventListener('click', () => openSubject(r.dataset.subj, r.dataset.name, st.group)));
  $$('[data-cred]').forEach(b => b.addEventListener('click', async e => {
    e.stopPropagation();
    const v = prompt(`«${b.dataset.cn}» fanining krediti (masalan 2, 4, 6; 0 — avtomatik):`, b.dataset.cv);
    if (v == null) return;
    try { const r = await api('/api/staff/subjects/credits', { method: 'POST', json: { key: b.dataset.cred, credits: v.trim() || 0 } });
      toast(r.limit ? `Saqlandi: chegara — ${r.limit} para` : 'Saqlandi'); route(); }
    catch (err) { toast('Saqlanmadi: kredit 0–30 oralig‘ida bo‘lsin', true); }
  }));
}
const group_key = g => String(g || '').toLowerCase().replace(/[^0-9a-zа-яёўқғҳ]+/gi, '');
async function openSubject(key, name, group) {
  const dr = $('#drawer'); if (!dr) return;
  $('#dbody').innerHTML = skel(300);
  dr.classList.add('on'); $('#scrim').classList.add('on'); dr.setAttribute('aria-hidden', 'false');
  $('#drawer header b').textContent = name;
  let d;
  try { d = await api(`/api/staff/subjects/students?subject=${encodeURIComponent(key)}${group ? '&group=' + encodeURIComponent(group) : ''}`); }
  catch (e) { $('#dbody').innerHTML = emptyBox('alert', 'Yuklab bo‘lmadi'); return; }
  $('#dbody').innerHTML = `<p class="hint" style="margin-top:0">${esc(group || 'Barcha guruhlar')} · semestr boshidan · eng past davomat yuqorida. Talabani bossangiz — kartasi ochiladi.</p>
    ${d.items.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Talaba</th><th>Davomat</th><th class="r">${d.items[0] && d.items[0].limit != null ? `Sababsiz / ${d.items[0].limit}` : 'Sababsiz'}</th><th class="r">Sababli</th></tr></thead><tbody>
      ${d.items.map(x => `<tr class="click${x.state === 'over' ? ' row-over' : ''}" data-student="${x.id}"><td class="name"><b>${esc(x.name)}</b><span>${esc(x.group || '')} · ${x.total} ta dars</span>${limChip(x)}</td><td>${pctCell(x.pct)}</td>
        <td class="r">${limCell(x)}</td><td class="r">${x.sababli || '<span class="dash">0</span>'}</td></tr>`).join('')}</tbody></table></div>`
      : emptyBox('cal', 'Ma’lumot yo‘q')}`;
}

/* ================================================================ chora ko'rish (intizomiy choralar) */
const MEAS = { ogohlantirish: { t: 'Dekan ogohlantirishi', s: 'Ogohlantirish', c: 'warn', doc: 'Dekan farmoyishi' },
  hayfsan: { t: 'Hayfsan', s: 'Hayfsan', c: 'bordo', doc: 'Buyruq' }, boshqa: { t: 'Boshqa chora', s: 'Boshqa', c: 'muted', doc: 'Qaror' },
  xat: { t: 'Ota-onaga ogohlantirish xati', s: 'Ota-onaga xat', c: 'info', doc: 'Ogohlantirish xati' } };
const GRND = { davomat: 'Davomat', tartib: 'Ichki tartib', trimestr: 'Trimestr qarzi' };
const TST = { new: ['Xat yuborilmagan', 'bordo'], draft: ['Xat tayyorlanmoqda', 'muted'], sent: ['Xat yuborilgan', 'ok'] };
const CST = { new: ['Yangi', 'bordo'], more: ['Yana qoldirgan', 'bordo'], asked: ['Sababi so‘ralgan', 'warn'], draft: ['Hujjat tayyorlanmoqda', 'muted'],
  excused: ['Sababli', 'ok'], removed: ['Ro‘yxatdan o‘chirilgan', 'muted'] };
const FKIND = { imzolangan: 'Imzolangan nusxa', xat: 'Ota-onaga xat', tushuntirish: 'Tushuntirish xati', bildirishnoma: 'Bildirishnoma',
  dalolatnoma: 'Dalolatnoma', asos: 'Asoslovchi hujjat (ma’lumotnoma va h.k.)', farmoyish: 'Dekan farmoyishi', buyruq: 'Buyruq', boshqa: 'Boshqa hujjat' };
const isPdf = f => /\.pdf$/i.test(f.name || '');
const ORIG = ['imzolangan', 'farmoyish', 'buyruq', 'xat'];
/* asl nusxa yuklanganda: ota-onalarga avtomatik yuborilgani (yoki chora chiqarilgach yuborilishi) */
function autoMsg(a, kind, o) {
  if (a && a.files) return ` · ota-onalarga yuborildi: ${a.students} talaba (${a.parents} ota-ona)${a.skipped.length ? ` · ${a.skipped.length} tasi yuborilmadi: ${a.skipped[0].reason}` : ''}`;
  if (ORIG.includes(kind) && o && o.status !== 'issued') return ' · chora chiqarilgach ota-onalarga avtomatik yuboriladi';
  return '';
}
const fileTone = f => (f.sent_at ? 'ok' : f.send_note ? 'warn' : 'muted');
const CH_ERR = { no_basis: 'Avval 1-bosqich: imzolangan bildirishnoma (PDF) yoki tushuntirish xatlari', no_signed: 'Avval imzolangan nusxa (PDF) yuklansin',
  not_pdf: 'Imzolangan nusxa PDF bo‘lsin', no_number: 'Raqami va sanasini kiriting', too_big: 'Fayl juda katta (20 MB gacha)' };
/* dalolatnomaning o'z raqami (arxivda qidirish uchun); bekor qilinsa — null (yuklanmaydi) */
async function askDocNo(kind) {
  if (kind === 'bildirishnoma') {
    const v = await formDlg('Imzolangan bildirishnoma', `<p>Kurs koordinatori bildirishnomasi — 1-bosqich asosi. Sanasi farmoyish/buyruqdagi «Asos:» qatoriga yoziladi; yuklangach dekan bosqichiga o‘tiladi.</p><div class="cols2">
      <label class="field"><span>Sanasi</span><input class="input" type="date" name="date" value="${todayIso()}" required></label>
      <label class="field"><span>Kiruvchi raqami (bo‘lsa)</span><input class="input" name="number" placeholder="Masalan: 45"></label></div>`, 'Yuklash');
    return v ? { number: v.get('number') || '', date: v.get('date') || '' } : null;
  }
  if (kind !== 'dalolatnoma') return {};
  const v = await formDlg('Dalolatnoma — raqam va sana', `<p>Asl nusxa arxivda shu raqam bo‘yicha topiladi (raqami bo‘lmasa — bo‘sh qoldiring).</p><div class="cols2">
    <label class="field"><span>Raqami</span><input class="input" name="number" placeholder="Masalan: 3"></label>
    <label class="field"><span>Sanasi</span><input class="input" type="date" name="date" value="${todayIso()}"></label></div>`, 'Yuklash');
  return v ? { number: v.get('number') || '', date: v.get('date') || '' } : null;
}
/* hujjatni brauzerda ochish (PDF, rasm) — oyna darhol ochiladi, keyin fayl yuklanadi (qalqib chiquvchi oyna to'sig'i uchun) */
async function viewFile(fid) {
  const w = window.open('', '_blank');
  try { const r = await api(`/api/staff/discipline/files/${fid}?view=1`, { raw: true });
    const url = URL.createObjectURL(await r.blob());
    if (w) w.location = url; else location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 120000); }
  catch (e) { if (w) w.close(); toast('Ochib bo‘lmadi', true); }
}
async function editAddress(sid, name, cur) {
  const v = await formDlg('Yashash manzili', `<p>${esc(name)} — ota-onaga xatdagi manzil (kontingent faylida bo‘lmasa, shu yerda kiritiladi).</p>
    <label class="field"><span>Manzil</span><textarea class="input textarea" name="address" rows="2" placeholder="Viloyat, tuman, MFY, ko‘cha, uy">${esc(cur || '')}</textarea></label>`);
  if (!v) return false;
  try { await api('/api/staff/discipline/address', { method: 'POST', json: { sid, address: v.get('address') } }); toast('Saqlandi'); return true; }
  catch (e) { toast('Saqlanmadi', true); return false; }
}
const dmy = iso => { const d = parseDate(iso); return d ? `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}` : ''; };
const todayIso = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
function formDlg(title, inner, okText = 'Saqlash', danger = false) {
  return new Promise(res => {
    const d = $('#dlg');
    d.innerHTML = `<form method="dialog" class="wide"><h3>${esc(title)}</h3>${inner}
      <div class="row"><button class="btn" value="cancel" formnovalidate>Bekor qilish</button>
        <button class="btn ${danger ? 'danger solid' : 'primary'}" value="ok">${esc(okText)}</button></div></form>`;
    d.returnValue = '';
    d.onclose = () => res(d.returnValue === 'ok' ? new FormData(d.querySelector('form')) : null);
    d.showModal();
    d.querySelector('input:not([type=hidden]), textarea')?.focus();
  });
}
async function pChora(parts, q) {
  document.title = 'Chora ko‘rish — Boshqaruv paneli';
  const st = S.chora = S.chora || { tab: 'list', m: 'ogohlantirish', sel: new Set(), hm: '', hg: '' };
  if (q && (q.get('tab') || q.get('m') || q.has('aq') || q.has('hm'))) {  // havoladan (masalan, «Kurs holati»dan) — bir marta; keyin yorliqlar o'zi almashadi
    if (q.get('tab')) st.tab = q.get('tab');
    if (q.get('m')) st.m = q.get('m');
    if (q.has('hm')) { st.hm = q.get('hm'); st.hg = ''; }
    if (q.has('aq')) { st.aq = q.get('aq'); st.at = ''; }
    history.replaceState(null, '', '#/chora');
  }
  view(head('Chora ko‘rish', courseSub()) + skel(70) + skel(320));
  const d = await api('/api/staff/discipline');
  S.chData = d;
  S.badges.chora = (d.counts.ogohlantirish || 0) + (d.counts.hayfsan || 0); paintBadges();
  const drafts = d.orders.filter(o => !o.archived_at && !o.done).length;
  const tab = (k, icn, label, n) => `<button data-tab="${k}" class="${st.tab === k ? 'on' : ''}" role="tab" aria-selected="${st.tab === k}">${ic(icn)} ${label}${n ? ` <span class="n">${n}</span>` : ''}</button>`;
  const tabs = `<div class="toolbar"><div class="seg" role="tablist">${tab('list', 'alert', 'Chegaraga yetganlar', S.badges.chora)}${tab('docs', 'file', 'Hujjatlar', drafts)}
    ${tab('hist', 'chart', 'Chora ko‘rilganlar')}${tab('arch', 'folder', 'Arxiv')}${tab('tpl', 'book', 'Shablonlar va sozlama')}</div><span class="grow"></span>
    <button class="btn" data-ch="tartib">${ic('plus')} Ichki tartib bo‘yicha chora</button></div>`;
  let body = '';
  if (st.tab === 'list') body = choraList(d, st);
  else if (st.tab === 'docs') body = choraDocs(d);
  else if (st.tab === 'hist') body = `<div id="ch-hist">${skel(90)}${skel(260)}</div>`;
  else if (st.tab === 'arch') body = choraArch(st);
  else body = choraTpl(d);
  view(head('Chora ko‘rish', courseSub(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + tabs + body);
  $$('[data-tab]').forEach(b => b.addEventListener('click', () => { st.tab = b.dataset.tab; route(); }));
  $('[data-ch="tartib"]').addEventListener('click', () => choraTartib(d));
  if (st.tab === 'list') (st.m === 'trimestr' ? bindChoraTri : bindChoraList)(d, st);
  if (st.tab === 'docs') bindChoraDocs(d);
  if (st.tab === 'hist') loadChoraHist(st);
  if (st.tab === 'arch') bindChoraArch(st);
  if (st.tab === 'tpl') bindChoraTpl(d);
}
function choraSeg(d, m) {
  return `<div class="seg">${['ogohlantirish', 'hayfsan'].map(k => `<button data-m="${k}" class="${k === m ? 'on' : ''}">${MEAS[k].t} · ${num(d.thresholds[k], 0)}+ soat
    ${d.counts[k] ? ` <span class="n">${d.counts[k]}</span>` : ''}</button>`).join('')}<button data-m="trimestr" class="${m === 'trimestr' ? 'on' : ''}">${ic('mail')} Trimestr qarzi — ota-onaga xat
    ${d.trimestr.count ? ` <span class="n">${d.trimestr.count}</span>` : ''}</button></div>`;
}
function choraList(d, st) {
  if (st.m === 'trimestr') return choraTri(d, st);
  const m = st.m, lim = d.thresholds[m];
  const rows = d[m];
  const excl = d.excluded.filter(x => x.measure === m);
  const seg = choraSeg(d, m);
  const rule = m === 'ogohlantirish'
    ? `Akademik nizom (6-bob, 113-modda): sababsiz qoldirilgan darslar <b>${num(lim, 0)} soatdan</b> oshsa — dekan farmoyishi bilan «Ogohlantirish».`
    : `Akademik nizom (6-bob, 113-modda): sababsiz qoldirilgan darslar <b>${num(lim, 0)} soatdan</b> oshsa — universitet buyrug‘i bilan «Hayfsan».`;
  const tbl = rows.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl ch-tbl"><thead><tr>
      <th class="cbx"><input type="checkbox" data-all aria-label="Hammasini tanlash"></th><th>Talaba</th><th class="r">Sababsiz</th><th>Holat</th>
      <th>Avval ko‘rilgan chora</th><th class="r">Amallar</th></tr></thead><tbody>
      ${rows.map(x => { const [lab, tone] = x.state === 'draft' && x.stage ? [STG_S[x.stage] || STG[x.stage], 'muted'] : CST[x.state] || [x.state, 'muted']; const can = x.state !== 'draft';
        return `<tr data-sid="${x.sid}"><td class="cbx">${can ? `<input type="checkbox" data-pick="${x.sid}" ${st.sel.has(x.sid) ? 'checked' : ''} aria-label="Tanlash">` : ''}</td>
        <td class="name click" data-chs="${x.sid}"><b>${esc(x.name)}</b><span>${esc(x.group)}${x.hemis_id ? ', HEMIS ' + esc(x.hemis_id) : ''}</span></td>
        <td class="r nowrap"><b>${pairs(x.hours)}</b><div class="sub-l">${x.percent != null ? `davomat ${Math.round(x.percent)}%` : ''}</div></td>
        <td><span class="chip ${tone}">${lab}</span>${x.state === 'more' && x.excused_hours != null ? `<div class="sub-l">avval sababli: ${pairs(x.excused_hours)}</div>` : ''}
          ${x.asked_at ? `<div class="sub-l">${ic('chat')} so‘ralgan: ${when(x.asked_at)}</div>` : ''}${x.note ? `<div class="sub-l">${esc(x.note)}</div>` : ''}</td>
        <td>${x.prior.length ? `<span class="sub-l">${esc(x.prior_text)}</span>` : '<span class="dash">—</span>'}</td>
        <td class="r nowrap">${can ? `<button class="btn sm ghost" data-ask="${x.sid}" title="Ota-onadan sababini so‘rash (bot orqali)" ${x.parents ? '' : 'disabled'}>${ic('chat')} So‘rash</button>
          <button class="btn sm ghost" data-exc="${x.sid}" title="Sababli — ro‘yxatdan chiqarish">${ic('check')} Sababli</button>
          <button class="btn sm ghost" data-rem="${x.sid}" title="Ro‘yxatdan o‘chirish">${ic('x')}</button>`
          : `<a class="btn sm ghost" href="#/chora?tab=docs">${ic('file')} Hujjat</a>`}</td></tr>`; }).join('')}</tbody></table></div>`
    : emptyBox('ok', 'Chegaraga yetgan talaba yo‘q', `Sababsiz qoldirishlari ${num(lim, 0)} soatdan oshgan talaba topilmadi.`);
  const ex = excl.length ? `<details class="sec" style="margin-top:18px"><summary class="pad">${ic('check')} Ro‘yxatdan chiqarilganlar — ${excl.length} ta (sababli / o‘chirilgan)</summary>
    <div class="tbl-wrap" style="max-height:none"><table class="tbl"><tbody>${excl.map(x => `<tr><td class="name click" data-chs="${x.sid}"><b>${esc(x.name)}</b><span>${esc(x.group)} · hujjatlar (ma’lumotnoma)</span></td>
      <td class="r">${pairs(x.hours)}</td><td><span class="chip ${CST[x.state][1]}">${CST[x.state][0]}</span>${x.note ? `<div class="sub-l">${esc(x.note)}</div>` : ''}</td>
      <td class="r"><button class="btn sm ghost" data-res="${x.sid}">${ic('refresh')} Qaytarish</button></td></tr>`).join('')}</tbody></table></div></details>` : '';
  return `<div class="toolbar">${seg}</div>
    <p class="hint scope">${ic('info')}<span>${rule} Davr: ${dmy(d.period.from)} — ${dmy(d.period.to)}. Sababini aniqlang: sababli bo‘lsa — «Sababli» (ro‘yxatdan chiqadi), keyin yana qoldirsa — o‘zi qaytib chiqadi.</span></p>
    <section class="sec">${tbl}${rows.length ? `<div class="pad ch-foot"><span id="ch-sel">Tanlangan: <b>${st.sel.size}</b></span>
      <button class="btn primary" data-make ${st.sel.size ? '' : 'disabled'}>${ic('file')} Tanlanganlar uchun hujjatlarni tayyorlash</button></div>` : ''}</section>${ex}`;
}
function bindChoraList(d, st) {
  const m = st.m;
  const valid = new Set(d[m].filter(x => x.state !== 'draft').map(x => x.sid));
  [...st.sel].forEach(s => { if (!valid.has(s)) st.sel.delete(s); });
  const paint = () => { $('#ch-sel') && ($('#ch-sel').innerHTML = `Tanlangan: <b>${st.sel.size}</b>`); const b = $('[data-make]'); if (b) b.disabled = !st.sel.size; };
  $$('[data-m]').forEach(b => b.addEventListener('click', () => { st.m = b.dataset.m; st.sel.clear(); route(); }));
  $$('[data-pick]').forEach(c => c.addEventListener('change', () => { const s = Number(c.dataset.pick); c.checked ? st.sel.add(s) : st.sel.delete(s); paint(); }));
  $('[data-all]')?.addEventListener('change', e => { $$('[data-pick]').forEach(c => { c.checked = e.target.checked; const s = Number(c.dataset.pick); c.checked ? st.sel.add(s) : st.sel.delete(s); }); paint(); });
  const act = async (sid, action, note = '') => {
    try { await api('/api/staff/discipline/case', { method: 'POST', json: { sid, measure: m, action, note } }); st.sel.delete(sid); route(); }
    catch (e) { toast(e.message === 'in_order' ? 'Talaba hujjatga kiritilgan — avval hujjatdan chiqaring' : 'Saqlanmadi', true); }
  };
  $$('[data-exc]').forEach(b => b.addEventListener('click', async () => {
    const x = d[m].find(r => r.sid === Number(b.dataset.exc));
    const v = await formDlg('Sababli deb belgilash', `<p>${esc(x.name)} — ${pairs(x.hours)}. Talaba ro‘yxatdan chiqariladi; keyin yana sababsiz qoldirsa — qaytib chiqadi.</p>
      <label class="field"><span>Sababi (hujjat)</span><textarea class="input textarea" name="note" rows="3" required placeholder="Masalan: kasallik — 12.10–20.10 ma’lumotnoma (086-shakl)"></textarea></label>`, 'Sababli');
    if (v) act(x.sid, 'excuse', v.get('note'));
  }));
  $$('[data-rem]').forEach(b => b.addEventListener('click', async () => {
    const x = d[m].find(r => r.sid === Number(b.dataset.rem));
    const v = await formDlg('Ro‘yxatdan o‘chirish', `<p>${esc(x.name)} shu chora ro‘yxatidan o‘chiriladi (masalan, ma’lumot noto‘g‘ri bo‘lsa).</p>
      <label class="field"><span>Izoh</span><input class="input" name="note" placeholder="Nega o‘chirilmoqda"></label>`, 'O‘chirish', true);
    if (v) act(x.sid, 'remove', v.get('note'));
  }));
  $$('[data-res]').forEach(b => b.addEventListener('click', () => act(Number(b.dataset.res), 'restore')));
  $$('[data-ask]').forEach(b => b.addEventListener('click', async () => {
    const x = d[m].find(r => r.sid === Number(b.dataset.ask));
    if (!await confirmDlg('Ota-onadan sababini so‘rash', `${esc(x.name)} ning ota-onasiga bot orqali xabar boradi: ${pairs(x.hours)} sababsiz qoldirilgani va sababi bo‘lsa — yozib, ma’lumotnomani yuborishi so‘raladi. Javobi «Xabarlar» bo‘limiga keladi.`, 'Yuborish')) return;
    try { const r = await api('/api/staff/discipline/ask', { method: 'POST', json: { sid: x.sid, measure: m } }); toast(`Yuborildi: ${r.delivered} / ${r.parents} ota-ona`); route(); }
    catch (e) { toast(e.message === 'no_parents' ? 'Ota-onasi botga ulanmagan' : 'Yuborilmadi', true); }
  }));
  $('[data-make]')?.addEventListener('click', async () => {
    const items = [...st.sel].map(sid => ({ sid }));
    try { await api('/api/staff/discipline/orders', { method: 'POST', json: { measure: m, ground: 'davomat', items } });
      st.sel.clear(); st.tab = 'docs'; toast('Hujjatlar tayyor — yuklab oling'); route(); }
    catch (e) { toast('Hujjat yaratilmadi', true); }
  });
}
function choraTri(d, st) {
  const t = d.trimestr, rows = t.items;
  st.tsel = st.tsel || new Set();
  const tbl = rows.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl ch-tbl"><thead><tr>
      <th class="cbx"><input type="checkbox" data-tall aria-label="Hammasini tanlash"></th><th>Talaba</th><th class="r">Qarz</th><th>Yashash manzili (xat uchun)</th><th>Holat</th></tr></thead><tbody>
    ${rows.map(x => { const [lab, tone] = TST[x.state]; const can = x.state !== 'draft';
      return `<tr><td class="cbx">${can ? `<input type="checkbox" data-tpick="${x.sid}" ${st.tsel.has(x.sid) ? 'checked' : ''} aria-label="Tanlash">` : ''}</td>
        <td class="name click" data-chs="${x.sid}"><b>${esc(x.name)}</b><span>${esc(x.group)}${x.hemis_id ? ', HEMIS ' + esc(x.hemis_id) : ''}</span></td>
        <td class="r nowrap"><b>${money(x.debt)}</b><div class="sub-l">${dmy(x.as_of)} holatiga</div></td>
        <td><div class="wrapc">${x.address ? `<span class="sub-l">${esc(x.address)}</span>` : '<span class="chip warn">kiritilmagan</span>'}
          <button class="btn sm ghost" data-addr="${x.sid}" title="Manzilni kiritish">${ic('edit')}</button></div></td>
        <td><span class="chip ${tone}">${lab}</span>${x.state === 'sent' ? `<div class="sub-l">${x.sent_number ? '№ ' + esc(x.sent_number) + ', ' : ''}${dmy(x.sent_date)}${x.sent_amount ? ' · ' + money(x.sent_amount) : ''}</div>` : ''}
          ${x.parents ? '' : '<div class="sub-l">ota-onasi botga ulanmagan</div>'}</td></tr>`; }).join('')}</tbody></table></div>`
    : emptyBox('ok', 'Trimestr qarzdori yo‘q', 'Trimestr qarzdorligi hisobotida qarzi bor talaba topilmadi.');
  return `<div class="toolbar">${choraSeg(d, 'trimestr')}</div>
    <p class="hint scope">${ic('info')}<span>Qayta o‘qish (trimestr) shartnomasi bo‘yicha qarzdorlar — oxirgi hisobot${t.as_of ? ` (${dmy(t.as_of)})` : ''} bo‘yicha. Tanlanganlarning ota-onasiga ogohlantirish xati tayyorlanadi — har biriga alohida, JIDU blankasida: qarz miqdori, sana va to‘lash muddati bilan.</span></p>
    <section class="sec">${tbl}${rows.length ? `<div class="pad ch-foot"><span id="ch-tsel">Tanlangan: <b>${st.tsel.size}</b></span>
      <button class="btn primary" data-tmake ${st.tsel.size ? '' : 'disabled'}>${ic('mail')} Tanlanganlar uchun ota-onaga xat tayyorlash</button></div>` : ''}</section>`;
}
function bindChoraTri(d, st) {
  st.tsel = st.tsel || new Set();
  const valid = new Set(d.trimestr.items.filter(x => x.state !== 'draft').map(x => x.sid));
  [...st.tsel].forEach(s => { if (!valid.has(s)) st.tsel.delete(s); });
  const paint = () => { $('#ch-tsel') && ($('#ch-tsel').innerHTML = `Tanlangan: <b>${st.tsel.size}</b>`); const b = $('[data-tmake]'); if (b) b.disabled = !st.tsel.size; };
  $$('[data-m]').forEach(b => b.addEventListener('click', () => { st.m = b.dataset.m; st.sel.clear(); route(); }));
  $$('[data-tpick]').forEach(c => c.addEventListener('change', () => { const s = Number(c.dataset.tpick); c.checked ? st.tsel.add(s) : st.tsel.delete(s); paint(); }));
  $('[data-tall]')?.addEventListener('change', e => { $$('[data-tpick]').forEach(c => { c.checked = e.target.checked; const s = Number(c.dataset.tpick); c.checked ? st.tsel.add(s) : st.tsel.delete(s); }); paint(); });
  $$('[data-addr]').forEach(b => b.addEventListener('click', async () => { const x = d.trimestr.items.find(r => r.sid === Number(b.dataset.addr)); if (await editAddress(x.sid, x.name, x.address)) route(); }));
  $('[data-tmake]')?.addEventListener('click', async () => {
    const noAddr = d.trimestr.items.filter(x => st.tsel.has(x.sid) && !x.address).length;
    const dl = new Date(); dl.setDate(dl.getDate() + 14);
    const iso = `${dl.getFullYear()}-${String(dl.getMonth() + 1).padStart(2, '0')}-${String(dl.getDate()).padStart(2, '0')}`;
    const v = await formDlg('Ota-onaga ogohlantirish xati', `<p><b>${st.tsel.size} ta</b> talabaning ota-onasiga xat tayyorlanadi (trimestr to‘lovi qarzdorligi).</p>
      <label class="field"><span>Qarzni to‘lash muddati (xatga yoziladi)</span><input class="input" type="date" name="deadline" value="${iso}" required></label>
      ${noAddr ? `<div class="note warn">${ic('alert')}<span>${noAddr} ta talabaning manzili kiritilmagan — xatda bo‘sh joy qoladi (keyin ham kiritish mumkin).</span></div>` : ''}`, 'Xatlarni tayyorlash');
    if (!v) return;
    try { await api('/api/staff/discipline/orders', { method: 'POST', json: { measure: 'xat', ground: 'trimestr', deadline: v.get('deadline'), items: [...st.tsel].map(sid => ({ sid })) } });
      st.tsel.clear(); st.tab = 'docs'; toast('Xatlar tayyor — yuklab oling'); route(); }
    catch (e) { toast('Xat yaratilmadi', true); }
  });
}
const STG = { 1: 'Asos', 2: 'Farmoyish / buyruq', 3: 'Ota-onaga xat', 4: 'Yakunlangan' };
const STG_S = { 1: '1-bosqich: asos kutilmoqda', 2: '2-bosqich: farmoyish/buyruq', 3: '3-bosqich: ota-onaga xat' };
const orderCard = o => (o.measure === 'xat' ? letterCard(o) : stagedCard(o));
/* chora jarayoni A dan B gacha: 1 — asos (tushuntirish xati / dalolatnoma yoki kurs koordinatori bildirishnomasi),
   2 — dekan farmoyishi / universitet buyrug'i (1-bosqichsiz ochilmaydi), 3 — ota-onaga xat (2-bosqichdan keyin) */
function stagedCard(o) {
  const M = MEAS[o.measure] || MEAS.boshqa, S = o.stages, cur = S.current, B = S.basis, L = S.letters;
  const draft = o.status === 'draft', issued = o.status === 'issued', cancelled = o.status === 'cancelled';
  const st = n => (cancelled ? 'lock' : n < cur ? 'done' : n === cur ? 'cur' : 'lock');
  const has = k => o.doc_kinds.some(x => x.kind === k);
  const main = o.doc_kinds.find(x => x.kind === 'farmoyish' || x.kind === 'buyruq');
  const docT = o.measure === 'hayfsan' ? 'Hayfsan — universitet buyrug‘i' : o.measure === 'ogohlantirish' ? 'Dekan ogohlantirishi — dekan farmoyishi' : `${M.t} — qaror`;
  const fchips = list => list.map(f => `<span class="chip ${fileTone(f)}" title="${esc(f.send_note || (ORIG.includes(f.kind) ? 'Chora chiqarilgach ota-onalarga avtomatik yuboriladi' : ''))}">${ic(f.sent_at ? 'send' : 'file')}<a href="#" data-file="${f.id}">${esc(FKIND[f.kind] || f.kind)}: ${esc(f.name)}</a><button data-fdel="${f.id}" aria-label="O‘chirish">${ic('x')}</button></span>`).join('');
  const common = kinds => o.files.filter(f => !f.case_id && kinds.includes(f.kind));
  const upl = (kind, label, cls = 'ghost', pdf = false) => `<label class="btn sm ${cls}">${ic('upload')} ${label}<input type="file" data-upk="${kind}" ${pdf ? 'accept=".pdf,application/pdf"' : ''} hidden multiple></label>`;
  const OD = S.order, unsignedCase = id => (B.unsigned || []).includes(id);
  const head = (n, title, chip) => `<div class="st-h"><span class="st-n">${st(n) === 'done' ? ic('check') : n}</span><b>${title}</b>${chip}</div>`;
  const stChip = cancelled ? '<span class="chip muted">Bekor qilingan</span>' : cur === 4 ? `<span class="chip ok">${ic('check')} Yakunlangan</span>`
    : `<span class="chip warn">${cur}-bosqich: ${STG[cur]}</span>`;
  const s1 = `<li class="step ${st(1)}">${head(1, 'Asos: talabaning tushuntirish xati yoki kurs koordinatori bildirishnomasi',
      B.recorded ? `<span class="chip ok">${[B.bildirishnoma ? `bildirishnoma${B.date ? ' · ' + dmy(B.date) : ''}` : '', B.students ? `tushuntirish xati: ${B.tushuntirish}${B.dalolatnoma ? `, dalolatnoma: ${B.dalolatnoma}` : ''} / ${B.total}` : ''].filter(Boolean).join(' + ')}</span>`
        : issued ? '<span class="chip muted">qayd etilmagan</span>' : `<span class="chip warn">kutilmoqda${B.students ? ` · ${B.students} / ${B.total}` : ''}</span>`)}
    <div class="st-b"><div class="opt"><div class="opt-h"><b>A. Kurs koordinatori bildirishnomasi</b> — dekan nomiga, barcha talabalar uchun</div>
        <div class="wrapc">${has('bildirishnoma') ? `<button class="btn sm" data-doc="bildirishnoma">${ic('download')} Bildirishnoma (Word)</button>` : ''}
          ${B.bildirishnoma ? `<span class="chip ok">${ic('check')} Imzolangan nusxa yuklangan${B.number ? ' · № ' + esc(B.number) : ''}${B.date ? ' · ' + dmy(B.date) : ''}</span>`
            : draft ? upl('bildirishnoma', 'Imzolangan bildirishnomani yuklash (PDF)', 'primary', true) : ''}
          ${fchips(common(['bildirishnoma']))}</div>
        ${!B.bildirishnoma && draft ? '<p class="hint" style="margin:6px 0 0">Bildirishnoma imzolangach PDF nusxasini yuklang — shundan keyin dekan bosqichiga (farmoyish / buyruq) o‘tiladi.</p>' : ''}</div>
      <div class="opt-or"><span>yoki</span></div>
      <div class="opt"><div class="opt-h"><b>B. Talabalarning tushuntirish xatlari</b> — har bir talabadan; yozishdan bosh tortsa — dalolatnoma</div>
        <ul class="ord-st">${o.cases.map(c => `<li><span><b class="click" data-chs="${c.student_id}">${esc(c.full_name)}</b> <span class="sub-l">${esc(c.group_name || '')}${c.hours != null ? ' · ' + pairs(c.hours) : ''}${c.note ? ' · ' + esc(c.note) : ''}</span>
            ${c.basis === 'tushuntirish' && !unsignedCase(c.id) ? `<span class="chip ok">${ic('check')} tushuntirish xati yuklangan</span>`
              : c.basis === 'tushuntirish' ? '<span class="chip warn">tushuntirish xati yuklanmagan</span>'
              : c.basis === 'dalolatnoma' ? `<span class="chip ${unsignedCase(c.id) ? 'warn' : 'ok'}">yozmadi — dalolatnoma${unsignedCase(c.id) ? ' (imzolangani yuklanmagan)' : ''}</span>` : '<span class="chip muted">tushuntirish xati kutilmoqda</span>'}</span>
          <span class="nowrap">${c.basis && !(c.basis === 'tushuntirish' && unsignedCase(c.id)) ? (draft ? `<button class="btn sm ghost" data-cb="${c.id}" data-v="" title="Bekor qilish">${ic('refresh')}</button>` : '')
            : `<label class="btn sm ghost" title="Talabaning tushuntirish xati (skan: PDF yoki rasm)">${ic('upload')} Yuklash<input type="file" data-cup="${c.id}" accept=".pdf,image/*" hidden></label>
              ${c.basis ? '' : `<button class="btn sm ghost" data-cb="${c.id}" data-v="dalolatnoma" title="Yozishdan bosh tortdi — dalolatnoma tuziladi">Yozmadi</button>`}`}
            <button class="btn sm ghost" data-chs="${c.student_id}" title="Talabaning hujjatlari">${ic('folder')}${c.files_n ? ` ${c.files_n}` : ''}</button>
            ${draft ? `<button class="btn sm ghost" data-dcase="${c.id}" title="Hujjatdan chiqarish">${ic('x')}</button>` : ''}</span></li>`).join('')}</ul>
        ${B.dalolatnoma && has('dalolatnoma') ? `<div class="wrapc"><button class="btn sm" data-doc="dalolatnoma">${ic('download')} Dalolatnoma (Word) — yozmaganlar</button>
          ${fchips(common(['dalolatnoma']))}${B.dalolatnoma_pdf ? '' : upl('dalolatnoma', 'Imzolangan dalolatnomani yuklash (PDF)', 'primary', true)}</div>` : ''}</div></div></li>`;
  const sigLbl = o.measure === 'hayfsan' ? 'buyruqni' : o.measure === 'ogohlantirish' ? 'farmoyishni' : 'qarorni';
  const s2 = `<li class="step ${st(2)}">${head(2, docT, issued && OD.signed ? `<span class="chip ok">${o.number ? '№ ' + esc(o.number) + ' · ' : ''}${dmy(o.date)}</span>`
      : issued ? `<span class="chip warn">${o.number ? '№ ' + esc(o.number) + ' · ' : ''}imzolangan nusxasi yuklanmagan</span>`
      : cur < 2 ? '<span class="chip muted">1-bosqichdan keyin</span>' : '<span class="chip warn">imzolangan nusxasi kutilmoqda</span>')}
    <div class="st-b">${cur < 2 && !issued ? `<p class="hint">Avval 1-bosqich: imzolangan bildirishnoma (PDF) yuklansin yoki har bir talabaning tushuntirish xati (yozmasa — imzolangan dalolatnoma) yuklansin. Shundan keyin ${main ? main.title.toLowerCase() : 'hujjat'} shu asosda tayyorlanadi.</p>`
      : `<p class="hint">Asos: <i>${esc(o.basis_text || '')}</i></p>
      <div class="wrapc">${main ? `<button class="btn sm" data-doc="${main.kind}">${ic('download')} ${main.title} (Word)</button>` : ''}
        ${draft ? `<button class="btn sm primary" data-sign>${ic('upload')} Imzolangan ${sigLbl} yuklash (PDF)</button>`
          : issued && !OD.signed ? `<button class="btn sm primary" data-sign>${ic('upload')} Imzolangan nusxani yuklash (PDF)</button>` : ''}
        ${issued ? `<button class="btn sm ghost" data-issue>${ic('edit')} Raqam va sana</button>` : ''}
        ${fchips(common(['imzolangan', 'farmoyish', 'buyruq']))}${issued && OD.signed ? upl('imzolangan', 'Yana nusxa') : ''}</div>
      ${draft ? '<p class="hint" style="margin:6px 0 0">Dekan imzolagach PDF nusxasini raqami va sanasi bilan yuklang — chora rasman ko‘rilgan hisoblanadi, ota-onasi botga ulangan talabalarga hujjat darhol yuboriladi (har biriga faqat o‘z farzandi, boshqalari yopilgan), keyin ota-onaga xat bosqichi ochiladi.</p>' : ''}`}</div></li>`;
  const s3 = `<li class="step ${st(3)}">${head(3, 'Ota-onaga xat', OD.done ? `<span class="chip ${L.done ? 'ok' : 'warn'}">${L.sent} / ${L.total} yuborilgan</span>` : '<span class="chip muted">2-bosqichdan keyin</span>')}
    <div class="st-b">${!OD.done ? `<p class="hint">Xatda ${o.measure === 'hayfsan' ? 'buyruq' : 'farmoyish'} raqami va sanasi bo‘ladi — shuning uchun avval 2-bosqich: imzolangan ${o.measure === 'hayfsan' ? 'buyruq' : 'farmoyish'} (PDF) yuklansin.</p>`
      : `<ul class="ord-st">${o.cases.map(c => `<li><span><b class="click" data-chs="${c.student_id}">${esc(c.full_name)}</b>
            ${c.letter_date ? `<span class="chip ok">${ic('check')} ${c.letter_no ? '№ ' + esc(c.letter_no) + ' · ' : ''}${dmy(c.letter_date)}</span>` : '<span class="chip muted">yuborilmagan</span>'}
            ${!c.address ? `<button class="chip warn" data-caddr="${c.student_id}" title="Xat uchun yashash manzili">${ic('edit')} manzil yo‘q</button>` : ''}</span>
          <span class="nowrap"><button class="btn sm ghost" data-cxat="${c.id}" title="Shu talabaning ota-onasiga xat (Word)">${ic('mail')} Xat</button>
            <button class="btn sm ghost" data-chs="${c.student_id}" title="Imzolangan xatni yuklash, PDF ni ota-onaga yuborish">${ic('folder')}${c.files_n ? ` ${c.files_n}` : ''}</button></span></li>`).join('')}</ul>
        <div class="wrapc">${o.cases.length > 1 ? `<button class="btn sm" data-doc="xat">${ic('mail')} Barcha xatlar (ZIP)</button>` : ''}
          <button class="btn sm primary" data-letters>${ic('send')} Xatlar yuborildi deb belgilash</button></div>`}</div></li>`;
  const other = o.files.filter(f => !f.case_id && !['bildirishnoma', 'imzolangan', 'farmoyish', 'buyruq', ...(B.dalolatnoma ? ['dalolatnoma'] : [])].includes(f.kind));
  return `<article class="sec ord" data-oid="${o.id}"><header><h2><span class="h-ic c-${o.measure === 'hayfsan' ? 'risk' : 'acad'}" aria-hidden="true">${ic(o.measure === 'hayfsan' ? 'shield' : 'alert')}</span>
      ${M.t} <small>${GRND[o.ground] || ''} · ${o.cases.length} ta talaba</small></h2>${stChip}</header>
    <div class="pad">${o.rule ? `<p class="hint">Qoida: ${esc(o.rule)}</p>` : ''}
      <ol class="steps">${s1}${s2}${s3}</ol>
      <div class="ord-files"><span class="lbl">Boshqa hujjatlar:</span>${other.length ? fchips(other) : '<span class="dash">yo‘q</span>'}
        <label class="btn sm ghost">${ic('upload')} Yuklash<input type="file" data-up hidden multiple></label>
        <select class="select sm" data-upkind aria-label="Hujjat turi">${Object.entries(FKIND).map(([k, v]) => `<option value="${k}" ${k === 'asos' ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
      <div class="actions"><button class="btn sm ghost" data-doc="zip">${ic('download')} Barcha hujjatlar (ZIP)</button>
        ${draft ? `<button class="btn sm danger" data-odel>${ic('x')} Loyihani o‘chirish</button>` : issued ? `<button class="btn sm ghost" data-ocancel>Chorani bekor qilish</button>` : ''}</div>
    </div></article>`;
}
function letterCard(o) {
  const M = MEAS[o.measure] || MEAS.boshqa, draft = o.status === 'draft', issued = o.status === 'issued';
  const letter = o.doc_kinds.some(k => k.kind === 'xat'), isXat = o.measure === 'xat';
  const stChip = issued ? `<span class="chip ok">${ic('check')} ${isXat ? 'Yuborilgan' : 'Chiqarilgan'}${o.number ? ` · № ${esc(o.number)}` : ''}${o.date ? ` · ${dmy(o.date)}` : ''}</span>`
    : o.status === 'cancelled' ? '<span class="chip muted">Bekor qilingan</span>' : `<span class="chip warn">Loyiha — ${isXat ? 'yuborilishi' : 'imzolanishi'} kutilmoqda</span>`;
  const common = o.files.filter(f => !f.case_id);
  return `<article class="sec ord" data-oid="${o.id}"><header><h2><span class="h-ic c-${o.measure === 'hayfsan' ? 'risk' : isXat ? 'msg' : 'acad'}" aria-hidden="true">${ic(isXat ? 'mail' : o.measure === 'hayfsan' ? 'shield' : 'alert')}</span>
      ${M.t} <small>${GRND[o.ground] || ''} · ${o.cases.length} ta talaba</small></h2>${stChip}</header>
    <div class="pad">
      ${o.rule ? `<p class="hint">Qoida: ${esc(o.rule)}</p>` : ''}${o.deadline ? `<p class="hint">Qarzni to‘lash muddati (xatda): <b>${dmy(o.deadline)}</b></p>` : ''}
      <ul class="ord-st">${o.cases.map(c => `<li><span><b class="click" data-chs="${c.student_id}">${esc(c.full_name)}</b> <span class="sub-l">${esc(c.group_name || '')}${c.hours != null ? ' · ' + pairs(c.hours) : ''}${c.amount ? ' · qarz ' + money(c.amount) : ''}${c.note ? ' · ' + esc(c.note) : ''}</span>
          ${letter && !c.address ? `<button class="chip warn" data-caddr="${c.student_id}" title="Xat uchun yashash manzilini kiritish">${ic('edit')} manzil yo‘q</button>` : ''}</span>
        <span class="nowrap">${letter ? `<button class="btn sm ghost" data-cxat="${c.id}" title="Shu talabaning ota-onasiga xat (Word)">${ic('mail')} Xat</button>` : ''}
          <button class="btn sm ghost" data-chs="${c.student_id}" title="Talabaning hujjatlari: asl nusxalar, yuklash, ota-onaga yuborish">${ic('folder')}${c.files_n ? ` ${c.files_n}` : ''}</button>
          ${draft ? `<button class="btn sm ghost" data-dcase="${c.id}" title="Hujjatdan chiqarish">${ic('x')}</button>` : ''}</span></li>`).join('')}</ul>
      <div class="ord-docs"><span class="lbl">Tayyor hujjatlar (Word):</span>${o.doc_kinds.map(k => `<button class="btn sm" data-doc="${k.kind}">${ic(k.kind === 'xat' ? 'mail' : 'download')} ${k.title}${k.kind === 'xat' && o.cases.length > 1 ? ' — barchasi (ZIP)' : ''}</button>`).join('')}
        ${o.doc_kinds.length > 1 ? `<button class="btn sm ghost" data-doc="zip">${ic('download')} Hammasi (ZIP)</button>` : ''}</div>
      <div class="ord-files"><span class="lbl">Umumiy hujjatlar:</span>${common.length ? common.map(f => `<span class="chip muted">${ic('file')}
          <a href="#" data-file="${f.id}">${esc(FKIND[f.kind] || f.kind)}: ${esc(f.name)}</a><button data-fdel="${f.id}" aria-label="O‘chirish">${ic('x')}</button></span>`).join('') : '<span class="dash">hali yo‘q</span>'}
        <label class="btn sm ghost">${ic('upload')} Yuklash<input type="file" data-up hidden multiple></label>
        <select class="select sm" data-upkind aria-label="Hujjat turi">${Object.entries(FKIND).map(([k, v]) => `<option value="${k}" ${k === (issued ? 'imzolangan' : 'tushuntirish') ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
      <p class="hint ord-hint">${ic('folder')} Umumiy — butun ${isXat ? 'ro‘yxat' : 'farmoyish/buyruq'} (imzolangan nusxa). Talabaning o‘z hujjatlari (imzolangan xat, tushuntirish xati, ma’lumotnoma) — qatordagi papka tugmasi orqali: PDF bo‘lsa, ota-onasiga bot orqali yuboriladi.</p>
      <div class="actions">${draft ? `<button class="btn primary" data-issue>${ic('check')} ${isXat ? 'Xatlar yuborildi deb belgilash' : 'Imzolandi — chiqarildi deb belgilash'}</button>
          <button class="btn danger" data-odel>${ic('x')} Loyihani o‘chirish</button>`
        : issued ? `<button class="btn" data-issue>${ic('edit')} Raqam va sanani o‘zgartirish</button><button class="btn ghost" data-ocancel>Bekor qilish</button>` : ''}</div>
    </div></article>`;
}
function choraDocs(d) {
  const st = S.chora; st.open = st.open || new Set();
  const live = d.orders.filter(o => !o.archived_at);
  const act = live.filter(o => !o.done), fin = live.filter(o => o.done), arch = d.orders.filter(o => o.archived_at);
  const row = (o, archived) => { const M = MEAS[o.measure] || MEAS.boshqa, open = st.open.has(o.id);
    return `<li><span><b>${M.t}</b> <span class="sub-l">${GRND[o.ground] || ''} · ${o.cases.length} ta talaba${o.number ? ' · № ' + esc(o.number) : ''}${o.date ? ' · ' + dmy(o.date) : ''}</span>
        ${o.status === 'cancelled' ? '<span class="chip muted">bekor qilingan</span>' : `<span class="chip ok">${ic('check')} yakunlangan</span>`}
        <span class="sub-l who">${esc(o.cases.slice(0, 4).map(c => c.full_name).join(', '))}${o.cases.length > 4 ? ` va yana ${o.cases.length - 4} ta` : ''}</span></span>
      <span class="nowrap"><button class="btn sm ghost" data-oopen="${o.id}">${ic(open ? 'chevu' : 'chevd')} ${open ? 'Yopish' : 'Ochish'}</button>
        ${archived ? `<button class="btn sm ghost" data-unarch="${o.id}" title="«Hujjatlar»ga qaytarish">${ic('refresh')} Qaytarish</button>`
          : `<button class="btn sm ghost" data-arch="${o.id}" title="«Hujjatlar»dan olish (tarixda qoladi)">${ic('check')} Tozalash</button>`}
        <button class="btn sm ghost danger-t" data-odel2="${o.id}" title="Butunlay o‘chirish">${ic('x')} O‘chirish</button></span></li>
      ${open ? `<li class="ord-open">${orderCard(o)}</li>` : ''}`; };
  return `<p class="hint scope">${ic('info')}<span>Chora tartib bilan ko‘riladi: <b>1. Asos</b> — kurs koordinatori bildirishnomasi yoki talabaning tushuntirish xati (yozmasa — dalolatnoma): <b>imzolangan nusxasi (PDF) yuklangach</b> → <b>2. Dekan farmoyishi / universitet buyrug‘i</b>: <b>imzolangan PDF raqami va sanasi bilan yuklangach</b> chora rasman ko‘rilgan hisoblanadi va ota-onasi botga ulangan talabalarga darhol yuboriladi (har biriga faqat o‘z farzandi, boshqalari qora rang bilan yopiladi) → <b>3. Ota-onaga xat</b> (farmoyish/buyruq raqami bilan).</span></p>
    ${act.length ? act.map(orderCard).join('') : emptyBox('file', 'Jarayondagi hujjat yo‘q', '«Chegaraga yetganlar» bo‘limida talabalarni tanlab, «Hujjatlarni tayyorlash» ni bosing.')}
    ${fin.length ? `<section class="sec ord-done"><header>${H('check', `Yakunlanganlar — ${fin.length} ta`, 'att')}<button class="btn sm" data-archall>${ic('check')} Barchasini tozalash</button></header>
      <p class="hint" style="margin:0 20px">Tozalangan chora bu yerdan olinadi, lekin «Chora ko‘rilganlar»da hujjatlari bilan qoladi. «O‘chirish» — butunlay (tarix va statistikadan ham).</p>
      <ul class="ord-list">${fin.map(o => row(o, false)).join('')}</ul></section>` : ''}
    ${arch.length ? `<details class="sec ord-arch" ${st.archOpen ? 'open' : ''}><summary class="pad">${ic('folder')} Tozalanganlar — ${arch.length} ta</summary>
      <ul class="ord-list">${arch.map(o => row(o, true)).join('')}</ul></details>` : ''}`;
}
function bindChoraDocs(d) {
  const st = S.chora;
  $$('[data-oopen]').forEach(b => b.addEventListener('click', () => { const id = Number(b.dataset.oopen); st.open.has(id) ? st.open.delete(id) : st.open.add(id); route(); }));
  $('.ord-arch')?.addEventListener('toggle', e => { st.archOpen = e.target.open; });
  $$('[data-arch], [data-unarch]').forEach(b => b.addEventListener('click', async () => {
    const id = b.dataset.arch || b.dataset.unarch;
    try { await api(`/api/staff/discipline/orders/${id}/archive`, { method: 'POST', json: { archived: !!b.dataset.arch } }); toast(b.dataset.arch ? 'Tozalandi' : 'Qaytarildi'); route(); }
    catch (e) { toast(e.message === 'not_done' ? 'Jarayon hali tugamagan' : 'Bajarilmadi', true); } }));
  $('[data-archall]')?.addEventListener('click', async () => {
    try { const r = await api('/api/staff/discipline/archive-done', { method: 'POST' }); toast(`Tozalandi: ${r.archived} ta`); route(); } catch (e) { toast('Bajarilmadi', true); } });
  $$('[data-odel2]').forEach(b => b.addEventListener('click', async () => {
    const o = d.orders.find(x => x.id === Number(b.dataset.odel2));
    if (!await confirmDlg('Chorani butunlay o‘chirish', `«${esc((MEAS[o.measure] || MEAS.boshqa).t)}» (${o.cases.length} ta talaba) hujjatlari va fayllari bilan butunlay o‘chiriladi — «Chora ko‘rilganlar» va statistikadan ham. Ota-onalarga yuborilgan xabar va hujjatlar ularda qoladi. Odatda «Tozalash» yetarli.`, 'O‘chirish', true)) return;
    try { await api(`/api/staff/discipline/orders/${o.id}?force=1`, { method: 'DELETE' }); toast('O‘chirildi'); route(); } catch (e) { toast('O‘chirilmadi', true); } }));
  $$('.ord').forEach(card => {
    const oid = Number(card.dataset.oid), o = d.orders.find(x => x.id === oid);
    const base = `/api/staff/discipline/orders/${oid}`;
    card.querySelectorAll('[data-doc]').forEach(b => b.addEventListener('click', async () => {
      b.disabled = true; try { await download(`${base}/doc/${b.dataset.doc}`); } catch (e) { toast('Yuklab bo‘lmadi', true); } b.disabled = false; }));
    card.querySelectorAll('[data-file]').forEach(a => a.addEventListener('click', async e => { e.preventDefault(); try { await download(`/api/staff/discipline/files/${a.dataset.file}`); } catch (_) { toast('Yuklab bo‘lmadi', true); } }));
    card.querySelectorAll('[data-fdel]').forEach(b => b.addEventListener('click', async () => {
      if (!await confirmDlg('Faylni o‘chirish', 'Biriktirilgan fayl o‘chiriladi.', 'O‘chirish', true)) return;
      await api(`/api/staff/discipline/files/${b.dataset.fdel}`, { method: 'DELETE' }); route(); }));
    card.querySelector('[data-up]')?.addEventListener('change', async e => {
      const files = [...e.target.files]; if (!files.length) return;
      const kind = card.querySelector('[data-upkind]').value, meta = await askDocNo(kind); if (!meta) return;
      const fd = new FormData(); fd.append('kind', kind);
      Object.entries(meta).forEach(([k, v]) => fd.append(k, v));
      files.forEach(f => fd.append('file', f, f.name));
      try { const r = await api(`${base}/files`, { method: 'POST', body: fd }); toast('Yuklandi' + autoMsg(r.auto, fd.get('kind'), o)); route(); }
      catch (err) { toast(err.message === 'too_big' ? 'Fayl juda katta (20 MB gacha)' : 'Yuklanmadi', true); }
    });
    const upload = async (url, kind, files) => {
      if (!files.length) return;
      if (['bildirishnoma', 'dalolatnoma'].includes(kind) && files.some(f => !/\.pdf$/i.test(f.name))) { toast('Imzolangan nusxa PDF bo‘lsin', true); return; }
      const meta = await askDocNo(kind); if (!meta) return;
      const fd = new FormData(); fd.append('kind', kind);
      Object.entries(meta).forEach(([k, v]) => fd.append(k, v));  // raqam va sana — fayldan oldin (server shu tartibda o'qiydi)
      files.forEach(f => fd.append('file', f, f.name));
      try { const r = await api(url, { method: 'POST', body: fd });
        const now = r.order && r.order.stages, was = o.stages.current;
        toast((now && now.current > was && was === 1 ? '1-bosqich yakunlandi — dekan bosqichiga o‘tildi' : 'Yuklandi') + autoMsg(r.auto, kind, o)); route(); }
      catch (err) { toast(CH_ERR[err.message] || 'Yuklanmadi', true); }
    };
    card.querySelectorAll('[data-upk]').forEach(i => i.addEventListener('change', e => upload(`${base}/files`, i.dataset.upk, [...e.target.files])));
    card.querySelectorAll('[data-cup]').forEach(i => i.addEventListener('change', e => upload(`/api/staff/discipline/cases/${i.dataset.cup}/files`, 'tushuntirish', [...e.target.files])));
    card.querySelectorAll('[data-cb]').forEach(b => b.addEventListener('click', async () => {
      try { await api(`/api/staff/discipline/cases/${b.dataset.cb}/basis`, { method: 'POST', json: { basis: b.dataset.v || null } }); route(); }
      catch (e) { toast('Saqlanmadi', true); } }));
    card.querySelector('[data-sign]')?.addEventListener('click', async () => {
      const first = o.status !== 'issued', doc = MEAS[o.measure] ? MEAS[o.measure].doc : 'Hujjat';
      const v = await formDlg(`Imzolangan ${String(doc).toLowerCase()} (PDF)`, `<label class="field"><span>Imzolangan nusxa — PDF</span><input class="input" type="file" name="file" accept=".pdf,application/pdf" required></label>
        <div class="cols2"><label class="field"><span>Raqami</span><input class="input" name="number" value="${esc(o.number || '')}" placeholder="Masalan: 17 yoki 215" required></label>
        <label class="field"><span>Sanasi</span><input class="input" type="date" name="date" value="${esc(o.date || todayIso())}" required></label></div>
        <p class="hint">${first ? 'Yuklanishi bilan chora rasman ko‘rilgan hisoblanadi; ota-onasi botga ulangan talabalarga hujjat darhol yuboriladi (har biriga faqat o‘z farzandi — boshqalar yopilgan). Keyin — ota-onaga xat bosqichi.' : 'Ota-onasi botga ulangan talabalarga darhol yuboriladi.'}</p>`, 'Yuklash');
      if (!v) return;
      const f = v.get('file');
      if (!f || !f.name || !/\.pdf$/i.test(f.name)) { toast('PDF fayl tanlang', true); return; }
      const fd = new FormData(); fd.append('kind', 'imzolangan'); fd.append('number', v.get('number')); fd.append('date', v.get('date'));
      if (first) fd.append('issue', '1');
      fd.append('file', f, f.name);
      try { const r = await api(`${base}/files`, { method: 'POST', body: fd });
        toast((r.issued ? '2-bosqich yakunlandi — chora rasman ko‘rildi' : 'Yuklandi') + autoMsg(r.auto, 'imzolangan', r.order || o)); route(); }
      catch (e) { toast(CH_ERR[e.message] || 'Yuklanmadi', true); } });
    card.querySelector('[data-letters]')?.addEventListener('click', async () => {
      const v = await formDlg('Ota-onaga xatlar — yuborildi', `<p>Belgilangan talabalarning ota-onasiga xat yuborilgan deb qayd etiladi; chiquvchi raqami xatga yoziladi.</p>
        <label class="field"><span>Yuborilgan sana</span><input class="input" type="date" name="date" value="${todayIso()}" required></label>
        <div class="field"><span>Talabalar va xatlarning chiquvchi raqami</span><ul class="ord-st">${o.cases.map(c => `<li><label class="cbxl"><input type="checkbox" name="c${c.id}" ${c.letter_date ? '' : 'checked'}> ${esc(c.full_name)}</label>
          <input class="input sm" name="n${c.id}" value="${esc(c.letter_no || '')}" placeholder="№ (masalan, 01-12/345)" aria-label="Chiquvchi raqam"></li>`).join('')}</ul></div>
        <label class="cbxl"><input type="checkbox" name="notify" checked> Ota-onalarga bot orqali xabar yuborish</label>
        <label class="cbxl"><input type="checkbox" name="pdf" checked> Imzolangan xat PDF nusxasini ham yuborish (talabaga yuklangan bo‘lsa)</label>`, 'Saqlash');
      if (!v) return;
      const items = o.cases.filter(c => v.get(`c${c.id}`) === 'on').map(c => ({ case_id: c.id, number: v.get(`n${c.id}`) || '' }));
      if (!items.length) { toast('Talaba belgilanmagan', true); return; }
      try { const r = await api(`${base}/letters`, { method: 'POST', json: { date: v.get('date'), items, notify: v.get('notify') === 'on', send_pdf: v.get('pdf') === 'on' } });
        toast(`Qayd etildi: ${r.marked}${r.notified ? ` · ota-onalarga xabar: ${r.notified}` : ''}${r.pdf ? ` · PDF: ${r.pdf}` : ''}`); route(); }
      catch (e) { toast(CH_ERR[e.message] || 'Saqlanmadi', true); } });
    card.querySelectorAll('[data-cxat]').forEach(b => b.addEventListener('click', async () => {
      b.disabled = true; try { await download(`${base}/doc/xat?case=${b.dataset.cxat}`); } catch (e) { toast('Yuklab bo‘lmadi', true); } b.disabled = false; }));
    card.querySelectorAll('[data-caddr]').forEach(b => b.addEventListener('click', async e => {
      e.stopPropagation(); const c = o.cases.find(x => x.student_id === Number(b.dataset.caddr));
      if (await editAddress(c.student_id, c.full_name, c.address)) route(); }));
    card.querySelectorAll('[data-dcase]').forEach(b => b.addEventListener('click', async () => {
      await api(`${base}/cases/${b.dataset.dcase}`, { method: 'DELETE' }); route(); }));
    card.querySelector('[data-odel]')?.addEventListener('click', async () => {
      if (!await confirmDlg('Loyihani o‘chirish', 'Hujjat loyihasi o‘chiriladi, talabalar «Chegaraga yetganlar» ro‘yxatiga qaytadi.', 'O‘chirish', true)) return;
      await api(base, { method: 'DELETE' }); route(); });
    card.querySelector('[data-ocancel]')?.addEventListener('click', async () => {
      if (!await confirmDlg('Chorani bekor qilish', 'Chora bekor qilingan deb belgilanadi (masalan, xato kiritilgan bo‘lsa). Talabalar yana ro‘yxatga qaytadi.', 'Bekor qilish', true)) return;
      await api(`${base}/cancel`, { method: 'POST' }); route(); });
    card.querySelector('[data-issue]')?.addEventListener('click', async () => {
      const first = o.status !== 'issued';
      const isXat = o.measure === 'xat';
      const v = await formDlg(isXat ? 'Ota-onaga xat — yuborildi' : `${MEAS[o.measure].doc} — imzolandi`, `<div class="cols2">
        <label class="field"><span>${isXat ? 'Chiquvchi raqami' : 'Raqami'}</span><input class="input" name="number" value="${esc(o.number || '')}" placeholder="${isXat ? 'Masalan: 01-12/345' : 'Masalan: 17 yoki 215'}" ${isXat ? '' : 'required'}></label>
        <label class="field"><span>Sanasi</span><input class="input" type="date" name="date" value="${esc(o.date || todayIso())}" required></label></div>
        ${first && isXat ? `<label class="cbxl"><input type="checkbox" name="notify" checked> Ota-onalarga xabar yuborish (bot orqali)</label>` : ''}
        <p class="hint">${isXat ? 'Imzolangan xatni talaba qatoridagi papka tugmasi orqali yuklang — PDF bo‘lsa, ota-onasiga yuboriladi.'
          : 'Keyingi bosqich — ota-onaga xat: unda shu raqam va sana yoziladi. Imzolangan nusxani «Imzolangan nusxa» tugmasi orqali yuklang.'}</p>`, 'Saqlash');
      if (!v) return;
      try { const r = await api(`${base}/issue`, { method: 'POST', json: { number: v.get('number'), date: v.get('date'), notify: v.get('notify') === 'on' } });
        toast(first ? (isXat ? `Yuborildi${r.notified ? ` · ota-onalarga ${r.notified} ta xabar` : ''}` : '2-bosqich yakunlandi — endi ota-onaga xat') : 'Saqlandi'); route(); }
      catch (e) { toast(CH_ERR[e.message] || 'Saqlanmadi', true); }
    });
  });
}
async function choraTartib(d) {
  const sel = new Map();
  const dl = $('#dlg');
  dl.innerHTML = `<form method="dialog" class="wide"><h3>Ichki tartib qoidalarini buzish bo‘yicha chora</h3>
    <div class="cols2"><label class="field"><span>Chora</span><select class="select" name="measure">
      <option value="ogohlantirish">Dekan ogohlantirishi (farmoyish)</option><option value="hayfsan">Hayfsan (buyruq)</option>
      <option value="xat">Faqat ota-onaga ogohlantirish xati</option><option value="boshqa">Boshqa chora</option></select></label>
      <label class="field"><span>Talaba qidirish</span><input class="input" id="tq" placeholder="F.I.Sh. yoki HEMIS ID" autocomplete="off"></label></div>
    <div id="tres" class="tres"></div>
    <label class="field"><span>Buzilgan qoida (hujjatga shu matn yoziladi)</span><input class="input" name="rule" list="rules" required placeholder="“Odob-axloq Kodeksi”ning … moddasi (…)">
      <datalist id="rules">${d.rules.map(r => `<option value="${esc(r)}">`).join('')}</datalist></label>
    <div class="field"><span>Talabalar va holat tafsiloti</span><ul id="tsel" class="ord-st"><li class="dash">Talaba tanlanmagan</li></ul></div>
    <p class="hint">Jarayon: 1. tushuntirish xati yoki bildirishnoma (imzolangan PDF) → 2. farmoyish/buyruq (imzolangan PDF) → 3. ota-onaga xat («Hujjatlar» yorlig‘ida bosqichma-bosqich).</p>
    <label class="cbxl"><input type="checkbox" id="tdone"> Farmoyish/buyruq allaqachon imzolangan (raqami, sanasi va PDF nusxasi bor)</label>
    <div class="cols2" id="tiss" hidden><label class="field cbxl-full" style="grid-column:1 / -1"><span>Imzolangan farmoyish / buyruq — PDF (ota-onasi botga ulanganlarga darhol yuboriladi)</span>
        <input class="input" type="file" name="sigfile" accept=".pdf,application/pdf"></label>
      <label class="field"><span>Raqami</span><input class="input" name="number"></label>
      <label class="field"><span>Sanasi</span><input class="input" type="date" name="date" value="${todayIso()}"></label>
      <label class="field"><span>Asos (1-bosqich)</span><select class="select" name="basis"><option value="tushuntirish">Talabaning tushuntirish xati</option>
        <option value="bildirishnoma">Kurs koordinatori bildirishnomasi</option></select></label></div>
    <div class="row"><button class="btn" value="cancel" formnovalidate>Bekor qilish</button><button class="btn primary" value="ok">Saqlash va hujjatlarni tayyorlash</button></div></form>`;
  const paintSel = () => { $('#tsel').innerHTML = sel.size ? [...sel.values()].map(x => `<li><span><b>${esc(x.name)}</b> <span class="sub-l">${esc(x.group || '')}</span>
      <input class="input sm" data-tnote="${x.id}" value="${esc(x.note || '')}" placeholder="Sana, holat (masalan: 27.10 — sport kiyimida)"></span>
      <button type="button" class="btn sm ghost" data-tdel="${x.id}">${ic('x')}</button></li>`).join('') : '<li class="dash">Talaba tanlanmagan</li>';
    $$('[data-tnote]').forEach(i => i.addEventListener('input', () => { sel.get(Number(i.dataset.tnote)).note = i.value; }));
    $$('[data-tdel]').forEach(b => b.addEventListener('click', () => { sel.delete(Number(b.dataset.tdel)); paintSel(); })); };
  let tm = null;
  $('#tq').addEventListener('input', e => { clearTimeout(tm); const qv = e.target.value.trim(); if (qv.length < 2) { $('#tres').innerHTML = ''; return; }
    tm = setTimeout(async () => { const r = await api(`/api/staff/students?q=${encodeURIComponent(qv)}&limit=8`);
      $('#tres').innerHTML = r.items.map(s => `<button type="button" class="btn sm ghost" data-tadd="${s.id}">${ic('plus')} ${esc(s.name)} <span class="sub-l">${esc(s.group || '')}</span></button>`).join('') || '<span class="dash">Topilmadi</span>';
      $$('[data-tadd]').forEach(b => b.addEventListener('click', () => { const s = r.items.find(x => x.id === Number(b.dataset.tadd)); sel.set(s.id, { id: s.id, name: s.name, group: s.group, note: '' }); paintSel(); })); }, 250); });
  $('#tdone').addEventListener('change', e => { $('#tiss').hidden = !e.target.checked; });
  dl.returnValue = '';
  dl.showModal();
  dl.onclose = async () => {
    if (dl.returnValue !== 'ok') return;
    const f = new FormData(dl.querySelector('form'));
    if (!sel.size) { toast('Talaba tanlang', true); return; }
    const body = { measure: f.get('measure'), ground: 'tartib', rule: f.get('rule'), items: [...sel.values()].map(x => ({ sid: x.id, note: x.note })) };
    const done = $('#tdone').checked, sig = f.get('sigfile');
    if (done && f.get('measure') !== 'xat') {
      if (!sig || !sig.name || !/\.pdf$/i.test(sig.name)) { toast('Imzolangan farmoyish/buyruqning PDF nusxasini tanlang', true); return; }
      if (!f.get('number')) { toast('Farmoyish/buyruq raqamini kiriting', true); return; }
      body.issue = { basis: f.get('basis') };
    }
    let r;
    try { r = await api('/api/staff/discipline/orders', { method: 'POST', json: body }); }
    catch (e) { toast(e.message === 'no_rule' ? 'Buzilgan qoidani yozing' : 'Saqlanmadi', true); return; }
    S.chora.tab = 'docs';
    if (body.issue) {
      const fd = new FormData(); fd.append('kind', 'imzolangan'); fd.append('number', f.get('number')); fd.append('date', f.get('date') || todayIso());
      fd.append('issue', '1'); fd.append('file', sig, sig.name);
      try { const u = await api(`/api/staff/discipline/orders/${r.id}/files`, { method: 'POST', body: fd });
        toast('Saqlandi — chora rasman ko‘rilgan' + autoMsg(u.auto, 'imzolangan', u.order)); }
      catch (e) { toast('Chora saqlandi, lekin PDF yuklanmadi: ' + (CH_ERR[e.message] || 'xato') + ' — «Hujjatlar»da qayta yuklang', true); }
    } else toast('Saqlandi');
    route();
  };
}
function choraBars(dyn) {
  const v = (x, k) => x[k] || 0, sum = x => v(x, 'ogohlantirish') + v(x, 'hayfsan') + v(x, 'boshqa') + v(x, 'xat');
  const max = Math.max(1, ...dyn.map(sum));
  return `<div class="ch-bars" role="img" aria-label="Oylar bo‘yicha ko‘rilgan choralar">${dyn.map(x => {
    const h = k => `${(100 * v(x, k) / max).toFixed(1)}%`;
    const tot = sum(x);
    return `<div class="ch-col" title="${x.label}: ogohlantirish ${v(x, 'ogohlantirish')}, hayfsan ${v(x, 'hayfsan')}, ota-onaga xat ${v(x, 'xat')}${x.boshqa ? ', boshqa ' + x.boshqa : ''}">
      <b class="num">${tot || ''}</b><div class="ch-stack"><i class="hy" style="height:${h('hayfsan')}"></i><i class="og" style="height:${h('ogohlantirish')}"></i><i class="xa" style="height:${h('xat')}"></i><i class="bo" style="height:${h('boshqa')}"></i></div>
      <span>${x.label.slice(0, 3)}</span></div>`; }).join('')}</div>
    <div class="ch-leg"><span><i class="og"></i>Dekan ogohlantirishi</span><span><i class="hy"></i>Hayfsan</span><span><i class="xa"></i>Ota-onaga xat</span><span><i class="bo"></i>Boshqa</span></div>`;
}
/* ota-onaga yuborilgan xatlar: nima bo'yicha (davomat / ichki tartib / trimestr) va qaysi chora bilan */
const LT_GROUNDS = [['davomat', 'davomat'], ['tartib', 'ichki tartib'], ['trimestr', 'trimestr qarzi']];
const LT_MEAS = [['ogohlantirish', 'dekan ogohlantirishi'], ['hayfsan', 'hayfsan'], ['boshqa', 'boshqa chora'], ['xat', 'alohida xat']];
function lettersKpi(L) {
  const g = LT_GROUNDS.filter(([k]) => L[k]).map(([k, l]) => `${l}: <b>${L[k]}</b>`).join(' · ');
  const m = LT_MEAS.filter(([k]) => (L.by_measure || {})[k]).map(([k, l]) => `${l} ${L.by_measure[k]}`).join(' · ');
  return kpi({ href: '#/chora?tab=hist&hm=xat', icon: 'mail', c: 'msg', label: 'Ota-onaga xatlar', value: L.sent, unit: 'ta',
    state: L.pending ? 'bad' : null,
    title: `O‘quv yilida ota-onaga yuborilgan xatlar: ${L.sent} ta (${L.students} talaba)${m ? `\nChora bo‘yicha: ${m}` : ''}`
      + `\nBotda imzolangan xat yetkazilgan: ${L.in_bot}${L.last ? `\nOxirgisi: ${dmy(L.last)}` : ''}`,
    sub: `<span class="ln">${g || 'hali xat yuborilmagan'}</span>${m ? `<span class="ln sub-m">${m}</span>` : ''}`
      + (L.pending ? `<span class="ln warn-t">yuborilmagan: <b>${L.pending}</b> ta</span>` : '') });
}
/* chora turlari × asos: dekan ogohlantirishi va hayfsan — nechtasi davomat, nechtasi ichki tartib bo'yicha */
const MX_ROWS = [['ogohlantirish', 'Dekan ogohlantirishi'], ['hayfsan', 'Hayfsan'], ['boshqa', 'Boshqa chora'], ['xat', 'Ota-onaga xat']];
function choraMatrix(mx) {
  const sum = o => Object.values(o || {}).reduce((a, b) => a + b, 0);
  const rows = MX_ROWS.filter(([m]) => ['ogohlantirish', 'hayfsan'].includes(m) || sum(mx[m]));
  const tri = rows.some(([m]) => (mx[m] || {}).trimestr);
  const cell = v => (v ? `<b class="num">${v}</b>` : '<span class="dash">0</span>');
  const tot = g => rows.reduce((a, [m]) => a + ((mx[m] || {})[g] || 0), 0);
  return `<div class="tbl-wrap" style="max-height:none"><table class="tbl mx"><thead><tr><th>Chora</th><th class="r">Jami</th><th class="r">Davomat bo‘yicha</th>
      <th class="r">Ichki tartib bo‘yicha</th>${tri ? '<th class="r">Trimestr</th>' : ''}</tr></thead><tbody>
    ${rows.map(([m, l]) => `<tr><td><span class="chip ${(MEAS[m] || MEAS.boshqa).c}">${l}</span></td><td class="r">${cell(sum(mx[m]))}</td>
      <td class="r">${cell((mx[m] || {}).davomat)}</td><td class="r">${cell((mx[m] || {}).tartib)}</td>${tri ? `<td class="r">${cell((mx[m] || {}).trimestr)}</td>` : ''}</tr>`).join('')}
    <tr class="tot"><td><b>Jami</b></td><td class="r">${cell(tot('davomat') + tot('tartib') + tot('trimestr'))}</td><td class="r">${cell(tot('davomat'))}</td>
      <td class="r">${cell(tot('tartib'))}</td>${tri ? `<td class="r">${cell(tot('trimestr'))}</td>` : ''}</tr></tbody></table></div>`;
}
function choraMonths(dyn) {
  const v = (x, m, g) => ((x.by || {})[m] || {})[g] || 0;
  const pair = (x, m) => { const a = v(x, m, 'davomat'), b = v(x, m, 'tartib');
    return a + b ? `<b class="num">${a + b}</b><span class="sub-l">davomat ${a} · tartib ${b}</span>` : '<span class="dash">0</span>'; };
  const xat = x => v(x, 'xat', 'trimestr') + v(x, 'xat', 'tartib') + v(x, 'xat', 'davomat');
  const all = x => ['ogohlantirish', 'hayfsan', 'boshqa', 'xat'].reduce((a, m) => a + v(x, m, 'davomat') + v(x, m, 'tartib') + v(x, m, 'trimestr'), 0);
  return `<div class="tbl-wrap" style="max-height:none"><table class="tbl mx"><thead><tr><th>Oy</th><th class="r">Dekan ogohlantirishi</th><th class="r">Hayfsan</th>
      <th class="r">Ota-onaga xat</th><th class="r">Jami</th></tr></thead><tbody>
    ${dyn.slice().reverse().map(x => `<tr><td class="nowrap">${x.label} ${x.month.slice(0, 4)}</td><td class="r">${pair(x, 'ogohlantirish')}</td>
      <td class="r">${pair(x, 'hayfsan')}</td><td class="r">${xat(x) ? `<b class="num">${xat(x)}</b>` : '<span class="dash">0</span>'}</td>
      <td class="r">${all(x) ? `<b class="num">${all(x)}</b>` : '<span class="dash">0</span>'}</td></tr>`).join('')}</tbody></table></div>`;
}
async function loadChoraHist(st) {
  const box = $('#ch-hist');
  const qs = new URLSearchParams(); if (st.hm === 'xat') qs.set('letters', '1'); else if (st.hm) qs.set('measure', st.hm); if (st.hg) qs.set('ground', st.hg);
  const h = await api('/api/staff/discipline/history' + (qs.toString() ? '?' + qs : ''));
  const k = h.kpi;
  box.innerHTML = `<section class="kpis">
      ${kpi({ icon: 'alert', c: 'acad', label: 'Dekan ogohlantirishi', value: k.ogohlantirish, unit: 'ta', sub: 'o‘quv yili boshidan' })}
      ${kpi({ icon: 'shield', c: 'risk', label: 'Hayfsan', value: k.hayfsan, unit: 'ta', sub: 'o‘quv yili boshidan' })}
      ${lettersKpi(k.letters)}
      ${kpi({ icon: 'calx', c: 'att', label: 'Davomat bo‘yicha', value: k.davomat, unit: 'ta', sub: 'sababsiz dars qoldirish' })}
      ${kpi({ icon: 'book', c: 'gpa', label: 'Ichki tartib bo‘yicha', value: k.tartib, unit: 'ta', sub: 'qoidalarni buzish' })}
      ${kpi({ icon: 'users', c: 'people', label: 'Talabalar', value: k.students, unit: 'ta', sub: `${k.repeat} tasiga takroriy chora` })}
      ${kpi({ icon: 'file', c: 'money2', label: 'Asl hujjati yo‘q', value: k.no_original, unit: 'ta', state: k.no_original ? 'bad' : 'ok', sub: 'imzolangan nusxa yuklanmagan' })}
    </section>
    <div class="grid-2"><section class="sec"><header>${H('chart', 'Dinamika — oylar bo‘yicha', 'att')}<span class="hint">${dmy(h.since)} dan</span></header><div class="pad">${choraBars(h.dynamics)}</div></section>
      <section class="sec"><header>${H('users', 'Guruhlar bo‘yicha', 'people')}</header><div class="pad">${h.by_group.length ? `<ul class="list ch-grp">${h.by_group.map(([g, n]) =>
        `<li><span>${esc(g)}</span><b class="num">${n}</b></li>`).join('')}</ul>` : '<span class="dash">Hali chora ko‘rilmagan</span>'}</div></section></div>
    <section class="sec" style="margin-top:18px"><header>${H('layers', 'Chora turlari: davomat va ichki tartib bo‘yicha', 'acad')}<span class="hint">${dmy(h.since)} dan</span></header>
      <div class="mx-grid"><div><div class="mx-h">Jami — tur va asos</div>${choraMatrix(h.matrix)}</div><div><div class="mx-h">Oylar kesimida</div>${choraMonths(h.dynamics)}</div></div></section>
    <section class="sec" style="margin-top:18px"><header>${H('file', 'Chora ko‘rilgan talabalar', 'acad')}
      <div class="seg">${[['', 'Hammasi'], ['ogohlantirish', 'Ogohlantirish'], ['hayfsan', 'Hayfsan'], ['xat', 'Ota-onaga xat']].map(([v, l]) => `<button data-hm="${v}" class="${st.hm === v ? 'on' : ''}">${l}</button>`).join('')}</div>
      <div class="seg">${[['', 'Barcha asoslar'], ['davomat', 'Davomat'], ['tartib', 'Ichki tartib'], ['trimestr', 'Trimestr']].map(([v, l]) => `<button data-hg="${v}" class="${st.hg === v ? 'on' : ''}">${l}</button>`).join('')}</div></header>
      <p class="hint pad" style="margin:0;padding-bottom:0">${ic('folder')} Talabani bossangiz — barcha choralari asl hujjatlari bilan ochiladi: ko‘rish, yuklash, ota-onaga yuborish.</p>
      ${h.items.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Sana</th><th>Talaba</th><th>Chora</th><th>Asos</th><th>Asl hujjatlar</th></tr></thead><tbody>
        ${h.items.map(x => `<tr class="click" data-chs="${x.student_id}"><td class="nowrap">${dmy(x.date)}${x.number ? `<div class="sub-l"><a href="#/chora?tab=arch&aq=${encodeURIComponent(x.number)}" title="Arxivda — asl nusxa">№ ${esc(x.number)}</a></div>` : ''}</td>
          <td class="name"><b>${esc(x.full_name)}</b><span>${esc(x.group_name || '')}</span></td>
          <td><span class="chip ${(MEAS[x.measure] || MEAS.boshqa).c}">${esc((MEAS[x.measure] || {}).s || x.title)}</span>
            ${x.measure !== 'xat' ? (x.letter_date ? `<div class="sub-l">${ic('mail')} xat: ${x.letter_no ? '№ ' + esc(x.letter_no) + ', ' : ''}${dmy(x.letter_date)}</div>` : '<div class="sub-l warn-t">ota-onaga xat yuborilmagan</div>') : ''}</td>
          <td>${x.ground === 'davomat' ? `Davomat: sababsiz ${pairs(x.hours)}` : x.ground === 'trimestr' ? `Trimestr qarzi: ${money(x.amount)}` : `Ichki tartib: ${esc(x.rule || '')}`}${x.note ? `<div class="sub-l">${esc(x.note)}</div>` : ''}</td>
          <td><div class="wrapc">${x.files.length ? x.files.map(f => `<a href="#" class="chip ${f.shared ? 'muted' : 'ok'}" data-fview="${f.id}" title="${esc(f.name)}${f.shared ? ' (umumiy hujjat)' : ''}">${ic(isPdf(f) ? 'eye' : 'file')} ${esc(FKIND[f.kind] || f.kind)}</a>`).join('')
            : `<span class="chip warn">${ic('alert')} asl hujjat yo‘q</span>`}
            <button class="btn sm ghost" data-hdoc="${x.order_id}" title="Shablondan: farmoyish/buyruq, bildirishnoma, xat (ZIP)">${ic('download')}</button></div></td></tr>`).join('')}</tbody></table></div>`
        : emptyBox('ok', 'Chora ko‘rilgan talaba yo‘q', 'Farmoyish, buyruq yoki xat «chiqarildi / yuborildi» deb belgilanganda shu yerda saqlanadi.')}</section>`;
  box.querySelectorAll('[data-hm]').forEach(b => b.addEventListener('click', () => { st.hm = b.dataset.hm; loadChoraHist(st); }));
  box.querySelectorAll('[data-hg]').forEach(b => b.addEventListener('click', () => { st.hg = b.dataset.hg; loadChoraHist(st); }));
  box.querySelectorAll('[data-hdoc]').forEach(b => b.addEventListener('click', async e => { e.stopPropagation(); b.disabled = true; try { await download(`/api/staff/discipline/orders/${b.dataset.hdoc}/doc/zip`); } catch (_) { toast('Yuklab bo‘lmadi', true); } b.disabled = false; }));
  box.querySelectorAll('[data-fview]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); viewFile(a.dataset.fview); }));
}
/* asl nusxalar arxivi: raqam (17, 215-T, 01-12/101) yoki talaba F.I.Sh. bo'yicha qidiruv */
const ARCH_C = { farmoyish: 'warn', buyruq: 'bordo', bildirishnoma: 'info', dalolatnoma: 'muted', xat: 'info', tushuntirish: 'muted', qaror: 'muted', asos: 'muted', boshqa: 'muted' };
function choraArch(st) {
  return `<p class="hint scope">${ic('info')}<span>Faqat yuklangan <b>asl nusxalar</b> (imzolangan farmoyish, buyruq, bildirishnoma, dalolatnoma, ota-onaga xat, tushuntirish xati) — tozalangan choralarniki ham. Bitta hujjat bir necha talabaga chiqqan bo‘lsa — bitta yozuv. Raqami bo‘yicha (masalan <b>17</b>, <b>215-T</b>, <b>01-12/101</b>) yoki talaba F.I.Sh. bo‘yicha qidiring.</span></p>
    <div class="toolbar"><div class="search wide">${ic('search')}<input class="input" id="arq" type="search" placeholder="Hujjat raqami yoki talaba F.I.Sh." value="${esc(st.aq || '')}" aria-label="Arxivda qidirish"></div></div>
    <div id="ch-arch">${skel(60)}${skel(260)}</div>`;
}
function bindChoraArch(st) {
  let tm = null;
  $('#arq').addEventListener('input', e => { clearTimeout(tm); tm = setTimeout(() => { st.aq = e.target.value.trim(); loadChoraArch(st); }, 300); });
  if (!st.aq) $('#arq').focus();
  loadChoraArch(st);
}
async function loadChoraArch(st) {
  const qs = new URLSearchParams(); if (st.aq) qs.set('q', st.aq); if (st.at) qs.set('type', st.at);
  const d = await api('/api/staff/discipline/archive' + (qs.toString() ? '?' + qs : ''));
  const box = $('#ch-arch'); if (!box) return;
  const types = Object.entries(d.types).filter(([k]) => d.counts[k] || k === st.at);
  const studs = e => `${e.students.slice(0, 5).map(x => `<a href="#" class="stl" data-achs="${x.id}">${esc(x.name)}</a>`).join(', ')}${e.students.length > 5 ? ` <span class="sub-l">va yana ${e.students.length - 5} ta</span>` : ''}
    <div class="sub-l">${e.students.length} ta talaba${e.students.length && e.students[0].group ? ' · ' + esc([...new Set(e.students.map(x => x.group))].join(', ')) : ''}</div>`;
  const head = e => `<span class="chip ${ARCH_C[e.type] || 'muted'}">${esc(e.title)}</span>${e.number ? `<div class="docno">№ ${esc(e.number)}${e.exact ? ` <span class="chip ok">${ic('check')} aniq</span>` : ''}</div>` : '<div class="sub-l">raqamsiz</div>'}`;
  box.innerHTML = `<div class="toolbar"><div class="seg">${[['', `Hammasi`], ...types].map(([k, l]) => `<button data-at="${k}" class="${(st.at || '') === k ? 'on' : ''}">${esc(k ? l.replace(/ \(.*\)$/, '') : l)}${k && d.counts[k] ? ` <span class="n">${d.counts[k]}</span>` : ''}</button>`).join('')}</div></div>
    <section class="sec">${d.items.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl arch"><thead><tr><th>Hujjat</th><th>Sana</th><th>Talabalar</th><th>Asl nusxa</th><th></th></tr></thead><tbody>
      ${d.items.map(e => `<tr class="${e.exact ? 'hit' : ''}"><td>${head(e)}</td><td class="nowrap">${dmy(e.date)}</td><td>${studs(e)}</td>
        <td><div class="wrapc">${e.files.map(f => `<a href="#" class="chip ${f.sent_at ? 'ok' : 'muted'}" data-fview="${f.id}" title="${esc(f.name)}${f.send_note ? ' — ' + esc(f.send_note) : ''}">${ic(isPdf(f) ? 'eye' : 'file')} ${esc(f.name.length > 28 ? f.name.slice(0, 26) + '…' : f.name)}</a>
          <button class="btn sm ghost" data-fdl="${f.id}" title="Yuklab olish">${ic('download')}</button>`).join('')}</div></td>
        <td class="r nowrap"><button class="btn sm ghost" data-ameta="${e.files.map(f => f.id).join(',')}" data-no="${esc(e.number || '')}" data-dt="${esc(e.date || '')}" title="Raqam va sana">${ic('edit')}</button></td></tr>`).join('')}</tbody></table></div>`
      : emptyBox('folder', st.aq ? 'Asl nusxa topilmadi' : 'Arxiv hali bo‘sh', st.aq ? 'Raqam yoki F.I.Sh. ni tekshiring; quyida — raqami bor, lekin asl nusxasi yuklanmagan hujjatlar.' : 'Imzolangan asl nusxalar «Hujjatlar» yorlig‘ida yoki talaba oynasida yuklanadi.')}</section>
    ${d.missing.length ? `<section class="sec" style="margin-top:18px"><header>${H('alert', `Asl nusxasi yuklanmagan — ${d.missing.length} ta`, 'money2')}</header>
      <div class="tbl-wrap" style="max-height:none"><table class="tbl arch"><tbody>${d.missing.map(e => `<tr><td>${head(e)}</td><td class="nowrap">${dmy(e.date)}</td><td>${studs(e)}</td>
        <td class="r nowrap"><label class="btn sm">${ic('upload')} Asl nusxani yuklash<input type="file" data-aup="${e.order_id}" data-k="${e.upload}" accept=".pdf,image/*" hidden multiple></label></td></tr>`).join('')}</tbody></table></div></section>` : ''}`;
  box.querySelectorAll('[data-at]').forEach(b => b.addEventListener('click', () => { st.at = b.dataset.at; loadChoraArch(st); }));
  box.querySelectorAll('[data-achs]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); openChora(Number(a.dataset.achs)); }));
  box.querySelectorAll('[data-fview]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); viewFile(a.dataset.fview); }));
  box.querySelectorAll('[data-fdl]').forEach(b => b.addEventListener('click', async () => { try { await download(`/api/staff/discipline/files/${b.dataset.fdl}`); } catch (_) { toast('Yuklab bo‘lmadi', true); } }));
  box.querySelectorAll('[data-ameta]').forEach(b => b.addEventListener('click', async () => {
    const v = await formDlg('Asl nusxa — raqam va sana', `<p>Arxivda shu raqam bo‘yicha topiladi. Bo‘sh qoldirilsa — choradagi raqam olinadi.</p><div class="cols2">
      <label class="field"><span>Raqami</span><input class="input" name="number" value="${esc(b.dataset.no)}"></label>
      <label class="field"><span>Sanasi</span><input class="input" type="date" name="date" value="${esc(b.dataset.dt)}"></label></div>`);
    if (!v) return;
    try { await api('/api/staff/discipline/files/meta', { method: 'POST', json: { ids: b.dataset.ameta.split(','), number: v.get('number'), date: v.get('date') } }); toast('Saqlandi'); loadChoraArch(st); }
    catch (e) { toast('Saqlanmadi', true); } }));
  box.querySelectorAll('[data-aup]').forEach(i => i.addEventListener('change', async e => {
    const files = [...e.target.files]; if (!files.length) return;
    const fd = new FormData(); fd.append('kind', i.dataset.k); files.forEach(f => fd.append('file', f, f.name));
    try { const r = await api(`/api/staff/discipline/orders/${i.dataset.aup}/files`, { method: 'POST', body: fd });
      toast('Yuklandi' + autoMsg(r.auto, i.dataset.k, { status: 'issued' })); loadChoraArch(st); }
    catch (err) { toast(err.message === 'too_big' ? 'Fayl juda katta (20 MB gacha)' : 'Yuklanmadi', true); } }));
}
function choraTpl(d) {
  const s = d.settings;
  return `<div class="grid-2"><section class="sec"><header>${H('book', 'Hujjat shablonlari', 'acad')}</header><div class="pad" id="ch-tpl">${skel(200)}</div></section>
    <section class="sec"><header>${H('edit', 'Hujjatlardagi ma’lumotlar', 'people')}</header><div class="pad">
      ${myGroups().length ? '<p class="hint">Sozlamani kurs koordinatori (guruhsiz) yoki super-admin o‘zgartiradi.</p>' : ''}
      <label class="field"><span>Kurs koordinator(lar)i — hujjatlarda</span><input class="input" id="ch-co" value="${esc(s.coordinators)}" placeholder="${esc(s.auto_coordinators || 'A.Usmonov, N.Egamberdiyev')}">
        <small class="hint">Bo‘sh qoldirilsa — botdagi koordinatorlar: ${esc(s.auto_coordinators || '—')}</small></label>
      <label class="field"><span>Fakultet (hujjatlardagi jadvalda)</span><input class="input" id="ch-fac" value="${esc(s.faculty)}" placeholder="Xalqaro munosabatlar"></label>
      <label class="field"><span>Telefon — ota-onaga xatda (bog‘lanish va ijrochi telefoni)</span><input class="input" id="ch-tel" value="${esc(s.phone)}" placeholder="+998 (71) 000-00-00">
        <small class="hint">Xatdagi «Ijrochi» — yuqoridagi koordinator(lar).</small></label>
      <button class="btn primary" id="ch-save" ${myGroups().length ? 'disabled' : ''}>${ic('check')} Saqlash</button></div></section></div>`;
}
async function bindChoraTpl(d) {
  $('#ch-save')?.addEventListener('click', async () => {
    try { await api('/api/staff/discipline/settings', { method: 'POST', json: { coordinators: $('#ch-co').value, faculty: $('#ch-fac').value, phone: $('#ch-tel').value } }); toast('Saqlandi'); }
    catch (e) { toast('Saqlanmadi', true); }
  });
  const t = await api('/api/staff/discipline/templates');
  $('#ch-tpl').innerHTML = `<p class="hint">Word shablonidagi <code>{{…}}</code> belgilar o‘rniga ma’lumot qo‘yiladi: jadvalning <code>{{T_FISH}}</code> bor satri har bir talaba uchun takrorlanadi.
      Matnni o‘zgartirish uchun shablonni yuklab oling, Word’da tahrirlang (belgilarni saqlab) va qayta yuklang${t.can_upload ? '' : ' (super-admin)'}.</p>
    <ul class="list ch-tpls">${t.items.map(x => `<li><span><b>${esc(x.title)}</b>${x.custom ? ' <span class="chip ok">yuklangan</span>' : ''}
      <span class="sub-l">${x.placeholders.map(p => `{{${p}}}`).join(' ')}</span></span>
      <span class="nowrap"><button class="btn sm ghost" data-tget="${x.name}">${ic('download')}</button>
      ${t.can_upload ? `<label class="btn sm ghost" title="Yangi shablon yuklash">${ic('upload')}<input type="file" accept=".docx" data-tput="${x.name}" hidden></label>
        ${x.custom ? `<button class="btn sm ghost" data-treset="${x.name}" title="Asl shablonga qaytarish">${ic('refresh')}</button>` : ''}` : ''}</span></li>`).join('')}</ul>`;
  $$('[data-tget]').forEach(b => b.addEventListener('click', () => download(`/api/staff/discipline/templates/${b.dataset.tget}`)));
  $$('[data-tput]').forEach(i => i.addEventListener('change', async e => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append('file', f, f.name);
    try { await api(`/api/staff/discipline/templates/${i.dataset.tput}`, { method: 'POST', body: fd }); toast('Shablon yangilandi'); route(); }
    catch (err) { toast(err.message === 'no_table' ? 'Shablonda {{T_FISH}} bor jadval satri yo‘q' : err.message === 'no_name' ? 'Xat shablonida talaba ismi ({{FISH_KATTA}}) yo‘q'
      : 'Shablon qabul qilinmadi (.docx bo‘lishi kerak)', true); }
  }));
  $$('[data-treset]').forEach(b => b.addEventListener('click', async () => { await api(`/api/staff/discipline/templates/${b.dataset.treset}`, { method: 'DELETE' }); route(); }));
}

/* talabaning choralari: asl hujjatlar (yuklangan PDF/skan), shablondan hujjatlar, ota-onaga yuborish */
async function openChora(sid) {
  const dr = $('#drawer'); if (!dr) return;
  $('#dbody').innerHTML = skel(120) + skel(160, 2);
  dr.classList.add('on'); $('#scrim').classList.add('on'); dr.setAttribute('aria-hidden', 'false');
  $('#drawer header b').textContent = 'Chora ko‘rish — hujjatlar';
  let d;
  try { d = await api(`/api/staff/discipline/student/${sid}`); } catch (e) { $('#dbody').innerHTML = emptyBox('alert', 'Ma’lumotni yuklab bo‘lmadi'); return; }
  const s = d.student;
  $('#drawer header b').textContent = s.name;
  const fileRow = (f, c) => `<li><span class="t">${ic(isPdf(f) ? 'eye' : 'file')}<span><b>${esc(FKIND[f.kind] || f.kind)}</b>${f.shared ? ' <span class="chip muted">umumiy hujjat</span>' : ''}
      <span class="sub-l">${esc(f.name)} · ${when(f.uploaded_at)}${f.sent_at ? ` · ${ic('check')} ota-onaga yuborilgan ${when(f.sent_at)}` : ''}</span>
      ${f.send_note ? `<span class="sub-l ${f.sent_at ? '' : 'warn-t'}">${esc(f.send_note)}</span>` : ''}</span></span>
    <span class="nowrap"><button class="btn sm ghost" data-fv="${f.id}" title="Ko‘rish">${ic('eye')}</button><button class="btn sm ghost" data-fd="${f.id}" title="Yuklab olish">${ic('download')}</button>
      ${!f.shared && isPdf(f) ? `<button class="btn sm ghost" data-fs="${f.id}" title="Ota-onasiga bot orqali yuborish («Hujjatlar» bo‘limiga)" ${d.parents ? '' : 'disabled'}>${ic('send')}</button>` : ''}
      ${!f.shared ? `<button class="btn sm ghost" data-fx="${f.id}" title="O‘chirish">${ic('x')}</button>` : ''}</span></li>`;
  const caseBox = c => { const M = MEAS[c.measure] || MEAS.boshqa, issued = c.status === 'issued';
    const tone = issued ? 'ok' : c.status === 'excused' ? 'ok' : c.status === 'draft' ? 'warn' : 'muted';
    return `<div class="box chs-case"><h4><span class="chip ${M.c}">${esc(M.t)}</span> <span class="chip ${tone}">${esc(c.state_title)}</span></h4>
      <div class="kv"><span>Sabab</span><b>${esc(GRND[c.ground] || c.ground_title)}${c.why ? ': ' + esc(c.why) : ''}</b>
        ${c.order_id && c.measure !== 'xat' ? `<span>1. Asos</span><b>${[c.basis_kind === 'bildirishnoma' ? `kurs koordinatori bildirishnomasi${c.basis_date ? ' · ' + dmy(c.basis_date) : ''}` : '',
            c.basis === 'tushuntirish' ? 'tushuntirish xati' : c.basis === 'dalolatnoma' ? 'dalolatnoma (yozmagan)' : ''].filter(Boolean).join(' + ') || '<span class="dash">kutilmoqda</span>'}</b>` : ''}
        ${c.order_id ? `<span>${c.o_measure === 'xat' ? 'Xat' : '2. ' + ((MEAS[c.measure] || {}).doc || 'Hujjat')}</span><b>${c.number ? '№ ' + esc(c.number) + ', ' : ''}${c.date ? dmy(c.date) : 'imzolanmagan'}</b>` : ''}
        ${c.order_id && c.measure !== 'xat' ? `<span>3. Ota-onaga xat</span><b>${c.letter_date ? `${c.letter_no ? '№ ' + esc(c.letter_no) + ', ' : ''}${dmy(c.letter_date)}` : '<span class="dash">yuborilmagan</span>'}</b>` : ''}
        ${c.deadline ? `<span>To‘lash muddati</span><b>${dmy(c.deadline)}</b>` : ''}${c.note ? `<span>Izoh</span><b>${esc(c.note)}</b>` : ''}</div>
      <div class="chs-sub">Asl hujjatlar</div>
      ${c.files.length ? `<ul class="list chs-files">${c.files.map(f => fileRow(f, c)).join('')}</ul>`
        : `<div class="note ${issued ? 'warn' : ''}">${ic(issued ? 'alert' : 'info')}<span>${issued ? 'Asl hujjat hali yuklanmagan — imzolangan PDF yoki skan nusxani yuklang.' : 'Hujjat yuklanmagan.'}</span></div>`}
      <div class="chs-up"><select class="select sm" data-ukind="${c.id}" aria-label="Hujjat turi">${Object.entries(FKIND).map(([k, v]) => `<option value="${k}" ${k === (c.status === 'excused' ? 'asos' : c.measure === 'xat' || issued ? (c.measure === 'xat' ? 'xat' : 'imzolangan') : 'tushuntirish') ? 'selected' : ''}>${v}</option>`).join('')}</select>
        <label class="btn sm">${ic('upload')} Fayl yuklash (PDF, rasm)<input type="file" data-ufile="${c.id}" accept=".pdf,image/*,.doc,.docx" hidden multiple></label></div>
      ${c.docs.length ? `<div class="chs-sub">Shablondan (Word)</div><div class="wrapc">${c.docs.map(k => `<button class="btn sm ghost" data-wd="${c.order_id}" data-wk="${k.kind}" data-wc="${k.kind === 'xat' ? c.id : ''}">${ic(k.kind === 'xat' ? 'mail' : 'download')} ${esc(k.title)}</button>`).join('')}</div>` : ''}
    </div>`; };
  $('#dbody').innerHTML = `<p class="hint" style="margin:0">${esc(s.group)}${s.hemis_id ? ', HEMIS ' + esc(s.hemis_id) : ''}${s.hours != null ? ` · sababsiz: <b>${pairs(s.hours)}</b>` : ''} · ota-onalar: ${d.parents || 'ulanmagan'}</p>
    <div class="box"><h4>Yashash manzili <span class="sub-l" style="display:inline">(ota-onaga xat uchun)</span></h4><div class="wrapc"><span>${s.address ? esc(s.address) : '<span class="dash">kiritilmagan</span>'}</span>
      <button class="btn sm ghost" data-eaddr>${ic('edit')} O‘zgartirish</button></div></div>
    ${d.cases.length ? d.cases.map(caseBox).join('') : emptyBox('ok', 'O‘quv yilida chora ko‘rilmagan')}
    <a class="btn ghost" href="#/student/${s.id}">${ic('users')} Talaba kartasi</a>`;
  const reload = () => openChora(sid);
  $('[data-eaddr]', $('#dbody'))?.addEventListener('click', async () => { if (await editAddress(sid, s.name, s.address)) reload(); });
  $$('#dbody [data-fv]').forEach(b => b.addEventListener('click', () => viewFile(b.dataset.fv)));
  $$('#dbody [data-fd]').forEach(b => b.addEventListener('click', async () => { try { await download(`/api/staff/discipline/files/${b.dataset.fd}`); } catch (_) { toast('Yuklab bo‘lmadi', true); } }));
  $$('#dbody [data-fx]').forEach(b => b.addEventListener('click', async () => {
    if (!await confirmDlg('Faylni o‘chirish', 'Biriktirilgan fayl o‘chiriladi (ota-onaga yuborilgan nusxa ularda qoladi).', 'O‘chirish', true)) return;
    try { await api(`/api/staff/discipline/files/${b.dataset.fx}`, { method: 'DELETE' }); reload(); } catch (_) { toast('O‘chirilmadi', true); } }));
  $$('#dbody [data-fs]').forEach(b => b.addEventListener('click', async () => {
    if (!await confirmDlg('Ota-onaga yuborish', `${esc(s.name)} ning ota-onasiga ushbu PDF bot orqali yuboriladi va ilovadagi «Hujjatlar» bo‘limida saqlanadi.`, 'Yuborish')) return;
    b.disabled = true;
    try { const r = await api(`/api/staff/discipline/files/${b.dataset.fs}/send`, { method: 'POST' }); toast(`Yuborildi: ${r.parents} ota-ona`); reload(); }
    catch (e) { toast(e.message === 'shared_file' ? 'Umumiy hujjat chora chiqarilganda avtomatik yuboriladi' : e.message === 'not_sent' ? 'Yuborilmadi: hujjatda talaba topilmadi yoki ismdosh bor' : 'Yuborilmadi', true); b.disabled = false; } }));
  $$('#dbody [data-ufile]').forEach(i => i.addEventListener('change', async e => {
    const files = [...e.target.files]; if (!files.length) return;
    const meta = await askDocNo($(`[data-ukind="${i.dataset.ufile}"]`).value); if (!meta) return;
    const fd = new FormData(); fd.append('kind', $(`[data-ukind="${i.dataset.ufile}"]`).value);
    Object.entries(meta).forEach(([k, v]) => fd.append(k, v));
    files.forEach(f => fd.append('file', f, f.name));
    const kind = fd.get('kind'), cs = d.cases.find(c => c.id === Number(i.dataset.ufile));
    try { const r = await api(`/api/staff/discipline/cases/${i.dataset.ufile}/files`, { method: 'POST', body: fd });
      toast('Yuklandi' + autoMsg(r.auto, kind, cs && { status: cs.order_status })); reload(); }
    catch (err) { toast(err.message === 'too_big' ? 'Fayl juda katta (20 MB gacha)' : 'Yuklanmadi', true); } }));
  $$('#dbody [data-wd]').forEach(b => b.addEventListener('click', async () => {
    b.disabled = true; try { await download(`/api/staff/discipline/orders/${b.dataset.wd}/doc/${b.dataset.wk}${b.dataset.wc ? '?case=' + b.dataset.wc : ''}`); } catch (_) { toast('Yuklab bo‘lmadi', true); } b.disabled = false; }));
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
  ['debts', 'Kontrakt qarzdorligi'], ['debts_t', 'Trimestr qarzdorligi'], ['acad_debts', 'Akademik qarzdorlar (HEMIS ro‘yxati)'], ['phones', 'Talaba telefonlari'], ['addresses', 'Manzillar (ijarada yashash)'], ['categories', 'Ijtimoiy toifalar'], ['translations', 'Tarjimalar']];
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
  // chora ko'rilganlar — barcha kurslar (o'quv yili boshidan)
  const DS = ['students', 'total', 'repeat', 'pending', 'ogohlantirish', 'hayfsan', 'boshqa', 'xat', 'davomat', 'tartib', 'trimestr', 'letters'];
  const disc = d.courses.reduce((a, c) => { DS.forEach(k => { a[k] += (c.disc && c.disc[k]) || 0; }); return a; }, Object.fromEntries(DS.map(k => [k, 0])));
  const discTitle = x => x ? `O‘quv yilida: ${x.total} ta chora — ogohlantirish ${x.ogohlantirish}, hayfsan ${x.hayfsan}, boshqa ${x.boshqa}, xat ${x.xat}; asos: davomat ${x.davomat}, ichki tartib ${x.tartib}, trimestr ${x.trimestr}` : 'ma’lumot yo‘q';
  const discCell = x => !x ? '<span class="dash">—</span>' : `<span title="${esc(discTitle(x))}">${countCell(x.students, 'shield', x.pending ? 'bad' : '')}${x.pending ? `<small class="warn-t" style="display:block">kutilmoqda: ${x.pending}</small>` : ''}</span>`;
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
    <section class="kpis k2" aria-label="Talabalar bo‘yicha choralar">
      ${kpi({ icon: 'shield', c: 'risk', label: 'Chora ko‘rilganlar (barcha kurslar)', value: disc.students, unit: 'talaba', state: disc.pending ? 'bad' : null,
        title: `O‘quv yili boshidan rasman ko‘rilgan choralar: ${disc.total} ta`,
        sub: `<span class="ln">dekan ogohlantirishi: <b>${disc.ogohlantirish}</b> · hayfsan: <b>${disc.hayfsan}</b> · boshqa: <b>${disc.boshqa}</b></span>
          <span class="ln">asos — davomat: <b>${disc.davomat}</b> · ichki tartib: <b>${disc.tartib}</b> · trimestr: <b>${disc.trimestr}</b></span>
          <span class="ln">ota-onaga xat: <b>${disc.letters}</b>${disc.repeat ? ` · takroriy: <b>${disc.repeat}</b> talaba` : ''}</span>
          ${disc.pending ? `<span class="ln warn-t">chora kutilmoqda: <b>${disc.pending}</b> ta talaba</span>` : ''}` })}
      ${typeof socialKpi === 'function' ? socialKpi(d.courses) : ''}
    </section>
    <section class="sec"><header>${H('layers', 'Kurslar kesimida', 'people')}<a href="#/super/courses">Kurslarni boshqarish ${ic('arrow')}</a></header>
      ${d.courses.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl courses"><thead><tr><th>Kurs</th><th>Kurs koordinatorlari</th><th class="r">Talabalar</th><th>Ota-onasi ulangan</th>
        <th class="r">Muammoli</th><th class="r">Davomat</th><th class="r">Akademik</th><th class="r" title="O‘quv yilida chora ko‘rilgan talabalar">Chora</th><th class="r">Kontrakt qarzi</th><th class="r">Trimestr qarzi</th><th></th></tr></thead><tbody>
        ${d.courses.map(c => `<tr><td class="name"><div class="cname"><span class="h-ic sm c-people" aria-hidden="true">${ic('layers')}</span><b>${esc(c.title)}</b></div></td>
          <td>${c.admins.length ? `<div class="people">${c.admins.map(a => `<span class="person"><span class="av-s">${/^\p{L}/u.test(a.label) && !/^ID\b/.test(a.label) ? esc(initials(a.label)) : ic('users')}</span>${esc(a.label)}</span>`).join('')}</div>` : `<span class="chip warn">${ic('alert')}tayinlanmagan</span>`}</td>
          <td class="r">${c.total}</td><td>${pctCell(c.total ? pct(c.linked, c.total) : null)}</td>
          <td class="r">${countCell(c.prob, 'flame', c.multi ? 'bad' : '')}</td><td class="r">${countCell(c.att, 'calx', 'bad')}</td><td class="r">${countCell(c.acad, 'bookx', 'bad')}</td>
          <td class="r">${discCell(c.disc)}</td>
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
  const chs = e.target.closest('[data-chs]');
  if (chs && !e.target.closest('a, input, select, label') && (chs.tagName === 'BUTTON' || !e.target.closest('button'))) { openChora(Number(chs.dataset.chs)); return; }
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
