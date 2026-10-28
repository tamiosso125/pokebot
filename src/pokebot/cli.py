import argparse

import httpx

from pokebot import catalog, db
from pokebot.config import Settings
from pokebot.sources.base import SourceAccessError
from pokebot.sources.manual import manual_listing
from pokebot.sources.mercadolivre import MercadoLivreSource


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pokebot")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sync-catalog", help="baixa cartas do pokemontcg.io (ex.: --query 'name:charizard')")
    s.add_argument("--query", required=True)

    s = sub.add_parser("search-ml", help="busca anúncios no Mercado Livre e grava no banco")
    s.add_argument("--query", required=True)
    s.add_argument("--limit", type=int, default=50)

    s = sub.add_parser("add-manual", help="registra um anúncio da OLX/Shopee/etc. à mão")
    s.add_argument("--source", required=True, help="olx, shopee…")
    s.add_argument("--url", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--price", type=float)
    s.add_argument("--image", action="append", default=[], help="URL de foto (repetível)")

    s = sub.add_parser("list", help="mostra os anúncios gravados, mais novos primeiro")
    s.add_argument("--limit", type=int, default=20)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    conn = db.connect(settings.db_path)

    if args.cmd == "sync-catalog":
        with httpx.Client(timeout=30) as client:
            n = catalog.sync_cards(conn, client, args.query, settings.pokemontcg_api_key)
        print(f"{n} cartas sincronizadas")
    elif args.cmd == "search-ml":
        with httpx.Client(timeout=30) as client:
            try:
                listings = MercadoLivreSource(client, settings.meli_access_token).search(args.query, args.limit)
            except SourceAccessError as e:
                print(e)
                return 1
        new = sum(db.upsert_listing(conn, item)[1] for item in listings)
        print(f"{len(listings)} anúncios lidos, {new} novos")
    elif args.cmd == "add-manual":
        _, is_new = db.upsert_listing(
            conn, manual_listing(args.source, args.url, args.title, args.price, args.image)
        )
        print("anúncio adicionado" if is_new else "anúncio já existia (atualizado)")
    elif args.cmd == "list":
        rows = conn.execute(
            "SELECT source, title, price, currency, url FROM listings ORDER BY first_seen_at DESC, id DESC LIMIT ?",
            (args.limit,),
        )
        for r in rows:
            price = f"{r['currency'] or ''} {r['price']:.2f}" if r["price"] is not None else "sem preço"
            print(f"[{r['source']}] {r['title']} — {price}\n    {r['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
