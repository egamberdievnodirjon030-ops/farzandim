// Kompilyatsiya qilingan Keyman klaviaturasini (build/yangi_ozbek.js) tugma bosişlarini
// taqlid qilib tekşiradi. Avval: npm run build
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const SHIFT = 0x10, RALT = 0x08;
const source = readFileSync(new URL('../keyman/yangi_ozbek/build/yangi_ozbek.js', import.meta.url), 'utf8');

// KeymanWeb'ning kompilyatsiya qilingan qoidalar çaqiradigan qismi
function loadKeyboard() {
  let keyboard;
  let anyIndices = [];
  const KeymanWeb = {
    KR: (kbd) => { keyboard = kbd; },
    KKM: (e, ruleShift, ruleKey) => e.Lcode === ruleKey && (ruleShift & 0xff) === e.Lmodifiers,
    KFCM: (n, t, spec) => {
      const ctx = [...t.text].slice(-n);
      if (ctx.length < n) return false;
      const indices = [];
      for (let i = 0; i < n; i++) {
        const item = spec[i];
        if (item.t !== 'a') throw new Error('mock: unsupported context item ' + JSON.stringify(item));
        indices[i] = [...item.a].indexOf(ctx[i]);
        if (indices[i] < 0) return false;
      }
      anyIndices = indices;
      return true;
    },
    KDC: (n, t) => { const chars = [...t.text]; t.text = chars.slice(0, chars.length - n).join(''); },
    KO: (dn, t, s) => { t.text += s; },
    KIO: (dn, store, n, t) => { t.text += [...store][anyIndices[n - 1]]; },
  };
  vm.runInNewContext(source, { keyman: { version: '18.0' }, KeymanWeb, console });
  return keyboard;
}

const kbd = loadKeyboard();
const touchKeys = kbd.KVKD.split(' ');

// AQŞ klaviaturasidagi belgi → [tugma kodi, Shift]
const US = {};
for (let c = 65; c <= 90; c++) {
  US[String.fromCharCode(c + 32)] = [c, 0];
  US[String.fromCharCode(c)] = [c, SHIFT];
}
for (let d = 0; d <= 9; d++) US[String(d)] = [48 + d, 0];
Object.assign(US, {
  ' ': [32, 0], "'": [222, 0], '"': [222, SHIFT], '`': [192, 0], '~': [192, SHIFT],
  '@': [50, SHIFT], '.': [190, 0], ',': [188, 0], '/': [191, 0], ':': [186, SHIFT], '-': [189, 0],
});

function press(t, code, mods, fallback) {
  const handled = kbd.gs(t, { Lcode: code, Lmodifiers: mods });
  if (!handled && fallback !== undefined) t.text += fallback;
}

// Matnni xuddi klaviaturada terganday kiritadi.
// {AltGr+x} — öng Alt bilan, {T_SH} — telefon tugmasi, {U+015F} — telefondagi tayyor harf.
function type(input) {
  const t = { text: '' };
  for (const [, special, ch] of input.matchAll(/\{([^}]+)\}|(.)/gsu)) {
    if (special?.startsWith('AltGr+')) {
      const c = special.slice(6);
      const [code, shift] = US[c];
      press(t, code, RALT | shift);
    } else if (special?.startsWith('T_')) {
      const i = touchKeys.indexOf(special);
      assert.ok(i >= 0, `${special} touch tugmasi yöq`);
      press(t, 256 + i, 0);
    } else if (special?.startsWith('U+')) {
      t.text += String.fromCodePoint(parseInt(special.slice(2), 16));
    } else {
      const [code, shift] = US[ch];
      press(t, code, shift, ch);
    }
  }
  return t.text;
}

const cases = [
  // eski yozuv → yangi alifbo
  ['Sherzod', 'Şerzod'],
  ['SHERZOD', 'ŞERZOD'],
  ['shahar', 'şahar'],
  ['choy', 'çoy'],
  ['Chorshanba', 'Çorşanba'],
  ['CHO\'L', 'ÇÖL'],
  ["O'zbekiston", 'Özbekiston'],
  ["o'zbek", 'özbek'],
  ['o`zbek', 'özbek'],
  ["G'afur G'ulom", 'Ğafur Ğulom'],
  ["tog'", 'toğ'],
  ["bog'cha", 'boğça'],
  ["ma'no", 'maʼno'],
  ["san'at", 'sanʼat'],
  ["she'r", 'şeʼr'],
  ["Is'hoq", 'Isʼhoq'],
  ['mashhur', 'maşhur'],
  ['dengiz', 'dengiz'],
  ["O'zbekiston Respublikasi Prezidenti Shavkat Mirziyoyev", 'Özbekiston Respublikasi Prezidenti Şavkat Mirziyoyev'],
  // AltGr bilan
  ['{AltGr+s}{AltGr+c}{AltGr+o}{AltGr+g}', 'şçöğ'],
  ['{AltGr+S}{AltGr+C}{AltGr+O}{AltGr+G}', 'ŞÇÖĞ'],
  ['s{AltGr+h}erzod@mail.uz', 'sherzod@mail.uz'],
  ["o{AltGr+'}", "o'"],
  ['o{AltGr+`}', 'o`'],
  // telefon tugmalari
  ['{T_SH}erzod', 'sherzod'],
  ['{T_SH_U}', 'Sh'],
  ['{T_CH}{T_CH_U}', 'chCh'],
  ['o{T_APOS}', "o'"],
  ['{U+015E}erzod', 'Şerzod'],
];

for (const [input, expected] of cases) {
  test(`${input} → ${expected}`, () => {
    assert.equal(type(input), expected);
  });
}
