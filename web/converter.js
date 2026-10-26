/*
 * Eski özbek lotin yozuvidagi matnni yangi (2026) alifboga ögiriş:
 *   sh → ş, ch → ç, o' → ö, g' → ğ, harflar orasidagi apostrof → ʼ (tutuq belgisi)
 *
 * Brauzerda: window.YangiAlifbo.convert(matn)
 * Node.js'da: require('./converter.js').convert(matn)
 */
(function (root) {
  'use strict';

  // Eski matnlarda apostrof örnida uçraydigan belgilar: ' ` ‘ ’ ʻ ʼ ´
  var APOS = "'`‘’ʻʼ´";
  var TUTUQ = 'ʼ';
  var NEW = { s: 'ş', S: 'Ş', c: 'ç', C: 'Ç', o: 'ö', O: 'Ö', g: 'ğ', G: 'Ğ' };

  var RULES = new RegExp(
    '([sScC])[hH]' +                         // sh, ch
    '|([oO])[' + APOS + '](?=\\p{L})' +      // o' (keyin harf kelsa; 'kino' kabi qöştirnoq emas)
    '|([gG])[' + APOS + ']' +                // g' (toğ, boğ — söz oxirida ham)
    '|(\\p{L})[' + APOS + '](?=\\p{L})',     // maʼno, sanʼat
    'gu'
  );

  // Email va havolalar ögirilmaydi: sherzod@mail.uz, https://...
  var PROTECTED = /\S+@\S+\.\S+|(?:https?:\/\/|www\.)\S+/gi;

  function convertPlain(text) {
    return text.replace(RULES, function (m, sc, o, g, letter) {
      if (sc) return NEW[sc];
      if (o) return NEW[o];
      if (g) return NEW[g];
      return letter + TUTUQ;
    });
  }

  function convert(text) {
    var out = '';
    var last = 0;
    var m;
    PROTECTED.lastIndex = 0;
    while ((m = PROTECTED.exec(text)) !== null) {
      out += convertPlain(text.slice(last, m.index)) + m[0];
      last = m.index + m[0].length;
    }
    return out + convertPlain(text.slice(last));
  }

  // Yoziş paytida: matn maydonining oldingi (prev) va hozirgi (value) qiymatini solişirib,
  // faqat yangi yozilgan/qöyilgan qismni (va undan oldingi 2 belgini) ögiradi.
  // Özgariş bölmasa null, aks holda { value, caret } qaytaradi.
  function liveUpdate(prev, value, caret) {
    var start = 0;
    var max = Math.min(prev.length, value.length);
    while (start < max && prev.charCodeAt(start) === value.charCodeAt(start)) start++;
    var endOld = prev.length;
    var endNew = value.length;
    while (endOld > start && endNew > start &&
           prev.charCodeAt(endOld - 1) === value.charCodeAt(endNew - 1)) {
      endOld--;
      endNew--;
    }
    if (endNew === start) return null; // faqat öçirildi

    var from = Math.max(0, start - 2);
    var to = Math.min(value.length, endNew + 1);
    var seg = value.slice(from, to);
    var conv = convert(seg);
    if (conv === seg) return null;

    var next = value.slice(0, from) + conv + value.slice(to);
    var pos = caret >= to
      ? caret + conv.length - seg.length
      : from + convert(value.slice(from, Math.max(from, caret))).length;
    return { value: next, caret: Math.min(pos, next.length) };
  }

  var api = { convert: convert, convertPlain: convertPlain, liveUpdate: liveUpdate };
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.YangiAlifbo = api;
  }
})(typeof self !== 'undefined' ? self : this);
