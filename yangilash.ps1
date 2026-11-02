# =====================================================================
#  Botni qayta o'rnatmasdan YANGILASH (Windows)
#  GitHub'dan shu tarmoqning eng yangi kodini yuklab, shu papkaga ustidan ko'chiradi.
#  TEGILMAYDI: .env (tokenlar, sozlamalar), data\ (baza, Manage sozlamasi, fayllar), venv\, logs\.
#
#  Ishga tushirish: yangilash.bat faylini ikki marta bosing
#  (yoki: powershell -ExecutionPolicy Bypass -File yangilash.ps1)
#  So'ng botni qayta ishga tushiring (oynasini yopib, odatdagidek qayta oching).
# =====================================================================
param(
    [string]$Repo = 'egamberdievnodirjon030-ops/farzandim',
    [string]$Branch = 'claude/make-it-u9vz9t'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Say([string]$text, [string]$color = 'Gray') { Write-Host $text -ForegroundColor $color }

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
$tmp = Join-Path $env:TEMP ("farzandim_yangilash_" + [Guid]::NewGuid().ToString('N').Substring(0, 8))
$zip = "$tmp.zip"
$url = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"

Say "1/4  Yangi kod yuklanmoqda: $url" 'Cyan'
try {
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
} catch {
    Say "Yuklab bo'lmadi: $($_.Exception.Message)" 'Red'
    Say "Internetni tekshiring. Repozitoriy yopiq (private) bo'lsa - GitHub'dan ZIP ni qo'lda yuklab, shu papkaga ko'chiring (.env va data ga tegmang)." 'Yellow'
    exit 1
}

Say "2/4  Ochilmoqda..." 'Cyan'
Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
$src = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
if (-not $src -or -not (Test-Path (Join-Path $src.FullName 'bot.py'))) {
    Say "Arxiv kutilgan ko'rinishda emas - yangilanmadi." 'Red'
    exit 1
}

Say "3/4  Fayllar yangilanmoqda (.env, data, venv, logs - o'zgarmaydi)..." 'Cyan'
# robocopy: 0-7 - muvaffaqiyat (nusxa olindi / o'zgarish yo'q), 8+ - xato
robocopy $src.FullName $PSScriptRoot /E /XD venv data logs .git __pycache__ /XF .env /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) {
    Say "Ko'chirishda xato (robocopy kodi $LASTEXITCODE). Bot ishlab turgan bo'lsa - to'xtatib, qayta urinib ko'ring." 'Red'
    exit 1
}
Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue

Say "4/4  Kutubxonalar tekshirilmoqda..." 'Cyan'
$venvPy = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
$py = if (Test-Path -LiteralPath $venvPy) { $venvPy } else { 'python' }
try {
    & $py -m pip install -q -r requirements.txt
} catch {
    Say "pip ishlamadi: $($_.Exception.Message) - kerak bo'lsa qo'lda: $py -m pip install -r requirements.txt" 'Yellow'
}

Say ""
Say "Tayyor! Endi botni qayta ishga tushiring (bot oynasini yopib, odatdagidek qayta oching)." 'Green'
Say "Ilova (Telegram ichida) yangi versiyani o'zi oladi - qo'shimcha hech narsa qilish shart emas." 'Green'
