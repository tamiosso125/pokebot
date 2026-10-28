import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import httpx

from pokebot import alerts, dashboard, db, watch
from pokebot.config import Settings
from pokebot.sources.base import Listing


def settings(tmp_path, **kw):
    base = dict(db_path=str(tmp_path / "t.db"), pokemontcg_api_key=None, meli_access_token=None, usd_brl=5.0,
                vision_model="m", telegram_bot_token="tok", telegram_chat_id="42", min_discount_pct=30,
                queries=["carta pokemon"])
    return Settings(**{**base, **kw})


def seed(conn, price=300.0):
    conn.execute("INSERT INTO cards (id, name, number, set_name, set_printed_total, price_usd_market)"
                 " VALUES ('swsh7-194', 'Rayquaza V', '194', 'Evolving Skies', 203, 200.0)")  # ref = R$ 1000
    conn.commit()
    return db.upsert_listing(conn, Listing("olx", "1", "Rayquaza V 194/203", "https://olx/1", price, "BRL",
                                           image_urls=["http://i/1"]))[0]


def link(conn):
    conn.execute("UPDATE listings SET card_id = 'swsh7-194'")
    conn.commit()


def telegram_client(status=200, sent=None):
    def handler(request):
        if sent is not None:
            sent.append(json.loads(request.content))
        return httpx.Response(status, json={"ok": status == 200})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_pending_alerts_filters_by_discount_and_notified():
    conn = db.connect(":memory:")
    seed(conn, price=300)  # 70% abaixo
    link(conn)
    assert len(alerts.pending_alerts(conn, 5.0, 30)) == 1
    assert alerts.pending_alerts(conn, 5.0, 80) == []


def test_notify_marks_sent_once_and_retries_after_failure():
    conn = db.connect(":memory:")
    seed(conn)
    link(conn)
    assert alerts.notify_new(conn, telegram_client(500), "tok", "42", 5.0, 30) == 0
    sent = []
    assert alerts.notify_new(conn, telegram_client(200, sent), "tok", "42", 5.0, 30) == 1
    assert "70% abaixo" in sent[0]["text"] and "https://olx/1" in sent[0]["text"]
    assert alerts.notify_new(conn, telegram_client(200, sent), "tok", "42", 5.0, 30) == 0


def test_run_cycle_searches_matches_and_alerts(tmp_path):
    conn = db.connect(":memory:")
    conn.execute("INSERT INTO cards (id, name, number, set_name, set_printed_total, price_usd_market)"
                 " VALUES ('swsh7-194', 'Rayquaza V', '194', 'Evolving Skies', 203, 200.0)")
    conn.commit()
    sent = []

    def handler(request):
        if "mercadolibre" in request.url.host:
            return httpx.Response(200, json={"results": [{
                "id": "MLB1", "title": "Rayquaza V 194/203", "price": 300.0, "currency_id": "BRL",
                "permalink": "https://ml/1", "thumbnail": "http://i/1"}]})
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    stats = watch.run_cycle(conn, settings(tmp_path), http)
    assert (stats["new"], stats["alerts"], stats["errors"]) == (1, 1, [])
    assert watch.run_cycle(conn, settings(tmp_path), http)["alerts"] == 0  # não repete


def test_run_cycle_reports_access_error_without_crashing(tmp_path):
    conn = db.connect(":memory:")
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    stats = watch.run_cycle(conn, settings(tmp_path), http)
    assert stats["new"] == 0 and len(stats["errors"]) == 1


def test_dashboard_serves_page_and_json(tmp_path):
    s = settings(tmp_path)
    conn = db.connect(s.db_path)
    seed(conn)
    link(conn)
    conn.close()
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.make_handler(s))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        assert b"PokeBot" in urllib.request.urlopen(base + "/").read()
        rows = json.loads(urllib.request.urlopen(base + "/api/listings").read())
        assert rows[0]["card_name"] == "Rayquaza V" and rows[0]["discount_pct"] == 70.0
    finally:
        server.shutdown()
