/* =====================================================================
   Bosh sahifa — dekan (barcha kurslar) va kurs koordinatori: rangli ko'rsatkich kartalari, dinamika grafigi (yorliqlar),
   muammolar tarkibi (donut), kesim jadvali (kurslar / guruhlar), intizomiy choralar, bugungi vazifalar, yaqin tadbir va
   tashriflar, integratsiyalar holati. Shuningdek: «Akademik natijalar» va «To'lovlar» (chek / kvitansiya bilan qarzni
   yopish) sahifalari. desk.js dagi yordamchilardan (api, view, ic, esc, kpi, toast, formDlg …) foydalanadi.
   ===================================================================== */
'use strict';

/* ---------------------------------------------------------------- kichik yordamchilar */
const SER_C = ['#2F6BED', '#8B5CF6', '#1E9E5A', '#D9861C', '#E5484D', '#0EA5E9', '#DB2777'];
const pctOf = (n, t) => (t ? Math.round(1000 * n / t) / 10 : 0);
const fmtPct = v => `${String(v).replace('.', ',')}%`;
const kc = ({ href, tone, icon, label, value, unit = '', sub = '', bg }) => {
  const tag = href ? 'a' : 'div';
  return `<${tag} class="kc ${tone}"${href ? ` href="${href}"` : ''}><div class="kc-h"><span class="kc-ic">${ic(icon)}</span>${label}</div>
    <div class="kc-v">${value}${unit ? `<small>${unit}</small>` : ''}</div><div class="kc-s">${sub}</div><span class="kc-bg" aria-hidden="true">${ic(bg || icon)}</span></${tag}>`;
};
const card = (icon, c, title, body, link = '', extra = '') => `<section class="card"><header><h3><span class="hic c-${c}">${ic(icon)}</span>${title}</h3>${extra}${link}</header>${body}</section>`;
const kvl = rows => `<ul class="kvl">${rows.map(r => `<li>${r.href ? `<a href="${r.href}">` : ''}<span class="k">${r.k}${r.s ? `<small>${r.s}</small>` : ''}</span><b${r.c ? ` style="color:${r.c}"` : ''}>${r.v}</b>${r.href ? '</a>' : ''}</li>`).join('')}</ul>`;
const moneyB = v => { const [a, u] = moneyShort(v); return `${a}<small>${u}</small>`; };
const more = (href, t = 'Barchasi') => `<a href="${href}">${t} ${ic('arrow')}</a>`;
const attPill = v => (v == null ? '<span class="pill gray">—</span>' : `<span class="pill ${v >= 90 ? 'green' : v >= 75 ? 'amber' : 'red'}">${fmtPct(v)}</span>`);
const probPill = n => (n ? `<span class="pill red">${ic('flame')}${n}</span>` : '<span class="pill gray">0</span>');
const evDay = e => { const d = new Date(`${e.date}T00:00`); return `${d.getDate()}-${MONTHS[d.getMonth()]}, ${e.start}–${e.end}`; };
function semLabel() { const d = new Date(), y = d.getMonth() >= 7 ? d.getFullYear() : d.getFullYear() - 1; return `${y}/${y + 1}-o‘quv yili, ${d.getMonth() >= 7 || d.getMonth() === 0 ? 1 : 2}-semestr`; }

/* ---------------------------------------------------------------- grafiklar */
/* «dd.mm» yorliqlari — o'quv yili tartibida (sentabr → avgust) */
const lblKey = l => { const m = /^(\d{1,2})\.(\d{1,2})/.exec(l || ''); if (!m) return 0; const mo = Number(m[2]); return (mo >= 8 ? 0 : 10000) + mo * 100 + Number(m[1]); };
function niceStep(raw) { const p = 10 ** Math.floor(Math.log10(raw || 1)), f = raw / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p; }
function yFmt(v, unit) {
  if (unit === '%') return `${Math.round(v)}%`;
  if (unit === 'gpa') return gpaFmt(v);
  if (unit === 'so\'m') { const [a, u] = moneyShort(v); return `${a} ${u.replace(' so‘m', '')}`; }
  return num(v, 0);
}
function valFmt(v, unit) { return unit === '%' ? fmtPct(v) : unit === 'so\'m' ? moneyShort(v).join(' ') : unit === 'gpa' ? gpaFmt(v) : `${num(v, 0)} ta`; }
/* series: [{name, color, points:[{label, value}]}] — chiziqli grafik, sichqoncha ustida qiymatlar */
function drawLine(el, series, unit) {
  const labels = [...new Set(series.flatMap(s => s.points.map(p => p.label)))].sort((a, b) => lblKey(a) - lblKey(b));
  const vals = series.flatMap(s => s.points.map(p => p.value)).filter(v => v != null);
  if (!labels.length || !vals.length) { el.innerHTML = `<div class="lc-empty">${ic('trend')}<div>Dinamika uchun ma’lumot hali kam — davomat yoki hisobotlar yuklanishi bilan grafik paydo bo‘ladi.</div></div>`; return; }
  const W = Math.max(300, el.clientWidth || 600), H = 240, L = unit === 'so\'m' ? 58 : 44, R = 16, T = 16, B = 30;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (unit === '%') { lo = Math.max(0, Math.floor((lo - 3) / 5) * 5); hi = Math.min(100, Math.ceil((hi + 2) / 5) * 5); if (hi - lo < 10) lo = Math.max(0, hi - 10); }
  else { const pad = (hi - lo) * 0.15 || Math.max(1, hi * 0.15); lo = Math.max(0, lo - pad); hi += pad; }
  const step = niceStep((hi - lo) / 4); lo = Math.floor(lo / step) * step; hi = Math.max(lo + step, Math.ceil(hi / step) * step);
  const x = i => L + (labels.length === 1 ? (W - L - R) / 2 : i * (W - L - R) / (labels.length - 1));
  const y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  const ticks = []; for (let v = lo; v <= hi + step / 2; v += step) ticks.push(v);
  const every = Math.max(1, Math.ceil(labels.length / Math.floor((W - L - R) / 56)));
  const single = series.length === 1;
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(series.map(s => s.name + ': ' + s.points.map(p => p.label + ' ' + valFmt(p.value, unit)).join(', ')).join('; '))}">
    <defs><linearGradient id="lcg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${series[0].color}" stop-opacity=".22"/><stop offset="1" stop-color="${series[0].color}" stop-opacity="0"/></linearGradient></defs>
    ${ticks.map(v => `<line class="gl" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${yFmt(v, unit)}</text>`).join('')}
    ${labels.map((l, i) => (i % every === 0 || i === labels.length - 1) ? `<text class="ax" x="${x(i)}" y="${H - 8}" text-anchor="middle">${esc(l)}</text>` : '').join('')}`;
  for (const s of series) {
    const pts = s.points.map(p => [x(labels.indexOf(p.label)), y(p.value)]).sort((a, b) => a[0] - b[0]);
    if (!pts.length) continue;
    const d = pts.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)} ${py.toFixed(1)}`).join('');
    if (single && pts.length > 1) svg += `<path d="${d}L${pts[pts.length - 1][0].toFixed(1)} ${y(lo)}L${pts[0][0].toFixed(1)} ${y(lo)}Z" fill="url(#lcg)"/>`;
    svg += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`;
    svg += pts.map(([px, py], i) => `<circle cx="${px}" cy="${py}" r="${i === pts.length - 1 ? 4.5 : 3}" fill="var(--surface)" stroke="${s.color}" stroke-width="2"/>`).join('');
  }
  svg += `<line class="hl" id="lchl" x1="0" x2="0" y1="${T}" y2="${H - B}" visibility="hidden"/><rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" data-hov/></svg>`;
  el.innerHTML = svg + '<div class="tip" hidden></div>';
  const tip = $('.tip', el), hl = $('#lchl', el), sv = $('svg', el);
  $('[data-hov]', el).addEventListener('mousemove', e => {
    const r = sv.getBoundingClientRect(), mx = (e.clientX - r.left) * W / r.width;
    let i = Math.round((mx - L) / ((W - L - R) / Math.max(1, labels.length - 1)));
    i = Math.max(0, Math.min(labels.length - 1, labels.length === 1 ? 0 : i));
    const rows = series.map(s => [s, s.points.find(p => p.label === labels[i])]).filter(([, p]) => p);
    if (!rows.length) { tip.hidden = true; return; }
    hl.setAttribute('x1', x(i)); hl.setAttribute('x2', x(i)); hl.setAttribute('visibility', 'visible');
    tip.innerHTML = `<span class="hint">${esc(labels[i])}</span>${rows.map(([s, p]) => `<div>${single ? '' : `<i style="background:${s.color}"></i>${esc(s.name)}: `}<b style="display:inline">${valFmt(p.value, unit)}</b></div>`).join('')}`;
    tip.style.left = `${x(i) / W * 100}%`; tip.style.top = `${Math.min(...rows.map(([, p]) => y(p.value))) / H * 100}%`; tip.hidden = false;
  });
  $('[data-hov]', el).addEventListener('mouseleave', () => { tip.hidden = true; hl.setAttribute('visibility', 'hidden'); });
}
/* dinamika yorliqlari (tartibi bilan); ma'lumoti yo'q ko'rsatkich ko'rsatilmaydi */
const DYN_T = { att: 'Davomat', limit: 'Chegaraga yetganlar', acad: 'Akademik qarz', gpa_low: 'GPA past', gpa_avg: 'O‘rtacha GPA',
  kontrakt: 'Kontrakt', trimestr: 'Trimestr' };
