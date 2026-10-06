# =====================================================================
#  Ota-onalar davomat boti - ilovani (Telegram Web App) VAQTINCHA sinash
#  Cloudflare Quick Tunnel orqali HTTPS manzil ochadi, .env ga yozadi va botni ishga tushiradi.
#
#  Ishga tushirish: ilova_sinov.bat faylini ikki marta bosing
#  (yoki: powershell -ExecutionPolicy Bypass -File ilova_sinov.ps1)
#
#  FAQAT SINOV UCHUN: manzil har ishga tushirishda o'zgaradi, Cloudflare ishlash kafolatini bermaydi.
#  Doimiy ishlatish uchun - README, "Web App uchun HTTPS manzil" bo'limi.
# =====================================================================
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$envFile = Join-Path $PSScriptRoot '.env'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Say([string]$text, [string]$color = 'Gray') { Write-Host $text -ForegroundColor $color }

function Read-Shared([string]$path) {
    # cloudflared jurnalini u yozib turgan paytda o'qish (fayl band bo'lsa ham)
    try {
        $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
        $sr = New-Object System.IO.StreamReader($fs)
        $t = $sr.ReadToEnd(); $sr.Close(); return $t
    } catch { return '' }
}

function Set-WebAppUrl([string]$text, [string]$value) {
    $line = "WEBAPP_URL=$value"
    $rx = '(?m)^[ \t]*WEBAPP_URL[ \t]*=[^\r\n]*'
    if ([regex]::IsMatch($text, $rx)) { return [regex]::Replace($text, $rx, $line) }
    return $text.TrimEnd("`r", "`n") + "`r`n" + $line + "`r`n"
}

# ---------------------------------------------------------------- 1. .env
if (-not (Test-Path -LiteralPath $envFile)) {
    Say ".env fayli topilmadi." 'Red'
    Say "Avval:  copy .env.example .env   - so'ng .env da BOT_TOKEN va ADMIN_IDS ni to'ldiring." 'Yellow'
    exit 1
}
$envText = [System.IO.File]::ReadAllText($envFile)   # BOM bo'lsa ham to'g'ri o'qiladi
if (-not [regex]::IsMatch($envText, '(?m)^[ \t]*BOT_TOKEN[ \t]*=[ \t]*\S+')) {
    Say "BOT_TOKEN .env faylida to'ldirilmagan (@BotFather beradi)." 'Red'; exit 1
}
$port = 8080
$m = [regex]::Match($envText, '(?m)^[ \t]*WEBAPP_PORT[ \t]*=[ \t]*(\d+)')
if ($m.Success) { $port = [int]$m.Groups[1].Value }
if ($port -eq 0) { Say "WEBAPP_PORT=0 - ilova serveri o'chiq. .env da WEBAPP_PORT=8080 qiling." 'Red'; exit 1 }
$m = [regex]::Match($envText, '(?m)^[ \t]*WEBAPP_URL[ \t]*=([^\r\n]*)')
$oldUrl = if ($m.Success) { $m.Groups[1].Value.Trim() } else { $null }

# ---------------------------------------------------------------- 2. Python
$py = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { $cmd = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $cmd) { Say "Python topilmadi. README, 'O'rnatish' bo'limiga qarang." 'Red'; exit 1 }
    $py = $cmd.Source
}

