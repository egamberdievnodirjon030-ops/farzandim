/* =====================================================================
   Ijtimoiy toifalar — nogironligi borlar, ijtimoiy himoyaga muhtojlar (ijtimoiy himoya reestri, xotin-qizlar
   reestri, ayollar daftari, temir daftar, yoshlar daftari, boshqa), chin yetimlar, mehribonlik uyi tarbiyalanuvchilari:
     • «Kurs holati» kartalari (toifa va kichik toifa bo'yicha soni) — bosilsa, ro'yxat yon panelda;
     • qo'lda belgilash — bir nechta talabaga yoki butun guruhga birdan (fayl bilan — «Ijtimoiy toifalar» importi);
     • talaba kartasida — toifalari, qo'shish va olib tashlash;
     • «Barcha kurslar» (super-admin) — umumiy karta.
   desk.js va tashrif.js dagi yordamchilardan (api, kpi, ic, esc, el, fillKids, stuPicker …) foydalanadi.
   ===================================================================== */
'use strict';

Object.assign(P, {
  heart: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/>',
  access: '<circle cx="11" cy="4" r="1.6"/><path d="M11 7.5V13h5l2.5 5.5"/><path d="M11 10h4"/><path d="M8 10.2a5.5 5.5 0 1 0 7.6 7.3"/>',
  user1: '<circle cx="12" cy="8" r="3.6"/><path d="M5 20.5a7 7 0 0 1 14 0"/>',
  homeh: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M12 18.2s-3.2-1.9-3.2-4.2a1.7 1.7 0 0 1 3.2-.8 1.7 1.7 0 0 1 3.2.8c0 2.3-3.2 4.2-3.2 4.2z"/>'
});

const SOC = {
  nogironlik: { icon: 'access', c: 'gpa', hint: 'I, II yoki III guruh' },
  ijtimoiy: { icon: 'heart', c: 'acad', hint: 'reestr, xotin-qizlar, ayollar, temir daftar…' },
  chin_yetim: { icon: 'user1', c: 'msg', hint: 'ota-onasining ikkalasi ham yo‘q' },
  mehribonlik: { icon: 'homeh', c: 'att', hint: 'mehribonlik uyi tarbiyalanuvchisi' }
};
const SOC_SRC = { fayl: 'fayldan', qolda: 'qo‘lda' };
const SOC_ERR = { bad_category: 'Toifani tanlang', bad_sub: 'Kichik toifa noto‘g‘ri', no_students: 'Kamida bitta talabani tanlang', bad_student: 'Talaba noto‘g‘ri' };
const socErr = e => (e && e.data && e.data.message) || SOC_ERR[e && e.message] || 'Bajarilmadi';

/* kartadagi qatorlar: kichik toifalar (sonli), guruhi / kichik toifasi ko'rsatilmaganlar */
function socLines(k, x, meta) {
  const subs = (meta[k] || {}).subs || {};
  const parts = Object.entries(subs).filter(([s]) => x.subs[s]).map(([s, t]) => `${esc(t)}: <b>${x.subs[s]}</b>`);
  if (x.subs[''] && Object.keys(subs).length) parts.push(`${k === 'nogironlik' ? 'guruhi ko‘rsatilmagan' : 'ko‘rsatilmagan'}: <b>${x.subs['']}</b>`);
  return parts;
}