/* dinamika kartasi: yorliqlar (ko'rsatkichlar), oxirgi qiymat va o'zgarish — sarlavha o'ngida */
function dynCard(id, tabs, cur) {
  const t = tabs.find(x => x.key === cur) || tabs[0];
  const tabsHtml = tabs.length > 1 ? `<div class="tabs" role="tablist">${tabs.map(x => `<button data-dtab="${x.key}" class="${x.key === (t && t.key) ? 'on' : ''}" role="tab">${esc(x.title)}</button>`).join('')}</div>` : '';
  const leg = t && t.series.length > 1 ? `<div class="lc-leg">${t.series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('')}</div>` : '';
  let val = '';
  if (t && t.series.length === 1 && t.series[0].points.length) {
    const k = t.unit === 'gpa' ? 100 : 10, p = t.series[0].points, v = p[p.length - 1].value, d = p.length > 1 ? Math.round((v - p[p.length - 2].value) * k) / k : 0;
    const good = (d > 0) === (t.better === 'up');
    val = `<span class="dyn-v" title="Oxirgi qiymat va oldingi davrga nisbatan o‘zgarish">${valFmt(v, t.unit)}${d ? ` <span class="${good ? 'up' : 'down'}">${d > 0 ? '▲' : '▼'} ${t.unit === '%' ? String(Math.abs(d)).replace('.', ',') + ' p.p.' : valFmt(Math.abs(d), t.unit)}</span>` : ''}</span>`;
  }
  return card('trend', 'blue', 'Asosiy ko‘rsatkichlar dinamikasi', `<div class="cb"><div class="dyn-top">${tabsHtml}${leg}</div><div class="lc" id="${id}"></div>${t && t.caption ? `<p class="hint" style="margin:6px 0 0">${esc(t.caption)}</p>` : ''}</div>`, '', val);
}
function bindDyn(id, tabs, st, rerender) {
  const el = $('#' + id); if (!el) return;
  const t = tabs.find(x => x.key === st.tab) || tabs[0];
  if (!t) { el.innerHTML = `<div class="lc-empty">${ic('trend')}<div>Dinamika uchun ma’lumot hali yo‘q.</div></div>`; return; }
  drawLine(el, t.series, t.unit);
  if (window.ResizeObserver) { let w = el.clientWidth; new ResizeObserver(() => { if (Math.abs(el.clientWidth - w) > 20) { w = el.clientWidth; drawLine(el, t.series, t.unit); } }).observe(el); }
  $$('[data-dtab]').forEach(b => b.addEventListener('click', () => { st.tab = b.dataset.dtab; rerender(); }));
}
function donut(parts, center, centerSub) {
  const tot = parts.reduce((a, p) => a + p.value, 0), R = 66, C = 2 * Math.PI * R, cx = 86;
  let off = 0;
  const arcs = tot ? parts.filter(p => p.value).map(p => { const len = C * p.value / tot, gap = parts.filter(q => q.value).length > 1 ? 3 : 0;
    const a = `<circle cx="${cx}" cy="${cx}" r="${R}" fill="none" stroke="${p.color}" stroke-width="22" stroke-dasharray="${Math.max(0, len - gap)} ${C - Math.max(0, len - gap)}" stroke-dashoffset="${-off}" transform="rotate(-90 ${cx} ${cx})"><title>${esc(p.label)}: ${p.value}</title></circle>`;
    off += len; return a; }).join('') : `<circle cx="${cx}" cy="${cx}" r="${R}" fill="none" stroke="var(--line-2)" stroke-width="22"/>`;
  return `<div class="donut"><svg viewBox="0 0 172 172" role="img" aria-label="${esc(parts.map(p => p.label + ' ' + p.value).join(', '))}">${arcs}
      <text class="dc" x="${cx}" y="${cx + 4}" text-anchor="middle"><tspan style="font:800 30px var(--sans);fill:var(--ink)">${center}</tspan></text>
      <text x="${cx}" y="${cx + 24}" text-anchor="middle" style="font-size:12.5px;fill:var(--muted)">${esc(centerSub)}</text></svg>
    <ul>${parts.map(p => `<li><a href="${p.href || '#'}"><i style="background:${p.color}"></i><span>${esc(p.label)}</span><b>${p.value} ta</b><small>${tot ? fmtPct(pctOf(p.value, tot)) : '—'}</small></a></li>`).join('')}</ul></div>`;
}
const hbars = rows => { const max = Math.max(1, ...rows.map(r => r.v));
  return `<div class="hbars">${rows.map(r => `<${r.href ? `a href="${r.href}"` : 'div'} class="hb c-${r.c}"><span>${esc(r.t)}</span><div class="tr"><i style="width:${(100 * r.v / max).toFixed(1)}%"></i></div><b>${r.v} <small>ta</small></b></${r.href ? 'a' : 'div'}>`).join('')}</div>`; };
