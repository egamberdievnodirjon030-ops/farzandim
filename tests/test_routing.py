"""Marshrut: ko'chalar bo'yicha chiziq (OSRM), kesh, ommaviy serverlarga ehtiyotkor murojaat, zaxira."""

from __future__ import annotations

import time

from aiohttp import web
from aiohttp.test_utils import TestServer

from taxi_bot.services.geo import Point
from taxi_bot.services.routing import RoutingService

A, B = Point(40.9983, 71.6726), Point(41.0100, 71.6900)
# Burilishli yo'l: avval shimolga, keyin sharqqa, keyin yana shimolga
TURNS = [[71.6727, 40.9984], [71.6727, 41.0040], [71.6890, 41.0040], [71.6890, 41.0099]]


async def fake_osrm(hits: list[str], fail: bool = False, table_ok: bool = False) -> TestServer:
    async def route(request: web.Request) -> web.Response:
        hits.append(request.path)
        if fail:
            return web.Response(status=503)
        assert request.query["geometries"] == "geojson" and request.query["overview"] == "full"
        assert "ShaharTaksi" in request.headers["User-Agent"]
        return web.json_response({
            "code": "Ok",
            "routes": [{"distance": 3120.5, "duration": 410.2, "geometry": {"type": "LineString", "coordinates": TURNS}}],
            "waypoints": [{"location": TURNS[0]}, {"location": TURNS[-1]}],
        })

    async def table(request: web.Request) -> web.Response:
        hits.append(request.path)
        if not table_ok:
            return web.Response(status=500)
        n = len(request.query["sources"].split(";"))
        # Yo'lning narigi tomoni: to'g'ri chiziqda yaqin, lekin aylanib o'tish kerak
        return web.json_response({"code": "Ok", "distances": [[2100.0]] * n, "durations": [[330.0]] * n})

    app = web.Application()
    app.router.add_get("/route/v1/driving/{coords}", route)
    app.router.add_get("/table/v1/driving/{coords}", table)
    server = TestServer(app, host="127.0.0.1")
    await server.start_server()
    return server


async def test_route_follows_streets_and_is_cached():
    hits: list[str] = []
    server = await fake_osrm(hits)
    routing = RoutingService(None, public_urls=[str(server.make_url(""))])
    try:
        est, coords = await routing.route_geometry(A, B)
        assert est.precise and est.distance_m == 3120.5
        assert coords == [[lat, lon] for lon, lat in TURNS]  # burilishlar saqlanadi, to'g'ri chiziq emas
        assert len(coords) > 2
        assert (await routing.route(A, B)).distance_m == 3120.5  # narx ham shu yo'l bo'yicha
        assert len(hits) == 1  # takroriy so'rov keshdan
    finally:
        await routing.close()
        await server.close()


async def test_broken_server_is_skipped_and_next_used():
    bad_hits: list[str] = []
    good_hits: list[str] = []
    bad = await fake_osrm(bad_hits, fail=True)
    good = await fake_osrm(good_hits)
    routing = RoutingService(None, public_urls=[str(bad.make_url("")), str(good.make_url(""))])
    try:
        est, _ = await routing.route_geometry(A, B)
        assert est.precise and len(bad_hits) == 1 and len(good_hits) == 1
        await routing.route_geometry(B, A)
        assert len(bad_hits) == 1  # ishlamagan server bir daqiqa chetlab o'tiladi
        assert len(good_hits) == 2
    finally:
        await routing.close()
        await bad.close()
        await good.close()


async def test_public_servers_get_at_most_one_request_per_second():
    hits: list[str] = []
    server = await fake_osrm(hits)
    routing = RoutingService(None, public_urls=[str(server.make_url(""))])
    try:
        t0 = time.monotonic()
        await routing.route(A, B)
        await routing.route(B, A)
        assert time.monotonic() - t0 >= 1.0 and len(hits) == 2
    finally:
        await routing.close()
        await server.close()


async def test_driver_distance_is_by_road_not_straight_line():
    """Foydalanuvchi holati: yo'lovchi yo'lning narigi tomonida, 150 m — lekin mashinada aylanib 2.1 km."""
    from taxi_bot.services.geo import haversine_m

    hits: list[str] = []
    server = await fake_osrm(hits, table_ok=True)
    routing = RoutingService(None, public_urls=[str(server.make_url(""))])
    across = Point(A.lat + 0.00135, A.lon)  # ~150 m
    try:
        assert haversine_m(A.lat, A.lon, across.lat, across.lon) < 160
        many = await routing.many_to_one([A, B, A], across)
        assert len(hits) == 1 and hits[0].startswith("/table/")  # bitta to'lqin — bitta so'rov
        assert all(r.precise and r.distance_m == 2100.0 and r.duration_s == 330.0 for r in many)
    finally:
        await routing.close()
        await server.close()


async def test_fallback_when_router_is_down():
    hits: list[str] = []
    server = await fake_osrm(hits, fail=True)
    routing = RoutingService(None, public_urls=[str(server.make_url(""))])
    try:
        est, coords = await routing.route_geometry(A, B)
        assert not est.precise and coords == [[A.lat, A.lon], [B.lat, B.lon]]
        many = await routing.many_to_one([A, B], B)  # table ham ishlamasa — taxminiy hisob
        assert len(many) == 2 and not any(r.precise for r in many)
    finally:
        await routing.close()
        await server.close()


async def test_route_url_setting_can_be_disabled():
    from .conftest import make_settings

    assert make_settings(route_urls="none").route_urls == []
    assert make_settings(route_urls="https://a.example/x, https://b.example").route_urls == [
        "https://a.example/x", "https://b.example"
    ]
