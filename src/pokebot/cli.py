import argparse
import os

import httpx

from pokebot import catalog, dashboard, db, matching, valuation, vision, watch
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

    s = sub.add_parser("import-liga", help="importa preços da LigaPokemon de um CSV (nome,numero,preco_brl,url)")
    s.add_argument("csv")

    sub.add_parser("match", help="associa anúncios às cartas do catálogo pelo número impresso (ex.: 194/203)")

    s = sub.add_parser("analyze", help="analisa as fotos dos anúncios novos (carta e condição); cada anúncio custa uma chamada à API")
    s.add_argument("--limit", type=int, default=10, help="máximo de anúncios por execução (controla o custo)")

    s = sub.add_parser("watch", help="roda sem parar: busca, analisa e avisa no Telegram os anúncios bons")
    s.add_argument("--interval", type=float, default=15, help="minutos entre rodadas")
    s.add_argument("--once", action="store_true", help="faz só uma rodada e sai")

    s = sub.add_parser("dashboard", help="abre o painel local no navegador")
    s.add_argument("--port", type=int, default=8000)

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
    elif args.cmd == "import-liga":
        n, unmatched = valuation.import_liga_prices(conn, args.csv)
        print(f"{n} preços importados")
        for name in unmatched:
            print(f"  sem carta no catálogo (rode sync-catalog antes?): {name}")
    elif args.cmd == "match":
        print(f"{matching.link_listings(conn)} anúncios associados a cartas")
    elif args.cmd == "analyze":
        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Defina ANTHROPIC_API_KEY (console.anthropic.com) para analisar imagens.")
            return 1
        done, failed = vision.analyze_pending(conn, anthropic.Anthropic(), settings.vision_model, args.limit)
        matching.link_listings(conn)
        print(f"{done} anúncios analisados, {failed} falhas")
    elif args.cmd == "watch":
        vision_client = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic

            vision_client = anthropic.Anthropic()
        if not (settings.telegram_bot_token and settings.telegram_chat_id):
            print("Aviso: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não definidos; a coleta roda, mas sem alertas.")
        if args.once:
            with httpx.Client(timeout=30) as http:
                print(watch.run_cycle(conn, settings, http, vision_client))
        else:
            watch.watch_forever(conn, settings, args.interval, vision_client)
    elif args.cmd == "dashboard":
        dashboard.serve(settings, args.port)
    elif args.cmd == "list":
        rows = conn.execute(
            "SELECT l.source, l.title, l.price, l.currency, l.url, l.card_id, c.name AS card_name,"
            " a.condition, a.condition_confidence, a.in_protective_case, a.notes"
            " FROM listings l LEFT JOIN cards c ON c.id = l.card_id"
            " LEFT JOIN listing_analysis a ON a.listing_id = l.id"
            " ORDER BY l.first_seen_at DESC, l.id DESC LIMIT ?",
            (args.limit,),
        )
        for r in rows:
            price = f"{r['currency'] or ''} {r['price']:.2f}" if r["price"] is not None else "sem preço"
            print(f"[{r['source']}] {r['title']} — {price}\n    {r['url']}")
            if r["condition"]:
                case = ", em proteção" if r["in_protective_case"] else ""
                print(f"    condição {r['condition']} (confiança {r['condition_confidence']:.0%}{case}): {r['notes']}")
            if r["card_id"]:
                ref = valuation.reference_price(conn, r["card_id"], settings.usd_brl)
                if ref and r["price"] is not None and r["currency"] == "BRL":
                    diff = (ref.price_brl - r["price"]) / ref.price_brl * 100
                    side = "abaixo" if diff >= 0 else "acima"
                    print(f"    {r['card_name']}: referência R$ {ref.price_brl:.2f} ({ref.source}); anúncio {abs(diff):.0f}% {side}")
                elif ref:
                    print(f"    {r['card_name']}: referência R$ {ref.price_brl:.2f} ({ref.source})")
                else:
                    print(f"    {r['card_name']}: sem preço de referência")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