/* «Kurs holati» bo'limi (desk.js pPanel chaqiradi): s — /api/staff/social javobi, total — kurs talabalari */
function socialSection(s, total) {
  if (!s) return '';
  const card = (k, x) => {
    const m = SOC[k] || { icon: 'users', c: 'people' }, lines = socLines(k, x, s.meta);
    const share = total && x.students ? `kurs talabalarining ${Math.max(1, Math.round(100 * x.students / total))}%` : '';
    return kpi({ href: '#', icon: m.icon, c: m.c, label: esc(x.title), value: x.students, unit: 'ta', title: 'Ro‘yxatni ochish',
      sub: x.students ? (lines.length ? lines.map(l => `<span class="ln">${l}</span>`).join('') : '') + (share ? `<span class="ln">${share}</span>` : '')
        : '<span class="ln">belgilanmagan</span>' }).replace('<a ', `<a data-soc="${k}" `);
  };
  return `<section class="sec soc-sec" data-total="${total || 0}"><header>${H('heart', 'Ijtimoiy toifalar', 'acad')}
      <span class="nowrap"><a href="#/files" title="«Ijtimoiy toifalar» shabloni bo‘yicha Excel fayl">${ic('upload')} Fayldan yuklash</a>
      <button class="btn sm primary" data-soc-add>${ic('plus')} Toifa belgilash</button></span></header>
    <div class="pad"><div class="kpis zrow">${Object.entries(s.cats).map(([k, x]) => card(k, x)).join('')}</div>
      <p class="hint" style="margin:0">${s.students ? `Jami <b>${s.students}</b> ta talaba kamida bitta toifada.` : 'Hali hech bir talabaga toifa berilmagan.'}
        Toifa fayl bilan («Ma’lumot va hisobot» → «Ijtimoiy toifalar» shabloni) yoki qo‘lda — talabalarni (butun guruhni ham) tanlab beriladi.</p></div></section>`;
}

/* «Barcha kurslar» (super-admin): kurslar bo'yicha yig'indi */
function socialKpi(courses) {
  const cats = {}, by = [];
  let total = 0;
  for (const c of courses) {
    if (!c.social) continue;
    total += c.social.students || 0;
    if (c.social.students) by.push(`${c.title}: ${c.social.students}`);
    for (const [k, x] of Object.entries(c.social.cats)) {
      const a = cats[k] = cats[k] || { title: x.title, students: 0, subs: {} };
      a.students += x.students;
      for (const [s, n] of Object.entries(x.subs || {})) a.subs[s] = (a.subs[s] || 0) + n;
    }
  }
  const sub = k => cats[k] ? cats[k].students : 0, ij = cats.ijtimoiy ? cats.ijtimoiy.subs : {};
  const ijt = [['reestr', 'reestr'], ['xotin_qizlar', 'xotin-qizlar'], ['ayollar', 'ayollar d.'], ['temir', 'temir d.'], ['yoshlar', 'yoshlar d.'], ['boshqa', 'boshqa']]
    .filter(([s]) => ij[s]).map(([s, t]) => `${t}: <b>${ij[s]}</b>`).join(' · ');
  return kpi({ icon: 'heart', c: 'acad', label: 'Ijtimoiy toifalar (barcha kurslar)', value: total, unit: 'talaba', title: by.join('\n') || 'Hali belgilanmagan',
    sub: `<span class="ln">nogironligi bor: <b>${sub('nogironlik')}</b> · chin yetim: <b>${sub('chin_yetim')}</b> · mehribonlik uyi: <b>${sub('mehribonlik')}</b></span>
      <span class="ln">ijtimoiy himoyaga muhtoj: <b>${sub('ijtimoiy')}</b></span>${ijt ? `<span class="ln">${ijt}</span>` : ''}` });
}

