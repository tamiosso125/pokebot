import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pokebot.sources.base import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    number TEXT,
    set_id TEXT,
    set_name TEXT,
    set_printed_total INTEGER,
    rarity TEXT,
    image_url TEXT,
    price_usd_market REAL,
    price_updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_name ON cards (name);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    price REAL,
    currency TEXT,
    url TEXT NOT NULL,
    seller TEXT,
    condition_text TEXT,
    card_id TEXT REFERENCES cards (id),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS liga_prices (
    card_id TEXT PRIMARY KEY REFERENCES cards (id),
    price_brl REAL NOT NULL,
    url TEXT,
    collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listing_analysis (
    listing_id INTEGER PRIMARY KEY REFERENCES listings (id) ON DELETE CASCADE,
    card_name TEXT,
    card_number TEXT,
    set_name TEXT,
    card_confidence REAL,
    condition TEXT NOT NULL,
    condition_confidence REAL,
    in_protective_case INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    model TEXT NOT NULL,
    analyzed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listing_images (
    listing_id INTEGER NOT NULL REFERENCES listings (id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    PRIMARY KEY (listing_id, url)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    return conn


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Bancos criados na etapa 1 não têm estas colunas."""
    for table, column, ddl in (
        ("cards", "set_printed_total", "INTEGER"),
        ("listings", "card_id", "TEXT REFERENCES cards (id)"),
    ):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    conn.commit()


def upsert_listing(conn: sqlite3.Connection, listing: Listing) -> tuple[int, bool]:
    """Grava o anúncio e devolve (id, é_novo). Anúncios repetidos só atualizam preço e última vez visto."""
    ts = now()
    row = conn.execute(
        "SELECT id FROM listings WHERE source = ? AND external_id = ?",
        (listing.source, listing.external_id),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE listings SET title = ?, price = ?, currency = ?, url = ?, last_seen_at = ? WHERE id = ?",
            (listing.title, listing.price, listing.currency, listing.url, ts, row["id"]),
        )
        listing_id, is_new = row["id"], False
    else:
        cur = conn.execute(
            "INSERT INTO listings (source, external_id, title, price, currency, url, seller,"
            " condition_text, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                listing.source, listing.external_id, listing.title, listing.price,
                listing.currency, listing.url, listing.seller, listing.condition_text, ts, ts,
            ),
        )
        listing_id, is_new = cur.lastrowid, True
    conn.executemany(
        "INSERT OR IGNORE INTO listing_images (listing_id, url) VALUES (?, ?)",
        [(listing_id, u) for u in listing.image_urls],
    )
    conn.commit()
    return listing_id, is_new
