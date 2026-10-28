import csv
import sqlite3
from dataclasses import dataclass

from pokebot.db import now
from pokebot.matching import match_card


@dataclass
class Reference:
    price_brl: float
    source: str  # "ligapokemon" (preço do Brasil) ou "tcgplayer" (dólar convertido, menos preciso)


def import_liga_prices(conn: sqlite3.Connection, csv_path: str) -> tuple[int, list[str]]:
    """Lê um CSV com colunas nome,numero,preco_brl,url. Devolve (importadas, linhas sem carta no catálogo)."""
    imported, unmatched = 0, []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            card_id = match_card(conn, f"{row['nome']} {row['numero']}")
            if not card_id:
                unmatched.append(f"{row['nome']} {row['numero']}")
                continue
            conn.execute(
                "INSERT INTO liga_prices (card_id, price_brl, url, collected_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (card_id) DO UPDATE SET price_brl = excluded.price_brl, url = excluded.url,"
                " collected_at = excluded.collected_at",
                (card_id, float(row["preco_brl"].replace(",", ".")), row.get("url") or None, now()),
            )
            imported += 1
    conn.commit()
    return imported, unmatched


def reference_price(conn: sqlite3.Connection, card_id: str, usd_brl: float) -> Reference | None:
    """Preço de revenda de referência: LigaPokemon se houver; senão o dólar do TCGPlayer convertido."""
    liga = conn.execute("SELECT price_brl FROM liga_prices WHERE card_id = ?", (card_id,)).fetchone()
    if liga:
        return Reference(liga["price_brl"], "ligapokemon")
    card = conn.execute("SELECT price_usd_market FROM cards WHERE id = ?", (card_id,)).fetchone()
    if card and card["price_usd_market"] is not None:
        return Reference(round(card["price_usd_market"] * usd_brl, 2), "tcgplayer")
    return None
