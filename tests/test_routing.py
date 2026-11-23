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


async def fake_osrm(hits: list[str], fail: bool = False) -> TestServer:
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
        return web.Response(status=500)

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


async def test_fallback_and_dispatch_never_hit_public_servers():
    hits: list[str] = []
    server = await fake_osrm(hits, fail=True)
    routing = RoutingService(None, public_urls=[str(server.make_url(""))])
    try:
        est, coords = await routing.route_geometry(A, B)
        assert not est.precise and coords == [[A.lat, A.lon], [B.lat, B.lon]]
        hits.clear()
        many = await routing.many_to_one([A, B], B)  # haydovchilarni saralash — ommaviy serverga yuborilmaydi
        assert len(many) == 2 and not hits
    finally:
        await routing.close()
        await server.close()


async def test_route_url_setting_can_be_disabled():
    from .conftest import make_settings

    assert make_settings(route_urls="none").route_urls == []
    assert make_settings(route_urls="https://a.example/x, https://b.example").route_urls == [
        "https://a.example/x", "https://b.example"
    ]
