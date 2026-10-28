# PokeBot

Monitora anúncios de cartas Pokémon (Mercado Livre, OLX, Shopee…), compara com o preço de referência, analisa as fotos e avisa quando vale a pena comprar para revenda.

## Estado atual (etapas 1 e 2)

- Banco SQLite local (`data/pokebot.db`).
- Catálogo de cartas e preço de referência em USD (TCGPlayer) via [pokemontcg.io](https://pokemontcg.io).
- Coletor do Mercado Livre.
- Entrada manual de anúncios (OLX, Shopee) enquanto não há coletor automático.
- Associação do anúncio à carta pelo número impresso no título (ex.: `194/203`).
- Preço de referência: LigaPokemon (importado de CSV) se existir; senão o dólar do TCGPlayer convertido por `USD_BRL`.

Ainda não existem: coleta automática da LigaPokemon (por enquanto o CSV é preenchido à mão), identificação por imagem, painel e alertas.

## Como usar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # e exporte as variáveis, se for usar chaves

pokebot sync-catalog --query 'name:charizard'
pokebot search-ml --query 'carta pokemon charizard'
pokebot add-manual --source olx --url https://... --title 'Charizard base' --price 120 --image https://...
pokebot match                      # liga anúncios às cartas do catálogo
pokebot import-liga precos.csv     # CSV: nome,numero,preco_brl,url
pokebot list                       # mostra anúncio vs. preço de referência
pytest
```

> A busca pública do Mercado Livre pode exigir token. Se responder 401/403, o comando avisa; crie um app em developers.mercadolivre.com.br e defina `MELI_ACCESS_TOKEN`. Este coletor ainda não foi testado contra a API real.
