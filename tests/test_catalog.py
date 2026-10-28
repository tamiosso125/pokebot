import httpx

from pokebot import catalog, db


def card(id_, prices):
    return {
        "id": id_, "name": "Charizard", "number": "4", "rarity": "Rare Holo",
        "set": {"id": "base1", "name": "Base"}, "images": {"small": "http://img/" + id_},
        "tcgplayer": {"prices": prices},
    }


def test_market_price_prefers_normal_then_any_variant():
    assert catalog.market_price_usd(card("a", {"holofoil": {"market": 9.0}, "normal": {"market": 1.5}})) == 1.5
    assert catalog.market_price_usd(card("a", {"foo": {"market": 3.0}})) == 3.0
    assert catalog.market_price_usd({"id": "x"}) is None


def test_sync_paginates_and_upserts():
    pages = {1: [card("a", {"normal": {"market": 1.0}})], 2: [card("b", {})]}
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        seen.append(request.headers.get("x-api-key"))
        return httpx.Response(200, json={"data": pages[page], "totalCount": 251 if page == 1 else 251})

    conn = db.connect(":memory:")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert catalog.sync_cards(conn, client, "name:charizard", api_key="k") == 2
    assert seen == ["k", "k"]
    rows = {r["id"]: r["price_usd_market"] for r in conn.execute("SELECT id, price_usd_market FROM cards")}
    assert rows == {"a": 1.0, "b": None}
    catalog.sync_cards(conn, client, "name:charizard")
    assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 2
