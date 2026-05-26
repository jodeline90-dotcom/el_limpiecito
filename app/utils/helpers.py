# ============================================================
# app/utils/helpers.py - Funciones de utilidad compartidas
# ============================================================

from datetime import datetime, timezone
from typing import Any, Optional
import hashlib
import math


def paginar(total: int, pagina: int, limite: int) -> dict:
    """Calcula metadatos de paginación."""
    total_paginas = math.ceil(total / limite) if total > 0 else 1
    return {
        "pagina": pagina,
        "limite": limite,
        "total": total,
        "total_paginas": total_paginas,
        "tiene_siguiente": pagina < total_paginas,
        "tiene_anterior": pagina > 1,
    }


def ahora_utc() -> datetime:
    """Retorna el datetime actual en UTC con zona horaria"""
    return datetime.now(timezone.utc)


def formatear_precio(monto: float | int) -> str:
    """Formatea un número como precio en MXN. Ej: 1500.5 → '$1,500.50 MXN'"""
    return f"${monto:,.2f} MXN"


def truncar_id(uuid_str: str, longitud: int = 8) -> str:
    """Retorna los primeros N caracteres del UUID en mayúsculas"""
    return uuid_str[:longitud].upper()


def hash_ip(ip: str) -> str:
    """Hash SHA-256 de una IP para logs anónimos"""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def limpiar_telefono(telefono: Optional[str]) -> Optional[str]:
    """Normaliza un número de teléfono eliminando espacios, guiones y paréntesis."""
    if not telefono:
        return None
    return "".join(c for c in telefono if c.isdigit() or c == "+")


def calcular_descuento(
    precio_original: float,
    precio_comparacion: Optional[float],
) -> Optional[int]:
    """Calcula el porcentaje de descuento entre precio actual y precio de comparación."""
    if not precio_comparacion or precio_comparacion <= precio_original:
        return None
    return round((1 - precio_original / precio_comparacion) * 100)


def validar_stock(stock: int, cantidad_solicitada: int) -> tuple[bool, str]:
    """Valida si hay suficiente stock. Retorna (ok, mensaje)."""
    if stock <= 0:
        return False, "Producto sin stock disponible"
    if cantidad_solicitada > stock:
        return False, f"Solo hay {stock} unidades disponibles"
    return True, ""


def sanitizar_busqueda(termino: str) -> str:
    """Limpia un término de búsqueda para evitar caracteres problemáticos en ILIKE."""
    termino = termino.strip()[:100]
    termino = termino.replace("%", "").replace("_", " ").replace("\\", "")
    return termino
