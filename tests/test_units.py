from taxi_bot.services.geo import bearing_deg, bounding_box, compass, format_distance, haversine_m
from taxi_bot.services.matching import Candidate, bayesian_rating, select_wave
from taxi_bot.services.pricing import Tariff, money
from taxi_bot.services.telephony import TelephonyService, normalize_phone
from taxi_bot.ui.kit import nav_url

from .conftest import make_settings


def test_haversine_known_distance():
    # Toshkent -> Samarqand ~ 266 km (to'g'ri chiziq)
    d = haversine_m(41.2995, 69.2401, 39.6542, 66.9597)
    assert 260_000 < d < 275_000
    assert haversine_m(40.0, 71.0, 40.0, 71.0) == 0


def test_bounding_box_contains_radius():
    lat, lon = 40.9983, 71.6726
    min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, 1000)
    assert abs(haversine_m(lat, lon, max_lat, lon) - 1000) < 1
    assert abs(haversine_m(lat, lon, lat, max_lon) - 1000) < 1
    assert min_lat < lat < max_lat and min_lon < lon < max_lon


def test_bearing_and_compass():
    assert round(bearing_deg(40, 71, 41, 71)) == 0
    assert "sharq" in compass(bearing_deg(40, 71, 40, 72))
    assert compass(225).endswith("janubi-g'arbda")


def test_format_distance():
    assert format_distance(853) == "850 m"
    assert format_distance(4200) == "4.2 km"
    assert format_distance(3000) == "3 km"


def test_tariff():
    t = Tariff.from_settings(make_settings())
    assert t.ride_price(0) == 7000  # minimal narx
    assert t.ride_price(5000) == 7000 + 3 * 2000
    assert t.ride_price(5100) == 13500  # 500 ga yaxlitlanadi (yuqoriga)
    assert t.wait_charge(2 * 60) == 0  # 3 daqiqa bepul
    assert t.wait_charge(5 * 60 + 10) == 2 * 500  # to'liq daqiqalar hisoblanadi
    assert t.wait_charge(6 * 60) == 3 * 500
    assert t.commission(13000) == 1300  # 10%
    assert money(13000) == "13 000 so'm"


def test_select_wave_priority_and_bands():
    def c(i, rating, dist, eta):
        return Candidate(i, i, rating, dist, dist * 1.3, eta, precise=False)

    cands = [
        c(1, 4.5, 300, 60),
        c(2, 4.95, 900, 200),
        c(3, 4.85, 500, 100),
        c(4, 5.0, 1500, 300),  # 1 km dan tashqarida
    ]
    priority, rest = select_wave(cands, 1000, 4.8)
    assert [x.driver_id for x in priority] == [2, 3]  # avval reyting
    assert [x.driver_id for x in rest] == [1]
    priority, rest = select_wave(cands, 2000, 4.8)
    assert [x.driver_id for x in priority] == [4, 2, 3]


def test_precise_road_distance_is_used_for_bands():
    # To'g'ri chiziqda yaqin, lekin yo'l bo'yicha uzoq (masalan, daryo ortida)
    across_river = Candidate(1, 1, 5.0, 400, 3200, 600, precise=True)
    priority, rest = select_wave([across_river], 1000, 4.8)
    assert not priority and not rest


def test_bayesian_rating():
    assert bayesian_rating(0, 0, 4.7, 5) == 4.7
    assert bayesian_rating(25, 5, 4.7, 5) == 4.85
    assert bayesian_rating(5, 5, 4.7, 5) < 3.5


def test_phone_normalize():
    assert normalize_phone("998901234567") == "+998901234567"
    assert normalize_phone("+998 (90) 123-45-67") == "+998901234567"
    assert normalize_phone("901234567") == "+998901234567"
    assert normalize_phone("123") is None


def test_zadarma_signature_is_deterministic():
    sig = TelephonyService.zadarma_signature(
        "/v1/request/callback/", {"to": "998901112233", "from": "998907778899"}, "KEY", "SECRET"
    )
    key, b64 = sig.split(":")
    assert key == "KEY" and len(b64) == 56  # base64(sha1 hex)


def test_nav_urls_open_route_immediately():
    assert "dir_action=navigate" in nav_url("google", 41.0, 71.6)
    assert "rtext=~41.000000%2C71.600000" in nav_url("yandex", 41.0, 71.6)
    assert "navigate=yes" in nav_url("waze", 41.0, 71.6)


def test_settings_csv_lists():
    s = make_settings(admin_ids="1,2", wave_radii_km="3,1,2")
    assert s.admin_ids == [1, 2]
    assert s.wave_radii_km == [1.0, 2.0, 3.0]
    assert not s.single_bot
    assert make_settings(driver_bot_token="").single_bot
