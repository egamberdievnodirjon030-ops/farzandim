"use strict";
/* Taksi — admin panel. Barcha manzillar nisbiy: panel ham localhost:8080 da, ham https://…/admin/ da ishlaydi. */

// ================================================================== yordamchilar
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const TILE_URL = document.body.dataset.tile || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTR = document.body.dataset.attr || "© OpenStreetMap";

const S = {
  page: "dashboard",
  ordersScope: "active",
  driversStatus: "approved",
  financeDays: 14,
  currency: "so'm",
  summary: null,
  cache: {},
  maps: {},
  filters: { free: true, busy: true, stale: true, orders: true },
  timer: null,
  busy: false,
  again: false,
  chartAt: 0,
};

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const num = (n) => Math.round(n || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const money = (n) => (n == null ? "—" : `${num(n)} ${S.currency}`);
const compact = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(Math.round(n)));
const km = (m) => (m == null ? "—" : m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);
const pad = (n) => String(n).padStart(2, "0");
const icon = (name) => `<svg><use href="#i-${name}"/></svg>`;
const dt = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const ago = (iso) => {
  if (!iso) return "—";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "hozir";
  if (s < 3600) return `${Math.floor(s / 60)} daq oldin`;
  if (s < 86400) return `${Math.floor(s / 3600)} soat oldin`;
  return dt(iso);
};
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* ixtiyoriy */ } },
};

const STATUS = {
  searching: "Qidirilmoqda", accepted: "Yo'lda", arrived: "Kutmoqda", in_progress: "Safarda",
  finishing: "Tasdiq kutilmoqda", completed: "Yakunlangan", cancelled: "Bekor qilingan", no_drivers: "Topilmadi",
  pending: "Ariza", approved: "Tasdiqlangan", rejected: "Rad etilgan", blocked: "Bloklangan",
};
const KIND = { commission: "Komissiya", topup: "To'ldirish", payment: "To'lov", bonus: "Bonus", adjust: "Tuzatish" };
const ACTIVE = ["searching", "accepted", "arrived", "in_progress", "finishing"];
const chip = (s, label) => `<span class="chip ${esc(s)}">${esc(label || STATUS[s] || s)}</span>`;
const matches = (q, ...fields) => !q || fields.some((f) => String(f ?? "").toLowerCase().includes(q));
const emptyState = (title, text = "") => `<div class="empty"><b>${title}</b>${esc(text)}</div>`;

