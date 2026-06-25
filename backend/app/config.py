"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://mii:password@localhost:5432/mii"

    # AWS
    AWS_REGION: str = "eu-west-1"
    AWS_ACCOUNT_IDS: str = ""  # Comma-separated
    AWS_ASSUME_ROLE_ARN: str = ""

    # GitLab
    GITLAB_URL: str = "https://gitlab.com"
    GITLAB_TOKEN: str = ""

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Application
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DISCOVERY_SCHEDULE_HOURS: int = 24

    @property
    def aws_account_ids_list(self) -> list[str]:
        """Parse comma-separated account IDs into a list."""
        if not self.AWS_ACCOUNT_IDS:
            return []
        return [aid.strip() for aid in self.AWS_ACCOUNT_IDS.split(",") if aid.strip()]

    @property
    def database_url_sync(self) -> str:
        """Return sync database URL for Alembic migrations."""
        return self.DATABASE_URL.replace("+asyncpg", "")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
