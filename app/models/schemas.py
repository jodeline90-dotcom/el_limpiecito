

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import datetime
from decimal import Decimal
import re



class RegistroRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    telefono: Optional[str] = Field(None, max_length=20)

    @field_validator("password")
    @classmethod
    def password_seguro(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe tener al menos una mayúscula")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe tener al menos un número")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RecuperarPasswordRequest(BaseModel):
    email: EmailStr


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str = Field(..., min_length=8)

    @field_validator("password_nueva")
    @classmethod
    def password_seguro(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe tener al menos una mayúscula")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe tener al menos un número")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: "UsuarioResponse"



class UsuarioResponse(BaseModel):
    id: str
    nombre: str
    email: str
    telefono: Optional[str] = None
    foto_url: Optional[str] = None
    rol: str
    activo: bool
    nivel: str = "Nuevo"
    fecha_creacion: Optional[datetime] = None


class ActualizarPerfilRequest(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    telefono: Optional[str] = Field(None, max_length=20)


class DireccionCreate(BaseModel):
    calle: str = Field(..., max_length=200)
    ciudad: str = Field(..., max_length=100)
    estado: str = Field(..., max_length=100)
    codigo_postal: str = Field(..., max_length=10)
    pais: str = Field(default="México", max_length=100)
    es_predeterminada: bool = False
    referencia: Optional[str] = Field(None, max_length=200)


class DireccionResponse(BaseModel):
    id: str
    calle: str
    ciudad: str
    estado: str
    codigo_postal: str
    pais: str
    es_predeterminada: bool
    referencia: Optional[str] = None



class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=200)
    descripcion: Optional[str] = None
    precio: Decimal = Field(..., gt=0, decimal_places=2)
    precio_comparacion: Optional[Decimal] = Field(None, gt=0)
    stock: int = Field(..., ge=0)
    stock_minimo: int = Field(default=5, ge=0)
    sku: Optional[str] = Field(None, max_length=50)
    categoria_id: str
    proveedor_id: Optional[str] = None
    activo: bool = True
    destacado: bool = False
    peso_gramos: Optional[int] = None
    unidad_medida: Optional[str] = Field(None, max_length=20)


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=200)
    descripcion: Optional[str] = None
    precio: Optional[Decimal] = Field(None, gt=0)
    precio_comparacion: Optional[Decimal] = None
    stock: Optional[int] = Field(None, ge=0)
    stock_minimo: Optional[int] = Field(None, ge=0)
    sku: Optional[str] = None
    categoria_id: Optional[str] = None
    activo: Optional[bool] = None
    destacado: Optional[bool] = None


class ProductoVisibilidadRequest(BaseModel):
    activo: bool


class ProductoFiltros(BaseModel):
    categoria: Optional[str] = None
    precio_min: Optional[float] = Field(None, ge=0)
    precio_max: Optional[float] = Field(None, ge=0)
    orden: Optional[Literal["precio_asc", "precio_desc", "nombre", "mas_vendido", "mas_nuevo"]] = "mas_nuevo"
    busqueda: Optional[str] = None
    pagina: int = Field(default=1, ge=1)
    limite: int = Field(default=20, ge=1, le=100)


class ProductoResponse(BaseModel):
    id: str
    nombre: str
    descripcion: Optional[str] = None
    precio: Decimal
    precio_comparacion: Optional[Decimal] = None
    stock: int
    stock_minimo: int
    sku: Optional[str] = None
    categoria_id: str
    categoria_nombre: Optional[str] = None
    activo: bool
    destacado: bool
    contador_visitas: int
    imagenes: List[str] = []
    promedio_estrellas: float = 0.0
    total_resenas: int = 0
    fecha_creacion: Optional[datetime] = None


class ProductoListResponse(BaseModel):
    productos: List[ProductoResponse]
    total: int
    pagina: int
    total_paginas: int



class AgregarItemCarritoRequest(BaseModel):
    producto_id: str
    cantidad: int = Field(..., ge=1)


