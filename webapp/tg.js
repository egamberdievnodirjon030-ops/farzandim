/* Telegram Web App skripti — faqat Telegram ichida yuklanadi. Oddiy brauzerda (Chrome, Safari, Firefox...) telegram.org ga
   murojaat qilinmaydi: Telegram yopilgan tarmoqda ham sahifa darhol ochiladi. app.js shu va'dani (TG_LOADING) kutadi. */
(function () {
  var inTg = false;
  try { inTg = /tgWebApp/.test(location.hash + location.search) || !!sessionStorage.getItem('__telegram__initParams'); }
  catch (e) { /* sessionStorage yopiq */ }
  inTg = inTg || !!window.TelegramWebviewProxy || window.parent !== window;
  window.TG_LOADING = !inTg ? Promise.resolve() : new Promise(function (done) {
    var s = document.createElement('script');
    s.src = 'https://telegram.org/js/telegram-web-app.js';
    s.onload = s.onerror = function () { done(); };
    setTimeout(done, 8000);  // tarmoq sekin bo'lsa ham ilova ochiladi
    document.head.appendChild(s);
  });
})();
