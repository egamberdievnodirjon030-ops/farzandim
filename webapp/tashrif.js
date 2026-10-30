/* =====================================================================
   Tashriflar — kurs koordinatorining ijara xonadonlariga tashriflari, madaniy tashriflar, tadbirlar va
   koordinatorlik soatlari (tashrif-py loyihasining asosiy qismlari, boshqaruv paneliga moslab):
     • rejalar — haftalik kalendar va ro'yxat, holatlar, jurnal;
     • talaba tasdig'i (botda): hammasi tasdiqlagach reja aktual; tadbir va boshqalar — darhol aktual;
     • «Qanday boriladi» — xarita, bekatlar, turgan joydan avtobus va metro (faqat koordinatorga);
     • yashash joylari — dashboard: ijara / TTJ / o'z uyi / qarindoshi, xonadon toifasi, xarita, tumanlar;
     • dalolatnoma — 16 band, telefon ekranida imzo, bir betli Word fayl (talaba hujjati sifatida saqlanadi);
     • hisobot — faqat tasdiqlangan rejalar.
   desk.js dagi umumiy yordamchilardan (api, view, kpi, ic, esc, toast …) foydalanadi.
   ===================================================================== */
'use strict';

Object.assign(P, {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  route: '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7.5a3.5 3.5 0 0 0 0-7h-7a3.5 3.5 0 0 1 0-7H16"/>',
  map: '<path d="m9 4-6 2.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
  img: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
  pen: '<path d="M4 20c2.5-1 4-3.5 5.5-6S13 9 15.5 9 18 11 16.5 13s-4 3-3 5 4 1 6.5-1"/>',
  chevr: '<path d="m9 6 6 6-6 6"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>'
});
PAGE_IC['Tashriflar'] = 'home';

/* ---------------------------------------------------------------- turlar, holatlar, javoblar */
const VT = {
  ijara_tashrifi: { t: 'Ijara xonadoniga tashrif', s: 'Ijara', c: 'vt-ij', icon: 'home' },
  madaniy_tashrif: { t: 'Madaniy tashrif', s: 'Madaniy', c: 'vt-ma', icon: 'map' },
  tadbir: { t: 'Tadbir', s: 'Tadbir', c: 'vt-ta', icon: 'mega' },
  koordinatorlik_soati: { t: 'Koordinatorlik soati', s: 'Koord. soati', c: 'vt-ks', icon: 'users' }
};
const VS = {
  qoralama: ['muted', 'Qoralama'], talaba_tasdigida: ['warn', 'Talabada'], tasdiqlangan: ['ok', 'Tasdiqlangan'],
  bajarildi: ['ok', 'Bajarildi'], bekor_qilingan: ['muted', 'Bekor qilingan']
};
const VS_LONG = { talaba_tasdigida: 'Talaba javobi kutilmoqda' };
const VR = {
  kutilmoqda: ['muted', 'javob kutilmoqda'], tasdiqladi: ['ok', 'tasdiqladi'], vaqt_taklif_qildi: ['warn', 'boshqa vaqt taklif qildi'],
  rad_etdi: ['bordo', 'bu manzilda yashamaydi'], javob_bermadi: ['muted', 'javob bermadi']
};
const LIVING_T = { ijara: 'Ijara xonadonida', ttj: 'Talabalar turar joyida', uy: 'O‘z uyida', qarindosh: 'Qarindoshinikida' };
const ZONE_C = { yashil: ['#2E7D4F', 'Yashil'], sariq: ['#B06800', 'Sariq'], qizil: ['#C0392B', 'Qizil'] };
const EV_T = {
  yaratildi: 'Reja tuzildi', tahrirlandi: 'Tahrirlandi', yuborildi: 'Yuborildi', talaba_tasdiqladi: 'Talaba tasdiqladi',
  talaba_vaqt_taklif_qildi: 'Talaba boshqa vaqt taklif qildi', talaba_rad_etdi: 'Talaba: bu manzilda yashamayman',
  vaqti_ozgartirildi: 'Vaqti o‘zgartirildi', tasdiqlandi: 'Tasdiqlandi — reja aktual', tasdiqlandi_javobsiz: 'Shundayligicha tasdiqlandi (javobsizlar bilan)',
  bajarildi: 'O‘tkazildi', bekor_qilindi: 'Bekor qilindi', dalolatnoma: 'Dalolatnoma tuzildi',
  ishtirokchilar_ozgartirildi: 'Ishtirokchilar o‘zgartirildi', elon_yuborildi: 'Botda e’lon qilindi',
  talaba_royxatdan_otdi: 'Talaba botda ro‘yxatdan o‘tdi', talaba_royxatdan_chiqdi: 'Talaba ro‘yxatdan chiqdi',
  royxat_yopildi: 'Ro‘yxatga olish yopildi', royxat_ochildi: 'Ro‘yxatga olish qayta ochildi'
};
/* e'londa ro'yxatga olish holati */
const REG_S = { open: ['ok', 'ro‘yxatga olish ochiq'], full: ['warn', 'joylar to‘ldi'], closed: ['muted', 'ro‘yxat yopilgan'],
  started: ['muted', 'ro‘yxatga olish yakunlangan'], over: ['muted', 'yakunlangan'], draft: ['muted', 'aktual qilinganda yuboriladi'] };
const EVT = ['tadbir', 'madaniy_tashrif'];            // ishtirokchi talabalar belgilanadi — botda ma'lumot va eslatma
const withStu = t => t === 'ijara_tashrifi' || EVT.includes(t);
const WHO_T = { koordinator: 'koordinator', talaba: 'talaba', tizim: 'tizim' };
const VERR = {
  past: 'Sanasi o‘tib ketgan rejani yuborib bo‘lmaydi', no_students: 'Ijara tashrifiga kamida bitta talaba biriktiring',
  no_title: 'Reja nomini yozing', bad_time: 'Vaqt noto‘g‘ri: tugash vaqti boshlanishidan keyin bo‘lsin', bad_date: 'Sana noto‘g‘ri',
  early: 'Tashrif vaqti hali kelmagan', no_reason: 'Bekor qilish sababini yozing',
  not_all: 'Hali barcha talabalar tasdiqlamagan', forbidden: 'Bu amal sizga ruxsat etilmagan', bad_location: 'Joylashuvni tushunmadim',
  bad_type: 'Bu reja turida bu amal yo‘q', no_audience: 'E’lon uchun kamida bitta guruh tanlang', bad_capacity: 'Joylar soni noto‘g‘ri'
};
const delivTxt = d => !d ? '' : (d.sent || d.missed ? ` · botda xabar: ${d.sent} ta${d.missed ? `, ulanmagan: ${d.missed} ta (koordinatorga havolalar yuborildi)` : ''}` : '')
  + (d.elon ? ` · e’lon: ${d.elon.sent} ta talabaga${d.elon.unlinked ? ` (botga ulanmagan: ${d.elon.unlinked} ta)` : ''}` : '');
const verr = e => (e && e.data && e.data.message) || VERR[e && e.message] || 'Bajarilmadi';

/* ---------------------------------------------------------------- kichik yordamchilar */
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else if (k === 'html') n.innerHTML = v;
    else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
    else if (k === 'value') n.value = v;
    else if (k === 'checked' || k === 'disabled' || k === 'hidden') n[k] = !!v;
    else n.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return n;
}
const fillKids = (node, ...kids) => node.replaceChildren(...kids.flat().filter(k => k != null && k !== false));
const isoD = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const mondayOf = d => { const x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; };
const dLong = iso => { const d = parseDate(iso + 'T00:00'); return d ? `${d.getDate()}-${MONTHS[d.getMonth()]}, ${DAYS[d.getDay()]}` : ''; };
const dShort = iso => { const d = parseDate(iso + 'T00:00'); return d ? `${d.getDate()}-${MONTHS[d.getMonth()]}` : ''; };
const pWhen = p => `${dLong(p.visit_date)}, ${p.start_time}–${p.end_time}`;
const vChip = s => { const v = VS[s] || ['muted', s]; return `<span class="chip ${v[0]}">${esc(v[1])}</span>`; };
const tChip = t => { const v = VT[t] || { s: t, c: '' }; return `<span class="chip vt ${v.c}">${ic(v.icon || 'cal')}${esc(v.s)}</span>`; };
const rChip = r => { const v = VR[r] || ['muted', r]; return `<span class="chip ${v[0]}">${esc(v[1])}</span>`; };
const fmtDist = m => m < 1000 ? `${Math.max(10, Math.round(m / 10) * 10)} m` : `${(m / 1000).toFixed(1).replace('.', ',')} km`;
const walkMin = m => `${Math.max(1, Math.round(m * 1.3 / 80))} daqiqa piyoda`;
const shortName = n => String(n || '').split(/\s+/).slice(0, 2).join(' ');

/* «Kurs holati» va menyu belgisi (desk.js chaqiradi) */
function tashrifBadge(c) { return c ? (c.need_act || 0) : 0; }
function tashrifKpi(c) {
  const lines = [`<span class="ln">talaba javobi kutilmoqda: <b>${c.students}</b>${c.drafts ? ` · qoralama: <b>${c.drafts}</b>` : ''}</span>`];
  if (c.need_act) lines.push(`<span class="ln warn-t">dalolatnoma yo‘q: <b>${c.need_act}</b></span>`);
  return kpi({ href: '#/tashrif', icon: 'home', c: 'people', label: 'Tashriflar', value: c.week, unit: 'ta', title: 'Shu haftadagi rejalar (bekor qilinganlarsiz)',
    state: c.need_act ? 'bad' : null, sub: `<span class="ln">bu hafta · aktual: <b>${c.week_actual}</b> · o‘tkazilgan: <b>${c.done}</b></span>` + lines.join('') });
}

/* ================================================================ sahifa */
async function pTashrif(parts, q) {
  document.title = 'Tashriflar — Boshqaruv paneli';
  const st = S.tash = S.tash || { tab: 'plans', mon: isoD(mondayOf(new Date())), view: 'week', type: '' };
  if (q && q.get('tab')) { st.tab = q.get('tab'); history.replaceState(null, '', '#/tashrif'); }
  view(head('Tashriflar', courseSub(), `<button class="btn primary" data-vnew>${ic('plus')} Yangi reja</button>`) + skel(70) + skel(320));
  const mon = parseDate(st.mon + 'T00:00');
  const from = isoD(addDays(mon, -7 * 5)), to = isoD(addDays(mon, 7 * 10));
  const d = await api(`/api/staff/visits?from=${from}&to=${to}`);
  S.tashD = d; S.tash.range = [from, to];
  S.badges.tashrif = tashrifBadge(d.counts); paintBadges();
  if (!['plans', 'homes', 'report'].includes(st.tab)) st.tab = 'plans';
  const tab = (k, icn, label, n) => `<button data-vtab="${k}" class="${st.tab === k ? 'on' : ''}" role="tab" aria-selected="${st.tab === k}">${ic(icn)} ${label}${n ? ` <span class="n">${n}</span>` : ''}</button>`;
  const sbot = d.student_bot ? `<span class="grow"></span><a class="chip ok" href="https://t.me/${esc(d.student_bot)}" target="_blank" rel="noopener" title="Talabaga tegishli hammasi shu botda: tashrif so‘rovlari, tadbir e’lonlari, eslatmalar. Talaba telefon raqami bilan o‘zi ulanadi.">${ic('telegram')} Talabalar boti: @${esc(d.student_bot)}</a>` : '';
  const tabs = `<div class="toolbar"><div class="seg" role="tablist">${tab('plans', 'cal', 'Rejalar', d.counts.week)}${tab('homes', 'map', 'Yashash joylari')}${tab('report', 'chart', 'Hisobot')}</div>${sbot}</div>`;
  let body = '';
  if (st.tab === 'plans') body = plansView(d, st);
  else if (st.tab === 'homes') body = `<div id="v-homes">${skel(110)}${skel(420)}</div>`;
  else body = `<div id="v-report">${skel(110)}${skel(300)}</div>`;
  view(head('Tashriflar', courseSub(), `<button class="btn primary" data-vnew>${ic('plus')} Yangi reja</button>`) + tabs + body);
  $$('[data-vtab]').forEach(b => b.addEventListener('click', () => { st.tab = b.dataset.vtab; route(); }));
  $('[data-vnew]')?.addEventListener('click', () => planEditor(null));
  bindPlanCards(main());
  if (st.tab === 'plans') bindPlans(d, st);
  if (st.tab === 'homes') loadHomes($('#v-homes'));
  if (st.tab === 'report') loadReport($('#v-report'), st);
}
function bindPlanCards(root) {
  $$('[data-vp]', root).forEach(x => x.addEventListener('click', e => { e.preventDefault(); openPlan(Number(x.dataset.vp)); }));
}

