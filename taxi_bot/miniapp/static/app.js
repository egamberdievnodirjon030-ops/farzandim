"use strict";
/* Taksi — Telegram Mini App (yo'lovchi va haydovchi). Xarita: Leaflet. */

const tg = window.Telegram && window.Telegram.WebApp;
const $ = (s, r = document) => r.querySelector(s);
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const num = (n) => Math.round(n || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const S = {
  app: null, config: null, map: null, layers: {}, car: null, me: null,
  pickup: null, dest: null, quote: null, mode: "boot", order: null, offerIdx: 0,
  pollBusy: false, lastRouteKey: "", lastRouteAt: 0, pinHandler: null, location: null,
  driver: null, online: false,
};

// ====================================================================== Telegram
function money(n) { return n == null ? "—" : `${num(n)} ${S.config ? S.config.currency : "so'm"}`; }
function km(m) { return m == null ? "—" : m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`; }
function mins(s) { return s == null ? "—" : `${Math.max(1, Math.ceil(s / 60))} daq`; }

function haptic(kind) {
  try {
    if (!tg || !tg.HapticFeedback) return;
    if (["success", "error", "warning"].includes(kind)) tg.HapticFeedback.notificationOccurred(kind);
    else tg.HapticFeedback.impactOccurred(kind || "light");
  } catch { /* eski klient */ }
}

let toastTimer = null;
function toast(text, err = false) {
  const el = $("#toast");
  el.textContent = text;
  el.className = err ? "toast err" : "toast";
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 3200);
  if (err) haptic("error");
}

function makeBottomButton(btn) {
  let handler = null;
  return {
    set(text, onClick, opts = {}) {
      if (!btn) return;
      if (handler) btn.offClick(handler);
      handler = async () => {
        if (opts.progress !== false) btn.showProgress(false);
        try { await onClick(); } finally { btn.hideProgress(); }
      };
      btn.onClick(handler);
      btn.setParams({
        text, is_visible: true, is_active: opts.active !== false,
        color: opts.color || "#ffd21f", text_color: opts.textColor || "#111111",
      });
    },
    hide() {
      if (!btn) return;
      if (handler) btn.offClick(handler);
      handler = null;
      btn.hide();
    },
  };
}
const Main = makeBottomButton(tg && tg.MainButton);
const Second = makeBottomButton(tg && tg.SecondaryButton);

const Back = {
  handler: null,
  show(fn) {
    if (!tg || !tg.BackButton) return;
    if (this.handler) tg.BackButton.offClick(this.handler);
    this.handler = fn;
    tg.BackButton.onClick(fn);
    tg.BackButton.show();
  },
  hide() {
    if (!tg || !tg.BackButton) return;
    if (this.handler) tg.BackButton.offClick(this.handler);
    this.handler = null;
    tg.BackButton.hide();
  },
};

function confirmBox(text) {
  return new Promise((resolve) => {
    if (tg && tg.showConfirm) tg.showConfirm(text, (ok) => resolve(!!ok));
    else resolve(window.confirm(text));
  });
}

function openLink(url) {
  if (tg && tg.openLink) tg.openLink(url);
  else window.open(url, "_blank");
}

// ====================================================================== API
async function api(path, body) {
  const opts = { headers: { Authorization: `tma ${tg ? tg.initData : ""}` } };
  if (S.app) opts.headers["X-App"] = S.app;
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Xato (${res.status})`);
  return data;
}

// ====================================================================== joylashuv
function lmReady() {
  return new Promise((resolve) => {
    const lm = tg && tg.LocationManager;
    if (!lm) return resolve(null);
    if (lm.isInited) return resolve(lm);
    lm.init(() => resolve(lm));
    setTimeout(() => resolve(lm.isInited ? lm : null), 1500);
  });
}

/** Telefon joylashuvini so'raydi (Telegram LocationManager → brauzer geolocation). */
async function locate() {
  const lm = await lmReady();
  if (lm && lm.isLocationAvailable) {
    const viaTelegram = await new Promise((resolve) => {
      lm.getLocation((d) => resolve(d ? {
        lat: d.latitude, lon: d.longitude, accuracy: d.horizontal_accuracy, heading: d.course, speed: d.speed,
      } : null));
    });
    if (viaTelegram) return viaTelegram;
    if (lm.isAccessRequested && !lm.isAccessGranted) {
      toast("Joylashuvga ruxsat bering — sozlamalar ochilmoqda", true);
      try { lm.openSettings(); } catch { /* eski klient */ }
      return null;
    }
  }
  if (!navigator.geolocation) return null;
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy, heading: p.coords.heading }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 3000 }
    );
  });
}

// ====================================================================== xarita
const CAR_SVG = `<svg class="car-body" viewBox="0 0 40 40"><g transform="translate(20 20)">
  <rect x="-8" y="-15" width="16" height="30" rx="6" fill="#ffd21f" stroke="#1d1d1d" stroke-width="1.6"/>
  <rect x="-6" y="-8" width="12" height="6" rx="2" fill="#2b2b2b"/><rect x="-6" y="5" width="12" height="5" rx="2" fill="#2b2b2b"/>
  <rect x="-5" y="-1" width="10" height="5" fill="#ffe680"/></g></svg>`;

function initMap(center) {
  S.map = L.map("map", { zoomControl: false, attributionControl: true, zoomSnap: 0.5 }).setView(center, 16);
  L.tileLayer(S.config.tile_url, { maxZoom: 19, attribution: S.config.tile_attribution, subdomains: "abc" }).addTo(S.map);
  for (const name of ["route", "markers", "cars", "radar"]) S.layers[name] = L.layerGroup().addTo(S.map);
  S.map.on("movestart", () => $("#center-pin").classList.add("lifted"));
  S.map.on("moveend", () => {
    $("#center-pin").classList.remove("lifted");
    if (S.pinHandler && !$("#center-pin").hidden) S.pinHandler(visibleCenter());
  });
  $("#locate").addEventListener("click", async () => {
    haptic();
    const loc = await locate();
    if (loc) { S.location = loc; updateMe(loc); centerOn(loc.lat, loc.lon, 17); if (S.mode === "home") S.pinHandler(loc); }
  });
}

function sheetHeight() { return $("#sheet").offsetHeight || 0; }

/** Ko'rinadigan maydon markazi (pastki panel hisobga olingan). */
function visibleCenter() {
  const size = S.map.getSize();
  const p = S.map.containerPointToLatLng([size.x / 2, pinY()]);
  return { lat: p.lat, lon: p.lng };
}

/** Ninaning uchi turgan ekran nuqtasi: pastki panel ustidagi ko'rinadigan maydon markazi. */
function pinY() { return Math.round((S.map.getSize().y - sheetHeight()) / 2 + 24); }

