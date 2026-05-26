# ============================================================
# app/services/pdf_service.py - Generación de facturas PDF con WeasyPrint
# ============================================================

from loguru import logger
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except Exception:
    logger.warning("⚠️ WeasyPrint no está disponible. La generación de facturas PDF estará desactivada.")
    WEASYPRINT_AVAILABLE = False
from app.database import get_supabase
from datetime import datetime
from typing import Optional


def _html_factura(pedido: dict, items: list, usuario: dict, direccion: dict) -> str:
    """
    Genera el HTML de la factura para renderizar con WeasyPrint.
    """
    fecha = datetime.fromisoformat(pedido.get("fecha_creacion", datetime.now().isoformat()))
    folio = pedido["id"][:8].upper()

    items_html = "".join([
        f"""
        <tr>
            <td>{item.get('nombre_producto', 'Producto')}</td>
            <td class="center">{item['cantidad']}</td>
            <td class="right">${float(item['precio_unitario']):.2f}</td>
            <td class="right">${float(item['subtotal']):.2f}</td>
        </tr>
        """
        for item in items
    ])

    descuento = float(pedido.get("descuento", 0))
    subtotal = float(pedido.get("subtotal", 0))
    total = float(pedido.get("total", 0))

    fila_descuento = ""
    if descuento > 0:
        fila_descuento = f"""
        <tr class="descuento-row">
            <td colspan="3">Descuento aplicado</td>
            <td class="right">-${descuento:.2f}</td>
        </tr>
        """

    dir_texto = ""
    if direccion:
        dir_texto = f"{direccion.get('calle', '')}, {direccion.get('ciudad', '')}, {direccion.get('estado', '')}, C.P. {direccion.get('codigo_postal', '')}"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: 'Inter', Arial, sans-serif; font-size: 12px; color: #1f2937; line-height: 1.5; }}
            .page {{ padding: 40px; max-width: 800px; margin: 0 auto; }}

            /* Encabezado */
            .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; border-bottom: 3px solid #0ea5e9; padding-bottom: 20px; }}
            .logo {{ color: #0ea5e9; font-size: 22px; font-weight: 700; }}
            .logo span {{ display: block; font-size: 11px; color: #6b7280; font-weight: 400; margin-top: 2px; }}
            .factura-info {{ text-align: right; }}
            .factura-info h2 {{ font-size: 18px; color: #0ea5e9; font-weight: 700; }}
            .factura-info p {{ color: #6b7280; font-size: 11px; margin-top: 4px; }}

            /* Datos */
            .datos {{ display: flex; justify-content: space-between; margin-bottom: 30px; gap: 20px; }}
            .datos-box {{ flex: 1; }}
            .datos-box h3 {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #9ca3af; margin-bottom: 8px; }}
            .datos-box p {{ font-size: 12px; color: #374151; }}
            .datos-box .nombre {{ font-weight: 600; font-size: 13px; }}

            /* Tabla de productos */
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            thead tr {{ background: #0ea5e9; color: white; }}
            thead th {{ padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600; letter-spacing: 0.03em; }}
            tbody tr {{ border-bottom: 1px solid #f1f5f9; }}
            tbody tr:nth-child(even) {{ background: #f8fafc; }}
            tbody td {{ padding: 9px 12px; }}
            .center {{ text-align: center; }}
            .right {{ text-align: right; }}
            .descuento-row td {{ color: #059669; font-style: italic; }}

            /* Totales */
            .totales {{ display: flex; justify-content: flex-end; }}
            .totales table {{ width: 280px; }}
            .totales td {{ padding: 6px 12px; }}
            .total-final {{ background: #0ea5e9; color: white; font-weight: 700; font-size: 14px; }}
            .total-final td {{ padding: 10px 12px; }}

            /* Pie */
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #9ca3af; font-size: 11px; }}
            .badge {{ display: inline-block; background: #dcfce7; color: #15803d; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="page">
            <div class="header">
                <div class="logo">
                    🧹 El Limpiecito
                    <span>Tu tienda de productos de limpieza</span>
                </div>
                <div class="factura-info">
                    <h2>FACTURA</h2>
                    <p>Folio: <strong>#{folio}</strong></p>
                    <p>Fecha: {fecha.strftime('%d/%m/%Y')}</p>
                </div>
            </div>

            <div class="datos">
                <div class="datos-box">
                    <h3>Cliente</h3>
                    <p class="nombre">{usuario.get('nombre', 'Cliente')}</p>
                    <p>{usuario.get('email', '')}</p>
                    {f"<p>{usuario.get('telefono', '')}</p>" if usuario.get('telefono') else ''}
                </div>
                <div class="datos-box">
                    <h3>Dirección de envío</h3>
                    <p>{dir_texto or 'No especificada'}</p>
                </div>
                <div class="datos-box">
                    <h3>Estado del pago</h3>
                    <span class="badge">✓ PAGADO</span>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Producto</th>
                        <th class="center">Cantidad</th>
                        <th class="right">Precio unit.</th>
                        <th class="right">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>

            <div class="totales">
                <table>
                    <tr>
                        <td>Subtotal</td>
                        <td class="right">${subtotal:.2f} MXN</td>
                    </tr>
                    {fila_descuento}
                    <tr class="total-final">
                        <td><strong>TOTAL</strong></td>
                        <td class="right"><strong>${total:.2f} MXN</strong></td>
                    </tr>
                </table>
            </div>

            <div class="footer">
                <p>El Limpiecito · contacto@ellimpiecito.com · www.ellimpiecito.com</p>
                <p>Este documento es un comprobante de tu compra. Consérvalo para cualquier aclaración.</p>
            </div>
        </div>
    </body>
    </html>
    """


async def generar_factura(pedido_id: str) -> Optional[bytes]:
    """
    Genera la factura PDF de un pedido.
    Retorna los bytes del PDF o None si hay error.
    """
    supabase = get_supabase()
    try:
        # Obtener datos del pedido
        pedido_res = (
            supabase.table("Pedido")
            .select("*, Direccion(*)")
            .eq("id", pedido_id)
            .single()
            .execute()
        )
        pedido = pedido_res.data
        if not pedido:
            logger.error(f"Pedido {pedido_id} no encontrado para generar factura")
            return None

        # Obtener items del pedido
        items_res = (
            supabase.table("ItemPedido")
            .select("*, Producto(nombre)")
            .eq("pedido_id", pedido_id)
            .execute()
        )
        items = items_res.data or []

        # Normalizar nombre del producto en cada item
        for item in items:
            if isinstance(item.get("Producto"), dict):
                item["nombre_producto"] = item["Producto"].get("nombre", "Producto")

        # Obtener datos del usuario
        usuario_res = (
            supabase.table("Usuario")
            .select("nombre, email, telefono")
            .eq("id", pedido["usuario_id"])
            .single()
            .execute()
        )
        usuario = usuario_res.data or {}
        direccion = pedido.get("Direccion") or {}

        # Generar HTML y convertir a PDF
        if not WEASYPRINT_AVAILABLE:
            logger.warning(f"⚠️ Saltando generación de factura para pedido {pedido_id} porque WeasyPrint no está instalado.")
            return None

        html_content = _html_factura(pedido, items, usuario, direccion)
        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(f"📄 Factura generada para pedido {pedido_id} ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ Error generando factura para pedido {pedido_id}: {e}")
        return None