async function api(path, opts = {}) {
  const headers = { "X-Panel": "1" };
  if (opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { credentials: "same-origin", ...opts, headers });
  if (res.status === 401) {
    location.href = "login";
    throw new Error("unauthorized");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Xato: HTTP ${res.status}`);
  return data;
}

function toast(message, isError = false) {
  const el = document.createElement("div");
  el.className = isError ? "toast err" : "toast";
  el.innerHTML = `${icon(isError ? "alert" : "check")}<span>${esc(message)}</span>`;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 3600);
}

/** Tasdiqlash / summa kiritish oynasi. */
function ask({ title, text = "", input = false, presets = [], okText = "Tasdiqlash", danger = false }) {
  const dialog = $("#dialog");
  $("#dialog-title").textContent = title;
  $("#dialog-text").textContent = text;
  const field = $("#dialog-input");
  field.hidden = !input;
  field.value = "";
  const box = $("#dialog-presets");
  box.hidden = !presets.length;
  box.innerHTML = presets.map((p) => `<button type="button" class="btn small ${p < 0 ? "danger" : "blue"}" data-v="${p}">${p > 0 ? "+" : ""}${num(p)}</button>`).join("");
  box.onclick = (e) => { const b = e.target.closest("button[data-v]"); if (b) { field.value = b.dataset.v; field.focus(); } };
  const ok = $("#dialog-ok");
  ok.textContent = okText;
  ok.className = danger ? "btn danger" : "btn primary";
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok" ? (input ? field.value : true) : null), { once: true });
    dialog.returnValue = "";
    dialog.showModal();
    if (input) field.focus();
  });
}

function setLive(ok) {
  const now = new Date();
  for (const el of [$("#live"), $("#live-m")]) el.className = `${el.id === "live-m" ? "live compact mobile-only" : "live"} ${ok ? "ok" : "err"}`;
  $("#live-text").textContent = ok ? `Jonli · ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}` : "Aloqa yo'q";
}

// ================================================================== mavzu (kun / tun)
function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  const dark = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  $$('[data-act="theme"] use').forEach((u) => u.setAttribute("href", dark ? "#i-sun" : "#i-moon"));
}
function toggleTheme() {
  const current = document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  store.set("taxi_admin_theme", next);
  applyTheme(next);
}

// ================================================================== xarita
const divIcon = (html, size) => L.divIcon({ className: "", html, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });

class LiveMap {
  constructor(el) {
    this.map = L.map(el, { zoomControl: false }).setView([41.3111, 69.2797], 12);
    L.control.zoom({ position: "bottomright" }).addTo(this.map);
    const tiles = L.tileLayer(TILE_URL, {
      maxZoom: 19, subdomains: "abc", attribution: TILE_ATTR,
      referrerPolicy: "strict-origin-when-cross-origin", // OpenStreetMap Referer'siz so'rovni bloklaydi
    }).addTo(this.map);
    let loaded = 0;
    let failed = 0;
    tiles.on("tileload", () => { loaded++; $("#tile-note").hidden = true; });
    tiles.on("tileerror", () => { failed++; if (failed >= 6 && loaded === 0) $("#tile-note").hidden = false; });
    this.layers = { drivers: L.layerGroup().addTo(this.map), orders: L.layerGroup().addTo(this.map), lines: L.layerGroup().addTo(this.map) };
    this.drivers = new Map();
    this.orders = new Map();
    this.lines = new Map();
    this.fitted = false;
  }

  /** Belgilar qayta chizilmaydi — faqat siljiydi / qo'shiladi / o'chiriladi (tez va silliq). */
  update(data, filters = S.filters) {
    const byId = new Map(data.drivers.map((d) => [d.id, d]));
    sync(this.drivers, data.drivers, (d, m) => {
      const html = `<div class="pin ${d.state}">${icon("car")}</div>`;
      if (!m) m = L.marker([d.lat, d.lon], { icon: divIcon(html, 30), riseOnHover: true });
      else {
        m.setLatLng([d.lat, d.lon]);
        if (m._state !== d.state) m.setIcon(divIcon(html, 30));
      }
      m._state = d.state;
      const tip = `<b>${esc(d.plate)}</b> · ${esc(d.car)}<br>${esc(d.name)} · ⭐ ${Number(d.rating).toFixed(2)}<br>`
        + `${d.order_id ? `Buyurtma #${d.order_id}` : d.state === "free" ? "Bo'sh" : "Joylashuv eski"} · ${ago(d.updated_at)}`;
      if (m.getTooltip()) m.setTooltipContent(tip); else m.bindTooltip(tip, { direction: "top", offset: [0, -14] });
      toggle(this.layers.drivers, m, filters[d.state]);
      return m;
    });
    sync(this.orders, data.orders, (o, m) => {
      if (!m) m = L.marker(o.pickup, { icon: divIcon(`<div class="pin order"><span>${o.id % 100}</span></div>`, 26), zIndexOffset: 400 });
      else m.setLatLng(o.pickup);
      const tip = `<b>#${o.id}</b> · ${esc(STATUS[o.status] || o.status)}`;
      if (m.getTooltip()) m.setTooltipContent(tip); else m.bindTooltip(tip, { direction: "top", offset: [0, -14] });
      toggle(this.layers.orders, m, filters.orders);
      return m;
    });
    const withDriver = data.orders.filter((o) => o.driver_id && byId.has(o.driver_id));
    sync(this.lines, withDriver, (o, line) => {
      const d = byId.get(o.driver_id);
      const pts = [o.pickup, [d.lat, d.lon]];
      if (!line) line = L.polyline(pts, { color: "#d97706", weight: 2.5, dashArray: "6 7", opacity: 0.9 });
      else line.setLatLngs(pts);
      toggle(this.layers.lines, line, filters.orders && filters[d.state]);
      return line;
    });
    if (!this.fitted && (data.drivers.length || data.orders.length)) { this.fit(); this.fitted = true; }
  }

  fit() {
    const pts = [];
    for (const m of this.drivers.values()) if (this.layers.drivers.hasLayer(m)) pts.push(m.getLatLng());
    for (const m of this.orders.values()) if (this.layers.orders.hasLayer(m)) pts.push(m.getLatLng());
    if (pts.length) this.map.fitBounds(L.latLngBounds(pts), { padding: [50, 50], maxZoom: 15 });
  }

  focusOrder(id) {
    const m = this.orders.get(id);
    if (!m) return toast("Buyurtma xaritada yo'q", true);
    this.map.setView(m.getLatLng(), 16, { animate: true });
    m.openTooltip();
  }
}

