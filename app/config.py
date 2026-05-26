

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # --- App ---
    app_env: str = "development"
    secret_key: str = "cambia_esto_en_produccion"
    port: int = 8000

    # --- CORS ---
    frontend_url: str = "http://127.0.0.1:5500"
    cors_origins: str = "http://127.0.0.1:5500,http://localhost:5500"

    # --- Supabase ---
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    database_url: str
    supabase_storage_bucket: str = "productos"

    # --- Stripe ---
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_publishable_key: str = ""

    # --- Resend ---
    resend_api_key: str
    email_from: str = "noreply@ellimpiecito.com"
    email_from_name: str = "El Limpiecito"

    # --- Rate Limiting ---
    rate_limit_login_intentos: int = 5
    rate_limit_login_ventana_minutos: int = 15

    @property
    def cors_origins_list(self) -> List[str]:
        """Convierte el string de CORS en lista"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def es_produccion(self) -> bool:
        return self.app_env == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Singleton de configuración con caché"""
    return Settings()
