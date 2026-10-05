"""Klaviaturalar va callback ma'lumotlari."""
from aiogram.filters.callback_data import CallbackData
from pydantic import Field
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

import loc
from tenancy import current_course
from i18n import LANG_BUTTONS, N_, tr, variants
from utils import DOC_TYPES, fmt_date

# ---------------------------------------------------------------- asosiy menyu
# Tugma matnlari o'zbekcha kalit; ota-ona tanlagan tilda ko'rsatiladi, har uchala tildagi ko'rinishi ham taniladi
BTN_CHILDREN = N_("👨‍🎓 Farzandim")
BTN_CHILDREN_OLD = "👨‍🎓 Farzandlarim"  # oldingi versiya tugmasi — ota-onalar telefonida qolgan bo'lishi mumkin
BTN_ATTENDANCE = N_("📊 Davomat")
BTN_SCHEDULE = N_("📅 Dars jadvali")
BTN_GRADES = N_("📝 Baholar")
BTN_NEWS = N_("📢 E'lonlar")
BTN_ASK = N_("✉️ Kurs koordinatoriga savol")
BTN_SETTINGS = N_("⚙️ Bildirishnomalar")
BTN_INFO = N_("ℹ️ Foydali ma'lumot")
BTN_LANG = N_("🌐 Til")
_MENU = (BTN_CHILDREN, BTN_ATTENDANCE, BTN_SCHEDULE, BTN_GRADES, BTN_NEWS, BTN_ASK, BTN_SETTINGS, BTN_INFO, BTN_LANG)
MENU_TEXTS = {BTN_CHILDREN_OLD}.union(*(variants(b) for b in _MENU))


def btn(key: str) -> set[str]:
    """Menyu tugmasining barcha tillardagi matnlari (filtr uchun)."""
    return variants(key) | ({BTN_CHILDREN_OLD} if key == BTN_CHILDREN else set())

ADD_CHILD_CB = "addchild"


def webapp_url(route: str = "") -> str | None:
    """Web App manzili (WEBAPP_URL sozlanmagan bo'lsa — None). route — ilova ichidagi sahifa: «/chat/3-kurs/12»."""
    from config import WEBAPP_URL
    if not WEBAPP_URL:
        return None
    return WEBAPP_URL + "/" + (f"#{route}" if route else "")


def webapp_kb(route: str = "", text: str | None = None) -> InlineKeyboardMarkup | None:
    """Xabar ostidagi «📱 Ilovada ochish» tugmasi (Web App sozlangan bo'lsa)."""
    url = webapp_url(route)
    if not url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text or tr("📱 Ilovada ochish"),
                                                                       web_app=WebAppInfo(url=url))]])


def main_menu() -> ReplyKeyboardMarkup:
    def b(key: str) -> KeyboardButton:
        return KeyboardButton(text=tr(key))
    url = webapp_url()
    return ReplyKeyboardMarkup(
        keyboard=([[KeyboardButton(text=tr("📱 Ilovani ochish"), web_app=WebAppInfo(url=url))]] if url else []) + [
            [b(BTN_CHILDREN)],
            [b(BTN_ATTENDANCE), b(BTN_SCHEDULE)],
            [b(BTN_GRADES), b(BTN_NEWS)],
            [b(BTN_ASK)],
            [b(BTN_SETTINGS), b(BTN_INFO)],
            [b(BTN_LANG)],
        ],
        resize_keyboard=True,
        input_field_placeholder=tr("Farzandingiz ism-familiyasini yozing…"),
    )


class LangCb(CallbackData, prefix="lang"):
    l: str  # uz | ru | en


