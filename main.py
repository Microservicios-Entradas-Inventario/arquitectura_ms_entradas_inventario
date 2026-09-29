from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List, Optional
from services.promociones_service import PromocionesService
from services.catalogo_service import CatalogoService
from services.pagos_service import PagosService
from services.notificaciones_service import NotificacionesService
from services.checkin_service import CheckinService

app = FastAPI(
    title="TicketU - API de Entradas e Inventario",
    description="Microservicio central de Entradas e Inventario. Expone servicios propios (BE1) y requeridos por otros (BE3).",
    version="1.0.0"
)

# ==========================================
# SCHEMAS (Pydantic Models)
# ==========================================

class InventarioResponse(BaseModel):
    id_evento: str
    stock_actual: int
    tipo_entrada: str
    precio_unitario: int

class ReservaRequest(BaseModel):
    id_evento: str
    id_usuario: str
    cantidad_entradas: int = Field(gt=0)

class ReservaResponse(BaseModel):
    id_reserva: str
    estado: str
    monto_total: int
    descuento_aplicado: float
    id_pago_pendiente: Optional[str] = None

class StockValidacionResponse(BaseModel):
    id_evento: str
    stock_actual: int
    cantidad_entrada_reservada: int
    cantidad_entrada_comprada: int
    permite_eliminar: bool

class ValidacionEntradaResponse(BaseModel):
    id_entrada: str
    id_usuario: str
    nombre_usuario: str
    qr_data: str
    valida: bool

class DetalleReservaNotificacion(BaseModel):
    id_reserva: str
    id_usuario: str
    nombre_evento: str
    fecha_evento: str
    cantidad_entradas: int

# ==========================================
# ÍTEM BE1: SERVICIOS PROPIOS
# ==========================================

@app.get("/api/v1/inventario/{id_evento}", tags=["Inventario (BE1)"], response_model=InventarioResponse)
async def obtener_disponibilidad(id_evento: str):
    """ HU-01: Visualización de disponibilidad. """
    return {"id_evento": id_evento, "stock_actual": 148, "tipo_entrada": "PAGADA", "precio_unitario": 10000}

@app.post("/api/v1/reservas", tags=["Reservas (BE1)"], response_model=ReservaResponse)
async def crear_reserva(reserva: ReservaRequest, authorization: Optional[str] = Header(None)):
    """ 
    HU-03: Reserva temporal de cupo.
    1. Llama a Promociones (Síncrono) para calcular el descuento.
    2. Llama a Pagos para iniciar cobro (Síncrono).
    3. Llama a Catálogo para actualizar stock (Síncrono) vía PUT enviando el token.
    """
    token = authorization.replace("Bearer ", "") if authorization else "dummy_token"

    # Invocación a Promociones
    promo = await PromocionesService.consultar_promocion_vigente(reserva.id_evento, reserva.id_usuario, reserva.cantidad_entradas)
    descuento = promo.get("porcentaje_descuento", 0)
    monto_total = (10000 * reserva.cantidad_entradas) * (1 - descuento/100)
    
    # Invocación a Pagos
    pago = await PagosService.iniciar_cobro("res-98765", int(monto_total), reserva.id_usuario)

    # Invocación a Catálogo
    await CatalogoService.actualizar_stock_catalogo(reserva.id_evento, 148 - reserva.cantidad_entradas, token)

    return {
        "id_reserva": "res-98765",
        "estado": pago.get("estado", "PENDIENTE"),
        "monto_total": int(monto_total),
        "descuento_aplicado": descuento,
        "id_pago_pendiente": pago.get("id_pago")
    }

# ==========================================
# ÍTEM BE3: SERVICIOS REQUERIDOS POR OTROS MÓDULOS
# ==========================================

@app.get("/api/v1/entradas/{id_entrada}/validacion", tags=["Integración Externa (BE3) - Para Check-in"], response_model=ValidacionEntradaResponse)
async def validar_entrada_para_checkin(id_entrada: str):
    """
    Rúbrica: Expone los datos "QR y nombre de usuario".
    Fallback/Pull API en caso de que el envío paralelo falle o Check-in necesite re-validar.
    """
    return {
        "id_entrada": id_entrada,
        "id_usuario": "usr-12345",
        "nombre_usuario": "Estudiante Anonimo",
        "qr_data": "https://storage.midominio.com/qr/tk-998877.png",
        "valida": True
    }

@app.get("/api/v1/reservas/{id_reserva}/detalles", tags=["Integración Externa (BE3) - Para Notificaciones"], response_model=DetalleReservaNotificacion)
async def obtener_detalles_para_notificacion(id_reserva: str):
    """
    Rúbrica: Expone "id usuario, nombre evento, fecha y cantidad de entradas".
    Fallback/Pull API para que Notificaciones obtenga el detalle de una compra.
    """
    return {
        "id_reserva": id_reserva,
        "id_usuario": "usr-12345",
        "nombre_evento": "Gala de Informática",
        "fecha_evento": "2026-11-15T20:00:00Z",
        "cantidad_entradas": 2
    }

@app.get("/api/v1/inventario/{id_evento}/stock-validacion", tags=["Integración Externa (BE3) - Para Panel Organizador"], response_model=StockValidacionResponse)
async def validar_stock_para_panel(id_evento: str):
    """
    Contrato: Contrato_Entradas_Panel_Unificado_v3.docx
    Permite al Panel validar si un evento tiene compras antes de permitir su eliminación.
    """
    return {
        "id_evento": id_evento,
        "stock_actual": 148,
        "cantidad_entrada_reservada": 1,
        "cantidad_entrada_comprada": 1,
        "permite_eliminar": False # No permite eliminar si ya hay compras
    }

# ==========================================
# SIMULACIÓN DE ASINCRONÍA (RABBITMQ) -> EMISIÓN DE TICKETS
# ==========================================

@app.post("/api/v1/reservas/{id_reserva}/webhook-pago", tags=["Simulación RabbitMQ - Pago Aprobado"])
async def procesar_pago_aprobado(id_reserva: str):
    """
    HU-09: Emisión definitiva.
    Simula la recepción del evento asíncrono 'PagoAprobado' desde el broker RabbitMQ.
    1. Llama a Checkin para distribuir el QR.
    2. Llama a Notificaciones para enviar el correo.
    """
    id_usuario = "usr-12345"
    id_evento = "evt-77889"
    qr_data = "https://storage.midominio.com/qr/tk-998877.png"

    await CheckinService.registrar_ticket_puerta("tk-998877", id_evento, id_usuario, qr_data)
    await NotificacionesService.enviar_ticket_correo(id_usuario, "Gala de Informática", "2026-11-15T20:00:00Z", qr_data)

    return {"message": "Ticket emitido y notificaciones distribuidas correctamente."}
