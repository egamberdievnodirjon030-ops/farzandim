// capacitor.config.json va www/config.js ni yaratadi.
// Ilova o'z ichidagi kichik sahifadan (www/index.html) ishga tushadi va oxirgi ma'lum server manzilini ochadi.
// Manzil o'zgarsa (masalan, vaqtinchalik tunnel), ilova uni botdan oladi — APK ni qayta yig'ish shart emas.
// Server manzili: APP_SERVER_URL (muhit) yoki app.json → serverUrl.
import { readFileSync, writeFileSync } from 'node:fs';

let file = {};
try { file = JSON.parse(readFileSync('app.json', 'utf8')); } catch { /* yo'q */ }
const url = (process.env.APP_SERVER_URL || file.serverUrl || '').trim().replace(/\/+$/, '');
if (!/^https:\/\/[^/]+/.test(url)) {
  console.error("Server manzili berilmagan yoki https:// bilan boshlanmaydi (app.json → serverUrl yoki APP_SERVER_URL)");
  process.exit(1);
}
const hosts = [...new Set([new URL(url).host, ...(file.allowHosts || [])])];
const config = {
  appId: process.env.APP_ID || 'uz.jidu.otaona',
  appName: process.env.APP_NAME || 'JIDU Ota-ona',
  webDir: 'www',
  // Telegram'siz rejimni server sahifasi o'zi aniqlaydi (webapp/app.js: NATIVE)
  appendUserAgent: 'JiduApp/1.0',
  backgroundColor: '#0E2240',
  server: {
    androidScheme: 'https',
    // shu domenlar ilova ichida ochiladi; boshqa havolalar (t.me va h.k.) — Telegram yoki brauzerda
    allowNavigation: hosts,
    errorPath: 'offline.html',
    cleartext: false
  },
  android: { allowMixedContent: false },
  ios: { contentInset: 'never', scrollEnabled: true, limitsNavigationsToAppBoundDomains: false },
  plugins: { SystemBars: { insetsHandling: 'css' } }
};
writeFileSync('capacitor.config.json', JSON.stringify(config, null, 2) + '\n');
writeFileSync('www/config.js', `window.APP_DEFAULT_SERVER = ${JSON.stringify(url + '/')};\n` +
  `window.APP_ALLOW_HOSTS = ${JSON.stringify(hosts)};\n`);
console.log(`capacitor.config.json: ${config.appId} → ${url}/ (ruxsat: ${hosts.join(', ')})`);
