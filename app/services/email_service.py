# ============================================================
# app/services/email_service.py - Envío de correos con Resend
# ============================================================

import resend
from app.config import get_settings
from loguru import logger
from typing import Optional, List

settings = get_settings()
resend.api_key = settings.resend_api_key


async def send_email(
    to: str | List[str],
    subject: str,
    html: str,
    texto_plano: Optional[str] = None,
) -> bool:
    """
    Envía un email usando la API de Resend.
    Retorna True si se envió correctamente, False en caso de error.
    """
    destinatarios = [to] if isinstance(to, str) else to
    try:
        params: resend.Emails.SendParams = {
            "from": f"{settings.email_from_name} <{settings.email_from}>",
            "to": destinatarios,
            "subject": subject,
            "html": html,
        }
        if texto_plano:
            params["text"] = texto_plano

        response = resend.Emails.send(params)
        logger.info(f"✉️  Email enviado a {destinatarios} | ID: {response.get('id')}")
        return True
    except Exception as e:
        logger.error(f"❌ Error enviando email a {destinatarios}: {e}")
        return False


# ─── Templates de email ──────────────────────────────────────────────────────

def _base_template(contenido: str, titulo: str) -> str:
    """Template HTML base con branding de El Limpiecito"""
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{titulo}</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #0ea5e9, #0284c7); padding: 30px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 24px; }}
            .header p {{ color: rgba(255,255,255,0.85); margin: 5px 0 0; }}
            .body {{ padding: 30px; color: #374151; line-height: 1.6; }}
            .footer {{ background: #f8fafc; padding: 20px; text-align: center; color: #9ca3af; font-size: 13px; }}
            .btn {{ display: inline-block; background: #0ea5e9; color: white !important; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0; }}
            .info-box {{ background: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 15px; border-radius: 0 8px 8px 0; margin: 15px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #f1f5f9; padding: 10px; text-align: left; font-size: 13px; color: #6b7280; }}
            td {{ padding: 10px; border-bottom: 1px solid #f1f5f9; }}
            .total-row {{ font-weight: bold; background: #f8fafc; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧹 El Limpiecito</h1>
                <p>Tu tienda de productos de limpieza</p>
            </div>
            <div class="body">
                {contenido}
            </div>
            <div class="footer">
                <p>© 2024 El Limpiecito. Todos los derechos reservados.</p>
                <p>Si no realizaste esta acción, ignora este correo.</p>
            </div>
        </div>
    </body>
    </html>
    """


async def enviar_bienvenida(email: str, nombre: str) -> bool:
    """Email de bienvenida al registrarse"""
    contenido = f"""
        <h2>¡Bienvenido, {nombre}! 🎉</h2>
        <p>Tu cuenta en <strong>El Limpiecito</strong> ha sido creada exitosamente.</p>
        <div class="info-box">
            <strong>¿Qué puedes hacer ahora?</strong>
            <ul>
                <li>Explorar nuestro catálogo de productos</li>
                <li>Agregar artículos a tu carrito</li>
                <li>Gestionar tus direcciones de envío</li>
            </ul>
        </div>
        <p>¡Gracias por elegirnos!</p>
    """
    return await send_email(email, "¡Bienvenido a El Limpiecito! 🧹", _base_template(contenido, "Bienvenida"))


async def enviar_recuperacion_password(email: str, nombre: str, link: str) -> bool:
    """Email para recuperar contraseña"""
    contenido = f"""
        <h2>Recuperación de contraseña</h2>
        <p>Hola <strong>{nombre}</strong>, recibimos una solicitud para restablecer tu contraseña.</p>
        <p>Haz clic en el botón para crear una nueva contraseña:</p>
        <div style="text-align: center;">
            <a href="{link}" class="btn">Restablecer Contraseña</a>
        </div>
        <div class="info-box">
            ⚠️ Este enlace es válido por <strong>1 hora</strong>. 
            Si no solicitaste esto, ignora este correo.
        </div>
    """
    return await send_email(email, "Recupera tu contraseña - El Limpiecito", _base_template(contenido, "Recuperar contraseña"))


async def enviar_confirmacion_pedido(
    email: str,
    nombre: str,
    pedido_id: str,
    items: list,
    total: float,
    pdf_bytes: Optional[bytes] = None,
) -> bool:
    """Email de confirmación de pedido con factura adjunta"""
    items_html = "".join([
        f"<tr><td>{item['nombre']}</td><td>{item['cantidad']}</td><td>${item['precio']:.2f}</td><td>${item['subtotal']:.2f}</td></tr>"
        for item in items
    ])
    contenido = f"""
        <h2>¡Pedido confirmado! ✅</h2>
        <p>Hola <strong>{nombre}</strong>, tu pago fue procesado exitosamente.</p>
        <div class="info-box">
            <strong>Número de pedido:</strong> #{pedido_id[:8].upper()}
        </div>
        <table>
            <thead>
                <tr>
                    <th>Producto</th><th>Cant.</th><th>Precio</th><th>Subtotal</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
                <tr class="total-row">
                    <td colspan="3"><strong>Total pagado</strong></td>
                    <td><strong>${total:.2f} MXN</strong></td>
                </tr>
            </tbody>
        </table>
        <p>Te notificaremos cuando tu pedido sea enviado. ¡Gracias por tu compra!</p>
    """

    params: resend.Emails.SendParams = {
        "from": f"{settings.email_from_name} <{settings.email_from}>",
        "to": [email],
        "subject": f"Pedido #{pedido_id[:8].upper()} confirmado - El Limpiecito",
        "html": _base_template(contenido, "Pedido confirmado"),
    }

    # Adjuntar factura PDF si se generó correctamente
    if pdf_bytes:
        params["attachments"] = [{
            "filename": f"factura_{pedido_id[:8]}.pdf",
            "content": list(pdf_bytes),
        }]

    try:
        resend.Emails.send(params)
        logger.info(f"✉️  Confirmación de pedido enviada a {email}")
        return True
    except Exception as e:
        logger.error(f"❌ Error enviando confirmación de pedido: {e}")
        return False


async def enviar_cambio_estado_pedido(
    email: str,
    nombre: str,
    pedido_id: str,
    nuevo_estado: str,
) -> bool:
    """Notifica al usuario sobre cambio de estado de su pedido"""
    estados_texto = {
        "confirmado": "ha sido confirmado ✅",
        "en_preparacion": "está siendo preparado 📦",
        "enviado": "ya va en camino 🚚",
        "entregado": "fue entregado con éxito 🎉",
        "cancelado": "fue cancelado ❌",
    }
    descripcion = estados_texto.get(nuevo_estado, f"cambió a: {nuevo_estado}")
    contenido = f"""
        <h2>Actualización de tu pedido</h2>
        <p>Hola <strong>{nombre}</strong>, tu pedido <strong>#{pedido_id[:8].upper()}</strong> {descripcion}.</p>
        <p>Ingresa a tu cuenta para ver más detalles.</p>
    """
    return await send_email(email, f"Tu pedido #{pedido_id[:8].upper()} - El Limpiecito", _base_template(contenido, "Estado del pedido"))
