"""Zaxira nusxa: barcha kurs bazalari (data/<kurs>/bot.db) va umumiy ro'yxat (central.db) — bitta arxivga.

  • SQLite'ning o'z zaxira usuli (backup API): bot ishlab turgan paytda ham buzilmagan nusxa olinadi;
  • har bir nusxa yaxlitlikka tekshiriladi (PRAGMA integrity_check);
  • BACKUP_PASSWORD bo'lsa — arxiv AES-256 bilan shifrlanadi (unda talabalarning shaxsiy ma'lumotlari bor);
  • serverda backups/ papkasida oxirgi BACKUP_KEEP_DAYS kunlik arxivlar saqlanadi;
  • arxiv holat hisoboti bilan super-admin(lar)ga Telegram orqali yuboriladi (Telegram botlar 50 MB dan katta fayl
    yubora olmaydi — bunday holda faqat hisobot va arxivning serverdagi manzili).
"""
from __future__ import annotations

import logging
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import aiosqlite

from config import DATA_DIR, BACKUP_DIR, BACKUP_KEEP_DAYS, BACKUP_PASSWORD, BACKUP_SEND, SUPERADMIN_IDS
from database import db
from logsetup import errors_since
from tenancy import central, course_title
from utils import fmt_dt, now, now_iso

log = logging.getLogger(__name__)
TELEGRAM_LIMIT = 49 * 1024 * 1024


async def _copy(src: aiosqlite.Connection, dst_path: Path) -> str:
    """Ishlab turgan bazadan nusxa va yaxlitlik tekshiruvi; qaytaradi: «ok» yoki xato matni."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst = await aiosqlite.connect(str(dst_path))
    try:
        await src.backup(dst)
        async with dst.execute("PRAGMA integrity_check") as cur:
            row = await cur.fetchone()
        return row[0] if row else "?"
    finally:
        await dst.close()


async def make_backup() -> dict:
    stamp = now().strftime("%Y-%m-%d_%H%M")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    items, started = [], time.time()
    try:
        for key in db.keys():
            d = db.for_course(key)
            ok = await _copy(d.conn, tmp / key / "bot.db")
            docs = Path(DATA_DIR) / key / "documents"  # ilova va kompyuter versiyasidan yuborilgan hujjatlar
            if docs.is_dir() and any(docs.iterdir()):
                shutil.copytree(docs, tmp / key / "documents")
            s = await d.stats()
            items.append({"key": key, "title": course_title(key), "ok": ok, "students": s["students"],
                          "parents": s["parents_active"], "updated": await _last_update(d)})
        central_ok = await _copy(central.conn, tmp / "central.db")
        tpl_dir = Path(DATA_DIR) / "templates"  # super-admin yuklagan shablonlar (barcha versiyalar)
        if tpl_dir.exists():
            shutil.copytree(tpl_dir, tmp / "templates")
        reg_dir = Path(DATA_DIR) / "regulations"  # universitet ichki nizomlari (PDF)
        if reg_dir.exists():
            shutil.copytree(reg_dir, tmp / "regulations")
        manifest = [f"Zaxira nusxa: {stamp}", f"Kurslar: {len(items)}", ""]
        manifest += [f"{i['key']}: {i['title']} — talabalar {i['students']}, ota-onalar {i['parents']}, "
                     f"yaxlitlik: {i['ok']}" for i in items]
        manifest += [f"central.db — yaxlitlik: {central_ok}", "",
                     "Tiklash: botni to'xtating, kerakli <kurs>/bot.db (va central.db) faylini data/ papkasiga "
                     "qo'ying, botni qayta ishga tushiring. Shablonlar: templates/ papkasini data/templates/ ga."]
        (tmp / "manifest.txt").write_text("\n".join(manifest), encoding="utf-8")
        path = BACKUP_DIR / f"zaxira_{stamp}.zip"
        encrypted = False
        if BACKUP_PASSWORD:
            try:
                import pyzipper
                with pyzipper.AESZipFile(path, "w", compression=pyzipper.ZIP_DEFLATED,
                                         encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(BACKUP_PASSWORD.encode())
                    for f in sorted(tmp.rglob("*")):
                        if f.is_file():
                            zf.write(f, f.relative_to(tmp).as_posix())
                encrypted = True
            except ImportError:
                log.warning("BACKUP_PASSWORD berilgan, lekin pyzipper o'rnatilmagan — arxiv shifrlanmadi")
        if not encrypted:
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for f in sorted(tmp.rglob("*")):
                    if f.is_file():
                        zf.write(f, f.relative_to(tmp).as_posix())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    removed = prune()
    bad = [i for i in items if i["ok"] != "ok"] + ([{"key": "central.db"}] if central_ok != "ok" else [])
    if bad:
        log.error("Zaxira nusxada yaxlitlik xatosi: %s", ", ".join(i["key"] for i in bad))
    info = {"path": path, "size": path.stat().st_size, "items": items, "central_ok": central_ok,
            "encrypted": encrypted, "removed": removed, "seconds": round(time.time() - started, 1)}
    await central.set_meta("last_backup", now_iso())
    log.info("Zaxira nusxa: %s (%s bayt, %s kurs)", path.name, info["size"], len(items))
    return info


async def _last_update(d) -> str | None:
    vals = [r["value"] for r in await d.fetchall("SELECT value FROM settings WHERE key LIKE 'updated:%'") if r["value"]]
    return max(vals) if vals else None


def prune() -> int:
    """BACKUP_KEEP_DAYS kundan eski arxivlarni o'chiradi."""
    edge = time.time() - BACKUP_KEEP_DAYS * 86400
    n = 0
    for f in BACKUP_DIR.glob("zaxira_*.zip"):
        if f.stat().st_mtime < edge:
            f.unlink(missing_ok=True)
            n += 1
    return n


