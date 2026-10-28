# PokeBot

Monitora anúncios de cartas Pokémon (Mercado Livre, OLX, Shopee…), compara com o preço de referência, analisa as fotos e avisa quando vale a pena comprar para revenda.

## Estado atual (etapa 1: base e coleta)

- Banco SQLite local (`data/pokebot.db`).
- Catálogo de cartas e preço de referência em USD (TCGPlayer) via [pokemontcg.io](https://pokemontcg.io).
- Coletor do Mercado Livre.
- Entrada manual de anúncios (OLX, Shopee) enquanto não há coletor automático.

Ainda não existem: preço de revenda no Brasil (LigaPokemon, coleta semanal), análise de imagem, painel e alertas.

## Como usar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # e exporte as variáveis, se for usar chaves

pokebot sync-catalog --query 'name:charizard'
pokebot search-ml --query 'carta pokemon charizard'
pokebot add-manual --source olx --url https://... --title 'Charizard base' --price 120 --image https://...
pokebot list
pytest
```

> A busca pública do Mercado Livre pode exigir token. Se responder 401/403, o comando avisa; crie um app em developers.mercadolivre.com.br e defina `MELI_ACCESS_TOKEN`. Este coletor ainda não foi testado contra a API real.
