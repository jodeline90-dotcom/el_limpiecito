# 🧹 El Limpiecito — Backend API

Backend completo en **FastAPI + Supabase** para la tienda de productos de limpieza "El Limpiecito".

---

## 📁 Estructura del proyecto

```
el_limpiecito/
├── app/
│   ├── main.py                  # Punto de entrada, CORS, middleware, lifespan
│   ├── config.py                # Configuración centralizada (pydantic-settings)
│   ├── database.py              # Conexiones Supabase + SQLAlchemy
│   ├── dependencies.py          # get_current_user, get_admin_user
│   ├── routers/
│   │   ├── auth.py              # POST /auth/registro, /login, /recuperar-password, /cambiar-password
│   │   ├── productos.py         # GET/POST/PUT/PATCH /productos
│   │   ├── carrito.py           # GET/POST/PUT/DELETE /carrito
│   │   ├── pedidos.py           # POST /pedidos (transacción atómica)
│   │   ├── pagos.py             # Stripe PaymentIntent + Webhook
│   │   ├── usuarios.py          # Perfil, foto, direcciones
│   │   └── admin.py             # Dashboard, reportes, cupones, proveedores
│   ├── models/
│   │   └── schemas.py           # Todos los schemas Pydantic v2
│   ├── services/
│   │   ├── email_service.py     # Resend — bienvenida, recuperación, confirmación
│   │   ├── pdf_service.py       # WeasyPrint — generación de facturas PDF
│   │   ├── stock_service.py     # Actualización/restauración transaccional de stock
│   │   └── notificacion_service.py  # Notificaciones internas
│   └── utils/
│       ├── helpers.py           # Utilidades compartidas (paginación, formateo, etc.)
│       └── storage.py           # Helpers para Supabase Storage
├── sql/
│   └── funciones_rpc.sql        # ⚠️ Ejecutar en Supabase ANTES de arrancar
├── logs/                        # Logs de la app (auto-generado)
├── .env.example                 # Variables de entorno de ejemplo
├── requirements.txt             # Dependencias Python
├── Procfile                     # Para Railway
└── railway.toml                 # Configuración de deploy en Railway
```

---

## ⚡ Inicio rápido

### 1. Clonar e instalar dependencias

```bash
git clone <tu-repo>
cd el_limpiecito
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tus claves reales de Supabase, Stripe y Resend
```

### 3. Ejecutar SQL en Supabase

En tu proyecto de Supabase ve a **SQL Editor** y ejecuta el contenido de:
```
sql/funciones_rpc.sql
```
Esto agrega columnas extra y funciones RPC que necesita el backend.

### 4. Configurar Supabase Storage

En Supabase → **Storage**, crea dos buckets públicos:
- `productos` — imágenes de productos
- `avatars` — fotos de perfil de usuarios

### 5. Arrancar el servidor

```bash
# Desarrollo (con recarga automática)
uvicorn app.main:app --reload --port 8000

# La API estará en http://localhost:8000
# Documentación interactiva: http://localhost:8000/docs
```

---

## 🔌 Endpoints principales

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| POST | `/auth/registro` | Crear cuenta | ❌ |
| POST | `/auth/login` | Login → JWT | ❌ |
| POST | `/auth/recuperar-password` | Email de recuperación | ❌ |
| PUT | `/auth/cambiar-password` | Nueva contraseña | ✅ |
| GET | `/productos` | Listar con filtros | ❌ |
| GET | `/productos/{id}` | Detalle + visitas | ❌ |
| POST | `/productos` | Crear producto | 👑 Admin |
| GET | `/carrito` | Ver carrito | ✅ |
| POST | `/carrito/items` | Agregar al carrito | ✅ |
| POST | `/carrito/cupon` | Aplicar cupón | ✅ |
| POST | `/pedidos` | Crear pedido (atómico) | ✅ |
| POST | `/pagos/stripe/intent` | Crear PaymentIntent | ✅ |
| POST | `/pagos/stripe/webhook` | Webhook Stripe | 🔑 Stripe |
| GET | `/usuarios/perfil` | Ver perfil | ✅ |
| GET | `/admin/dashboard` | Dashboard admin | 👑 Admin |
| GET | `/admin/reportes/ventas` | Reporte de ventas | 👑 Admin |
| GET | `/admin/inventario` | Stock y alertas | 👑 Admin |

---

## 🔐 Seguridad implementada

- **JWT** firmados por Supabase Auth, verificados en cada request
- **Rate limiting** en `/auth/login`: 5 intentos / 15 min por IP
- **Roles**: `cliente` y `admin` — rutas de admin bloqueadas con `get_admin_user()`
- **Webhook Stripe**: verificación de firma `stripe-signature` obligatoria
- **Validación de datos**: Pydantic v2 en todos los endpoints
- **CORS** configurado explícitamente por origen

---

## 💳 Flujo de pago completo

```
Frontend                    Backend                     Servicios externos
   │                           │                              │
   │── POST /pedidos ──────────▶│── Transacción atómica:      │
   │                           │   crear pedido               │
   │                           │   crear items                │
   │                           │   descontar stock            │
   │                           │   vaciar carrito             │
   │◀── { pedido_id } ─────────│                              │
   │                           │                              │
   │── POST /pagos/stripe/intent▶│── stripe.PaymentIntent.create ──▶ Stripe
   │◀── { client_secret } ─────│◀─────────────────────────────────│
   │                           │                              │
   │── Confirmar con Stripe.js──────────────────────────────▶ Stripe
   │                           │                              │
   │                           │◀── Webhook payment_intent.succeeded
   │                           │── Actualizar estado pedido   │
   │                           │── Generar PDF (WeasyPrint)   │
   │                           │── Enviar email + PDF (Resend)│
   │                           │── Crear notificación         │
```

---

## 🚀 Deploy en Railway

1. Conecta tu repositorio en [railway.app](https://railway.app)
2. Agrega las variables de entorno desde `.env.example`
3. Railway detecta automáticamente el `Procfile` y hace el deploy
4. Configura el webhook de Stripe apuntando a `https://tu-app.railway.app/pagos/stripe/webhook`

---

## 🛠️ Variables de entorno requeridas

Ver `.env.example` para la lista completa. Las **obligatorias** son:
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
- `DATABASE_URL` (conexión directa PostgreSQL para transacciones)
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- `RESEND_API_KEY`
