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

test('öçiriş hech narsani özgartirmaydi', () => {
  assert.equal(liveUpdate('sah', 'sh', 1), null);
});
