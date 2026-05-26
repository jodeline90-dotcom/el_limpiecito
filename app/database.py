

from supabase import create_client, Client
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from app.config import get_settings
from loguru import logger
from typing import Generator

settings = get_settings()


def get_supabase() -> Client:
    """Retorna cliente Supabase con clave de servicio (sin RLS)"""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_anon() -> Client:
    """Retorna cliente Supabase con clave anónima (respeta RLS)"""
    return create_client(settings.supabase_url, settings.supabase_anon_key)



engine = create_engine(
    settings.database_url,
    poolclass=NullPool,          # Railway/Supabase cierran conexiones inactivas
    echo=settings.app_env == "development",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency de FastAPI para obtener sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def verificar_conexion_supabase() -> bool:
    """Verifica que Supabase responda correctamente al arrancar la app"""
    try:
        client = get_supabase()
        resultado = client.table("Categoria").select("id").limit(1).execute()
        logger.info("[SUCCESS] Conexión a Supabase establecida correctamente")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Error conectando a Supabase: {e}")
        return False


async def verificar_conexion_db() -> bool:
    """Verifica conexión directa a PostgreSQL"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[SUCCESS] Conexión directa a PostgreSQL establecida")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Error conectando a PostgreSQL: {e}")
        return False
