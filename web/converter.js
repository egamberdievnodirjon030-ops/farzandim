/*
 * Eski özbek lotin yozuvidagi matnni yangi (2026) alifboga ögiriş:
 *   sh → ş, ch → ç, o' → ö, g' → ğ, harflar orasidagi apostrof → ʼ (tutuq belgisi)
 *
 * Brauzerda: window.YangiAlifbo.convert(matn)
 * Node.js'da: require('./converter.js').convert(matn)
 */
(function (root) {
  'use strict';

  // Eski matnlarda o', g' va tutuq örnida uçraydigan barça apostrof şakllari:
  // ' ` ´ ‘ ’ ‛ ′ ʹ ʻ ʼ ʽ ＇
  var APOS = "'`\u00B4\u2018\u2019\u201B\u2032\u02B9\u02BB\u02BC\u02BD\uFF07";
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

    var next = value.slice(0, from) + conv + value.slice(to);
    var pos = caret >= to
      ? caret + conv.length - seg.length
      : from + convert(value.slice(from, Math.max(from, caret))).length;
    pos = Math.min(pos, next.length);

    // o' yozilişi bilan darhol ö bölsin (keyingi harfni kutmasdan), xuddi klaviaturadagidek
    if (endNew - start === 1 && pos >= 2 && APOS.indexOf(next.charAt(pos - 1)) >= 0) {
      var o = next.charAt(pos - 2);
      if (o === 'o' || o === 'O') {
        next = next.slice(0, pos - 2) + NEW[o] + next.slice(pos);
        pos -= 1;
      }
    }
    if (next === value) return null;
    return { value: next, caret: pos };
  }

  var api = { convert: convert, convertPlain: convertPlain, liveUpdate: liveUpdate };
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.YangiAlifbo = api;
  }
})(typeof self !== 'undefined' ? self : this);