/** Map<id, layer> ni yangi ro'yxat bilan moslaydi: yangi — qo'shiladi, eskirgan — olib tashlanadi. */
function sync(store_, items, upsert) {
  const seen = new Set();
  for (const it of items) {
    seen.add(it.id);
    store_.set(it.id, upsert(it, store_.get(it.id)));
  }
  for (const [id, layer] of store_) if (!seen.has(id)) { layer.remove(); store_.delete(id); }
}
function toggle(group, layer, show) {
  if (show && !group.hasLayer(layer)) group.addLayer(layer);
  else if (!show && group.hasLayer(layer)) group.removeLayer(layer);
}
function mapFor(key, elId) {
  if (!S.maps[key] && typeof L !== "undefined") S.maps[key] = new LiveMap(elId);
  const m = S.maps[key];
  if (m) setTimeout(() => m.map.invalidateSize(), 60);
  return m;
}

// ================================================================== grafik (SVG, kutubxonasiz)
function barChart(el, days, { trips = false } = {}) {
  const w = Math.max(280, el.clientWidth);
  const h = Math.max(150, el.clientHeight);
  const padL = 44; const padB = 22; const padT = 10; const padR = trips ? 30 : 6;
  const max = Math.max(1, ...days.map((d) => d.commission));
  const maxT = Math.max(1, ...days.map((d) => d.trips));
  const cw = (w - padL - padR) / Math.max(1, days.length);
  const y = (v) => padT + (h - padT - padB) * (1 - v / max);
  const yT = (v) => padT + (h - padT - padB) * (1 - v / maxT);
  let svg = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Kunlik komissiya">`;
  for (let i = 0; i <= 3; i++) {
    const v = (max / 3) * i;
    svg += `<line class="grid" x1="${padL}" x2="${w - padR}" y1="${y(v)}" y2="${y(v)}"/><text x="${padL - 6}" y="${y(v) + 4}" text-anchor="end">${compact(v)}</text>`;
  }
  const step = Math.ceil(days.length / 10);
  days.forEach((d, i) => {
    const x = padL + i * cw;
    const bh = Math.max(1, h - padB - y(d.commission));
    svg += `<rect class="bar" rx="4" x="${x + cw * 0.18}" y="${h - padB - bh}" width="${cw * 0.64}" height="${bh}"><title>${d.date}: ${money(d.commission)} · ${d.trips} safar</title></rect>`;
    if (i % step === 0 || i === days.length - 1) svg += `<text x="${x + cw / 2}" y="${h - 6}" text-anchor="middle">${d.date.slice(8)}.${d.date.slice(5, 7)}</text>`;
  });
  if (trips && days.length) {
    const pts = days.map((d, i) => `${padL + i * cw + cw / 2},${yT(d.trips)}`).join(" ");
    svg += `<polyline class="trip" points="${pts}"/>`;
    days.forEach((d, i) => { svg += `<circle class="trip-dot" r="3" cx="${padL + i * cw + cw / 2}" cy="${yT(d.trips)}"><title>${d.trips} safar</title></circle>`; });
    svg += `<text x="${w - 2}" y="${padT + 4}" text-anchor="end">safar ${maxT}</text>`;
  }
  el.innerHTML = `${svg}</svg>`;
}

// ================================================================== ma'lumot bloklari
function kpi({ label, value, unit = "", sub = "", ico = "list", tone = "blue", alert = false, goto = "" }) {
  return `<div class="card kpi t-${tone}${alert ? " alert" : ""}" ${goto ? `data-goto="${goto}" role="link" tabindex="0"` : ""}>
    <div class="ico">${icon(ico)}</div><div><div class="label">${esc(label)}</div><div class="value">${esc(value)}${unit ? ` <small>${esc(unit)}</small>` : ""}</div>
    ${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div></div>`;
}

async function loadSummary() {
  const s = await api("api/summary");
  S.summary = s;
  S.currency = s.currency || S.currency;
  const pending = $("#nav-pending");
  pending.hidden = !s.pending_drivers;
  pending.textContent = s.pending_drivers;
  $("#c-pending").textContent = s.pending_drivers || "";
  const count = $("#nav-orders");
  count.hidden = !s.active;
  count.textContent = s.active;
  return s;
}

