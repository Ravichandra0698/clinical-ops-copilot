# config.py
# Purpose: ONE place for every setting the app needs (names, keys, limits).
# Values come from environment variables or from a local file named ".env",
# so secrets never get written into the code itself.

from pydantic import SecretStr  # a string type that hides its value when printed or logged
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read values from a ".env" file in the project root if it exists.
    # extra="ignore" means other lines in .env (like DATABASE_URL) won't cause errors.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Clinical Ops Copilot"
    environment: str = "local"

    # --- Which LLM do we use? -----------------------------------------------
    # "ollama"    = a free open-source model running on YOUR computer (default)
    # "anthropic" = a paid cloud API
    llm_provider: str = "ollama"
    llm_max_tokens: int = 500          # hard cap on the answer length
    llm_timeout_seconds: float = 120.0  # local models can be slow, especially on the first call

    # --- Ollama (free, local) -----------------------------------------------
    ollama_base_url: str = "http://localhost:11434"  # where the Ollama app listens on your PC
    ollama_model: str = "llama3.2:3b"                # a small model that runs on most laptops

    # --- Anthropic (paid, optional) -----------------------------------------
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-haiku-5-5"


settings = Settings()