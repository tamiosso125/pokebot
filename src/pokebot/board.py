import sqlite3

from pokebot.valuation import reference_price


def listing_rows(conn: sqlite3.Connection, usd_brl: float, limit: int = 200) -> list[dict]:
    """Anúncios mais novos primeiro, já com carta, condição, referência e desconto (% abaixo da referência)."""
    rows = conn.execute(
        "SELECT l.id, l.source, l.title, l.price, l.currency, l.url, l.card_id, l.notified_at, l.first_seen_at,"
        " c.name AS card_name, c.set_name, a.condition, a.condition_confidence, a.in_protective_case, a.notes,"
        " (SELECT url FROM listing_images i WHERE i.listing_id = l.id LIMIT 1) AS image_url"
        " FROM listings l LEFT JOIN cards c ON c.id = l.card_id"
        " LEFT JOIN listing_analysis a ON a.listing_id = l.id"
        " ORDER BY l.first_seen_at DESC, l.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["reference_brl"] = d["reference_source"] = d["discount_pct"] = None
        if r["card_id"]:
            ref = reference_price(conn, r["card_id"], usd_brl)
            if ref:
                d["reference_brl"], d["reference_source"] = ref.price_brl, ref.source
                if r["price"] is not None and r["currency"] == "BRL":
                    d["discount_pct"] = round((ref.price_brl - r["price"]) / ref.price_brl * 100, 1)
        out.append(d)
    return out
