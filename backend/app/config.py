from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM provider — defaults to Groq (free, fast, OpenAI-compatible)
    # Set LLM_BASE_URL="http://localhost:11434/v1" + LLM_API_KEY="ollama" to use Ollama instead
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.1-8b-instant"
    llm_api_key: str = ""  # set via LLM_API_KEY env var

    # Client-side rate limiting — keep us under the provider's per-minute ceilings.
    # Groq free tier for llama-3.1-8b-instant is ~30 RPM / 6,000 TPM; defaults leave headroom.
    llm_max_concurrency: int = 2  # simultaneous in-flight requests
    llm_rpm: int = 25  # requests per minute
    llm_tpm: int = 5500  # tokens per minute (prompt + completion)
    llm_completion_token_budget: int = 1200  # tokens reserved per call for the response

    tavily_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
