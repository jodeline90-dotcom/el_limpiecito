

from fastapi import APIRouter, HTTPException, Request, Depends, status, BackgroundTasks
from app.models.schemas import (
    RegistroRequest, LoginRequest, RecuperarPasswordRequest,
    CambiarPasswordRequest, TokenResponse, MensajeResponse, UsuarioResponse
)
from app.database import get_supabase
from app.dependencies import get_current_user, UsuarioActual
from app.services.email_service import enviar_bienvenida, enviar_recuperacion_password
from app.services.notificacion_service import crear_notificacion
from app.config import get_settings
from loguru import logger
import passlib.hash
from datetime import datetime, timedelta
import uuid

router = APIRouter(prefix="/auth", tags=["Autenticación"])
settings = get_settings()


_intentos_login: dict = {}  # {"ip": {"intentos": 0, "reset_en": datetime}}


def _verificar_rate_limit(ip: str):
    """
    Verifica si la IP excedió el límite de intentos de login.
    Límite: 5 intentos cada 15 minutos.
    """
    ahora = datetime.utcnow()
    estado = _intentos_login.get(ip, {"intentos": 0, "reset_en": ahora + timedelta(minutes=settings.rate_limit_login_ventana_minutos)})

    # Resetear si venció la ventana
    if ahora > estado["reset_en"]:
        estado = {"intentos": 0, "reset_en": ahora + timedelta(minutes=settings.rate_limit_login_ventana_minutos)}

    if estado["intentos"] >= settings.rate_limit_login_intentos:
        segundos_restantes = int((estado["reset_en"] - ahora).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos fallidos. Intenta en {segundos_restantes} segundos.",
            headers={"Retry-After": str(segundos_restantes)},
        )
    return estado


def _registrar_intento_login(ip: str, exitoso: bool, email: str):
    """Registra intento de login en memoria y en BD"""
    ahora = datetime.utcnow()

    if exitoso:
        # Limpiar contador al lograr login exitoso
        _intentos_login.pop(ip, None)
    else:
        estado = _intentos_login.get(ip, {
            "intentos": 0,
            "reset_en": ahora + timedelta(minutes=settings.rate_limit_login_ventana_minutos)
        })
        estado["intentos"] += 1
        _intentos_login[ip] = estado

    # Guardar en tabla IntentoLogin (si existe en el schema)
    try:
        supabase = get_supabase()
        supabase.table("IntentoLogin").insert({
            "ip": ip,
            "email": email,
            "exitoso": exitoso,
            "fecha": ahora.isoformat(),
        }).execute()
    except Exception:
        pass  # No interrumpir el flujo si falla el log



@router.post("/registro", response_model=MensajeResponse, status_code=201)
async def registro(
    datos: RegistroRequest,
    background_tasks: BackgroundTasks,
):
    """
    Crea un nuevo usuario en Supabase Auth y en la tabla Usuario.
    Envía email de bienvenida en background.
    """
    supabase = get_supabase()

    # Verificar si el email ya existe
    existente = supabase.table("Usuario").select("id").eq("email", datos.email).execute()
    if existente.data:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    try:
        # Crear usuario en Supabase Auth
        auth_response = supabase.auth.admin.create_user({
            "email": datos.email,
            "password": datos.password,
            "email_confirm": True,  # Confirmar email automáticamente
            "user_metadata": {"nombre": datos.nombre},
        })
        user_id = auth_response.user.id

        # Crear registro en tabla Usuario
        supabase.table("Usuario").insert({
            "id": user_id,
            "nombre": datos.nombre,
            "email": datos.email,
            "telefono": datos.telefono,
            "rol": "cliente",
            "activo": True,
        }).execute()

        # Crear carrito vacío para el nuevo usuario
        supabase.table("Carrito").insert({
            "usuario_id": user_id,
        }).execute()

        # Email de bienvenida en background (no bloquea la respuesta)
        background_tasks.add_task(enviar_bienvenida, datos.email, datos.nombre)
        background_tasks.add_task(crear_notificacion, user_id, "bienvenida", f"¡Bienvenido a El Limpiecito, {datos.nombre}!")

        logger.info(f"✅ Nuevo usuario registrado: {datos.email}")
        return MensajeResponse(mensaje="Cuenta creada exitosamente. ¡Bienvenido!")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en registro: {e}")
        raise HTTPException(status_code=500, detail="Error al crear la cuenta")