/** Nuqtani nina ostiga keltiradi. Panel chizilib bo'lgach (keyingi kadrda) ishlaydi — balandlik aniq bo'ladi. */
function centerOn(lat, lon, zoom) {
  requestAnimationFrame(() => {
    const z = zoom || S.map.getZoom();
    const size = S.map.getSize();
    const pt = S.map.project([lat, lon], z).add([0, size.y / 2 - pinY()]);
    S.map.setView(S.map.unproject(pt, z), z, { animate: true });
  });
}

function layoutOverlays() {
  const h = sheetHeight();
  const pin = $("#center-pin");
  if (S.map) pin.style.top = `${pinY()}px`;
  $("#locate").style.bottom = `${h + 14}px`;
}

function showPin(kind, bubble) {
  const pin = $("#center-pin");
  pin.hidden = false;
  pin.querySelector(".pin-head").className = kind === "dest" ? "pin-head dest" : "pin-head";
  $("#pin-bubble").textContent = bubble || "";
  layoutOverlays();
}
function hidePin() { $("#center-pin").hidden = true; S.pinHandler = null; }

function fitTo(points) {
  const valid = points.filter((p) => p && p[0] != null);
  if (!valid.length) return;
  if (valid.length === 1) return centerOn(valid[0][0], valid[0][1], 16);
  requestAnimationFrame(() => S.map.fitBounds(L.latLngBounds(valid), {
    paddingTopLeft: [40, 90], paddingBottomRight: [40, sheetHeight() + 40], maxZoom: 17, animate: true,
  }));
}

/** Doiraviy hududni (radius, metr) ko'rinadigan qilib moslaydi. */
function fitCircle(lat, lon, radius, extra = []) {
  const b = L.latLng(lat, lon).toBounds(radius * 2);
  fitTo([[b.getNorth(), b.getWest()], [b.getSouth(), b.getEast()], ...extra]);
}

function drawRoute(coords) {
  S.layers.route.clearLayers();
  if (!coords || coords.length < 2) return;
  L.polyline(coords, { color: "#ffffff", weight: 9, opacity: 0.9 }).addTo(S.layers.route);
  L.polyline(coords, { color: "#2f6fed", weight: 5, opacity: 0.95 }).addTo(S.layers.route);
}

