/* Ishga tushiruvchi va «aloqa yo'q» sahifalari uchun umumiy kod (ilova ichidagi mahalliy sahifalar). */
(function () {
  'use strict';
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* */ } }
  };
  function server() { return store.get('server') || window.APP_DEFAULT_SERVER || ''; }
  function hostAllowed(host) {
    return (window.APP_ALLOW_HOSTS || []).some(function (h) {
      return h.indexOf('*.') === 0 ? host.slice(-(h.length - 1)) === h.slice(1) : host === h;
    });
  }
  function normalize(v) {
    v = String(v || '').trim();
    var m = v.match(/https:\/\/[^\s<>"']+/);  // botdagi xabarni to'liq joylasa ham manzil ajratib olinadi
    if (!m) return null;
    try { var u = new URL(m[0]); } catch (e) { return null; }
    return hostAllowed(u.host) ? u.origin + '/' : null;
  }
  function timeout(ms) { return new Promise(function (_, rej) { setTimeout(function () { rej(new Error('timeout')); }, ms); }); }
  // Server javob bersa — bot nomini eslab qolib, ilovani ochadi; bo'lmasa «aloqa yo'q» sahifasi
  function launch() {
    var s = server();
    if (!s) { location.replace('offline.html'); return; }
    Promise.race([fetch(s + 'api/app/info', { cache: 'no-store' }), timeout(8000)])
      .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
      .then(function (d) { if (d.bot) store.set('bot', d.bot); store.set('server', s); location.replace(s); })
      .catch(function () { location.replace('offline.html'); });
  }
  window.JIDU = { store: store, server: server, normalize: normalize, launch: launch };
})();