# ---------------------------------------------------------------- 3. cloudflared
function Test-Exe([string]$path) {
    # to'liq yuklangan Windows dasturimi: "MZ" bilan boshlanadi va hajmi kamida 10 MB
    # (chala yuklangan fayl - disk to'lgan, internet uzilgan yoki antivirus - "not a valid Win32 application" beradi)
    try {
        $fi = Get-Item -LiteralPath $path -ErrorAction Stop
        if ($fi.Length -lt 10MB) { return $false }
        $fs = [System.IO.File]::OpenRead($path); $b = New-Object byte[] 2
        [void]$fs.Read($b, 0, 2); $fs.Close()
        return ($b[0] -eq 0x4D -and $b[1] -eq 0x5A)
    } catch { return $false }
}
$cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($cmd -and (Test-Exe $cmd.Source)) { $cf = $cmd.Source } else {
    $cf = Join-Path $PSScriptRoot 'cloudflared.exe'
    if ((Test-Path -LiteralPath $cf) -and -not (Test-Exe $cf)) {
        Say "cloudflared.exe buzilgan yoki chala yuklangan - o'chirilib, qayta yuklanadi." 'Yellow'
        Remove-Item -LiteralPath $cf -Force
    }
    if (-not (Test-Path -LiteralPath $cf)) {
        $arch = if ([Environment]::Is64BitOperatingSystem) { 'amd64' } else { '386' }
        Say "cloudflared yuklab olinmoqda (rasmiy GitHub sahifasidan, taxminan 60 MB)..." 'Cyan'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'
        $tmp = "$cf.part"
        try {
            Invoke-WebRequest -UseBasicParsing -OutFile $tmp `
                -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-$arch.exe"
        } catch {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
            Say "cloudflared yuklab olinmadi: $($_.Exception.Message)" 'Red'
            Say "Diskda bo'sh joy (kamida 100 MB) va internetni tekshiring yoki cloudflared-windows-$arch.exe ni qo'lda yuklab, shu papkaga cloudflared.exe nomi bilan qo'ying." 'Yellow'
            exit 1
        }
        if (-not (Test-Exe $tmp)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
            Say "cloudflared chala yuklandi (diskda joy yetmagan yoki antivirus to'sgan bo'lishi mumkin)." 'Red'
            Say "Diskda joy bo'shating va qayta ishga tushiring." 'Yellow'
            exit 1
        }
        Move-Item -LiteralPath $tmp -Destination $cf -Force
    }
}

# ---------------------------------------------------------------- 4. Tunnel
$log = Join-Path ([System.IO.Path]::GetTempPath()) 'ota_ona_cloudflared.log'
if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
Say "Tunnel ochilmoqda: https://...trycloudflare.com  ->  http://127.0.0.1:$port" 'Cyan'
try {
    $tunnel = Start-Process -FilePath $cf -ArgumentList @('tunnel', '--no-autoupdate', '--url', "http://127.0.0.1:$port") `
        -RedirectStandardError $log -NoNewWindow -PassThru
} catch {
    Say "cloudflared ishga tushmadi: $($_.Exception.Message)" 'Red'
    if ($cf -eq (Join-Path $PSScriptRoot 'cloudflared.exe')) {
        Remove-Item -LiteralPath $cf -Force -ErrorAction SilentlyContinue
        Say "Buzilgan cloudflared.exe o'chirildi - skriptni qayta ishga tushiring, u yangidan yuklanadi." 'Yellow'
    } else {
        Say "Tizimdagi cloudflared ($cf) ishlamayapti - uni qayta o'rnating." 'Yellow'
    }
    exit 1
}

$url = $null
for ($i = 0; $i -lt 90 -and -not $url; $i++) {
    Start-Sleep -Seconds 1
    if ($tunnel.HasExited) { break }
    $mm = [regex]::Match((Read-Shared $log), 'https://(?!api\.)[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com')
    if ($mm.Success) { $url = $mm.Value }
}
if (-not $url) {
    Say "Tunnel manzilini olib bo'lmadi. cloudflared jurnalining oxiri:" 'Red'
    (Read-Shared $log) -split "`n" | Select-Object -Last 12 | ForEach-Object { Say "   $_" 'DarkGray' }
    Say "Internet ulanishini tekshiring; tarmoq (masalan, ofis tarmog'i) Cloudflare'ni to'sib qo'ygan bo'lishi mumkin." 'Yellow'
    if (-not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}

# ---------------------------------------------------------------- 5. .env ga yozish va bot
[System.IO.File]::WriteAllText($envFile, (Set-WebAppUrl $envText $url), $utf8NoBom)
Write-Host ''
Say "  Ilova manzili:  $url" 'Green'
Say "  Telegram'da botingizni oching va /start bosing - chat pastida 'Ilova' tugmasi paydo bo'ladi." 'Green'
Say "  To'xtatish: Ctrl+C. Tunnel yopiladi va .env dagi WEBAPP_URL avvalgi holatiga qaytadi." 'Yellow'
Write-Host ''
try {
    & $py bot.py
} finally {
    if (-not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
    $cur = [System.IO.File]::ReadAllText($envFile)
    $restore = if ($oldUrl) { $oldUrl } else { '' }
    [System.IO.File]::WriteAllText($envFile, (Set-WebAppUrl $cur $restore), $utf8NoBom)
    Say "Tunnel yopildi, .env tiklandi. Botni oddiy ishga tushirsangiz, 'Ilova' tugmasi o'zi olib tashlanadi." 'Cyan'
}
