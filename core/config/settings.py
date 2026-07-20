import json
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_env: str = "development"
    app_secret_key: str = "dev-secret-key"
    log_level: str = "INFO"
    timezone: str = "America/Chicago"
    base_dir: Path = Path(__file__).resolve().parent.parent.parent

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://aurum:changeme@localhost:5432/aurum_commerce"
    database_url_sync: str = "postgresql+psycopg2://aurum:changeme@localhost:5432/aurum_commerce"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection_business_memory: str = "business_memory"
    chroma_collection_products: str = "products"
    chroma_collection_creatives: str = "creatives"

    # ── Local LLM ─────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.1:70b"
    ollama_fast_model: str = "llama3.2:3b"
    ollama_vision_model: str = "llava:13b"
    ollama_embed_model: str = "nomic-embed-text"
    llm_prefer_local: bool = True
    llm_max_local_retries: int = 3

    # ── Cloud LLM ────────────────────────────────────────────────────────────
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-6"

    # ── Shopify ───────────────────────────────────────────────────────────────
    shopify_stores: str = "[]"
    shopify_api_version: str = "2025-01"

    @property
    def shopify_stores_list(self) -> list:
        return json.loads(self.shopify_stores)

    # ── Meta ──────────────────────────────────────────────────────────────────
    meta_app_id: Optional[str] = None
    meta_app_secret: Optional[str] = None
    meta_access_token: Optional[str] = None
    meta_ad_account_id: Optional[str] = None
    meta_page_id: Optional[str] = None

    # ── TikTok ───────────────────────────────────────────────────────────────
    tiktok_app_id: Optional[str] = None
    tiktok_app_secret: Optional[str] = None
    tiktok_access_token: Optional[str] = None
    tiktok_advertiser_id: Optional[str] = None

    # ── Google ────────────────────────────────────────────────────────────────
    google_api_key: Optional[str] = None
    google_search_engine_id: Optional[str] = None
    serpapi_key: Optional[str] = None

    # ── Pexels ────────────────────────────────────────────────────────────────
    pexels_api_key: Optional[str] = None

    # ── Email ─────────────────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    report_recipients: str = "torylivas@gmail.com"

    @property
    def report_recipients_list(self) -> List[str]:
        return [r.strip() for r in self.report_recipients.split(",")]

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # ── Tandem Browser ────────────────────────────────────────────────────────
    tandem_ws_url: str = "ws://localhost:9222"
    tandem_timeout: int = 30

    # ── Business Rules ────────────────────────────────────────────────────────
    min_gross_margin: float = 0.40
    min_opportunity_score: float = 60.0
    min_confidence_score: float = 65.0
    max_shipping_days: int = 15
    min_supplier_rating: float = 4.0
    price_change_approval_threshold: float = 0.15
    ad_spend_approval_threshold: float = 100.0

    # ── Schedules ─────────────────────────────────────────────────────────────
    brief_schedule_cron: str = "0 7 * * *"
    brief_timezone: str = "America/Chicago"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


settings = Settings()