function abMarker(lat, lon, label, cls = "") {
  return L.marker([lat, lon], {
    icon: L.divIcon({ className: "", html: `<div class="ab-marker ${cls}">${label}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] }),
    interactive: false,
  });
}

function updateMe(loc) {
  if (!loc) return;
  if (!S.me) {
    S.me = L.marker([loc.lat, loc.lon], {
      icon: L.divIcon({ className: "", html: '<div class="me-marker"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }),
      interactive: false, zIndexOffset: 500,
    }).addTo(S.map);
  } else S.me.setLatLng([loc.lat, loc.lon]);
}

/** Mashina belgisi: yangi nuqtaga silliq siljiydi va yo'nalish bo'yicha buriladi. */
class AnimatedCar {
  constructor(lat, lon, heading) {
    this.pos = [lat, lon];
    this.heading = heading || 0;
    this.marker = L.marker(this.pos, {
      icon: L.divIcon({ className: "", html: `<div class="car-marker">${CAR_SVG}</div>`, iconSize: [34, 34], iconAnchor: [17, 17] }),
      interactive: false, zIndexOffset: 400,
    });
    this.marker.on("add", () => this.rotate(this.heading));
  }
  addTo(layer) { this.marker.addTo(layer); this.rotate(this.heading); return this; }
  rotate(deg) {
    const el = this.marker.getElement();
    const body = el && el.querySelector(".car-body");
    if (body) body.style.transform = `rotate(${deg}deg)`;
  }
  moveTo(lat, lon, heading) {
    const from = this.pos.slice();
    const dist = Math.hypot(lat - from[0], lon - from[1]);
    if (dist < 1e-7) return;
    let h = heading;
    if (h == null || h === 0) h = (Math.atan2(lon - from[1], lat - from[0]) * 180) / Math.PI;
    this.heading = h;
    this.rotate(h);
    const start = performance.now();
    const dur = 1800;
    const step = (t) => {
      const k = Math.min(1, (t - start) / dur);
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      this.pos = [from[0] + (lat - from[0]) * e, from[1] + (lon - from[1]) * e];
      this.marker.setLatLng(this.pos);
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
}

function setCar(lat, lon, heading) {
  if (lat == null) { if (S.car) { S.layers.markers.removeLayer(S.car.marker); S.car = null; } return; }
  if (!S.car) S.car = new AnimatedCar(lat, lon, heading).addTo(S.layers.markers);
  else S.car.moveTo(lat, lon, heading);
}

function drawNearby(cars) {
  S.layers.cars.clearLayers();
  for (const c of cars || []) new AnimatedCar(c.lat, c.lon, c.heading).addTo(S.layers.cars);
}

function radar(on, lat, lon) {
  S.layers.radar.clearLayers();
  if (!on) return;
  for (const cls of ["radar-ring", "radar-ring r2"]) {
    L.marker([lat, lon], {
      icon: L.divIcon({ className: "", html: `<div class="${cls}"></div>`, iconSize: [160, 160], iconAnchor: [80, 80] }),
      interactive: false,
    }).addTo(S.layers.radar);
  }
}

async function routeBetween(a, b, force = false) {
  const key = `${a[0].toFixed(4)},${a[1].toFixed(4)}>${b[0].toFixed(4)},${b[1].toFixed(4)}`;
  if (!force && key === S.lastRouteKey && Date.now() - S.lastRouteAt < 20000) return;
  S.lastRouteKey = key;
  S.lastRouteAt = Date.now();
  try {
    const r = await api("/api/route", { a, b });
    drawRoute(r.route);
  } catch { drawRoute([a, b]); }
}

// ====================================================================== bottom sheet
function sheet(html) {
  $("#sheet-body").innerHTML = html;
  requestAnimationFrame(layoutOverlays);
}
function on(id, fn) { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); }

const geoCache = new Map();
async function reverse(lat, lon) {
  const key = `${lat.toFixed(4)},${lon.toFixed(4)}`;
  if (geoCache.has(key)) return geoCache.get(key);
  try {
    const r = await api(`/api/reverse?lat=${lat}&lon=${lon}`);
    const v = r && r.title ? r : null;
    geoCache.set(key, v);
    return v;
  } catch { return null; }
}

// ====================================================================== YO'LOVCHI
let reverseTimer = null;

// ---------------------------------------------------------------- rolni almashtirish (bitta bot rejimi)
function roleChip() {
  if (!S.config || !S.config.single_bot) return "";
  return S.app === "driver"
    ? `<button class="chip-btn role" id="switch-role">🙋 Yo'lovchi rejimi</button>`
    : `<button class="chip-btn role" id="switch-role">🚕 Haydovchi rejimi</button>`;
}

async function switchRole() {
  const next = S.app === "driver" ? "passenger" : "driver";
  const ok = await confirmBox(next === "driver"
    ? "Haydovchi rejimiga o'tasizmi?"
    : "Yo'lovchi rejimiga o'tasizmi? Liniyadan chiqasiz — buyurtmalar kelmaydi.");
  if (!ok) return;
  const prev = S.app;
  S.app = next;
  try {
    await api("/api/me"); // tanlov saqlanadi: keyingi safar ilova shu rejimda ochiladi
  } catch (e) {
    S.app = prev;
    return toast(e.message, true);
  }
  haptic("success");
  // #tgWebAppData (hash) saqlanadi — Telegram ma'lumotlari qayta yuklashda yo'qolmaydi
  location.replace(`${location.pathname}?app=${next}${location.hash}`);
}

function passengerTop() {
  $("#top").innerHTML = roleChip();
  on("switch-role", switchRole);
}

async function passengerStart() {
  passengerTop();
  const state = await api("/api/p/state");
  S.state = state;
  if (!state.registered) return renderPhoneShare("passenger");
  S.location = await locate();
  const start = S.location || (state.places[0] ? { lat: state.places[0].lat, lon: state.places[0].lon } : { lat: 41.3111, lon: 69.2797 });
  if (!S.location) toast("Joylashuv aniqlanmadi — xaritada olish joyini belgilang", true);
  S.map.setView([start.lat, start.lon], 15.5, { animate: false });
  updateMe(S.location);
  S.pickup = { lat: start.lat, lon: start.lon, accuracy: S.location ? S.location.accuracy : null, title: null };
  if (state.order || state.rate_order) renderPassengerOrder(state);
  else enterHome();
  setInterval(passengerPoll, 2500);
}

async function passengerPoll() {
  if (S.pollBusy || document.hidden) return;
  if (!["order", "home", "rate"].includes(S.mode)) return;
  S.pollBusy = true;
  try {
    const state = await api("/api/p/state");
    S.state = state;
    if (state.order || state.rate_order) renderPassengerOrder(state);
    else if (S.mode === "order" || S.mode === "rate") { resetMap(); enterHome(); }
    else if (S.mode === "home" && S.pickup) refreshNearby();
  } catch { /* tarmoq vaqtincha yo'q */ }
  S.pollBusy = false;
}

function resetMap() {
  S.layers.route.clearLayers();
  S.layers.markers.clearLayers();
  S.layers.radar.clearLayers();
  S.car = null;
  S.order = null;
}

let nearbyAt = 0;
async function refreshNearby(force = false) {
  if (!force && Date.now() - nearbyAt < 8000) return;
  nearbyAt = Date.now();
  try {
    const cars = await api(`/api/p/nearby?lat=${S.pickup.lat}&lon=${S.pickup.lon}`);
    drawNearby(cars);
    let best = null;
    for (const c of cars) {
      const d = Math.hypot((c.lat - S.pickup.lat) * 111, (c.lon - S.pickup.lon) * 84);
      best = best == null ? d : Math.min(best, d);
    }
    if (S.mode === "home") $("#pin-bubble").textContent = best == null ? "Mashina qidiramiz" : `${Math.max(1, Math.round((best * 1.3) / 0.42))} daq`;
  } catch { /* ixtiyoriy */ }
}

function enterHome() {
  S.mode = "home";
  S.dest = null;
  S.quote = null;
  Second.hide();
  Back.hide();
  drawRoute(null);
  S.layers.markers.clearLayers();
  showPin("pickup", "");
  S.pinHandler = (c) => {
    // GPS nuqtasiga 15 m dan yaqin bo'lsa — aynan GPS koordinatasi (aniqlik saqlanadi)
    const g = S.location;
    const near = g && Math.hypot((c.lat - g.lat) * 111320, (c.lon - g.lon) * 111320 * Math.cos((g.lat * Math.PI) / 180)) < 15;
    S.pickup = near ? { lat: g.lat, lon: g.lon, accuracy: g.accuracy, title: null } : { lat: c.lat, lon: c.lon, accuracy: null, title: null };
    renderHome();
    clearTimeout(reverseTimer);
    reverseTimer = setTimeout(async () => {
      const r = await reverse(c.lat, c.lon);
      if (r && S.mode === "home") { S.pickup.title = r.title; S.pickup.subtitle = r.subtitle; renderHome(); }
    }, 450);
    refreshNearby(true);
  };
  const target = S.pickup || visibleCenter();
  S.pinHandler(target);
  centerOn(target.lat, target.lon, 15.5);
  Main.set("🚕 Taksi chaqirish · taksometr", () => placeOrder(), {});
}

function placeChips() {
  const st = S.state || { places: [], recent: [] };
  const icons = { home: "🏠", work: "🏢", other: "📌" };
  const chips = st.places.map((p) => `<button class="chip ${p.kind}" data-lat="${p.lat}" data-lon="${p.lon}" data-title="${esc(p.title)}">${icons[p.kind] || "📌"} ${esc(p.title)}</button>`);
  for (const r of st.recent) chips.push(`<button class="chip" data-lat="${r.lat}" data-lon="${r.lon}" data-title="${esc(r.title)}">🕘 ${esc(r.title)}</button>`);
  return chips.join("");
}

function renderHome() {
  const p = S.pickup || {};
  sheet(`
    <button class="field" id="pickup-field"><span class="icon">🟡</span><span class="txt">
      <div class="t1">${esc(p.title || "Olish joyi aniqlanmoqda…")}</div>
      <div class="t2">${esc(p.subtitle || "Xaritani surib aniq nuqtani tanlang")}</div></span></button>
    <button class="field" id="dest-field"><span class="icon">🏁</span><span class="txt"><div class="t1 muted">Qayerga boramiz?</div></span><span>›</span></button>
    <div class="chips" id="chips">${placeChips()}</div>
    <div class="muted small mt">Manzilni tanlang — narx darhol chiqadi. Yoki pastdagi tugma bilan taksometrda chaqiring.</div>`);
  on("dest-field", openSearch);
  on("pickup-field", () => toast("Xaritani surib olish joyini aniqlang"));
  $("#chips").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-lat]");
    if (b) { haptic(); setDest({ lat: +b.dataset.lat, lon: +b.dataset.lon, title: b.dataset.title }); }
  });
}

// ---------- qidiruv
let searchTimer = null;
function openSearch() {
  S.mode = "search";
  $("#search").hidden = false;
  const input = $("#search-input");
  input.value = "";
  renderSearchResults([]);
  setTimeout(() => input.focus(), 50);
  Main.hide();
  Back.show(closeSearch);
}
function closeSearch() {
  $("#search").hidden = true;
  $("#search-input").blur();
  enterHome();
}
function renderSearchResults(items) {
  const st = S.state || { places: [], recent: [] };
  const fixed = [`<button class="result" data-act="pick"><span class="icon">📍</span><span><b>Xaritada belgilash</b><div class="muted small">Nuqtani xaritada tanlang</div></span></button>`];
  if (!items.length) {
    for (const p of st.places) fixed.push(resultRow({ title: p.title, subtitle: "Saqlangan manzil", lat: p.lat, lon: p.lon }, p.kind === "home" ? "🏠" : p.kind === "work" ? "🏢" : "📌"));
    for (const r of st.recent) fixed.push(resultRow({ title: r.title, subtitle: "Oxirgi safar", lat: r.lat, lon: r.lon }, "🕘"));
  }
  $("#search-results").innerHTML = fixed.join("") + items.map((r) => resultRow(r, "📍")).join("");
}
function resultRow(r, icon) {
  return `<button class="result" data-lat="${r.lat}" data-lon="${r.lon}" data-title="${esc(r.title)}"><span class="icon">${icon}</span>
    <span><b>${esc(r.title)}</b><div class="muted small">${esc(r.subtitle || "")}</div></span></button>`;
}
function initSearch() {
  $("#search-input").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    searchTimer = setTimeout(async () => {
      if (q.length < 2) return renderSearchResults([]);
      try {
        const near = S.pickup ? `&lat=${S.pickup.lat}&lon=${S.pickup.lon}` : "";
        renderSearchResults(await api(`/api/geocode?q=${encodeURIComponent(q)}${near}`));
      } catch { renderSearchResults([]); }
    }, 380);
  });
  $("#search-results").addEventListener("click", (e) => {
    const b = e.target.closest("button.result");
    if (!b) return;
    haptic();
    $("#search").hidden = true;
    if (b.dataset.act === "pick") return enterPickDest();
    setDest({ lat: +b.dataset.lat, lon: +b.dataset.lon, title: b.dataset.title });
  });
}

