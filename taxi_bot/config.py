"""Loyiha sozlamalari (.env fayldan o'qiladi)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: object) -> object:
    """`1,2,3` ko'rinishidagi qiymatni ro'yxatga aylantiradi (JSON ham qabul qilinadi)."""
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("["):
            import json

            return json.loads(value)
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    # --- Botlar -------------------------------------------------------------
    passenger_bot_token: SecretStr
    # Bo'sh qoldirilsa — bitta bot rejimi: kirishda "Haydovchi / Yo'lovchi" so'raladi.
    driver_bot_token: SecretStr | None = None

    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    # Ariza, operator so'rovlari kabi xabarlar yuboriladigan guruh/chat (ixtiyoriy).
    admin_chat_id: int | None = None

    database_url: str = "sqlite+aiosqlite:///data/taxi.db"
    redis_url: str | None = None  # FSM uchun (ixtiyoriy)

    company_name: str = "Shahar Taksi"
    company_phone: str | None = None
    currency: str = "so'm"

    # --- Tarif --------------------------------------------------------------
    base_fare: int = 7000  # o'tirish narxi (base_km ichida)
    base_km: float = 2.0
    per_km: int = 2000
    free_wait_min: int = 3
    per_wait_min: int = 500
    min_fare: int = 7000
    price_round: int = 500
    commission_percent: float = 10.0
    min_driver_balance: int = 1000  # shundan kam balansda buyurtma kelmaydi
    welcome_bonus: int = 30000  # yangi haydovchiga (tasdiqlanganda) bir martalik bonus
    welcome_bonus_limit: int = 0  # 0 — barcha yangi haydovchilarga; N — faqat birinchi N tasiga

    # --- Qidiruv (dispetcherlik) -------------------------------------------
    wave_radii_km: Annotated[list[float], NoDecode] = Field(
        default_factory=lambda: [1.0, 2.0, 3.5, 5.0, 8.0]
    )
    wave_timeout_sec: float = 60.0  # har bir diapazon uchun kutish vaqti
    search_timeout_sec: float = 420.0  # umumiy qidiruv vaqti
    rescan_interval_sec: float = 15.0  # diapazonlar tugagach qayta skanerlash
    priority_rating: float = 4.8  # shu reytingdan yuqorilar birinchi ko'radi
    priority_headstart_sec: float = 10.0
    road_factor: float = 1.3  # to'g'ri chiziq -> yo'l masofasi koeffitsienti
    city_speed_kmh: float = 25.0
    osrm_url: str | None = None  # masalan: http://osrm:5000 (aniq yo'l masofasi uchun)
    # Marshrut chizig'i va narx uchun ommaviy OSRM serverlari (navbat bilan). O'chirish: ROUTE_URLS=none
    route_urls: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["https://routing.openstreetmap.de/routed-car", "https://router.project-osrm.org"]
    )
    max_offer_concurrency: int = 20

    # ❤️ Sevimli haydovchilar avval ko'radi (shu radius ichida bo'lsa)
    favorite_radius_km: float = 3.0
    favorite_headstart_sec: float = 10.0
    # 🏡 "Uyga" rejimi: manzil haydovchini uyiga kamida shuncha foiz yaqinlashtirishi kerak
    home_mode_min_gain: float = 0.25

    # --- Joylashuv ----------------------------------------------------------
    require_live_location: bool = True
    static_location_ttl_min: float = 10.0
    live_location_idle_ttl_min: float = 30.0
    bad_accuracy_m: float = 150.0

    # --- Safar --------------------------------------------------------------
    finish_confirm_timeout_min: float = 10.0  # 0 = faqat yo'lovchi tasdig'i
    no_show_wait_min: float = 5.0
    near_notify_radius_m: float = 400.0  # "Haydovchi yaqinlashmoqda" xabari
    auto_arrive_radius_m: float = 70.0  # GPS bo'yicha avtomatik "Yetib keldim" (0 = o'chirilgan)
    rating_prior: float = 4.7  # yangi haydovchi reytingi (ustuvorlik chegarasidan biroz past)
    rating_prior_weight: int = 5

    # --- Aloqa (kompaniya raqami orqali) -----------------------------------
    call_provider: Literal["none", "operator", "zadarma", "webhook"] = "operator"
    call_cooldown_sec: int = 30
    calls_per_order: int = 8
    zadarma_key: str | None = None
    zadarma_secret: SecretStr | None = None
    zadarma_sip: str | None = None
    call_webhook_url: str | None = None
    call_webhook_secret: SecretStr | None = None

    # --- To'lov (balans to'ldirish) ----------------------------------------
    payment_provider_token: SecretStr | None = None  # Click / Payme provider token
    topup_amounts: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [20000, 50000, 100000]
    )
    payment_instructions: str = (
        "Balansni to'ldirish uchun operatorga murojaat qiling va ID raqamingizni yuboring."
    )

    # --- Interfeys ----------------------------------------------------------
    rich_messages: bool = True  # Bot API 10.x Rich Messages (xarita bloki bilan)
    message_effects: bool = True
    # Tugmalarda custom emoji (bot egasida Telegram Premium bo'lishi kerak). Masalan: {"taxi": "5368..."}
    button_emoji_ids: dict[str, str] = Field(default_factory=dict)

    # --- Telegram Mini App (yo'lovchi va haydovchi ilovasi) ----------------
    webapp_enabled: bool = True
    webapp_port: int = 8081
    webapp_host: str = "127.0.0.1"  # serverda reverse-proxy ortida: 0.0.0.0
    # Doimiy HTTPS manzil (domen bo'lsa). Bo'sh bo'lsa va cloudflared o'rnatilgan bo'lsa — tunnel o'zi ochiladi
    webapp_url: str | None = None
    webapp_tunnel: Literal["auto", "none"] = "auto"
    webapp_auth_max_age_h: int = 48
    tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    tile_attribution: str = "© OpenStreetMap"
    geocoder_url: str | None = "https://nominatim.openstreetmap.org"
    geocoder_country: str = "uz"

    # --- Admin web-panel (brauzerda: http://localhost:8080) -----------------
    admin_panel_enabled: bool = True
    admin_panel_host: str = "127.0.0.1"  # faqat shu kompyuterdan; tarmoqqa ochish: 0.0.0.0
    admin_panel_port: int = 8080
    admin_panel_password: SecretStr | None = None  # bo'sh bo'lsa data/admin_panel_password.txt da yaratiladi

    log_level: str = "INFO"

    @field_validator("admin_ids", "wave_radii_km", "topup_amounts", mode="before")
    @classmethod
    def _csv(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("route_urls", mode="before")
    @classmethod
    def _route_urls(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in ("none", "off", "0", "false"):
            return []
        return _split_csv(value)

    @field_validator("wave_radii_km")
    @classmethod
    def _sorted_radii(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("wave_radii_km bo'sh bo'lmasligi kerak")
        return sorted(value)

    @property
    def single_bot(self) -> bool:
        if self.driver_bot_token is None:
            return True
        token = self.driver_bot_token.get_secret_value().strip()
        return not token or token == self.passenger_bot_token.get_secret_value().strip()

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
