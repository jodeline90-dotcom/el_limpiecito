# ============================================================
# app/services/stock_service.py - Manejo transaccional de stock
# ============================================================

from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger
from typing import List, Dict


class StockInsuficienteError(Exception):
    """Se lanza cuando no hay suficiente stock para un producto"""
    def __init__(self, producto_id: str, nombre: str, stock_disponible: int, solicitado: int):
        self.producto_id = producto_id
        self.nombre = nombre
        self.stock_disponible = stock_disponible
        self.solicitado = solicitado
        super().__init__(
            f"Stock insuficiente para '{nombre}': disponible={stock_disponible}, solicitado={solicitado}"
        )


def actualizar_stock_transaccional(
    db: Session,
    items: List[Dict],
) -> bool:
    """
    Descuenta el stock de múltiples productos en una sola transacción ACID.
    
    Parámetros:
        db: Sesión SQLAlchemy activa (con transacción en curso)
        items: Lista de dicts con 'producto_id' y 'cantidad'
    
    Lanza StockInsuficienteError si algún producto no tiene suficiente stock.
    Lanza Exception genérica para otros errores (el caller debe hacer rollback).
    """
    # Verificar stock de todos los productos ANTES de modificar
    for item in items:
        resultado = db.execute(
            text("SELECT id, nombre, stock FROM \"Producto\" WHERE id = :id FOR UPDATE"),
            {"id": item["producto_id"]},
        ).fetchone()

        if not resultado:
            raise ValueError(f"Producto {item['producto_id']} no encontrado")

        if resultado.stock < item["cantidad"]:
            raise StockInsuficienteError(
                producto_id=item["producto_id"],
                nombre=resultado.nombre,
                stock_disponible=resultado.stock,
                solicitado=item["cantidad"],
            )

    # Descontar stock de todos los productos
    for item in items:
        db.execute(
            text("""
                UPDATE "Producto" 
                SET stock = stock - :cantidad,
                    contador_ventas = COALESCE(contador_ventas, 0) + :cantidad,
                    fecha_actualizacion = NOW()
                WHERE id = :id
            """),
            {"id": item["producto_id"], "cantidad": item["cantidad"]},
        )
        logger.debug(f"Stock actualizado: producto={item['producto_id']}, cantidad=-{item['cantidad']}")

    return True


def restaurar_stock_transaccional(
    db: Session,
    items: List[Dict],
) -> bool:
    """
    Restaura el stock de productos al cancelar un pedido.
    
    Parámetros:
        items: Lista de dicts con 'producto_id' y 'cantidad'
    """
    for item in items:
        db.execute(
            text("""
                UPDATE "Producto"
                SET stock = stock + :cantidad,
                    contador_ventas = GREATEST(0, COALESCE(contador_ventas, 0) - :cantidad),
                    fecha_actualizacion = NOW()
                WHERE id = :id
            """),
            {"id": item["producto_id"], "cantidad": item["cantidad"]},
        )
        logger.debug(f"Stock restaurado: producto={item['producto_id']}, cantidad=+{item['cantidad']}")

    return True


# ============================================================
# app/services/notificacion_service.py - Notificaciones internas
# ============================================================