function renderKpis(s) {
  const searching = s.active_by_status.searching || 0;
  $("#kpis").innerHTML = [
    kpi({ label: "Liniyada", value: s.online, sub: `bo'sh ${s.free} · band ${s.busy}`, ico: "car", tone: "green", goto: "map" }),
    kpi({ label: "Faol buyurtmalar", value: s.active, sub: searching ? `${searching} tasi qidiruvda` : "qidiruvda yo'q", ico: "route", goto: "orders" }),
    kpi({ label: "Bugun yakunlangan", value: s.today_done, sub: `topilmagan: ${s.today_no_drivers}`, ico: "check", tone: "green" }),
    kpi({ label: `Bugungi komissiya (${s.commission_percent}%)`, value: num(s.today_commission), unit: S.currency, sub: `aylanma ${money(s.today_turnover)}`, ico: "coins", tone: "amber", goto: "finance" }),
    kpi({ label: "Yangi arizalar", value: s.pending_drivers, sub: "tasdiq kutmoqda", ico: "users", tone: "blue", alert: s.pending_drivers > 0, goto: "drivers:pending" }),
    kpi({ label: "Balansi kam", value: s.low_balance, sub: "buyurtma olmaydi", ico: "wallet", tone: "red", alert: s.low_balance > 0, goto: "drivers:approved" }),
    kpi({ label: "Haydovchilar", value: s.drivers_total, sub: "tasdiqlangan", ico: "car", tone: "amber", goto: "drivers:approved" }),
    kpi({ label: "Yo'lovchilar", value: s.passengers_total, sub: "jami", ico: "users", tone: "blue", goto: "passengers" }),
  ].join("");
}

function orderItem(o, clickable = true) {
  const codes = o.call_codes && o.call_codes.length
    ? `<div class="meta">📞 kod: ${o.call_codes.map((c) => `<span class="code">${esc(c)}</span>`).join(" / ")} <span class="small">(yo'lovchi / haydovchi)</span></div>` : "";
  return `<div class="item${clickable ? " clickable" : ""}" data-order="${o.id}">
    <div class="item-top"><b>#${o.id}</b>${chip(o.status)}</div>
    <div class="meta">${ago(o.created_at)} · ${o.driver ? `🚕 ${esc(o.driver.plate)}` : "haydovchi yo'q"} · ${o.price ? money(o.price) : "taksometr"}</div>
    ${codes}${o.comment ? `<div class="meta">💬 ${esc(o.comment)}</div>` : ""}
    <div class="actions"><button class="btn small danger" data-act="cancel-order" data-id="${o.id}">Bekor qilish</button></div></div>`;
}

function pendingItem(d) {
  return `<div class="item"><div class="item-top"><b>${esc(d.name)}</b><span class="code">${esc(d.plate)}</span></div>
    <div class="meta">${esc(d.car)} · ${esc(d.phone || "")}</div>
    <div class="actions">
      <button class="btn small success" data-act="driver" data-action="approve" data-id="${d.id}">${icon("check")}Tasdiqlash</button>
      <button class="btn small" data-act="driver" data-action="reject" data-id="${d.id}">Rad etish</button></div></div>`;
}

// ================================================================== sahifalar
async function loadDashboard() {
  const needChart = Date.now() - S.chartAt > 60000;
  const [s, map, active, pending, fin] = await Promise.all([
    loadSummary(), api("api/map"), api("api/orders?scope=active"), api("api/drivers?status=pending"),
    needChart ? api("api/finance?days=14") : Promise.resolve(null),
  ]);
  renderKpis(s);
  const m = mapFor("dash", "dash-map");
  if (m) m.update(map);
  $("#active-count").textContent = active.length;
  $("#active-list").innerHTML = active.length ? active.map((o) => orderItem(o)).join("") : emptyState("✨", "Hozir faol buyurtma yo'q");
  $("#pending-list").innerHTML = pending.length ? pending.slice(0, 5).map(pendingItem).join("") : emptyState("👌", "Yangi ariza yo'q");
  if (fin) { S.chartAt = Date.now(); S.cache.dashFin = [...fin.days].reverse(); }
  if (S.cache.dashFin) barChart($("#dash-chart"), S.cache.dashFin);
}

async function loadMapPage() {
  const [, map, active] = await Promise.all([loadSummary(), api("api/map"), api("api/orders?scope=active")]);
  const m = mapFor("full", "full-map");
  S.cache.mapData = map;
  if (m) m.update(map);
  const count = { free: 0, busy: 0, stale: 0 };
  for (const d of map.drivers) count[d.state]++;
  $("#f-free").textContent = count.free;
  $("#f-busy").textContent = count.busy;
  $("#f-stale").textContent = count.stale;
  $("#f-orders").textContent = map.orders.length;
  $("#map-count").textContent = active.length;
  $("#map-orders").innerHTML = active.length ? active.map((o) => orderItem(o)).join("") : emptyState("✨", "Faol buyurtma yo'q");
}

