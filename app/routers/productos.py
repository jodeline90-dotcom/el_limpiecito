

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, UploadFile, File
from app.models.schemas import (
    ProductoCreate, ProductoUpdate, ProductoVisibilidadRequest,
    ProductoResponse, ProductoListResponse, MensajeResponse,
    ResenaCreate, ResenaResponse
)
from app.database import get_supabase
from app.dependencies import get_current_user, get_admin_user, get_optional_user, UsuarioActual
from app.config import get_settings
from loguru import logger
from typing import Optional
import uuid
import io

router = APIRouter(prefix="/productos", tags=["Productos"])
settings = get_settings()


def _construir_query_productos(supabase, filtros: dict):
    """Construye la query con filtros aplicados"""
    query = supabase.table("Producto").select(
        "*, Categoria(nombre)"
    ).eq("activo", True)

    if filtros.get("categoria"):
        # Buscar por nombre o id de categoría
        query = query.eq("categoria_id", filtros["categoria"])

    if filtros.get("precio_min") is not None:
        query = query.gte("precio", filtros["precio_min"])

    if filtros.get("precio_max") is not None:
        query = query.lte("precio", filtros["precio_max"])

    if filtros.get("busqueda"):
        termino = filtros["busqueda"]
        query = query.ilike("nombre", f"%{termino}%")

    # Ordenamiento
    orden = filtros.get("orden", "mas_nuevo")
    if orden == "precio_asc":
        query = query.order("precio", desc=False)
    elif orden == "precio_desc":
        query = query.order("precio", desc=True)
    elif orden == "nombre":
        query = query.order("nombre", desc=False)
    elif orden == "mas_vendido":
        query = query.order("contador_ventas", desc=True)
    else:  # mas_nuevo
        query = query.order("fecha_creacion", desc=True)

    return query


