from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = Field(repr=False)
    api_key: SecretStr
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5-coder:14b"
    max_request_bytes: int = Field(default=2_097_152, ge=1024, le=16_777_216)
    max_batch_events: int = Field(default=500, ge=1, le=5000)
    max_message_chars: int = Field(default=16_384, ge=1, le=65_536)
    max_analysis_events: int = Field(default=50, ge=1, le=100)
    max_analysis_input_bytes: int = Field(default=10_000, ge=512, le=100_000)
    ollama_timeout_seconds: float = Field(default=120, gt=0, le=600)
    ollama_max_concurrency: int = Field(default=1, ge=1, le=8)
    ollama_context_tokens: int = Field(default=16_384, ge=4096, le=131_072)
    ollama_output_tokens: int = Field(default=2048, ge=256, le=8192)
    max_model_response_bytes: int = Field(default=65_536, ge=1024, le=1_048_576)

    @field_validator("api_key")
    @classmethod
    def secure_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("API_KEY debe tener al menos 32 caracteres")
        return value

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL debe usar postgresql+psycopg://")
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def base_url(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("OLLAMA_BASE_URL debe ser una URL HTTP(S) sin credenciales")
        return value.rstrip("/")

    @model_validator(mode="after")
    def context_budget(self):
        # Conservative byte budget leaves room for the system prompt, JSON schema,
        # and output, without relying on a tokenizer for a different model.
        if self.max_analysis_input_bytes + self.ollama_output_tokens + 4096 > self.ollama_context_tokens:
            raise ValueError("El contexto debe cubrir entrada, salida y 4096 tokens de instrucciones")
        return self
