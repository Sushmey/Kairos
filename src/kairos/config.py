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

    mongodb_uri: str | None = None

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
