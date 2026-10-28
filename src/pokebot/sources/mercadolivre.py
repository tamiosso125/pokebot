import httpx

from pokebot.sources.base import Listing, SourceAccessError

SEARCH_URL = "https://api.mercadolibre.com/sites/MLB/search"


class MercadoLivreSource:
    name = "mercadolivre"

    def __init__(self, client: httpx.Client, access_token: str | None = None):
        self.client = client
        self.headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

    def search(self, query: str, limit: int = 50) -> list[Listing]:
        resp = self.client.get(
            SEARCH_URL, params={"q": query, "limit": limit}, headers=self.headers
        )
        if resp.status_code in (401, 403, 429):
            raise SourceAccessError(
                f"Mercado Livre recusou a busca (HTTP {resp.status_code}). "
                "Defina MELI_ACCESS_TOKEN com o token do seu app em developers.mercadolivre.com.br."
            )
        resp.raise_for_status()
        return [self._parse(item) for item in resp.json().get("results", [])]

    def _parse(self, item: dict) -> Listing:
        thumb = item.get("thumbnail")
        return Listing(
            source=self.name,
            external_id=item["id"],
            title=item["title"],
            url=item["permalink"],
            price=item.get("price"),
            currency=item.get("currency_id"),
            seller=(item.get("seller") or {}).get("nickname"),
            condition_text=item.get("condition"),
            image_urls=[thumb] if thumb else [],
        )