@router.get("", response_model=ProductoListResponse)
async def listar_productos(
    categoria: Optional[str] = Query(None),
    precio_min: Optional[float] = Query(None, ge=0),
    precio_max: Optional[float] = Query(None, ge=0),
    orden: Optional[str] = Query("mas_nuevo"),
    busqueda: Optional[str] = Query(None, max_length=100),
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    usuario: Optional[UsuarioActual] = Depends(get_optional_user),
):
    """
    Lista productos con filtros opcionales.
    Los admins también ven productos inactivos si se especifica.
    """
    supabase = get_supabase()
    filtros = {
        "categoria": categoria,
        "precio_min": precio_min,
        "precio_max": precio_max,
        "orden": orden,
        "busqueda": busqueda,
    }

    try:
        query = _construir_query_productos(supabase, filtros)

        # Paginación
        offset = (pagina - 1) * limite
        resultado = query.range(offset, offset + limite - 1).execute()

        # Total para paginación (query separado sin range)
        total_query = _construir_query_productos(supabase, filtros)
        total_res = total_query.execute()
        total = len(total_res.data or [])

        productos = []
        for p in (resultado.data or []):
            # Normalizar datos de categoría
            cat_nombre = None
            if isinstance(p.get("Categoria"), dict):
                cat_nombre = p["Categoria"].get("nombre")

            # Obtener imágenes del producto
            imagenes = _obtener_imagenes_producto(supabase, p["id"])
            promedio_estrellas, total_resenas = _calcular_rating_producto(supabase, p["id"])

            productos.append(ProductoResponse(
                **{k: v for k, v in p.items() if k != "Categoria"},
                categoria_nombre=cat_nombre,
                imagenes=imagenes,
                promedio_estrellas=promedio_estrellas,
                total_resenas=total_resenas,
            ))

        return ProductoListResponse(
            productos=productos,
            total=total,
            pagina=pagina,
            total_paginas=max(1, -(-total // limite)),  # ceil division
        )
    except Exception as e:
        logger.error(f"Error listando productos: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener productos")


@router.get("/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(
    producto_id: str,
    background_tasks: BackgroundTasks,
):
    """Obtiene detalle de un producto e incrementa su contador de visitas"""
    supabase = get_supabase()
    try:
        resultado = (
            supabase.table("Producto")
            .select("*, Categoria(nombre)")
            .eq("id", producto_id)
            .single()
            .execute()
        )
        if not resultado.data:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        p = resultado.data

        # Incrementar contador de visitas en background (no bloquea)
        background_tasks.add_task(_incrementar_visitas, producto_id)

        cat_nombre = None
        if isinstance(p.get("Categoria"), dict):
            cat_nombre = p["Categoria"].get("nombre")

        imagenes = _obtener_imagenes_producto(supabase, producto_id)
        promedio_estrellas, total_resenas = _calcular_rating_producto(supabase, producto_id)

        return ProductoResponse(
            **{k: v for k, v in p.items() if k != "Categoria"},
            categoria_nombre=cat_nombre,
            imagenes=imagenes,
            promedio_estrellas=promedio_estrellas,
            total_resenas=total_resenas,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo producto {producto_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener el producto")


async def _incrementar_visitas(producto_id: str):
    """Incrementa contador_visitas del producto (tarea de background)"""
    try:
        supabase = get_supabase()
        # RPC para incremento atómico
        supabase.rpc("incrementar_visitas_producto", {"p_id": producto_id}).execute()
    except Exception:
        pass  # No crítico


def _obtener_imagenes_producto(supabase, producto_id: str) -> list:
    """Obtiene URLs de imágenes del producto desde Supabase Storage"""
    try:
        archivos = supabase.storage.from_(settings.supabase_storage_bucket).list(f"productos/{producto_id}/")
        urls = []
        for archivo in (archivos or []):
            if archivo.get("name"):
                url = supabase.storage.from_(settings.supabase_storage_bucket).get_public_url(
                    f"productos/{producto_id}/{archivo['name']}"
                )
                urls.append(url)
        return urls
    except Exception:
        return []


def _calcular_rating_producto(supabase, producto_id: str) -> tuple[float, int]:
    """Retorna (promedio_estrellas, total_resenas) para un producto"""
    try:
        res = supabase.table("Resena").select("estrellas").eq("producto_id", producto_id).execute()
        datos = res.data or []
        total = len(datos)
        if total == 0:
            return 0.0, 0
        promedio = sum(item["estrellas"] for item in datos) / total
        return round(promedio, 1), total
    except Exception:
        return 0.0, 0


@router.post("", response_model=ProductoResponse, status_code=201)
async def crear_producto(
    datos: ProductoCreate,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Crea un nuevo producto (solo admins)"""
    supabase = get_supabase()
    try:
        # Verificar que la categoría existe
        cat = supabase.table("Categoria").select("id").eq("id", datos.categoria_id).execute()
        if not cat.data:
            raise HTTPException(status_code=400, detail="Categoría no encontrada")

        nuevo = supabase.table("Producto").insert({
            **datos.model_dump(exclude_none=True),
            "contador_visitas": 0,
            "contador_ventas": 0,
        }).execute()

        producto = nuevo.data[0]

        # Registrar en historial de precios
        supabase.table("HistorialPrecio").insert({
            "producto_id": producto["id"],
            "precio": float(datos.precio),
            "motivo": "Precio inicial",
        }).execute()

        logger.info(f"Producto creado: {producto['nombre']} por {admin.email}")
        return ProductoResponse(**producto, imagenes=[])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando producto: {e}")
        raise HTTPException(status_code=500, detail="Error al crear el producto")


@router.put("/{producto_id}", response_model=ProductoResponse)
async def actualizar_producto(
    producto_id: str,
    datos: ProductoUpdate,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Actualiza un producto (solo admins)"""
    supabase = get_supabase()
    try:
        # Verificar que existe
        existente = supabase.table("Producto").select("id, precio").eq("id", producto_id).single().execute()
        if not existente.data:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        cambios = datos.model_dump(exclude_none=True)
        if not cambios:
            raise HTTPException(status_code=400, detail="No hay cambios para aplicar")

        # Si cambia el precio, registrar en historial
        precio_anterior = existente.data.get("precio")
        if datos.precio and float(datos.precio) != float(precio_anterior):
            supabase.table("HistorialPrecio").insert({
                "producto_id": producto_id,
                "precio": float(datos.precio),
                "precio_anterior": float(precio_anterior),
                "motivo": f"Actualizado por {admin.email}",
            }).execute()

        resultado = (
            supabase.table("Producto")
            .update(cambios)
            .eq("id", producto_id)
            .execute()
        )
        producto = resultado.data[0]
        imagenes = _obtener_imagenes_producto(supabase, producto_id)

        logger.info(f"Producto {producto_id} actualizado por {admin.email}")
        return ProductoResponse(**producto, imagenes=imagenes)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando producto {producto_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar el producto")


@router.patch("/{producto_id}/visibilidad", response_model=MensajeResponse)
async def cambiar_visibilidad(
    producto_id: str,
    datos: ProductoVisibilidadRequest,
    admin: UsuarioActual = Depends(get_admin_user),
):
    """Oculta o muestra un producto (solo admins)"""
    supabase = get_supabase()
    try:
        supabase.table("Producto").update({"activo": datos.activo}).eq("id", producto_id).execute()
        accion = "mostrado" if datos.activo else "ocultado"
        logger.info(f"Producto {producto_id} {accion} por {admin.email}")
        return MensajeResponse(mensaje=f"Producto {accion} correctamente")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al cambiar visibilidad")


@router.post("/{producto_id}/imagenes", response_model=MensajeResponse)
async def subir_imagen(
    producto_id: str,
    imagen: UploadFile = File(...),
    admin: UsuarioActual = Depends(get_admin_user),
):
    """
    Sube una imagen del producto a Supabase Storage.
    Tipos permitidos: JPEG, PNG, WebP. Máximo 5MB.
    """
    # Validar tipo de archivo
    tipos_permitidos = {"image/jpeg", "image/png", "image/webp"}
    if imagen.content_type not in tipos_permitidos:
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes JPEG, PNG o WebP")

    # Validar tamaño (5MB)
    contenido = await imagen.read()
    if len(contenido) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB")

    supabase = get_supabase()
    try:
        # Nombre único para el archivo
        extension = imagen.filename.rsplit(".", 1)[-1].lower() if "." in imagen.filename else "jpg"
        nombre_archivo = f"productos/{producto_id}/{uuid.uuid4()}.{extension}"

        # Subir a Supabase Storage
        supabase.storage.from_(settings.supabase_storage_bucket).upload(
            nombre_archivo,
            contenido,
            {"content-type": imagen.content_type},
        )

        url_publica = supabase.storage.from_(settings.supabase_storage_bucket).get_public_url(nombre_archivo)
        logger.info(f"Imagen subida para producto {producto_id}: {url_publica}")

        return MensajeResponse(mensaje=f"Imagen subida correctamente: {url_publica}")
    except Exception as e:
        logger.error(f"Error subiendo imagen: {e}")
        raise HTTPException(status_code=500, detail="Error al subir la imagen")



@router.post("/{producto_id}/resenas", response_model=MensajeResponse)
async def crear_resena(
    producto_id: str,
    datos: ResenaCreate,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Registra o actualiza una reseña (comentario y estrellas) de un producto.
    Requiere que el usuario haya comprado el producto previamente.
    """
    supabase = get_supabase()
    
    # 1. Verificar si el producto existe
    prod = supabase.table("Producto").select("id").eq("id", producto_id).single().execute()
    if not prod.data:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
        
    # 2. Verificar compra del producto
    compra_verificada = False
    try:
        pedidos_res = supabase.table("Pedido").select("id").eq("usuario_id", usuario.id).in_("estado", ["confirmado", "en_preparacion", "enviado", "entregado"]).execute()
        pedido_ids = [p["id"] for p in (pedidos_res.data or [])]
        if pedido_ids:
            items_res = supabase.table("ItemPedido").select("id").in_("pedido_id", pedido_ids).eq("producto_id", producto_id).execute()
            if items_res.data:
                compra_verificada = True
    except Exception as e:
        logger.error(f"Error verificando compra para reseña: {e}")
        
    if not compra_verificada:
        raise HTTPException(
            status_code=403, 
            detail="Solo puedes calificar productos que hayas comprado y pagado en la tienda."
        )
        
    # 3. Insertar o actualizar la reseña
    try:
        supabase.table("Resena").insert({
            "usuario_id": usuario.id,
            "producto_id": producto_id,
            "estrellas": datos.estrellas,
            "comentario": datos.comentario,
        }).execute()
        return MensajeResponse(mensaje="Tu calificación ha sido publicada. ¡Gracias por tu opinión!")
    except Exception as e:
        if "duplicate key" in str(e) or "already exists" in str(e).lower():
            # Si ya existe, la actualizamos
            try:
                supabase.table("Resena").update({
                    "estrellas": datos.estrellas,
                    "comentario": datos.comentario,
                }).eq("usuario_id", usuario.id).eq("producto_id", producto_id).execute()
                return MensajeResponse(mensaje="Tu calificación ha sido actualizada correctamente.")
            except Exception as update_err:
                logger.error(f"Error actualizando reseña: {update_err}")
        logger.error(f"Error registrando reseña: {e}")
        raise HTTPException(status_code=500, detail="Error al publicar tu reseña.")


@router.get("/{producto_id}/resenas", response_model=list[ResenaResponse])
async def listar_resenas(
    producto_id: str,
    pagina: int = Query(1, ge=1),
    limite: int = Query(10, ge=1, le=50),
):
    """Lista las reseñas de un producto de forma paginada"""
    supabase = get_supabase()
    try:
        offset = (pagina - 1) * limite
        res = (
            supabase.table("Resena")
            .select("*, Usuario(nombre, foto_url)")
            .eq("producto_id", producto_id)
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
        logger.error(f"Error listando reseñas de producto {producto_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener reseñas.")



@router.get("/{producto_id}/relacionados", response_model=list[ProductoResponse])
async def obtener_productos_relacionados(
    producto_id: str,
    limite: int = Query(4, ge=1, le=10),
):
    """Obtiene productos relacionados de la misma categoría, excluyendo el producto actual"""
    supabase = get_supabase()
    try:
        # 1. Obtener la categoría del producto actual
        prod_res = supabase.table("Producto").select("categoria_id").eq("id", producto_id).single().execute()
        if not prod_res.data:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        categoria_id = prod_res.data["categoria_id"]
        
        # 2. Consultar productos relacionados
        res = (
            supabase.table("Producto")
            .select("*, Categoria(nombre)")
            .eq("categoria_id", categoria_id)
            .eq("activo", True)
            .neq("id", producto_id)
            .limit(limite)
            .execute()
        )
        
        relacionados = []
        for p in (res.data or []):
            cat_nombre = None
            if p.get("Categoria") and isinstance(p["Categoria"], dict):
                cat_nombre = p["Categoria"].get("nombre")
                
            imagenes = _obtener_imagenes_producto(supabase, p["id"])
            promedio_estrellas, total_resenas = _calcular_rating_producto(supabase, p["id"])
            
            relacionados.append(ProductoResponse(
                **{k: v for k, v in p.items() if k != "Categoria"},
                categoria_nombre=cat_nombre,
                imagenes=imagenes,
                promedio_estrellas=promedio_estrellas,
                total_resenas=total_resenas,
            ))
        return relacionados
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo productos relacionados para {producto_id}: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener productos relacionados.")

