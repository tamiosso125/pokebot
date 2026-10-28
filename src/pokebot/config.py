import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    pokemontcg_api_key: str | None
    meli_access_token: str | None
    usd_brl: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=os.environ.get("POKEBOT_DB", "data/pokebot.db"),
            pokemontcg_api_key=os.environ.get("POKEMONTCG_API_KEY") or None,
            meli_access_token=os.environ.get("MELI_ACCESS_TOKEN") or None,
            usd_brl=float(os.environ.get("USD_BRL", "5.50")),
        )
