

from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import (
    AgregarItemCarritoRequest, ActualizarItemCarritoRequest,
    AplicarCuponRequest, CarritoResponse, ItemCarritoResponse, MensajeResponse
)
from app.database import get_supabase
from app.dependencies import get_current_user, UsuarioActual
from loguru import logger
from decimal import Decimal
from datetime import datetime

router = APIRouter(prefix="/carrito", tags=["Carrito"])


def _obtener_o_crear_carrito(supabase, usuario_id: str) -> dict:
    """Obtiene el carrito del usuario o lo crea si no existe"""
    resultado = (
        supabase.table("Carrito")
        .select("*")
        .eq("usuario_id", usuario_id)
        .execute()
    )
    if resultado.data:
        return resultado.data[0]

    # Crear carrito si no existe
    nuevo = supabase.table("Carrito").insert({"usuario_id": usuario_id}).execute()
    return nuevo.data[0]


def _calcular_totales_carrito(items: list, descuento_porcentaje: int = 0, descuento_fijo: float = 0) -> dict:
    """Calcula subtotal, descuento y total del carrito"""
    subtotal = sum(Decimal(str(item["precio_unitario"])) * item["cantidad"] for item in items)
    descuento = Decimal("0.00")

    if descuento_porcentaje:
        descuento = subtotal * Decimal(str(descuento_porcentaje)) / 100

    if descuento_fijo:
        descuento = min(Decimal(str(descuento_fijo)), subtotal)  # No descontar más del subtotal

    total = max(Decimal("0.00"), subtotal - descuento)
    return {"subtotal": subtotal, "descuento": descuento, "total": total}


def _construir_respuesta_carrito(supabase, carrito: dict, items_raw: list) -> CarritoResponse:
    """Construye la respuesta completa del carrito con todos sus items"""
    items_respuesta = []
    for item in items_raw:
        producto = item.get("Producto", {}) or {}
        nombre = producto.get("nombre", "Producto")
        precio = Decimal(str(item.get("precio_unitario", 0)))
        cantidad = item.get("cantidad", 1)

        items_respuesta.append(ItemCarritoResponse(
            id=item["id"],
            producto_id=item["producto_id"],
            nombre_producto=nombre,
            imagen_url=None,  # TODO: obtener primera imagen de Supabase Storage
            precio_unitario=precio,
            cantidad=cantidad,
            subtotal=precio * cantidad,
        ))

    descuento_pct = carrito.get("cupon_descuento_porcentaje", 0) or 0
    descuento_fijo = float(carrito.get("cupon_descuento_fijo", 0) or 0)
    totales = _calcular_totales_carrito(items_raw, descuento_pct, descuento_fijo)

    return CarritoResponse(
        id=carrito["id"],
        items=items_respuesta,
        subtotal=totales["subtotal"],
        descuento=totales["descuento"],
        total=totales["total"],
        cupon_aplicado=carrito.get("cupon_codigo"),
        descuento_porcentaje=descuento_pct if descuento_pct else None,
    )


@router.get("", response_model=CarritoResponse)
async def obtener_carrito(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Obtiene el carrito completo del usuario autenticado"""
    supabase = get_supabase()
    carrito = _obtener_o_crear_carrito(supabase, usuario.id)

    items_res = (
        supabase.table("ItemCarrito")
        .select("*, Producto(nombre, precio, stock)")
        .eq("carrito_id", carrito["id"])
        .execute()
    )
    return _construir_respuesta_carrito(supabase, carrito, items_res.data or [])


@router.post("/items", response_model=CarritoResponse, status_code=201)
async def agregar_item(
    datos: AgregarItemCarritoRequest,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Agrega un producto al carrito.
    Valida stock disponible antes de agregar.
    Si el producto ya está en el carrito, suma la cantidad.
    """
    supabase = get_supabase()

    # Validar que el producto existe y tiene stock
    producto_res = (
        supabase.table("Producto")
        .select("id, nombre, precio, stock, activo")
        .eq("id", datos.producto_id)
        .single()
        .execute()
    )
    if not producto_res.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    producto = producto_res.data
    if not producto.get("activo", True):
        raise HTTPException(status_code=400, detail="Este producto no está disponible")

    if producto["stock"] < datos.cantidad:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente. Disponible: {producto['stock']} unidades"
        )

    carrito = _obtener_o_crear_carrito(supabase, usuario.id)

    # Verificar si ya está en el carrito
    item_existente = (
        supabase.table("ItemCarrito")
        .select("id, cantidad")
        .eq("carrito_id", carrito["id"])
        .eq("producto_id", datos.producto_id)
        .execute()
    )

    if item_existente.data:
        # Actualizar cantidad
        item = item_existente.data[0]
        nueva_cantidad = item["cantidad"] + datos.cantidad

        if nueva_cantidad > producto["stock"]:
            raise HTTPException(
                status_code=400,
                detail=f"No hay suficiente stock. Máximo disponible: {producto['stock']}"
            )

        supabase.table("ItemCarrito").update({"cantidad": nueva_cantidad}).eq("id", item["id"]).execute()
    else:
        # Agregar nuevo item
        supabase.table("ItemCarrito").insert({
            "carrito_id": carrito["id"],
            "producto_id": datos.producto_id,
            "cantidad": datos.cantidad,
            "precio_unitario": float(producto["precio"]),
        }).execute()

    # Retornar carrito actualizado
    items_res = (
        supabase.table("ItemCarrito")
        .select("*, Producto(nombre, precio, stock)")
        .eq("carrito_id", carrito["id"])
        .execute()
    )
    return _construir_respuesta_carrito(supabase, carrito, items_res.data or [])