/* ---------------------------------------------------------------- toifa ro'yxati (yon panel) */
async function openSocial(cat, subF = '') {
  const dr = $('#drawer'); if (!dr) return;
  $('#dbody').innerHTML = skel(90) + skel(60, 3);
  dr.classList.add('on'); $('#scrim').classList.add('on'); dr.setAttribute('aria-hidden', 'false');
  let d;
  try { d = await api(`/api/staff/social/list?cat=${encodeURIComponent(cat)}`); } catch (e) { $('#dbody').innerHTML = emptyBox('alert', 'Ro‘yxatni yuklab bo‘lmadi'); return; }
  const meta = d.meta[cat], m = SOC[cat] || { icon: 'users', c: 'people' }, subs = meta.subs || {};
  $('#drawer header b').textContent = meta.title;
  const ids = new Set(d.items.map(r => r.student_id));
  const st = { sub: subF, q: '' };
  const subCnt = s => new Set(d.items.filter(r => r.sub === s).map(r => r.student_id)).size;
  const segs = Object.keys(subs).length ? [['', 'Hammasi', ids.size], ...Object.entries(subs).map(([s, t]) => [s, t, subCnt(s)]).filter(x => x[2]),
    ...(subCnt('') ? [['-', cat === 'nogironlik' ? 'Guruhi ko‘rsatilmagan' : 'Ko‘rsatilmagan', subCnt('')]] : [])] : [];
  $('#dbody').innerHTML = `
    <div class="soc-h"><span class="h-ic c-${m.c}" aria-hidden="true">${ic(m.icon)}</span>
      <div class="t"><b>${esc(meta.title)}</b><span>${ids.size} ta talaba</span></div>
      <button class="btn sm primary" data-soc-add="${cat}">${ic('plus')} Talaba qo‘shish</button></div>
    ${segs.length > 2 ? `<div class="seg wrap" id="soc-seg">${segs.map(([s, t, n]) => `<button data-sub="${s}" class="${st.sub === s ? 'on' : ''}">${esc(t)}<span class="n">${n}</span></button>`).join('')}</div>` : ''}
    ${ids.size > 8 ? `<div class="search">${ic('search')}<input class="input" id="soc-q" type="search" placeholder="Ism yoki guruh" aria-label="Qidirish"></div>` : ''}
    <div id="soc-list"></div>`;
  const draw = () => {
    const q = norm(st.q);
    const rows = d.items.filter(r => (!st.sub || (st.sub === '-' ? !r.sub : r.sub === st.sub))
      && (!q || norm(r.full_name).includes(q) || norm(r.group_name).includes(q)));
    if (!rows.length) { $('#soc-list').innerHTML = d.items.length ? emptyBox('search', 'Topilmadi')
      : emptyBox(m.icon, 'Ro‘yxat bo‘sh', 'Talabalarni tanlab toifa bering yoki «Ijtimoiy toifalar» faylini yuklang.'); return; }
    const by = {};
    rows.forEach(r => (by[r.group_name || '—'] = by[r.group_name || '—'] || []).push(r));
    $('#soc-list').innerHTML = Object.entries(by).sort(([a], [b]) => a.localeCompare(b, 'uz')).map(([g, l]) => `
      <div class="chs-sub">${esc(g)} · ${new Set(l.map(r => r.student_id)).size} ta</div>
      <ul class="soc-list">${l.map(r => `<li data-student="${r.student_id}">
        <div class="t"><b>${esc(r.full_name)}</b><span>${r.sub_title ? `<span class="chip ${m.c === 'acad' ? 'bordo' : 'muted'}">${esc(r.sub_title)}</span> ` : ''}${r.note ? esc(r.note) + ' · ' : ''}${SOC_SRC[r.source] || ''}${r.set_at ? ', ' + dmy(r.set_at) : ''}</span></div>
        <button class="btn sm ghost" data-soc-del="${r.student_id}" data-cat="${cat}" data-sub="${esc(r.sub)}" data-name="${esc(r.full_name)}" title="Toifani olib tashlash" aria-label="Toifani olib tashlash">${ic('x')}</button></li>`).join('')}</ul>`).join('');
  };
  draw();
  $('#soc-seg')?.addEventListener('click', e => { const b = e.target.closest('[data-sub]'); if (!b) return; st.sub = b.dataset.sub; $$('#soc-seg button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
  $('#soc-q')?.addEventListener('input', e => { st.q = e.target.value; draw(); });
}

/* ---------------------------------------------------------------- qo'lda belgilash: toifa + talabalar (guruh bilan) */
function socFields(meta, v, onChange) {
  const subSel = el('select', { class: 'select', onchange: e => { v.sub = e.target.value; } });
  const subBox = el('label', { class: 'field' }, el('span', { text: 'Kichik toifa' }), subSel);
  const paintSub = () => {
    const subs = v.cat ? meta[v.cat].subs : {};
    subBox.hidden = !Object.keys(subs).length;
    subBox.firstChild.textContent = v.cat === 'nogironlik' ? 'Nogironlik guruhi' : 'Qaysi ro‘yxatda (reestr, daftar)';
    if (!(v.sub in subs)) v.sub = v.cat === 'ijtimoiy' ? 'reestr' : '';
    fillKids(subSel, v.cat === 'nogironlik' ? el('option', { value: '', text: '— ko‘rsatilmagan —' }) : null,
      Object.entries(subs).map(([s, t]) => el('option', { value: s, text: t, selected: s === v.sub })));
  };
  const cats = el('div', { class: 'vtypes soc-cats' }, Object.entries(meta).map(([k, c]) => el('label', { class: 'vtype soc-t c-' + (SOC[k] || {}).c },
    el('input', { type: 'radio', name: 'soccat', value: k, checked: v.cat === k, onchange: () => { v.cat = k; paintSub(); onChange && onChange(); } }),
    el('span', { html: `${ic((SOC[k] || {}).icon || 'users')}<b>${esc(c.short)}</b><small>${esc((SOC[k] || {}).hint || c.title)}</small>` }))));
  const note = el('input', { class: 'input', placeholder: 'Masalan: ma’lumotnoma № 123', oninput: e => { v.note = e.target.value; } });
  paintSub();
  return { cats, subBox, noteBox: el('label', { class: 'field' }, el('span', { text: 'Izoh, asos hujjat (ixtiyoriy)' }), note) };
}
async function socialAssignDlg(cat = '', preset = null, course = null) {
  let meta;
  try { meta = (await api('/api/staff/social', { course })).meta; } catch (e) { toast('Ma’lumotni yuklab bo‘lmadi', true); return; }
  const v = { cat: cat || '', sub: '', note: '' };
  const sel = new Map(preset ? [[preset.id, preset]] : []);
  const pk = preset ? null : stuPicker(sel, () => 'plain');
  const f = socFields(meta, v);
  const err = el('div', { class: 'note bordo', hidden: true });
  const dl = el('dialog', { class: 'vdlg' });
  const save = el('button', { class: 'btn primary', type: 'button', onclick: async () => {
    err.hidden = true;
    if (!v.cat) { err.textContent = SOC_ERR.bad_category; err.hidden = false; return; }
    if (!sel.size) { err.textContent = SOC_ERR.no_students; err.hidden = false; return; }
    save.disabled = true;
    try {
      const r = await api('/api/staff/social/assign', { method: 'POST', course, json: { student_ids: [...sel.keys()], category: v.cat, sub: v.sub, note: v.note } });
      dl.close();
      toast(r.added ? `Toifa berildi: ${r.added} ta talaba${r.same ? ` (${r.same} tasida avvaldan bor edi)` : ''}` : 'Tanlangan talabalarda bu toifa avvaldan bor');
      socialRefresh(v.cat, preset ? preset.id : null, course);
    } catch (e) { err.textContent = socErr(e); err.hidden = false; save.disabled = false; }
  } }, 'Saqlash');
  dl.append(el('form', { method: 'dialog', class: 'wide', onsubmit: e => e.preventDefault() },
    el('h3', { text: preset ? `Ijtimoiy toifa — ${preset.name}` : 'Ijtimoiy toifa belgilash' }),
    preset ? null : el('p', { class: 'hint', style: 'margin-top:-6px', text: 'Toifani tanlang, so‘ng talabalarni qo‘shing — alohida yoki butun guruhni. Bir talabada bir nechta toifa bo‘lishi mumkin (masalan, chin yetim va mehribonlik uyi).' }),
    el('div', { class: 'field' }, el('span', { text: 'Toifa' }), f.cats),
    el('div', { class: 'cols2' }, f.subBox, f.noteBox),
    pk ? el('div', { class: 'field' }, el('span', { text: 'Talabalar' }), pk.groups, pk.q, pk.res, pk.chosen) : null,
    err,
    el('div', { class: 'row' }, el('button', { class: 'btn', type: 'button', onclick: () => dl.close() }, 'Bekor qilish'), save)));
  document.body.append(dl);
  dl.addEventListener('close', () => dl.remove());
  if (pk) { pk.load(); pk.repaint(); }
  dl.showModal();
}
/* o'zgarishdan keyin: ochiq ro'yxat / talaba kartasi va «Kurs holati» bo'limi (yon panel yopilmaydi) */
async function socialRefresh(cat, sid, course) {
  const dr = $('#drawer');
  if (sid && $('#stu-social')) loadStudentSocial(sid, course);
  else if (dr && dr.classList.contains('on') && $('#soc-list')) openSocial(cat);
  const sec = $('.soc-sec');
  if (!sec || course) return;
  try { const s = await api('/api/staff/social'); if (sec.isConnected) sec.outerHTML = socialSection(s, Number(sec.dataset.total)); } catch (_) { /* keyingi ochilishda */ }
}

/* ---------------------------------------------------------------- talaba kartasi */
async function loadStudentSocial(sid, course) {
  const box = $('#stu-social'); if (!box) return;
  let d;
  try { d = await api(`/api/staff/social/student/${sid}`, { course }); } catch (e) { box.remove(); return; }
  if (!$('#stu-social')) return;
  box.innerHTML = `<h4 class="h4row"><span>Ijtimoiy toifa</span><button class="btn sm ghost" data-soc-one>${ic('plus')} Belgilash</button></h4>
    ${d.items.length ? `<ul class="soc-list">${d.items.map(r => { const m = SOC[r.category] || {}; return `<li>
      <span class="h-ic sm c-${m.c}" aria-hidden="true">${ic(m.icon || 'users')}</span>
      <div class="t"><b>${esc(r.label)}</b><span>${r.note ? esc(r.note) + ' · ' : ''}${SOC_SRC[r.source] || ''}${r.set_at ? ', ' + dmy(r.set_at) : ''}</span></div>
      <button class="btn sm ghost" data-soc-del="${sid}" data-cat="${r.category}" data-sub="${esc(r.sub)}" data-one="1" title="Olib tashlash" aria-label="Olib tashlash">${ic('x')}</button></li>`; }).join('')}</ul>`
      : '<span class="dash">Belgilanmagan (nogironlik, ijtimoiy himoya, chin yetim, mehribonlik uyi)</span>'}`;
  $('[data-soc-one]', box).addEventListener('click', () => socialAssignDlg('', { id: sid, name: $('#drawer header b').textContent }, course));
  box.dataset.course = course || '';
}

document.addEventListener('click', async e => {
  const card = e.target.closest('a[data-soc]');
  if (card) { e.preventDefault(); openSocial(card.dataset.soc); return; }
  const add = e.target.closest('[data-soc-add]');
  if (add) { e.preventDefault(); socialAssignDlg(add.dataset.socAdd || ''); return; }
  const del = e.target.closest('[data-soc-del]');
  if (!del) return;
  e.preventDefault(); e.stopPropagation();
  const sid = Number(del.dataset.socDel), one = del.dataset.one === '1';
  const course = one ? ($('#stu-social')?.dataset.course || null) : null;
  const what = del.closest('li')?.querySelector('.t b')?.textContent || '';
  if (!await confirmDlg('Toifani olib tashlaysizmi?', one ? `«${esc(what)}» toifasi talabadan olib tashlanadi.` : `${esc(del.dataset.name || what)} bu toifa ro‘yxatidan chiqariladi.`, 'Olib tashlash', true)) return;
  try {
    await api('/api/staff/social/remove', { method: 'POST', course, json: { student_id: sid, category: del.dataset.cat, sub: del.dataset.sub } });
    toast('Olib tashlandi');
    socialRefresh(del.dataset.cat, one ? sid : null, course);
  } catch (err) { toast(socErr(err), true); }
}, true);