def lang_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, label in LANG_BUTTONS.items():
        kb.button(text=label, callback_data=LangCb(l=code))
    kb.adjust(1)
    return kb.as_markup()


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=tr("📱 Telefon raqamni yuborish"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ---------------------------------------------------------------- callback turlari
def _course() -> str | None:
    """Tugma yaratilayotgan kurs (ko'p kursli rejim): ota-ona tugmasi bosilganda so'rov shu kurs bazasiga boradi.
    Bitta bazali rejimda — None (tugmada bo'sh qoladi)."""
    return current_course() or None


class ChildCb(CallbackData, prefix="c"):
    sid: int
    act: str  # card | att | sch | gr | ask
    t: str | None = Field(default_factory=_course)  # farzandning kursi


class AttCb(CallbackData, prefix="a"):
    sid: int
    p: str  # d0 d1 w0 w1 m0 sem subj abs cust hemis
    t: str | None = Field(default_factory=_course)


class SchCb(CallbackData, prefix="s"):
    sid: int
    p: str  # d0 d1 w0 w1
    t: str | None = Field(default_factory=_course)


class SetCb(CallbackData, prefix="set"):
    key: str


class LinkCb(CallbackData, prefix="lr"):
    rid: int
    ok: int


class AnsCb(CallbackData, prefix="q"):
    qid: int


class ImpCb(CallbackData, prefix="imp"):
    kind: str


class BcCb(CallbackData, prefix="bc"):
    act: str  # all | groups | send | cancel


class DocGetCb(CallbackData, prefix="dg"):  # ota-ona hujjatni qayta oladi
    did: int
    t: str | None = Field(default_factory=_course)


class DocStuCb(CallbackData, prefix="ds"):  # kurs koordinatori: talabani tanlash
    sid: int


class DocTypeCb(CallbackData, prefix="dt"):  # kurs koordinatori: hujjat turini tanlash
    t: str


class DocPickCb(CallbackData, prefix="dp"):  # kurs koordinatori: hujjatdagi talabani belgilash / olib tashlash
    sid: int


class DocActCb(CallbackData, prefix="da"):  # kurs koordinatori: send | student | type | cancel
    act: str


class DocRevCb(CallbackData, prefix="dr"):  # kurs koordinatori: hujjatni qaytarib olish
    did: int
    sure: int = 0   # 0 — tasdiq so'rash, 1 — qaytarib olish, 2 — fikridan qaytdi
    b: int = 0      # 1 — shu yuborishdagi barcha talabalar nusxalari


class GuardCb(CallbackData, prefix="g"):
    uid: int
    ok: int  # 1 — ota-ona, ruxsat berish; 0 — bloklangan qolsin


class GroupCb(CallbackData, prefix="tg"):
    cid: int
    act: str  # off — talabalar guruhi emas


# ---------------------------------------------------------------- ota-ona klaviaturalari
def children_kb(children: list[dict], act: str = "card", add: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in children:
        label = loc.student_name(c) + (f" · {c['group_name']}" if c.get("group_name") else "")
        kb.button(text=label[:60], callback_data=ChildCb(sid=c["id"], act=act, t=c.get("course_key") or _course()))
    if add:
        kb.button(text=tr("➕ Farzand qo'shish"), callback_data=ADD_CHILD_CB)
    kb.adjust(1)
    return kb.as_markup()


def add_child_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr("➕ Farzandni bog'lash"), callback_data=ADD_CHILD_CB)
    return kb.as_markup()


def child_card_kb(sid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr("📊 Davomat"), callback_data=ChildCb(sid=sid, act="att"))
    kb.button(text=tr("📅 Dars jadvali"), callback_data=ChildCb(sid=sid, act="sch"))
    kb.button(text=tr("📝 Baholar"), callback_data=ChildCb(sid=sid, act="gr"))
    kb.button(text=tr("📄 Hujjatlar"), callback_data=ChildCb(sid=sid, act="doc"))
    kb.button(text=tr("💰 Moliyaviy qarzdorlik"), callback_data=ChildCb(sid=sid, act="fin"))
    kb.button(text=tr("📚 Akademik qarzdorlik"), callback_data=ChildCb(sid=sid, act="acad"))
    kb.button(text=tr("📈 Dinamika"), callback_data=ChildCb(sid=sid, act="dyn"))
    kb.button(text=tr("✉️ Kurs koordinatoriga yozish"), callback_data=ChildCb(sid=sid, act="ask"))
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


def finance_kb(sid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr("💰 Kontraktdan qarzdorlik"), callback_data=ChildCb(sid=sid, act="fk"))
    kb.button(text=tr("💳 Trimestrdan qarzdorlik"), callback_data=ChildCb(sid=sid, act="ft"))
    kb.button(text=tr("🏠 Farzand sahifasi"), callback_data=ChildCb(sid=sid, act="card"))
    kb.adjust(1)
    return kb.as_markup()


def attendance_kb(sid: int, hemis: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    items = [
        (N_("Bugun"), "d0"), (N_("Kecha"), "d1"),
        (N_("Shu hafta"), "w0"), (N_("O'tgan hafta"), "w1"),
        (N_("Shu oy"), "m0"), (N_("Semestr boshidan"), "sem"),
        (N_("📚 Fanlar kesimida"), "subj"), (N_("❗ Qoldirilgan darslar"), "abs"),
        (N_("🗓 Sana yoki oraliq tanlash"), "cust"),
    ]
    if hemis:
        items.append((N_("📊 HEMIS statistikasi va chegaralar"), "hemis"))
    for text, p in items:
        kb.button(text=tr(text), callback_data=AttCb(sid=sid, p=p))
    kb.button(text=tr("⬅️ Orqaga"), callback_data=ChildCb(sid=sid, act="card"))
    kb.adjust(2, 2, 2, 2, 1, 1, 1)
    return kb.as_markup()


def schedule_kb(sid: int, selected: int | None = None) -> InlineKeyboardMarkup:
    """Dars jadvali: hafta kunlari (Dushanba — Shanba). Bugungi kun — 📍, tanlangan kun — 🔹.
    Yakshanba kuni — kelasi haftaning kunlari (shu hafta darslari tugagan)."""
    from utils import WEEKDAYS, today
    wd = today().weekday()
    kb = InlineKeyboardBuilder()
    for i, name in enumerate(WEEKDAYS[:6]):
        text = tr(name)
        if i == wd:
            text = "📍 " + text
        elif i == selected:
            text = "🔹 " + text
        kb.button(text=text, callback_data=SchCb(sid=sid, p=f"wd{i}"))
    kb.button(text=tr("⬅️ Orqaga"), callback_data=ChildCb(sid=sid, act="card"))
    kb.adjust(3, 3, 1)
    return kb.as_markup()


def back_kb(sid: int, section: str) -> InlineKeyboardMarkup:
    """section: att | sch | card — qaysi menyuga qaytish."""
    kb = InlineKeyboardBuilder()
    names = {"att": N_("⬅️ Davomat menyusi"), "sch": N_("⬅️ Jadval menyusi"), "fin": N_("⬅️ Moliyaviy qarzdorlik")}
    if section in names:
        kb.button(text=tr(names[section]), callback_data=ChildCb(sid=sid, act=section))
    kb.button(text=tr("🏠 Farzand sahifasi"), callback_data=ChildCb(sid=sid, act="card"))
    kb.adjust(1)
    return kb.as_markup()


def settings_kb(parent: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    items = [
        ("notify_instant", N_("Dars qoldirilganda darhol xabar")),
        ("notify_daily", N_("Har kuni kechqurun xulosa")),
        ("notify_warn", N_("Muhim ogohlantirishlar: dars qoldirish chegaralari, akademik qarz")),
        ("notify_pay", N_("Kontrakt va trimestr to'lovi: qarzdorlik va muddat eslatmalari")),
    ]
    for key, text in items:
        mark = "✅" if parent.get(key) else "⬜"
        kb.button(text=f"{mark} {tr(text)}", callback_data=SetCb(key=key))
    kb.adjust(1)
    return kb.as_markup()


# ---------------------------------------------------------------- admin klaviaturalari
def link_request_kb(rid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=LinkCb(rid=rid, ok=1))
    kb.button(text="❌ Rad etish", callback_data=LinkCb(rid=rid, ok=0))
    kb.adjust(2)
    return kb.as_markup()


def answer_kb(qid: int, sid: int | None = None, parent_id: int | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Javob berish", callback_data=AnsCb(qid=qid))
    url = webapp_url(f"/staff/chat/{current_course() or '_'}/{sid}/{parent_id}") if sid and parent_id else None
    if url:
        kb.row(InlineKeyboardButton(text="📱 Ilovada suhbat", web_app=WebAppInfo(url=url)))
    return kb.as_markup()


IMPORT_KINDS = (("👥 Talabalar", "students"), ("📊 Davomat", "attendance"),
                ("📅 Dars jadvali (asosiy fanlar)", "schedule"), ("📝 Baholar", "grades"),
                ("🎯 Tanlov/2-til: kim o'qiydi", "enroll"), ("🗓 Tanlov/2-til: jadval", "elsched"),
                ("💰 Kontrakt qarzdorligi", "debts"), ("🗓 Trimestr qarzdorligi", "debts_t"),
                ("📚 Akademik qarzdorlar", "acad_debts"), ("🎓 GPA (HEMIS)", "gpa"),
                ("📱 Talaba telefonlari", "phones"), ("🌐 Tarjimalar", "translations"))


def import_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🤖 Aralash fayllar — turini bot o'zi aniqlaydi", callback_data=ImpCb(kind="auto"))
    for text, kind in IMPORT_KINDS:
        kb.button(text=text, callback_data=ImpCb(kind=kind))
    kb.adjust(1, 2, 2, 2, 2, 2, 2)
    return kb.as_markup()


def broadcast_target_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Barcha ota-onalarga", callback_data=BcCb(act="all"))
    kb.button(text="🎯 Guruhlar bo'yicha", callback_data=BcCb(act="groups"))
    kb.button(text="✖️ Bekor qilish", callback_data=BcCb(act="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Yuborish", callback_data=BcCb(act="send"))
    kb.button(text="✖️ Bekor qilish", callback_data=BcCb(act="cancel"))
    kb.adjust(2)
    return kb.as_markup()


def guard_kb(uid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ota-ona — ruxsat berish", callback_data=GuardCb(uid=uid, ok=1))
    kb.button(text="🚫 Bloklangan qolsin", callback_data=GuardCb(uid=uid, ok=0))
    kb.adjust(1)
    return kb.as_markup()


def tg_group_kb(chat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Bu talabalar guruhi emas", callback_data=GroupCb(cid=chat_id, act="off"))
    return kb.as_markup()


# ---------------------------------------------------------------- rasmiy hujjatlar
def documents_kb(sid: int, docs: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, d in enumerate(docs[:20], 1):
        icon, name = DOC_TYPES.get(d["doc_type"], DOC_TYPES["boshqa"])
        day = fmt_date(d["doc_date"] or d["created_at"][:10], False)[:5]
        kb.button(text=f"📥 {i}. {icon} {tr(name)} · {day}", callback_data=DocGetCb(did=d["id"]))
    kb.button(text=tr("🏠 Farzand sahifasi"), callback_data=ChildCb(sid=sid, act="card"))
    kb.adjust(1)
    return kb.as_markup()


def doc_students_kb(students: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for st in students[:8]:
        kb.button(text=f"{st['full_name']} · {st.get('group_name') or '—'}", callback_data=DocStuCb(sid=st["id"]))
    kb.button(text="✖️ Bekor qilish", callback_data=DocActCb(act="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def doc_type_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, (icon, name) in DOC_TYPES.items():
        kb.button(text=f"{icon} {'Boshqa rasmiy hujjat' if key == 'boshqa' else name}", callback_data=DocTypeCb(t=key))
    kb.button(text="✖️ Bekor qilish", callback_data=DocActCb(act="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def doc_pick_kb(students: list[dict], selected: set[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for st in students[:30]:
        mark = "✅" if st["id"] in selected else "⬜"
        kb.button(text=f"{mark} {st['full_name']} · {st.get('group_name') or '—'}", callback_data=DocPickCb(sid=st["id"]))
    kb.button(text="➕ Boshqa talaba qo'shish", callback_data=DocActCb(act="add"))
    kb.button(text="▶️ Davom etish", callback_data=DocActCb(act="picked"))
    kb.button(text="✖️ Bekor qilish", callback_data=DocActCb(act="cancel"))
    kb.adjust(1)
    return kb.as_markup()


def doc_confirm_kb(checked: bool = True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Ota-onalarga yuborish" if checked else "📤 Boshqa talabalar yo'q — yuborish",
              callback_data=DocActCb(act="send"))
    kb.button(text="👨‍🎓 Talabalarni o'zgartirish", callback_data=DocActCb(act="student"))
    kb.button(text="🏷 Turini o'zgartirish", callback_data=DocActCb(act="type"))
    kb.button(text="✖️ Bekor qilish", callback_data=DocActCb(act="cancel"))
    kb.adjust(1, 2, 1)
    return kb.as_markup()


def doc_revoke_kb(doc_id: int, sure: bool = False, batch: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    b = int(batch)
    if sure:
        kb.button(text="⚠️ Ha, qaytarib olinsin", callback_data=DocRevCb(did=doc_id, sure=1, b=b))
        kb.button(text="↩️ Yo'q, qoldirilsin", callback_data=DocRevCb(did=doc_id, sure=2, b=b))
        kb.adjust(2)
    else:
        kb.button(text="🗑 Qaytarib olish (xato yuborilgan bo'lsa)", callback_data=DocRevCb(did=doc_id, b=b))
    return kb.as_markup()


# ---------------------------------------------------------------- kurs koordinatori paneli
class PanelCb(CallbackData, prefix="pn"):
    v: str        # home | prob | acad | kontrakt | trimestr | att
    f: str = ""   # filtr: kurs yoki guruh


def panel_kb(f: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for text, v in (("🔴 Muammoli talabalar", "prob"), ("📚 Akademik qarzdorlar", "acad"), ("🎓 GPA past", "gpa"),
                    ("💰 Kontrakt qarzdorlar", "kontrakt"), ("💳 Trimestr qarzdorlar", "trimestr"),
                    ("🚫 Davomat muammosi", "att"), ("🔁 Yangilash", "home")):
        kb.button(text=text, callback_data=PanelCb(v=v, f=f[:30]))
    kb.button(text="📥 Excel hisobot", callback_data=ExpCb(fmt="x", s="all", f=f[:30]))
    kb.button(text="📄 PDF hisobot", callback_data=ExpCb(fmt="p", s="all", f=f[:30]))
    kb.adjust(1, 2, 2, 2, 2)
    return kb.as_markup()


# ---------------------------------------------------------------- hisobot eksporti (Excel / PDF)
class ExpCb(CallbackData, prefix="ex"):
    fmt: str      # x — Excel, p — PDF
    s: str        # all | prob | att | acad | kontrakt | trimestr
    f: str = ""   # filtr: kurs yoki guruh


def export_kb(section: str = "all", f: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Excel", callback_data=ExpCb(fmt="x", s=section, f=f[:30]))
    kb.button(text="📄 PDF", callback_data=ExpCb(fmt="p", s=section, f=f[:30]))
    kb.adjust(2)
    return kb.as_markup()



# ---------------------------------------------------------------- import tekshiruvi
class ImpOkCb(CallbackData, prefix="io"):
    act: str      # cancel | go | switch
    tok: str = ""  # qaysi fayl (bir nechta fayl yuklanayotganda har biri alohida so'raladi)


def imp_confirm_kb(detected_title: str, tok: str = "", chosen_title: str = "") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ O'tkazib yuborish", callback_data=ImpOkCb(act="cancel", tok=tok))
    kb.button(text=f"✅ Baribir «{chosen_title}»" if chosen_title else "✅ Davom etish",
              callback_data=ImpOkCb(act="go", tok=tok))
    kb.button(text=f"🔄 «{detected_title}» sifatida yuklash", callback_data=ImpOkCb(act="switch", tok=tok))
    kb.adjust(2, 1)
    return kb.as_markup()


class ImpPickCb(CallbackData, prefix="ip"):
    tok: str
    kind: str     # import turi yoki «skip»


def imp_pick_kb(tok: str) -> InlineKeyboardMarkup:
    """Aralash rejimda turi aniqlanmagan fayl uchun — kurs koordinatori o'zi tanlaydi."""
    kb = InlineKeyboardBuilder()
    for text, kind in IMPORT_KINDS:
        kb.button(text=text, callback_data=ImpPickCb(tok=tok, kind=kind))
    kb.button(text="⏭ O'tkazib yuborish", callback_data=ImpPickCb(tok=tok, kind="skip"))
    kb.adjust(2)
    return kb.as_markup()


# ---------------------------------------------------------------- kurs koordinatori va super-admin menyulari
# (ota-ona menyusi ularga ko'rsatilmaydi; interfeys o'zbek tilida)
BTN_C_IMPORT, BTN_C_PANEL = "📥 Fayl yuklash", "📊 Kurs holati"
BTN_C_SEARCH, BTN_C_STAT = "🔎 Talaba qidirish", "📈 Statistika"
BTN_C_ANNOUNCE, BTN_C_DOC = "📢 E'lon yuborish", "📄 Hujjat yuborish"
BTN_C_DEBTS, BTN_C_LIMITS = "💰 Qarzdorlar", "📏 Chegaralar"
BTN_C_REPORT, BTN_C_TERMS = "📥 Hisobot (Excel/PDF)", "🌐 Tarjimalar"
BTN_C_HELP, BTN_C_TEMPLATES = "ℹ️ Barcha buyruqlar", "📑 Shablonlar"
BTN_C_DESK = "💻 Kompyuter versiyasi"
BTN_S_MENU = "🛡 Super-admin menyusi"
COORD_BUTTONS = {BTN_C_IMPORT, BTN_C_PANEL, BTN_C_SEARCH, BTN_C_STAT, BTN_C_ANNOUNCE, BTN_C_DOC, BTN_C_DEBTS,
                 BTN_C_LIMITS, BTN_C_REPORT, BTN_C_TERMS, BTN_C_HELP, BTN_C_TEMPLATES, BTN_C_DESK}

BTN_S_COURSES, BTN_S_OVERVIEW = "🏫 Kurslar va koordinatorlar", "📊 Umumiy holat"
BTN_S_ENTER, BTN_S_NEW = "🔀 Kursga kirish", "➕ Yangi kurs"
BTN_S_BACKUP, BTN_S_ERRORS = "💾 Zaxira nusxa", "🧾 Xatolar jurnali"
BTN_S_TEMPLATES = "📑 Shablonlar (import namunalari)"
SUPER_BUTTONS = {BTN_S_COURSES, BTN_S_OVERVIEW, BTN_S_ENTER, BTN_S_NEW, BTN_S_BACKUP, BTN_S_ERRORS, BTN_S_MENU,
                 BTN_S_TEMPLATES}


def coordinator_menu(course_title: str = "", super_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [[BTN_C_IMPORT, BTN_C_PANEL], [BTN_C_SEARCH, BTN_C_STAT], [BTN_C_ANNOUNCE, BTN_C_DOC],
            [BTN_C_DEBTS, BTN_C_LIMITS], [BTN_C_REPORT, BTN_C_TERMS], [BTN_C_TEMPLATES, BTN_C_HELP], [BTN_C_DESK]]
    if super_admin:
        rows.append([BTN_S_MENU])
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t) for t in r] for r in rows], resize_keyboard=True,
                               input_field_placeholder=f"{course_title}: familiya — talaba qidirish" if course_title
                               else "Familiya yozing — talaba qidirish")


def super_menu() -> ReplyKeyboardMarkup:
    rows = [[BTN_S_COURSES], [BTN_S_OVERVIEW, BTN_S_ENTER], [BTN_S_NEW], [BTN_S_TEMPLATES],
            [BTN_S_BACKUP, BTN_S_ERRORS], [BTN_C_DESK]]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t) for t in r] for r in rows], resize_keyboard=True)


class SupCb(CallbackData, prefix="su"):
    a: str            # course | enter | addc | delc | delc_ok | rename | list | grp | gt | gw | gc
    k: str = ""       # kurs kaliti
    u: int = 0        # foydalanuvchi (koordinator) ID
    g: int = -1       # guruh tartib raqami (koordinator guruhlari ekranida)


def courses_kb(courses: list[dict], action: str = "course") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in courses:
        kb.button(text=f"{c['title']} · 👤 {len(c['admins'])}", callback_data=SupCb(a=action, k=c["key"]))
    kb.adjust(1)
    return kb.as_markup()


def course_card_kb(key: str, admins: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Koordinator qo'shish", callback_data=SupCb(a="addc", k=key))
    for a in admins:
        kb.button(text=f"👥 {a['label']}: guruhlar", callback_data=SupCb(a="grp", k=key, u=a["user_id"]))
    for a in admins:
        kb.button(text=f"🗑 {a['label']}", callback_data=SupCb(a="delc", k=key, u=a["user_id"]))
    kb.button(text="✏️ Kurs nomini o'zgartirish", callback_data=SupCb(a="rename", k=key))
    kb.button(text="🔀 Shu kursga kirish", callback_data=SupCb(a="enter", k=key))
    kb.button(text="⬅️ Kurslar", callback_data=SupCb(a="list"))
    kb.adjust(1)
    return kb.as_markup()


def coord_groups_kb(key: str, uid: int, groups: list[dict]) -> InlineKeyboardMarkup:
    """Koordinator guruhlari: ✅ — unga biriktirilgan, 🔒 — boshqa koordinatorniki, ▫️ — bo'sh (bosib almashtiriladi)."""
    kb = InlineKeyboardBuilder()
    for i, g in enumerate(groups):
        mark = "✅" if g["owner"] == uid else ("🔒" if g["owner"] else "▫️")
        kb.button(text=f"{mark} {g['name']} ({g['students']})", callback_data=SupCb(a="gt", k=key, u=uid, g=i))
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text="✍️ Guruh nomlarini yozish", callback_data=SupCb(a="gw", k=key, u=uid).pack()))
    kb.row(InlineKeyboardButton(text="🧹 Hammasini olib tashlash", callback_data=SupCb(a="gc", k=key, u=uid).pack()))
    kb.row(InlineKeyboardButton(text="⬅️ Kurs", callback_data=SupCb(a="course", k=key).pack()))
    return kb.as_markup()


def pick_user_kb() -> ReplyKeyboardMarkup:
    """Telegram'ning o'zidan foydalanuvchini tanlash (kontaktlar ro'yxati) — ID ni qo'lda terish shart emas."""
    from aiogram.types import KeyboardButtonRequestUsers
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="👤 Foydalanuvchini tanlash", request_users=KeyboardButtonRequestUsers(
        request_id=1, user_is_bot=False, max_quantity=1, request_name=True, request_username=True))],
        [KeyboardButton(text="✖️ Bekor qilish")]], resize_keyboard=True, one_time_keyboard=True)


# ---------------------------------------------------------------- shablonlar (super-admin)
class TplCb(CallbackData, prefix="tp"):
    a: str        # list | open | get | up | edit | vers | getv | restore | reset | hide | show | del | del_ok | new | newk | save
    s: str = ""   # shablon (slot)
    v: int = 0    # versiya yozuvi ID si
    k: str = ""   # import turi (yangi shablon) yoki «n» — koordinatorlarga yuborish


class TplMapCb(CallbackData, prefix="tm"):
    f: str        # maydon | skip | skipall


def templates_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in items:
        badge = "🙈" if t["hidden"] else "🆕" if not t["builtin"] else "✏️" if t["changed"] else "📄"
        ver = f" · v{t['version']}" if t["version"] else ""
        kb.button(text=f"{badge} {t['title']}{ver}"[:60], callback_data=TplCb(a="open", s=t["slot"]))
    kb.button(text="➕ Yangi shablon qo'shish", callback_data=TplCb(a="new"))
    kb.adjust(1)
    return kb.as_markup()


def template_card_kb(t: dict, has_versions: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬇️ Yuklab olish", callback_data=TplCb(a="get", s=t["slot"]))
    kb.button(text="🔄 Yangi versiya yuklash", callback_data=TplCb(a="up", s=t["slot"]))
    kb.button(text="✏️ Nomi va izohi", callback_data=TplCb(a="edit", s=t["slot"]))
    if has_versions:
        kb.button(text="📜 Versiyalar", callback_data=TplCb(a="vers", s=t["slot"]))
    if t["changed"]:
        kb.button(text="↩️ Asl shablonga qaytarish", callback_data=TplCb(a="reset", s=t["slot"]))
    if t["builtin"]:
        kb.button(text="👁 Koordinatorlarga ko'rsatish" if t["hidden"] else "🙈 Koordinatorlardan yashirish",
                  callback_data=TplCb(a="show" if t["hidden"] else "hide", s=t["slot"]))
    else:
        kb.button(text="🗑 O'chirish", callback_data=TplCb(a="del", s=t["slot"]))
    kb.button(text="« Shablonlar ro'yxati", callback_data=TplCb(a="list"))
    kb.adjust(1, 2, 1, 1, 1, 1)
    return kb.as_markup()


def map_field_kb(fields: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f, title in fields:
        kb.button(text=title, callback_data=TplMapCb(f=f))
    kb.button(text="🚫 E'tiborsiz qoldirish", callback_data=TplMapCb(f="skip"))
    kb.button(text="⏭ Qolganlarini e'tiborsiz qoldirish", callback_data=TplMapCb(f="skipall"))
    kb.adjust(2)
    return kb.as_markup()


def template_save_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Saqlash va koordinatorlarga yuborish", callback_data=TplCb(a="save", k="n"))
    kb.button(text="✅ Faqat saqlash", callback_data=TplCb(a="save"))
    kb.button(text="❌ Bekor qilish", callback_data=TplCb(a="list"))
    kb.adjust(1)
    return kb.as_markup()
