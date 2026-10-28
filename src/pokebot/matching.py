import re
import sqlite3
import unicodedata

# "194/203", "194 / 203", "SWSH7 194/203"
NUMBER_RE = re.compile(r"(?<!\d)(\d{1,3})\s*/\s*(\d{1,3})(?!\d)")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def match_card(conn: sqlite3.Connection, title: str) -> str | None:
    """Acha a carta do catálogo pelo número impresso (194/203) e, se preciso, pelo nome no título.

    Devolve o id da carta ou None quando não há número, não há candidato ou sobra ambiguidade.
    """
    m = NUMBER_RE.search(title)
    if not m:
        return None
    number, total = str(int(m.group(1))), int(m.group(2))
    rows = conn.execute(
        "SELECT id, name FROM cards WHERE CAST(number AS INTEGER) = ? AND set_printed_total = ?",
        (int(number), total),
    ).fetchall()
    if len(rows) > 1:
        words = f" {_norm(title)} "
        rows = [r for r in rows if f" {_norm(r['name'])} " in words]
    return rows[0]["id"] if len(rows) == 1 else None


def link_listings(conn: sqlite3.Connection) -> int:
    """Associa a cartas do catálogo os anúncios ainda sem carta. Devolve quantos foram associados."""
    linked = 0
    for row in conn.execute("SELECT id, title FROM listings WHERE card_id IS NULL").fetchall():
        card_id = match_card(conn, row["title"])
        if card_id:
            conn.execute("UPDATE listings SET card_id = ? WHERE id = ?", (card_id, row["id"]))
            linked += 1
    conn.commit()
    return linked
