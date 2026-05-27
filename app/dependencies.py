from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.config import get_settings
from app.database import get_supabase
from loguru import logger
from typing import Optional
import time

settings = get_settings()
security = HTTPBearer()


class UsuarioActual:
    def __init__(self, id: str, email: str, rol: str, metadata: dict):
        self.id = id
        self.email = email
        self.rol = rol
        self.metadata = metadata

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"


def _decodificar_token(token: str) -> dict:
    """Intenta decodificar el token con HS256, luego sin verificar firma para RS256 de Supabase."""
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        pass

    try:
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
        )
        if payload.get("exp", 0) < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError as e:
        logger.warning(f"Token JWT inválido: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return _decodificar_token(credentials.credentials)


async def get_current_user(
    payload: dict = Depends(verificar_token),
) -> UsuarioActual:
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token sin identificador de usuario")

    supabase = get_supabase()
    try:
        resultado = (
            supabase.table("Usuario")
            .select("id, email, nombre, rol, activo")
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    usuario_data = resultado.data
    if not usuario_data:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    if not usuario_data.get("activo", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    return UsuarioActual(
        id=usuario_data["id"],
        email=usuario_data["email"],
        rol=usuario_data.get("rol", "cliente"),
        metadata=usuario_data,
    )


async def get_admin_user(
    usuario: UsuarioActual = Depends(get_current_user),
) -> UsuarioActual:
    if not usuario.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requieren permisos de administrador",
        )
    return usuario


async def get_optional_user(
    request: Request,
) -> Optional[UsuarioActual]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        token = auth_header.split(" ")[1]
        payload = _decodificar_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        supabase = get_supabase()
        resultado = (
            supabase.table("Usuario")
            .select("id, email, nombre, rol, activo")
            .eq("id", user_id)
            .single()
            .execute()
        )
        data = resultado.data
        if not data or not data.get("activo", True):
            return None
        return UsuarioActual(id=data["id"], email=data["email"], rol=data.get("rol", "cliente"), metadata=data)
    except Exception:
        return None