function taskCard(tasks) {
  const L = tasks || [], open = L.filter(t => t.n), done = L.filter(t => !t.n);
  const li = t => `<li class="${t.n ? '' : 'done'}"><a href="${t.href}"><span class="tk">${t.n ? '' : ic('check')}</span>
      <span class="tt">${esc(t.title)}${t.n && t.hint ? `<small>${esc(t.hint)}</small>` : ''}</span>${t.n ? `<span class="tn ${t.tone === 'bad' ? 'bad' : t.tone === 'info' ? 'info' : ''}">${t.n} ta</span>` : ''}</a></li>`;
  const body = (open.length ? `<ul class="tasks">${open.map(li).join('')}</ul>`
      : `<div class="cb"><div class="note ok">${ic('ok')}<span>Bugun bajarilmagan vazifa yo‘q.</span></div></div>`)
    + (done.length ? `<details class="tasks-done"><summary>${ic('check')}Bajarilgan / navbat yo‘q: ${done.length} ta yo‘nalish</summary><ul class="tasks">${done.map(li).join('')}</ul></details>` : '');
  return card('task', 'blue', 'Bugungi vazifalar', body, '', `<span class="cnum" title="Bajarilishi kerak">${open.length}</span>`);
}
const VT_IC = { ijara_tashrifi: ['home', 'violet'], madaniy_tashrif: ['map', 'amber'], tadbir: ['mega', 'blue'], koordinatorlik_soati: ['users', 'green'] };
function eventsCard(evs, sup) {
  const body = evs && evs.length ? `<ul class="evs">${evs.map(e => { const [icn, c] = VT_IC[e.type] || ['cal', 'blue'];
    const n = e.capacity ? `${e.students} / ${e.capacity}` : !e.students ? '' : e.type === 'ijara_tashrifi' ? `${e.students} talaba` : `${e.students} ta`;
    return `<li><a href="#/tashrif" ${e.course ? `data-ecourse="${esc(e.course)}"` : ''}><span class="ei c-${c}">${ic(icn)}</span><span class="et"><b>${esc(e.title)}</b>
      <span>${evDay(e)}${sup && e.course_title ? ' · ' + esc(e.course_title) : ''}${e.place ? ' · ' + esc(e.place) : ''}</span></span>${n ? `<span class="en">${n}</span>` : ''}</a></li>`; }).join('')}</ul>`
    : `<div class="cb"><div class="note">${ic('cal')}<span>Yaqin 2 haftada reja yo‘q.</span></div></div>`;
  return card('cal', 'violet', 'Yaqin tadbir va tashriflar', body, sup ? '' : more('#/tashrif'));
}
function integStrip(list) {
  if (!list || !list.length) return '';
  const warn = list.some(x => x.state === 'warn');
  return `<section class="card integ"><h3><span class="hic c-blue">${ic('plug')}</span>Integratsiyalar holati</h3>
    ${list.map(it => `<div class="integ-it ${it.state}" title="${esc(it.text || '')}"><span class="s">${ic(it.state === 'ok' ? 'check' : it.state === 'warn' ? 'alert' : 'clock')}</span>
      <div style="min-width:0"><b>${esc(it.title)}</b><span>${it.at ? `${it.key === 'hemis' ? 'Oxirgi yuklash' : 'Oxirgi sinxron'}: ${when(it.at)}` : esc(it.text || '')}</span></div></div>`).join('')}
    <span class="integ-all ${warn ? 'warn' : 'ok'}"><i></i>${warn ? 'E’tibor talab qiladi' : 'Tizimlar ishlamoqda'}</span></section>`;
}
const MIX = [['att', 'Davomat', '#2F6BED', 'att'], ['acad', 'Akademik qarz', '#8B5CF6', 'acad'], ['gpa', 'Past GPA', '#D9861C', 'gpa'],
  ['kontrakt', 'Kontrakt qarzi', '#1E9E5A', 'kontrakt'], ['trimestr', 'Trimestr qarzi', '#0EA5E9', 'trimestr']];
/* talabalar boti: ulanganlar, oxirgi 7 kunda faollar, bloklaganlar, ulanmaganlar — ro'yxatga havola bilan */
function botCard(b, all = false) {
  if (!b) return '';
  const q = all ? 'all=1&' : '', pct = b.total ? Math.round(100 * b.linked / b.total) : 0;
  return card('telegram', 'blue', 'Talabalar boti', `<div class="cb" style="padding-bottom:6px"><div class="botbar" title="${pct}% ulangan"><i style="width:${pct}%"></i></div>
      <p class="hint" style="margin:8px 0 0">${pct}% talaba botga ulangan — xabar, chora va hujjatlar o‘ziga boradi</p></div>${kvl([
    { k: 'Botga ulangan', s: `${b.total} ta talabadan`, v: `${b.linked}`, href: `#/students?${q}bot=on` },
    { k: 'Faol (oxirgi 7 kun)', s: 'botda yoki ilovada bo‘lgan', v: b.active, href: `#/students?${q}bot=active` },
    ...(b.blocked ? [{ k: 'Botni bloklagan', s: 'xabar yetmayapti', v: b.blocked, c: 'var(--red)', href: `#/students?${q}bot=blocked` }] : []),
    { k: 'Ulanmagan', s: 'bot havolasini yuboring', v: b.total - b.linked, c: b.total - b.linked ? 'var(--amber)' : '', href: `#/students?${q}bot=off` }])}`,
    more(`#/students?${q}bot=on`, 'Ro‘yxat'));
}
const discBars = k => hbars([{ t: 'Dekan ogohlantirishi', v: k.ogohlantirish || 0, c: 'blue', href: '#/chora?tab=hist&hm=ogohlantirish' },
  { t: 'Hayfsan', v: k.hayfsan || 0, c: 'violet', href: '#/chora?tab=hist&hm=hayfsan' },
  { t: 'Boshqa (ichki tartib)', v: k.boshqa || 0, c: 'amber', href: '#/chora?tab=hist&hm=boshqa' },
  { t: 'Ota-onaga xat', v: k.xat || 0, c: 'green', href: '#/chora?tab=hist&hm=xat' }]);

