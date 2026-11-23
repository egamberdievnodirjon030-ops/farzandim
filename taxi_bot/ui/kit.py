"""Interfeys "qurilish bloklari": rangli tugmalar va kartalar.

Telegramning yangi imkoniyatlari ishlatiladi:
  * Bot API 9.4 — rangli tugmalar (`style`: success/danger/primary) va tugmadagi custom emoji;
  * Bot API 10.x — Rich Messages: sarlavha, xarita bloki, jadval, footer;
  * `disabled` (bosilmaydigan) va `copy_text` (nusxa olish) tugmalari.
Rich Message qo'llab-quvvatlanmasa, xuddi shu karta oddiy HTML matn sifatida yuboriladi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape as _escape

from aiogram.enums import ButtonStyle
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CopyTextButton,
    DisabledButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputRichBlockDivider,
    InputRichBlockFooter,
    InputRichBlockMap,
    InputRichBlockParagraph,
    InputRichBlockSectionHeading,
    InputRichBlockTable,
    InputRichMessage,
    KeyboardButton,
    Location,
    RichBlockCaption,
    RichBlockTableCell,
    RichTextBold,
    WebAppInfo,
)

SUCCESS = ButtonStyle.SUCCESS.value
DANGER = ButtonStyle.DANGER.value
PRIMARY = ButtonStyle.PRIMARY.value

# Tugmalardagi custom emoji (ixtiyoriy). Kalit -> custom_emoji_id. `configure()` orqali o'rnatiladi.
_EMOJI_IDS: dict[str, str] = {}


def h(text: object) -> str:
    """HTML uchun xavfsiz matn (apostrof — o', g' — o'zgarmaydi)."""
    return _escape(str(text), quote=False)


def configure(emoji_ids: dict[str, str]) -> None:
    _EMOJI_IDS.clear()
    _EMOJI_IDS.update(emoji_ids)


# --- Callback ma'lumotlari ------------------------------------------------------


class PCb(CallbackData, prefix="p"):
    """Yo'lovchi tugmalari."""

    action: str
    oid: int = 0
    val: int = 0


class DCb(CallbackData, prefix="d"):
    """Haydovchi tugmalari."""

    action: str
    oid: int = 0
    val: int = 0


class ACb(CallbackData, prefix="a"):
    """Admin tugmalari."""

    action: str
    id: int = 0


class RoleCb(CallbackData, prefix="role"):
    role: str


# --- Tugmalar -------------------------------------------------------------------


def btn(
    text: str,
    *,
    cb: CallbackData | str | None = None,
    url: str | None = None,
    style: str | None = None,
    copy: str | None = None,
    disabled: bool = False,
    emoji: str | None = None,
    web_app: str | None = None,
) -> InlineKeyboardButton:
    kwargs: dict = {"text": text}
    if style:
        kwargs["style"] = style
    if emoji and emoji in _EMOJI_IDS:
        kwargs["icon_custom_emoji_id"] = _EMOJI_IDS[emoji]
    if disabled:
        kwargs["disabled"] = DisabledButton()
    elif web_app:
        kwargs["web_app"] = WebAppInfo(url=web_app)
    elif url:
        kwargs["url"] = url
    elif copy is not None:
        kwargs["copy_text"] = CopyTextButton(text=copy)
    else:
        kwargs["callback_data"] = cb.pack() if isinstance(cb, CallbackData) else (cb or "noop")
    return InlineKeyboardButton(**kwargs)


def kb_button(
    text: str,
    *,
    style: str | None = None,
    location: bool = False,
    contact: bool = False,
    emoji: str | None = None,
) -> KeyboardButton:
    kwargs: dict = {"text": text}
    if style:
        kwargs["style"] = style
    if emoji and emoji in _EMOJI_IDS:
        kwargs["icon_custom_emoji_id"] = _EMOJI_IDS[emoji]
    if location:
        kwargs["request_location"] = True
    if contact:
        kwargs["request_contact"] = True
    return KeyboardButton(**kwargs)


def inline(*rows: list[InlineKeyboardButton] | InlineKeyboardButton | None) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        if row is None:
            continue
        if isinstance(row, InlineKeyboardButton):
            keyboard.append([row])
        elif row:
            keyboard.append(list(row))
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# --- Kartalar -------------------------------------------------------------------


@dataclass
class Card:
    """Bitta karta — Rich Message va oddiy HTML ko'rinishida chiqariladi."""

    title: str
    rows: list[tuple[str, str]] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    map_point: tuple[float, float] | None = None
    map_caption: str | None = None
    map_zoom: int = 16
    footer: str | None = None

    def row(self, label: str, value: str | None) -> Card:
        if value:
            self.rows.append((label, value))
        return self

    def para(self, text: str | None) -> Card:
        if text:
            self.paragraphs.append(text)
        return self

    def map(self, lat: float, lon: float, caption: str | None = None, zoom: int = 16) -> Card:
        self.map_point = (lat, lon)
        self.map_caption = caption
        self.map_zoom = zoom
        return self

    def foot(self, text: str | None) -> Card:
        self.footer = text
        return self

    # Oddiy HTML (zaxira variant)
    def html(self) -> str:
        parts = [f"<b>{h(self.title)}</b>"]
        if self.rows:
            parts.append("\n".join(f"{h(k)}: <b>{h(v)}</b>" for k, v in self.rows))
        parts.extend(h(p) for p in self.paragraphs)
        if self.footer:
            parts.append(f"<i>{h(self.footer)}</i>")
        return "\n\n".join(parts)

    # Bot API 10.x Rich Message
    def rich(self) -> InputRichMessage:
        blocks: list = [InputRichBlockSectionHeading(text=self.title, size=2)]
        if self.map_point:
            lat, lon = self.map_point
            blocks.append(
                InputRichBlockMap(
                    location=Location(latitude=lat, longitude=lon),
                    zoom=self.map_zoom,
                    width=600,
                    height=300,
                    caption=RichBlockCaption(text=self.map_caption) if self.map_caption else None,
                )
            )
        if self.rows:
            blocks.append(
                InputRichBlockTable(
                    cells=[
                        [
                            RichBlockTableCell(align="left", valign="middle", text=label),
                            RichBlockTableCell(
                                align="right", valign="middle", text=RichTextBold(text=value)
                            ),
                        ]
                        for label, value in self.rows
                    ],
                    is_striped=True,
                    is_compact=True,
                )
            )
        for paragraph in self.paragraphs:
            blocks.append(InputRichBlockParagraph(text=paragraph))
        if self.footer:
            blocks.append(InputRichBlockDivider())
            blocks.append(InputRichBlockFooter(text=self.footer))
        return InputRichMessage(blocks=blocks)


@dataclass
class View:
    """Yuboriladigan xabar: karta (yoki oddiy matn) + tugmalar."""

    text: str
    markup: object | None = None
    rich: InputRichMessage | None = None

    @classmethod
    def of(cls, card: Card, markup: object | None = None) -> View:
        return cls(text=card.html(), markup=markup, rich=card.rich())

    @classmethod
    def plain(cls, text: str, markup: object | None = None) -> View:
        return cls(text=text, markup=markup)


def nav_url(navigator: str, lat: float, lon: float) -> str:
    """Bosilganda darhol yo'l (marshrut) ochiladigan havola."""
    if navigator == "yandex":
        return f"https://yandex.uz/maps/?rtext=~{lat:.6f}%2C{lon:.6f}&rtt=auto"
    if navigator == "waze":
        return f"https://waze.com/ul?ll={lat:.6f}%2C{lon:.6f}&navigate=yes"
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&destination={lat:.6f}%2C{lon:.6f}&travelmode=driving&dir_action=navigate"
    )


NAVIGATORS = {"google": "Google Maps", "yandex": "Yandex Maps", "waze": "Waze"}