/* ---------------------------------------------------------------- rejalar: hafta va ro'yxat */
function planCard(p, compact = false) {
  const a = p.answers || {}, vt = VT[p.type] || {};
  const who = p.type === 'ijara_tashrifi' ? `<span class="pc-st">${ic('users')} ${a.total || 0} talaba${p.status === 'talaba_tasdigida' ? ` · ✅ ${a.tasdiqladi || 0}/${a.total || 0}` : ''}</span>`
    : (p.place ? `<span class="pc-st">${ic('pin')} ${esc(p.place)}</span>` : '') + (a.total || p.capacity ? `<span class="pc-st">${ic('users')} ${a.total || 0}${p.capacity ? '/' + p.capacity : ''} ishtirokchi</span>` : '')
      + (p.announce ? `<span class="pc-st" title="Botda e’lon — talabalar o‘zi ro‘yxatdan o‘tadi">${ic('mega')} e’lon</span>` : '');
  return `<a href="#" class="pcard ${vt.c || ''} st-${p.status}" data-vp="${p.id}" title="${esc(p.title)}">
    <span class="pc-t">${esc(p.start_time)}–${esc(p.end_time)}${compact ? '' : ' · ' + esc(vt.s || '')}</span>
    <b>${esc(p.title)}</b>${who}${vChip(p.status)}${p.acts_n ? `<span class="chip ok">${ic('file')} ${p.acts_n}</span>` : ''}</a>`;
}
function plansView(d, st) {
  const mon = parseDate(st.mon + 'T00:00'), today = isoD(new Date());
  const items = d.items.filter(p => !st.type || p.type === st.type);
  const c = d.counts;
  const strip = `<section class="kpis vk">
    ${kpi({ icon: 'cal', c: 'people', label: 'Bu hafta', value: c.week, unit: 'ta', sub: `aktual: <b>${c.week_actual}</b>` })}
    ${kpi({ icon: 'users', c: 'att', label: 'Talaba javobi kutilmoqda', value: c.students, unit: 'ta', sub: 'hammasi tasdiqlagach — aktual' })}
    ${kpi({ icon: 'edit', c: 'msg', label: 'Qoralama', value: c.drafts, unit: 'ta', sub: 'hali yuborilmagan' })}
    ${kpi({ icon: 'file', c: 'acad', label: 'Dalolatnoma kutilmoqda', value: c.need_act, unit: 'ta', state: c.need_act ? 'bad' : 'ok', sub: 'o‘tkazilgan ijara tashriflari' })}
    ${kpi({ icon: 'ok', c: 'gpa', label: 'O‘tkazilgan', value: c.done, unit: 'ta', sub: 'oxirgi oylarda' })}
  </section>`;
  const types = `<div class="seg">${[['', 'Barcha turlar'], ...Object.entries(VT).map(([k, v]) => [k, v.s])].map(([k, l]) => `<button data-vtype="${k}" class="${st.type === k ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  const bar = `<div class="toolbar vbar"><div class="seg">${[['week', 'Hafta'], ['list', 'Ro‘yxat']].map(([k, l]) => `<button data-vview="${k}" class="${st.view === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    ${st.view === 'week' ? `<div class="wnav"><button class="btn sm ghost" data-wk="-1" aria-label="Oldingi hafta">${ic('chevl')}</button>
      <b>${dShort(isoD(mon))} — ${dShort(isoD(addDays(mon, 6)))} ${addDays(mon, 6).getFullYear()}</b>
      <button class="btn sm ghost" data-wk="1" aria-label="Keyingi hafta">${ic('chevr')}</button><button class="btn sm" data-wk="0">Bugun</button></div>` : ''}
    <span class="grow"></span>${types}</div>`;
  let body;
  if (st.view === 'week') {
    const days = Array.from({ length: 7 }, (_, i) => isoD(addDays(mon, i)));
    body = `<div class="wgrid">${days.map(dd => { const list = items.filter(p => p.visit_date === dd);
      return `<div class="wday ${dd === today ? 'today' : ''} ${dd < today ? 'past' : ''}"><header><span>${DAYS[parseDate(dd + 'T00:00').getDay()].slice(0, 2).toUpperCase()}</span><b>${parseDate(dd + 'T00:00').getDate()}</b>
        <button class="btn sm ghost" data-vadd="${dd}" title="Shu kunga reja" aria-label="Shu kunga reja">${ic('plus')}</button></header>
        <div class="wlist">${list.map(p => planCard(p, true)).join('') || '<span class="dash">—</span>'}</div></div>`; }).join('')}</div>`;
  } else {
    const up = items.filter(p => p.visit_date >= today), past = items.filter(p => p.visit_date < today).reverse();
    const group = arr => { const by = {}; arr.forEach(p => (by[p.visit_date] = by[p.visit_date] || []).push(p));
      return Object.entries(by).map(([dd, l]) => `<div class="vday"><h4>${esc(dLong(dd))}</h4><div class="vrow">${l.map(p => planCard(p)).join('')}</div></div>`).join(''); };
    body = `<section class="sec"><header>${H('cal', 'Kelgusi rejalar', 'people')}</header><div class="pad">${up.length ? group(up) : emptyBox('cal', 'Kelgusi reja yo‘q', '«Yangi reja» tugmasi orqali qo‘shing.')}</div></section>
      <section class="sec" style="margin-top:18px"><header>${H('clock', 'O‘tgan rejalar', 'att')}<span class="hint">oxirgi 5 hafta</span></header><div class="pad">${past.length ? group(past) : '<span class="dash">Yo‘q</span>'}</div></section>`;
  }
  return strip + bar + body;
}
function bindPlans(d, st) {
  $$('[data-vview]').forEach(b => b.addEventListener('click', () => { st.view = b.dataset.vview; route(); }));
  $$('[data-vtype]').forEach(b => b.addEventListener('click', () => { st.type = b.dataset.vtype; route(); }));
  $$('[data-wk]').forEach(b => b.addEventListener('click', () => {
    const n = Number(b.dataset.wk);
    st.mon = n ? isoD(addDays(parseDate(st.mon + 'T00:00'), 7 * n)) : isoD(mondayOf(new Date())); route(); }));
  $$('[data-vadd]').forEach(b => b.addEventListener('click', () => planEditor(null, { visit_date: b.dataset.vadd })));
}

async function vAct(pid, act, body = {}, okMsg = 'Saqlandi', reopen = false) {
  try {
    const r = await api(`/api/staff/visits/${pid}/${act}`, { method: 'POST', json: body });
    toast(okMsg + delivTxt(r.delivery));
    const keep = reopen && $('#drawer.on');
    if (location.hash.startsWith('#/tashrif')) route();   // route() oynani yopadi — shuning uchun undan keyin ochamiz
    if (keep) openPlan(pid); else closeDrawer();
    return r;
  } catch (e) { toast(verr(e), true); return null; }
}

/* ---------------------------------------------------------------- reja oynasi (o'ng panel) */
async function openPlan(pid) {
  const dr = $('#drawer'); if (!dr) return;
  $('#dbody').innerHTML = skel(120) + skel(160, 2);
  dr.classList.add('on'); $('#scrim').classList.add('on'); dr.setAttribute('aria-hidden', 'false');
  $('#drawer header b').textContent = 'Reja';
  let p;
  try { p = (await api(`/api/staff/visits/${pid}`)).item; } catch (e) { $('#dbody').innerHTML = emptyBox('alert', 'Rejani ochib bo‘lmadi'); return; }
  $('#drawer header b').textContent = p.title;
  const own = p.can_manage, ij = p.type === 'ijara_tashrifi', ev = EVT.includes(p.type);
  const steps = ij ? [['qoralama', 'Qoralama'], ['talaba_tasdigida', 'Talabalar tasdig‘i'], ['tasdiqlangan', 'Tasdiqlangan'], ['bajarildi', 'O‘tkazildi']]
    : [['qoralama', 'Qoralama'], ['tasdiqlangan', 'Aktual'], ['bajarildi', 'O‘tkazildi']];
  const cur = steps.findIndex(([k]) => k === p.status);
  const flow = p.status === 'bekor_qilingan' ? '' : `<ol class="vflow">${steps.map(([k, l], i) => `<li class="${i < cur ? 'done' : i === cur ? 'cur' : ''}"><span>${i < cur ? ic('check') : i + 1}</span>${esc(l)}</li>`).join('')}</ol>`;
  const S_ = p.students || [];
  const studRow = s => `<li class="vst"><div class="vst-h"><span class="t"><b>${esc(s.full_name)}</b><span class="sub-l">${esc(s.group_name || '')}${s.address ? ' · ' + esc(s.address) : ' · <span class="warn-t">manzil kiritilmagan</span>'}</span></span>
      ${rChip(s.response)}</div>
      ${s.response === 'vaqt_taklif_qildi' ? `<div class="sub-l">Taklif: <b>${esc(dLong(s.proposed_date))}${s.proposed_time ? ', ' + esc(s.proposed_time) : ''}</b></div>` : ''}
      ${s.comment ? `<div class="sub-l">Izoh: ${esc(s.comment)}</div>` : ''}
      <div class="vst-a">${s.linked ? `<span class="chip ok" title="Tashrif xabarlari talabaning o‘ziga botda keladi">${ic('telegram')} botda</span>` : `<span class="chip warn" title="Talaba botga ulanmagan — shaxsiy havolani yuboring">${ic('telegram')} ulanmagan</span>
          <button class="btn sm ghost" data-vinv="${s.student_id}">${ic('link')} Havola</button>`}
        ${own && p.status === 'talaba_tasdigida' && s.response === 'vaqt_taklif_qildi' ? `<button class="btn sm primary" data-vacc="${s.student_id}">${ic('check')} Taklifni qabul qilish</button>` : ''}
        ${own && p.status === 'talaba_tasdigida' ? `<button class="btn sm ghost" data-vans="${s.student_id}">${ic('edit')} Javobni belgilash</button>` : ''}
        <span class="grow"></span><button class="btn sm ghost" data-vroute1="${s.student_id}">${ic('route')} Yo‘l</button>
        <button class="btn sm ghost" data-vstu="${s.student_id}" title="Talaba kartasi">${ic('users')}</button></div></li>`;
  const partRow = s => `<li class="vst"><div class="vst-h"><span class="t"><b>${esc(s.full_name)}</b></span>
      <span class="wrapc">${s.source === 'bot' ? `<span class="chip muted" title="E’londagi tugma orqali o‘zi ro‘yxatdan o‘tgan${s.registered_at ? ': ' + esc(when(s.registered_at)) : ''}">${ic('mega')} o‘zi yozildi</span>` : ''}${s.notified_at ? `<span class="chip ok" title="Botda xabar yetkazildi: ${esc(when(s.notified_at))}">${ic('check')} xabar yetdi</span>`
        : s.linked ? `<span class="chip ok" title="Reja aktual bo‘lganda xabar botda keladi">${ic('telegram')} botda</span>`
        : `<span class="chip warn" title="Talaba botga ulanmagan — shaxsiy havolani yuboring">${ic('telegram')} ulanmagan</span><button class="btn sm ghost" data-vinv="${s.student_id}">${ic('link')} Havola</button>`}
        <button class="btn sm ghost" data-vstu="${s.student_id}" title="Talaba kartasi" aria-label="Talaba kartasi">${ic('users')}</button></span></div></li>`;
  const partGroups = () => { const by = {}; S_.forEach(s => (by[s.group_name || '—'] = by[s.group_name || '—'] || []).push(s));
    return Object.entries(by).sort(([a], [b]) => a.localeCompare(b, 'uz')).map(([g, l]) => `<div class="chs-sub" style="margin-top:8px">${esc(g)} · ${l.length} ta</div><ul class="vsts compact">${l.map(partRow).join('')}</ul>`).join(''); };
  const ended = new Date(`${p.visit_date}T${p.end_time}`) < new Date();
  const canPart = own && ev && (p.status === 'qoralama' || (p.status === 'tasdiqlangan' && !ended));
  const acts = p.acts || [];
  const actRow = a => { const d = a.data || {};
    return `<li><span class="t">${ic('file')}<span><b>${esc(d.fio || 'Talaba tanlanmagan')}</b>${a.category ? ` <span class="zchip z-${a.category}">${esc(ZONE_C[a.category][1])} hudud</span>` : ''}
      <span class="sub-l">${esc(d.address || '')}${a.docx ? ` · Word fayl ${when(a.docx_at)}` : ''} · imzo: ${d.sigCoord ? 'koordinator ✓' : 'koordinator —'}, ${d.sigStudent ? 'talaba ✓' : 'talaba —'}</span></span></span>
      <span class="nowrap">${own ? `<button class="btn sm ghost" data-vaed="${a.id}" title="Tahrirlash">${ic('edit')}</button>` : ''}
        <button class="btn sm" data-vadoc="${a.id}" title="Word fayl (bir bet, imzolar bilan)">${ic('download')} Word</button>
        ${own ? `<button class="btn sm ghost" data-vadel="${a.id}" title="O‘chirish">${ic('x')}</button>` : ''}</span></li>`; };
  const canAct = own && ij && ['tasdiqlangan', 'bajarildi'].includes(p.status);
  const photos = p.photos || [];
  const evRow = ev => `<li><span class="ev-t">${when(ev.at)}</span><span><b>${esc(EV_T[ev.action] || ev.action)}</b>${ev.actor_name ? ` — ${esc(ev.actor_name)}` : ''}${ev.actor_kind ? ` <span class="sub-l" style="display:inline">(${esc(WHO_T[ev.actor_kind] || ev.actor_kind)})</span>` : ''}
    ${ev.detail ? `<span class="sub-l">${esc(ev.detail)}</span>` : ''}</span></li>`;
  const A = [];
  if (own && p.status === 'qoralama') A.push(`<button class="btn primary" data-vdo="send">${ic('send')} ${ij ? 'Talabalarga yuborish' : 'Aktual qilish'}</button>`, `<button class="btn" data-vedit>${ic('edit')} Tahrirlash</button>`);
  if (own && p.status === 'tasdiqlangan') A.push(`<button class="btn primary" data-vdone>${ic('ok')} O‘tkazildi</button>`);
  if (own && p.status === 'talaba_tasdigida') A.push(`<button class="btn" data-vforce>${ic('check')} Shundayligicha tasdiqlash</button>`);
  if (own && ['talaba_tasdigida', 'tasdiqlangan'].includes(p.status)) A.push(`<button class="btn" data-vtime>${ic('clock')} Vaqtni o‘zgartirish</button>`);
  if (own && !['bajarildi', 'bekor_qilingan'].includes(p.status)) A.push(`<button class="btn ghost danger-t" data-vcancel>${ic('x')} Bekor qilish</button>`);
  if (own && p.status === 'qoralama' && !p.sent_at) A.push(`<button class="btn ghost danger-t" data-vdel>${ic('x')} O‘chirish</button>`);
  $('#dbody').innerHTML = `<div class="wrapc">${tChip(p.type)}${vChip(p.status)}${p.status === 'talaba_tasdigida' ? `<span class="sub-l" style="display:inline">${esc(VS_LONG[p.status])}</span>` : ''}</div>
    ${flow}
    <div class="box"><div class="kv"><span>Sana va vaqt</span><b>${esc(pWhen(p))}</b><span>Kurs koordinatori</span><b>${esc(p.coordinator_name || '')}</b>
      ${p.place ? `<span>Joy</span><b>${esc(p.place)}</b>` : ''}${p.student_deadline && p.status === 'talaba_tasdigida' ? `<span>Talaba javobi muddati</span><b>${when(p.student_deadline)}</b>` : ''}</div>
      ${p.note ? `<p class="hint" style="margin:10px 0 0">${esc(p.note)}</p>` : ''}</div>
    ${p.status === 'bekor_qilingan' && p.cancel_reason ? `<div class="note">${ic('x')}<span><b>Bekor qilingan:</b> ${esc(p.cancel_reason)}</span></div>` : ''}
    ${p.result || p.problem ? `<div class="box"><h4>Natija</h4>${p.result ? `<p style="margin:0">${esc(p.result)}</p>` : ''}${p.problem ? `<p class="warn-t" style="margin:6px 0 0">Muammo: ${esc(p.problem)}</p>` : ''}</div>` : ''}
    ${A.length ? `<div class="vacts">${A.join('')}</div>` : ''}
    ${ij ? `<div class="box"><h4 class="h4row"><span>Talabalar — ${p.answers.total} ta <span class="sub-l" style="display:inline">· tasdiqlagan ${p.answers.tasdiqladi}</span></span>
        <button class="btn sm" data-vroute>${ic('route')} Qanday boriladi</button></h4>
      <ul class="vsts">${S_.map(studRow).join('')}</ul>
      <p class="hint" style="margin:8px 0 0">Talaba botda ✅ tasdiqlaydi, 🕒 boshqa vaqt taklif qiladi yoki ❌ «bu manzilda yashamayman» deydi. Tasdiqlashi bilan sizga shu manzilga qanday borilishi keladi (talabaga — yo‘q).</p></div>` : ''}
    ${ev ? elonBox(p, own, ended) : ''}
    ${ev ? `<div class="box"><h4 class="h4row"><span>Ishtirokchilar — ${S_.length} ta${S_.length ? ` <span class="sub-l" style="display:inline">· botda ${S_.filter(s => s.linked).length} · xabar yetgan ${S_.filter(s => s.notified_at).length}</span>` : ''}</span>
        ${canPart ? `<button class="btn sm" data-vpart title="Alohida talaba yoki butun guruhni qo‘shish, olib tashlash">${ic('users')} Qo‘lda kiritish</button>` : ''}</h4>
      ${S_.length ? partGroups() : `<span class="dash">${p.elon && p.elon.on ? 'Hali hech kim yozilmagan.' : 'Ishtirokchi talabalar belgilanmagan.'}</span>`}
      <p class="hint" style="margin:8px 0 0">Ishtirokchilar — qo‘lda kiritilganlar va e’londa o‘zi yozilganlar («o‘zi yozildi»). Botga ulanganlarga nomi, sanasi, vaqti va joyi yuboriladi; oldingi kuni kechqurun va boshlanishidan oldin eslatma boradi, vaqt o‘zgarsa yoki bekor qilinsa — ham. Ulanmagan talabaga shaxsiy havolani yuboring: ochishi bilan xabar keladi.</p></div>` : ''}
    ${ij && ['tasdiqlangan', 'bajarildi'].includes(p.status) ? `<div class="box"><h4>Dalolatnomalar — ${acts.length} ta</h4>
      ${acts.length ? `<ul class="list chs-files">${acts.map(actRow).join('')}</ul>` : `<div class="note ${p.status === 'bajarildi' ? 'warn' : ''}">${ic(p.status === 'bajarildi' ? 'alert' : 'info')}<span>Har bir talaba uchun dalolatnoma to‘ldiriladi (16 band, imzolar) — Word fayli bitta betda, qog‘oz namunadagidek chiqadi. 14-band (xonadon toifasi) «Yashash joylari» xaritasiga tushadi.</span></div>`}
      ${canAct ? `<div style="margin-top:10px"><button class="btn sm primary" data-vanew>${ic('plus')} Dalolatnoma</button></div>` : ''}</div>` : ''}
    ${['tasdiqlangan', 'bajarildi'].includes(p.status) ? `<div class="box"><h4>Suratlar — ${photos.length} ta</h4>
      ${photos.length ? `<div class="vph">${photos.map(f => `<figure><img data-vimg="${f.id}" alt="${esc(f.name || 'Surat')}" loading="lazy">${own ? `<button class="btn sm ghost" data-vphx="${f.id}" aria-label="O‘chirish">${ic('x')}</button>` : ''}</figure>`).join('')}</div>` : '<span class="dash">Surat yuklanmagan — ular dalolatnomaga ilova qilinadi.</span>'}
      ${own ? `<div style="margin-top:10px"><label class="btn sm">${ic('upload')} Surat yuklash<input type="file" data-vphup accept="image/jpeg,image/png,image/webp" hidden multiple></label></div>` : ''}</div>` : ''}
    <div class="box"><h4>Jurnal</h4><ul class="vev">${(p.events || []).slice().reverse().map(evRow).join('')}</ul></div>`;
  const B = $('#dbody'), re = () => openPlan(pid);
  bindPlanCards(B);
  $$('[data-vdo]', B).forEach(b => b.addEventListener('click', async () => {
    const act = b.dataset.vdo;
    if (act === 'send' && ij && !await confirmDlg('Talabalarga yuborish', `${S_.length} ta talabaga botda tashrif so‘rovi yuboriladi. Hammasi tasdiqlagach, reja o‘zi aktual bo‘ladi.`, 'Yuborish')) return;
    const E = p.elon || {};
    if (act === 'send' && ev && (S_.length || E.on) && !await confirmDlg('Aktual qilish', `Reja aktual bo‘ladi.${S_.length ? ` ${S_.length} ta ishtirokchiga botda ${esc(VT[p.type].t.toLowerCase())} haqida xabar yuboriladi: nomi, sanasi, vaqti va joyi.` : ''}${E.on ? ` ${esc((E.groups || []).join(', '))} guruhlari talabalariga botda e’lon boradi — «Ro‘yxatdan o‘tish» tugmasi bilan${E.capacity ? ` (${E.capacity} ta joy)` : ''}.` : ''}`, 'Aktual qilish')) return;
    b.disabled = true; await vAct(pid, act, {}, ij ? 'Yuborildi' : 'Aktual qilindi', true); b.disabled = false; }));
  $('[data-vedit]', B)?.addEventListener('click', () => planEditor(p));
  $('[data-vpart]', B)?.addEventListener('click', () => editParticipants(p));
  $('[data-vann]', B)?.addEventListener('click', () => announceDlg(p));
  $('[data-vreg]', B)?.addEventListener('click', async e => {
    const open = e.currentTarget.dataset.vreg === 'open';
    if (open || await confirmDlg('Ro‘yxatga olishni yopish', 'E’londagi «Ro‘yxatdan o‘tish» tugmalari o‘chadi, talabalar o‘zi yozila va chiqa olmaydi. Qo‘lda qo‘shish mumkin bo‘lib qoladi; ro‘yxatni keyin qayta ochish mumkin.', 'Yopish'))
      vAct(pid, open ? 'regopen' : 'regclose', {}, open ? 'Ro‘yxatga olish qayta ochildi' : 'Ro‘yxatga olish yopildi', true); });
  $('[data-vforce]', B)?.addEventListener('click', async () => {
    if (await confirmDlg('Shundayligicha tasdiqlash', 'Javob bermagan talabalar «javob bermadi» deb belgilanadi va reja aktual bo‘ladi. Tasdiqlagan talabalarga yakuniy xabar ketadi.', 'Tasdiqlash')) vAct(pid, 'confirm', {}, 'Tasdiqlandi', true); });
  $('[data-vtime]', B)?.addEventListener('click', async () => {
    const f = await formDlg('Vaqtni o‘zgartirish', `<p>${ij ? 'Vaqt o‘zgarsa, barcha tasdiqlar bekor bo‘ladi va so‘rov qaytadan yuboriladi (talaba 14:00 ga rozi bo‘lgan edi, boshqa vaqtga emas).'
      : ev && S_.length ? 'Ishtirokchilarga yangi vaqt botda yuboriladi; eslatmalar yangi vaqtga ko‘ra boradi.' : 'Reja yangi vaqtga ko‘chiriladi.'}</p>
      <div class="cols2"><label class="field"><span>Sana</span><input class="input" type="date" name="visit_date" value="${esc(p.visit_date)}" required></label><span></span>
      <label class="field"><span>Boshlanishi</span><input class="input" type="time" name="start_time" value="${esc(p.start_time)}" required></label>
      <label class="field"><span>Tugashi</span><input class="input" type="time" name="end_time" value="${esc(p.end_time)}" required></label></div>
      <label class="field"><span>Sabab (ixtiyoriy)</span><input class="input" name="reason"></label>`, 'O‘zgartirish');
    if (f) vAct(pid, 'time', Object.fromEntries(f), 'Vaqt o‘zgartirildi', true); });
  $('[data-vdone]', B)?.addEventListener('click', async () => {
    const f = await formDlg('Tashrif o‘tkazildi', `<label class="field"><span>Natija (qisqacha)</span><textarea class="textarea" name="result" rows="3"></textarea></label>
      <label class="field"><span>Aniqlangan muammo (bo‘lsa)</span><textarea class="textarea" name="problem" rows="2"></textarea></label>`, 'Saqlash');
    if (f) vAct(pid, 'done', Object.fromEntries(f), 'O‘tkazildi deb belgilandi', true); });
  $('[data-vcancel]', B)?.addEventListener('click', async () => {
    const f = await formDlg('Rejani bekor qilish', `<p>Talabalarga (xabar olgan bo‘lsa) bekor qilingani haqida botda yoziladi.</p><label class="field"><span>Sabab</span><input class="input" name="reason" required></label>`, 'Bekor qilish', true);
    if (f) vAct(pid, 'cancel', { reason: f.get('reason') }, 'Bekor qilindi', true); });
  $('[data-vdel]', B)?.addEventListener('click', async () => {
    if (!await confirmDlg('Qoralamani o‘chirish', 'Reja butunlay o‘chiriladi.', 'O‘chirish', true)) return;
    try { await api(`/api/staff/visits/${pid}`, { method: 'DELETE' }); toast('O‘chirildi'); closeDrawer(); route(); } catch (e) { toast(verr(e), true); } });
  $$('[data-vacc]', B).forEach(b => b.addEventListener('click', async () => {
    const s = S_.find(x => x.student_id === Number(b.dataset.vacc));
    if (await confirmDlg('Taklifni qabul qilish', `Tashrif vaqti ${esc(dLong(s.proposed_date))}${s.proposed_time ? ', ' + esc(s.proposed_time) : ''} ga ko‘chiriladi (davomiyligi saqlanadi). Barcha talabalarga so‘rov qaytadan yuboriladi.`, 'Qabul qilish'))
      vAct(pid, 'accept', { student_id: s.student_id }, 'Vaqt o‘zgartirildi', true); }));
  $$('[data-vans]', B).forEach(b => b.addEventListener('click', async () => {
    const s = S_.find(x => x.student_id === Number(b.dataset.vans));
    const f = await formDlg('Talaba javobini belgilash', `<p>${esc(s.full_name)} javobini telefonda yoki og‘zaki aytgan bo‘lsa — shu yerda belgilang (jurnalga «koordinator belgiladi» deb yoziladi).</p>
      <label class="field"><span>Javob</span><select class="select" name="response"><option value="tasdiqladi">✅ Tasdiqladi</option><option value="vaqt_taklif_qildi">🕒 Boshqa vaqt taklif qildi</option><option value="rad_etdi">❌ Bu manzilda yashamaydi</option></select></label>
      <div class="cols2"><label class="field"><span>Taklif sanasi</span><input class="input" type="date" name="proposed_date" value="${esc(p.visit_date)}"></label>
      <label class="field"><span>Taklif vaqti</span><input class="input" type="time" name="proposed_time"></label></div>
      <label class="field"><span>Izoh</span><input class="input" name="comment"></label>`, 'Saqlash');
    if (f) vAct(pid, 'answer', { student_id: s.student_id, ...Object.fromEntries(f) }, 'Javob belgilandi', true); }));
  $$('[data-vinv]', B).forEach(b => b.addEventListener('click', () => copyInvite(Number(b.dataset.vinv))));
  $$('[data-vstu]', B).forEach(b => b.addEventListener('click', () => { closeDrawer(); location.hash = `#/student/${b.dataset.vstu}`; }));
  $('[data-vroute]', B)?.addEventListener('click', () => openRoute({ pid, title: p.title }));
  $$('[data-vroute1]', B).forEach(b => b.addEventListener('click', () => { const s = S_.find(x => x.student_id === Number(b.dataset.vroute1)); openRoute({ sid: s.student_id, title: s.full_name }); }));
  $('[data-vanew]', B)?.addEventListener('click', () => openActEditor(p, null));
  $$('[data-vaed]', B).forEach(b => b.addEventListener('click', () => openActEditor(p, acts.find(a => a.id === Number(b.dataset.vaed)))));
  $$('[data-vadoc]', B).forEach(b => b.addEventListener('click', async () => {
    const a = acts.find(x => x.id === Number(b.dataset.vadoc)); b.disabled = true;
    try { await saveActDocx(p, a, own); re(); } catch (e) { console.error(e); toast('Word faylni yasab bo‘lmadi', true); }
    b.disabled = false; }));
  $$('[data-vadel]', B).forEach(b => b.addEventListener('click', async () => {
    if (!await confirmDlg('Dalolatnomani o‘chirish', 'Dalolatnoma va uning Word fayli o‘chiriladi.', 'O‘chirish', true)) return;
    try { await api(`/api/staff/visits/acts/${b.dataset.vadel}`, { method: 'DELETE' }); re(); } catch (e) { toast(verr(e), true); } }));
  $('[data-vphup]', B)?.addEventListener('change', async e => {
    const files = [...e.target.files]; if (!files.length) return;
    const fd = new FormData(); files.forEach(f => fd.append('file', f, f.name));
    try { await api(`/api/staff/visits/${pid}/photos`, { method: 'POST', body: fd }); toast('Yuklandi'); re(); }
    catch (err) { toast(err.message === 'too_big' ? 'Surat 16 MB dan katta' : 'Yuklanmadi (faqat JPG, PNG, WEBP)', true); } });
  $$('[data-vphx]', B).forEach(b => b.addEventListener('click', async () => {
    if (!await confirmDlg('Suratni o‘chirish', 'Surat o‘chiriladi.', 'O‘chirish', true)) return;
    try { await api(`/api/staff/visits/photos/${b.dataset.vphx}`, { method: 'DELETE' }); re(); } catch (e) { toast(verr(e), true); } }));
  $$('[data-vimg]', B).forEach(async im => { try { im.src = URL.createObjectURL(await (await api(`/api/staff/visits/photos/${im.dataset.vimg}`, { raw: true })).blob()); } catch (_) { /* */ } });
}
async function copyInvite(sid) {
  try {
    const r = await api(`/api/staff/visits/student/${sid}/invite`);
    try { await navigator.clipboard.writeText(r.url); toast('Havola nusxalandi — talabaga yuboring'); }
    catch (_) { await formDlg('Talabaning shaxsiy havolasi', `<p>Havolani talabaga yuboring: ochsa, botga ulanadi va tashrif so‘rovlari unga keladi.</p><input class="input" style="width:100%" value="${esc(r.url)}" readonly>`, 'Yopish'); }
  } catch (e) { toast('Havolani olib bo‘lmadi', true); }
}

/* ---------------------------------------------------------------- talaba tanlash (reja muharriri, ishtirokchilar) */
const stuOf = s => ({ id: s.student_id, name: s.full_name, group: s.group_name || '', address: s.address, linked: s.linked });
/* sel — tanlanganlar (Map id → talaba); mode() — 'ijara' (manzil bo'yicha, bittalab) yoki 'event' (guruh bilan) */
function stuPicker(sel, mode) {
  let all = null;
  const q = el('input', { class: 'input', type: 'search', oninput: () => paintRes() });
  const groups = el('div', { class: 'vgrp' }), res = el('div', { class: 'vpick-res' }), chosen = el('div', { class: 'vpick-box' });
  const changed = () => { paintRes(); paintSel(); };
  const tgChip = s => s.linked ? `<span class="chip ok" title="Botga ulangan — xabar o‘ziga boradi">${ic('telegram')}</span>` : '';
  const paintRes = () => {
    const ev = mode() === 'event', t = q.value.trim().toLowerCase();
    q.placeholder = ev ? 'F.I.Sh. yoki guruh bo‘yicha qidirish' : 'F.I.Sh., guruh yoki manzil bo‘yicha qidirish';
    groups.hidden = !ev || !all;
    if (!all) return;
    if (ev) {
      const by = {}; all.forEach(s => (by[s.group || '—'] = by[s.group || '—'] || []).push(s));
      fillKids(groups, el('span', { class: 'sub-l', text: 'Butun guruhni qo‘shish:' }), ...Object.entries(by).sort(([a], [b]) => a.localeCompare(b, 'uz')).map(([g, l]) => {
        const left = l.filter(s => !sel.has(s.id));
        return el('button', { type: 'button', class: 'btn sm' + (left.length ? '' : ' ghost'), disabled: !left.length,
          title: left.length ? `${left.length} ta talaba qo‘shiladi` : 'Guruhning hammasi tanlangan',
          onclick: () => { left.forEach(s => sel.set(s.id, s)); changed(); }, html: `${left.length ? ic('plus') : ic('check')} ${esc(g)} <small>${l.length}</small>` });
      }));
    }
    const list = all.filter(s => !sel.has(s.id) && (!t || s.name.toLowerCase().includes(t) || s.group.toLowerCase().includes(t) || (!ev && (s.address || '').toLowerCase().includes(t))))
      .sort(ev ? (a, b) => a.group.localeCompare(b.group) || a.name.localeCompare(b.name) : (a, b) => (b.living === 'ijara') - (a.living === 'ijara') || a.name.localeCompare(b.name))
      .slice(0, t ? 40 : 12);
    fillKids(res, ...list.map(s => el('button', { type: 'button', class: 'vpick', onclick: () => { sel.set(s.id, s); changed(); } },
      el('span', { class: 't', html: `<b>${esc(s.name)}</b><small>${esc(s.group)}${ev ? '' : s.address ? ' · ' + esc(s.address) : ' · manzil yo‘q'}</small>` }),
      el('span', { class: 'b', html: ev ? tgChip(s) : `${s.living && s.living !== 'ijara' ? `<span class="chip muted">${esc(LIVING_T[s.living] || s.living)}</span>` : ''}${s.located ? '<span class="chip ok">joyi aniq</span>' : ''}${tgChip(s)}` }),
      el('span', { html: ic('plus') }))), list.length ? null : el('span', { class: 'dash', text: 'Topilmadi' }));
  };
  const paintSel = () => {
    const L = [...sel.values()];
    if (mode() !== 'event') {
      fillKids(chosen, el('ul', { class: 'vpick-sel' }, L.map(s => el('li', {},
        el('span', { html: `<b>${esc(s.name)}</b> <small>${esc(s.group || '')}${s.address ? ' · ' + esc(s.address) : ''}</small>` }),
        el('button', { type: 'button', class: 'btn sm ghost', 'aria-label': 'Olib tashlash', onclick: () => { sel.delete(s.id); changed(); }, html: ic('x') }))),
        L.length ? null : el('li', { class: 'dash', text: 'Talaba tanlanmagan' })));
      return;
    }
    if (!L.length) { fillKids(chosen, el('span', { class: 'dash', text: 'Ishtirokchi tanlanmagan — guruh tugmasi yoki qidiruv orqali qo‘shing' })); return; }
    const by = {}; L.forEach(s => (by[s.group || '—'] = by[s.group || '—'] || []).push(s));
    fillKids(chosen, el('div', { class: 'vsel-h' }, el('b', { text: `Tanlangan: ${L.length} ta` }),
      el('span', { class: 'sub-l', text: `botga ulangan: ${L.filter(s => s.linked).length} ta` }), el('span', { class: 'grow' }),
      el('button', { type: 'button', class: 'btn sm ghost', onclick: () => { sel.clear(); changed(); } }, 'Hammasini olib tashlash')),
    Object.entries(by).sort(([a], [b]) => a.localeCompare(b, 'uz')).map(([g, l]) => el('div', { class: 'vsel-g' },
      el('div', { class: 'vsel-gh' }, el('b', { text: g }), el('small', { text: `${l.length} ta` }), el('span', { class: 'grow' }),
        el('button', { type: 'button', class: 'btn sm ghost', onclick: () => { l.forEach(s => sel.delete(s.id)); changed(); } }, 'Guruhni olib tashlash')),
      el('div', { class: 'vsel-chips' }, l.sort((a, b) => a.name.localeCompare(b.name)).map(s => el('span', { class: 'vchipx' + (s.linked ? ' on' : ''), title: s.linked ? 'Botga ulangan' : 'Botga ulanmagan' },
        shortName(s.name), el('button', { type: 'button', 'aria-label': 'Olib tashlash', onclick: () => { sel.delete(s.id); changed(); }, html: ic('x') })))))));
  };
  let loadP = null;
  const load = () => loadP || (loadP = api('/api/staff/visits/students').then(r => {
    all = r.items;
    for (const s of all) if (sel.has(s.id)) sel.set(s.id, { ...sel.get(s.id), linked: s.linked });
    changed();
    return all;
  }).catch(() => { res.textContent = 'Ro‘yxatni yuklab bo‘lmadi'; loadP = null; return []; }));
  return { groups, q, res, chosen, load, repaint: changed };
}

/* ---------------------------------------------------------------- reja tuzish / tahrirlash */
const TYPE_HINT = { ijara_tashrifi: 'talabalar tasdiqlaydi', tadbir: 'botda e’lon, ro‘yxatdan o‘tish', madaniy_tashrif: 'botda e’lon, ro‘yxatdan o‘tish', koordinatorlik_soati: 'yuborilishi bilan aktual' };
/* e'lon guruhlari: [{name, n}] → tugmalar; tanlanmagan bo'lsa — barchasi */
const groupsOf = all => { const by = {}; (all || []).forEach(s => { const g = s.group || '—'; by[g] = (by[g] || 0) + 1; });
  return Object.entries(by).sort(([a], [b]) => a.localeCompare(b, 'uz')).map(([name, n]) => ({ name, n })); };
function audPicker(chosen) {
  const sel = new Set(chosen || []), box = el('div', { class: 'vaud' });
  let groups = [];
  const paint = () => {
    const all = !sel.size || groups.every(g => sel.has(g.name));
    fillKids(box, el('button', { type: 'button', class: 'vgchip' + (all ? ' on' : ''), onclick: () => { sel.clear(); paint(); } }, `Barcha guruhlarim (${groups.length})`),
      groups.map(g => el('button', { type: 'button', class: 'vgchip' + (!all && sel.has(g.name) ? ' on' : ''), 'aria-pressed': String(!all && sel.has(g.name)),
        onclick: () => { if (all) sel.clear(); sel.has(g.name) ? sel.delete(g.name) : sel.add(g.name); if (groups.every(x => sel.has(x.name))) sel.clear(); paint(); },
        html: `${esc(g.name)} <small>${g.n}</small>` })));
  };
  return { node: box, set: g => { groups = g; paint(); }, value: () => (groups.length && groups.every(g => sel.has(g.name)) ? [] : [...sel]) };
}
const TITLE_PH = { ijara_tashrifi: 'Masalan: Ijara xonadonlariga tashrif — XM-21', tadbir: 'Masalan: Mustaqillik bayrami konserti', madaniy_tashrif: 'Masalan: Temuriylar tarixi muzeyiga sayohat', koordinatorlik_soati: 'Masalan: Koordinatorlik soati — XM-21' };
async function planEditor(p, preset = {}) {
  const isNew = !p;
  const v = p ? { ...p } : { type: 'ijara_tashrifi', title: '', visit_date: preset.visit_date || isoD(addDays(new Date(), 1)), start_time: '14:00', end_time: '16:00', place: '', note: '' };
  const sel = new Map((p ? p.students : []).map(s => [s.student_id, stuOf(s)]));
  const dl = el('dialog', { class: 'vdlg' });
  const typeSeg = el('div', { class: 'vtypes' }, Object.entries(VT).map(([k, t]) => el('label', { class: 'vtype ' + t.c },
    el('input', { type: 'radio', name: 'type', value: k, checked: v.type === k, disabled: !isNew, onchange: () => { v.type = k; paint(); } }),
    el('span', { html: `${ic(t.icon)}<b>${esc(t.s)}</b><small>${esc(TYPE_HINT[k] || '')}</small>` }))));
  const inp = (name, type = 'text', attrs = {}) => el('input', { class: 'input', type, name, value: v[name] || '', oninput: e => { v[name] = e.target.value; }, ...attrs });
  const pk = stuPicker(sel, () => v.type === 'ijara_tashrifi' ? 'ijara' : 'event');
  const stuLbl = el('span'), stuNote = el('p', { class: 'hint', style: 'margin:0' });
  const stuBox = el('div', { class: 'field' }, stuLbl, stuNote, pk.groups, pk.q, pk.res, pk.chosen);
  // botda e'lon: yangi tadbirda — yoqilgan, barcha guruhlarga
  const E = p ? (p.elon || {}) : { on: true };
  const annOn = el('input', { type: 'checkbox', checked: !!E.on, onchange: () => paint() });
  const aud = audPicker(E.groups);
  const capIn = el('input', { class: 'input', type: 'number', min: 1, max: 5000, placeholder: 'cheklanmagan', value: E.capacity || '' });
  const annBody = el('div', { class: 'vel-b' }, el('span', { class: 'sub-l', text: 'Kimlarga (shu guruhlardagi botga ulangan talabalarga):' }), aud.node,
    el('label', { class: 'field', style: 'margin:6px 0 0;max-width:220px' }, el('span', { text: 'Joylar soni' }), capIn));
  const annBox = el('div', { class: 'field vel' }, el('label', { class: 'vel-h' }, annOn,
    el('span', { html: `<b>${ic('mega')} Botda e’lon qilish</b><small>Talabalar e’londagi «✅ Ro‘yxatdan o‘tish» tugmasini bosib o‘zi yoziladi va ishtirokchilar ro‘yxatiga qo‘shiladi. Joylar to‘lsa, ro‘yxatga olish o‘zi yopiladi.</small>` })), annBody);
  const placeBox = el('label', { class: 'field' }, el('span', { text: 'Joyi' }), inp('place', 'text', { placeholder: 'Masalan: Milliy teatr, universitet akt zali' }));
  const err = el('div', { class: 'note bordo', hidden: true });
  const titleIn = inp('title', 'text', { required: true });
  const paint = () => {
    const ij = v.type === 'ijara_tashrifi';
    stuBox.hidden = !withStu(v.type); placeBox.hidden = ij;
    annBox.hidden = !EVT.includes(v.type); annBody.hidden = !annOn.checked;
    stuLbl.textContent = ij ? 'Talabalar (ijara manzili talaba kartasidan olinadi)' : 'Qo‘lda kiritish (ixtiyoriy) — alohida talaba yoki butun guruh';
    stuNote.textContent = ij ? '' : 'Qo‘lda kiritilganlar e’lonsiz ham ishtirokchi bo‘ladi: reja aktual bo‘lishi bilan ularga botda nomi, sanasi, vaqti va joyi yuboriladi; oldingi kuni kechqurun va boshlanishidan oldin eslatma boradi.';
    stuNote.hidden = ij;
    titleIn.placeholder = TITLE_PH[v.type] || '';
    if (withStu(v.type)) pk.load().then(all => aud.set(groupsOf(all)));
    pk.repaint();
  };
  const submit = async send => {
    err.hidden = true;
    if (!v.title.trim()) {
      v.title = v.type === 'ijara_tashrifi' ? `Ijara xonadonlariga tashrif${sel.size ? ' — ' + [...new Set([...sel.values()].map(s => s.group).filter(Boolean))].join(', ') : ''}` : VT[v.type].t;
    }
    const body = { type: v.type, title: v.title, visit_date: v.visit_date, start_time: v.start_time, end_time: v.end_time, place: v.place, note: v.note,
      student_ids: withStu(v.type) ? [...sel.keys()] : undefined,
      ...(EVT.includes(v.type) ? { announce: annOn.checked, audience: aud.value(), capacity: annOn.checked ? capIn.value : '' } : {}) };
    try {
      let r;
      if (isNew) r = await api('/api/staff/visits', { method: 'POST', json: { ...body, send } });
      else { r = await api(`/api/staff/visits/${p.id}`, { method: 'POST', json: body });
        if (send) r = await api(`/api/staff/visits/${p.id}/send`, { method: 'POST' }); }
      dl.close(); dl.remove();
      if (r.send_error) toast('Qoralama saqlandi, lekin yuborilmadi: ' + (r.send_error.message || VERR[r.send_error.error] || r.send_error.error), true);
      else toast(send ? 'Saqlandi va yuborildi' + delivTxt(r.delivery) : 'Qoralama saqlandi');
      S.tash = S.tash || {}; S.tash.mon = isoD(mondayOf(parseDate(body.visit_date + 'T00:00')));
      if (location.hash.startsWith('#/tashrif')) route(); else location.hash = '#/tashrif';
      openPlan(r.item.id);
    } catch (e) { err.textContent = verr(e); err.hidden = false; }
  };
  dl.append(el('form', { method: 'dialog', class: 'wide', onsubmit: e => e.preventDefault() },
    el('h3', { text: isNew ? 'Yangi reja' : 'Rejani tahrirlash' }),
    el('div', { class: 'field' }, el('span', { text: 'Turi' }), typeSeg),
    el('label', { class: 'field' }, el('span', { text: 'Nomi' }), titleIn),
    el('div', { class: 'cols3' },
      el('label', { class: 'field' }, el('span', { text: 'Sana' }), inp('visit_date', 'date', { required: true })),
      el('label', { class: 'field' }, el('span', { text: 'Boshlanishi' }), inp('start_time', 'time', { required: true })),
      el('label', { class: 'field' }, el('span', { text: 'Tugashi' }), inp('end_time', 'time', { required: true }))),
    placeBox,
    el('label', { class: 'field' }, el('span', { text: 'Izoh (talabaga ko‘rinadi)' }),
      el('textarea', { class: 'textarea', rows: 2, oninput: e => { v.note = e.target.value; } }, v.note || '')),
    annBox, stuBox,
    err,
    el('div', { class: 'row' },
      el('button', { class: 'btn', type: 'button', onclick: () => { dl.close(); dl.remove(); } }, 'Bekor qilish'),
      el('button', { class: 'btn', type: 'button', onclick: () => submit(false) }, 'Qoralama sifatida saqlash'),
      el('button', { class: 'btn primary', type: 'button', onclick: () => submit(true) }, 'Saqlash va yuborish'))));
  document.body.append(dl);
  dl.addEventListener('close', () => dl.remove());
  paint();
  dl.showModal();
}

/* aktual tadbir / madaniy tashrifning ishtirokchilari — yangi qo'shilganlarga botda darhol xabar */
function editParticipants(p) {
  const sel = new Map(p.students.map(s => [s.student_id, stuOf(s)]));
  const pk = stuPicker(sel, () => 'event');
  const dl = el('dialog', { class: 'vdlg' });
  const save = el('button', { class: 'btn primary', type: 'button', onclick: async () => {
    save.disabled = true;
    const r = await vAct(p.id, 'students', { student_ids: [...sel.keys()] }, 'Ishtirokchilar saqlandi', true);
    if (r) dl.close(); else save.disabled = false; } }, 'Saqlash');
  dl.append(el('form', { method: 'dialog', class: 'wide', onsubmit: e => e.preventDefault() },
    el('h3', { text: 'Ishtirokchilar' }), el('p', { class: 'hint', style: 'margin-top:-6px', text: `${p.title} · ${pWhen(p)}` }),
    p.status === 'tasdiqlangan' ? el('div', { class: 'note' }, el('span', { html: ic('info') }), el('span', { text: 'Reja aktual: yangi qo‘shilgan talabalarga botda darhol xabar boradi, ro‘yxatdan chiqarilganlarga (xabar olgan bo‘lsa) bu haqda yoziladi.' })) : null,
    el('div', { class: 'field' }, pk.groups, pk.q, pk.res, pk.chosen),
    el('div', { class: 'row' }, el('button', { class: 'btn', type: 'button', onclick: () => dl.close() }, 'Bekor qilish'), save)));
  document.body.append(dl);
  dl.addEventListener('close', () => dl.remove());
  pk.load(); pk.repaint();
  dl.showModal();
}

/* reja oynasidagi «Botda e'lon» bo'limi */
function elonBox(p, own, ended) {
  const E = p.elon || {}, act = own && p.status === 'tasdiqlangan' && !ended;
  if (!E.on) return act ? `<div class="box"><h4 class="h4row"><span>${ic('mega')} Botda e’lon</span><button class="btn sm primary" data-vann>${ic('mega')} E’lon qilish</button></h4>
    <span class="dash">E’lon qilinmagan. E’lon qilsangiz, tanlangan guruhlar talabalari botda «Ro‘yxatdan o‘tish» tugmasini bosib o‘zi yoziladi.</span></div>` : '';
  const rs = REG_S[E.state] || ['muted', E.state], open = ['open', 'full'].includes(E.state);
  return `<div class="box"><h4 class="h4row"><span>${ic('mega')} Botda e’lon <span class="chip ${rs[0]}">${esc(rs[1])}</span></span>
      ${act ? `<span class="nowrap">${E.state === 'closed' ? `<button class="btn sm" data-vreg="open">${ic('check')} Qayta ochish</button>` : open ? `<button class="btn sm" data-vreg="close">${ic('x')} Ro‘yxatni yopish</button>` : ''}
        <button class="btn sm ghost" data-vann title="Guruh qo‘shish, joylar soni">${ic('edit')} Sozlash</button></span>` : ''}</h4>
    <div class="kv"><span>Guruhlar</span><b>${esc((E.groups || []).join(', '))}</b>
      ${E.state !== 'draft' ? `<span>E’lon yuborildi</span><b>${E.sent} ta talabaga${E.audience - E.linked ? ` <span class="sub-l" style="display:inline">· botga ulanmagan: ${E.audience - E.linked} ta</span>` : ''}</b>
      <span>Botda ro‘yxatdan o‘tgan</span><b>${E.registered} ta</b>` : `<span>Talabalar</span><b>${E.audience} ta, botga ulangan: ${E.linked} ta</b>`}
      <span>Joylar</span><b>${E.capacity ? `${E.total} / ${E.capacity}${E.free != null ? ` <span class="sub-l" style="display:inline">· bo‘sh ${E.free}</span>` : ''}` : 'cheklanmagan'}</b></div>
    ${open ? '<p class="hint" style="margin:8px 0 0">Botga keyinroq ulangan talabalarga e’lon bir necha daqiqada o‘zi boradi. Ro‘yxatdan o‘tganlar quyidagi «Ishtirokchilar» ro‘yxatiga qo‘shiladi; ularga ham eslatmalar boradi.</p>' : ''}</div>`;
}
/* aktual rejani e'lon qilish yoki e'lonni kengaytirish (guruh qo'shish, joylar soni) */
async function announceDlg(p) {
  const E = p.elon || {};
  const aud = audPicker(E.on ? E.groups : []);
  const capIn = el('input', { class: 'input', type: 'number', min: 1, max: 5000, placeholder: 'cheklanmagan', value: E.capacity || '' });
  const dl = el('dialog', { class: 'vdlg' });
  const go = el('button', { class: 'btn primary', type: 'button', onclick: async () => {
    go.disabled = true;
    const r = await vAct(p.id, 'announce', { audience: aud.value(), capacity: capIn.value }, E.on ? 'E’lon yangilandi' : 'E’lon yuborildi', true);
    if (r) dl.close(); else go.disabled = false; } }, E.on ? 'Saqlash va yuborish' : 'E’lon qilish');
  dl.append(el('form', { method: 'dialog', class: 'wide', onsubmit: e => e.preventDefault() },
    el('h3', { text: E.on ? 'E’lon sozlamalari' : 'Botda e’lon qilish' }), el('p', { class: 'hint', style: 'margin-top:-6px', text: `${p.title} · ${pWhen(p)}` }),
    el('p', { text: E.on ? 'Yangi qo‘shilgan guruhlarga e’lon boradi; avval yuborilgan e’lonlardagi joylar soni yangilanadi.' : 'Tanlangan guruhlardagi botga ulangan talabalarga e’lon boradi — «✅ Ro‘yxatdan o‘tish» tugmasi bilan. Yozilganlar ishtirokchilar ro‘yxatiga qo‘shiladi.' }),
    el('div', { class: 'field' }, el('span', { text: 'Kimlarga' }), aud.node),
    el('label', { class: 'field', style: 'max-width:220px' }, el('span', { text: 'Joylar soni' }), capIn),
    el('div', { class: 'row' }, el('button', { class: 'btn', type: 'button', onclick: () => dl.close() }, 'Bekor qilish'), go)));
  document.body.append(dl);
  dl.addEventListener('close', () => dl.remove());
  dl.showModal();
  try { aud.set(groupsOf((await api('/api/staff/visits/students')).items)); } catch (_) { toast('Guruhlarni yuklab bo‘lmadi', true); }
}

/* ================================================================ xarita (Leaflet — serverdan) */
let leafletP = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve();
  if (!leafletP) leafletP = new Promise((res, rej) => {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/static/vendor/leaflet/leaflet.css'; document.head.append(css);
    const js = document.createElement('script'); js.src = '/static/vendor/leaflet/leaflet.js';
    js.onload = () => res(); js.onerror = () => { leafletP = null; js.remove(); rej(new Error('xarita')); };
    document.head.append(js);
  });
  return leafletP;
}
function baseMap(box, center, zoom = 12, opts = {}) {
  const map = L.map(box, { zoomControl: true, scrollWheelZoom: !!opts.wheel, zoomSnap: 0.5 }).setView(center, zoom);
  // OpenStreetMap sayt manzili (Referer) siz so'rovlarni «Access blocked» rasmi bilan rad etadi; sahifamiz esa
  // no-referrer — faqat xarita rasmlariga sayt domeni (yo'lsiz) yuboriladi
  const o = { maxZoom: 19, attribution: '© OpenStreetMap', referrerPolicy: 'strict-origin-when-cross-origin' };
  const main_ = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', o).addTo(map);
  main_.on('tileerror', () => { if (map._altTiles) return; map._altTiles = true;
    try { map.removeLayer(main_); L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png', { ...o, maxZoom: 18 }).addTo(map); } catch (e) { /* */ } });
  return map;
}
const numIcon = (n, color, dashed) => L.divIcon({ className: 'vpin', iconSize: [28, 28], iconAnchor: [14, 14],
  html: `<span style="background:${color}${dashed ? ';outline:2px dashed #fff;outline-offset:-5px' : ''}">${n}</span>` });

/* ---------------------------------------------------------------- «Qanday boriladi» */
async function openRoute({ pid, sid, title }) {
  const dl = el('dialog', { class: 'vdlg vroute' });
  const bar = el('div', { class: 'rtbar' }), list = el('div', { class: 'rtlist' }), mapBox = el('div', { class: 'rtmap' }), msg = el('div', { class: 'hint' });
  let map = null, layer = null, data = null, me = null, focus = 0, picking = false, timer = null, tries = 0, gone = false;
  const close = () => { gone = true; clearTimeout(timer); if (map) map.remove(); dl.close(); dl.remove(); };
  dl.append(el('div', { class: 'vd-h' }, el('b', { text: `Qanday boriladi — ${title || ''}` }), el('button', { class: 'btn sm ghost', type: 'button', onclick: close, html: ic('x') + ' Yopish' })),
    bar, msg, el('div', { class: 'rtwrap' }, list, mapBox));
  document.body.append(dl); dl.addEventListener('cancel', e => { e.preventDefault(); close(); }); dl.showModal();
  const url = () => (pid ? `/api/staff/visits/${pid}/route` : `/api/staff/visits/student/${sid}/route`) + (me ? `?lat=${me[0]}&lon=${me[1]}` : '');
  async function load() {
    clearTimeout(timer);
    try { data = await api(url()); } catch (e) { list.replaceChildren(el('div', { class: 'empty', html: `<b>Yo‘l ma’lumotini olib bo‘lmadi</b>${esc(verr(e))}` })); return; }
    if (gone) return;
    drawBar(); drawList(); drawMap();
    if (data.talabalar.some(t => t.holat === 'aniqlanmoqda') && tries++ < 8) timer = setTimeout(load, 5000);
  }
  function drawBar() {
    bar.replaceChildren(el('span', { class: 'me', html: me ? `<span class="dot"></span><span>Siz turgan joy<small>${me[0].toFixed(5)}, ${me[1].toFixed(5)}</small></span>` : '<span>Turgan joyingizni ko‘rsating<small>shunda qaysi avtobus yoki metro borishi chiqadi</small></span>' }),
      el('span', { class: 'grow' }),
      el('button', { class: 'btn sm' + (me ? '' : ' primary'), type: 'button', onclick: locate, html: ic('pin') + (me ? ' Yangilash' : ' Turgan joyimni aniqlash') }),
      el('button', { class: 'btn sm ghost', type: 'button', 'aria-pressed': String(picking), onclick: () => { picking = !picking; drawBar(); msg.textContent = picking ? 'Xaritada turgan joyingizni bosing.' : ''; } }, picking ? 'Bekor qilish' : 'Xaritadan ko‘rsatish'));
  }
  function locate() {
    if (!navigator.geolocation) { msg.textContent = 'Brauzer joylashuvni aniqlay olmaydi — «Xaritadan ko‘rsatish» ni bosing.'; return; }
    msg.textContent = 'Joylashuvingiz aniqlanmoqda… (brauzer ruxsat so‘rasa — ruxsat bering)';
    navigator.geolocation.getCurrentPosition(p => { me = [p.coords.latitude, p.coords.longitude]; msg.textContent = ''; load(); },
      e => { msg.textContent = e.code === 1 ? 'Joylashuvga ruxsat berilmadi — «Xaritadan ko‘rsatish» ni bosing.' : 'Joylashuvni aniqlab bo‘lmadi — «Xaritadan ko‘rsatish» ni bosing.'; },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
  }
  const buses = (arr, cls = '') => arr.map(r => `<span class="bus ${cls}">${esc(r)}</span>`).join('');
  function routeBlock(y) {
    let h = `<div class="rts">Turgan joyingizdan <b>${fmtDist(y.masofa)}</b></div>`;
    (y.togri || []).forEach((o, i) => { h += `<div class="rtopt ${i ? '' : 'best'}"><div class="rtline">${buses(o.raqamlar)}<span class="how">almashishsiz</span></div><ol class="rtsteps">
      <li>Sizdan <b>«${esc(o.chiqish.nom)}»</b> bekatigacha — ${fmtDist(o.chiqish.masofa)}, ${walkMin(o.chiqish.masofa)}</li>
      <li class="ride"><b>${esc(o.raqamlar.join(', '))}</b>-avtobusda <b>«${esc(o.tushish.nom)}»</b> bekatigacha</li>
      <li>Bekatdan manzilgacha — ${fmtDist(o.tushish.masofa)}, ${walkMin(o.tushish.masofa)}</li></ol></div>`; });
    if (y.metro) h += `<div class="rtopt ${(y.togri || []).length ? '' : 'best'}"><div class="rtline"><span class="metro">M</span> Metro</div><ol class="rtsteps">
      <li>Sizdan <b>«${esc(y.metro.chiqish.nom)}»</b> bekatigacha — ${fmtDist(y.metro.chiqish.masofa)}</li><li class="ride m">Metroda <b>«${esc(y.metro.tushish.nom)}»</b> bekatigacha</li>
      <li>Bekatdan manzilgacha — ${fmtDist(y.metro.tushish.masofa)}, ${walkMin(y.metro.tushish.masofa)}</li></ol></div>`;
    if (!(y.togri || []).length) (y.almashish || []).forEach(a => { h += `<div class="rtopt"><div class="rtline"><span class="bus">${esc(a.birinchi)}</span>→<span class="bus alt">${esc(a.ikkinchi)}</span><span class="how">bitta almashish</span></div><ol class="rtsteps">
      <li><b>«${esc(a.chiqish.nom)}»</b> bekatidan (sizdan ${fmtDist(a.chiqish.masofa)})</li><li class="ride"><b>${esc(a.birinchi)}</b>-avtobusda <b>«${esc(a.bekat)}»</b> gacha, u yerda <b>${esc(a.ikkinchi)}</b> ga o‘ting</li>
      <li><b>«${esc(a.tushish.nom)}»</b> bekatida tushing (manzilgacha ${fmtDist(a.tushish.masofa)})</li></ol></div>`; });
    if (y.masofa <= 1200) h += `<div class="hint">🚶 Piyoda ham bo‘ladi: ${walkMin(y.masofa)}.</div>`;
    else if (!(y.togri || []).length && !y.metro && !(y.almashish || []).length) h += '<div class="hint">Qulay avtobus yoki metro topilmadi — xaritadan qarang yoki taksi chaqiring.</div>';
    return h;
  }
  function nearBlock(t) {
    const st = (t.bekatlar || []).filter(b => (b.raqamlar || []).length).slice(0, 3), show = st.length ? st : (t.bekatlar || []).slice(0, 2);
    return `<div class="rts">Manzil yaqinida</div>${show.map(b => `<div class="rtstop"><span class="pt"></span><div><div class="nm">${esc(b.nom || 'Bekat')}</div><div class="w">${fmtDist(b.masofa)} · ${walkMin(b.masofa)}</div>
      ${(b.raqamlar || []).length ? `<div class="buses">${buses(b.raqamlar.slice(0, 14), 'dim')}</div>` : ''}</div></div>`).join('')}
      ${(t.metro || []).slice(0, 1).map(m => `<div class="rtstop"><span class="metro">M</span><div><div class="nm">${esc(m.nom)} metro bekati</div><div class="w">${fmtDist(m.masofa)}</div></div></div>`).join('')}
      ${!show.length && !(t.metro || []).length ? '<div class="hint">Yaqin atrofda bekat topilmadi.</div>' : ''}`;
  }
  function drawList() {
    if (!data.talabalar.length) { list.innerHTML = emptyBox('users', 'Talaba yo‘q'); return; }
    list.innerHTML = data.talabalar.map((t, i) => {
      const badge = t.joy ? (t.joy.aniqlik === 'aniq' ? ['ok', 'joy aniq'] : ['warn', 'joy taxminiy']) : ['muted', t.holat === 'aniqlanmoqda' ? 'aniqlanmoqda…' : t.holat === 'manzil_yoq' ? 'manzil yo‘q' : 'joy topilmadi'];
      let body = '';
      if (!t.joy) body = `<div class="hint">${t.holat === 'aniqlanmoqda' ? 'Manzil xaritadan aniqlanmoqda — bir necha soniyada o‘zi yangilanadi.' : 'Xarita bu manzilni topa olmadi. Talaba kartasida joylashuvni ko‘rsating — shunda bekatlar va yo‘l aniq chiqadi.'}</div>
        <div class="rtact"><button class="btn sm" data-rtloc="${t.id}">${ic('pin')} Joylashuvni kiritish</button>${t.havolalar.qidiruv ? `<a class="btn sm ghost" href="${esc(t.havolalar.qidiruv)}" target="_blank" rel="noopener">Yandex Xaritalarda qidirish</a>` : ''}</div>`;
      else body = (t.joy.aniqlik !== 'aniq' ? '<div class="hint">Uy xaritada topilmadi — joy taxminiy. Aniq bo‘lishi uchun talaba kartasida joylashuvni ko‘rsating.</div>' : '')
        + (t.yonalish ? routeBlock(t.yonalish) : data.turgan_joy ? '<div class="hint">Bu hudud uchun marshrut ma’lumoti yo‘q — xaritadan qarang.</div>' : '') + nearBlock(t)
        + `<div class="rtact"><a class="btn sm primary" href="${esc(t.havolalar.xarita)}" target="_blank" rel="noopener">🗺 Yandex Xaritalarda ${data.turgan_joy ? 'aniq ' : ''}yo‘l</a><a class="btn sm" href="${esc(t.havolalar.taksi)}" target="_blank" rel="noopener">🚕 Yandex Go</a>
          ${t.joy.aniqlik !== 'aniq' ? `<button class="btn sm ghost" data-rtloc="${t.id}">${ic('pin')} Joylashuvni kiritish</button>` : ''}</div>`;
      return `<div class="rtc" aria-current="${i === focus}"><button class="rth" type="button" data-rtf="${i}"><span class="rtn">${i + 1}</span><span class="tx"><b>${esc(t.ism)}</b><small>${esc(t.manzil || 'manzil kiritilmagan')}</small></span><span class="chip ${badge[0]}">${badge[1]}</span></button>${i === focus ? body : ''}</div>`;
    }).join('');
    $$('[data-rtf]', list).forEach(b => b.addEventListener('click', () => { focus = Number(b.dataset.rtf); drawList(); drawMap(); }));
    $$('[data-rtloc]', list).forEach(b => b.addEventListener('click', () => { close(); closeDrawer(); location.hash = `#/student/${b.dataset.rtloc}`; }));
  }
  async function drawMap() {
    try { await loadLeaflet(); } catch (e) { mapBox.innerHTML = emptyBox('map', 'Xarita yuklanmadi'); return; }
    if (gone) return;
    const pts = data.talabalar.map(t => t.joy ? [t.joy.lat, t.joy.lon] : null);
    if (!map) {
      map = baseMap(mapBox, pts.find(Boolean) || [41.3111, 69.2797], 13, { wheel: true });
      map.on('click', e => { if (!picking) return; picking = false; me = [e.latlng.lat, e.latlng.lng]; msg.textContent = ''; load(); });
    }
    if (layer) layer.remove();
    layer = L.layerGroup().addTo(map);
    const t = data.talabalar[focus], css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    data.talabalar.forEach((x, i) => { if (pts[i]) L.marker(pts[i], { icon: numIcon(i + 1, i === focus ? '#7A1C2C' : '#1F3A8A', x.joy.aniqlik !== 'aniq') }).addTo(layer).on('click', () => { focus = i; drawList(); drawMap(); }); });
    const b = [];
    if (t && t.joy) {
      b.push(pts[focus]);
      (t.bekatlar || []).slice(0, 6).forEach(s => s.lat && L.circleMarker([s.lat, s.lon], { radius: 5, color: '#B06800', weight: 2, fillColor: '#fff', fillOpacity: 1 }).bindTooltip(`${s.nom || 'Bekat'}${(s.raqamlar || []).length ? ' — ' + s.raqamlar.slice(0, 8).join(', ') : ''}`).addTo(layer));
      (t.metro || []).slice(0, 1).forEach(m => m.lat && L.marker([m.lat, m.lon], { icon: L.divIcon({ className: 'vpin m', iconSize: [22, 22], iconAnchor: [11, 11], html: '<span>M</span>' }) }).bindTooltip(m.nom + ' metro').addTo(layer));
      const y = t.yonalish, o = y && ((y.togri || [])[0] || null);
      if (me && o) {
        L.polyline([me, [o.chiqish.lat, o.chiqish.lon]], { color: '#5B6B86', weight: 3, dashArray: '4 6' }).addTo(layer);
        L.polyline([[o.chiqish.lat, o.chiqish.lon], [o.tushish.lat, o.tushish.lon]], { color: css('--accent') || '#1F3A8A', weight: 5 }).addTo(layer);
        L.polyline([[o.tushish.lat, o.tushish.lon], pts[focus]], { color: '#5B6B86', weight: 3, dashArray: '4 6' }).addTo(layer);
      } else if (me && y && y.metro && y.metro.chiqish.lat) {
        L.polyline([me, [y.metro.chiqish.lat, y.metro.chiqish.lon], [y.metro.tushish.lat, y.metro.tushish.lon], pts[focus]], { color: '#C0392B', weight: 4, dashArray: '8 6' }).addTo(layer);
      }
    }
    if (me) { L.circleMarker(me, { radius: 8, color: '#fff', weight: 3, fillColor: '#2563EB', fillOpacity: 1 }).bindTooltip('Siz turgan joy').addTo(layer); b.push(me); }
    if (b.length > 1) map.fitBounds(L.latLngBounds(b).pad(0.25), { maxZoom: 16 }); else if (b.length) map.setView(b[0], 16);
    setTimeout(() => map && map.invalidateSize(), 60);
  }
  drawBar(); list.innerHTML = skel(160); load();
}

/* ---------------------------------------------------------------- xaritadan nuqta tanlash */
function pickPoint(start, title = 'Xaritadan tanlash') {
  return new Promise(async resolve => {
    try { await loadLeaflet(); } catch (e) { toast('Xarita yuklanmadi', true); resolve(null); return; }
    const box = el('div', { class: 'rtmap pick' }), info = el('div', { class: 'hint', text: 'Uyning ustiga bosing (xaritani yaqinlashtirib oling).' });
    let pt = start || null, mk = null;
    const ok = el('button', { class: 'btn primary', type: 'button', disabled: !pt }, 'Shu joyni saqlash');
    const dl = el('dialog', { class: 'vdlg' }, el('div', { class: 'vd-h' }, el('b', { text: title }), el('button', { class: 'btn sm ghost', type: 'button', onclick: () => done(null), html: ic('x') })),
      info, box, el('div', { class: 'row', style: 'padding:0 18px 16px' }, el('button', { class: 'btn', type: 'button', onclick: () => done(null) }, 'Bekor qilish'), ok));
    let map;
    const done = v => { if (map) map.remove(); dl.close(); dl.remove(); resolve(v); };
    ok.addEventListener('click', () => done(pt));
    dl.addEventListener('cancel', e => { e.preventDefault(); done(null); });
    document.body.append(dl); dl.showModal();
    map = baseMap(box, pt || [41.3111, 69.2797], pt ? 17 : 12, { wheel: true });
    const put = p => { pt = p; ok.disabled = false; if (mk) mk.setLatLng(p); else mk = L.marker(p, { icon: numIcon('', '#7A1C2C') }).addTo(map); info.textContent = `${p[0].toFixed(6)}, ${p[1].toFixed(6)}`; };
    if (pt) put(pt);
    map.on('click', e => put([e.latlng.lat, e.latlng.lng]));
    setTimeout(() => map.invalidateSize(), 80);
  });
}

/* ---------------------------------------------------------------- talaba kartasi: yashash joyi va tashriflar */
async function loadStudentHome(sid, course) {
  const box = $('#stu-home'); if (!box) return;
  let d;
  try { d = await api(`/api/staff/visits/student/${sid}`, { course }); } catch (e) { box.remove(); return; }
  if (!$('#stu-home')) return;
  const z = d.zone ? ZONE_C[d.zone] : null;
  box.innerHTML = `<h4>Yashash joyi va tashriflar</h4>
    <div class="kv"><span>Yashash joyi</span><b><select class="select sm" data-hliv>${['', ...Object.keys(LIVING_T)].map(k => `<option value="${k}" ${d.living === k || (!d.living && !k) ? 'selected' : ''}>${k ? esc(LIVING_T[k]) : '— belgilanmagan —'}</option>`).join('')}</select></b>
      <span>Ijara manzili</span><b class="wrapc" style="justify-content:flex-end">${d.address ? esc(d.address) : '<span class="dash">kiritilmagan</span>'}<button class="btn sm ghost" data-haddr title="O‘zgartirish">${ic('edit')}</button></b>
      <span>Xaritadagi joyi</span><b class="wrapc" style="justify-content:flex-end">${d.lat != null ? `<span class="chip ok">${ic('pin')} ${Number(d.lat).toFixed(5)}, ${Number(d.lon).toFixed(5)}</span>` : '<span class="dash">ko‘rsatilmagan</span>'}
        <button class="btn sm ghost" data-hloc>${ic('pin')} ${d.lat != null ? 'O‘zgartirish' : 'Ko‘rsatish'}</button></b>
      <span>Xonadon toifasi</span><b class="wrapc" style="justify-content:flex-end">${z ? `<span class="zchip z-${d.zone}">${esc(z[1])} hudud</span>` : '<span class="dash">baholanmagan</span>'}
        ${d.zone_from === 'act' ? '<span class="sub-l" style="display:inline">dalolatnomadan</span>' : `<select class="select sm" data-hzone><option value="">— qo‘lda —</option>${Object.entries(ZONE_C).map(([k, v]) => `<option value="${k}" ${d.zone === k ? 'selected' : ''}>${v[1]}</option>`).join('')}</select>`}</b>
      <span>Bot (tashrif xabarlari)</span><b>${d.account.linked ? `<span class="chip ok">${ic('telegram')} ulangan${d.account.via === 'tasdiq' ? ' (ota-onani tasdiqlagan)' : ''}</span>` : `<button class="btn sm ghost" data-hinv>${ic('link')} Shaxsiy havola</button>`}</b></div>
    ${d.near ? `<p class="hint" style="margin:8px 0 0">${ic('pin')} ${esc(d.near)}</p>` : ''}
    <div class="wrapc" style="margin-top:10px"><button class="btn sm" data-hroute ${d.address || d.lat != null ? '' : 'disabled'}>${ic('route')} Qanday boriladi</button>
      <button class="btn sm ghost" data-hnew>${ic('plus')} Tashrif rejalash</button></div>
    ${d.visits.length ? `<div class="chs-sub" style="margin-top:12px">Tashriflar</div><ul class="vmini">${d.visits.map(x => `<li><a href="#" data-vp="${x.id}"><span>${tChip(x.type)} ${esc(x.when)}</span>${vChip(x.status)}${x.response && x.type === 'ijara_tashrifi' ? rChip(x.response) : ''}</a></li>`).join('')}</ul>` : ''}
    ${d.acts.length ? `<div class="chs-sub" style="margin-top:12px">Dalolatnomalar</div><ul class="vmini">${d.acts.map(a => `<li><span>${ic('file')} ${esc(dmy(a.created_at))}${a.category ? ` <span class="zchip z-${a.category}">${esc(ZONE_C[a.category][1])}</span>` : ''}</span>
      ${a.docx ? `<button class="btn sm ghost" data-hdoc="${a.id}">${ic('download')} Word</button>` : '<span class="dash">Word fayl yasalmagan</span>'}</li>`).join('')}</ul>` : ''}`;
  const save = async body => { try { await api(`/api/staff/visits/student/${sid}`, { method: 'POST', json: body, course }); toast('Saqlandi'); loadStudentHome(sid, course); } catch (e) { toast(verr(e), true); } };
  $('[data-hliv]', box).addEventListener('change', e => save({ living: e.target.value }));
  $('[data-hzone]', box)?.addEventListener('change', e => save({ zone: e.target.value }));
  $('[data-haddr]', box).addEventListener('click', async () => {
    const f = await formDlg('Ijara manzili', `<p>Tuman, ko‘cha (mavze), uy, xonadon — masalan: «Uchtepa tumani, 14-kvartal, 2-uy, 63-xonadon». Bu — talaba hozir yashayotgan (ijara) manzili: tashriflar va xarita uchun. Ota-onaga xatdagi doimiy manzil (kontingentdan) bundan alohida va o‘zgarmaydi.</p>
      <label class="field"><span>Manzil</span><input class="input" name="address" value="${esc(d.address)}"></label>`, 'Saqlash');
    if (f) save({ address: f.get('address') }); });
  $('[data-hloc]', box).addEventListener('click', async () => {
    const f = await formDlg('Xaritadagi aniq joy', `<p>Koordinata (41.3418, 69.2879) yoki xarita havolasi (Yandex, Google, 2GIS, OpenStreetMap — «ulashish» qisqa havolasi ham) kiriting yoki xaritadan tanlang. Shu nuqtadan bekatlar va yo‘l hisoblanadi.</p>
      <label class="field"><span>Koordinata yoki havola</span><input class="input" name="location" value="${d.lat != null ? `${d.lat}, ${d.lon}` : ''}" placeholder="41.3418, 69.2879"></label>
      <div class="wrapc"><button class="btn sm" type="button" data-pick>${ic('map')} Xaritadan tanlash</button>${d.lat != null ? '<span class="hint">Bo‘sh qoldirilsa — joy olib tashlanadi</span>' : ''}</div>`, 'Saqlash');
    if (f) save({ location: f.get('location') || '' }); });
  $('[data-hinv]', box)?.addEventListener('click', () => copyInvite(sid));
  $('[data-hroute]', box).addEventListener('click', () => openRoute({ sid, title: $('#drawer header b').textContent }));
  $('[data-hnew]', box).addEventListener('click', () => planEditorFor(sid, d));
  $$('[data-hdoc]', box).forEach(b => b.addEventListener('click', async () => { try { await download(`/api/staff/visits/acts/${b.dataset.hdoc}/docx`); } catch (_) { toast('Yuklab bo‘lmadi', true); } }));
  bindPlanCards(box);
}
/* «Xaritadan tanlash» tugmasi joylashuv dialogi ichida — nuqtani maydonga yozadi */
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-pick]'); if (!b) return;
  const inp = b.closest('form').querySelector('[name=location]'), m = (inp.value || '').match(/(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)/);
  const dlg = b.closest('dialog'); dlg.close();
  const pt = await pickPoint(m ? [Number(m[1]), Number(m[2])] : null, 'Talabaning ijara xonadoni');
  if (pt) inp.value = `${pt[0].toFixed(6)}, ${pt[1].toFixed(6)}`;
  dlg.showModal();
});
async function planEditorFor(sid, d) {
  closeDrawer();
  let all;
  try { all = (await api('/api/staff/visits/students')).items; } catch (_) { all = []; }
  const s = all.find(x => x.id === sid);
  planEditor(null, {});
  setTimeout(() => {   // tanlangan talabani darhol qo'shamiz
    const dl = document.querySelector('dialog.vdlg[open]'); if (!dl || !s) return;
    const q = dl.querySelector('input[type=search]'); q.value = s.name; q.dispatchEvent(new Event('input'));
    setTimeout(() => dl.querySelector('.vpick')?.click(), 400);
  }, 50);
}

/* ---------------------------------------------------------------- yashash joylari (dashboard) */
async function loadHomes(box) {
  let d, shapes = [];
  try { [d, shapes] = await Promise.all([api('/api/staff/visits/dashboard'), api('/api/staff/visits/districts').catch(() => [])]); }
  catch (e) { box.innerHTML = emptyBox('alert', 'Ma’lumotni yuklab bo‘lmadi'); return; }
  const st = S.tash.homes = S.tash.homes || { show: { ijara: true }, zone: '', dist: '' };
  const L_ = d.living, Z = d.zones, rent = L_.ijara || 0;
  const share = n => d.total ? Math.round(100 * n / d.total) + '%' : '';
  const card = (k, icon, c, label) => `<a href="#" class="kpi c-${c} ${st.show[k] ? 'sel' : ''}" data-hshow="${k}" title="Xaritaga qo‘shish / olish">
    <div class="kpi-top"><span class="kpi-ic c-${c}">${ic(icon)}</span><span class="kpi-k">${label}</span></div><div class="kpi-v num">${L_[k] || 0}<small>ta</small></div><div class="kpi-s">${share(L_[k] || 0)} talabalar</div></a>`;
  const zcard = (k, label) => { const z = Z[k] || { students: 0, flats: 0 };
    return `<a href="#" class="kpi zk ${st.zone === k ? 'sel' : ''}" data-hzone="${k}" style="--zc:${k === 'none' ? 'var(--faint)' : ZONE_C[k][0]}"><div class="kpi-top"><span class="zdot"></span><span class="kpi-k">${label}</span></div>
      <div class="kpi-v num">${z.students}<small>talaba</small></div><div class="kpi-s">${z.flats} ta xonadon</div></a>`; };
  box.innerHTML = `<section class="kpis k3">${card('ijara', 'home', 'people', 'Ijara xonadonida')}${card('ttj', 'building', 'msg', 'Talabalar turar joyida')}${card('uy', 'users', 'gpa', 'O‘z uyida')}${card('qarindosh', 'users', 'acad', 'Qarindoshinikida')}
      ${kpi({ icon: 'alert', c: 'risk', label: 'Yashash joyi belgilanmagan', value: d.unknown, unit: 'ta', sub: 'talaba kartasida belgilanadi' })}
      ${kpi({ icon: 'pin', c: 'att', label: 'Xaritada', value: d.located, unit: `/ ${rent}`, sub: `${d.queue ? `aniqlanmoqda: <b>${d.queue}</b> · ` : ''}topilmadi: <b>${d.not_found}</b> · manzilsiz: <b>${d.no_address}</b>` })}</section>
    <section class="kpis k3 zrow">${zcard('yashil', 'Yashil hudud')}${zcard('sariq', 'Sariq hudud')}${zcard('qizil', 'Qizil hudud')}${zcard('none', 'Baholanmagan')}</section>
    ${!d.geo ? `<div class="note warn">${ic('alert')}<span>Yo‘l ma’lumoti o‘chirilgan (YOL_MALUMOTI=yoq) — manzillar xaritadan qidirilmaydi, faqat talaba kartasida ko‘rsatilgan nuqtalar chiqadi.</span></div>` : ''}
    <div class="grid-2 hgrid"><section class="sec"><header>${H('map', 'Talabalar qayerda yashaydi', 'people')}<span class="hint">belgi rangi — xonadon toifasi, raqam — shu joyda nechta talaba</span></header>
      <div class="dmap" id="hmap"></div></section>
      <section class="sec"><header>${H('layers', 'Hududlar kesimi', 'att')}</header><div class="pad hdist">${d.districts.length ? `<table class="tbl"><thead><tr><th>Tuman</th><th class="r">Talaba</th><th class="r">Xonadon</th><th>Toifalar</th></tr></thead><tbody>
        ${d.districts.map(x => `<tr class="click ${st.dist === x.name ? 'sel' : ''}" data-hdist="${esc(x.name)}"><td>${esc(x.name)}</td><td class="r"><b>${x.students}</b></td><td class="r">${x.flats}</td>
          <td><span class="zbar">${['yashil', 'sariq', 'qizil'].map(z => x[z] ? `<i style="flex:${x[z]};background:${ZONE_C[z][0]}" title="${ZONE_C[z][1]}: ${x[z]}"></i>` : '').join('')}${x.students - x.yashil - x.sariq - x.qizil > 0 ? `<i style="flex:${x.students - x.yashil - x.sariq - x.qizil}" class="zn" title="Baholanmagan"></i>` : ''}</span></td></tr>`).join('')}</tbody></table>` : '<span class="dash">Ijarada yashovchi talaba yo‘q</span>'}</div></section></div>
    <div id="hlist"></div>`;
  $$('[data-hshow]', box).forEach(a => a.addEventListener('click', e => { e.preventDefault(); const k = a.dataset.hshow; st.show[k] = !st.show[k]; loadHomesMap(d, shapes, st); a.classList.toggle('sel', !!st.show[k]); }));
  $$('[data-hzone]', box).forEach(a => a.addEventListener('click', e => { e.preventDefault(); st.zone = st.zone === a.dataset.hzone ? '' : a.dataset.hzone; $$('[data-hzone]', box).forEach(x => x.classList.toggle('sel', x.dataset.hzone === st.zone)); loadHomesMap(d, shapes, st); paintFlats(d, st); }));
  $$('[data-hdist]', box).forEach(r => r.addEventListener('click', () => { st.dist = st.dist === r.dataset.hdist ? '' : r.dataset.hdist; $$('[data-hdist]', box).forEach(x => x.classList.toggle('sel', x.dataset.hdist === st.dist)); paintFlats(d, st); loadHomesMap(d, shapes, st, true); }));
  paintFlats(d, st);
  loadHomesMap(d, shapes, st);
}
function homesFiltered(d, st) {
  return d.items.filter(x => st.show[x.living || 'none'] && (!st.zone || (st.zone === 'none' ? !x.zone : x.zone === st.zone)) && (!st.dist || (x.tuman || '—') === st.dist));
}
function paintFlats(d, st) {
  const box = $('#hlist'); if (!box) return;
  const rows = homesFiltered(d, st).filter(x => x.living === 'ijara');
  const flats = {};
  rows.forEach(x => (flats[x.xonadon || 'id' + x.id] = flats[x.xonadon || 'id' + x.id] || []).push(x));
  const list = Object.values(flats).sort((a, b) => b.length - a.length || (a[0].tuman || '').localeCompare(b[0].tuman || ''));
  const miss = rows.filter(x => x.holat !== 'ok');
  box.innerHTML = `<section class="sec" style="margin-top:18px"><header>${H('home', `Xonadonlar — ${list.length} ta${st.dist ? ' · ' + esc(st.dist) : ''}${st.zone ? ' · ' + esc(st.zone === 'none' ? 'baholanmagan' : ZONE_C[st.zone][1].toLowerCase()) : ''}`, 'people')}
      <span class="hint">bir xonadonda 2+ talaba: <b>${list.filter(f => f.length > 1).length}</b></span></header>
    ${list.length ? `<div class="tbl-wrap" style="max-height:520px"><table class="tbl"><thead><tr><th>Manzil</th><th>Tuman</th><th>Talabalar</th><th>Toifa</th><th></th></tr></thead><tbody>
      ${list.map(f => { const z = f.find(x => x.zone); return `<tr><td>${esc(f[0].address || '—')}${f[0].holat === 'ok' && f[0].aniqlik !== 'aniq' ? ' <span class="chip warn">taxminiy</span>' : f[0].holat !== 'ok' ? ` <span class="chip muted">${f[0].holat === 'navbatda' ? 'aniqlanmoqda' : f[0].holat === 'manzilsiz' ? 'manzil yo‘q' : 'xaritada topilmadi'}</span>` : ''}</td>
        <td>${esc(f[0].tuman || '—')}</td><td>${f.map(x => `<a href="#/student/${x.id}">${esc(shortName(x.name))}</a> <span class="sub-l" style="display:inline">${esc(x.group)}</span>`).join('<br>')}</td>
        <td>${z ? `<span class="zchip z-${z.zone}">${ZONE_C[z.zone][1]}</span>` : '<span class="dash">—</span>'}</td><td>${f.length > 1 ? `<span class="chip info">${f.length} talaba</span>` : ''}</td></tr>`; }).join('')}</tbody></table></div>`
      : `<div class="pad">${emptyBox('home', 'Xonadon yo‘q', 'Talabalar kartasida yashash joyi «Ijara xonadonida» bo‘lsa va manzili kiritilgan bo‘lsa — shu yerda chiqadi.')}</div>`}
    ${miss.length ? `<p class="hint pad" style="margin:0">${ic('info')} Xaritada yo‘q: ${miss.length} ta — talaba kartasida «Xaritadagi joyi» ni ko‘rsating (koordinata, xarita havolasi yoki xaritadan tanlash).</p>` : ''}</section>`;
}
let homesMap = null;
async function loadHomesMap(d, shapes, st, fit = false) {
  const box = $('#hmap'); if (!box) return;
  try { await loadLeaflet(); } catch (e) { box.innerHTML = emptyBox('map', 'Xarita yuklanmadi', 'Internet ulanishini tekshiring.'); return; }
  if (!homesMap || homesMap.getContainer() !== box) {
    if (homesMap) { try { homesMap.remove(); } catch (_) { /* */ } }
    homesMap = baseMap(box, d.center, 11.5);
    homesMap._v = L.layerGroup().addTo(homesMap);
    const counts = {};
    d.items.filter(x => x.living === 'ijara').forEach(x => { counts[x.tuman] = counts[x.tuman] || {}; if (x.zone) counts[x.tuman][x.zone] = (counts[x.tuman][x.zone] || 0) + 1; });
    (shapes || []).forEach(t => {
      const c = counts[t.nom] || {}, top = Object.entries(c).sort((a, b) => b[1] - a[1])[0];
      L.polygon(t.chegara, { color: '#5B6B86', weight: 1, fillColor: top ? ZONE_C[top[0]][0] : '#5B6B86', fillOpacity: top ? 0.10 : 0.03 }).bindTooltip(t.nom, { sticky: true }).addTo(homesMap);
    });
    fit = true;
  }
  const layer = homesMap._v; layer.clearLayers();
  const groups = {};
  homesFiltered(d, st).filter(x => x.holat === 'ok').forEach(x => { const k = x.bino || `${x.lat.toFixed(5)},${x.lon.toFixed(5)}`; (groups[k] = groups[k] || []).push(x); });
  const pts = [];
  Object.values(groups).forEach(g => {
    const z = (g.find(x => x.zone) || {}).zone, color = z ? ZONE_C[z][0] : g[0].living === 'ttj' ? '#1F6FB2' : g[0].living === 'ijara' ? '#5B6B86' : '#7A6A9A';
    const p = [g[0].lat, g[0].lon]; pts.push(p);
    L.marker(p, { icon: numIcon(g.length, color, g[0].aniqlik !== 'aniq') }).bindPopup(`<b>${esc(g[0].address || 'Manzil')}</b><br><span style="color:#5B6B86">${esc(g[0].tuman || '')}${z ? ' · ' + ZONE_C[z][1] + ' hudud' : ''}${g[0].aniqlik !== 'aniq' ? ' · joy taxminiy' : ''}</span><br>`
      + g.map(x => `<a href="#/student/${x.id}">${esc(x.name)}</a> <small>${esc(x.group)}</small>`).join('<br>'), { maxWidth: 320 }).addTo(layer);
  });
  if (fit && pts.length) homesMap.fitBounds(L.latLngBounds(pts).pad(0.15), { maxZoom: 15 });
  setTimeout(() => homesMap && homesMap.invalidateSize(), 60);
}

/* ---------------------------------------------------------------- hisobot */
async function loadReport(box, st) {
  const t = new Date(), y = t.getMonth() >= 8 ? t.getFullYear() : t.getFullYear() - 1;
  st.rep = st.rep || { from: `${y}-09-01`, to: isoD(new Date(t.getFullYear(), t.getMonth() + 1, 0)) };
  let r;
  try { r = await api(`/api/staff/visits/report?from=${st.rep.from}&to=${st.rep.to}`); } catch (e) { box.innerHTML = emptyBox('alert', 'Hisobotni yuklab bo‘lmadi'); return; }
  const types = Object.entries(VT);
  box.innerHTML = `<div class="toolbar"><label class="inline-f">Davr <input class="input sm" type="date" data-rf value="${r.from}"> — <input class="input sm" type="date" data-rt value="${r.to}"></label>
      <div class="seg">${[['m', 'Shu oy'], ['p', 'O‘tgan oy'], ['y', 'O‘quv yili']].map(([k, l]) => `<button data-rp="${k}">${l}</button>`).join('')}</div></div>
    <p class="hint">${ic('info')} Hisobotga faqat <b>tasdiqlangan</b> va <b>o‘tkazilgan</b> rejalar kiradi — qoralama va tasdiqlanmaganlar sanalmaydi.</p>
    <section class="kpis k3">${kpi({ icon: 'cal', c: 'people', label: 'Aktual rejalar', value: r.total, unit: 'ta', sub: `o‘tkazilgan: <b>${r.done}</b>` })}
      ${types.map(([k, v]) => kpi({ icon: v.icon, c: k === 'ijara_tashrifi' ? 'att' : k === 'tadbir' ? 'msg' : k === 'madaniy_tashrif' ? 'gpa' : 'acad', label: v.t, value: r.by_type[k].plans, unit: 'ta', sub: `o‘tkazilgan: <b>${r.by_type[k].done}</b>` })).join('')}
      ${kpi({ icon: 'file', c: 'money2', label: 'Ijara tashriflari', value: r.students, unit: 'talaba', sub: `dalolatnomalar: <b>${r.acts}</b>` })}</section>
    <section class="sec"><header>${H('users', 'Koordinatorlar kesimida', 'people')}</header>${r.coordinators.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Kurs koordinatori</th><th class="r">Jami</th>${types.map(([, v]) => `<th class="r">${esc(v.s)}</th>`).join('')}<th class="r">O‘tkazilgan</th><th class="r">Talabalar</th><th class="r">Dalolatnoma</th></tr></thead><tbody>
      ${r.coordinators.map(c => `<tr><td><b>${esc(c.name || '—')}</b></td><td class="r"><b>${c.plans}</b></td>${types.map(([k]) => `<td class="r">${c[k] || '<span class="dash">0</span>'}</td>`).join('')}<td class="r">${c.done}</td><td class="r">${c.students}</td><td class="r">${c.acts}</td></tr>`).join('')}</tbody></table></div>` : `<div class="pad">${emptyBox('chart', 'Bu davrda aktual reja yo‘q')}</div>`}</section>
    ${r.months.length ? `<section class="sec" style="margin-top:18px"><header>${H('chart', 'Oylar bo‘yicha', 'att')}</header><div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Oy</th>${types.map(([, v]) => `<th class="r">${esc(v.s)}</th>`).join('')}</tr></thead><tbody>
      ${r.months.map(m => `<tr><td>${MONTHS[Number(m.month.slice(5)) - 1]} ${m.month.slice(0, 4)}</td>${types.map(([k]) => `<td class="r">${m[k] || '<span class="dash">0</span>'}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>` : ''}
    <section class="sec" style="margin-top:18px"><header>${H('file', 'Rejalar', 'acad')}</header>${r.items.length ? `<div class="tbl-wrap" style="max-height:none"><table class="tbl"><thead><tr><th>Sana</th><th>Turi</th><th>Nomi</th><th>Koordinator</th><th>Holat</th><th class="r">Talaba</th></tr></thead><tbody>
      ${r.items.map(p => `<tr class="click" data-vp="${p.id}"><td class="nowrap">${dmy(p.visit_date)} ${esc(p.start_time)}</td><td>${tChip(p.type)}</td><td>${esc(p.title)}</td><td>${esc(p.coordinator_name || '')}</td><td>${vChip(p.status)}</td><td class="r">${p.students.length || ''}</td></tr>`).join('')}</tbody></table></div>` : `<div class="pad"><span class="dash">Yo‘q</span></div>`}</section>`;
  const set = (f, t_) => { st.rep = { from: f, to: t_ }; loadReport(box, st); };
  $('[data-rf]', box).addEventListener('change', e => set(e.target.value, st.rep.to));
  $('[data-rt]', box).addEventListener('change', e => set(st.rep.from, e.target.value));
  $$('[data-rp]', box).forEach(b => b.addEventListener('click', () => {
    const n = new Date();
    if (b.dataset.rp === 'm') set(isoD(new Date(n.getFullYear(), n.getMonth(), 1)), isoD(new Date(n.getFullYear(), n.getMonth() + 1, 0)));
    else if (b.dataset.rp === 'p') set(isoD(new Date(n.getFullYear(), n.getMonth() - 1, 1)), isoD(new Date(n.getFullYear(), n.getMonth(), 0)));
    else set(`${y}-09-01`, `${y + 1}-08-31`); }));
  bindPlanCards(box);
}

/* ================================================================ dalolatnoma: ma'lumot modeli */
const ACT_Q = [
  { k: 'contract', no: 6, label: 'Ijara huquqi (shartnoma) asosida yashayotganligi', opts: [['bor', 'Ijara shartnomasi mavjud'], ['yoq', 'Ijara shartnomasi mavjud emas']] },
  { k: 'loc', no: 7, label: 'Ijara xonadoni oliy ta’lim tashkilotiga kelib-ketishi uchun qulay lokatsiyada joylashganligi', opts: [['qulay', 'qulay'], ['noqulay', 'noqulay']] },
  { k: 'climate', no: 8, label: 'Xonadondagi ijarachilar o‘rtasida o‘zaro muhit barqarorligi', opts: [['qoniqarsiz', 'qoniqarsiz'], ['qoniqarli', 'qoniqarli'], ['yaxshi', 'yaxshi']] },
  { k: 'study', no: 9, label: 'Dars mashg‘ulotlariga tayyorlanish uchun sharoit mavjudligi', opts: [['ha', 'ha'], ['yoq', 'yo‘q']] },
  { k: 'air', no: 10, label: 'Xonaning havo almashtirish uchun qulayligi (tashqi deraza mavjudligi)', opts: [['ha', 'ha'], ['yoq', 'yo‘q']] },
  { k: 'safety', no: 11, label: 'Ijara xonadonida mavjud gaz plitasi, suv quvurlari, isitish tizimi, yong‘in xavfsizligi talablariga javob berishi', opts: [['ha', 'ha'], ['yoq', 'yo‘q']] },
  { k: 'bed', no: 12, label: 'Talabaga ajratilgan yotoq joyi va holati', opts: [['xona', 'xona'], ['oshxona', 'oshxona'], ['balkon', 'balkon (ayvon)']] },
  { k: 'common', no: 13, label: 'Xonadonning umumiy yuvinish xonasi, hojatxona, oshxonaning holati', opts: [['qoniqarsiz', 'qoniqarsiz'], ['qoniqarli', 'qoniqarli'], ['yaxshi', 'yaxshi']] },
  { k: 'category', no: 14, label: 'Kurs koordinatori xulosasi: (Bunda xonadon qaysi toifaga kirishi ko‘rsatiladi)', opts: [['qizil', 'qizil'], ['sariq', 'sariq'], ['yashil', 'yashil']] }
];
const ACT_BY_K = Object.fromEntries(ACT_Q.map(q => [q.k, q]));
const UNIVERSITY = 'JAHON IQTISODIYOTI VA DIPLOMATIYA UNIVERSITETI';
function actProfile(p) { return { name: p.coordinator_name || '', university: UNIVERSITY, faculty: '', course: '' }; }
function actFromStudent(s, p) {
  return { studentId: s.student_id, fio: s.full_name, group: s.group_name || '', course: s.course ? String(s.course) : '',
    faculty: s.faculty || '', phone: s.phone ? fmtPhone(s.phone) : '', address: s.address || '' };
}

/* ---------------------------------------------------------------- dalolatnoma tahriri */
function openActEditor(p, act) {
  const isNew = !act;
  const a = act ? { ...act.data, studentId: act.student_id || '' } : { studentId: '', fio: '', group: '', course: '', faculty: '', phone: '', address: '', owner: '', ownerPhone: '', coresidents: '',
    contract: '', loc: '', climate: '', study: '', air: '', safety: '', bed: '', common: '', category: '', problems: String(p.problem || '').trim(), advice: '' };
  const Pf = actProfile(p);
  const dl = el('dialog', { class: 'vdlg vact' });
  const used = new Set((p.acts || []).filter(x => !act || x.id !== act.id).map(x => x.student_id));
  const sSel = el('select', { class: 'select', onchange: e => { const s = p.students.find(x => x.student_id === Number(e.target.value)); if (s) { Object.assign(a, actFromStudent(s, p)); fill(); } } },
    el('option', { value: '', text: '— talabani tanlang —' }),
    p.students.map(s => el('option', { value: s.student_id, selected: Number(a.studentId) === s.student_id, text: `${s.full_name}${used.has(s.student_id) ? ' (dalolatnoma bor)' : ''}` })));
  const f = {};
  const fld = (lb, k, ph, ta) => el('label', { class: 'field' }, el('span', { text: lb }),
    f[k] = el(ta ? 'textarea' : 'input', { class: ta ? 'textarea' : 'input', rows: ta ? 2 : null, placeholder: ph || '', oninput: e => { a[k] = e.target.value; fitSoon(); } }));
  const fill = () => Object.entries(f).forEach(([k, n]) => { n.value = a[k] || ''; });
  const fitWarn = el('div', { class: 'note warn', hidden: true, html: `${ic('alert')}<span>Matn juda uzun: dalolatnoma eng kichik shriftda ham bitta betga sig‘maydi. «Birga yashovchilar», kamchilik va tavsiyalarni qisqaroq yozing.</span>` });
  let fitT = null;
  const fitSoon = () => { clearTimeout(fitT); fitT = setTimeout(() => { fitWarn.hidden = actFits({ ...a, _dateText: dmy(p.visit_date) }, Pf); }, 350); };
  const warn = el('div', { class: 'hint' });
  const upd = () => { const miss = ACT_Q.filter(q => !a[q.k]).length;
    warn.textContent = miss ? `${miss} ta band belgilanmagan — ular dalolatnomada bo‘sh qoladi.` : 'Barcha bandlar belgilandi.';
    warn.style.color = miss ? 'var(--warn)' : 'var(--ok)'; };
  const qBox = q => el('div', { class: 'qrow' }, el('span', { class: 'qn', text: q.no }),
    el('div', { style: 'min-width:0' }, el('div', { class: 'ql', text: q.label }),
      el('div', { class: 'qopts' + (q.k === 'category' ? ' zonebox' : '') }, q.opts.map(([v, t]) => el('label', { class: 'qopt', style: q.k === 'category' ? `--c:${ZONE_C[v][0]}` : null },
        el('input', { type: 'radio', name: 'q_' + q.k, value: v, checked: a[q.k] === v, onchange: () => { a[q.k] = v; upd(); } }), el('span', { text: t }))))));
  const signSlot = (key, title, who) => {
    const prev = el('div', { class: 'sb-prev' }), btns = el('div', { class: 'wrapc' });
    const draw = () => {
      prev.replaceChildren(sigValid(a[key]) ? sigCanvas(a[key], 196, 80) : el('span', { class: 'sb-empty', text: 'Imzo qo‘yilmagan' }));
      fillKids(btns, el('button', { class: 'btn sm primary', type: 'button', onclick: async () => { const s = await signaturePad(title, who()); if (s) { a[key] = s; draw(); } }, html: ic('pen') + (sigValid(a[key]) ? ' Qayta imzolash' : ' Imzo qo‘yish') }),
        sigValid(a[key]) ? el('button', { class: 'btn sm ghost', type: 'button', onclick: () => { delete a[key]; draw(); } }, 'O‘chirish') : null);
    };
    draw();
    return el('div', { class: 'signbox' }, el('b', { text: title }), el('span', { class: 'who', text: who() || '—' }), prev, btns);
  };
  const err = el('div', { class: 'note bordo', hidden: true });
  const save = async () => {
    err.hidden = true;
    try {
      const r = await api(`/api/staff/visits/${p.id}/acts${act ? '/' + act.id : ''}`, { method: 'POST', json: a });
      dl.close(); toast(isNew ? 'Dalolatnoma qo‘shildi' : 'Dalolatnoma saqlandi');
      if (await confirmDlg('Word fayl', 'Dalolatnomaning Word faylini (bir bet, imzolar bilan) hozir yasab, talaba hujjati sifatida saqlaymi?', 'Ha, yasash')) {
        try { await saveActDocx(p, r.act, true); } catch (e) { console.error(e); toast('Word faylni yasab bo‘lmadi', true); }
      }
      openPlan(p.id);
    } catch (e) { err.textContent = verr(e); err.hidden = false; }
  };
  dl.append(el('form', { method: 'dialog', class: 'wide', onsubmit: e => e.preventDefault() },
    el('h3', { text: isNew ? 'Yangi dalolatnoma' : 'Dalolatnomani tahrirlash' }),
    el('p', { text: `O‘rganish sanasi: ${dLong(p.visit_date)} — tashrif sanasidan olinadi. Mas’ul: ${Pf.name || '—'} (kurs koordinatori).` }),
    el('label', { class: 'field' }, el('span', { text: '2. Talaba' }), sSel),
    el('div', { class: 'cols3' }, fld('Guruh', 'group'), fld('Kurs', 'course'), fld('Fakultet', 'faculty')),
    fld('3. Ijarada yashash manzili', 'address', 'Tuman, mavze, ko‘cha, uy, xonadon'), fld('Talabaning shaxsiy telefon raqami', 'phone'),
    el('div', { class: 'cols2' }, fld('4. Xonadon egasi (F.I.Sh.)', 'owner'), fld('Xonadon egasi telefoni', 'ownerPhone')),
    fld('5. Ijarada birga yashovchilar', 'coresidents', 'F.I.Sh., o‘qish yoki ish joyi, lavozimi', true),
    el('div', { class: 'qlist' }, ACT_Q.map(qBox)),
    fld('15. Aniqlangan kamchilik va muammolar', 'problems', '', true),
    fld('16. Muammolarni bartaraf etish yuzasidan tavsiyalar', 'advice', '', true),
    el('div', { class: 'field' }, el('span', { text: 'Imzolar' }), el('div', { class: 'signs' },
      signSlot('sigCoord', 'Mas’ul (kurs koordinatori)', () => Pf.name), signSlot('sigStudent', 'Talaba', () => a.fio)),
    el('span', { class: 'hint', text: 'Telefon (yoki planshet) ekraniga barmoq bilan imzo chiziladi. Qanchalik katta yoki kichik chizilmasin, faylda imzo qog‘ozdagi oddiy imzo kattaligida chiqadi. Imzo qo‘yilmasa — faylda qo‘lda imzolash uchun bo‘sh chiziq qoladi.' })),
    fitWarn, warn, err,
    el('div', { class: 'row' }, el('button', { class: 'btn', type: 'button', onclick: () => dl.close() }, 'Bekor qilish'),
      el('button', { class: 'btn primary', type: 'button', onclick: save }, 'Saqlash'))));
  document.body.append(dl);
  dl.addEventListener('close', () => dl.remove());
  fill(); upd(); fitSoon();
  dl.showModal();
}

/* ---------------------------------------------------------------- imzo (tashrif-py: vektor ko'rinishida saqlanadi) */
const SIG_W_CM = 2.8, SIG_H_CM = 1.3, SIG_INK = '#1F3A8A', SIG_PEN_CM = 0.045;
const sigValid = s => !!(s && s.d && s.w > 0 && s.h > 0);
function sigPack(strokes) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  strokes.forEach(st => st.forEach(([x, y]) => { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }));
  const bw = x1 - x0, bh = y1 - y0;
  if (!isFinite(bw) || Math.max(bw, bh) < 14) return null;        // nuqta yoki tasodifiy tegish — imzo emas
  const s = Math.max(bw, bh) / 1000;
  return { w: Math.max(1, Math.round(bw / s)), h: Math.max(1, Math.round(bh / s)),
    d: strokes.map(st => st.map(([x, y]) => `${Math.round((x - x0) / s)},${Math.round((y - y0) / s)}`).join(' ')).join(';') };
}
const sigStrokes = s => s.d.split(';').map(st => st.split(' ').map(p => p.split(',').map(Number)));
function sigDraw(ctx, s, W, H, lw) {
  const k = Math.min((W - 2 * lw) / s.w, (H - 2 * lw) / s.h), ox = (W - s.w * k) / 2, oy = (H - s.h * k) / 2;
  ctx.strokeStyle = ctx.fillStyle = SIG_INK; ctx.lineWidth = lw; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  sigStrokes(s).forEach(st => {
    const p = st.map(([x, y]) => [ox + x * k, oy + y * k]);
    if (p.length === 1) { ctx.beginPath(); ctx.arc(p[0][0], p[0][1], lw / 2, 0, Math.PI * 2); ctx.fill(); return; }
    ctx.beginPath(); ctx.moveTo(p[0][0], p[0][1]);
    for (let i = 1; i < p.length - 1; i++) ctx.quadraticCurveTo(p[i][0], p[i][1], (p[i][0] + p[i + 1][0]) / 2, (p[i][1] + p[i + 1][1]) / 2);
    ctx.lineTo(p[p.length - 1][0], p[p.length - 1][1]); ctx.stroke();
  });
}
function sigCanvas(s, W, H) {
  const dpr = Math.min(3, window.devicePixelRatio || 1);
  const c = el('canvas', { width: Math.round(W * dpr), height: Math.round(H * dpr), style: `width:${W}px;height:${H}px`, 'aria-label': 'Imzo' });
  const ctx = c.getContext('2d'); ctx.scale(dpr, dpr); sigDraw(ctx, s, W, H, 2.2);
  return c;
}
async function sigPng(s) {                       // faylga: namunadagi imzo qutisiga sig'adigan o'lchamda
  const PX = 300, wide = s.w / s.h >= SIG_W_CM / SIG_H_CM;
  const wCm = Math.max(0.4, wide ? SIG_W_CM : SIG_H_CM * s.w / s.h), hCm = Math.max(0.4, wide ? SIG_W_CM * s.h / s.w : SIG_H_CM);
  const c = document.createElement('canvas'); c.width = Math.round(wCm * PX); c.height = Math.round(hCm * PX);
  sigDraw(c.getContext('2d'), s, c.width, c.height, SIG_PEN_CM * PX);
  const blob = await new Promise((ok, bad) => c.toBlob(b => (b ? ok(b) : bad(new Error('png'))), 'image/png'));
  return { bytes: new Uint8Array(await blob.arrayBuffer()), cx: Math.round(wCm * 360000), cy: Math.round(hCm * 360000) };
}
function signaturePad(title, who) {             // butun ekranli imzo oynasi → imzo yoki null
  return new Promise(resolve => {
    const strokes = []; let cur = null, dpr = 1;
    const cv = el('canvas', {}), ctx = cv.getContext('2d');
    const hint = el('div', { class: 'sp-hint', text: 'Chiziq ustiga barmog‘ingiz (yoki sichqoncha) bilan imzo chizing' });
    const area = el('div', { class: 'sp-area' }, el('div', { class: 'sp-line' }), hint, cv);
    const saveBtn = el('button', { class: 'btn primary', type: 'button', disabled: true }, 'Imzoni saqlash');
    const pen = () => { ctx.strokeStyle = ctx.fillStyle = SIG_INK; ctx.lineWidth = 3.2; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; };
    const redraw = () => { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, cv.width, cv.height); pen();
      strokes.forEach(st => { ctx.beginPath(); ctx.moveTo(st[0][0], st[0][1]);
        if (st.length === 1) { ctx.arc(st[0][0], st[0][1], 1.6, 0, Math.PI * 2); ctx.fill(); return; }
        st.slice(1).forEach(([x, y]) => ctx.lineTo(x, y)); ctx.stroke(); }); };
    const fit = () => { const r = area.getBoundingClientRect(); dpr = Math.min(3, window.devicePixelRatio || 1);
      cv.width = Math.max(1, Math.round(r.width * dpr)); cv.height = Math.max(1, Math.round(r.height * dpr)); redraw(); };
    const at = e => { const r = cv.getBoundingClientRect(); return [Math.round((e.clientX - r.left) * 10) / 10, Math.round((e.clientY - r.top) * 10) / 10]; };
    const refresh = () => { saveBtn.disabled = !sigPack(strokes); hint.hidden = strokes.length > 0; };
    cv.addEventListener('pointerdown', e => { e.preventDefault(); try { cv.setPointerCapture(e.pointerId); } catch (err) { /* */ }
      cur = [at(e)]; strokes.push(cur); pen(); ctx.beginPath(); ctx.arc(cur[0][0], cur[0][1], 1.6, 0, Math.PI * 2); ctx.fill(); refresh(); });
    cv.addEventListener('pointermove', e => { if (!cur) return; e.preventDefault();
      const evs = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
      pen(); ctx.beginPath(); ctx.moveTo(cur[cur.length - 1][0], cur[cur.length - 1][1]);
      (evs.length ? evs : [e]).forEach(ev => { const p = at(ev), q = cur[cur.length - 1]; if (Math.hypot(p[0] - q[0], p[1] - q[1]) < 1.5) return; cur.push(p); ctx.lineTo(p[0], p[1]); });
      ctx.stroke(); });
    const end = () => { if (cur) { cur = null; refresh(); } };
    cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
    const d = el('dialog', { class: 'sigpad', 'aria-label': title });
    const finish = r => { window.removeEventListener('resize', fit); if (d.open) d.close(); d.remove(); resolve(r); };
    d.addEventListener('cancel', e => { e.preventDefault(); finish(null); });
    saveBtn.addEventListener('click', () => { const s = sigPack(strokes); if (s) finish(s); });
    d.append(el('div', { class: 'sp-head' }, el('b', { text: title + (who ? ' — ' + who : '') }), el('button', { class: 'btn sm ghost', type: 'button', onclick: () => finish(null) }, 'Yopish')),
      area, el('div', { class: 'sp-foot' }, el('button', { class: 'btn', type: 'button', onclick: () => { strokes.length = 0; cur = null; redraw(); refresh(); } }, 'Tozalash'),
        el('span', { class: 'sp-gap' }), el('span', { class: 'hint', text: 'Istalgan kattalikda chizing — faylda imzo qog‘ozdagi oddiy imzo o‘lchamida chiqadi.' }), saveBtn));
    document.body.append(d); d.showModal();
    window.addEventListener('resize', fit); requestAnimationFrame(fit);
  });
}

/* ---------------------------------------------------------------- Word (OOXML) — tashrif-py dan */
const XE = v => String(v == null ? '' : v).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
function wRun(text, o = {}) {
  const rPr = (o.font ? `<w:rFonts w:ascii="${o.font}" w:hAnsi="${o.font}" w:eastAsia="${o.font}" w:cs="${o.font}"/>` : '') + (o.b ? '<w:b/><w:bCs/>' : '') + (o.i ? '<w:i/><w:iCs/>' : '') + (o.color ? `<w:color w:val="${o.color}"/>` : '') + (o.spacing ? `<w:spacing w:val="${o.spacing}"/>` : '') + (o.sz ? `<w:sz w:val="${o.sz}"/><w:szCs w:val="${o.sz}"/>` : '');
  const body = String(text == null ? '' : text).split('\n').map(t => `<w:t xml:space="preserve">${XE(t)}</w:t>`).join('<w:br/>');
  return `<w:r>${rPr ? `<w:rPr>${rPr}</w:rPr>` : ''}${body}</w:r>`;
}
function wPara(runs, o = {}) {
  const sp = (o.before != null || o.after != null || o.line) ? `<w:spacing${o.before != null ? ` w:before="${o.before}"` : ''}${o.after != null ? ` w:after="${o.after}"` : ''}${o.line ? ` w:line="${o.line}" w:lineRule="auto"` : ''}/>` : '';
  const pPr = (o.style ? `<w:pStyle w:val="${o.style}"/>` : '') + (o.keepNext ? '<w:keepNext/>' : '') + (o.pageBreak ? '<w:pageBreakBefore/>' : '') + sp + (o.jc ? `<w:jc w:val="${o.jc}"/>` : '');
  return `<w:p>${pPr ? `<w:pPr>${pPr}</w:pPr>` : ''}${Array.isArray(runs) ? runs.join('') : runs}</w:p>`;
}
function wTable(widths, rows, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0), bd = o.noBorder ? 'none' : 'single';
  const line = side => `<w:${side} w:val="${bd}" w:sz="4" w:space="0" w:color="${o.noBorder ? 'auto' : '6B6B6B'}"/>`;
  const tblPr = `<w:tblPr><w:tblW w:w="${total}" w:type="dxa"/><w:tblInd w:w="0" w:type="dxa"/><w:tblBorders>${['top', 'left', 'bottom', 'right', 'insideH', 'insideV'].map(line).join('')}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="${o.pad != null ? o.pad : 45}" w:type="dxa"/><w:left w:w="85" w:type="dxa"/><w:bottom w:w="${o.pad != null ? o.pad : 45}" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar></w:tblPr>`;
  const grid = `<w:tblGrid>${widths.map(w => `<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>`;
  const trs = rows.map(r => {
    let gi = 0; r.cells.forEach(c => { c._gi = gi; gi += c.span || 1; });
    const tcs = r.cells.map((c, i) => {
      const shade = r.shade || c.shade, span = c.span || 1;
      let wsum = 0; for (let k = 0; k < span; k++) wsum += widths[(c._gi != null ? c._gi : i) + k] || 0;
      const tcPr = `<w:tcPr><w:tcW w:w="${wsum}" w:type="dxa"/>${span > 1 ? `<w:gridSpan w:val="${span}"/>` : ''}${shade ? `<w:shd w:val="clear" w:color="auto" w:fill="${shade}"/>` : ''}<w:vAlign w:val="${c.va || (o.noBorder ? 'bottom' : 'center')}"/></w:tcPr>`;
      const paras = c.xml != null ? [c.xml] : String(c.text == null ? '' : c.text).split('\n\n').map(t => wPara(wRun(t, { b: c.b || r.header, sz: c.sz }), { style: o.cellStyle || 'ActCell', jc: c.jc || (r.header ? 'center' : 'left') }));
      return `<w:tc>${tcPr}${paras.join('')}</w:tc>`;
    }).join('');
    return `<w:tr><w:trPr><w:cantSplit/>${r.header ? '<w:tblHeader/>' : ''}</w:trPr>${tcs}</w:tr>`;
  }).join('');
  return `<w:tbl>${tblPr}${grid}${trs}</w:tbl>`;
}
const W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';
const A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main';
const DOC_NS = W_NS + ` xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="${A_NS}" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"`;
const TWIP = 635;
function wDrawing(id, name, file, rid, cx, cy, descr) {
  return `<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>` +
    `<wp:docPr id="${id}" name="${XE(name)}" descr="${XE(descr || '')}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="${A_NS}" noChangeAspect="1"/></wp:cNvGraphicFramePr>` +
    `<a:graphic xmlns:a="${A_NS}"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">` +
    `<pic:nvPicPr><pic:cNvPr id="${id}" name="${file}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="${rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>` +
    `<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>`;
}
function wImage(img, maxWtw, maxHtw) {
  const maxW = maxWtw * TWIP, maxH = maxHtw * TWIP, ar = (img.h && img.w) ? img.h / img.w : 0.75;
  let cx = maxW, cy = Math.round(maxW * ar);
  if (cy > maxH) { cy = maxH; cx = Math.round(maxH / ar); }
  return `<w:p><w:pPr><w:spacing w:before="40" w:after="40"/><w:jc w:val="center"/></w:pPr>${wDrawing(img.num + 100, `Rasm ${img.num}`, img.file, img.rid, cx, cy, img.alt)}</w:p>`;
}
const XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
function stylesXml() {
  return XML_HEAD + `<w:styles ${W_NS}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="28"/><w:szCs w:val="28"/><w:lang w:val="uz-Latn-UZ" w:eastAsia="en-US" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>` +
    `<w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>` +
    `<w:style w:type="paragraph" w:customStyle="1" w:styleId="ActCell"><w:name w:val="Dalolatnoma katagi"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style></w:styles>`;
}
const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(buf) { let c = 0xFFFFFFFF; for (let i = 0; i < buf.length; i++) c = CRC_T[(c ^ buf[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
function zipStore(files, mime) {
  const enc = new TextEncoder(), parts = [], central = [];
  let offset = 0;
  const d = new Date(), dosTime = ((d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1)) & 0xFFFF, dosDate = (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF;
  for (const f of files) {
    const nm = enc.encode(f.name), data = f.data instanceof Uint8Array ? f.data : enc.encode(f.data), crc = crc32(data);
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true); lh.setUint16(10, dosTime, true); lh.setUint16(12, dosDate, true);
    lh.setUint32(14, crc, true); lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true); lh.setUint16(26, nm.length, true); lh.setUint16(28, 0, true);
    parts.push(new Uint8Array(lh.buffer), nm, data);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true); ch.setUint16(12, dosTime, true); ch.setUint16(14, dosDate, true);
    ch.setUint32(16, crc, true); ch.setUint32(20, data.length, true); ch.setUint32(24, data.length, true); ch.setUint16(28, nm.length, true);
    ch.setUint16(30, 0, true); ch.setUint16(32, 0, true); ch.setUint16(34, 0, true); ch.setUint16(36, 0, true); ch.setUint32(38, 0, true); ch.setUint32(42, offset, true);
    central.push(new Uint8Array(ch.buffer), nm);
    offset += 30 + nm.length + data.length;
  }
  const cdSize = central.reduce((a, p) => a + p.length, 0), end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(4, 0, true); end.setUint16(6, 0, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
  end.setUint32(12, cdSize, true); end.setUint32(16, offset, true); end.setUint16(20, 0, true);
  return new Blob([...parts, ...central, new Uint8Array(end.buffer)], { type: mime });
}
function packDocx(docXml, imgs, title, creator) {
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const imgRels = imgs.map(im => `<Relationship Id="${im.rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/${im.file}"/>`).join('');
  return zipStore([
    { name: '[Content_Types].xml', data: XML_HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="jpeg" ContentType="image/jpeg"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>' },
    { name: '_rels/.rels', data: XML_HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>' },
    { name: 'word/_rels/document.xml.rels', data: XML_HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>' + imgRels + '</Relationships>' },
    { name: 'word/document.xml', data: docXml },
    ...imgs.map(im => ({ name: `word/media/${im.file}`, data: im.bytes })),
    { name: 'word/styles.xml', data: stylesXml() },
    { name: 'word/settings.xml', data: XML_HEAD + `<w:settings ${W_NS}><w:zoom w:percent="100"/><w:defaultTabStop w:val="709"/><w:characterSpacingControl w:val="doNotCompress"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>` },
    { name: 'docProps/core.xml', data: XML_HEAD + `<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${XE(title)}</dc:title><dc:creator>${XE(creator || '')}</dc:creator><dc:language>uz-Latn-UZ</dc:language><dcterms:created xsi:type="dcterms:W3CDTF">${now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">${now}</dcterms:modified></cp:coreProperties>` },
    { name: 'docProps/app.xml', data: XML_HEAD + '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Office Word</Application></Properties>' }
  ], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
}

/* ---- dalolatnoma hujjati: har doim BITTA bet (matn ko'p bo'lsa, shrift bosqichma-bosqich kichraytiriladi) ---- */
const CB = on => (on ? '☑ ' : '☐ ');
const CB_FONT = 'Segoe UI Symbol';
const ACT_MARGIN = { top: 709, bottom: 709, left: 1134, right: 851 };
const ACT_G = [420, 1420, 1260, 420, 1420, 1260, 420, 1380, 1354];
const ACT_LEVELS = [
  { sz: 20, lab: 20, opt: 20, box: 22, blank: 3 }, { sz: 20, lab: 20, opt: 20, box: 22, blank: 2 }, { sz: 20, lab: 18, opt: 19, box: 20, blank: 1 },
  { sz: 19, lab: 17, opt: 18, box: 19, blank: 1 }, { sz: 18, lab: 16, opt: 17, box: 18, blank: 1 }, { sz: 17, lab: 15, opt: 16, box: 17, blank: 1 },
  { sz: 16, lab: 14, opt: 15, box: 16, blank: 1 }, { sz: 15, lab: 13, opt: 14, box: 15, blank: 1 }, { sz: 14, lab: 12, opt: 13, box: 14, blank: 1 }];
function actRows(a, L) {
  const num = n => ({ text: String(n), jc: 'center', b: 1, sz: L.sz });
  const label = (t, o = {}) => ({ text: t, b: o.b !== false, sz: o.sz || L.sz, va: o.va });
  const paras = list => ({ paras: list.map(x => String(x || '')), sz: L.sz, va: 'top' });
  const multi = t => { const p = String(t || '').split('\n').map(x => x.trim()).filter(Boolean); return p.length ? p : Array(L.blank).fill(''); };
  const opts = (q, v, sz) => ({ opts: q.opts.map(([k, t]) => ({ on: v === k, text: t })), sz, box: L.box, va: 'center' });
  const wide = (n, lbl, value) => ({ cells: [num(n), { ...label(lbl), span: 3 }, { ...value, span: 5 }] });
  const trio = (...qs) => ({ cells: qs.flatMap(q => [num(q.no), label(q.label, { b: false, sz: L.lab, va: 'center' }), opts(q, a[q.k], L.opt)]) });
  return [
    { header: true, shade: 'F2E4E7', cells: [{ text: '№', jc: 'center', b: 1, sz: L.sz }, { text: 'Tegishli ma’lumotlar', span: 3, jc: 'center', b: 1, sz: L.sz }, { text: 'O‘rganish natijalari', span: 5, jc: 'center', b: 1, sz: L.sz }] },
    wide(1, 'O‘rganish o‘tkazilgan sana', paras([a._dateText])),
    wide(2, 'Talabaning F.I.Sh.', paras([a.fio])),
    wide(3, 'Ijarada yashash manzili\n\n(tuman, mavze, ko‘cha, uy, xonadon)\n\nShaxsiy telefon raqami', paras([a.address, a.phone])),
    wide(4, 'Xonadon egasi to‘g‘risida ma’lumot:\n\n(F.I.Sh, telefon raqami)', paras([[a.owner, a.ownerPhone].filter(Boolean).join(', ')])),
    wide(5, 'Ijarada birga yashovchilar:\n\n(F.I.Sh., o‘qish yoki ish joyi, lavozimi)', paras(multi(a.coresidents))),
    wide(6, 'Ijara huquqi (shartnoma) asosida yashayotganligi', opts(ACT_BY_K.contract, a.contract, L.sz)),
    trio(ACT_BY_K.loc, ACT_BY_K.climate, ACT_BY_K.study),
    trio(ACT_BY_K.air, ACT_BY_K.safety, ACT_BY_K.bed),
    { cells: [num(13), label(ACT_BY_K.common.label, { b: false, sz: L.lab, va: 'center' }), opts(ACT_BY_K.common, a.common, L.opt),
      num(14), label(ACT_BY_K.category.label, { sz: L.lab, va: 'center' }), { ...opts(ACT_BY_K.category, a.category, L.sz), span: 4 }] },
    wide(15, 'Aniqlangan kamchilik va muammolar:', paras(multi(a.problems))),
    wide(16, 'Aniqlangan muammolarni bartaraf etish yuzasidan tavsiyalar:', paras(multi(a.advice)))
  ];
}
function actCellXml(c) {
  const p = (runs, jc) => wPara(runs, { style: 'ActCell', jc: jc || 'left' });
  if (c.opts) return c.opts.map(o => p([wRun(CB(o.on), { font: CB_FONT, sz: c.box }), wRun(o.text, { b: o.on, sz: c.sz })])).join('');
  if (c.paras) return c.paras.map(t => p(wRun(t, { sz: c.sz }))).join('');
  return String(c.text).split('\n\n').map(t => p(wRun(t, { b: c.b, sz: c.sz }), c.jc)).join('');
}
function actTableXml(a, L) {
  return wTable(ACT_G, actRows(a, L).map(r => ({ ...r, cells: r.cells.map(c => ({ xml: actCellXml(c), span: c.span, va: c.va })) })), { cellStyle: 'ActCell', pad: 28 });
}
let actCtx = null;
function actTextW(text, sz, b) {
  if (!actCtx) actCtx = document.createElement('canvas').getContext('2d');
  actCtx.font = `${b ? 'bold ' : ''}${sz / 2}pt "Times New Roman", Tinos, "Liberation Serif", serif`;
  return actCtx.measureText(String(text)).width * 15 * 1.03;
}
function actLines(text, width, sz, b, lead = 0) {
  const avail = width - 170, sp = actTextW(' ', sz, b);
  let n = 0;
  for (const para of String(text == null ? '' : text).split('\n')) {
    let x = lead, lines = 1;
    for (const w of para.split(/\s+/).filter(Boolean)) {
      const ww = actTextW(w, sz, b);
      if (x > lead && x + sp + ww > avail) { lines++; x = 0; }
      if (ww > avail) { lines += Math.floor(ww / avail); x = ww % avail; } else x += (x > lead ? sp : 0) + ww;
    }
    n += lines;
  }
  return n;
}
const actLineH = (sz, k = 1) => sz * 10 * 1.15 * k;
function actCellH(c, width) {
  if (c.opts) { const lead = actTextW('☐', c.box) + actTextW(' ', c.sz), lh = Math.max(actLineH(c.sz), c.box * 10 * 1.33);
    return c.opts.reduce((h, o) => h + actLines(o.text, width, c.sz, o.on, lead) * lh, 0); }
  if (c.paras) return c.paras.reduce((h, t) => h + actLines(t, width, c.sz, false) * actLineH(c.sz), 0);
  return String(c.text).split('\n\n').reduce((h, t) => h + actLines(t, width, c.sz, c.b) * actLineH(c.sz), 0);
}
function actTableH(a, L) {
  return actRows(a, L).reduce((sum, r) => { let gi = 0, h = 0;
    for (const c of r.cells) { const span = c.span || 1; let w = 0; for (let k = 0; k < span; k++) w += ACT_G[gi + k]; gi += span; h = Math.max(h, actCellH(c, w)); }
    return sum + h + 2 * 28 + 15; }, 0);
}
const ACT_PHOTO_NOTE = 'Maskur dalolatnomaga tashrif jarayonidan fotolavhalar ilova qilinadi.';
const actTitle = Pf => `${(Pf.university || '').trim()} da tahsil olayotgan ijarada yashovchi talabaning yashash manzillarini o‘rganish natijalari bo‘yicha`;
function actGroupLine(a, Pf) {
  const fac = String(a.faculty || Pf.faculty || '').replace(/\s*fakulteti\s*$/i, '').trim(), crs = String(a.course || Pf.course || '').replace(/\s*-?\s*kurs\s*$/i, '').trim();
  return `${fac} fakulteti, ${crs}-kurs, ${a.group || ''}-guruh`;
}
const SIGN_LINE_TW = 680, SIGN_ROLE_TW = 3600;
function actSignH() {
  const role2 = actLines('Talaba (Ogohlantirildi va tushuntirish ishlari olib borildi):', SIGN_ROLE_TW, 22, true);
  return Math.max(actLineH(22, 1.1), SIGN_LINE_TW) + 200 + 80 + Math.max(role2 * actLineH(22, 1.1), SIGN_LINE_TW) + 200 + 20;
}
function actHeight(a, Pf, L) {
  const W = 11906 - ACT_MARGIN.left - ACT_MARGIN.right + 170;
  const headH = actLines(actTitle(Pf), W, 23, true) * actLineH(23, 1.1) + 40 + actLineH(26, 1.1) + 80 + actLines(actGroupLine(a, Pf), W, 24, true) * actLineH(24, 1.1) + 110;
  return headH + actTableH(a, L) + actLines(ACT_PHOTO_NOTE, W, 23, true) * actLineH(23, 1.1) + 60 + actSignH();
}
const ACT_USABLE = 16838 - ACT_MARGIN.top - ACT_MARGIN.bottom - 500;
const actLevel = (a, Pf) => ACT_LEVELS.find(L => actHeight(a, Pf, L) <= ACT_USABLE) || ACT_LEVELS[ACT_LEVELS.length - 1];
const actFits = (a, Pf) => ACT_LEVELS.some(L => actHeight(a, Pf, L) <= ACT_USABLE);
function wFloatSig(sig) {                       // imzo chiziq ustida «suzib» turadi — qatorni kattalashtirmaydi
  const top = SIGN_LINE_TW * TWIP + 18000 - sig.cy;
  return `<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="${251660000 + sig.docId}" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">` +
    `<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="column"><wp:align>center</wp:align></wp:positionH><wp:positionV relativeFrom="paragraph"><wp:posOffset>${top}</wp:posOffset></wp:positionV>` +
    `<wp:extent cx="${sig.cx}" cy="${sig.cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/><wp:docPr id="${sig.docId}" name="Imzo ${sig.docId}" descr="Imzo"/>` +
    `<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="${A_NS}" noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic xmlns:a="${A_NS}"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">` +
    `<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="${sig.docId}" name="${sig.file}"/><pic:cNvPicPr/></pic:nvPicPr>` +
    `<pic:blipFill><a:blip r:embed="${sig.rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${sig.cx}" cy="${sig.cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>` +
    `</pic:pic></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>`;
}
function signRows(blocks) {
  const p = (inner, o = {}) => `<w:p><w:pPr>${o.end ? '' : '<w:keepNext/>'}${o.rule ? '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/></w:pBdr>' : ''}` +
    `<w:spacing w:before="${o.before || 0}" w:after="0"${o.exact ? ` w:line="${o.exact}" w:lineRule="exact"` : ''}/><w:jc w:val="${o.jc || 'center'}"/></w:pPr>${inner}</w:p>`;
  const rows = blocks.map(({ role, name, sig }, i) => {
    const before = i ? 80 : 0, end = i === blocks.length - 1, cap = t => p(wRun(t, { sz: 16, i: 1 }), { exact: 200, end });
    return { cells: [{ xml: p(wRun(role + ':', { b: 1, sz: 22 }), { jc: 'left', before }) + cap(' ') },
      { xml: p(sig ? wFloatSig(sig) : '', { rule: true, exact: SIGN_LINE_TW, before }) + cap('(imzo)') },
      { xml: p(wRun(name || ' ', { sz: 22 }), { rule: true, exact: SIGN_LINE_TW, before }) + cap('(F.I.Sh.)') }] };
  });
  return wTable([SIGN_ROLE_TW, 2600, 3700], rows, { noBorder: true, pad: 0 }) +
    '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/><w:rPr><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr></w:pPr></w:p>';
}
function buildActsXml(acts, Pf, imgsByAct, sigsByAct) {
  const B = [];
  acts.forEach((a, idx) => {
    const L = actLevel(a, Pf);
    B.push(wPara(wRun(actTitle(Pf), { b: 1, sz: 23 }), { jc: 'center', after: 40, pageBreak: idx > 0 }));
    B.push(wPara(wRun('DALOLATNOMA', { b: 1, sz: 26, spacing: 20 }), { jc: 'center', after: 80 }));
    B.push(wPara(wRun(actGroupLine(a, Pf), { b: 1, sz: 24 }), { jc: 'center', after: 110 }));
    B.push(actTableXml(a, L));
    B.push(wPara(wRun(ACT_PHOTO_NOTE, { b: 1, sz: 23 }), { before: 0, after: 60, keepNext: true }));
    const sg = (sigsByAct && sigsByAct[a._key]) || {};
    B.push(signRows([{ role: 'Mas’ul (Kurs koordinatori)', name: Pf.name || '', sig: sg.coord },
      { role: 'Talaba (Ogohlantirildi va tushuntirish ishlari olib borildi)', name: a.fio || '', sig: sg.student }]));
    const imgs = (imgsByAct && imgsByAct[a._key]) || [];
    if (imgs.length) {
      B.push(wPara(wRun(`Ilova. ${a.fio ? a.fio + ' — ' : ''}tashrif jarayonidan fotolavhalar`, { b: 1, sz: 24 }), { jc: 'center', after: 140, pageBreak: true }));
      const rws = [];
      for (let i = 0; i < imgs.length; i += 2) rws.push({ cells: [imgs[i], imgs[i + 1]].map(im => ({ xml: im ? wImage(im, 4400, 4200) + wPara(wRun(`${im.num}-rasm. ${im.capText}`, { i: 1, sz: 20 }), { jc: 'center', after: 120 }) : wPara(wRun('')) })) });
      B.push(wTable([4677, 4677], rws, { noBorder: true }));
    }
  });
  const M = ACT_MARGIN;
  return XML_HEAD + `<w:document ${DOC_NS}><w:body>${B.join('')}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="${M.top}" w:right="${M.right}" w:bottom="${M.bottom}" w:left="${M.left}" w:header="397" w:footer="397" w:gutter="0"/><w:cols w:space="708"/></w:sectPr></w:body></w:document>`;
}
/* surat — Word uchun JPEG (o'lchami bilan); PNG/WEBP ham JPEG ga o'giriladi */
async function photoJpeg(fid) {
  const blob = await (await api(`/api/staff/visits/photos/${fid}`, { raw: true })).blob();
  const bmp = await createImageBitmap(blob);
  const k = Math.min(1, 1600 / Math.max(bmp.width, bmp.height)), c = document.createElement('canvas');
  c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
  const ctx = c.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height); ctx.drawImage(bmp, 0, 0, c.width, c.height);
  const out = await new Promise((ok, bad) => c.toBlob(b => (b ? ok(b) : bad(new Error('jpeg'))), 'image/jpeg', 0.86));
  return { bytes: new Uint8Array(await out.arrayBuffer()), w: c.width, h: c.height };
}
/* dalolatnoma Word fayli: yasaladi, yuklab olinadi va (koordinatorniki bo'lsa) talaba hujjati sifatida saqlanadi */
async function saveActDocx(p, act, store = true) {
  const Pf = actProfile(p), a = { ...act.data, _key: act.id, _dateText: dmy(p.visit_date) };
  const photos = (p.photos || []).filter(f => !f.act_id || f.act_id === act.id);
  let imgs = [];
  for (const [i, f] of photos.entries()) {
    try { const j = await photoJpeg(f.id); imgs.push({ ...j, num: i + 1, rid: 'rIdImg' + (i + 1), file: `image${i + 1}.jpeg`, alt: f.name || '', capText: `${dmy(p.visit_date)}, ${p.title}` }); } catch (e) { /* o'qilmagan surat o'tkazib yuboriladi */ }
  }
  imgs = imgs.map((im, i) => ({ ...im, num: i + 1, rid: 'rIdImg' + (i + 1), file: `image${i + 1}.jpeg` }));
  const sigImgs = [], got = {};
  for (const [slot, key] of [['coord', 'sigCoord'], ['student', 'sigStudent']]) {
    if (!sigValid(a[key])) continue;
    try { const png = await sigPng(a[key]), n = sigImgs.length + 1; got[slot] = { ...png, rid: 'rIdSig' + n, file: `imzo${n}.png`, docId: 900 + n }; sigImgs.push(got[slot]); } catch (e) { /* */ }
  }
  const xml = buildActsXml([a], Pf, { [act.id]: imgs }, { [act.id]: got });
  const blob = packDocx(xml, imgs.concat(sigImgs), 'Dalolatnoma', Pf.name);
  const fn = `Dalolatnoma_${p.visit_date}${a.fio ? '_' + a.fio.split(/\s+/).slice(0, 2).join('_') : ''}.docx`.replace(/[^\w.\-Ѐ-ӿ]+/g, '_');
  const url = URL.createObjectURL(blob), link = el('a', { href: url, download: fn, style: 'display:none' });
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 4000);
  if (store) {
    try { await api(`/api/staff/visits/acts/${act.id}/docx`, { method: 'POST', body: blob }); toast('Dalolatnoma tayyor — talaba hujjati sifatida saqlandi'); }
    catch (e) { toast('Fayl yuklab olindi, lekin serverga saqlanmadi', true); }
  } else toast('Dalolatnoma tayyorlandi');
  return blob;
}
