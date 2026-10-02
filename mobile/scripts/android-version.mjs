// Android versiyasi: versionCode — har bir yig'ishda oshib boradi (yangi APK eskisining ustiga o'rnatiladi).
import { readFileSync, writeFileSync } from 'node:fs';

const code = parseInt(process.env.APP_BUILD || '1', 10);
const name = process.env.APP_VERSION || `1.0.${code}`;
const file = 'android/app/build.gradle';
let g = readFileSync(file, 'utf8');
g = g.replace(/versionCode\s+\d+/, `versionCode ${code}`).replace(/versionName\s+"[^"]*"/, `versionName "${name}"`);
writeFileSync(file, g);
console.log(`Android: versionCode ${code}, versionName ${name}`);