@router.put("/items/{item_id}", response_model=CarritoResponse)
async def actualizar_item(
    item_id: str,
    datos: ActualizarItemCarritoRequest,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Actualiza la cantidad de un item en el carrito"""
    supabase = get_supabase()
    carrito = _obtener_o_crear_carrito(supabase, usuario.id)

    # Verificar que el item pertenece al carrito del usuario
    item_res = (
        supabase.table("ItemCarrito")
        .select("*, Producto(stock)")
        .eq("id", item_id)
        .eq("carrito_id", carrito["id"])
        .execute()
    )
    if not item_res.data:
        raise HTTPException(status_code=404, detail="Item no encontrado en tu carrito")

    item = item_res.data[0]
    stock_disponible = item.get("Producto", {}).get("stock", 0) if item.get("Producto") else 0

    if datos.cantidad > stock_disponible:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente. Disponible: {stock_disponible}"
        )

    supabase.table("ItemCarrito").update({"cantidad": datos.cantidad}).eq("id", item_id).execute()

    items_res = (
        supabase.table("ItemCarrito")
        .select("*, Producto(nombre, precio, stock)")
        .eq("carrito_id", carrito["id"])
        .execute()
    )
    return _construir_respuesta_carrito(supabase, carrito, items_res.data or [])


@router.delete("/items/{item_id}", response_model=MensajeResponse)
async def eliminar_item(
    item_id: str,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Elimina un item del carrito"""
    supabase = get_supabase()
    carrito = _obtener_o_crear_carrito(supabase, usuario.id)

    # Verificar que el item pertenece al carrito del usuario
    item_res = (
        supabase.table("ItemCarrito")
        .select("id")
        .eq("id", item_id)
        .eq("carrito_id", carrito["id"])
        .execute()
    )
    if not item_res.data:
        raise HTTPException(status_code=404, detail="Item no encontrado en tu carrito")

    supabase.table("ItemCarrito").delete().eq("id", item_id).execute()
    return MensajeResponse(mensaje="Producto eliminado del carrito")


@router.post("/cupon", response_model=CarritoResponse)
async def aplicar_cupon(
    datos: AplicarCuponRequest,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Valida y aplica un cupón de descuento al carrito.
    Verifica: existencia, vigencia, usos disponibles y monto mínimo.
    """
    supabase = get_supabase()

    # Buscar cupón
    cupon_res = (
        supabase.table("Cupon")
        .select("*")
        .eq("codigo", datos.codigo.upper())
        .eq("activo", True)
        .execute()
    )
    if not cupon_res.data:
        raise HTTPException(status_code=400, detail="Cupón inválido o inactivo")

    cupon = cupon_res.data[0]

    # Verificar fecha de vencimiento
    if cupon.get("fecha_vencimiento"):
        vencimiento = datetime.fromisoformat(cupon["fecha_vencimiento"].replace("Z", "+00:00"))
        if datetime.utcnow().replace(tzinfo=vencimiento.tzinfo) > vencimiento:
            raise HTTPException(status_code=400, detail="Este cupón ha vencido")

    # Verificar usos restantes
    if cupon.get("maximo_usos") and cupon.get("usos_actuales", 0) >= cupon["maximo_usos"]:
        raise HTTPException(status_code=400, detail="Este cupón ya no tiene usos disponibles")

    # Obtener carrito y verificar monto mínimo
    carrito = _obtener_o_crear_carrito(supabase, usuario.id)
    items_res = (
        supabase.table("ItemCarrito")
        .select("*, Producto(nombre, precio, stock)")
        .eq("carrito_id", carrito["id"])
        .execute()
    )
    items = items_res.data or []

    if not items:
        raise HTTPException(status_code=400, detail="Tu carrito está vacío")

    subtotal = sum(Decimal(str(i["precio_unitario"])) * i["cantidad"] for i in items)

    if cupon.get("monto_minimo") and subtotal < Decimal(str(cupon["monto_minimo"])):
        raise HTTPException(
            status_code=400,
            detail=f"El cupón requiere un mínimo de ${cupon['monto_minimo']:.2f} en tu carrito"
        )

    # Aplicar cupón al carrito
    supabase.table("Carrito").update({
        "cupon_codigo": cupon["codigo"],
        "cupon_descuento_porcentaje": cupon.get("descuento_porcentaje"),
        "cupon_descuento_fijo": cupon.get("descuento_fijo"),
    }).eq("id", carrito["id"]).execute()

    # Recargar carrito actualizado
    carrito_actualizado = supabase.table("Carrito").select("*").eq("id", carrito["id"]).single().execute().data
    return _construir_respuesta_carrito(supabase, carrito_actualizado, items)