function enterPickDest() {
  S.mode = "pickdest";
  showPin("dest", "Manzil");
  S.pinHandler = async (c) => {
    S.pending = c;
    const r = await reverse(c.lat, c.lon);
    if (S.mode !== "pickdest") return;
    sheet(`<h3>Manzilni belgilang</h3><button class="field"><span class="icon">🏁</span><span class="txt">
      <div class="t1">${esc((r && r.title) || "Belgilangan nuqta")}</div><div class="t2">${esc((r && r.subtitle) || "")}</div></span></button>`);
    S.pending.title = r && r.title;
  };
  sheet(`<h3>Manzilni belgilang</h3><div class="muted small">Xaritani surib, ninani manzilga qo'ying</div>`);
  S.pinHandler(visibleCenter());
  Main.set("Shu yerga borish", () => setDest(S.pending || visibleCenter()));
  Back.show(() => { hidePin(); enterHome(); });
}

// ---------- narx
async function setDest(dest) {
  S.mode = "quote";
  S.dest = dest;
  hidePin();
  S.layers.cars.clearLayers();
  S.layers.markers.clearLayers();
  abMarker(S.pickup.lat, S.pickup.lon, "A").addTo(S.layers.markers);
  abMarker(dest.lat, dest.lon, "B", "b").addTo(S.layers.markers);
  sheet(`<div class="row between"><h2>Narx hisoblanmoqda…</h2></div><div class="searching-line"><i></i></div>`);
  Back.show(() => enterHome());
  Second.hide();
  try {
    const q = await api("/api/p/quote", { pickup: S.pickup, dest });
    if (S.mode !== "quote") return;
    S.quote = q;
    drawRoute(q.route);
    fitTo([[S.pickup.lat, S.pickup.lon], [dest.lat, dest.lon]]);
    renderQuote();
  } catch (e) { toast(e.message, true); enterHome(); }
}

function renderQuote() {
  const q = S.quote;
  const t = S.config.tariff;
  sheet(`
    <div class="row between"><div><div class="muted small">${esc(S.dest.title || "Manzil")}</div><div class="price">${money(q.price)}</div></div>
      <div class="muted small right">🔒 Qat'iy narx</div></div>
    <div class="kv"><div><b>${km(q.distance_m)}</b><span>masofa</span></div><div><b>${mins(q.duration_s)}</b><span>yo'lda</span></div>
      <div><b>${q.nearby ? mins(q.nearest_eta_s) : "—"}</b><span>${q.nearby ? `${q.nearby} ta mashina yaqin` : "yaqinda yo'q"}</span></div></div>
    <div class="field"><span class="icon">💬</span><span class="txt"><input id="comment" maxlength="200" placeholder="Haydovchiga izoh (masalan: 3-podyezd)"></span></div>
    <div class="field"><span class="icon">👤</span><span class="txt"><input id="rider" inputmode="tel" maxlength="20" placeholder="Boshqa odam uchun? Raqamini yozing"></span></div>
    <div class="muted small mt">Kutish: ${t.free_wait_min} daq bepul, keyin ${money(t.per_wait_min)}/daq</div>`);
  Main.set(`Buyurtma berish · ${money(q.price)}`, () => placeOrder(S.dest), {});
}

async function placeOrder(dest = null) {
  const body = { pickup: S.pickup, dest };
  const comment = $("#comment");
  const rider = $("#rider");
  if (comment && comment.value.trim()) body.comment = comment.value.trim();
  if (rider && rider.value.trim()) body.rider_phone = rider.value.trim();
  try {
    await api("/api/p/order", body);
    haptic("success");
    hidePin();
    S.layers.cars.clearLayers();
    S.state = await api("/api/p/state");
    renderPassengerOrder(S.state);
  } catch (e) { toast(e.message, true); }
}

