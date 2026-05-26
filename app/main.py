

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from loguru import logger
import sys
import time

from app.config import get_settings
from app.database import verificar_conexion_supabase, verificar_conexion_db

# Importar todos los routers
from app.routers import auth, productos, carrito, pedidos, pagos, usuarios, admin

settings = get_settings()


logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if not settings.es_produccion else "INFO",
)
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
    level="INFO",
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Eventos de arranque y cierre de la aplicación.
    Al iniciar: verifica conexiones a BD.
    Al cerrar: limpieza si es necesario.
    """
    logger.info("[START] Iniciando El Limpiecito API...")
    logger.info(f"   Entorno: {settings.app_env}")
    logger.info(f"   CORS permitido desde: {settings.cors_origins_list}")

    # Verificar conexiones al arrancar
    supabase_ok = await verificar_conexion_supabase()
    postgres_ok = await verificar_conexion_db()

    if not supabase_ok or not postgres_ok:
        logger.warning("[WARN] La app inició pero hay problemas de conexión con la BD")
    else:
        logger.info("[SUCCESS] El Limpiecito API lista para recibir peticiones")

    yield  # La app está corriendo aquí

    logger.info("[STOP] Cerrando El Limpiecito API...")



app = FastAPI(
    title="El Limpiecito API",
    description="Backend para la tienda de productos de limpieza 'El Limpiecito'",
    version="1.0.0",
    docs_url="/docs" if not settings.es_produccion else None,   # Ocultar docs en prod
    redoc_url="/redoc" if not settings.es_produccion else None,
    lifespan=lifespan,
)




app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)



@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Registra todas las peticiones HTTP con su tiempo de respuesta"""
    inicio = time.time()
    response = await call_next(request)
    duracion = round((time.time() - inicio) * 1000, 2)

    # NO loggear el health check para no saturar los logs
    if request.url.path != "/health":
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duracion}ms)"
        )
    return response



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formatea los errores de validación de Pydantic de forma amigable"""
    errores = []
    for error in exc.errors():
        campo = " → ".join(str(loc) for loc in error["loc"] if loc != "body")
        errores.append(f"{campo}: {error['msg']}" if campo else error["msg"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Error de validación en los datos enviados",
            "errores": errores,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Captura errores no manejados y devuelve respuesta genérica"""
    logger.error(f"Error no controlado en {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor. Por favor intenta más tarde."},
    )



app.include_router(auth.router)
app.include_router(productos.router)
app.include_router(carrito.router)
app.include_router(pedidos.router)
app.include_router(pagos.router)
app.include_router(usuarios.router)
app.include_router(admin.router)



@app.get("/", tags=["Root"])
async def root():
    """Endpoint raíz: confirma que la API está funcionando"""
    return {
        "mensaje": "🧹 El Limpiecito API funcionando",
        "version": "1.0.0",
        "docs": "/docs",
        "entorno": settings.app_env,
    }


@app.get("/health", tags=["Root"])
async def health_check():
    """Health check para Railway y monitoreo"""
    supabase_ok = await verificar_conexion_supabase()
    return {
        "status": "ok" if supabase_ok else "degradado",
        "supabase": "conectado" if supabase_ok else "error",
        "version": "1.0.0",
    }
