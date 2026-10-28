import httpx
import pytest

from pokebot import db
from pokebot.sources.base import SourceAccessError
from pokebot.sources.manual import manual_listing
from pokebot.sources.mercadolivre import MercadoLivreSource

ITEM = {
    "id": "MLB1", "title": "Carta Charizard Base Set", "price": 250.0, "currency_id": "BRL",
    "permalink": "https://produto.mercadolivre.com.br/MLB-1", "thumbnail": "http://img/1.jpg",
    "condition": "used", "seller": {"nickname": "loja"},
}


def client_for(status, body=None):
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body or {})))


def test_ml_parses_results():
    results = MercadoLivreSource(client_for(200, {"results": [ITEM]})).search("charizard")
    assert results[0].external_id == "MLB1" and results[0].price == 250.0
    assert results[0].image_urls == ["http://img/1.jpg"]


@pytest.mark.parametrize("status", [401, 403, 429])
def test_ml_access_denied_raises_clear_error(status):
    with pytest.raises(SourceAccessError):
        MercadoLivreSource(client_for(status)).search("charizard")


def test_ml_sends_token():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"results": []})

    MercadoLivreSource(httpx.Client(transport=httpx.MockTransport(handler)), "tok").search("x")
    assert seen["auth"] == "Bearer tok"


def test_upsert_marks_new_then_existing_and_updates_price():
    conn = db.connect(":memory:")
    item = MercadoLivreSource(client_for(200, {"results": [ITEM]})).search("x")[0]
    id1, new1 = db.upsert_listing(conn, item)
    item.price = 200.0
    id2, new2 = db.upsert_listing(conn, item)
    assert (new1, new2, id1 == id2) == (True, False, True)
    assert conn.execute("SELECT price FROM listings").fetchone()[0] == 200.0
    assert conn.execute("SELECT COUNT(*) FROM listing_images").fetchone()[0] == 1


def test_manual_listing_is_deduplicated_by_url():
    conn = db.connect(":memory:")
    a = manual_listing("olx", "https://olx.com.br/x", "Pikachu", 30, ["http://i/1"])
    b = manual_listing("olx", "https://olx.com.br/x", "Pikachu", 25)
    assert db.upsert_listing(conn, a)[1] is True
    assert db.upsert_listing(conn, b)[1] is False