class ActualizarItemCarritoRequest(BaseModel):
    cantidad: int = Field(..., ge=1)


class AplicarCuponRequest(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=50)


class ItemCarritoResponse(BaseModel):
    id: str
    producto_id: str
    nombre_producto: str
    imagen_url: Optional[str] = None
    precio_unitario: Decimal
    cantidad: int
    subtotal: Decimal


class CarritoResponse(BaseModel):
    id: str
    items: List[ItemCarritoResponse]
    subtotal: Decimal
    descuento: Decimal = Decimal("0.00")
    total: Decimal
    cupon_aplicado: Optional[str] = None
    descuento_porcentaje: Optional[int] = None



class CrearPedidoRequest(BaseModel):
    direccion_id: str
    metodo_pago_id: Optional[str] = None
    notas: Optional[str] = Field(None, max_length=500)


class CambiarEstadoPedidoRequest(BaseModel):
    estado: Literal["pendiente", "confirmado", "en_preparacion", "enviado", "entregado", "cancelado"]
    notas: Optional[str] = None


class ItemPedidoResponse(BaseModel):
    id: str
    producto_id: str
    nombre_producto: str
    precio_unitario: Decimal
    cantidad: int
    subtotal: Decimal


class PedidoResponse(BaseModel):
    id: str
    usuario_id: str
    estado: str
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    notas: Optional[str] = None
    direccion: Optional[dict] = None
    items: List[ItemPedidoResponse] = []
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None


class PedidoListResponse(BaseModel):
    pedidos: List[PedidoResponse]
    total: int



class CrearPaymentIntentRequest(BaseModel):
    pedido_id: str


class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    monto: int   # en centavos
    moneda: str



class CrearCuponRequest(BaseModel):
    codigo: str = Field(..., min_length=3, max_length=50)
    descuento_porcentaje: Optional[int] = Field(None, ge=1, le=100)
    descuento_fijo: Optional[Decimal] = Field(None, gt=0)
    maximo_usos: Optional[int] = Field(None, ge=1)
    fecha_vencimiento: Optional[datetime] = None
    monto_minimo: Optional[Decimal] = Field(None, ge=0)
    activo: bool = True

    @model_validator(mode="after")
    def validar_descuento(self) -> "CrearCuponRequest":
        if not self.descuento_porcentaje and not self.descuento_fijo:
            raise ValueError("Debe especificar descuento_porcentaje o descuento_fijo")
        if self.descuento_porcentaje and self.descuento_fijo:
            raise ValueError("Solo puede especificar un tipo de descuento")
        return self


class CrearProveedorRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=200)
    contacto_nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    notas: Optional[str] = None


class ReporteVentasFiltros(BaseModel):
    fecha_inicio: datetime
    fecha_fin: datetime
    agrupar_por: Optional[Literal["dia", "semana", "mes"]] = "dia"




class MensajeResponse(BaseModel):
    mensaje: str
    exitoso: bool = True


class ErrorResponse(BaseModel):
    detail: str
    codigo: Optional[str] = None


class CoberturaResponse(BaseModel):
    id: str
    colonia: str
    codigo_postal: str
    costo_envio: Decimal
    tiempo_estimado: str
    activo: bool




class FavoritoCreate(BaseModel):
    producto_id: str


class FavoritoResponse(BaseModel):
    id: str
    usuario_id: str
    producto_id: str
    fecha_agregado: datetime
    producto: Optional[ProductoResponse] = None




class ResenaCreate(BaseModel):
    estrellas: int = Field(..., ge=1, le=5)
    comentario: Optional[str] = Field(None, max_length=1000)


class ResenaResponse(BaseModel):
    id: str
    usuario_id: str
    usuario_nombre: Optional[str] = None
    usuario_foto: Optional[str] = None
    producto_id: str
    estrellas: int
    comentario: Optional[str] = None
    fecha_creacion: datetime



class NewsletterSubscriptionRequest(BaseModel):
    email: EmailStr


class NewsletterResponse(BaseModel):
    email: str
    fecha_registro: datetime



