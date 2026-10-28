import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    pokemontcg_api_key: str | None
    meli_access_token: str | None
    meli_client_id: str | None
    meli_client_secret: str | None
    usd_brl: float
    vision_model: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    min_discount_pct: float
    queries: list[str]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=os.environ.get("POKEBOT_DB", "data/pokebot.db"),
            pokemontcg_api_key=os.environ.get("POKEMONTCG_API_KEY") or None,
            meli_access_token=os.environ.get("MELI_ACCESS_TOKEN") or None,
            meli_client_id=os.environ.get("MELI_CLIENT_ID") or None,
            meli_client_secret=os.environ.get("MELI_CLIENT_SECRET") or None,
            usd_brl=float(os.environ.get("USD_BRL", "5.50")),
            vision_model=os.environ.get("POKEBOT_VISION_MODEL", "claude-sonnet-5-5"),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID") or None,
            min_discount_pct=float(os.environ.get("MIN_DISCOUNT_PCT", "30")),
            queries=[q.strip() for q in os.environ.get("POKEBOT_QUERIES", "carta pokemon").split(";") if q.strip()],
        )
