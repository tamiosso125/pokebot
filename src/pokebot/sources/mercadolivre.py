import time

import httpx

from pokebot.sources.base import Listing, SourceAccessError

SEARCH_URL = "https://api.mercadolibre.com/sites/MLB/search"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


class MercadoLivreSource:
    name = "mercadolivre"

    def __init__(
        self,
        client: httpx.Client,
        access_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.client = client
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._expires_at = float("inf") if access_token else 0.0

    def _refresh_token(self) -> None:
        """Token do próprio aplicativo (client credentials); vale algumas horas."""
        if not (self.client_id and self.client_secret):
            return
        resp = self.client.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret},
        )
        if resp.status_code >= 400:
            raise SourceAccessError(
                f"Mercado Livre recusou o Client ID/Secret (HTTP {resp.status_code}). Confira MELI_CLIENT_ID e MELI_CLIENT_SECRET."
            )
        body = resp.json()
        self.access_token = body["access_token"]
        self._expires_at = time.monotonic() + max(int(body.get("expires_in", 0)) - 60, 0)

    def _headers(self) -> dict:
        if time.monotonic() >= self._expires_at:
            self._refresh_token()
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def _get(self, query: str, limit: int) -> httpx.Response:
        return self.client.get(SEARCH_URL, params={"q": query, "limit": limit}, headers=self._headers())

    def search(self, query: str, limit: int = 50) -> list[Listing]:
        resp = self._get(query, limit)
        if resp.status_code == 401 and self.client_id and self.client_secret:
            self._expires_at = 0.0  # token vencido: pega outro e repete uma vez
            resp = self._get(query, limit)
        if resp.status_code in (401, 403, 429):
            raise SourceAccessError(
                f"Mercado Livre recusou a busca (HTTP {resp.status_code}). "
                "Crie um app em developers.mercadolivre.com.br e defina MELI_CLIENT_ID e MELI_CLIENT_SECRET."
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
