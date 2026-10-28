from types import SimpleNamespace

from pokebot import db, vision
from pokebot.sources.base import Listing


class FakeClient:
    def __init__(self, payload=None, fail=False):
        self.calls = []
        self.payload = payload
        self.fail = fail
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("api fora do ar")
        blocks = [SimpleNamespace(type="text", text="ok")]
        if self.payload is not None:
            blocks.append(SimpleNamespace(type="tool_use", input=self.payload))
        return SimpleNamespace(content=blocks)


PAYLOAD = {
    "card_name": "Rayquaza V", "card_number": "194/203", "set_name": "Evolving Skies", "card_confidence": 0.9,
    "condition": "LP", "condition_confidence": 0.4, "in_protective_case": True, "notes": "reflexo na pasta",
}


def setup(title="Carta rara"):
    conn = db.connect(":memory:")
    conn.execute("INSERT INTO cards (id, name, number, set_printed_total) VALUES ('swsh7-194', 'Rayquaza V', '194', 203)")
    db.upsert_listing(conn, Listing("olx", "1", title, "https://olx/1", 100, "BRL",
                                    image_urls=["http://i/1", "http://i/2", "http://i/3", "http://i/4"]))
    return conn


def test_analyze_images_sends_forced_tool_and_at_most_three_images():
    client = FakeClient(PAYLOAD)
    res = vision.analyze_images(client, "m", "t", ["a", "b", "c", "d"])
    call = client.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "report_card"}
    assert [b["type"] for b in call["messages"][0]["content"]] == ["image", "image", "image", "text"]
    assert (res.condition, res.in_protective_case, res.condition_confidence) == ("LP", True, 0.4)


def test_invalid_condition_becomes_unknown():
    res = vision.analyze_images(FakeClient({**PAYLOAD, "condition": "mint!"}), "m", "t", ["a"])
    assert res.condition == "unknown"


def test_analyze_pending_stores_result_and_links_card_from_photo_number():
    conn = setup()  # título sem número: a carta só aparece pela foto
    assert vision.analyze_pending(conn, FakeClient(PAYLOAD), "m", limit=5) == (1, 0)
    row = conn.execute("SELECT condition, in_protective_case FROM listing_analysis").fetchone()
    assert (row["condition"], row["in_protective_case"]) == ("LP", 1)
    assert conn.execute("SELECT card_id FROM listings").fetchone()[0] == "swsh7-194"
    client = FakeClient(PAYLOAD)
    assert vision.analyze_pending(conn, client, "m", limit=5) == (0, 0)  # não reanalisa
    assert client.calls == []


def test_analyze_pending_counts_failures_and_retries_later():
    conn = setup()
    assert vision.analyze_pending(conn, FakeClient(fail=True), "m", limit=5) == (0, 1)
    assert vision.analyze_pending(conn, FakeClient(PAYLOAD), "m", limit=5) == (1, 0)


def test_listing_without_images_is_skipped():
    conn = db.connect(":memory:")
    db.upsert_listing(conn, Listing("olx", "1", "x", "https://olx/1"))
    assert vision.analyze_pending(conn, FakeClient(PAYLOAD), "m", limit=5) == (0, 0)
