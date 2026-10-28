import sqlite3

import httpx

from pokebot.board import listing_rows
from pokebot.db import now


def pending_alerts(conn: sqlite3.Connection, usd_brl: float, min_discount_pct: float) -> list[dict]:
    """Anúncios ainda não avisados, com carta identificada e desconto acima do mínimo."""
    return [
        r for r in listing_rows(conn, usd_brl, limit=1000)
        if r["notified_at"] is None and r["discount_pct"] is not None and r["discount_pct"] >= min_discount_pct
    ]


def format_message(r: dict) -> str:
    lines = [
        f"{r['card_name']} — R$ {r['price']:.2f}",
        f"{r['discount_pct']:.0f}% abaixo da referência (R$ {r['reference_brl']:.2f}, {r['reference_source']})",
    ]
    if r["condition"]:
        case = ", em proteção" if r["in_protective_case"] else ""
        lines.append(f"Condição {r['condition']} (confiança {r['condition_confidence']:.0%}{case})")
    lines += [f"[{r['source']}] {r['title']}", r["url"]]
    return "\n".join(lines)


def send_telegram(client: httpx.Client, token: str, chat_id: str, text: str) -> None:
    resp = client.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
    )
    resp.raise_for_status()


def notify_new(
    conn: sqlite3.Connection, client: httpx.Client, token: str, chat_id: str, usd_brl: float, min_discount_pct: float
) -> int:
    """Envia um aviso por anúncio novo e marca como avisado só depois que o envio deu certo."""
    sent = 0
    for r in pending_alerts(conn, usd_brl, min_discount_pct):
        try:
            send_telegram(client, token, chat_id, format_message(r))
        except httpx.HTTPError:
            continue  # tenta de novo no próximo ciclo
        conn.execute("UPDATE listings SET notified_at = ? WHERE id = ?", (now(), r["id"]))
        conn.commit()
        sent += 1
    return sent
