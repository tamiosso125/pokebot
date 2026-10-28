# PokeBot

Monitora anúncios de cartas Pokémon (Mercado Livre, OLX, Shopee…), compara com o preço de referência, analisa as fotos e avisa quando vale a pena comprar para revenda.

## Estado atual (etapas 1 a 4)

- Banco SQLite local (`data/pokebot.db`).
- Catálogo de cartas e preço de referência em USD (TCGPlayer) via [pokemontcg.io](https://pokemontcg.io).
- Coletor do Mercado Livre.
- Entrada manual de anúncios (OLX, Shopee) enquanto não há coletor automático.
- Associação do anúncio à carta pelo número impresso no título (ex.: `194/203`).
- Análise de imagem (`pokebot analyze`): um modelo de visão lê a carta (nome e número) e estima a condição (NM/LP/MP/HP/DMG/unknown) com confiança; carta em sleeve/pasta ou foto ruim baixa a confiança. Se o título não trazia o número, o número lido na foto liga o anúncio à carta.
- Vigia contínuo (`pokebot watch`): a cada N minutos busca no Mercado Livre, associa às cartas, analisa fotos (se houver `ANTHROPIC_API_KEY`) e manda no Telegram os anúncios novos com desconto acima de `MIN_DISCOUNT_PCT`. Cada anúncio é avisado uma vez só.
- Painel local (`pokebot dashboard`): tabela filtrável e ordenável em http://127.0.0.1:8000, atualiza sozinha a cada 30 s.
- Preço de referência: LigaPokemon (importado de CSV) se existir; senão o dólar do TCGPlayer convertido por `USD_BRL`.

Ainda não existem: coleta automática da LigaPokemon (por enquanto o CSV é preenchido à mão), coletores de OLX/Shopee.

## Como usar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # e exporte as variáveis, se for usar chaves

pokebot sync-catalog --query 'name:charizard*'
pokebot search-ml --query 'carta pokemon charizard'
pokebot add-manual --source olx --url https://... --title 'Charizard base' --price 120 --image https://...
pokebot match                      # liga anúncios às cartas do catálogo
pokebot import-liga precos.csv     # CSV: nome,numero,preco_brl,url
pokebot analyze --limit 10         # precisa de ANTHROPIC_API_KEY; cada anúncio = 1 chamada paga
pokebot watch --interval 15        # vigia contínuo (use --once para testar uma rodada)
pokebot dashboard --port 8000      # painel local
pokebot list                       # mostra anúncio vs. preço de referência
pytest
```

> A busca do Mercado Livre exige token (a busca pública responde 403). Crie um app em developers.mercadolivre.com.br e defina `MELI_CLIENT_ID` e `MELI_CLIENT_SECRET`; o programa pede e renova o token sozinho. Ainda não validado contra a API real.

> Condição vem de fotos: é uma estimativa, não nota oficial. Miniaturas do Mercado Livre são pequenas e rendem análise fraca; prefira fotos grandes.

Para rodar o vigia e o painel juntos, abra dois terminais (um com `pokebot watch`, outro com `pokebot dashboard`); eles compartilham o mesmo banco.

## Windows (PowerShell)

- Ative o ambiente com `.venv\Scripts\Activate.ps1` (o `source` é do Linux/Mac) e defina chaves com `$env:NOME="valor"` (vale só para aquela janela).
- O PowerShell remove aspas duplas de dentro de argumentos: em vez de `name:"rayquaza v"`, use curinga, `--query "name:rayquaza*"`.
- Se `pokebot` não for reconhecido, use `python -m pokebot.cli <comando>`.
