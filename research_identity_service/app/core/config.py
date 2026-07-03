from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from pathlib import Path

class Settings(BaseSettings):
    nvidia_api_key: str = Field(default="", validation_alias="NVIDIA_API_KEY")
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    port: int = Field(default=8001, validation_alias="PORT")
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    database_url: str = Field(default="sqlite:///data/cache/app.db", validation_alias="DATABASE_URL")
    output_dir: str = Field(default="data/output", validation_alias="OUTPUT_DIR")

    @property
    def db_path(self) -> Path:
        # Extract SQLite path
        path_str = self.database_url
        if path_str.startswith("sqlite:///"):
            path_str = path_str[10:]
        return Path(path_str)

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
