from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_prefix="MOSAIC_",
        extra="ignore",
    )

    environment: str = "development"
    data_dir: Path = REPOSITORY_ROOT / "data"
    frontend_origin: str = "http://localhost:3000"
    collector_origins: str = ""
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    auto_forget: bool = False

    @property
    def allowed_origins(self) -> list[str]:
        """Origins permitted to send events to the local API.

        Browser extensions receive a stable `chrome-extension://…` origin after
        installation.  Keeping that origin explicit prevents arbitrary web
        pages from using a locally running Mosaic API as an event sink.
        """
        configured_origins = [
            origin.strip()
            for origin in self.collector_origins.split(",")
            if origin.strip()
        ]
        return list(dict.fromkeys([self.frontend_origin, *configured_origins]))

    @property
    def database_url(self) -> str:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.data_dir / "mosaic.db"
        return f"sqlite:///{db_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
