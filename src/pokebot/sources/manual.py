import hashlib

from pokebot.sources.base import Listing


def manual_listing(
    source: str,
    url: str,
    title: str,
    price: float | None = None,
    image_urls: list[str] | None = None,
    condition_text: str | None = None,
) -> Listing:
    """Anúncio informado à mão (OLX, Shopee…). O id vem do link, então colar o mesmo link duas vezes não duplica."""
    return Listing(
        source=source,
        external_id=hashlib.sha1(url.encode()).hexdigest()[:16],
        title=title,
        url=url,
        price=price,
        currency="BRL",
        condition_text=condition_text,
        image_urls=image_urls or [],
    )
