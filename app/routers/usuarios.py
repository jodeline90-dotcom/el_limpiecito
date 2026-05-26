

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from app.models.schemas import (
    UsuarioResponse, ActualizarPerfilRequest,
    DireccionCreate, DireccionResponse, MensajeResponse, CoberturaResponse,
    FavoritoCreate, FavoritoResponse, ProductoResponse, NewsletterSubscriptionRequest
)
from app.database import get_supabase
from app.dependencies import get_current_user, UsuarioActual
from app.config import get_settings
from loguru import logger
import uuid

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])
settings = get_settings()

MAXIMO_DIRECCIONES = 5



@router.get("/perfil", response_model=UsuarioResponse)
async def obtener_perfil(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Retorna los datos del perfil del usuario autenticado"""
    supabase = get_supabase()
    res = (
        supabase.table("Usuario")
        .select("id, nombre, email, telefono, foto_url, rol, activo, fecha_creacion")
        .eq("id", usuario.id)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UsuarioResponse(**res.data)


@router.put("/perfil", response_model=UsuarioResponse)
async def actualizar_perfil(
    datos: ActualizarPerfilRequest,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Actualiza nombre y teléfono del perfil"""
    supabase = get_supabase()
    cambios = datos.model_dump(exclude_none=True)

    if not cambios:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    res = (
        supabase.table("Usuario")
        .update(cambios)
        .eq("id", usuario.id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=500, detail="Error al actualizar perfil")

    return UsuarioResponse(**res.data[0])


@router.post("/perfil/foto", response_model=MensajeResponse)
async def subir_foto_perfil(
    foto: UploadFile = File(...),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Sube la foto de perfil del usuario a Supabase Storage"""
    tipos_permitidos = {"image/jpeg", "image/png", "image/webp"}
    if foto.content_type not in tipos_permitidos:
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes JPEG, PNG o WebP")

    contenido = await foto.read()
    if len(contenido) > 2 * 1024 * 1024:  # 2MB máximo para fotos de perfil
        raise HTTPException(status_code=400, detail="La foto no puede superar 2MB")

    supabase = get_supabase()
    extension = foto.filename.rsplit(".", 1)[-1].lower() if "." in foto.filename else "jpg"
    ruta = f"avatars/{usuario.id}.{extension}"

    try:
        # Subir (upsert para sobreescribir si ya existe)
        supabase.storage.from_("avatars").upload(
            ruta, contenido, {"content-type": foto.content_type, "upsert": "true"}
        )
        url_publica = supabase.storage.from_("avatars").get_public_url(ruta)

        # Guardar URL en el perfil
        supabase.table("Usuario").update({"foto_url": url_publica}).eq("id", usuario.id).execute()

        return MensajeResponse(mensaje=f"Foto de perfil actualizada: {url_publica}")
    except Exception as e:
        logger.error(f"Error subiendo foto de perfil para {usuario.email}: {e}")
        raise HTTPException(status_code=500, detail="Error al subir la foto")



@router.get("/direcciones", response_model=list[DireccionResponse])
async def listar_direcciones(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Lista todas las direcciones del usuario"""
    supabase = get_supabase()
    res = (
        supabase.table("Direccion")
        .select("*")
        .eq("usuario_id", usuario.id)
        .order("es_predeterminada", desc=True)
        .execute()
    )
    return [DireccionResponse(**d) for d in (res.data or [])]


@router.post("/direcciones", response_model=DireccionResponse, status_code=201)
async def agregar_direccion(
    datos: DireccionCreate,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Agrega una dirección de envío.
    Límite: máximo 5 direcciones por usuario.
    """
    supabase = get_supabase()

    # Verificar límite de 5 direcciones
    conteo = (
        supabase.table("Direccion")
        .select("id", count="exact")
        .eq("usuario_id", usuario.id)
        .execute()
    )
    if (conteo.count or 0) >= MAXIMO_DIRECCIONES:
        raise HTTPException(
            status_code=400,
            detail=f"No puedes agregar más de {MAXIMO_DIRECCIONES} direcciones"
        )

    # Si la nueva dirección es predeterminada, quitar predeterminada anterior
    if datos.es_predeterminada:
        supabase.table("Direccion").update({"es_predeterminada": False}).eq("usuario_id", usuario.id).execute()

    nueva = supabase.table("Direccion").insert({
        **datos.model_dump(),
        "usuario_id": usuario.id,
    }).execute()

    if not nueva.data:
        raise HTTPException(status_code=500, detail="Error al guardar la dirección")

    return DireccionResponse(**nueva.data[0])


@router.delete("/direcciones/{direccion_id}", response_model=MensajeResponse)
async def eliminar_direccion(
    direccion_id: str,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Elimina una dirección del usuario"""
    supabase = get_supabase()

    # Verificar que la dirección pertenece al usuario
    res = (
        supabase.table("Direccion")
        .select("id, es_predeterminada")
        .eq("id", direccion_id)
        .eq("usuario_id", usuario.id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")

    supabase.table("Direccion").delete().eq("id", direccion_id).execute()
    return MensajeResponse(mensaje="Dirección eliminada correctamente")



@router.get("/notificaciones")
async def listar_notificaciones(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Lista las últimas 20 notificaciones del usuario"""
    supabase = get_supabase()
    res = (
        supabase.table("Notificacion")
        .select("*")
        .eq("usuario_id", usuario.id)
        .order("fecha_creacion", desc=True)
        .limit(20)
        .execute()
    )
    return res.data or []


@router.patch("/notificaciones/leer", response_model=MensajeResponse)
async def marcar_notificaciones_leidas(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Marca todas las notificaciones del usuario como leídas"""
    supabase = get_supabase()
    supabase.table("Notificacion").update({"leida": True}).eq("usuario_id", usuario.id).eq("leida", False).execute()
    return MensajeResponse(mensaje="Notificaciones marcadas como leídas")


@router.get("/cobertura", response_model=list[CoberturaResponse])
async def obtener_cobertura():
    """Retorna la lista de colonias y costos de envío en Jerez de García Salinas"""
    supabase = get_supabase()
    res = (
        supabase.table("CoberturaJerez")
        .select("*")
        .eq("activo", True)
        .order("colonia", desc=False)
        .execute()
    )
    return [CoberturaResponse(**c) for c in (res.data or [])]


@router.delete("/cuenta", response_model=MensajeResponse)
async def eliminar_cuenta(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Desactiva y anonimiza la cuenta del usuario para mantener la integridad de los reportes de ventas.
    """
    supabase = get_supabase()
    try:
        # Anonimizar en la base de datos pública
        supabase.table("Usuario").update({
            "activo": False,
            "nombre": "Cuenta Eliminada",
            "telefono": None,
            "foto_url": None
        }).eq("id", usuario.id).execute()

        # Desactivar login cambiando el email en Supabase Auth y añadiendo un sufijo aleatorio
        # Se requiere acceso al admin de Auth (el cliente supabase del backend usa el service_role)
        nuevo_email_anonimo = f"eliminado_{usuario.id.replace('-', '')}@ellimpiecito.local"
        supabase.auth.admin.update_user_by_id(
            usuario.id,
            {"email": nuevo_email_anonimo}
        )

        logger.info(f"Cuenta {usuario.id} anonimizada y eliminada por el usuario.")
        return MensajeResponse(mensaje="Tu cuenta ha sido eliminada exitosamente.")
    except Exception as e:
        logger.error(f"Error al eliminar cuenta {usuario.id}: {e}")
        raise HTTPException(status_code=500, detail="Error al intentar eliminar la cuenta.")


# Helper para obtener imágenes del producto localmente en favoritos
def _obtener_imagenes_producto_local(supabase, producto_id: str) -> list:
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



@router.get("/favoritos", response_model=list[FavoritoResponse])
async def listar_favoritos(
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Lista todos los productos guardados como favoritos por el usuario"""
    supabase = get_supabase()
    try:
        res = (
            supabase.table("Favorito")
            .select("*, Producto(*, Categoria(nombre))")
            .eq("usuario_id", usuario.id)
            .order("fecha_agregado", desc=True)
            .execute()
        )
        
        favoritos = []
        for item in (res.data or []):
            p = item.get("Producto")
            if not p:
                continue
                
            cat_nombre = None
            if p.get("Categoria") and isinstance(p["Categoria"], dict):
                cat_nombre = p["Categoria"].get("nombre")
                
            # Obtener imágenes
            imagenes = _obtener_imagenes_producto_local(supabase, p["id"])
            
            # Promedio de estrellas
            resenas_res = supabase.table("Resena").select("estrellas").eq("producto_id", p["id"]).execute()
            resenas = resenas_res.data or []
            total_resenas = len(resenas)
            promedio_estrellas = (
                sum(r["estrellas"] for r in resenas) / total_resenas if total_resenas > 0 else 0.0
            )
            
            producto_resp = ProductoResponse(
                **{k: v for k, v in p.items() if k != "Categoria"},
                categoria_nombre=cat_nombre,
                imagenes=imagenes,
                promedio_estrellas=promedio_estrellas,
                total_resenas=total_resenas,
            )
            
            favoritos.append(FavoritoResponse(
                id=item["id"],
                usuario_id=item["usuario_id"],
                producto_id=item["producto_id"],
                fecha_agregado=item["fecha_agregado"],
                producto=producto_resp,
            ))
            
        return favoritos
    except Exception as e:
        logger.error(f"Error listando favoritos de {usuario.id}: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener favoritos.")


@router.post("/favoritos", response_model=MensajeResponse)
async def agregar_favorito(
    datos: FavoritoCreate,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Agrega un producto a favoritos (o lo ignora si ya existe)"""
    supabase = get_supabase()
    try:
        # Verificar que el producto existe
        prod = supabase.table("Producto").select("id").eq("id", datos.producto_id).single().execute()
        if not prod.data:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
            
        # Intentar insertar
        supabase.table("Favorito").insert({
            "usuario_id": usuario.id,
            "producto_id": datos.producto_id,
        }).execute()
        
        return MensajeResponse(mensaje="Producto agregado a favoritos correctamente.")
    except Exception as e:
        # Si ya existe por el constraint UNIQUE, devolvemos éxito silencioso
        if "duplicate key" in str(e) or "already exists" in str(e).lower():
            return MensajeResponse(mensaje="El producto ya está en tus favoritos.")
        logger.error(f"Error agregando favorito {datos.producto_id} para {usuario.id}: {e}")
        raise HTTPException(status_code=500, detail="Error al agregar a favoritos.")


@router.delete("/favoritos/{producto_id}", response_model=MensajeResponse)
async def eliminar_favorito(
    producto_id: str,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Elimina un producto de los favoritos del usuario"""
    supabase = get_supabase()
    try:
        supabase.table("Favorito").delete().eq("usuario_id", usuario.id).eq("producto_id", producto_id).execute()
        return MensajeResponse(mensaje="Producto eliminado de favoritos correctamente.")
    except Exception as e:
        logger.error(f"Error eliminando favorito {producto_id} para {usuario.id}: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar de favoritos.")



@router.post("/newsletter/suscribir", response_model=MensajeResponse)
async def suscribir_newsletter(
    datos: NewsletterSubscriptionRequest,
):
    """Suscribe un correo electrónico al boletín informativo (boletín público)"""
    supabase = get_supabase()
    try:
        supabase.table("Newsletter").insert({
            "email": datos.email,
        }).execute()
        return MensajeResponse(mensaje="¡Gracias por suscribirte a nuestro boletín!")
    except Exception as e:
        if "duplicate key" in str(e) or "already exists" in str(e).lower():
            return MensajeResponse(mensaje="Este correo electrónico ya se encuentra registrado en nuestro boletín.")
        logger.error(f"Error registrando newsletter para {datos.email}: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar la suscripción.")