// ---------- buyurtma holatlari
function renderPassengerOrder(state) {
  Back.hide();
  if (!state.order && state.rate_order) return renderRate(state.rate_order);
  const o = state.order;
  const first = !S.order || S.order.id !== o.id || S.order.status !== o.status;
  S.order = o;
  S.mode = "order";
  hidePin();
  $("#search").hidden = true;
  const pickup = [o.pickup.lat, o.pickup.lon];
  const dest = o.dest ? [o.dest.lat, o.dest.lon] : null;
  if (first) {
    S.layers.markers.clearLayers();
    S.car = null;
    abMarker(pickup[0], pickup[1], "A").addTo(S.layers.markers);
    if (dest) abMarker(dest[0], dest[1], "B", "b").addTo(S.layers.markers);
    haptic(o.status === "searching" ? "light" : "success");
  }
  const d = o.driver;
  radar(o.status === "searching", pickup[0], pickup[1]);
  if (o.status !== "searching") S.layers.cars.clearLayers();
  if (d && d.lat != null) setCar(d.lat, d.lon, d.heading);
  const carPos = d && d.lat != null ? [d.lat, d.lon] : null;

  if (o.status === "searching") {
    const s = o.search || {};
    if (first) { drawRoute(null); fitCircle(pickup[0], pickup[1], Math.min(s.radius_m || 1000, 2500)); refreshNearbyFor(pickup); }
    sheet(`<h2>Haydovchi qidirilmoqda</h2><div class="muted">Eng yaqin va reytingi yuqori haydovchilar birinchi ko'radi</div>
      <div class="searching-line"><i></i></div>
      <div class="kv"><div><b>${km(s.radius_m)}</b><span>radius</span></div><div><b>${s.offered || 0}</b><span>taklif yuborildi</span></div>
      <div><b>${o.price ? money(o.price) : "taksometr"}</b><span>narx</span></div></div>`);
    Main.hide();
    Second.set("Bekor qilish", () => cancelOrder(o), { color: "#f2f3f5", textColor: "#e5453b" });
    return;
  }
  if (o.status === "no_drivers") {
    sheet(`<h2>Hozircha bo'sh mashina yo'q</h2><div class="muted">Bir ozdan so'ng qayta urinib ko'ring — haydovchilar doimiy bo'shab turadi.</div>`);
    Main.set("🔄 Qayta qidirish", () => act("retry", o.id));
    Second.set("Yopish", () => cancelOrder(o, true), { color: "#f2f3f5", textColor: "#111111" });
    return;
  }
  const carHtml = d ? `<div class="car"><div class="flex1"><div class="t1"><b>${esc(d.car)}</b></div>
      <div class="muted small">⭐ ${Number(d.rating).toFixed(2)}</div></div><span class="plate">${esc(d.plate)}</span></div>` : "";
  if (o.status === "accepted") {
    if (carPos) { routeBetween(carPos, pickup); if (first) fitTo([carPos, pickup]); } else if (first) fitTo([pickup]);
    sheet(`<div class="row between"><h2>Haydovchi yo'lda</h2><div class="eta-big">${o.eta_s != null ? mins(o.eta_s) : ""}</div></div>
      ${carHtml}<div class="btns"><button class="btn" id="call">📞 Aloqa</button><button class="btn red" id="cancel">Bekor qilish</button></div>`);
  } else if (o.status === "arrived") {
    drawRoute(null);
    if (first) fitTo([pickup]);
    const free = o.free_wait_left_s;
    sheet(`<h2>Haydovchi sizni kutmoqda</h2>${carHtml}
      <div class="note">${free > 0 ? `⏳ Bepul kutish: ${Math.ceil(free / 60)} daq qoldi` : `⏳ Pullik kutish boshlandi: ${money(S.config.tariff.per_wait_min)}/daq`}</div>
      <div class="btns"><button class="btn" id="call">📞 Aloqa</button><button class="btn red" id="cancel">Bekor qilish</button></div>`);
  } else if (o.status === "in_progress") {
    if (carPos && dest) { routeBetween(carPos, dest); if (first) fitTo([carPos, dest]); } else if (first && carPos) fitTo([carPos]);
    sheet(`<div class="row between"><h2>Safardamiz</h2><div class="eta-big">${o.eta_s != null ? mins(o.eta_s) : ""}</div></div>
      ${carHtml}<div class="muted small">${o.fixed_price ? `Narx: ${money(o.price)}` : "Narx taksometr bo'yicha hisoblanadi"}</div>
      <div class="btns"><button class="btn" id="call">📞 Aloqa</button><button class="btn" id="noop" disabled>🛣 ${km(o.trip_distance_m)}</button></div>`);
    Main.set("🏁 Manzilga yetib keldim", () => act("arrived", o.id), { color: "#22a447", textColor: "#ffffff" });
    Second.hide();
    on("call", () => call(o));
    return;
  } else if (o.status === "finishing") {
    sheet(`<h2>Manzilga yetib keldingizmi?</h2>${carHtml}
      <div class="price">${money(o.final_price)}</div>
      <div class="muted small">${o.wait_charge ? `shundan kutish: ${money(o.wait_charge)} · ` : ""}${km(o.trip_distance_m)}</div>
      <div class="note">To'lovni haydovchiga bering. Tasdiqlaganingizdan so'ng safar yakunlanadi.</div>`);
    Main.set("✅ Ha, yetib keldim", () => act("arrived", o.id), { color: "#22a447", textColor: "#ffffff" });
    Second.set("Yo'q, hali emas", () => act("notyet", o.id), { color: "#f2f3f5", textColor: "#e5453b" });
    return;
  }
  Main.hide();
  Second.hide();
  on("call", () => call(o));
  on("cancel", () => cancelOrder(o));
}

async function refreshNearbyFor(pickup) {
  try { drawNearby(await api(`/api/p/nearby?lat=${pickup[0]}&lon=${pickup[1]}`)); } catch { /* ixtiyoriy */ }
}

async function act(action, orderId, extra = {}) {
  try {
    await api(`/api/p/${action}`, { order_id: orderId, ...extra });
    haptic("success");
    S.state = await api("/api/p/state");
    if (S.state.order || S.state.rate_order) renderPassengerOrder(S.state); else { resetMap(); enterHome(); }
  } catch (e) { toast(e.message, true); }
}

async function cancelOrder(o, silent = false) {
  if (!silent && !(await confirmBox("Buyurtmani bekor qilasizmi?"))) return;
  await act("cancel", o.id, { confirmed: true });
}

async function call(o) {
  try {
    const r = await api("/api/p/call", { order_id: o.id });
    if (tg && tg.showAlert) tg.showAlert(r.message); else toast(r.message);
  } catch (e) { toast(e.message, true); }
}

function renderRate(o) {
  S.mode = "rate";
  S.layers.radar.clearLayers();
  setCar(null);
  drawRoute(null);
  Second.hide();
  let stars = 5;
  const draw = () => $$stars().forEach((b, i) => b.classList.toggle("on", i < stars));
  sheet(`<h2>Safar yakunlandi 🎉</h2><div class="price">${money(o.final_price || o.price)}</div>
    ${o.driver ? `<div class="car"><div class="flex1"><b>${esc(o.driver.car)}</b></div><span class="plate">${esc(o.driver.plate)}</span></div>` : ""}
    <div class="muted center">Haydovchini baholang</div>
    <div class="stars" id="stars">${[1, 2, 3, 4, 5].map((n) => `<button data-n="${n}">⭐</button>`).join("")}</div>
    <div class="btns">${o.favorite ? '<button class="btn" disabled>❤️ Sevimli</button>' : '<button class="btn" id="fav">❤️ Sevimlilarga</button>'}
      ${o.dest ? '<button class="btn" id="save-home">💾 Uy deb saqlash</button>' : '<button class="btn" disabled>—</button>'}</div>`);
  draw();
  $("#stars").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { stars = +b.dataset.n; haptic(); draw(); } });
  on("fav", async () => { try { await api("/api/p/favorite", { order_id: o.id }); haptic("success"); toast("❤️ Sevimlilarga qo'shildi"); } catch (e) { toast(e.message, true); } });
  on("save-home", async () => {
    try { await api("/api/p/places", { kind: "home", lat: o.dest.lat, lon: o.dest.lon }); haptic("success"); toast("🏠 Uy manzili saqlandi"); } catch (e) { toast(e.message, true); }
  });
  Main.set("Baholash", async () => {
    try { await api("/api/p/rate", { order_id: o.id, stars }); haptic("success"); toast("Rahmat! 🙏"); } catch { /* allaqachon */ }
    S.state = await api("/api/p/state");
    resetMap();
    enterHome();
  });
}
function $$stars() { return Array.from(document.querySelectorAll("#stars button")); }

