

from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from app.models.schemas import CrearPaymentIntentRequest, PaymentIntentResponse, MensajeResponse
from app.database import get_supabase
from app.dependencies import get_current_user, UsuarioActual
from app.services.email_service import enviar_confirmacion_pedido
from app.services.pdf_service import generar_factura
from app.services.notificacion_service import crear_notificacion
from app.config import get_settings
from loguru import logger
import stripe

settings = get_settings()
stripe.api_key = settings.stripe_secret_key

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.post("/stripe/intent", response_model=PaymentIntentResponse)
async def crear_payment_intent(
    datos: CrearPaymentIntentRequest,
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Crea un PaymentIntent de Stripe para procesar el pago de un pedido.
    El frontend usa el client_secret para confirmar el pago con Stripe.js.
    """
    supabase = get_supabase()

    # Obtener pedido y verificar que pertenece al usuario
    pedido_res = (
        supabase.table("Pedido")
        .select("id, total, estado, usuario_id")
        .eq("id", datos.pedido_id)
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
            detail=f"El pedido no está en estado pendiente (estado actual: {pedido['estado']})"
        )

    # Convertir a centavos (Stripe trabaja con la unidad mínima de la moneda)
    monto_centavos = int(float(pedido["total"]) * 100)

    if monto_centavos < 500:  # Mínimo de Stripe en MXN: $5.00
        raise HTTPException(status_code=400, detail="El monto mínimo para pago es $5.00 MXN")

    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=monto_centavos,
            currency="mxn",
            metadata={
                "pedido_id": datos.pedido_id,
                "usuario_id": usuario.id,
                "usuario_email": usuario.email,
            },
            description=f"Pedido #{datos.pedido_id[:8].upper()} - El Limpiecito",
            receipt_email=usuario.email,
        )

        # Guardar ID del PaymentIntent en el pedido
        supabase.table("Pedido").update({
            "stripe_payment_intent_id": payment_intent.id,
        }).eq("id", datos.pedido_id).execute()

        logger.info(f"PaymentIntent {payment_intent.id} creado para pedido {datos.pedido_id}")

        return PaymentIntentResponse(
            client_secret=payment_intent.client_secret,
            payment_intent_id=payment_intent.id,
            monto=monto_centavos,
            moneda="mxn",
        )

    except stripe.StripeError as e:
        logger.error(f"Error Stripe al crear PaymentIntent: {e}")
        raise HTTPException(status_code=400, detail=f"Error de pago: {str(e)}")


@router.post("/stripe/webhook", response_model=MensajeResponse)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Webhook de Stripe para confirmar pagos completados.
    
    Flujo al recibir 'payment_intent.succeeded':
    1. Verificar firma del webhook (seguridad)
    2. Obtener pedido asociado al PaymentIntent
    3. Actualizar estado del pedido a 'confirmado'
    4. Crear registro de Pago
    5. [Background] Generar factura PDF con WeasyPrint
    6. [Background] Enviar email de confirmación con factura adjunta
    7. [Background] Crear notificación interna
    """
    # Leer payload raw para verificar firma de Stripe
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        evento = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.SignatureVerificationError:
        logger.warning("⚠️ Webhook de Stripe con firma inválida")
        raise HTTPException(status_code=400, detail="Firma del webhook inválida")

    logger.info(f"Webhook Stripe recibido: {evento['type']}")

    # ─── Pago exitoso ────────────────────────────────────────────────────
    if evento["type"] == "payment_intent.succeeded":
        payment_intent = evento["data"]["object"]
        pedido_id = payment_intent.get("metadata", {}).get("pedido_id")

        if not pedido_id:
            logger.warning("PaymentIntent sin pedido_id en metadata")
            return MensajeResponse(mensaje="OK - sin pedido asociado")

        background_tasks.add_task(_procesar_pago_exitoso, pedido_id, payment_intent)

    elif evento["type"] == "payment_intent.payment_failed":
        payment_intent = evento["data"]["object"]
        pedido_id = payment_intent.get("metadata", {}).get("pedido_id")
        usuario_id = payment_intent.get("metadata", {}).get("usuario_id")

        if pedido_id and usuario_id:
            background_tasks.add_task(_procesar_pago_fallido, pedido_id, usuario_id)

    return MensajeResponse(mensaje="OK")


async def _procesar_pago_exitoso(pedido_id: str, payment_intent: dict):
    """
    Procesa el pago exitoso en background:
    actualiza BD, genera PDF y envía email de confirmación.
    """
    supabase = get_supabase()
    try:
        # Obtener datos del pedido
        pedido_res = (
            supabase.table("Pedido")
            .select("*, Usuario(nombre, email)")
            .eq("id", pedido_id)
            .single()
            .execute()
        )
        pedido = pedido_res.data
        if not pedido:
            logger.error(f"Pedido {pedido_id} no encontrado en webhook")
            return

        # Actualizar estado del pedido
        supabase.table("Pedido").update({
            "estado": "confirmado",
            "fecha_actualizacion": "now()",
        }).eq("id", pedido_id).execute()

        # Crear registro de Pago
        supabase.table("Pago").insert({
            "pedido_id": pedido_id,
            "stripe_payment_intent_id": payment_intent["id"],
            "monto": float(payment_intent["amount"]) / 100,
            "moneda": payment_intent.get("currency", "mxn").upper(),
            "estado": "exitoso",
            "metodo": payment_intent.get("payment_method_types", ["card"])[0],
        }).execute()

        # Obtener items del pedido para el email
        items_res = (
            supabase.table("ItemPedido")
            .select("nombre_producto, cantidad, precio_unitario, subtotal")
            .eq("pedido_id", pedido_id)
            .execute()
        )
        items = [
            {
                "nombre": i.get("nombre_producto", "Producto"),
                "cantidad": i["cantidad"],
                "precio": float(i["precio_unitario"]),
                "subtotal": float(i["subtotal"]),
            }
            for i in (items_res.data or [])
        ]

        # Generar factura PDF
        pdf_bytes = await generar_factura(pedido_id)

        # Obtener datos del usuario
        usuario_data = pedido.get("Usuario", {}) or {}

        # Enviar email de confirmación con factura adjunta
        await enviar_confirmacion_pedido(
            email=usuario_data.get("email", ""),
            nombre=usuario_data.get("nombre", "Cliente"),
            pedido_id=pedido_id,
            items=items,
            total=float(pedido.get("total", 0)),
            pdf_bytes=pdf_bytes,
        )

        # Notificación interna
        await crear_notificacion(
            usuario_id=pedido["usuario_id"],
            tipo="pago_exitoso",
            mensaje=f"Pago confirmado para pedido #{pedido_id[:8].upper()}. ¡Gracias por tu compra!",
            referencia_id=pedido_id,
            referencia_tipo="pedido",
        )

        logger.info(f"✅ Pago procesado completamente para pedido {pedido_id}")

    except Exception as e:
        logger.error(f"❌ Error procesando pago exitoso para pedido {pedido_id}: {e}")


async def _procesar_pago_fallido(pedido_id: str, usuario_id: str):
    """Maneja un pago fallido: notifica al usuario"""
    try:
        supabase = get_supabase()
        await crear_notificacion(
            usuario_id=usuario_id,
            tipo="pago_fallido",
            mensaje=f"El pago del pedido #{pedido_id[:8].upper()} no pudo procesarse. Intenta de nuevo.",
            referencia_id=pedido_id,
            referencia_tipo="pedido",
        )
    except Exception as e:
        logger.error(f"Error notificando pago fallido: {e}")
