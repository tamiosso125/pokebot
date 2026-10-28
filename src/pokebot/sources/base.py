from dataclasses import dataclass, field


class SourceAccessError(Exception):
    """O site recusou o acesso (token ausente, bloqueio, limite de requisições)."""


@dataclass
class Listing:
    source: str
    external_id: str
    title: str
    url: str
    price: float | None = None
    currency: str | None = None
    seller: str | None = None
    condition_text: str | None = None
    image_urls: list[str] = field(default_factory=list)