// ====================================================================== telefon raqam
function renderPhoneShare(app) {
  S.mode = "phone";
  sheet(`<h2>Xush kelibsiz! 👋</h2><div class="muted">Boshlash uchun telefon raqamingizni ulashing. U ${app === "driver" ? "yo'lovchilarga" : "haydovchiga"} ko'rinmaydi —
    aloqa kompaniya raqami orqali bo'ladi.</div>`);
  Main.set("📱 Raqamni ulashish", () => new Promise((resolve) => {
    if (!tg || !tg.requestContact) { toast("Telegram'ni yangilang", true); return resolve(); }
    tg.requestContact(async (shared, res) => {
      if (shared && res && res.response) {
        try { await api("/api/contact", { response: res.response }); } catch { /* bot orqali ham keladi */ }
      }
      await sleep(shared ? 800 : 0);
      resolve();
      if (shared) location.reload();
    });
  }));
}

// ====================================================================== HAYDOVCHI
let locTimer = null;

async function driverStart() {
  S.location = await locate();
  if (S.location) { S.map.setView([S.location.lat, S.location.lon], 16, { animate: false }); updateMe(S.location); }
  else toast("Joylashuvga ruxsat bering — buyurtmalar joylashuv bo'yicha keladi", true);
  await driverRefresh();
  setInterval(driverRefresh, 2500);
  locTimer = setInterval(driverLocationTick, 4000);
}

async function driverLocationTick() {
  if (document.hidden || !S.dstate || !S.dstate.driver) return;
  const d = S.dstate.driver;
  if (!d.online && !S.dstate.order) return;
  const loc = await locate();
  if (!loc) return;
  S.location = loc;
  updateMe(loc);
  try { await api("/api/d/location", loc); } catch { /* keyingi safar */ }
}

async function driverRefresh() {
  if (S.pollBusy || document.hidden) return;
  S.pollBusy = true;
  try {
    const st = await api("/api/d/state");
    S.dstate = st;
    renderDriver(st);
  } catch (e) { if (S.mode === "boot") toast(e.message, true); }
  S.pollBusy = false;
}

function driverTop(d) {
  $("#top").innerHTML = d ? `<button class="chip-btn" id="bal">💳 ${money(d.balance)}</button>
    <button class="chip-btn"><span class="status-pill"><i class="dot ${d.online ? "on" : ""}"></i>${d.online ? "Liniyada" : "Oflayn"}</span></button>
    <button class="chip-btn" id="settings">⚙️</button>` : roleChip();
  on("settings", renderDriverSettings);
  on("switch-role", switchRole);
  on("bal", () => toast(`Balans: ${money(d.balance)} · minimal: ${money(S.config.min_driver_balance)}`));
}

function renderDriver(st) {
  if (S.mode === "settings" || S.mode === "register") return;
  if (!st.registered) {
    driverTop(null);
    return st.phone ? renderDriverRegister() : renderPhoneShare("driver");
  }
  const d = st.driver;
  driverTop(d);
  if (d.status === "pending") {
    S.mode = "pending";
    Main.hide();
    return sheet(`<h2>Arizangiz ko'rib chiqilmoqda ⏳</h2><div class="muted">Tasdiqlangach shu yerda va Telegram'da xabar olasiz.
      ${S.config.welcome_bonus ? `Tasdiqlangach balansingizga ${money(S.config.welcome_bonus)} bonus tushadi.` : ""}</div>`);
  }
  if (d.status !== "approved") {
    Main.hide();
    return sheet(`<h2>Hisob faol emas</h2><div class="muted">Arizangiz ${d.status === "blocked" ? "bloklangan" : "rad etilgan"}. Operatorga murojaat qiling.</div>`);
  }
  if (st.order) return renderDriverOrder(st.order, d);
  if (st.offers.length) return renderOffer(st.offers, d);
  renderDriverIdle(st, d);
}

