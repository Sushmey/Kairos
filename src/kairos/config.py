"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    gemini_flash_lite_model: str = "gemini-3.1-flash-lite"
    enrich_concurrency: int = 10
    enrich_max_input_chars: int = 2000

    embedding_backend: str = "gemini"  # local | gemini
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimensions: int = 768
    embedding_batch_size: int = 32
    embedding_max_input_chars: int = 2000
    hdbscan_min_cluster_size: int = 3
    hdbscan_min_samples: int = 2

    mongodb_uri: str | None = None
    mongodb_db_name: str = "kairos"

    # X API v2 — https://docs.x.com/x-api/users/get-bookmarks
    x_api_base_url: str = "https://api.x.com"
    x_access_token: str | None = None
    x_refresh_token: str | None = None
    x_client_id: str | None = None
    x_client_secret: str | None = None
    x_user_id: str | None = None
    x_oauth_redirect_uri: str = "http://127.0.0.1:8765/callback"
    x_oauth_scopes: str = "bookmark.read tweet.read users.read offline.access"

    google_calendar_credentials_path: str | None = None

    # Agent loop interval (seconds) for demo /loop parity
    decision_interval_seconds: int = 300

    daily_surface_budget: int = 3
    min_gap_between_surfaces_minutes: int = 45

    # Delivery adapters (comma-separated: web, os)
    delivery_targets: str = "web"
    web_base_url: str = "http://localhost:8420"
    os_delivery_enabled: bool = False
    mcp_suppress_ok_in_chat: bool = True

    def delivery_target_list(self) -> list[str]:
        return [t.strip() for t in self.delivery_targets.split(",") if t.strip()]


settings = Settings()