const td = (label, html, cls = "") => `<td${label ? ` data-label="${label}"` : ""}${cls ? ` class="${cls}"` : ""}>${html}</td>`;
function table(head, rows, empty) {
  return `<thead><tr>${head.map(([t, cls]) => `<th class="${cls || ""}">${t}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.length ? rows.join("") : `<tr><td class="empty-cell" colspan="${head.length}">${empty}</td></tr>`}</tbody>`;
}

async function loadOrders(refetch = true) {
  if (refetch) {
    const [, orders] = await Promise.all([loadSummary(), api(`api/orders?scope=${S.ordersScope}&limit=300`)]);
    S.cache.orders = orders;
  }
  const q = $("#orders-q").value.trim().toLowerCase().replace(/^#/, "");
  const rows = (S.cache.orders || [])
    .filter((o) => matches(q, o.id, o.passenger.phone, o.rider_phone, o.driver?.plate, o.driver?.name, o.passenger.name, ...(o.call_codes || [])))
    .map((o) => `<tr>
      ${td("", `<b>#${o.id}</b> ${chip(o.status)}`, "lead")}
      ${td("Vaqt", dt(o.created_at), "nowrap")}
      ${td("Yo'lovchi", `${esc(o.passenger.name)}<span class="sub">${esc(o.passenger.phone || "")}${o.rider_phone ? ` → 👤 ${esc(o.rider_phone)}` : ""}</span>`)}
      ${td("Haydovchi", o.driver ? `${esc(o.driver.plate)}<span class="sub">${esc(o.driver.name)}</span>` : "—")}
      ${td("Masofa", km(o.distance_m), "num")}
      ${td("Narx", o.price ? money(o.price) : "taksometr", "num")}
      ${td("Komissiya", o.commission != null ? money(o.commission) : "—", "num")}
      ${td("Baho", `${o.rating ? "⭐".repeat(o.rating) : ""}${o.cancelled_by ? `<span class="sub">bekor: ${esc(o.cancelled_by)}</span>` : ""}${o.call_codes?.length && ACTIVE.includes(o.status) ? `<span class="sub">📞 ${o.call_codes.map(esc).join(" / ")}</span>` : ""}` || "—")}
      ${td("", ACTIVE.includes(o.status) || o.status === "no_drivers" ? `<div class="actions"><button class="btn small danger" data-act="cancel-order" data-id="${o.id}">Bekor qilish</button></div>` : "", "act")}
    </tr>`);
  $("#orders-table").innerHTML = table(
    [["Buyurtma"], ["Vaqt"], ["Yo'lovchi"], ["Haydovchi"], ["Masofa", "num"], ["Narx", "num"], ["Komissiya", "num"], ["Baho / izoh"], [""]],
    rows, emptyState("🔍", "Buyurtma topilmadi"),
  );
}

function driverActions(d) {
  const b = (act, label, cls) => `<button class="btn small ${cls}" data-act="driver" data-action="${act}" data-id="${d.id}">${label}</button>`;
  const out = [];
  if (d.status === "pending") out.push(b("approve", `${icon("check")}Tasdiqlash`, "success"), b("reject", "Rad etish", ""));
  if (d.status === "approved") out.push(b("topup", `${icon("wallet")}Balans`, "blue"), b("block", "Bloklash", "danger"));
  if (d.status === "blocked" || d.status === "rejected") out.push(b("unblock", "Faollashtirish", "success"));
  return `<div class="actions">${out.join("")}</div>`;
}

async function loadDrivers(refetch = true) {
  if (refetch) {
    const [, drivers] = await Promise.all([loadSummary(), api(`api/drivers${S.driversStatus ? `?status=${S.driversStatus}` : ""}`)]);
    S.cache.drivers = drivers;
  }
  const q = $("#drivers-q").value.trim().toLowerCase();
  const low = S.summary ? S.summary.min_driver_balance : null;
  const rows = (S.cache.drivers || [])
    .filter((d) => matches(q, d.id, d.name, d.phone, d.plate, d.car))
    .map((d) => {
      const now = d.status !== "approved" ? "" : !d.online ? chip("", "Oflayn")
        : d.busy ? chip("busy", "Band") : d.location_fresh ? chip("online", "Liniyada") : chip("", "Joylashuv eski");
      const balCls = d.balance < 0 || (low != null && d.balance < low) ? "num neg" : "num";
      return `<tr>
        ${td("", `<b>${esc(d.name)}</b> <span class="muted small">#${d.id}</span>`, "lead")}
        ${td("Telefon", esc(d.phone || "—"))}
        ${td("Avtomobil", `${esc(d.car)}<span class="sub"><span class="code">${esc(d.plate)}</span></span>`)}
        ${td("Holat", `${chip(d.status)} ${now}${d.home_mode ? ` ${chip("", "🏡 Uyga")}` : ""}`)}
        ${td("Balans", money(d.balance), balCls)}
        ${td("Reyting", `⭐ ${Number(d.rating).toFixed(2)}<span class="sub">${d.rating_count} baho</span>`, "num")}
        ${td("Safar / bekor", `${d.trips} / ${d.cancels}`, "num")}
        ${td("", driverActions(d), "act")}
      </tr>`;
    });
  $("#drivers-table").innerHTML = table(
    [["Haydovchi"], ["Telefon"], ["Avtomobil"], ["Holat"], ["Balans", "num"], ["Reyting", "num"], ["Safar / bekor", "num"], [""]],
    rows, emptyState("🔍", "Haydovchi topilmadi"),
  );
}

async function loadPassengers(refetch = true) {
  if (refetch) S.cache.passengers = await api("api/passengers");
  const q = $("#passengers-q").value.trim().toLowerCase();
  const rows = (S.cache.passengers || [])
    .filter((p) => matches(q, p.id, p.name, p.phone))
    .map((p) => `<tr>
      ${td("", `<b>${esc(p.name)}</b> <span class="muted small">#${p.id}</span>`, "lead")}
      ${td("Telefon", esc(p.phone || "—"))}
      ${td("Safar / bekor", `${p.trips} / ${p.cancels}`, "num")}
      ${td("Qo'shilgan", dt(p.created_at))}
      ${td("Holat", p.blocked ? chip("blocked") : chip("online", "Faol"))}
      ${td("", `<div class="actions"><button class="btn small ${p.blocked ? "success" : "danger"}" data-act="passenger" data-action="${p.blocked ? "unblock" : "block"}" data-id="${p.id}">${p.blocked ? "Blokdan chiqarish" : "Bloklash"}</button></div>`, "act")}
    </tr>`);
  $("#passengers-table").innerHTML = table(
    [["Yo'lovchi"], ["Telefon"], ["Safar / bekor", "num"], ["Qo'shilgan"], ["Holat"], [""]],
    rows, emptyState("🔍", "Yo'lovchi topilmadi"),
  );
}

async function loadFinance() {
  const [f, tx] = await Promise.all([api(`api/finance?days=${S.financeDays}`), api("api/transactions?limit=100")]);
  const t = f.totals;
  $("#finance-kpis").innerHTML = [
    kpi({ label: "Safarlar", value: num(t.trips), sub: `${S.financeDays} kun`, ico: "route" }),
    kpi({ label: "Aylanma", value: num(t.turnover), unit: S.currency, ico: "coins", tone: "amber" }),
    kpi({ label: "Komissiya (daromad)", value: num(t.commission), unit: S.currency, ico: "wallet", tone: "green" }),
    kpi({ label: "Balans to'ldirishlar", value: num(t.topups), unit: S.currency, ico: "check", tone: "blue" }),
    kpi({ label: "Haydovchilar balansi", value: num(f.driver_balances), unit: S.currency, sub: "hozirgi jami qoldiq", ico: "car", tone: "amber" }),
  ].join("");
  S.cache.finDays = [...f.days].reverse();
  barChart($("#finance-chart"), S.cache.finDays, { trips: true });
  $("#finance-table").innerHTML = table(
    [["Sana"], ["Safar", "num"], ["Aylanma", "num"], ["Komissiya", "num"], ["To'ldirish", "num"]],
    f.days.map((d) => `<tr>${td("", `<b>${d.date}</b>`, "lead")}${td("Safar", d.trips, "num")}${td("Aylanma", money(d.turnover), "num")}
      ${td("Komissiya", money(d.commission), "num")}${td("To'ldirish", money(d.topups), "num")}</tr>`),
    emptyState("📭", "Ma'lumot yo'q"),
  );
  $("#tx-table").innerHTML = table(
    [["Haydovchi"], ["Vaqt"], ["Turi"], ["Summa", "num"], ["Qoldiq", "num"]],
    tx.map((x) => `<tr>${td("", `${esc(x.plate)} <span class="muted small">${esc(x.driver)}</span>`, "lead")}${td("Vaqt", dt(x.created_at), "nowrap")}
      ${td("Turi", `${esc(KIND[x.kind] || x.kind)}${x.order_id ? ` <span class="muted small">#${x.order_id}</span>` : ""}`)}
      ${td("Summa", `${x.amount > 0 ? "+" : ""}${money(x.amount)}`, `num ${x.amount < 0 ? "neg" : "pos"}`)}${td("Qoldiq", money(x.balance_after), "num")}</tr>`),
    emptyState("📭", "Tranzaksiya yo'q"),
  );
}

const PAGES = {
  dashboard: { title: "Bosh sahifa", sub: "Bugungi holat — jonli yangilanadi", load: loadDashboard, every: 5000 },
  map: { title: "Jonli xarita", sub: "Haydovchilar va faol buyurtmalar", load: loadMapPage, every: 5000 },
  orders: { title: "Buyurtmalar", sub: "Qidiruv: raqam, telefon, davlat raqami yoki aloqa kodi", load: loadOrders, every: 10000 },
  drivers: { title: "Haydovchilar", sub: "Arizalar, balans va holat", load: loadDrivers, every: 15000 },
  passengers: { title: "Yo'lovchilar", sub: "Ro'yxat va bloklash", load: loadPassengers, every: 30000 },
  finance: { title: "Moliya", sub: "Komissiya, aylanma va tranzaksiyalar", load: loadFinance, every: 60000 },
};

// ================================================================== yangilash va navigatsiya
async function refresh() {
  clearTimeout(S.timer);
  if (S.busy) { S.again = true; return; } // sahifa almashsa — joriy yuklanish tugashi bilan qayta
  if (document.hidden) return; // yashirin tabda so'rov yubormaymiz — qaytganda darhol yangilanadi
  S.busy = true;
  S.again = false;
  try {
    await PAGES[S.page].load();
    setLive(true);
  } catch (err) {
    if (err.message !== "unauthorized") { setLive(false); console.warn(err); }
  } finally {
    S.busy = false;
    if (S.again) refresh();
    else S.timer = setTimeout(refresh, PAGES[S.page].every);
  }
}

function showPage(page) {
  if (!PAGES[page]) page = "dashboard";
  S.page = page;
  $$(".page").forEach((p) => p.classList.toggle("active", p.id === `page-${page}`));
  $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  $("#page-title").textContent = PAGES[page].title;
  $("#page-sub").textContent = PAGES[page].sub;
  document.title = `${PAGES[page].title} — ${document.title.split(" — ").pop()}`;
  window.scrollTo(0, 0);
  for (const m of Object.values(S.maps)) setTimeout(() => m.map.invalidateSize(), 60);
  refresh();
}

function go(target) {
  const [page, status] = target.split(":");
  if (status !== undefined) {
    S.driversStatus = status;
    $$("#drivers-status button").forEach((b) => b.classList.toggle("on", b.dataset.v === status));
  }
  if (location.hash === `#${page}`) showPage(page); else location.hash = page;
}

function segment(id, key, after) {
  $(id).addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-v]");
    if (!btn) return;
    $$(`${id} button`).forEach((b) => b.classList.toggle("on", b === btn));
    S[key] = key === "financeDays" ? Number(btn.dataset.v) : btn.dataset.v;
    after().catch((err) => toast(err.message, true));
  });
}