/* ================================================================ kurs koordinatori: bosh sahifa (kurs holati) */
async function pPanel(parts, q) {
  document.title = 'Bosh sahifa — Boshqaruv paneli';
  const st = S.home = S.home || { tab: 'att', group: '' };
  if (st.course !== S.course) { st.group = ''; st.course = S.course; }
  if (!$('.dboard')) view(skel(46) + `<div class="kpi5">${skel(138, 1).repeat(5)}</div>` + skel(300));
  const gq = st.group ? `?group=${encodeURIComponent(st.group)}` : '';
  const [d, home, ch, sc] = await Promise.all([api('/api/staff/panel' + gq), api('/api/staff/home').catch(() => null),
    api('/api/staff/discipline/badge').catch(() => null), api('/api/staff/social').catch(() => null)]);
  S.badges.unread = d.unread; paintBadges();
  const sup = S.me.role === 'super', T = d.total, prob = d.prob, ok = T - prob;
  const chk = ch ? ch.kpi : null;
  const kpis = `<div class="kpi5">
    ${kc({ href: '#/students', tone: 'blue', icon: 'users', label: 'Jami talabalar', value: num(T, 0), sub: `ota-onasi ulangan: <b>${fmtPct(Math.round(pctOf(d.linked, T)))}</b>` })}
    ${kc({ href: '#/students', tone: 'green', icon: 'smile', bg: 'check', label: 'Faol (muammosiz)', value: num(ok, 0), sub: `<b>${fmtPct(pctOf(ok, T))}</b> talabalar` })}
    ${kc({ href: '#/students?f=prob', tone: 'red', icon: 'alert', label: 'Muammoli talabalar', value: num(prob, 0), sub: `<b>${fmtPct(pctOf(prob, T))}</b> talabalar${d.multi ? ` · 3+ masala: <b>${d.multi}</b>` : ''}` })}
    ${kc({ href: '#/chora?tab=hist', tone: 'amber', icon: 'shield', bg: 'gavel', label: 'Chora ko‘rilganlar', value: chk ? num(chk.students, 0) : '—',
      sub: chk ? (ch.new ? `<span class="down">+${ch.new} ta kutilmoqda</span>` : `o‘quv yilida <b>${chk.total}</b> ta chora`) : 'ma’lumot yo‘q' })}
    ${kc({ href: '#/social', tone: 'violet', icon: 'heart', label: 'Ijtimoiy toifadagilar', value: sc ? num(sc.students, 0) : '—', sub: sc ? `<b>${fmtPct(pctOf(sc.students, T))}</b> talabalar` : '' })}
  </div>`;
  const tabs = (d.dynamics || []).filter(it => it.points && it.points.length).map(it => ({ key: it.key, title: DYN_T[it.key] || it.title,
    unit: it.unit, better: it.better, caption: `${it.title}${it.note ? ' · ' + it.note : ''} — ${it.caption}`, series: [{ name: it.title, color: SER_C[0], points: it.points }] }));
  const mix = d.mix || {};
  const mixCard = card('pie', 'red', `Muammolar tarkibi <small>(${prob} ta talaba)</small>`, `<div class="cb">${donut(MIX.map(([k, l, c, f]) => ({ label: l, value: mix[k] || 0, color: c, href: `#/students?f=${f}` })), prob, 'talaba')}</div>`);
  const groups = d.groups || [];
  const grpCard = card('layers', 'blue', 'Guruhlar kesimida holat', groups.length ? `<div style="overflow:auto"><table class="dtbl"><thead><tr><th>Guruh</th><th class="r">Talabalar</th><th class="r">Muammoli</th><th class="r">Davomat</th><th class="r">Chora</th></tr></thead>
    <tbody>${groups.map(g => `<tr class="click" data-grp="${esc(g.group)}"><td><b>${esc(g.group)}</b></td><td class="r">${g.total}</td><td class="r">${probPill(g.prob)}</td><td class="r">${attPill(g.att)}</td>
      <td class="r">${g.chora || '<span class="dash">0</span>'}</td></tr>`).join('')}</tbody></table></div>` : `<div class="cb">${emptyBox('users', 'Talabalar yuklanmagan')}</div>`, more('#/students'));
  const discCard = card('shield', 'violet', 'Intizomiy choralar', `<div class="cb"><p class="hint" style="margin:-4px 0 10px">O‘quv yili boshidan rasman ko‘rilgan choralar</p>${chk ? discBars(chk) : emptyBox('shield', 'Ma’lumot yo‘q')}
      ${ch && (ch.new || (ch.flow && (ch.flow.basis || ch.flow.order))) ? `<div class="note warn" style="margin-top:14px">${ic('alert')}<span>${ch.new ? `Chora kutilmoqda: <b>${ch.new}</b> ta talaba. ` : ''}${ch.flow && (ch.flow.basis + ch.flow.order) ? `Imzolangan hujjat kutilmoqda: <b>${ch.flow.basis + ch.flow.order}</b> ta talaba.` : ''}</span></div>` : ''}</div>`, more('#/chora'));
  const top = d.top || [];
  const topCard = card('target', 'red', 'E’tibor talab qiladigan talabalar', top.length ? `<div style="overflow:auto"><table class="dtbl"><thead><tr><th>Talaba</th><th>Masalalar</th><th class="r">Davomat</th></tr></thead>
    <tbody>${top.slice(0, 12).map(r => `<tr class="click" data-student="${r.id}"><td><b>${esc(r.name)}</b><div class="sub-l">${esc(r.group)}${r.hemis_id ? ' · HEMIS ' + esc(r.hemis_id) : ''}</div></td>
      <td><div class="wrapc" style="display:flex;gap:5px;flex-wrap:wrap">${issueChips(r)}</div></td><td class="r">${attPill(r.percent)}</td></tr>`).join('')}</tbody></table></div>`
    : `<div class="cb"><div class="note ok">${ic('ok')}<span>Muammoli talaba yo‘q — davomat, baholar va to‘lovlar joyida.</span></div></div>`, more('#/students?f=prob'));
  const finCard = card('wallet', 'amber', 'Moliyaviy qarzdorlik', kvl([
    { k: 'Kontrakt qarzi', s: `${d.kontrakt.count} ta talaba`, v: moneyB(d.kontrakt.sum), href: '#/payments' },
    { k: 'Trimestr qarzi', s: `${d.trimestr.count} ta talaba`, v: moneyB(d.trimestr.sum), href: '#/payments?k=trimestr' }]), more('#/payments'));
  const gl = d.group_list || [];
  const filters = `<div class="dfilters">
    ${gl.length > 1 ? `<select class="dchip" id="hgrp" aria-label="Guruh"><option value="">Barcha guruhlar (${gl.length})</option>${gl.map(g => `<option ${g === st.group ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select>` : ''}
    <span class="dchip">${ic('cal')}${esc(d.semester || semLabel())}</span>
    ${d.scope ? `<span class="dchip" title="${esc(d.scope)}">${ic('info')}${esc(String(d.scope).replace(/^\s*ℹ️?\s*/u, '').slice(0, 60))}</span>` : ''}
    <span class="grow"></span>
    <button class="btn" data-act="export" data-fmt="x">${ic('download')} Excel</button><button class="btn" data-act="export" data-fmt="p">${ic('file')} PDF</button>
    <button class="btn" data-act="reload" title="Yangilash">${ic('refresh')}</button></div>`;
  const paint = () => {
    view(`${sup ? head('Kurs holati', courseSub()) : ''}${filters}<div class="dboard"><div class="dash-main">${kpis}
      <div class="drow">${dynCard('hdyn', tabs, st.tab)}${mixCard}</div>
      <div class="drow">${grpCard}${discCard}</div>
      ${topCard}</div>
      <aside class="dash-side">${taskCard(home && home.tasks)}${eventsCard(home && home.events)}${botCard(d.bot)}${finCard}</aside></div>
      ${home ? `<div style="margin-top:20px">${integStrip(home.integrations)}</div>` : ''}
      <p class="foot">${ic('clock')} Ma’lumotlar oxirgi marta yangilangan: ${d.updated ? when(d.updated) : 'hali yuklanmagan'}.</p>`);
    bindDyn('hdyn', tabs, st, paint);
    $('#hgrp')?.addEventListener('change', e => { st.group = e.target.value; pPanel(); });
    $$('[data-grp]').forEach(r => r.addEventListener('click', () => {
      S.stuState = { ...(S.stuState || { f: '', q: '', c: '', all: false, sort: 'problems', dir: -1 }), g: r.dataset.grp, f: '', all: false }; location.hash = '#/students'; }));
  };
  paint();
}

/* ================================================================ dekan: bosh sahifa (barcha kurslar) */
async function pSuperOverview() {
  document.title = 'Bosh sahifa — Dekanat paneli';
  const st = S.shome = S.shome || { tab: 'att' };
  view(skel(46) + `<div class="kpi5">${skel(138, 1).repeat(5)}</div>` + skel(300));
  const d = await api('/api/super/overview');
  const C = d.courses, sum = f => C.reduce((a, c) => a + (f(c) || 0), 0);
  const T = sum(c => c.total), prob = sum(c => c.prob), ok = T - prob;
  const disc = ['students', 'total', 'pending', 'ogohlantirish', 'hayfsan', 'boshqa', 'xat', 'letters'].reduce((a, k) => ({ ...a, [k]: sum(c => (c.disc || {})[k]) }), {});
  const social = sum(c => (c.social || {}).students);
  const kpis = `<div class="kpi5">
    ${kc({ href: '#/students?all=1', tone: 'blue', icon: 'users', label: 'Jami talabalar', value: num(T, 0), sub: `${C.length} ta kurs · ulangan: <b>${fmtPct(Math.round(pctOf(sum(c => c.linked), T)))}</b>` })}
    ${kc({ tone: 'green', icon: 'smile', bg: 'check', label: 'Faol (muammosiz)', value: num(ok, 0), sub: `<b>${fmtPct(pctOf(ok, T))}</b> talabalar` })}
    ${kc({ href: '#/students?all=1&f=prob', tone: 'red', icon: 'alert', label: 'Muammoli talabalar', value: num(prob, 0), sub: `<b>${fmtPct(pctOf(prob, T))}</b> talabalar · 3+ masala: <b>${sum(c => c.multi)}</b>` })}
    ${kc({ tone: 'amber', icon: 'shield', bg: 'gavel', label: 'Chora ko‘rilganlar', value: num(disc.students, 0), sub: disc.pending ? `<span class="down">+${disc.pending} ta kutilmoqda</span>` : `o‘quv yilida <b>${disc.total}</b> ta chora` })}
    ${kc({ tone: 'violet', icon: 'heart', label: 'Ijtimoiy toifadagilar', value: num(social, 0), sub: `<b>${fmtPct(pctOf(social, T))}</b> talabalar` })}
  </div>`;
  const keys = Object.entries(DYN_T);
  const tabs = keys.map(([k, t]) => { const series = C.map((c, i) => { const it = (c.dynamics || []).find(x => x.key === k);
      return it && it.points.length ? { name: c.title, color: SER_C[i % SER_C.length], points: it.points, unit: it.unit, better: it.better, cap: it.caption } : null; }).filter(Boolean);
    return series.length ? { key: k, title: t, unit: series[0].unit, better: series[0].better, caption: `Kurslar bo‘yicha — ${series[0].cap}`, series } : null; }).filter(Boolean);
  const mix = { att: sum(c => c.att), acad: sum(c => c.acad), gpa: sum(c => c.gpa), kontrakt: sum(c => c.kontrakt.count), trimestr: sum(c => c.trimestr.count) };
  const mixCard = card('pie', 'red', `Muammolar tarkibi <small>(${prob} ta talaba)</small>`, `<div class="cb">${donut(MIX.map(([k, l, c, f]) => ({ label: l, value: mix[k] || 0, color: c, href: `#/students?all=1&f=${f}` })), prob, 'talaba')}</div>`);
  const coursesCard = card('layers', 'blue', 'Kurslar kesimida holat', C.length ? `<div style="overflow:auto"><table class="dtbl"><thead><tr><th>Kurs</th><th class="r">Talabalar</th><th class="r">Muammoli</th>
      <th class="r">Davomat</th><th class="r">Chora</th><th class="r">Qarzdor</th><th class="r" title="Talabalar botiga ulangan">Botda</th><th></th></tr></thead><tbody>
      ${C.map(c => `<tr class="click" data-crs="${esc(c.key)}" title="Kursga o‘tish"><td><b class="nowrap">${esc(c.title)}</b><div class="sub-l">${c.admins.length ? esc(c.admins.map(a => a.label).join(', ')) : `<span style="color:var(--amber)">koordinator yo‘q</span>`}</div></td>
        <td class="r">${num(c.total, 0)}</td><td class="r">${probPill(c.prob)}</td><td class="r">${attPill(c.avg_att)}</td>
        <td class="r nowrap">${c.disc ? (c.disc.pending ? `<span class="pill red" title="Chora kutilmoqda">+${c.disc.pending}</span>` : c.disc.students) : '—'}</td>
        <td class="r">${c.kontrakt.count + c.trimestr.count || '<span class="dash">0</span>'}</td>
        <td class="r nowrap" title="${c.bot ? `Faol: ${c.bot.active}, bloklagan: ${c.bot.blocked}` : ''}">${c.bot ? `${c.bot.linked}<small class="sub-l" style="display:inline"> / ${c.bot.total}</small>` : '—'}</td><td class="r">${ic('chevr')}</td></tr>`).join('')}</tbody></table></div>`
    : emptyBox('building', 'Hali kurs yo‘q', '', `<a class="btn primary" href="#/super/courses">${ic('plus')} Kurs yaratish</a>`), more('#/super/courses', 'Boshqarish'));
  const discCard = card('shield', 'violet', 'Intizomiy choralar', `<div class="cb"><p class="hint" style="margin:-4px 0 10px">O‘quv yili boshidan, barcha kurslar</p>${discBars(disc)}
    </div>${kvl([{ k: 'Chora kutilmoqda', s: 'chegaraga yetgan talabalar', v: disc.pending, c: disc.pending ? 'var(--red)' : '' },
      { k: 'Ota-onaga xatlar', s: 'yuborilgan', v: disc.letters }])}`);
  const sysCard = card('server', 'blue', 'Moliya va tizim', kvl([
    { k: 'Kontrakt qarzi', s: `${sum(c => c.kontrakt.count)} ta talaba`, v: moneyB(sum(c => c.kontrakt.sum)) },
    { k: 'Trimestr qarzi', s: `${sum(c => c.trimestr.count)} ta talaba`, v: moneyB(sum(c => c.trimestr.sum)) },
    { k: 'Tizim xatolari', s: '24 soat ichida', v: d.errors_24h || 0, c: d.errors_24h ? 'var(--red)' : 'var(--green)', href: '#/super/system' },
    { k: 'Zaxira nusxa', s: 'har kecha avtomatik', v: `<span style="font-size:13px">${d.last_backup ? when(d.last_backup) : 'olinmagan'}</span>`, href: '#/super/system' }]));
  const filters = `<div class="dfilters"><div class="seg" id="hcrs"><button class="on">${ic('layers')} Umumiy</button>${C.map(c => `<button data-crs="${esc(c.key)}">${esc(c.title)}</button>`).join('')}</div>
    <span class="dchip">${ic('cal')}${esc(d.semester || semLabel())}</span><span class="grow"></span>
    <button class="btn" data-act="reload">${ic('refresh')} Yangilash</button></div>`;
  const paint = () => {
    view(`${filters}<div class="dboard"><div class="dash-main">${kpis}
      <div class="drow">${dynCard('sdyn', tabs, st.tab)}${mixCard}</div>
      <div class="drow">${coursesCard}${discCard}</div></div>
      <aside class="dash-side">${taskCard(d.tasks)}${eventsCard(d.events, true)}${botCard(C.reduce((a, c) => c.bot ? { total: a.total + c.bot.total, linked: a.linked + c.bot.linked, active: a.active + c.bot.active, blocked: a.blocked + c.bot.blocked } : a, { total: 0, linked: 0, active: 0, blocked: 0 }), true)}${sysCard}</aside></div>
      <div style="margin-top:20px">${integStrip(d.integrations)}</div>`);
    bindDyn('sdyn', tabs, st, paint);
    $$('[data-crs]').forEach(b => b.addEventListener('click', () => { switchCourse(b.dataset.crs); location.hash = '#/panel'; }));
    $$('[data-ecourse]').forEach(a => a.addEventListener('click', () => switchCourse(a.dataset.ecourse)));
  };
  paint();
}

/* ================================================================ akademik natijalar */
async function pAcademic(parts, q) {
  document.title = 'Akademik natijalar — Boshqaruv paneli';
  const st = S.acad = S.acad || { f: 'acad', g: '' };
  if (!S.stu || S.stuCourse !== S.course) view(head('Akademik natijalar', courseSub()) + skel(138) + skel(360));
  const { rows } = await loadStudents();
  const debtors = rows.filter(r => r.debts.length), low = rows.filter(r => r.flags.gpa), withG = rows.filter(r => r.gpa != null);
  const avg = withG.length ? withG.reduce((a, r) => a + r.gpa, 0) / withG.length : null;
  const subj = {}; debtors.forEach(r => r.debts.forEach(s => { subj[s] = (subj[s] || 0) + 1; }));
  const topSubj = Object.entries(subj).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const groups = [...new Set(rows.map(r => r.group).filter(Boolean))].sort();
  const kp = `<div class="kpi5" style="grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:20px">
    ${kc({ tone: 'violet', icon: 'bookx', label: 'Akademik qarzdorlar', value: debtors.length, unit: 'ta', sub: `jami <b>${debtors.reduce((a, r) => a + r.debts.length, 0)}</b> ta qarzdor fan` })}
    ${kc({ tone: 'amber', icon: 'cap', label: 'GPA past', value: low.length, unit: 'ta', sub: 'kursdan kursga o‘tmaydi' })}
    ${kc({ tone: 'blue', icon: 'chart', label: 'O‘rtacha GPA', value: avg != null ? gpaFmt(avg) : '—', sub: `${withG.length} ta talaba bo‘yicha (HEMIS)` })}
    ${kc({ tone: 'green', icon: 'smile', bg: 'check', label: 'Qarzsiz', value: rows.length - debtors.length, unit: 'ta', sub: `<b>${fmtPct(pctOf(rows.length - debtors.length, rows.length))}</b> talabalar` })}</div>`;
  const draw = () => {
    let list = st.f === 'acad' ? debtors : st.f === 'gpa' ? low : withG;
    if (st.g) list = list.filter(r => r.group === st.g);
    list = [...list].sort(st.f === 'acad' ? (a, b) => b.debts.length - a.debts.length || a.name.localeCompare(b.name) : (a, b) => (a.gpa ?? 9) - (b.gpa ?? 9));
    $('#acl').innerHTML = list.length ? `<table class="tbl"><thead><tr><th>Talaba</th><th>Guruh</th><th>Akademik qarz</th><th class="r">GPA</th><th>Davomat</th></tr></thead><tbody>
      ${list.map(r => `<tr class="click" data-student="${r.id}"><td class="name"><b>${esc(r.name)}</b><span>${r.hemis_id ? 'HEMIS ' + esc(r.hemis_id) : ''}</span></td><td class="nowrap">${esc(r.group)}</td>
        <td>${r.debts.length ? `<div class="wrapc" style="display:flex;gap:5px;flex-wrap:wrap">${r.debts.slice(0, 4).map(s => `<span class="chip bordo">${esc(s)}</span>`).join('')}${r.debts.length > 4 ? `<span class="chip muted">+${r.debts.length - 4}</span>` : ''}</div>` : '<span class="dash">—</span>'}</td>
        <td class="r">${r.gpa != null ? (r.flags.gpa ? `<span class="gpa-low">${ic('alert')}${gpaFmt(r.gpa)}</span>` : gpaFmt(r.gpa)) : '<span class="dash">—</span>'}</td><td>${pctCell(r.percent)}</td></tr>`).join('')}</tbody></table>`
      : emptyBox('ok', st.f === 'acad' ? 'Akademik qarzdor yo‘q' : st.f === 'gpa' ? 'GPA si past talaba yo‘q' : 'GPA hali yuklanmagan', 'Akademik qarzdorlar va GPA HEMIS fayllaridan («Hisobot va ma’lumot» → yuklash) olinadi.');
    $('#acn').textContent = `${list.length} ta talaba`;
  };
  view(head('Akademik natijalar', courseSub(), `<button class="btn" data-act="reload-students">${ic('refresh')} Yangilash</button>`) + kp + `
    <div class="drow" style="grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);align-items:start">
      <section class="sec"><div class="pad" style="padding-top:16px"><div class="toolbar" style="margin:0">
        <div class="seg" id="acf">${[['acad', 'Akademik qarz', debtors.length], ['gpa', 'GPA past', low.length], ['all', 'GPA bo‘yicha', withG.length]].map(([k, l, n]) => `<button data-f="${k}" class="${st.f === k ? 'on' : ''}">${l}<span class="n">${n}</span></button>`).join('')}</div>
        <select class="select" id="acg"><option value="">Barcha guruhlar</option>${groups.map(g => `<option ${g === st.g ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select>
        <span class="grow"></span><span class="count" id="acn"></span></div></div><div class="tbl-wrap" id="acl"></div></section>
      ${card('bookx', 'violet', 'Eng ko‘p qarz bo‘lgan fanlar', `<div class="cb">${topSubj.length ? hbars(topSubj.map(([t, v]) => ({ t, v, c: 'violet' }))) : '<p class="hint">Akademik qarzdorlar ro‘yxati yuklanmagan yoki qarz yo‘q.</p>'}</div>`)}
    </div>`);
  draw();
  $('#acf').addEventListener('click', e => { const b = e.target.closest('[data-f]'); if (!b) return; st.f = b.dataset.f; $$('#acf button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
  $('#acg').addEventListener('change', e => { st.g = e.target.value; draw(); });
}

/* ================================================================ to'lovlar: qarzdorlar, chek / kvitansiya */
const RC_ERR = { no_debt: 'Bu talabada qarz yo‘q', bad_file: 'Chek PDF yoki rasm (JPG, PNG) bo‘lsin', too_big: 'Fayl juda katta (15 MB gacha)', bad_amount: 'Summa noto‘g‘ri', empty: 'Fayl tanlanmagan' };
async function pPayments(parts, q) {
  document.title = 'To‘lovlar — Boshqaruv paneli';
  const st = S.pay = S.pay || { k: 'kontrakt', q: '', g: '' };
  if (q && q.get('k')) { st.k = q.get('k'); history.replaceState(null, '', '#/payments'); }
  view(head('To‘lovlar', courseSub()) + skel(138) + skel(360));
  const d = await api('/api/staff/payments');
  const K = d.kontrakt, Tr = d.trimestr, rc = d.receipts.filter(r => !r.cancelled_at);
  const month = new Date().toISOString().slice(0, 7), rcm = rc.filter(r => (r.uploaded_at || '').slice(0, 7) === month);
  const [km, ku] = moneyShort(K.sum), [tm, tu] = moneyShort(Tr.sum), [rm, ru] = moneyShort(rcm.reduce((a, r) => a + r.amount, 0));
  const dl = x => x.deadline ? `muddat: <b>${dmy(x.deadline)}</b>${x.days_left != null ? (x.days_left < 0 ? ' <span class="down">o‘tgan</span>' : ` · ${x.days_left} kun`) : ''}` : 'muddat belgilanmagan';
  const kp = `<div class="kpi5" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:20px">
    ${kc({ tone: 'amber', icon: 'dollar', label: 'Kontrakt qarzi', value: km, unit: ku, sub: `<b>${K.count}</b> ta talaba · ${dl(K)}` })}
    ${kc({ tone: 'red', icon: 'receipt', label: 'Trimestr qarzi', value: tm, unit: tu, sub: `<b>${Tr.count}</b> ta talaba · ${dl(Tr)}` })}
    ${kc({ tone: 'green', icon: 'check', label: 'Cheklar (shu oy)', value: rcm.length, unit: 'ta', sub: `jami <b>${rm} ${ru}</b> qabul qilingan` })}</div>`;
  const draw = () => {
    if (st.k === 'cheklar') {
      $('#pyl').innerHTML = d.receipts.length ? `<table class="tbl"><thead><tr><th>Sana</th><th>Talaba</th><th>Turi</th><th class="r">Summa</th><th class="r">Qarz (oldin → keyin)</th><th>Chek</th><th></th></tr></thead><tbody>
        ${d.receipts.map(r => `<tr class="${r.cancelled_at ? 'muted-row' : ''}"><td class="nowrap">${dmy(r.uploaded_at)}${r.paid_date ? `<div class="sub-l">to‘lov: ${dmy(r.paid_date)}</div>` : ''}</td>
          <td class="name click" data-student="${r.student_id}"><b>${esc(r.full_name)}</b><span>${esc(r.group_name || '')}</span></td><td>${esc(d.kinds[r.kind] || r.kind)}</td>
          <td class="r nowrap"><b>${money(r.amount)}</b></td><td class="r nowrap">${money(r.debt_before)} → <b>${r.debt_after ? money(r.debt_after) : '0'}</b></td>
          <td><button class="btn sm ghost" data-rview="${r.id}">${ic('eye')} ${esc(r.name.length > 22 ? r.name.slice(0, 20) + '…' : r.name)}</button>${r.note ? `<div class="sub-l">${esc(r.note)}</div>` : ''}</td>
          <td class="r">${r.cancelled_at ? '<span class="chip muted">bekor qilingan</span>' : `<button class="btn sm ghost" data-rcancel="${r.id}" title="Chekni bekor qilish — qarz qaytadi">${ic('x')} Bekor qilish</button>`}</td></tr>`).join('')}</tbody></table>`
        : emptyBox('receipt', 'Hali chek yuklanmagan', 'Qarzdor qatoridagi «Chek yuklash» tugmasi orqali to‘lov cheki yoki kvitansiyasini yuklang.');
      $('#pyn').textContent = `${d.receipts.length} ta chek`;
      return;
    }
    const X = d[st.k], qq = norm(st.q);
    const list = X.items.filter(r => (!st.g || r.group === st.g) && (!qq || norm(r.name).includes(qq) || norm(r.hemis_id) === qq));
    $('#pyl').innerHTML = list.length ? `<table class="tbl"><thead><tr><th>Talaba</th><th>Guruh</th><th class="r">Shartnoma</th><th class="r">To‘langan</th><th class="r">Qarz</th><th>Hisobot sanasi</th><th></th></tr></thead><tbody>
      ${list.map(r => `<tr><td class="name click" data-student="${r.id}"><b>${esc(r.name)}</b><span>${r.hemis_id ? 'HEMIS ' + esc(r.hemis_id) : ''}${r.linked ? '' : ' · ota-onasi ulanmagan'}</span></td><td class="nowrap">${esc(r.group)}</td>
        <td class="r nowrap">${r.contract ? money(r.contract) : '<span class="dash">—</span>'}</td><td class="r nowrap">${r.paid != null ? money(r.paid) : '<span class="dash">—</span>'}${r.percent != null ? `<div class="sub-l">${num(r.percent, 0)}%</div>` : ''}</td>
        <td class="r nowrap"><b class="money">${money(r.debt)}</b></td><td class="nowrap">${dmy(r.as_of)}${r.by_receipt ? '<div class="sub-l">chek bo‘yicha kamaygan</div>' : ''}</td>
        <td class="r"><button class="btn sm primary" data-rup="${r.id}">${ic('upload')} Chek yuklash</button></td></tr>`).join('')}</tbody></table>`
      : emptyBox('ok', X.items.length ? 'Topilmadi' : 'Qarzdor yo‘q', X.items.length ? 'Qidiruvni o‘zgartiring.' : 'Buxgalteriya hisoboti bo‘yicha qarzdor talaba yo‘q.');
    $('#pyn').textContent = `${list.length} ta talaba · ${moneyShort(list.reduce((a, r) => a + r.debt, 0)).join(' ')}`;
  };
  const groups = [...new Set([...K.items, ...Tr.items].map(r => r.group).filter(Boolean))].sort();
  view(head('To‘lovlar', courseSub(), `<button class="btn" data-act="reload">${ic('refresh')} Yangilash</button>`) + kp + `
    <section class="sec"><div class="pad" style="padding-top:16px"><div class="toolbar" style="margin:0">
      <div class="seg" id="pyk">${[['kontrakt', 'Kontrakt', K.count], ['trimestr', 'Trimestr', Tr.count], ['cheklar', 'Cheklar arxivi', d.receipts.length]].map(([k, l, n]) => `<button data-k="${k}" class="${st.k === k ? 'on' : ''}">${l}<span class="n">${n}</span></button>`).join('')}</div>
      <div class="search">${ic('search')}<input class="input" id="pyq" type="search" placeholder="Ism yoki HEMIS ID" value="${esc(st.q)}"></div>
      <select class="select" id="pyg"><option value="">Barcha guruhlar</option>${groups.map(g => `<option ${g === st.g ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select>
      <span class="grow"></span><span class="count" id="pyn"></span></div>
      <p class="hint" style="margin:10px 0 0">Talaba to‘lov qilib chek yoki kvitansiyasini yuborsa — uni shu yerda yuklang (PDF yoki rasm): qarz yopiladi (summa kam bo‘lsa — kamayadi) va talaba qarzdorlar ro‘yxatidan chiqadi. Buxgalteriyaning keyingi hisobotida qarz hali ko‘rinsa — o‘sha ustun bo‘ladi.</p></div>
      <div class="tbl-wrap" id="pyl"></div></section>`);
  draw();
  $('#pyk').addEventListener('click', e => { const b = e.target.closest('[data-k]'); if (!b) return; st.k = b.dataset.k; $$('#pyk button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
  $('#pyq').addEventListener('input', e => { st.q = e.target.value; draw(); });
  $('#pyg').addEventListener('change', e => { st.g = e.target.value; draw(); });
  $('#pyl').addEventListener('click', async e => {
    const up = e.target.closest('[data-rup]'), vw = e.target.closest('[data-rview]'), cn = e.target.closest('[data-rcancel]');
    if (up) { e.stopPropagation(); const r = d[st.k].items.find(x => x.id === Number(up.dataset.rup)); if (await receiptDlg(r, st.k)) pPayments(); }
    else if (vw) { e.stopPropagation(); viewReceipt(Number(vw.dataset.rview)); }
    else if (cn) { e.stopPropagation();
      if (!await confirmDlg('Chekni bekor qilasizmi?', 'Qarz chek yuklanishidan oldingi holatiga qaytadi (fayl arxivda «bekor qilingan» bo‘lib qoladi).', 'Bekor qilish', true)) return;
      try { await api(`/api/staff/payments/receipt/${cn.dataset.rcancel}/cancel`, { method: 'POST' }); toast('Chek bekor qilindi — qarz qaytdi'); S.stu = null; pPayments(); }
      catch (err) { toast((err.data && err.data.message) || 'Bajarilmadi', true); } }
  });
}
async function receiptDlg(r, kind) {
  const f = await formDlg(`To‘lov cheki — ${r.name}`, `<p>${kind === 'trimestr' ? 'Trimestr' : 'Kontrakt'} qarzi: <b>${money(r.debt)}</b>${r.as_of ? ` (${dmy(r.as_of)} holatiga)` : ''}. Chek yoki kvitansiya yuklansa — qarz yopiladi.</p>
    <label class="field"><span>Chek / kvitansiya — PDF yoki rasm</span><input class="input" type="file" name="file" accept=".pdf,application/pdf,image/*" required></label>
    <div class="cols2"><label class="field"><span>To‘langan summa (so‘m)</span><input class="input" name="amount" inputmode="decimal" placeholder="Bo‘sh — qarz to‘liq: ${esc(money(r.debt))}"></label>
      <label class="field"><span>To‘lov sanasi</span><input class="input" type="date" name="date" value="${todayIso()}"></label></div>
    <label class="field"><span>Izoh (ixtiyoriy)</span><input class="input" name="note" placeholder="Masalan: Click orqali, kvitansiya № 1234"></label>`, 'Yuklash va qarzni yopish');
  if (!f) return false;
  const file = f.get('file');
  if (!file || !file.name) { toast('Fayl tanlanmagan', true); return false; }
  const fd = new FormData();
  fd.append('student_id', r.id); fd.append('kind', kind); fd.append('amount', (f.get('amount') || '').trim()); fd.append('date', f.get('date') || '');
  fd.append('note', f.get('note') || ''); fd.append('file', file, file.name);
  try { const x = await api('/api/staff/payments/receipt', { method: 'POST', body: fd });
    toast(x.debt_after ? `Qarz kamaydi: ${money(x.amount)} qabul qilindi, qoldi — ${money(x.debt_after)}` : `Qarz yopildi — ${r.name} qarzdorlar ro‘yxatidan chiqdi`);
    S.stu = null; return true; }
  catch (e) { toast((e.data && e.data.message) || RC_ERR[e.message] || 'Yuklanmadi', true); return false; }
}
async function viewReceipt(rid) {
  const w = window.open('', '_blank');
  try { const r = await api(`/api/staff/payments/receipt/${rid}/file?view=1`, { raw: true });
    const url = URL.createObjectURL(await r.blob()); if (w) w.location = url; else location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 120000); }
  catch (e) { if (w) w.close(); toast('Ochib bo‘lmadi', true); }
}

