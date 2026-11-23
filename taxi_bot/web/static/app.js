"use strict";

// ---------------------------------------------------------------- yordamchilar
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const state = {
  tab: "overview",
  ordersScope: "active",
  driversStatus: "",
  financeDays: 14,
  currency: "so'm",
  cache: {},
  map: null,
  layer: null,
  fitted: false,
};

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const num = (n) => Math.round(n || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
const money = (n) => (n == null ? "—" : `${num(n)} ${state.currency}`);
const km = (m) => (m == null ? "—" : m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);
const pad = (n) => String(n).padStart(2, "0");
const dt = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const STATUS = {
  searching: "Qidirilmoqda", accepted: "Haydovchi yo'lda", arrived: "Kutmoqda", in_progress: "Safarda",
  finishing: "Tasdiq kutilmoqda", completed: "Yakunlangan", cancelled: "Bekor qilingan", no_drivers: "Topilmadi",
  pending: "Ariza", approved: "Tasdiqlangan", rejected: "Rad etilgan", blocked: "Bloklangan",
};
const KIND = { commission: "Komissiya", topup: "To'ldirish", payment: "To'lov", bonus: "Bonus", adjust: "Tuzatish" };
const ACTIVE = ["searching", "accepted", "arrived", "in_progress", "finishing"];
const chip = (s) => `<span class="chip ${esc(s)}">${esc(STATUS[s] || s)}</span>`;

async function api(path, opts = {}) {
  const headers = { "X-Panel": "1" };
  if (opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { credentials: "same-origin", ...opts, headers });
  if (res.status === 401) {
    location.href = "/login";
    throw new Error("unauthorized");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Xato: HTTP ${res.status}`);
  return data;
}

let toastTimer = null;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = isError ? "toast err" : "toast";
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 3200);
}

function ask({ title, text = "", input = false, okText = "Tasdiqlash", danger = false }) {
  const dialog = $("#dialog");
  $("#dialog-title").textContent = title;
  $("#dialog-text").textContent = text;
  const field = $("#dialog-input");
  field.hidden = !input;
  field.value = "";
  const ok = $("#dialog-ok");
  ok.textContent = okText;
  ok.className = danger ? "btn danger" : "btn primary";
  return new Promise((resolve) => {
    dialog.addEventListener(
      "close",
      () => resolve(dialog.returnValue === "ok" ? (input ? field.value : true) : null),
      { once: true }
    );
    dialog.showModal();
    if (input) field.focus();
  });
}

function setLive(ok) {
  const el = $("#live");
  el.className = ok ? "live ok" : "live err";
  const now = new Date();
  $("#live-text").textContent = ok
    ? `Jonli · ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
    : "Aloqa yo'q";
}

const empty = (text) => `<div class="empty">${esc(text)}</div>`;
const table = (head, rows, emptyText) =>
  `<thead><tr>${head.map(([t, cls]) => `<th class="${cls || ""}">${t}</th>`).join("")}</tr></thead>` +
  `<tbody>${rows.length ? rows.join("") : `<tr><td colspan="${head.length}">${empty(emptyText)}</td></tr>`}</tbody>`;
const matches = (q, ...fields) => !q || fields.some((f) => String(f ?? "").toLowerCase().includes(q));

// ---------------------------------------------------------------- umumiy
function kpi(label, value, sub = "", alert = false) {
  return `<div class="card kpi${alert ? " alert" : ""}"><div class="label">${esc(label)}</div>` +
    `<div class="value">${esc(value)}</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div>`;
}

async function loadSummary() {
  const s = await api("/api/summary");
  state.currency = s.currency || state.currency;
  const searching = s.active_by_status.searching || 0;
  $("#kpis").innerHTML = [
    kpi("Liniyada", s.online, `bo'sh ${s.free} · band ${s.busy}`),
    kpi("Faol buyurtmalar", s.active, searching ? `${searching} tasi qidiruvda` : "qidiruvda yo'q"),
    kpi("Bugun yakunlangan", s.today_done, `topilmagan: ${s.today_no_drivers}`),
    kpi("Bugungi aylanma", money(s.today_turnover)),
    kpi(`Bugungi komissiya (${s.commission_percent}%)`, money(s.today_commission)),
    kpi("Arizalar", s.pending_drivers, "tasdiq kutmoqda", s.pending_drivers > 0),
    kpi("Balansi kam", s.low_balance, "buyurtma olmaydi", s.low_balance > 0),
    kpi("Jami", `${s.drivers_total} / ${s.passengers_total}`, "haydovchi / yo'lovchi"),
  ].join("");
  const badge = $("#pending-badge");
  badge.hidden = !s.pending_drivers;
  badge.textContent = s.pending_drivers;
}

function initMap() {
  if (state.map || typeof L === "undefined") return;
  state.map = L.map("map", { zoomControl: true }).setView([41.3111, 69.2797], 12);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(state.map);
  state.layer = L.layerGroup().addTo(state.map);
}

async function loadMap() {
  initMap();
  const data = await api("/api/map");
  if (!state.map) return;
  state.layer.clearLayers();
  const colors = { free: "#16a34a", busy: "#d97706", stale: "#9ca3af" };
  const points = [];
  const byId = {};
  for (const d of data.drivers) {
    byId[d.id] = d;
    points.push([d.lat, d.lon]);
    L.circleMarker([d.lat, d.lon], {
      radius: 8, color: "#fff", weight: 2, fillColor: colors[d.state], fillOpacity: 1,
    })
      .bindTooltip(`🚕 ${esc(d.plate)} · ${esc(d.car)}<br>${esc(d.name)} · ⭐ ${d.rating.toFixed(2)}` +
        (d.order_id ? `<br>Buyurtma #${d.order_id}` : ""))
      .addTo(state.layer);
  }
  for (const o of data.orders) {
    points.push(o.pickup);
    L.circleMarker(o.pickup, { radius: 7, color: "#fff", weight: 2, fillColor: "#dc2626", fillOpacity: 1 })
      .bindTooltip(`📍 #${o.id} · ${esc(STATUS[o.status] || o.status)}`)
      .addTo(state.layer);
    const d = o.driver_id && byId[o.driver_id];
    if (d) L.polyline([o.pickup, [d.lat, d.lon]], { color: "#d97706", weight: 2, dashArray: "5 6" }).addTo(state.layer);
  }
  if (!state.fitted && points.length) {
    state.map.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
    state.fitted = true;
  }
}

function orderItem(o) {
  const driver = o.driver ? `🚕 ${esc(o.driver.plate)} · ${esc(o.driver.name)}` : "haydovchi yo'q";
  return `<div class="item"><div class="item-top"><b>#${o.id}</b>${chip(o.status)}</div>
    <div class="meta">${dt(o.created_at)} · 🙋 ${esc(o.passenger.phone || "—")} · ${driver}${o.call_codes && o.call_codes.length
      ? ` · 📞 kod: ${o.call_codes.map(esc).join(" / ")} (yo'lovchi / haydovchi)` : ""}</div>
    <div class="item-top"><span class="meta">${o.price ? money(o.price) : "taksometr"}${o.comment ? ` · 💬 ${esc(o.comment)}` : ""}</span>
    <button class="btn small danger" data-act="cancel-order" data-id="${o.id}">Bekor qilish</button></div></div>`;
}

async function loadActive() {
  const orders = await api("/api/orders?scope=active");
  $("#active-count").textContent = `${orders.length} ta`;
  $("#active-list").innerHTML = orders.length ? orders.map(orderItem).join("") : empty("Hozir faol buyurtma yo'q");
}

// ---------------------------------------------------------------- buyurtmalar
async function loadOrders(refetch = true) {
  if (refetch) state.cache.orders = await api(`/api/orders?scope=${state.ordersScope}&limit=300`);
  const q = $("#orders-q").value.trim().toLowerCase().replace(/^#/, "");
  const rows = (state.cache.orders || [])
    .filter((o) => matches(q, o.id, o.passenger.phone, o.rider_phone, o.driver?.plate, o.driver?.name, o.passenger.name, ...(o.call_codes || [])))
    .map((o) => `<tr><td><b>#${o.id}</b></td><td>${dt(o.created_at)}</td><td>${chip(o.status)}</td>
      <td>${esc(o.passenger.name)}<br><span class="muted small">${esc(o.passenger.phone || "")}${o.rider_phone ? ` → 👤 ${esc(o.rider_phone)}` : ""}</span></td>
      <td>${o.driver ? `${esc(o.driver.plate)}<br><span class="muted small">${esc(o.driver.name)}</span>` : "—"}</td>
      <td class="num">${km(o.distance_m)}</td><td class="num">${o.price ? money(o.price) : "—"}</td>
      <td class="num">${o.commission != null ? money(o.commission) : "—"}</td>
      <td>${o.rating ? "⭐".repeat(o.rating) : ""}${o.cancelled_by ? `<span class="muted small">bekor: ${esc(o.cancelled_by)}</span>` : ""}</td>
      <td>${ACTIVE.includes(o.status) || o.status === "no_drivers"
        ? `<button class="btn small danger" data-act="cancel-order" data-id="${o.id}">Bekor qilish</button>` : ""}</td></tr>`);
  $("#orders-table").innerHTML = table(
    [["#"], ["Vaqt"], ["Holat"], ["Yo'lovchi"], ["Haydovchi"], ["Masofa", "num"], ["Narx", "num"], ["Komissiya", "num"], ["Baho"], [""]],
    rows, "Buyurtma topilmadi"
  );
}

// ---------------------------------------------------------------- haydovchilar
function driverActions(d) {
  const b = (act, label, cls) => `<button class="btn small ${cls}" data-act="driver" data-action="${act}" data-id="${d.id}">${label}</button>`;
  const out = [];
  if (d.status === "pending") out.push(b("approve", "✅ Tasdiqlash", "success"), b("reject", "Rad etish", ""));
  if (d.status === "approved") out.push(b("topup", "💳 Balans", "primary"), b("block", "Bloklash", "danger"));
  if (d.status === "blocked" || d.status === "rejected") out.push(b("unblock", "Faollashtirish", "success"));
  return `<div class="actions">${out.join("")}</div>`;
}

async function loadDrivers(refetch = true) {
  if (refetch) state.cache.drivers = await api(`/api/drivers${state.driversStatus ? `?status=${state.driversStatus}` : ""}`);
  const q = $("#drivers-q").value.trim().toLowerCase();
  const rows = (state.cache.drivers || [])
    .filter((d) => matches(q, d.id, d.name, d.phone, d.plate, d.car))
    .map((d) => {
      const online = !d.online
        ? '<span class="chip">Oflayn</span>'
        : d.busy ? '<span class="chip accepted">Band</span>'
        : d.location_fresh ? '<span class="chip online">Liniyada</span>' : '<span class="chip">Joylashuv eski</span>';
      const lowBalance = d.balance < 0 ? " neg" : "";
      return `<tr><td><b>${d.id}</b></td><td>${esc(d.name)}<br><span class="muted small">${esc(d.phone || "")}</span></td>
        <td>${esc(d.car)}<br><b>${esc(d.plate)}</b></td><td>${chip(d.status)}</td>
        <td>${d.status === "approved" ? online : ""}${d.home_mode ? ' <span class="chip">🏡 Uyga</span>' : ""}</td>
        <td class="num${lowBalance}">${money(d.balance)}</td>
        <td class="num">⭐ ${d.rating.toFixed(2)}<br><span class="muted small">${d.rating_count} baho</span></td>
        <td class="num">${d.trips}</td><td class="num">${d.cancels}</td><td>${driverActions(d)}</td></tr>`;
    });
  $("#drivers-table").innerHTML = table(
    [["ID"], ["Haydovchi"], ["Avtomobil"], ["Holat"], ["Hozir"], ["Balans", "num"], ["Reyting", "num"], ["Safar", "num"], ["Bekor", "num"], ["Amallar"]],
    rows, "Haydovchi topilmadi"
  );
}

// ---------------------------------------------------------------- yo'lovchilar
async function loadPassengers(refetch = true) {
  if (refetch) state.cache.passengers = await api("/api/passengers");
  const q = $("#passengers-q").value.trim().toLowerCase();
  const rows = (state.cache.passengers || [])
    .filter((p) => matches(q, p.id, p.name, p.phone))
    .map((p) => `<tr><td><b>${p.id}</b></td><td>${esc(p.name)}</td><td>${esc(p.phone || "—")}</td>
      <td class="num">${p.trips}</td><td class="num">${p.cancels}</td><td>${dt(p.created_at)}</td>
      <td>${p.blocked ? chip("blocked") : '<span class="chip online">Faol</span>'}</td>
      <td><button class="btn small ${p.blocked ? "success" : "danger"}" data-act="passenger" data-action="${p.blocked ? "unblock" : "block"}" data-id="${p.id}">
        ${p.blocked ? "Blokdan chiqarish" : "Bloklash"}</button></td></tr>`);
  $("#passengers-table").innerHTML = table(
    [["ID"], ["Ism"], ["Telefon"], ["Safar", "num"], ["Bekor", "num"], ["Qo'shilgan"], ["Holat"], [""]],
    rows, "Yo'lovchi topilmadi"
  );
}

// ---------------------------------------------------------------- moliya
async function loadFinance() {
  const [f, tx] = await Promise.all([api(`/api/finance?days=${state.financeDays}`), api("/api/transactions?limit=100")]);
  const t = f.totals;
  $("#finance-kpis").innerHTML = [
    kpi("Safarlar", t.trips, `${state.financeDays} kun`),
    kpi("Aylanma", money(t.turnover)),
    kpi("Komissiya (daromad)", money(t.commission)),
    kpi("Balans to'ldirishlar", money(t.topups)),
    kpi("Haydovchilar balansi", money(f.driver_balances), "hozirgi jami qoldiq"),
  ].join("");
  const days = [...f.days].reverse();
  const max = Math.max(1, ...days.map((d) => d.commission));
  $("#finance-bars").innerHTML = days
    .map((d) => `<div class="bar" title="${d.date}: ${money(d.commission)}, ${d.trips} safar">
      <div class="fill" data-h="${(d.commission / max) * 100}"></div><div class="lbl">${d.date.slice(8)}.${d.date.slice(5, 7)}</div></div>`)
    .join("");
  $$("#finance-bars .fill").forEach((el) => (el.style.height = `${el.dataset.h}%`));
  $("#finance-table").innerHTML = table(
    [["Sana"], ["Safar", "num"], ["Aylanma", "num"], ["Komissiya", "num"], ["To'ldirish", "num"]],
    f.days.map((d) => `<tr><td>${d.date}</td><td class="num">${d.trips}</td><td class="num">${money(d.turnover)}</td>
      <td class="num">${money(d.commission)}</td><td class="num">${money(d.topups)}</td></tr>`),
    "Ma'lumot yo'q"
  );
  $("#tx-table").innerHTML = table(
    [["Vaqt"], ["Haydovchi"], ["Turi"], ["Summa", "num"], ["Qoldiq", "num"]],
    tx.map((x) => `<tr><td>${dt(x.created_at)}</td><td>${esc(x.plate)}<br><span class="muted small">${esc(x.driver)}</span></td>
      <td>${esc(KIND[x.kind] || x.kind)}${x.order_id ? ` <span class="muted small">#${x.order_id}</span>` : ""}</td>
      <td class="num">${x.amount > 0 ? "+" : ""}${money(x.amount)}</td><td class="num">${money(x.balance_after)}</td></tr>`),
    "Tranzaksiya yo'q"
  );
}

// ---------------------------------------------------------------- yangilash
const loaders = {
  overview: () => Promise.all([loadSummary(), loadMap(), loadActive()]),
  orders: () => Promise.all([loadSummary(), loadOrders()]),
  drivers: () => Promise.all([loadSummary(), loadDrivers()]),
  passengers: () => loadPassengers(),
  finance: () => loadFinance(),
};

let busy = false;
async function refresh() {
  if (busy || document.hidden) return;
  busy = true;
  try {
    await loaders[state.tab]();
    setLive(true);
  } catch (err) {
    if (err.message !== "unauthorized") setLive(false);
  } finally {
    busy = false;
  }
}

function switchTab(tab) {
  state.tab = tab;
  $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $$(".tab").forEach((s) => s.classList.toggle("active", s.id === `tab-${tab}`));
  if (tab === "overview" && state.map) setTimeout(() => state.map.invalidateSize(), 50);
  refresh();
}

function segment(id, key, after) {
  $(id).addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    $$(`${id} button`).forEach((b) => b.classList.toggle("active", b === btn));
    state[key] = key === "financeDays" ? Number(btn.dataset.v) : btn.dataset.v;
    after();
  });
}

// ---------------------------------------------------------------- amallar
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const id = btn.dataset.id;
  try {
    if (btn.dataset.act === "cancel-order") {
      const ok = await ask({
        title: `Buyurtma #${id} ni bekor qilasizmi?`,
        text: "Yo'lovchi va haydovchiga xabar boradi, haydovchi bo'shaydi. Komissiya yechilmaydi.",
        okText: "Bekor qilish", danger: true,
      });
      if (!ok) return;
      await api(`/api/orders/${id}/cancel`, { method: "POST" });
      toast(`Buyurtma #${id} bekor qilindi`);
    } else if (btn.dataset.act === "driver") {
      const action = btn.dataset.action;
      if (action === "topup") {
        const value = await ask({
          title: `Haydovchi #${id} balansini to'ldirish`,
          text: "Summani kiriting (so'm). Yechish uchun minus bilan: -5000",
          input: true, okText: "To'ldirish",
        });
        if (!value) return;
        const res = await api(`/api/drivers/${id}/topup`, { method: "POST", body: JSON.stringify({ amount: Number(value) }) });
        toast(`Yangi balans: ${money(res.balance)}`);
      } else {
        const labels = { approve: "tasdiqlaysizmi", reject: "rad etasizmi", block: "bloklaysizmi", unblock: "faollashtirasizmi" };
        const ok = await ask({ title: `Haydovchi #${id} ni ${labels[action]}?`, text: "Haydovchiga Telegram'da xabar boradi.",
          danger: action === "block" || action === "reject" });
        if (!ok) return;
        await api(`/api/drivers/${id}/${action}`, { method: "POST" });
        toast("Bajarildi");
      }
    } else if (btn.dataset.act === "passenger") {
      const action = btn.dataset.action;
      const ok = await ask({
        title: action === "block" ? `Yo'lovchi #${id} ni bloklaysizmi?` : `Yo'lovchi #${id} ni blokdan chiqarasizmi?`,
        text: action === "block" ? "U yangi buyurtma bera olmaydi." : "", danger: action === "block",
      });
      if (!ok) return;
      await api(`/api/passengers/${id}/${action}`, { method: "POST" });
      toast("Bajarildi");
    }
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
});

// ---------------------------------------------------------------- ishga tushirish
$("#tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-tab]");
  if (btn) switchTab(btn.dataset.tab);
});
segment("#orders-scope", "ordersScope", () => loadOrders());
segment("#drivers-status", "driversStatus", () => loadDrivers());
segment("#finance-days", "financeDays", () => loadFinance());
$("#orders-q").addEventListener("input", () => loadOrders(false));
$("#drivers-q").addEventListener("input", () => loadDrivers(false));
$("#passengers-q").addEventListener("input", () => loadPassengers(false));
document.addEventListener("visibilitychange", refresh);

refresh();
setInterval(refresh, 5000);
