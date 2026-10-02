// capacitor.config.json ni yaratadi: server manzili (APP_SERVER_URL — botdagi WEBAPP_URL bilan bir xil),
// ilova identifikatori va nomi. Ilova shu manzildagi Web App ni ochadi — yangi funksiyalar serverga qo'yilishi
// bilan telefonda ham paydo bo'ladi, ilovani qayta o'rnatish shart emas.
import { writeFileSync } from 'node:fs';

const url = (process.env.APP_SERVER_URL || '').trim().replace(/\/+$/, '');
if (!/^https:\/\/[^/]+/.test(url)) {
  console.error("APP_SERVER_URL berilmagan yoki https:// bilan boshlanmaydi (masalan: https://ilova.example.uz)");
  process.exit(1);
}
const host = new URL(url).host;
const config = {
  appId: process.env.APP_ID || 'uz.jidu.otaona',
  appName: process.env.APP_NAME || 'JIDU Ota-ona',
  webDir: 'www',
  // Telegram'siz rejimni ilova o'zi aniqlaydi (webapp/app.js: NATIVE)
  appendUserAgent: 'JiduApp/1.0',
  backgroundColor: '#0E2240',
  server: {
    url: url + '/',
    hostname: host,
    androidScheme: 'https',
    errorPath: 'offline.html',
    cleartext: false
  },
  android: { allowMixedContent: false },
  ios: { contentInset: 'never', scrollEnabled: true },
  plugins: { SystemBars: { insetsHandling: 'css' } }
};
writeFileSync('capacitor.config.json', JSON.stringify(config, null, 2) + '\n');
writeFileSync('www/config.js', `window.APP_SERVER_URL = ${JSON.stringify(url + '/')};\n`);
console.log(`capacitor.config.json: ${config.appId} → ${url}/`);