function renderDriverIdle(st, d) {
  if (S.mode !== "idle") { S.layers.markers.clearLayers(); drawRoute(null); S.car = null; }
  S.mode = "idle";
  Second.hide();
  const s = st.stats || {};
  const low = d.balance < S.config.min_driver_balance;
  sheet(`<div class="row between"><h2>${d.online ? "Buyurtma kutilmoqda" : "Salom, " + esc(d.name.split(" ")[0])}</h2>
      <span class="muted small">⭐ ${Number(d.rating).toFixed(2)}</span></div>
    ${d.online && !d.location_fresh ? '<div class="warn">📍 Joylashuv yangilanmayapti — ilovani ochiq tuting yoki Telegram\'da jonli joylashuvni ulashing</div>' : ""}
    ${low ? `<div class="warn">💳 Balans yetarli emas (${money(d.balance)}). Buyurtma olish uchun to'ldiring.</div>` : ""}
    <div class="kv"><div><b>${s.today_trips || 0}</b><span>bugungi safar</span></div><div><b>${num(s.today_income || 0)}</b><span>bugungi tushum</span></div>
      <div><b>${S.config.commission_percent}%</b><span>xizmat haqi</span></div></div>
    <button class="big-toggle ${d.online ? "on" : "off"}" id="toggle">${d.online ? "🔴 Liniyadan chiqish" : "🟢 Liniyaga chiqish"}</button>
    ${d.online ? '<div class="muted small mt">Ilova yopilsa ham buyurtma olish uchun Telegram\'da «Jonli joylashuv» ni ulashing.</div>' : ""}`);
  Main.hide();
  on("toggle", toggleOnline);
}

async function toggleOnline() {
  const d = S.dstate.driver;
  haptic("medium");
  try {
    if (d.online) await api("/api/d/online", { online: false });
    else {
      const loc = await locate();
      if (!loc) return toast("Joylashuvga ruxsat bering", true);
      S.location = loc;
      updateMe(loc);
      centerOn(loc.lat, loc.lon, 16);
      await api("/api/d/online", { online: true, ...loc });
      haptic("success");
    }
  } catch (e) { toast(e.message, true); }
  await driverRefresh();
}

function renderOffer(offers, d) {
  const o = offers[0];
  const isNew = S.mode !== "offer" || !S.offer || S.offer.order_id !== o.order_id;
  S.mode = "offer";
  S.offer = o;
  if (isNew) {
    haptic("warning");
    S.layers.markers.clearLayers();
    L.circle(o.approx, { radius: 250, color: "#f08c00", weight: 2, fillOpacity: 0.15, dashArray: "6 6" }).addTo(S.layers.markers);
    fitCircle(o.approx[0], o.approx[1], 400, [S.location ? [S.location.lat, S.location.lon] : null]);
  }
  const age = (Date.now() - new Date(o.sent_at).getTime()) / 1000;
  const left = Math.max(0, 1 - age / 60);
  sheet(`<div class="row between"><h2>Yangi buyurtma</h2><span class="muted small">${offers.length > 1 ? `+${offers.length - 1} ta yana` : ""}</span></div>
    <div class="offer-timer"><i></i></div>
    <div class="kv"><div><b>${km(o.distance_m)}</b><span>${mins(o.eta_s)} · ${esc(o.direction)}</span></div>
      <div><b>${o.trip_distance_m ? km(o.trip_distance_m) : "—"}</b><span>${o.trip_direction ? esc(o.trip_direction) : "manzil ko'rsatilmagan"}</span></div>
      <div><b>${o.price ? num(o.price) : "taksometr"}</b><span>${o.price ? S.config.currency : "narx"}</span></div></div>
    ${o.comment ? `<div class="note">💬 ${esc(o.comment)}</div>` : ""}
    ${o.rider ? '<span class="badge">👤 Boshqa odam uchun</span>' : ""}
    <div class="muted small mt">Aniq manzil qabul qilgandan so'ng ochiladi. O'tkazib yuborish uchun jarima yo'q.</div>`);
  const bar = document.querySelector(".offer-timer i");
  if (bar) bar.style.transform = `scaleX(${left})`;
  Main.set("✅ Qabul qilish", async () => {
    try { await api(`/api/d/offers/${o.order_id}/accept`, {}); haptic("success"); } catch (e) { toast(e.message, true); }
    await driverRefresh();
  }, { color: "#22a447", textColor: "#ffffff" });
  Second.set("O'tkazib yuborish", async () => {
    try { await api(`/api/d/offers/${o.order_id}/decline`, {}); } catch { /* eskirgan */ }
    await driverRefresh();
  }, { color: "#f2f3f5", textColor: "#111111" });
}

function navUrl(nav, lat, lon) {
  const ll = `${lat.toFixed(6)}%2C${lon.toFixed(6)}`;
  if (nav === "yandex") return `https://yandex.uz/maps/?rtext=~${ll}&rtt=auto`;
  if (nav === "waze") return `https://waze.com/ul?ll=${ll}&navigate=yes`;
  return `https://www.google.com/maps/dir/?api=1&destination=${ll}&travelmode=driving&dir_action=navigate`;
}

function renderDriverOrder(o, d) {
  const first = S.mode !== "dorder" || !S.order || S.order.id !== o.id || S.order.status !== o.status;
  S.mode = "dorder";
  S.order = o;
  const pickup = [o.pickup.lat, o.pickup.lon];
  const dest = o.dest ? [o.dest.lat, o.dest.lon] : null;
  const me = S.location ? [S.location.lat, S.location.lon] : null;
  if (first) {
    haptic("success");
    S.layers.markers.clearLayers();
    abMarker(pickup[0], pickup[1], "A").addTo(S.layers.markers);
    if (dest) abMarker(dest[0], dest[1], "B", "b").addTo(S.layers.markers);
  }
  const steps = ["accepted", "arrived", "in_progress", "finishing"];
  const idx = steps.indexOf(o.status);
  const stepper = `<div class="steps">${steps.map((_, i) => `<i class="${i <= idx ? "done" : ""}"></i>`).join("")}</div>`;
  const target = o.status === "in_progress" && dest ? dest : pickup;
  if (me && o.status !== "finishing") { routeBetween(me, target); if (first) fitTo([me, target]); }
  else if (first) fitTo([target]);
  const navBtn = `<button class="btn" id="nav">🧭 Navigator</button>`;
  const callBtn = `<button class="btn" id="call">📞 Aloqa</button>`;
  if (o.status === "accepted") {
    sheet(`${stepper}<h2>Yo'lovchi oldiga</h2><div class="muted" id="addr">Manzil aniqlanmoqda…</div>
      ${o.comment ? `<div class="note">💬 ${esc(o.comment)}</div>` : ""}${o.rider ? '<span class="badge">👤 Boshqa odam uchun</span>' : ""}
      <div class="btns">${navBtn}${callBtn}</div><button class="btn red mt" id="dcancel">Bekor qilish</button>`);
    reverse(pickup[0], pickup[1]).then((r) => { const el = $("#addr"); if (el && r) el.textContent = `📍 ${r.title}${r.subtitle ? ", " + r.subtitle : ""}`; });
    Main.set("✅ Yetib keldim", () => dAct("arrived", o.id), { color: "#2f6fed", textColor: "#ffffff" });
    Second.hide();
  } else if (o.status === "arrived") {
    const waited = o.arrived_at ? (Date.now() - new Date(o.arrived_at).getTime()) / 60000 : 0;
    sheet(`${stepper}<h2>Yo'lovchi kutilmoqda</h2>
      <div class="note">⏳ ${Math.floor(waited)} daq kutildi · ${o.free_wait_min} daq bepul</div>
      ${o.comment ? `<div class="note">💬 ${esc(o.comment)}</div>` : ""}
      <div class="btns">${callBtn}<button class="btn red" id="noshow" ${waited < o.no_show_wait_min ? "disabled" : ""}>🚫 Chiqmadi</button></div>`);
    Main.set("🚀 Safarni boshlash", () => dAct("start", o.id), { color: "#22a447", textColor: "#ffffff" });
    Second.hide();
  } else if (o.status === "in_progress") {
    const t = o.taximeter || {};
    sheet(`${stepper}<h2>Safar davom etmoqda</h2>
      <div class="kv"><div><b>${km(t.distance_m)}</b><span>bosib o'tildi</span></div><div><b>${t.minutes || 0} daq</b><span>yo'lda</span></div>
        <div><b>${num(o.fixed_price ? o.price : t.price)}</b><span>${o.fixed_price ? "qat'iy narx" : "taksometr"}</span></div></div>
      <div class="btns">${dest ? navBtn : ""}${callBtn}</div>`);
    Main.set("🏁 Safarni yakunlash", () => dAct("finish", o.id), { color: "#e5453b", textColor: "#ffffff" });
    Second.hide();
  } else {
    sheet(`${stepper}<h2>Yo'lovchi tasdig'i kutilmoqda</h2><div class="price">${money(o.price)}</div>
      <div class="note">🟢 Siz bo'shsiz — yangi buyurtmalar kelaveradi. Xizmat haqi tasdiqdan keyin yechiladi.</div>`);
    Main.hide();
    Second.hide();
  }
  on("nav", () => openLink(navUrl(d.navigator, target[0], target[1])));
  on("call", async () => {
    try { const r = await api(`/api/d/orders/${o.id}/call`, {}); if (tg && tg.showAlert) tg.showAlert(r.message); else toast(r.message); }
    catch (e) { toast(e.message, true); }
  });
  on("dcancel", async () => { if (await confirmBox("Buyurtmani bekor qilasizmi? Yo'lovchiga boshqa haydovchi qidiriladi.")) dAct("cancel", o.id); });
  on("noshow", async () => { if (await confirmBox("Yo'lovchi chiqmadimi? Buyurtma yopiladi.")) dAct("noshow", o.id); });
}

async function dAct(action, orderId) {
  try { await api(`/api/d/orders/${orderId}/${action}`, {}); haptic("success"); } catch (e) { toast(e.message, true); }
  await driverRefresh();
}

function renderDriverRegister() {
  S.mode = "register";
  const models = ["Cobalt", "Nexia 3", "Gentra", "Lacetti", "Spark", "Onix", "Malibu", "Tracker", "Damas"];
  const colors = ["Oq", "Qora", "Kumush", "Kulrang", "Ko'k", "Qizil", "Jigarrang"];
  sheet(`<h2>Haydovchi sifatida ro'yxatdan o'tish</h2><div class="form">
    <label>Ism-familiya</label><input id="f-name" maxlength="60" value="${esc((tg && tg.initDataUnsafe && tg.initDataUnsafe.user && [tg.initDataUnsafe.user.first_name, tg.initDataUnsafe.user.last_name].filter(Boolean).join(" ")) || "")}">
    <label>Avtomobil</label><select id="f-model">${models.map((m) => `<option>${m}</option>`).join("")}<option value="">Boshqa…</option></select>
    <input id="f-model-other" maxlength="40" placeholder="Model nomi" hidden>
    <label>Rangi</label><select id="f-color">${colors.map((c) => `<option>${c}</option>`).join("")}</select>
    <label>Davlat raqami</label><input id="f-plate" maxlength="12" placeholder="01 A 123 BC" autocapitalize="characters"></div>`);
  $("#f-model").addEventListener("change", (e) => { $("#f-model-other").hidden = e.target.value !== ""; });
  Main.set("Arizani yuborish", async () => {
    const body = {
      full_name: $("#f-name").value, car_model: $("#f-model").value || $("#f-model-other").value,
      car_color: $("#f-color").value, car_plate: $("#f-plate").value,
    };
    try { await api("/api/d/register", body); haptic("success"); S.mode = "pending"; await driverRefresh(); }
    catch (e) { toast(e.message, true); }
  });
}

function renderDriverSettings() {
  const d = S.dstate.driver;
  S.mode = "settings";
  const navs = { google: "Google Maps", yandex: "Yandex Maps", waze: "Waze" };
  sheet(`<h2>Sozlamalar</h2><div class="muted small">Navigator — «🧭 Navigator» bosilganda yo'l shu ilovada ochiladi</div>
    <div class="chips">${Object.entries(navs).map(([k, v]) => `<button class="chip ${k === d.navigator ? "home" : ""}" data-nav="${k}">${k === d.navigator ? "✅ " : ""}${v}</button>`).join("")}</div>
    <div class="field"><span class="icon">🏡</span><span class="txt"><div class="t1">«Uyga» rejimi: ${d.home_mode ? "yoqilgan" : "o'chiq"}</div>
      <div class="t2">Faqat uy tomonga ketayotgan buyurtmalar</div></span></div>
    <div class="btns"><button class="btn" id="set-home">📍 Uy = hozirgi joy</button>
      <button class="btn ${d.home_mode ? "red" : ""}" id="home-mode" ${d.home_set ? "" : "disabled"}>${d.home_mode ? "O'chirish" : "Yoqish"}</button></div>
    ${S.config.single_bot ? `<div class="btns"><button class="btn" id="switch-role">🙋 Yo'lovchi rejimiga o'tish</button></div>` : ""}`);
  on("switch-role", switchRole);
  Main.hide();
  Second.hide();
  Back.show(() => { Back.hide(); S.mode = "idle"; driverRefresh(); });
  $(".chips").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-nav]");
    if (!b) return;
    await api("/api/d/settings", { navigator: b.dataset.nav });
    S.dstate = await api("/api/d/state");
    renderDriverSettings();
  });
  on("set-home", async () => {
    const loc = await locate();
    if (!loc) return toast("Joylashuv aniqlanmadi", true);
    await api("/api/d/settings", { home: loc });
    S.dstate = await api("/api/d/state");
    toast("🏡 Uy manzili saqlandi");
    renderDriverSettings();
  });
  on("home-mode", async () => {
    await api("/api/d/settings", { home_mode: !d.home_mode });
    S.dstate = await api("/api/d/state");
    renderDriverSettings();
  });
}

