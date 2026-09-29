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
    id_evento: str = Field(..., description="Identificador único del evento.")
    id_usuario: str = Field(..., description="Identificador del usuario que realiza la reserva.")
    cantidad_entradas: int = Field(gt=0, description="Cantidad de entradas a adquirir.")

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

@app.get(
    "/api/v1/inventario/{id_evento}", 
    tags=["Inventario (BE1)"], 
    response_model=InventarioResponse,
    responses={200: {"description": "Disponibilidad obtenida exitosamente"}, 404: {"description": "Evento no encontrado"}}
)
async def obtener_disponibilidad(id_evento: str):
    """
    **Propósito:** Consultar el stock actual y detalles comerciales de un evento en específico (Soporte a HU-01).
    
    **Parámetros:**
    - `id_evento` (Path): El identificador único del evento a consultar.
    
    **Flujo:**
    1. Recibe el ID del evento.
    2. Consulta en la base de datos la colección `inventario_evento`.
    3. Retorna la cantidad de stock disponible y el precio unitario.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Datos obtenidos correctamente.
    - `404 Not Found`: No existe inventario asociado al evento solicitado.
    """
    return {"id_evento": id_evento, "stock_actual": 148, "tipo_entrada": "PAGADA", "precio_unitario": 10000}

@app.post(
    "/api/v1/reservas", 
    tags=["Reservas (BE1)"], 
    response_model=ReservaResponse,
    responses={200: {"description": "Reserva creada y cobro iniciado"}, 400: {"description": "Datos inválidos o stock insuficiente"}}
)
async def crear_reserva(reserva: ReservaRequest, authorization: Optional[str] = Header(None)):
    """
    **Propósito:** Crear una reserva temporal de entradas (Soporte a HU-03).
    
    **Parámetros:**
    - `reserva` (Body): Objeto que contiene `id_evento`, `id_usuario` y `cantidad_entradas`.
    - `authorization` (Header): Token JWT del usuario para validación de origen en Catálogo.
    
    **Flujo:**
    1. **Promociones (Síncrono):** Consulta el descuento aplicable según contrato.
    2. Calcula el valor total restando el porcentaje de descuento obtenido.
    3. **Pagos (Síncrono):** Solicita a Pagos el inicio de un cobro, obteniendo un ID de pago en estado PENDIENTE.
    4. **Catálogo (Síncrono):** Llama a Catálogo para actualizar el aforo restante enviando el token de sesión.
    5. Retorna los detalles de la reserva junto con el estado del pago.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Reserva pre-aprobada exitosamente.
    - `400 Bad Request`: Stock insuficiente o error en parámetros obligatorios.
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

@app.get(
    "/api/v1/entradas/{id_entrada}/validacion", 
    tags=["Integración Externa (BE3) - Para Check-in"], 
    response_model=ValidacionEntradaResponse,
    responses={200: {"description": "Datos de acceso validados"}, 404: {"description": "Ticket inexistente"}}
)
async def validar_entrada_para_checkin(id_entrada: str):
    """
    **Propósito:** Permitir al módulo de **Check-in** recuperar la data del código QR y nombre de usuario para validación en puerta en caso de error asíncrono.
    
    **Parámetros:**
    - `id_entrada` (Path): El identificador de la entrada a verificar.
    
    **Flujo:**
    1. Recibe el ID de la entrada física.
    2. Busca los detalles asociados en la base de datos local.
    3. Retorna la información necesaria para desencriptar el QR y corroborar la identidad.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Datos encontrados y válidos para ingresar.
    - `404 Not Found`: La entrada no existe o ha sido anulada.
    """
    return {
        "id_entrada": id_entrada,
        "id_usuario": "usr-12345",
        "nombre_usuario": "Estudiante Anonimo",
        "qr_data": "https://storage.midominio.com/qr/tk-998877.png",
        "valida": True
    }

@app.get(
    "/api/v1/reservas/{id_reserva}/detalles", 
    tags=["Integración Externa (BE3) - Para Notificaciones"], 
    response_model=DetalleReservaNotificacion,
    responses={200: {"description": "Detalles recuperados exitosamente"}, 404: {"description": "Reserva no encontrada"}}
)
async def obtener_detalles_para_notificacion(id_reserva: str):
    """
    **Propósito:** Entregar información detallada de la compra a **Notificaciones** para que pueda personalizar la plantilla del correo electrónico.
    
    **Parámetros:**
    - `id_reserva` (Path): El identificador de la orden de compra.
    
    **Flujo:**
    1. Busca la reserva y cruza datos con el evento.
    2. Extrae el nombre, fecha y cantidades.
    3. Retorna el payload omitiendo datos sensibles.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Detalles de reserva listos para su consumo.
    - `404 Not Found`: El ID de reserva es incorrecto.
    """
    return {
        "id_reserva": id_reserva,
        "id_usuario": "usr-12345",
        "nombre_evento": "Gala de Informática",
        "fecha_evento": "2026-11-15T20:00:00Z",
        "cantidad_entradas": 2
    }

@app.get(
    "/api/v1/inventario/{id_evento}/stock-validacion", 
    tags=["Integración Externa (BE3) - Para Panel Organizador"], 
    response_model=StockValidacionResponse,
    responses={200: {"description": "Validación exitosa"}, 404: {"description": "Evento sin inventario registrado"}}
)
async def validar_stock_para_panel(id_evento: str):
    """
    **Propósito:** Informar al **Panel Organizador** si un evento posee compras asociadas, bloqueando su posible eliminación desde el catálogo principal.
    
    **Parámetros:**
    - `id_evento` (Path): ID del evento que se intenta borrar.
    
    **Flujo:**
    1. El Panel Organizador consulta este endpoint antes de borrar el evento.
    2. Inventario evalúa si hay entradas reservadas o compradas.
    3. Retorna el flag `permite_eliminar` bloqueando o habilitando la operación en el front.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Validación calculada sin errores.
    - `404 Not Found`: El evento no tiene historial de control de stock.
    """
    return {
        "id_evento": id_evento,
        "stock_actual": 148,
        "cantidad_entrada_reservada": 1,
        "cantidad_entrada_comprada": 1,
        "permite_eliminar": False # No permite eliminar si ya hay compras
    }

@app.post(
    "/api/v1/reservas/{id_reserva}/webhook-pago", 
    tags=["Simulación RabbitMQ - Pago Aprobado"],
    responses={200: {"description": "Proceso de emisión completado"}, 400: {"description": "Pago rechazado o inválido"}}
)
async def procesar_pago_aprobado(id_reserva: str):
    """
    **Propósito:** Simular el momento en el que se recibe el evento asíncrono de `PagoAprobado` (Originalmente vía RabbitMQ) para disparar la emisión definitiva (HU-09).
    
    **Parámetros:**
    - `id_reserva` (Path): El ID de la reserva consolidada.
    
    **Flujo:**
    1. Escucha la aprobación del flujo de dinero.
    2. Se consolida el ticket de acceso y se genera la metadata del código QR.
    3. **Check-in:** Envío en paralelo del ticket a la API de control en puerta.
    4. **Notificaciones:** Envío en paralelo de orden de correo electrónico al cliente.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Flujo de validación post-pago finalizado de manera exitosa.
    - `400 Bad Request`: Inconsistencia en la simulación del webhook.
    """
    id_usuario = "usr-12345"
    id_evento = "evt-77889"
    qr_data = "https://storage.midominio.com/qr/tk-998877.png"

    await CheckinService.registrar_ticket_puerta("tk-998877", id_evento, id_usuario, qr_data)
    await NotificacionesService.enviar_ticket_correo(id_usuario, "Gala de Informática", "2026-11-15T20:00:00Z", qr_data)

    return {"message": "Ticket emitido y notificaciones distribuidas correctamente."}
