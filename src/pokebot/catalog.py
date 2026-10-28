import sqlite3
import time
from collections.abc import Iterator

import httpx

from pokebot.db import now

class CatalogError(Exception):
    """O pokemontcg.io não respondeu direito mesmo depois de novas tentativas."""


RETRIES = 3
_sleep = time.sleep
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


def _get_page(client: httpx.Client, query: str, page: int, headers: dict) -> dict:
    """O pokemontcg.io responde 5xx/timeout com frequência: tenta algumas vezes antes de desistir."""
    last = ""
    for attempt in range(RETRIES):
        if attempt:
            _sleep(2 ** attempt)
        try:
            resp = client.get(API_URL, params={"q": query, "page": page, "pageSize": PAGE_SIZE}, headers=headers)
        except httpx.TransportError as e:
            last = f"falha de rede ({e.__class__.__name__})"
            continue
        if resp.status_code >= 500:
            last = f"HTTP {resp.status_code}"
            continue
        if resp.status_code >= 400:
            raise CatalogError(
                f"pokemontcg.io recusou a busca {query!r} (HTTP {resp.status_code}). "
                "Confira a sintaxe: ex. name:rayquaza* ou number:194 set.printedTotal:203."
            )
        return resp.json()
    raise CatalogError(
        f"pokemontcg.io indisponível para a busca {query!r} ({last}) depois de {RETRIES} tentativas. "
        "Se a busca tem espaços, use curinga (name:rayquaza*) ou tente de novo mais tarde."
    )


def fetch_cards(client: httpx.Client, query: str, api_key: str | None = None) -> Iterator[dict]:
    headers = {"X-Api-Key": api_key} if api_key else {}
    page = 1
    while True:
        body = _get_page(client, query, page, headers)
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
