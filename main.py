from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List, Optional
from services.promociones_service import PromocionesService
from services.catalogo_service import CatalogoService
from services.pagos_service import PagosService
from services.notificaciones_service import NotificacionesService
from services.checkin_service import CheckinService
from services.auth_service import AuthService

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
    3. Retorna la cantidad de stock disponible y expone si la categoría es PAGADA o GRATUITA.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Datos obtenidos correctamente.
    - `404 Not Found`: No existe inventario asociado al evento solicitado.
    """
    return {
        "id_evento": id_evento, 
        "stock_actual": 148, 
        "tipo_entrada": "PAGADA", # Cumple HU-01: Exponer si requiere pago o es directa
        "precio_unitario": 10000
    }

@app.post(
    "/api/v1/reservas", 
    tags=["Reservas (BE1)"], 
    response_model=ReservaResponse,
    responses={200: {"description": "Reserva creada y cobro iniciado / Emisión directa iniciada"}, 400: {"description": "Límite superado, datos inválidos o stock insuficiente"}, 401: {"description": "Cookie no enviada o expirada en el servicio Auth."}, 403: {"description": "Sesión válida pero sin permisos según Auth."}}
)
async def crear_reserva(reserva: ReservaRequest, cookie: Optional[str] = Header(None)):
    """
    **Propósito:** Crear una reserva temporal de entradas o emitir entradas gratuitas directamente (Soporte a HU-02 y HU-03).
    
    **Parámetros:**
    - `reserva` (Body): Objeto que contiene `id_evento`, `id_usuario` y `cantidad_entradas` (debe ser mayor a 0).
    - `Cookie` (Header): Cabecera de sesión original (HttpOnly) reenviada a Auth.
    
    **Flujo:**
    1. **Autenticación (Auth v2.0):** Intercepta la Cookie, valida sesión y extrae el perfil del usuario (nombre, correo, rol).
    2. **Validación (HU-02):** Verifica que la cantidad no supere el límite máximo permitido por transacción y que exista stock suficiente.
    3. **Identificación (HU-02):** Si el evento es GRATUITO, emite el ticket directamente y lo distribuye a Check-in y Notificaciones con los datos extraídos de Auth.
    4. Si el evento es PAGADO:
       - **Promociones:** Consulta el descuento aplicable.
       - **Pagos:** Solicita a Pagos el inicio de un cobro, obteniendo un ID de pago pendiente.
    5. **Catálogo:** Actualiza el aforo restante enviando un token de sesión genérico o el ID de usuario.
    6. Retorna los detalles de la reserva junto con el estado (CONSOLIDADO para gratuitas, PENDIENTE para pagadas).
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Reserva pre-aprobada o ticket gratuito emitido exitosamente.
    - `400 Bad Request`: Límite máximo superado o stock insuficiente.
    - `401 Unauthorized`: Cookie no enviada o expirada en el servicio Auth.
    - `403 Forbidden`: Sesión válida pero sin permisos según Auth.
    """
    if not cookie:
        raise HTTPException(status_code=401, detail="Falta el encabezado Cookie requerido por Auth.")
        
    # ==========================
    # Paso 1: Contrato Auth v2.0 (Validar sesión por Cookie HttpOnly)
    # ==========================
    usuario_auth = await AuthService.validar_sesion(cookie)
    if not usuario_auth:
        raise HTTPException(status_code=401, detail="No autorizado: Cookie expirada o inválida según el servicio de Autenticación.")
        
    id_usuario = usuario_auth.get("id_usuario", reserva.id_usuario)
    nombre_usuario = usuario_auth.get("nombre", "Usuario Desconocido")
    correo_usuario = usuario_auth.get("correo", "correo@ejemplo.com")

    # Simulación de datos de la base de datos para evaluar reglas de negocio (HU-02)
    maximo_permitido = 4
    stock_actual = 148
    tipo_entrada = "PAGADA" # Imagina que esto viene de la base de datos

    # ==========================
    # Criterio de Aceptación HU-02: Validar cantidad > 0 (Pydantic) y <= límite máximo
    # ==========================
    if reserva.cantidad_entradas > maximo_permitido:
        raise HTTPException(status_code=400, detail=f"Tu selección supera el límite máximo permitido por transacción ({maximo_permitido}).")
    if reserva.cantidad_entradas > stock_actual:
        raise HTTPException(status_code=400, detail="No hay stock suficiente para esta selección.")

    # ==========================
    # Criterio de Aceptación HU-02: Direccionar flujo según categoría
    # ==========================
    if tipo_entrada == "GRATUITA":
        # Flujo de emisión directa (Sin pasar por pagos)
        await CatalogoService.actualizar_stock_catalogo(reserva.id_evento, stock_actual - reserva.cantidad_entradas, id_usuario)
        
        qr_data = f"https://storage.midominio.com/qr/gratis-{reserva.id_evento}.png"
        
        # Despachando a Check-in y Notificaciones con los datos confiables obtenidos de Auth
        await CheckinService.registrar_ticket_puerta("tk-gratis-111", reserva.id_evento, id_usuario, nombre_usuario, qr_data)
        await NotificacionesService.enviar_ticket_correo(id_usuario, correo_usuario, "Evento Gratuito", "2026-12-01T10:00:00Z", qr_data)

        return {
            "id_reserva": "res-directa-001",
            "estado": "CONSOLIDADO",
            "monto_total": 0,
            "descuento_aplicado": 0,
            "id_pago_pendiente": None
        }
    else:
        # Flujo original de Reserva Temporal y Pago (HU-03)
        promo = await PromocionesService.consultar_promocion_vigente(reserva.id_evento, id_usuario, reserva.cantidad_entradas)
        descuento = promo.get("porcentaje_descuento", 0)
        monto_total = (10000 * reserva.cantidad_entradas) * (1 - descuento/100)
        
        pago = await PagosService.iniciar_cobro("res-98765", int(monto_total), id_usuario)
        await CatalogoService.actualizar_stock_catalogo(reserva.id_evento, stock_actual - reserva.cantidad_entradas, id_usuario)

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
    3. **Check-in (Síncrono):** Envío en paralelo del ticket a la API de control en puerta.
    4. **Notificaciones (Síncrono):** Envío en paralelo de orden de correo electrónico al cliente.
    
    **Códigos HTTP Posibles:**
    - `200 OK`: Flujo de validación post-pago finalizado de manera exitosa.
    - `400 Bad Request`: Inconsistencia en la simulación del webhook.
    """
    id_usuario = "usr-12345"
    nombre_usuario = "Esteban Quinteros"
    correo_usuario = "esteban@ticketu.com"
    id_evento = "evt-77889"
    qr_data = "https://storage.midominio.com/qr/tk-998877.png"

    await CheckinService.registrar_ticket_puerta("tk-998877", id_evento, id_usuario, nombre_usuario, qr_data)
    await NotificacionesService.enviar_ticket_correo(id_usuario, correo_usuario, "Gala de Informática", "2026-11-15T20:00:00Z", qr_data)

    return {"message": "Ticket emitido y notificaciones distribuidas correctamente."}
