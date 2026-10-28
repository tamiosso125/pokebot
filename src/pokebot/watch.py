import sqlite3
import time

import httpx

from pokebot import alerts, db, matching, vision
from pokebot.config import Settings
from pokebot.sources.base import SourceAccessError
from pokebot.sources.mercadolivre import MercadoLivreSource


def run_cycle(conn: sqlite3.Connection, settings: Settings, http: httpx.Client, vision_client=None) -> dict:
    """Uma rodada: busca, associa à carta, analisa fotos (se houver chave) e avisa os anúncios bons."""
    stats = {"new": 0, "errors": [], "analyzed": 0, "alerts": 0}
    source = MercadoLivreSource(http, settings.meli_access_token)
    for query in settings.queries:
        try:
            listings = source.search(query)
        except (SourceAccessError, httpx.HTTPError) as e:
            stats["errors"].append(f"{query!r}: {e}")
            continue
        stats["new"] += sum(db.upsert_listing(conn, item)[1] for item in listings)
    matching.link_listings(conn)
    if vision_client is not None:
        stats["analyzed"], _ = vision.analyze_pending(conn, vision_client, settings.vision_model, limit=10)
        matching.link_listings(conn)
    if settings.telegram_bot_token and settings.telegram_chat_id:
        stats["alerts"] = alerts.notify_new(
            conn, http, settings.telegram_bot_token, settings.telegram_chat_id,
            settings.usd_brl, settings.min_discount_pct,
        )
    return stats


def watch_forever(conn: sqlite3.Connection, settings: Settings, interval_min: float, vision_client=None) -> None:
    with httpx.Client(timeout=30) as http:
        while True:
            stats = run_cycle(conn, settings, http, vision_client)
            print(f"{time.strftime('%H:%M:%S')} novos={stats['new']} analisados={stats['analyzed']} "
                  f"alertas={stats['alerts']} erros={len(stats['errors'])}", flush=True)
            for err in stats["errors"]:
                print(f"  erro: {err}", flush=True)
            time.sleep(interval_min * 60)