@router.post("/login", response_model=TokenResponse)
async def login(
    datos: LoginRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Autentica usuario y devuelve JWT.
    Aplica rate limiting por IP: máx 5 intentos / 15 min.
    """
    ip = request.client.host if request.client else "unknown"

    # Verificar rate limit ANTES de intentar autenticar
    _verificar_rate_limit(ip)

    supabase = get_supabase()
    try:
        # Autenticar con Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": datos.email,
            "password": datos.password,
        })

        if not auth_response.user or not auth_response.session:
            raise Exception("Credenciales inválidas")

        # Registrar intento exitoso
        background_tasks.add_task(_registrar_intento_login, ip, True, datos.email)

        # Obtener datos del usuario para la respuesta
        usuario_data = (
            supabase.table("Usuario")
            .select("id, nombre, email, telefono, foto_url, rol, activo, fecha_creacion")
            .eq("id", auth_response.user.id)
            .single()
            .execute()
        ).data

        return TokenResponse(
            access_token=auth_response.session.access_token,
            token_type="bearer",
            expires_in=auth_response.session.expires_in or 3600,
            usuario=UsuarioResponse(**usuario_data),
        )

    except HTTPException:
        raise
    except Exception as e:
        # Registrar intento fallido
        background_tasks.add_task(_registrar_intento_login, ip, False, datos.email)
        logger.warning(f"Login fallido para {datos.email} desde {ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )


@router.post("/recuperar-password", response_model=MensajeResponse)
async def recuperar_password(
    datos: RecuperarPasswordRequest,
    background_tasks: BackgroundTasks,
):
    """
    Envía email para recuperar contraseña usando Supabase Auth + Resend.
    Siempre responde con éxito para no revelar qué emails existen.
    """
    supabase = get_supabase()
    try:
        # Verificar si el usuario existe
        usuario_res = (
            supabase.table("Usuario")
            .select("id, nombre, email")
            .eq("email", datos.email)
            .execute()
        )

        if usuario_res.data:
            usuario = usuario_res.data[0]
            # Generar link de recuperación con Supabase Auth
            link_response = supabase.auth.admin.generate_link({
                "type": "recovery",
                "email": datos.email,
                "options": {"redirect_to": f"{settings.frontend_url}/?vista=nueva-password"},
            })
            link = link_response.properties.action_link if link_response.properties else None

            if link:
                background_tasks.add_task(
                    enviar_recuperacion_password,
                    datos.email,
                    usuario["nombre"],
                    link,
                )

    except Exception as e:
        logger.error(f"Error en recuperar_password: {e}")

    # Siempre retornar éxito (seguridad: no revelar emails registrados)
    return MensajeResponse(
        mensaje="Si el correo está registrado, recibirás instrucciones en los próximos minutos."
    )


@router.put("/cambiar-password", response_model=MensajeResponse)
async def cambiar_password(
    datos: CambiarPasswordRequest,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Actualiza la contraseña del usuario autenticado.
    Verifica la contraseña actual antes de permitir el cambio.
    """
    supabase = get_supabase()
    try:
        # Verificar contraseña actual autenticando de nuevo
        supabase.auth.sign_in_with_password({
            "email": usuario.email,
            "password": datos.password_actual,
        })
    except Exception:
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")

    try:
        # Actualizar contraseña en Supabase Auth
        supabase.auth.admin.update_user_by_id(
            usuario.id,
            {"password": datos.password_nueva},
        )
        logger.info(f"Contraseña actualizada para usuario {usuario.email}")
        return MensajeResponse(mensaje="Contraseña actualizada correctamente")
    except Exception as e:
        logger.error(f"Error cambiando contraseña: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar la contraseña")
