// Veb-sahifadagi ögirgiç (web/converter.js) testlari
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const { convert, liveUpdate } = createRequire(import.meta.url)('../web/converter.js');

const cases = [
  ['Sherzod', 'Şerzod'],
  ['SHERZOD', 'ŞERZOD'],
  ['Chorshanba', 'Çorşanba'],
  ["O'zbekiston", 'Özbekiston'],
  ['O‘zbekiston', 'Özbekiston'],
  ['Oʻzbekiston', 'Özbekiston'],
  ['O’zbekiston', 'Özbekiston'],
  ['o`zbek', 'özbek'],
  ['G‘afur G‘ulom', 'Ğafur Ğulom'],
  ["tog'", 'toğ'],
  ["bog'cha", 'boğça'],
  ["ma'no", 'maʼno'],
  ['maʼno', 'maʼno'],
  ["she'r", 'şeʼr'],
  ["Is'hoq", 'Isʼhoq'],
  ['mashhur', 'maşhur'],
  ['dengiz', 'dengiz'],
  ['O‘ZBEKISTON RESPUBLIKASI', 'ÖZBEKISTON RESPUBLIKASI'],
  ["'kino' ko'rdik", "'kino' kördik"],
  ['Yozing: sherzod@mail.uz yoki https://shop.uz/choy', 'Yozing: sherzod@mail.uz yoki https://shop.uz/choy'],
  ['Şerzod Özbekistonda', 'Şerzod Özbekistonda'],
  [
    "Bolalar maktabga chiqishdi. O'qituvchi sho'rva haqida so'radi.",
    'Bolalar maktabga çiqişdi. Öqituvçi şörva haqida söradi.',
  ],
];

for (const [input, expected] of cases) {
  test(`convert: ${input} → ${expected}`, () => {
    assert.equal(convert(input), expected);
  });
}

// Matn maydonida harfma-harf yozişni taqlid qiladi
function typeLive(text, initial = '', caret = initial.length) {
  let value = initial;
  for (const ch of text) {
    const prev = value;
    value = value.slice(0, caret) + ch + value.slice(caret);
    caret += ch.length;
    const r = liveUpdate(prev, value, caret);
    if (r) ({ value, caret } = r);
  }
  return { value, caret };
}

const liveCases = [
  ['Sherzod', 'Şerzod'],
  ["O'zbekiston", 'Özbekiston'],
  ["G'ulom tog'da", 'Ğulom toğda'],
  ["ma'no she'r", 'maʼno şeʼr'],
  ['Chorshanba kuni choy ichdik', 'Çorşanba kuni çoy içdik'],
];

for (const [input, expected] of liveCases) {
  test(`yozish: ${input} → ${expected}`, () => {
    const { value, caret } = typeLive(input);
    assert.equal(value, expected);
    assert.equal(caret, expected.length);
  });
}

test('yozish: matn örtasiga', () => {
  const { value, caret } = typeLive('Sh', 'Salom, !', 7);
  assert.equal(value, 'Salom, Ş!');
  assert.equal(caret, 8);
});

test('qöyiş (paste): butun bölak ögiriladi', () => {
  const prev = 'Matn: ';
  const value = prev + "O'zbekiston, Toshkent shahri";
  const r = liveUpdate(prev, value, value.length);
  assert.deepEqual(r, { value: 'Matn: Özbekiston, Toşkent şahri', caret: 31 });
});

test('öçiriş heç narsani özgartirmaydi', () => {
  assert.equal(liveUpdate('sah', 'sh', 1), null);
});

// o', g' va tutuq uçun barça apostrof şakllari
const APOS_FORMS = ["'", '`', '´', '‘', '’', '‛', '′', 'ʹ', 'ʻ', 'ʼ', 'ʽ', '＇'];

for (const a of APOS_FORMS) {
  const cp = 'U+' + a.codePointAt(0).toString(16).toUpperCase().padStart(4, '0');
  test(`apostrof şakli ${a} (${cp})`, () => {
    assert.equal(convert(`O${a}zbekiston, tog${a}, ko${a}cha, ma${a}no`), 'Özbekiston, toğ, köça, maʼno');
    assert.equal(typeLive(`O${a}zbekiston, tog${a}, ko${a}cha, ma${a}no`).value, 'Özbekiston, toğ, köça, maʼno');
    // yozayotganda keyingi harfni kutmasdan darhol ögiriladi
    assert.deepEqual(typeLive(`o${a}`), { value: 'ö', caret: 1 });
    assert.deepEqual(typeLive(`O${a}`), { value: 'Ö', caret: 1 });
    assert.deepEqual(typeLive(`g${a}`), { value: 'ğ', caret: 1 });
  });
}

test("joylangan matnda qöştirnoq ('kino') ö ga aylanmaydi", () => {
  const value = "'kino' ko'rdik";
  assert.equal(liveUpdate('', value, value.length).value, "'kino' kördik");
});
