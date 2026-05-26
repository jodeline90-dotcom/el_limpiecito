

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.models.schemas import (
    CambiarEstadoPedidoRequest, CrearCuponRequest, CrearProveedorRequest,
    MensajeResponse, RegistroRequest, UsuarioResponse, ResenaResponse,
    NewsletterResponse
)
from app.database import get_supabase
from app.dependencies import get_admin_user, UsuarioActual
from app.services.email_service import enviar_confirmacion_pedido
from app.services.pdf_service import generar_factura
from loguru import logger
import csv
import io
from datetime import datetime
from typing import Optional, Literal
import uuid

router = APIRouter(prefix="/admin", tags=["Admin"])



@router.get("/pedidos")
async def listar_todos_pedidos(
    estado: Optional[str] = Query(None),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin: Optional[str] = Query(None),
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Lista todos los pedidos con filtros opcionales (solo admins)"""
    supabase = get_supabase()

    query = supabase.table("Pedido").select(
        "*, Usuario(nombre, email), Direccion(ciudad, estado)"
    )

    if estado:
        query = query.eq("estado", estado)
    if fecha_inicio:
        query = query.gte("fecha_creacion", fecha_inicio)
    if fecha_fin:
        query = query.lte("fecha_creacion", fecha_fin)

    offset = (pagina - 1) * limite
    resultado = query.order("fecha_creacion", desc=True).range(offset, offset + limite - 1).execute()

    return {
        "pedidos": resultado.data or [],
        "pagina": pagina,
        "total_pagina": len(resultado.data or []),
    }


@router.post("/pedidos/{pedido_id}/reenviar-comprobante", response_model=MensajeResponse)
async def reenviar_comprobante(
    pedido_id: str,
    background_tasks: BackgroundTasks,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Reenvía manualmente el correo de confirmación de pedido con su factura (solo admins)"""
    supabase = get_supabase()
    
    # Obtener pedido y usuario
    pedido_res = supabase.table("Pedido").select("*, Usuario(nombre, email)").eq("id", pedido_id).single().execute()
    if not pedido_res.data:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    pedido = pedido_res.data
    
    # Obtener items
    items_res = supabase.table("ItemPedido").select("*").eq("pedido_id", pedido_id).execute()
    items = items_res.data or []
    
    # Datos para el email
    email = pedido["Usuario"]["email"]
    nombre = pedido["Usuario"]["nombre"]
    total = float(pedido["total"])
    
    # Generar PDF
    try:
        pdf_bytes = await generar_factura(pedido_id)
    except Exception as e:
        logger.error(f"Error al generar PDF para reenvío: {e}")
        pdf_bytes = None
        
    # Enviar correo en background
    background_tasks.add_task(enviar_confirmacion_pedido, email, nombre, pedido_id, items, total, pdf_bytes)
    
    logger.info(f"Admin {admin.email} solicitó reenvío de comprobante para el pedido {pedido_id}")
    return MensajeResponse(mensaje="El comprobante ha sido puesto en cola para reenvío.")



@router.get("/clientes")
async def listar_clientes(
    busqueda: Optional[str] = Query(None),
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Lista todos los usuarios/clientes registrados"""
    supabase = get_supabase()

    query = supabase.table("Usuario").select(
        "id, nombre, email, telefono, rol, activo, fecha_creacion"
    ).eq("rol", "cliente")

    if busqueda:
        query = query.or_(f"nombre.ilike.%{busqueda}%,email.ilike.%{busqueda}%")

    offset = (pagina - 1) * limite
    resultado = query.order("fecha_creacion", desc=True).range(offset, offset + limite - 1).execute()

    return {"clientes": resultado.data or [], "pagina": pagina}


@router.patch("/clientes/{usuario_id}/estado", response_model=MensajeResponse)
async def cambiar_estado_cliente(
    usuario_id: str,
    activo: bool,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Activa o desactiva la cuenta de un cliente"""
    supabase = get_supabase()
    supabase.table("Usuario").update({"activo": activo}).eq("id", usuario_id).execute()
    accion = "activada" if activo else "desactivada"
    logger.info(f"Cuenta {usuario_id} {accion} por {admin.email}")
    return MensajeResponse(mensaje=f"Cuenta {accion} correctamente")



@router.get("/reportes/ventas")
async def reporte_ventas(
    fecha_inicio: str = Query(..., description="Formato: YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Formato: YYYY-MM-DD"),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """
    Reporte de ventas por período.
    Retorna totales y lista de pedidos confirmados/entregados en el rango de fechas.
    """
    supabase = get_supabase()

    # Pedidos en el período (solo confirmados y entregados = pagados)
    estados_pagados = ["confirmado", "en_preparacion", "enviado", "entregado"]
    pedidos_res = (
        supabase.table("Pedido")
        .select("id, total, subtotal, descuento, estado, fecha_creacion, Usuario(nombre, email)")
        .in_("estado", estados_pagados)
        .gte("fecha_creacion", f"{fecha_inicio}T00:00:00")
        .lte("fecha_creacion", f"{fecha_fin}T23:59:59")
        .order("fecha_creacion", desc=True)
        .execute()
    )
    pedidos = pedidos_res.data or []

    total_ventas = sum(float(p.get("total", 0)) for p in pedidos)
    total_descuentos = sum(float(p.get("descuento", 0)) for p in pedidos)

    return {
        "periodo": {"inicio": fecha_inicio, "fin": fecha_fin},
        "resumen": {
            "total_pedidos": len(pedidos),
            "total_ventas": round(total_ventas, 2),
            "total_descuentos": round(total_descuentos, 2),
            "promedio_pedido": round(total_ventas / len(pedidos), 2) if pedidos else 0,
        },
        "pedidos": pedidos,
    }



@router.get("/inventario")
async def ver_inventario(
    alerta_stock_bajo: bool = Query(False, description="Filtrar solo productos con stock bajo"),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """
    Vista de inventario con stock de todos los productos.
    Con alerta_stock_bajo=True, filtra solo los productos por debajo del stock mínimo.
    """
    supabase = get_supabase()

    query = supabase.table("Producto").select(
        "id, nombre, sku, stock, stock_minimo, precio, activo, Categoria(nombre)"
    )

    resultado = query.order("stock", desc=False).execute()
    productos = resultado.data or []

    if alerta_stock_bajo:
        productos = [p for p in productos if p["stock"] <= p.get("stock_minimo", 5)]

    return {
        "productos": productos,
        "total": len(productos),
        "con_stock_bajo": len([p for p in productos if p["stock"] <= p.get("stock_minimo", 5)]),
        "sin_stock": len([p for p in productos if p["stock"] == 0]),
    }



@router.post("/cupones", status_code=201)
async def crear_cupon(
    datos: CrearCuponRequest,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Crea un nuevo cupón de descuento"""
    supabase = get_supabase()

    # Verificar que el código no exista
    existente = supabase.table("Cupon").select("id").eq("codigo", datos.codigo.upper()).execute()
    if existente.data:
        raise HTTPException(status_code=400, detail=f"El código '{datos.codigo}' ya existe")

    nuevo = supabase.table("Cupon").insert({
        **datos.model_dump(exclude_none=True),
        "codigo": datos.codigo.upper(),
        "usos_actuales": 0,
        "creado_por": admin.id,
    }).execute()

    logger.info(f"Cupón '{datos.codigo}' creado por {admin.email}")
    return nuevo.data[0]


@router.get("/cupones")
async def listar_cupones(
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Lista todos los cupones creados"""
    supabase = get_supabase()
    res = supabase.table("Cupon").select("*").order("fecha_creacion", desc=True).execute()
    return res.data or []


@router.patch("/cupones/{cupon_id}/estado", response_model=MensajeResponse)
async def cambiar_estado_cupon(
    cupon_id: str,
    activo: bool,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Activa o desactiva un cupón"""
    supabase = get_supabase()
    supabase.table("Cupon").update({"activo": activo}).eq("id", cupon_id).execute()
    return MensajeResponse(mensaje=f"Cupón {'activado' if activo else 'desactivado'}")



@router.post("/proveedores", status_code=201)
async def crear_proveedor(
    datos: CrearProveedorRequest,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Registra un nuevo proveedor"""
    supabase = get_supabase()
    nuevo = supabase.table("Proveedor").insert(datos.model_dump(exclude_none=True)).execute()
    logger.info(f"Proveedor '{datos.nombre}' registrado por {admin.email}")
    return nuevo.data[0]


@router.get("/proveedores")
async def listar_proveedores(
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Lista todos los proveedores"""
    supabase = get_supabase()
    res = supabase.table("Proveedor").select("*").order("nombre").execute()
    return res.data or []



@router.get("/dashboard")
async def dashboard(
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Resumen ejecutivo del negocio para el dashboard de administración"""
    supabase = get_supabase()

    # Pedidos del día de hoy
    hoy = datetime.utcnow().strftime("%Y-%m-%d")
    pedidos_hoy = (
        supabase.table("Pedido")
        .select("id, total")
        .gte("fecha_creacion", f"{hoy}T00:00:00")
        .in_("estado", ["confirmado", "en_preparacion", "enviado", "entregado"])
        .execute()
    )

    # Productos con stock bajo
    stock_bajo = (
        supabase.table("Producto")
        .select("id", count="exact")
        .filter("stock", "lte", "stock_minimo")
        .eq("activo", True)
        .execute()
    )

    # Pedidos pendientes
    pendientes = (
        supabase.table("Pedido")
        .select("id", count="exact")
        .eq("estado", "pendiente")
        .execute()
    )

    # Total clientes
    clientes = (
        supabase.table("Usuario")
        .select("id", count="exact")
        .eq("rol", "cliente")
        .execute()
    )

    ventas_hoy = sum(float(p.get("total", 0)) for p in (pedidos_hoy.data or []))

    return {
        "ventas_hoy": {
            "monto": round(ventas_hoy, 2),
            "pedidos": len(pedidos_hoy.data or []),
        },
        "pedidos_pendientes": pendientes.count or 0,
        "productos_stock_bajo": stock_bajo.count or 0,
        "total_clientes": clientes.count or 0,
    }



@router.get("/equipo", response_model=list[UsuarioResponse])
async def listar_equipo(admin: UsuarioActual = Depends(get_admin_user)):
    """Lista todos los administradores del sistema"""
    supabase = get_supabase()
    res = supabase.table("Usuario").select("*").eq("rol", "admin").order("nombre").execute()
    return res.data or []


@router.post("/equipo", response_model=MensajeResponse, status_code=201)
async def crear_administrador(
    datos: RegistroRequest,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Crea una nueva cuenta con rol de administrador"""
    supabase = get_supabase()
    
    # Verificar si el email ya existe
    existente = supabase.table("Usuario").select("id").eq("email", datos.email).execute()
    if existente.data:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
        
    try:
        # Crear en Supabase Auth
        auth_response = supabase.auth.admin.create_user({
            "email": datos.email,
            "password": datos.password,
            "email_confirm": True,
            "user_metadata": {"nombre": datos.nombre},
        })
        user_id = auth_response.user.id
        
        # Insertar como admin en tabla
        supabase.table("Usuario").insert({
            "id": user_id,
            "nombre": datos.nombre,
            "email": datos.email,
            "telefono": datos.telefono,
            "rol": "admin",
            "activo": True,
        }).execute()
        
        logger.info(f"Nuevo administrador {datos.email} creado por {admin.email}")
        return MensajeResponse(mensaje="Administrador creado exitosamente.")
    except Exception as e:
        logger.error(f"Error creando administrador: {e}")
        raise HTTPException(status_code=500, detail="Error al crear administrador")


@router.delete("/equipo/{admin_id}", response_model=MensajeResponse)
async def remover_administrador(
    admin_id: str,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Quita los privilegios de administrador a un usuario (lo vuelve cliente y desactiva)"""
    if admin_id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes revocar tus propios privilegios")
        
    supabase = get_supabase()
    try:
        supabase.table("Usuario").update({
            "rol": "cliente",
            "activo": False
        }).eq("id", admin_id).execute()
        
        logger.info(f"Privilegios revocados para el usuario {admin_id} por {admin.email}")
        return MensajeResponse(mensaje="Privilegios de administrador revocados exitosamente.")
    except Exception as e:
        logger.error(f"Error revocando admin: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar la solicitud")



@router.get("/resenas", response_model=list[ResenaResponse])
async def listar_todas_resenas(
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Lista todas las opiniones emitidas en la plataforma para moderación"""
    supabase = get_supabase()
    try:
        offset = (pagina - 1) * limite
        res = (
            supabase.table("Resena")
            .select("*, Usuario(nombre, foto_url)")
            .order("fecha_creacion", desc=True)
            .range(offset, offset + limite - 1)
            .execute()
        )
        
        resenas = []
        for r in (res.data or []):
            nombre = "Cliente de El Limpiecito"
            foto = None
            if r.get("Usuario") and isinstance(r["Usuario"], dict):
                nombre = r["Usuario"].get("nombre") or nombre
                foto = r["Usuario"].get("foto_url")
                
            resenas.append(ResenaResponse(
                id=r["id"],
                usuario_id=r["usuario_id"],
                usuario_nombre=nombre,
                usuario_foto=foto,
                producto_id=r["producto_id"],
                estrellas=r["estrellas"],
                comentario=r["comentario"],
                fecha_creacion=r["fecha_creacion"],
            ))
        return resenas
    except Exception as e:
        logger.error(f"Error listando reseñas global para admin: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener reseñas global.")


@router.delete("/resenas/{resena_id}", response_model=MensajeResponse)
async def borrar_resena(
    resena_id: str,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Elimina una reseña de forma permanente (moderación de spam o acoso)"""
    supabase = get_supabase()
    try:
        # Verificar si la reseña existe
        existente = supabase.table("Resena").select("id").eq("id", resena_id).execute()
        if not existente.data:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
            
        supabase.table("Resena").delete().eq("id", resena_id).execute()
        logger.info(f"Reseña {resena_id} eliminada por el administrador {admin.email}")
        return MensajeResponse(mensaje="La reseña ha sido eliminada permanentemente por moderación.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando reseña {resena_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar la reseña.")



@router.get("/reportes/ventas/exportar")
async def exportar_ventas_csv(
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin: Optional[str] = Query(None),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Exporta el historial de ventas filtrado por fechas en formato CSV para Excel"""
    supabase = get_supabase()
    try:
        # Construir query de pedidos
        query = supabase.table("Pedido").select("id, usuario_id, total, costo_envio, estado, fecha_creacion, Usuario(email, nombre)")
        
        # Filtros opcionales de fechas
        if fecha_inicio:
            query = query.gte("fecha_creacion", fecha_inicio)
        if fecha_fin:
            query = query.lte("fecha_creacion", fecha_fin)
            
        res = query.order("fecha_creacion", desc=True).execute()
        pedidos = res.data or []
        
        # Generar CSV en memoria
        output = io.StringIO()
        # Agregar UTF-8 BOM para que Excel detecte acentos correctamente en español
        output.write('\ufeff')
        
        writer = csv.writer(output, delimiter=';')
        # Escribir encabezado
        writer.writerow([
            "ID Pedido", "Fecha", "Cliente Correo", "Cliente Nombre", 
            "Costo Envío", "Total de Venta", "Estado"
        ])
        
        for p in pedidos:
            u = p.get("Usuario") or {}
            email = u.get("email", "Desconocido/Eliminado")
            nombre = u.get("nombre", "Cliente")
            
            # Formatear fecha
            fecha_str = p["fecha_creacion"]
            try:
                dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                fecha_formateada = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                fecha_formateada = fecha_str
                
            writer.writerow([
                p["id"],
                fecha_formateada,
                email,
                nombre,
                f"${p['costo_envio']}",
                f"${p['total']}",
                p["estado"]
            ])
            
        # Posicionar puntero de StringIO al inicio
        output.seek(0)
        
        # Streaming response
        headers = {
            "Content-Disposition": 'attachment; filename="reporte_ventas.csv"'
        }
        return StreamingResponse(
            iter([output.getvalue()]), 
            media_type="text/csv; charset=utf-8", 
            headers=headers
        )
    except Exception as e:
        logger.error(f"Error exportando ventas a CSV: {e}")
        raise HTTPException(status_code=500, detail="Error al generar el reporte CSV.")



@router.get("/newsletter", response_model=list[NewsletterResponse])
async def listar_newsletter(
    pagina: int = Query(1, ge=1),
    limite: int = Query(50, ge=1, le=100),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Lista todos los correos electrónicos inscritos en el boletín informativo"""
    supabase = get_supabase()
    try:
        offset = (pagina - 1) * limite
        res = (
            supabase.table("Newsletter")
            .select("*")
            .order("fecha_registro", desc=True)
            .range(offset, offset + limite - 1)
            .execute()
        )
        return [NewsletterResponse(**n) for n in (res.data or [])]
    except Exception as e:
        logger.error(f"Error listando correos de newsletter: {e}")
        raise HTTPException(status_code=500, detail="Error al listar suscriptores.")



@router.post("/usuarios/recalcular-niveles", response_model=MensajeResponse)
async def recalcular_niveles_masivo(
    admin: UsuarioActual = Depends(get_admin_user),
):
    """
    Recalcula masivamente el nivel de lealtad de todos los clientes
    basándose en la sumatoria de sus compras entregadas.
    """
    supabase = get_supabase()
    try:
        # 1. Obtener todos los usuarios con rol de cliente
        clientes_res = supabase.table("Usuario").select("id, nombre, email").eq("rol", "cliente").execute()
        clientes = clientes_res.data or []
        
        actualizados = 0
        for c in clientes:
            uid = c["id"]
            # Sumar compras con estado entregado
            pedidos_res = supabase.table("Pedido").select("total").eq("usuario_id", uid).eq("estado", "entregado").execute()
            total_gastado = sum(float(p["total"]) for p in (pedidos_res.data or []))
            
            # Clasificar
            if total_gastado >= 5000.0:
                nivel = "VIP"
            elif total_gastado >= 1000.0:
                nivel = "Frecuente"
            else:
                nivel = "Nuevo"
                
            # Actualizar
            supabase.table("Usuario").update({"nivel": nivel}).eq("id", uid).execute()
            actualizados += 1
            
        logger.info(f"Recálculo masivo de niveles finalizado por {admin.email}. {actualizados} usuarios actualizados.")
        return MensajeResponse(mensaje=f"Se recalcularon y actualizaron los niveles de {actualizados} clientes.")
    except Exception as e:
        logger.error(f"Error en recálculo masivo de niveles: {e}")
        raise HTTPException(status_code=500, detail="Error al recalcular niveles de clientes.")
