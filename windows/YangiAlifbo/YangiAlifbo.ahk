; Yangi Özbek Lotin — Windows uçun, Keyman'siz.
; Klaviatura, uning tili va körinişi özgarmaydi: eski usulda yozasiz, matn yangi alifboga ögiriladi.
;
;   sh → ş    ch → ç    o' → ö    g' → ğ    harf + ' → ʼ (tutuq belgisi)
;   o' ning barça şakllari ögiriladi: o' o` o‘ o’ oʻ oʼ
;   AltGr (öng Alt) + S / C / O / G → ş ç ö ğ   (Caps Lock yoki Shift bilan → Ş Ç Ö Ğ)
;   AltGr + H / ' / `  → ögirmasdan oddiy belgi (sherzod@mail.uz kabi)
;   Ctrl + Alt + Space → yoqiş / öçiriş
;
; Işlaşi uçun AutoHotkey v2 kerak (bepul): https://www.autohotkey.com

#Requires AutoHotkey v2.0
#SingleInstance Force

APP_NAME := "Yangi alifbo"
ICON_ON := A_ScriptDir "\YangiAlifbo.ico"
ICON_OFF := A_ScriptDir "\YangiAlifbo-off.ico"
STARTUP_LINK := A_Startup "\Yangi alifbo.lnk"
SETTINGS := A_AppData "\YangiAlifbo.ini"
MENU_ON := "Yoqilgan`tCtrl+Alt+Space"
MENU_STARTUP := "Kompyuter yoqilganda işga tuşsin"

HELP_TEXT := "
(
Eski usulda yozavering, matn yangi alifboga özi ögiriladi:
    Sherzod → Şerzod,  O'zbekiston → Özbekiston,  choy → çoy,  tog' → toğ

AltGr (öng Alt) + S / C / O / G → ş ç ö ğ
Caps Lock yoniq bölsa → Ş Ç Ö Ğ

Ögirmasdan «sh» kerak bölsa (email, havola): s, keyin AltGr + H
Ctrl + Alt + Space — yoqiş / öçiriş

Parolingizda sh, ch yoki o' bölsa, parol yozişdan oldin öçirib turing.
)"

WELCOME_TEXT := "
(
Yangi alifbo işga tuşdi. Odatdagidek yozavering:
Sherzod → Şerzod,  O'zbekiston → Özbekiston.

Soat yonidagi Ş belgisi orqali yoqiş, öçiriş va yordam.

Kompyuter yoqilganda avtomatik işga tuşsinmi?
)"

; Apostrof örnida yoziladigan belgilar: ' ` ‘ ’ ʻ ʼ
APOS := ["'", Chr(0x60), Chr(0x2018), Chr(0x2019), Chr(0x02BB), Chr(0x02BC)]
TUTUQ := Chr(0x02BC)

; * darhol, ? söz içida ham, C katta-kiçik harf farqlanadi,
; Z ögirilgandan keyin hisob yangidan boşlanadi, T matn öz holicha yuboriladi
Rule(abbr, repl) => Hotstring(":*?CZT:" abbr, repl)

; sh → ş, ch → ç (Sh, SH → Ş; Ch, CH → Ç)
for pair in [["s", "ş", "Ş"], ["c", "ç", "Ç"]] {
    lo := pair[1]
    up := StrUpper(lo)
    Rule(lo "h", pair[2])
    Rule(lo "H", pair[2])
    Rule(up "h", pair[3])
    Rule(up "H", pair[3])
}

; o' → ö, g' → ğ
for a in APOS {
    Rule("o" a, "ö")
    Rule("O" a, "Ö")
    Rule("g" a, "ğ")
    Rule("G" a, "Ğ")
}

; boşqa harfdan keyin apostrof → ʼ (maʼno, sanʼat, şeʼr)
for a in APOS {
    if (a = TUTUQ)
        continue
    Loop Parse "abcdefhijklmnpqrstuvwxyz" {
        Rule(A_LoopField a, A_LoopField TUTUQ)
        Rule(StrUpper(A_LoopField) a, StrUpper(A_LoopField) TUTUQ)
    }
}

; AltGr + harf: 2 ta tugma bilan yangi harf. Caps Lock yoki Shift bilan — boş harf.
NewLetter(lower, upper) {
    SendText(GetKeyState("Shift") != GetKeyState("CapsLock", "T") ? upper : lower)
    Hotstring("Reset")
}
*>!s::NewLetter("ş", "Ş")
*>!c::NewLetter("ç", "Ç")
*>!o::NewLetter("ö", "Ö")
*>!g::NewLetter("ğ", "Ğ")

; AltGr + H / ' / `: ögirmasdan oddiy belgi
*>!h::NewLetter("h", "H")
*>!vkDE::NewLetter("'", "'")
*>!vkC0::NewLetter("``", "``")

; Ctrl + Alt + Space: yoqiş / öçiriş (öçiq paytda ham işlaydi)
#SuspendExempt
^!Space::Toggle()
#SuspendExempt False

Toggle(*) {
    Suspend(-1)
    UpdateState()
    ToolTip(APP_NAME ": " (A_IsSuspended ? "öçirildi" : "yoqildi"))
    SetTimer(() => ToolTip(), -1500)
}

ToggleStartup(*) {
    if FileExist(STARTUP_LINK)
        FileDelete(STARTUP_LINK)
    else
        FileCreateShortcut(A_AhkPath, STARTUP_LINK, A_ScriptDir, '"' A_ScriptFullPath '"', APP_NAME, ICON_ON)
    UpdateState()
}

ShowHelp(*) {
    MsgBox(HELP_TEXT, APP_NAME, "Iconi")
}

UpdateState() {
    on := !A_IsSuspended
    icon := on ? ICON_ON : ICON_OFF
    if FileExist(icon)
        TraySetIcon(icon, , true)
    A_IconTip := APP_NAME (on ? ": yoqilgan" : ": öçirilgan") "`nCtrl+Alt+Space — yoqiş / öçiriş"
    if on
        A_TrayMenu.Check(MENU_ON)
    else
        A_TrayMenu.Uncheck(MENU_ON)
    if FileExist(STARTUP_LINK)
        A_TrayMenu.Check(MENU_STARTUP)
    else
        A_TrayMenu.Uncheck(MENU_STARTUP)
}

; Soat yonidagi belgi menyusi
A_TrayMenu.Delete()
A_TrayMenu.Add(MENU_ON, Toggle)
A_TrayMenu.Add(MENU_STARTUP, ToggleStartup)
A_TrayMenu.Add()
A_TrayMenu.Add("Yordam", ShowHelp)
A_TrayMenu.Add("Çiqiş", (*) => ExitApp())
A_TrayMenu.Default := MENU_ON
UpdateState()

; Birinçi işga tuşganda
if (IniRead(SETTINGS, "main", "welcomed", "") = "") {
    IniWrite(1, SETTINGS, "main", "welcomed")
    if (MsgBox(WELCOME_TEXT, APP_NAME, "YesNo Iconi") = "Yes" && !FileExist(STARTUP_LINK))
        ToggleStartup()
}
