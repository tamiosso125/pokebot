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


def test_ml_fetches_app_token_with_client_credentials_and_reuses_it():
    seen = {"token_calls": 0, "auth": []}

    def handler(request):
        if request.url.path == "/oauth/token":
            seen["token_calls"] += 1
            assert b"grant_type=client_credentials" in request.content
            return httpx.Response(200, json={"access_token": "abc", "expires_in": 21600})
        seen["auth"].append(request.headers.get("authorization"))
        return httpx.Response(200, json={"results": []})

    src = MercadoLivreSource(httpx.Client(transport=httpx.MockTransport(handler)), client_id="id", client_secret="sec")
    src.search("a")
    src.search("b")
    assert seen == {"token_calls": 1, "auth": ["Bearer abc", "Bearer abc"]}


def test_ml_refreshes_token_once_on_401():
    state = {"tokens": 0}

    def handler(request):
        if request.url.path == "/oauth/token":
            state["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"t{state['tokens']}", "expires_in": 21600})
        ok = request.headers["authorization"] == "Bearer t2"
        return httpx.Response(200 if ok else 401, json={"results": []})

    src = MercadoLivreSource(httpx.Client(transport=httpx.MockTransport(handler)), client_id="id", client_secret="sec")
    assert src.search("a") == []
    assert state["tokens"] == 2


def test_ml_bad_client_credentials_raise_clear_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={})))
    with pytest.raises(SourceAccessError, match="MELI_CLIENT_ID"):
        MercadoLivreSource(client, client_id="id", client_secret="bad").search("a")


def test_ml_403_message_says_whether_token_was_used_and_shows_body():
    def forbidden(request):
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "abc", "expires_in": 21600})
        return httpx.Response(403, json={"message": "blocked by policy"})

    with_token = MercadoLivreSource(httpx.Client(transport=httpx.MockTransport(forbidden)), client_id="i", client_secret="s")
    with pytest.raises(SourceAccessError, match="com token do app.*blocked by policy"):
        with_token.search("a")
    without = MercadoLivreSource(httpx.Client(transport=httpx.MockTransport(forbidden)))
    with pytest.raises(SourceAccessError, match="sem token"):
        without.search("a")
