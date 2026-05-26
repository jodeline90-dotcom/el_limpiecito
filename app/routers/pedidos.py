

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.schemas import (
    CrearPedidoRequest, CambiarEstadoPedidoRequest,
    PedidoResponse, PedidoListResponse, ItemPedidoResponse, MensajeResponse
)
from app.database import get_supabase, get_db
from app.dependencies import get_current_user, get_admin_user, UsuarioActual
from app.services.stock_service import actualizar_stock_transaccional, restaurar_stock_transaccional, StockInsuficienteError
from app.services.notificacion_service import crear_notificacion, crear_notificacion_admin
from app.services.email_service import enviar_cambio_estado_pedido
from decimal import Decimal
from loguru import logger
import uuid

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def _serializar_pedido(pedido: dict, items: list) -> PedidoResponse:
    """Convierte datos del pedido en respuesta Pydantic"""
    items_resp = [
        ItemPedidoResponse(
            id=item["id"],
            producto_id=item["producto_id"],
            nombre_producto=item.get("nombre_producto") or (
                item.get("Producto", {}) or {}
            ).get("nombre", "Producto"),
            precio_unitario=Decimal(str(item["precio_unitario"])),
            cantidad=item["cantidad"],
            subtotal=Decimal(str(item["precio_unitario"])) * item["cantidad"],
        )
        for item in items
    ]

    return PedidoResponse(
        id=pedido["id"],
        usuario_id=pedido["usuario_id"],
        estado=pedido["estado"],
        subtotal=Decimal(str(pedido.get("subtotal", 0))),
        descuento=Decimal(str(pedido.get("descuento", 0))),
        total=Decimal(str(pedido.get("total", 0))),
        notas=pedido.get("notas"),
        direccion=pedido.get("Direccion"),
        items=items_resp,
        fecha_creacion=pedido.get("fecha_creacion"),
        fecha_actualizacion=pedido.get("fecha_actualizacion"),
    )


