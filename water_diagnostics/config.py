"""Load local configuration without displaying secrets or making requests."""

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1"
DEFAULT_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


class Settings(BaseModel):
    """Blank keys are valid during offline setup. Secrets are excluded from repr."""

    model_config = ConfigDict(frozen=True)

    nebius_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    nebius_base_url: str = DEFAULT_BASE_URL
    nebius_model: str = DEFAULT_MODEL
    tavily_api_key: SecretStr = Field(default=SecretStr(""), repr=False)


def load_settings(env_file: Path | None = None) -> Settings:
    """Read the project .env; process variables take precedence.

    This does not modify os.environ. A supplied path supports isolated tests.
    Values are not interpolated, so secrets containing dollar signs stay literal.
    """
    local_values = dotenv_values(
        env_file if env_file is not None else PROJECT_ROOT / ".env",
        interpolate=False,
        encoding="utf-8-sig",
    )

    def value(name: str, default: str = "") -> str:
        if name in os.environ:
            return os.environ[name]
        local_value = local_values.get(name)
        return default if local_value is None else local_value

    return Settings(
        nebius_api_key=value("NEBIUS_API_KEY"),
        nebius_base_url=value("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        nebius_model=value("NEBIUS_MODEL", DEFAULT_MODEL),
        tavily_api_key=value("TAVILY_API_KEY"),
    )
