# ============================================================
# app/services/notificacion_service.py - Notificaciones internas
# ============================================================

from app.database import get_supabase
from loguru import logger
from typing import Literal

TipoNotificacion = Literal[
    "pedido_confirmado",
    "pedido_enviado",
    "pedido_entregado",
    "pedido_cancelado",
    "pago_exitoso",
    "pago_fallido",
    "stock_bajo",
    "bienvenida",
    "oferta",
    "general",
]


async def crear_notificacion(
    usuario_id: str,
    tipo: TipoNotificacion,
    mensaje: str,
    referencia_id: str | None = None,
    referencia_tipo: str | None = None,
) -> bool:
    """
    Crea una notificación interna para el usuario en la tabla Notificacion.
    
    Parámetros:
        usuario_id: ID del usuario destinatario
        tipo: Tipo de notificación (define el ícono/color en el frontend)
        mensaje: Texto de la notificación
        referencia_id: ID del recurso relacionado (pedido, producto, etc.)
        referencia_tipo: Tipo del recurso ('pedido', 'producto', etc.)
    
    Retorna True si se creó correctamente.
    """
    supabase = get_supabase()
    try:
        datos = {
            "usuario_id": usuario_id,
            "tipo": tipo,
            "mensaje": mensaje,
            "leida": False,
        }
        if referencia_id:
            datos["referencia_id"] = referencia_id
        if referencia_tipo:
            datos["referencia_tipo"] = referencia_tipo

        supabase.table("Notificacion").insert(datos).execute()
        logger.debug(f"🔔 Notificación '{tipo}' creada para usuario {usuario_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creando notificación para {usuario_id}: {e}")
        return False


async def marcar_notificaciones_leidas(usuario_id: str) -> int:
    """
    Marca todas las notificaciones de un usuario como leídas.
    Retorna la cantidad de notificaciones actualizadas.
    """
    supabase = get_supabase()
    try:
        resultado = (
            supabase.table("Notificacion")
            .update({"leida": True})
            .eq("usuario_id", usuario_id)
            .eq("leida", False)
            .execute()
        )
        cantidad = len(resultado.data or [])
        logger.debug(f"✅ {cantidad} notificaciones marcadas como leídas para {usuario_id}")
        return cantidad
    except Exception as e:
        logger.error(f"Error marcando notificaciones leídas: {e}")
        return 0


async def crear_notificacion_admin(
    tipo: TipoNotificacion,
    mensaje: str,
    referencia_id: str | None = None,
) -> bool:
    """
    Crea notificaciones para todos los administradores del sistema.
    Usado para alertas de stock bajo, nuevos pedidos, etc.
    """
    supabase = get_supabase()
    try:
        admins = (
            supabase.table("Usuario")
            .select("id")
            .eq("rol", "admin")
            .eq("activo", True)
            .execute()
        )
        admin_ids = [a["id"] for a in (admins.data or [])]

        for admin_id in admin_ids:
            await crear_notificacion(admin_id, tipo, mensaje, referencia_id, "admin")

        return True
    except Exception as e:
        logger.error(f"Error notificando admins: {e}")
        return False
