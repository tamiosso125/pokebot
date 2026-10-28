import sqlite3
from collections.abc import Iterator

import httpx

from pokebot.db import now

API_URL = "https://api.pokemontcg.io/v2/cards"
PAGE_SIZE = 250
# Ordem de preferência quando a carta tem mais de uma variante de preço no TCGPlayer.
VARIANT_ORDER = (
    "normal", "holofoil", "reverseHolofoil", "1stEditionHolofoil", "1stEditionNormal", "unlimitedHolofoil",
)


def market_price_usd(card: dict) -> float | None:
    prices = (card.get("tcgplayer") or {}).get("prices") or {}
    for variant in (*VARIANT_ORDER, *prices):
        market = (prices.get(variant) or {}).get("market")
        if market is not None:
            return float(market)
    return None


def fetch_cards(client: httpx.Client, query: str, api_key: str | None = None) -> Iterator[dict]:
    headers = {"X-Api-Key": api_key} if api_key else {}
    page = 1
    while True:
        resp = client.get(
            API_URL,
            params={"q": query, "page": page, "pageSize": PAGE_SIZE},
            headers=headers,
        )
        resp.raise_for_status()
        body = resp.json()
        yield from body["data"]
        if page * PAGE_SIZE >= body.get("totalCount", 0) or not body["data"]:
            return
        page += 1


def sync_cards(conn: sqlite3.Connection, client: httpx.Client, query: str, api_key: str | None = None) -> int:
    count = 0
    for card in fetch_cards(client, query, api_key):
        conn.execute(
            "INSERT INTO cards (id, name, number, set_id, set_name, set_printed_total, rarity, image_url,"
            " price_usd_market, price_updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET name = excluded.name, rarity = excluded.rarity,"
            " set_printed_total = excluded.set_printed_total, image_url = excluded.image_url, price_usd_market = excluded.price_usd_market,"
            " price_updated_at = excluded.price_updated_at",
            (
                card["id"], card["name"], card.get("number"),
                (card.get("set") or {}).get("id"), (card.get("set") or {}).get("name"),
                (card.get("set") or {}).get("printedTotal"), card.get("rarity"), (card.get("images") or {}).get("small"),
                market_price_usd(card), now(),
            ),
        )
        count += 1
    conn.commit()
    return count