// ====================================================================== ishga tushirish
function chooseRole() {
  document.getElementById("boot").hidden = true;
  sheet(`<h2>Xush kelibsiz! 🚕</h2><div class="muted">Kim sifatida davom etasiz?</div>
    <div class="btns"><button class="btn accent" id="as-passenger">🙋 Yo'lovchi</button><button class="btn" id="as-driver">🚕 Haydovchi</button></div>`);
  const pick = (role) => {
    S.app = role;
    sheet("");
    document.getElementById("boot").hidden = false;
    launch();
  };
  on("as-passenger", () => pick("passenger"));
  on("as-driver", () => pick("driver"));
}

/** Ilova rejimi: havoladagi ?app= → botda tanlangan rol (bazadan) → so'raladi. */
async function resolveApp() {
  const param = new URLSearchParams(location.search).get("app");
  if (param === "driver" || param === "passenger") return param;
  const r = await api("/api/role");
  return r.role;
}

async function boot() {
  if (!tg || !tg.initData) {
    $("#boot").querySelector(".boot-text").textContent = "Ilovani Telegram orqali oching";
    $("#boot .spinner").hidden = true;
    return;
  }
  tg.ready();
  tg.expand();
  try { tg.disableVerticalSwipes(); } catch { /* eski klient */ }
  try { tg.setHeaderColor("bg_color"); } catch { /* eski klient */ }
  try {
    S.app = await resolveApp();
  } catch (e) {
    $("#boot").querySelector(".boot-text").textContent = e.message;
    $("#boot .spinner").hidden = true;
    return;
  }
  if (!S.app) {
    S.config = { currency: "so'm", tile_url: "", tile_attribution: "" };
    return chooseRole();
  }
  await launch();
}

async function launch() {
  try {
    const me = await api("/api/me");
    S.config = me.config;
  } catch (e) {
    $("#boot").querySelector(".boot-text").textContent = e.message;
    $("#boot .spinner").hidden = true;
    return;
  }
  initMap([41.3111, 69.2797]);
  initSearch();
  // Telegram pastki tugmasi paydo bo'lganda oyna balandligi o'zgaradi — olish joyi nina ostida qolsin
  let resizeTimer = null;
  const onResize = () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!S.map) return;
      S.map.invalidateSize({ pan: false });
      layoutOverlays();
      if (S.mode === "home" && S.pickup) centerOn(S.pickup.lat, S.pickup.lon);
    }, 120);
  };
  window.addEventListener("resize", onResize);
  try { tg.onEvent("viewportChanged", onResize); } catch { /* eski klient */ }
  $("#boot").hidden = true;
  if (S.app === "driver") await driverStart();
  else await passengerStart();
}

boot();