function debounce(fn, ms = 150) {
  let t;
  return () => { clearTimeout(t); t = setTimeout(fn, ms); };
}

// ================================================================== amallar
async function act(btn) {
  const id = btn.dataset.id;
  const kind = btn.dataset.act;
  if (kind === "cancel-order") {
    const ok = await ask({
      title: `Buyurtma #${id} ni bekor qilasizmi?`,
      text: "Yo'lovchi va haydovchiga xabar boradi, haydovchi bo'shaydi. Komissiya yechilmaydi.",
      okText: "Bekor qilish", danger: true,
    });
    if (!ok) return;
    await api(`api/orders/${id}/cancel`, { method: "POST" });
    toast(`Buyurtma #${id} bekor qilindi`);
  } else if (kind === "driver") {
    const action = btn.dataset.action;
    if (action === "topup") {
      const value = await ask({
        title: `Haydovchi #${id} balansi`,
        text: `To'ldirish summasini tanlang yoki yozing (${S.currency}). Yechish — minus bilan.`,
        input: true, presets: [10000, 20000, 50000, 100000, -5000], okText: "Saqlash",
      });
      if (!value) return;
      const res = await api(`api/drivers/${id}/topup`, { method: "POST", body: JSON.stringify({ amount: Number(value) }) });
      toast(`Yangi balans: ${money(res.balance)}`);
    } else {
      const labels = { approve: "tasdiqlaysizmi", reject: "rad etasizmi", block: "bloklaysizmi", unblock: "faollashtirasizmi" };
      const ok = await ask({
        title: `Haydovchi #${id} ni ${labels[action]}?`,
        text: action === "approve" ? "Haydovchiga Telegram'da xabar va bonus (sozlangan bo'lsa) boradi." : "Haydovchiga Telegram'da xabar boradi.",
        danger: action === "block" || action === "reject", okText: action === "approve" ? "Tasdiqlash" : "Ha",
      });
      if (!ok) return;
      await api(`api/drivers/${id}/${action}`, { method: "POST" });
      toast("Bajarildi");
    }
  } else if (kind === "passenger") {
    const action = btn.dataset.action;
    const ok = await ask({
      title: action === "block" ? `Yo'lovchi #${id} ni bloklaysizmi?` : `Yo'lovchi #${id} ni blokdan chiqarasizmi?`,
      text: action === "block" ? "U yangi buyurtma bera olmaydi." : "", danger: action === "block",
    });
    if (!ok) return;
    await api(`api/passengers/${id}/${action}`, { method: "POST" });
    toast("Bajarildi");
  }
  S.chartAt = 0;
  await refresh();
}

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (btn) {
    const kind = btn.dataset.act;
    try {
      if (kind === "theme") return toggleTheme();
      if (kind === "refresh") { S.chartAt = 0; return await refresh(); }
      if (kind === "fit") return S.maps.full && S.maps.full.fit();
      if (kind === "logout") {
        await fetch("logout", { method: "POST", headers: { "X-Panel": "1" }, credentials: "same-origin" }).catch(() => {});
        location.href = "login";
        return;
      }
      await act(btn);
    } catch (err) {
      toast(err.message, true);
    }
    return;
  }
  const goto = e.target.closest("[data-goto]");
  if (goto) return go(goto.dataset.goto);
  const gotoStatus = e.target.closest("[data-goto-status]");
  if (gotoStatus) { e.preventDefault(); return go(`drivers:${gotoStatus.dataset.gotoStatus}`); }
  const order = e.target.closest("[data-order]");
  if (order) {
    const id = Number(order.dataset.order);
    if (S.page !== "map") { location.hash = "map"; setTimeout(() => S.maps.full && S.maps.full.focusOrder(id), 700); }
    else if (S.maps.full) S.maps.full.focusOrder(id);
  }
});
document.addEventListener("keydown", (e) => {
  const goto = e.target.closest && e.target.closest("[data-goto]");
  if (goto && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); go(goto.dataset.goto); }
});

