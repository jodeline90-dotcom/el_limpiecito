# ============================================================
# app/utils/storage.py - Helpers para Supabase Storage
# ============================================================

from app.database import get_supabase
from app.config import get_settings
from loguru import logger
from typing import Optional
import uuid

settings = get_settings()


def subir_archivo(
    contenido: bytes,
    ruta: str,
    content_type: str,
    bucket: str = None,
    upsert: bool = False,
) -> Optional[str]:
    """
    Sube un archivo a Supabase Storage.
    
    Args:
        contenido: Bytes del archivo
        ruta: Ruta dentro del bucket (ej: "productos/uuid/imagen.jpg")
        content_type: MIME type del archivo
        bucket: Nombre del bucket (por defecto usa SUPABASE_STORAGE_BUCKET)
        upsert: Si True, sobreescribe si ya existe
    
    Returns:
        URL pública del archivo, o None si falla
    """
    bucket = bucket or settings.supabase_storage_bucket
    supabase = get_supabase()
    try:
        opciones = {"content-type": content_type}
        if upsert:
            opciones["upsert"] = "true"

        supabase.storage.from_(bucket).upload(ruta, contenido, opciones)
        url = supabase.storage.from_(bucket).get_public_url(ruta)
        logger.info(f"📦 Archivo subido: {ruta} ({len(contenido)} bytes)")
        return url
    except Exception as e:
        logger.error(f"❌ Error subiendo {ruta} a Storage: {e}")
        return None


def eliminar_archivo(ruta: str, bucket: str = None) -> bool:
    """Elimina un archivo de Supabase Storage"""
    bucket = bucket or settings.supabase_storage_bucket
    supabase = get_supabase()
    try:
        supabase.storage.from_(bucket).remove([ruta])
        logger.info(f"🗑️  Archivo eliminado: {ruta}")
        return True
    except Exception as e:
        logger.error(f"Error eliminando {ruta}: {e}")
        return False


def listar_archivos(prefijo: str, bucket: str = None) -> list[str]:
    """
    Lista archivos en un prefijo del bucket.
    Retorna lista de URLs públicas.
    """
    bucket = bucket or settings.supabase_storage_bucket
    supabase = get_supabase()
    try:
        archivos = supabase.storage.from_(bucket).list(prefijo)
        urls = []
        for archivo in (archivos or []):
            if archivo.get("name"):
                url = supabase.storage.from_(bucket).get_public_url(f"{prefijo}/{archivo['name']}")
                urls.append(url)
        return urls
    except Exception as e:
        logger.error(f"Error listando archivos en {prefijo}: {e}")
        return []


def generar_nombre_unico(nombre_original: str) -> str:
    """
    Genera un nombre de archivo único basado en UUID.
    Preserva la extensión original.
    Ej: 'foto.jpg' → 'a1b2c3d4-e5f6.jpg'
    """
    extension = ""
    if "." in nombre_original:
        extension = "." + nombre_original.rsplit(".", 1)[-1].lower()
    return f"{uuid.uuid4()}{extension}"