def report(info: dict) -> str:
    kb = info["size"] / 1024
    size = f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{max(kb, 1):.0f} KB"
    lines = [f"💾 <b>Zaxira nusxa</b> — {fmt_dt(now_iso())}",
             f"Arxiv: <code>{info['path'].name}</code>, {size}"
             + (", 🔐 AES-256 bilan shifrlangan" if info["encrypted"] else ", ⚠️ shifrlanmagan (BACKUP_PASSWORD yo'q)"), ""]
    for i in info["items"]:
        lines.append(f"{'✅' if i['ok'] == 'ok' else '❌'} {i['title']}: talabalar {i['students']}, ota-onalar "
                     f"{i['parents']}" + (f", oxirgi import {fmt_dt(i['updated'])}" if i["updated"] else ", import yo'q"))
    lines.append(("✅" if info["central_ok"] == "ok" else "❌") + " Umumiy ro'yxat (central.db)")
    errs = errors_since(24)
    lines.append(f"\n🧾 So'nggi 24 soatdagi tizim xatolari: {errs}" + (" — /xatolar" if errs else " ✅"))
    if info["removed"]:
        lines.append(f"🗑 Eski arxivlar o'chirildi: {info['removed']} ta (saqlanadi: {BACKUP_KEEP_DAYS} kun)")
    return "\n".join(lines)


async def send(bot, info: dict, to: set[int] | None = None) -> int:
    from aiogram.types import FSInputFile
    text = report(info)
    sent = 0
    for uid in to or SUPERADMIN_IDS:
        try:
            if BACKUP_SEND and info["size"] <= TELEGRAM_LIMIT:
                await bot.send_document(uid, FSInputFile(info["path"]), caption=text[:1024])
                if len(text) > 1024:
                    await bot.send_message(uid, text)
            else:
                await bot.send_message(uid, text + ("\n\n📁 Arxiv serverda: <code>" + str(info["path"]) + "</code>"
                                                    + (" (Telegram chegarasi 50 MB dan katta)" if BACKUP_SEND else "")))
            sent += 1
        except Exception:
            log.exception("Zaxira nusxani super-adminga yuborib bo'lmadi (%s)", uid)
    return sent
