"""Centralized configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "scraper"
    db_user: str = "scraper"
    db_password: str = "changeme"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Proxy
    proxy_provider: str = "packetstream"
    proxy_user: str = ""
    proxy_pass: str = ""
    proxy_host: str = ""
    proxy_port: int = 0

    # Scraping behavior
    scrape_delay_min: float = 3.0
    scrape_delay_max: float = 8.0
    max_retries: int = 3
    workers_concurrency: int = 4
    circuit_breaker_threshold: float = 0.20
    requests_before_cookie_rotation: int = 7

    # Monitoring
    grafana_password: str = "changeme"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def proxy_url(self) -> str | None:
        if not self.proxy_host:
            return None
        auth = f"{self.proxy_user}:{self.proxy_pass}@" if self.proxy_user else ""
        return f"http://{auth}{self.proxy_host}:{self.proxy_port}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
