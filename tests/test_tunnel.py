"""Cloudflare tunnel: buzilgan yoki ishga tushmaydigan cloudflared bot ishini to'xtatmasligi kerak."""

from __future__ import annotations

import os
import stat

from taxi_bot.services import tunnel as tunnel_mod
from taxi_bot.services.tunnel import QuickTunnel, find_cloudflared, is_valid_binary


def test_broken_download_is_detected_and_removed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tunnel_mod.shutil, "which", lambda _name: None)
    (tmp_path / "cloudflared.exe").write_text("<html>Access denied</html>")  # tarmoq HTML qaytargan
    assert find_cloudflared() is None
    assert not (tmp_path / "cloudflared.exe").exists()  # keyingi safar qayta yuklanadi


def test_binary_validation(tmp_path):
    good = tmp_path / "ok"
    good.write_bytes((b"MZ" if os.name == "nt" else b"\x7fELF") + b"\0" * 6_000_000)
    small = tmp_path / "small"
    small.write_bytes(b"MZ" + b"\0" * 100)
    assert is_valid_binary(good) and not is_valid_binary(small) and not is_valid_binary(tmp_path / "yoq")


async def test_unrunnable_binary_does_not_crash(tmp_path, monkeypatch):
    """WinError 193 kabi holat: fayl bor, lekin ishga tushmaydi."""
    monkeypatch.chdir(tmp_path)
    fake = tmp_path / "cloudflared"
    fake.write_bytes(b"\x7fELF" + b"\0" * 6_000_000)  # sarlavha to'g'ri, ichi buzilgan
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(tunnel_mod, "is_valid_binary", lambda _p: True)
    assert await QuickTunnel(8081).start(timeout=3) is None


async def test_tunnel_url_is_read_from_cloudflared_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = tmp_path / "cloudflared"
    script.write_text('#!/bin/sh\necho "INF |  https://brave-fox-123.trycloudflare.com  |" >&2\nsleep 30\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(tunnel_mod, "is_valid_binary", lambda _p: True)
    t = QuickTunnel(8081)
    assert await t.start(timeout=5) == "https://brave-fox-123.trycloudflare.com"
    await t.stop()
    assert t.process.returncode is not None