$("#map-filters").addEventListener("click", (e) => {
  const b = e.target.closest(".fchip");
  if (!b) return;
  S.filters[b.dataset.f] = !S.filters[b.dataset.f];
  b.classList.toggle("on", S.filters[b.dataset.f]);
  if (S.maps.full && S.cache.mapData) S.maps.full.update(S.cache.mapData);
});

segment("#orders-scope", "ordersScope", () => loadOrders());
segment("#drivers-status", "driversStatus", () => loadDrivers());
segment("#finance-days", "financeDays", () => loadFinance());
$("#orders-q").addEventListener("input", debounce(() => loadOrders(false)));
$("#drivers-q").addEventListener("input", debounce(() => loadDrivers(false)));
$("#passengers-q").addEventListener("input", debounce(() => loadPassengers(false)));
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
window.addEventListener("hashchange", () => showPage(location.hash.slice(1)));
window.addEventListener("resize", debounce(() => {
  if (S.page === "finance" && S.cache.finDays) barChart($("#finance-chart"), S.cache.finDays, { trips: true });
  if (S.page === "dashboard" && S.cache.dashFin) barChart($("#dash-chart"), S.cache.dashFin);
}, 200));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => applyTheme(store.get("taxi_admin_theme")));

applyTheme(store.get("taxi_admin_theme"));
showPage(location.hash.slice(1) || "dashboard");
