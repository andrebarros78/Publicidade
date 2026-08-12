import os
from dataclasses import dataclass

def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("ADS_ENV", "sandbox")
    dry_run: bool = env_bool("ADS_DRY_RUN", True)
    max_budget_increase_pct: float = float(os.getenv("ADS_MAX_BUDGET_INCREASE_PCT", "20"))
    meta_token: str = os.getenv("META_ACCESS_TOKEN", "")
    meta_account_id: str = os.getenv("META_AD_ACCOUNT_ID", "")
    meta_graph_version: str = os.getenv("META_GRAPH_VERSION", "v26.0")
    tiktok_token: str = os.getenv("TIKTOK_ACCESS_TOKEN", "")
    tiktok_advertiser_id: str = os.getenv("TIKTOK_ADVERTISER_ID", "")
    tiktok_api_base: str = os.getenv("TIKTOK_API_BASE", "https://business-api.tiktok.com/open_api/v1.3")

settings = Settings()