@router.post("", response_model=PedidoResponse, status_code=201)
async def crear_pedido(
    datos: CrearPedidoRequest,
    background_tasks: BackgroundTasks,
    usuario: UsuarioActual = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea un pedido desde el carrito del usuario.
    
    TRANSACCIÓN ATÓMICA (SQLAlchemy + PostgreSQL):
    1. Verificar carrito no vacío
    2. Verificar dirección del usuario
    3. Crear registro Pedido
    4. Crear registros ItemPedido
    5. Actualizar stock de productos (con rollback si falla)
    6. Vaciar carrito
    
    Si cualquier paso falla, se hace rollback completo.
    """
    supabase = get_supabase()

    # Verificar dirección pertenece al usuario
    dir_res = (
        supabase.table("Direccion")
        .select("*")
        .eq("id", datos.direccion_id)
        .eq("usuario_id", usuario.id)
        .execute()
    )
    if not dir_res.data:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")

    # Obtener carrito y sus items
    carrito_res = (
        supabase.table("Carrito")
        .select("*")
        .eq("usuario_id", usuario.id)
        .execute()
    )
    if not carrito_res.data:
        raise HTTPException(status_code=400, detail="No tienes un carrito activo")

    carrito = carrito_res.data[0]
    items_res = (
        supabase.table("ItemCarrito")
        .select("*, Producto(id, nombre, precio, stock)")
        .eq("carrito_id", carrito["id"])
        .execute()
    )
    items = items_res.data or []

    if not items:
        raise HTTPException(status_code=400, detail="Tu carrito está vacío")

    # Calcular totales
    subtotal = sum(
        Decimal(str(item["precio_unitario"])) * item["cantidad"]
        for item in items
    )
    descuento_pct = carrito.get("cupon_descuento_porcentaje", 0) or 0
    descuento_fijo = Decimal(str(carrito.get("cupon_descuento_fijo", 0) or 0))
    descuento = (subtotal * Decimal(str(descuento_pct)) / 100) + descuento_fijo
    descuento = min(descuento, subtotal)
    total = subtotal - descuento

    pedido_id = str(uuid.uuid4())

    try:
        # Crear pedido
        db.execute(
            text("""
                INSERT INTO "Pedido" (id, usuario_id, estado, subtotal, descuento, total,
                    direccion_id, notas, cupon_codigo, fecha_creacion, fecha_actualizacion)
                VALUES (:id, :usuario_id, 'pendiente', :subtotal, :descuento, :total,
                    :direccion_id, :notas, :cupon_codigo, NOW(), NOW())
            """),
            {
                "id": pedido_id,
                "usuario_id": usuario.id,
                "subtotal": float(subtotal),
                "descuento": float(descuento),
                "total": float(total),
                "direccion_id": datos.direccion_id,
                "notas": datos.notas,
                "cupon_codigo": carrito.get("cupon_codigo"),
            },
        )

        # Crear items del pedido
        items_para_stock = []
        for item in items:
            item_id = str(uuid.uuid4())
            producto = item.get("Producto") or {}
            db.execute(
                text("""
                    INSERT INTO "ItemPedido" (id, pedido_id, producto_id, nombre_producto,
                        precio_unitario, cantidad, subtotal)
                    VALUES (:id, :pedido_id, :producto_id, :nombre_producto,
                        :precio_unitario, :cantidad, :subtotal)
                """),
                {
                    "id": item_id,
                    "pedido_id": pedido_id,
                    "producto_id": item["producto_id"],
                    "nombre_producto": producto.get("nombre", "Producto"),
                    "precio_unitario": float(item["precio_unitario"]),
                    "cantidad": item["cantidad"],
                    "subtotal": float(item["precio_unitario"]) * item["cantidad"],
                },
            )
            items_para_stock.append({"producto_id": item["producto_id"], "cantidad": item["cantidad"]})

        # Actualizar stock (lanza excepción si no hay suficiente)
        actualizar_stock_transaccional(db, items_para_stock)

        # Vaciar carrito
        db.execute(
            text('DELETE FROM "ItemCarrito" WHERE carrito_id = :carrito_id'),
            {"carrito_id": carrito["id"]},
        )
        db.execute(
            text("""
                UPDATE "Carrito"
                SET cupon_codigo = NULL, cupon_descuento_porcentaje = NULL, cupon_descuento_fijo = NULL
                WHERE id = :id
            """),
            {"id": carrito["id"]},
        )

        # Registrar historial de estado inicial
        db.execute(
            text("""
                INSERT INTO "HistorialEstadoPedido" (id, pedido_id, estado, fecha)
                VALUES (:id, :pedido_id, 'pendiente', NOW())
            """),
            {"id": str(uuid.uuid4()), "pedido_id": pedido_id},
        )

        db.commit()
        logger.info(f"✅ Pedido {pedido_id} creado para usuario {usuario.email} | Total: ${total:.2f}")

    except StockInsuficienteError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente para '{e.nombre}': disponible {e.stock_disponible}, solicitado {e.solicitado}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creando pedido para {usuario.email}: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar el pedido")

    # Notificaciones en background (fuera de la transacción)
    background_tasks.add_task(
        crear_notificacion, usuario.id, "pedido_confirmado",
        f"Tu pedido #{pedido_id[:8].upper()} fue recibido. Total: ${total:.2f} MXN",
        pedido_id, "pedido"
    )
    background_tasks.add_task(
        crear_notificacion_admin, "general",
        f"Nuevo pedido #{pedido_id[:8].upper()} de {usuario.email} por ${total:.2f} MXN",
        pedido_id
    )

    # Retornar pedido creado
    items_formateados = [
        {
            "id": str(uuid.uuid4()),
            "producto_id": item["producto_id"],
            "nombre_producto": (item.get("Producto") or {}).get("nombre", "Producto"),
            "precio_unitario": item["precio_unitario"],
            "cantidad": item["cantidad"],
        }
        for item in items
    ]
    pedido_dict = {
        "id": pedido_id,
        "usuario_id": usuario.id,
        "estado": "pendiente",
        "subtotal": float(subtotal),
        "descuento": float(descuento),
        "total": float(total),
        "notas": datos.notas,
        "Direccion": dir_res.data[0],
        "fecha_creacion": None,
        "fecha_actualizacion": None,
    }
    return _serializar_pedido(pedido_dict, items_formateados)


@router.get("", response_model=PedidoListResponse)
async def historial_pedidos(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Obtiene el historial de pedidos del usuario autenticado"""
    supabase = get_supabase()
    pedidos_res = (
        supabase.table("Pedido")
        .select("*, Direccion(*), ItemPedido(*)")
        .eq("usuario_id", usuario.id)
        .order("fecha_creacion", desc=True)
        .execute()
    )
    pedidos = []
    for p in (pedidos_res.data or []):
        items = p.pop("ItemPedido", []) or []
        pedidos.append(_serializar_pedido(p, items))

    return PedidoListResponse(pedidos=pedidos, total=len(pedidos))


@router.get("/{pedido_id}", response_model=PedidoResponse)
async def detalle_pedido(
    pedido_id: str,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Obtiene el detalle de un pedido específico del usuario"""
    supabase = get_supabase()
    res = (
        supabase.table("Pedido")
        .select("*, Direccion(*), ItemPedido(*)")
        .eq("id", pedido_id)
        .eq("usuario_id", usuario.id)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    p = res.data
    items = p.pop("ItemPedido", []) or []
    return _serializar_pedido(p, items)


@router.put("/{pedido_id}/estado", response_model=MensajeResponse)
async def cambiar_estado_pedido(
    pedido_id: str,
    datos: CambiarEstadoPedidoRequest,
    background_tasks: BackgroundTasks,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Cambia el estado de un pedido (solo admins)"""
    supabase = get_supabase()

    pedido_res = (
        supabase.table("Pedido")
        .select("*, Usuario(email, nombre)")
        .eq("id", pedido_id)
        .single()
        .execute()
    )
    if not pedido_res.data:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    pedido = pedido_res.data

    # Actualizar estado
    supabase.table("Pedido").update({
        "estado": datos.estado,
        "fecha_actualizacion": "now()",
    }).eq("id", pedido_id).execute()

    # Registrar en historial
    supabase.table("HistorialEstadoPedido").insert({
        "id": str(uuid.uuid4()),
        "pedido_id": pedido_id,
        "estado": datos.estado,
        "notas": datos.notas,
        "cambiado_por": admin.id,
    }).execute()

    # Notificar al cliente
    usuario_data = pedido.get("Usuario", {}) or {}
    if usuario_data.get("email"):
        background_tasks.add_task(
            enviar_cambio_estado_pedido,
            usuario_data["email"],
            usuario_data.get("nombre", "Cliente"),
            pedido_id,
            datos.estado,
        )
    background_tasks.add_task(
        crear_notificacion,
        pedido["usuario_id"],
        f"pedido_{datos.estado}" if f"pedido_{datos.estado}" in [
            "pedido_confirmado", "pedido_enviado", "pedido_entregado", "pedido_cancelado"
        ] else "general",
        f"Tu pedido #{pedido_id[:8].upper()} está: {datos.estado}",
        pedido_id, "pedido"
    )

    # Si se entrega el pedido, recalcular nivel del cliente de forma asíncrona
    if datos.estado == "entregado":
        background_tasks.add_task(_recalcular_nivel_usuario, supabase, pedido["usuario_id"])

    logger.info(f"Pedido {pedido_id} cambió a '{datos.estado}' por {admin.email}")
    return MensajeResponse(mensaje=f"Estado del pedido actualizado a '{datos.estado}'")



@router.post("/{pedido_id}/cancelar", response_model=MensajeResponse)
async def cancelar_pedido(
    pedido_id: str,
    background_tasks: BackgroundTasks,
    usuario: UsuarioActual = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancela un pedido si está en estado 'pendiente'.
    Restaura el stock de los productos.
    """
    supabase = get_supabase()

    pedido_res = (
        supabase.table("Pedido")
        .select("*")
        .eq("id", pedido_id)
        .eq("usuario_id", usuario.id)
        .single()
        .execute()
    )
    if not pedido_res.data:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    pedido = pedido_res.data
    if pedido["estado"] != "pendiente":
        raise HTTPException(
            status_code=400,
            detail=f"Solo puedes cancelar pedidos en estado 'pendiente'. Estado actual: '{pedido['estado']}'"
        )

    # Obtener items para restaurar stock
    items_res = (
        supabase.table("ItemPedido")
        .select("producto_id, cantidad")
        .eq("pedido_id", pedido_id)
        .execute()
    )
    items = items_res.data or []

    try:
        restaurar_stock_transaccional(db, items)
        db.execute(
            text('UPDATE "Pedido" SET estado = \'cancelado\', fecha_actualizacion = NOW() WHERE id = :id'),
            {"id": pedido_id},
        )
        db.execute(
            text('INSERT INTO "HistorialEstadoPedido" (id, pedido_id, estado, fecha) VALUES (:id, :pedido_id, \'cancelado\', NOW())'),
            {"id": str(uuid.uuid4()), "pedido_id": pedido_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelando pedido {pedido_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al cancelar el pedido")

    background_tasks.add_task(
        crear_notificacion, usuario.id, "pedido_cancelado",
        f"Tu pedido #{pedido_id[:8].upper()} fue cancelado", pedido_id, "pedido"
    )

    return MensajeResponse(mensaje="Pedido cancelado. El stock ha sido restaurado.")


# Helper para recalculado asíncrono de nivel de cliente
def _recalcular_nivel_usuario(supabase, usuario_id: str):
    """Calcula el total gastado en pedidos completados del usuario y actualiza su nivel"""
    try:
        # Sumar los totales de todos los pedidos 'entregado' del usuario
        res = supabase.table("Pedido").select("total").eq("usuario_id", usuario_id).eq("estado", "entregado").execute()
        pedidos = res.data or []
        total_gastado = sum(float(p["total"]) for p in pedidos)
        
        # Determinar el nivel
        if total_gastado >= 5000.0:
            nivel = "VIP"
        elif total_gastado >= 1000.0:
            nivel = "Frecuente"
        else:
            nivel = "Nuevo"
            
        # Actualizar la tabla Usuario
        supabase.table("Usuario").update({"nivel": nivel}).eq("id", usuario_id).execute()
        logger.info(f"Nivel del usuario {usuario_id} recalculado: {nivel} (Total: ${total_gastado})")
    except Exception as e:
        logger.error(f"Error recalculando nivel para usuario {usuario_id}: {e}")

