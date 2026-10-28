import textwrap

import pytest

from pokebot import db, matching, valuation
from pokebot.sources.manual import manual_listing


def add_card(conn, id_, name, number, total, usd=None):
    conn.execute(
        "INSERT INTO cards (id, name, number, set_id, set_name, set_printed_total, price_usd_market)"
        " VALUES (?, ?, ?, 's', 'Set', ?, ?)",
        (id_, name, number, total, usd),
    )
    conn.commit()


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    add_card(c, "swsh7-194", "Rayquaza V", "194", 203, usd=100.0)
    add_card(c, "swsh7-111", "Rayquaza V", "111", 203, usd=2.0)
    add_card(c, "other-5", "Pikachu", "5", 100)
    add_card(c, "other2-5", "Charmander", "5", 100)
    return c


@pytest.mark.parametrize("title,expected", [
    ("Rayquaza V 194/203 Alt Art Evolving Skies", "swsh7-194"),
    ("Carta Rayquaza-V (194 / 203)", "swsh7-194"),
    ("Rayquaza V 111/203", "swsh7-111"),
    ("Pikachu 005/100 holo", "other-5"),   # zeros à esquerda
    ("Carta 5/100 rara", None),            # mesmo número em duas cartas, sem nome no título
    ("Carta pokemon rara", None),          # sem número
    ("Rayquaza V 999/203", None),          # número inexistente
])
def test_match_card(conn, title, expected):
    assert matching.match_card(conn, title) == expected


def test_link_listings_and_reference_prefers_liga(conn, tmp_path):
    db.upsert_listing(conn, manual_listing("olx", "https://olx/1", "Rayquaza V 194/203", 300))
    assert matching.link_listings(conn) == 1
    assert matching.link_listings(conn) == 0

    ref = valuation.reference_price(conn, "swsh7-194", usd_brl=5.0)
    assert (ref.source, ref.price_brl) == ("tcgplayer", 500.0)

    csv_file = tmp_path / "liga.csv"
    csv_file.write_text(textwrap.dedent("""\
        nome,numero,preco_brl,url
        Rayquaza V,194/203,"450,90",https://liga/x
        Carta Inexistente,1/1,10,
    """))
    n, unmatched = valuation.import_liga_prices(conn, str(csv_file))
    assert n == 1 and unmatched == ["Carta Inexistente 1/1"]
    ref = valuation.reference_price(conn, "swsh7-194", usd_brl=5.0)
    assert (ref.source, ref.price_brl) == ("ligapokemon", 450.9)
    assert valuation.reference_price(conn, "other-5", 5.0) is None


def test_old_database_gets_new_columns(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.executescript("CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT NOT NULL, number TEXT, set_id TEXT,"
                      " set_name TEXT, rarity TEXT, image_url TEXT, price_usd_market REAL, price_updated_at TEXT);"
                      "CREATE TABLE listings (id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,"
                      " price REAL, currency TEXT, url TEXT, seller TEXT, condition_text TEXT,"
                      " first_seen_at TEXT, last_seen_at TEXT);")
    old.close()
    conn = db.connect(path)
    assert "set_printed_total" in {r["name"] for r in conn.execute("PRAGMA table_info(cards)")}
    assert "card_id" in {r["name"] for r in conn.execute("PRAGMA table_info(listings)")}
