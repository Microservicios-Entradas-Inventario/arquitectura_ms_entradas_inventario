from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List, Optional
from services.promociones_service import PromocionesService
from services.catalogo_service import CatalogoService
from services.pagos_service import PagosService
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

class ProcesarCompraRequest(BaseModel):
    id_evento: str = Field(..., description="Identificador único del evento seleccionado.")
    tipo_entrada: str = Field(..., description="Tipo de entrada seleccionada (ej. General, VIP).")
    cantidad: int = Field(gt=0, description="Cantidad de entradas a comprar.")
    token_sesion: str = Field(..., description="Token de autenticación enviado por Catálogo.")
    codigo_promocional: Optional[str] = Field(None, description="Código de descuento ingresado por el usuario.")

class ProcesarCompraResponse(BaseModel):
    nuevo_stock: int

class StockPanelResponse(BaseModel):
    id_evento: str
    stock: int

# ==========================================
# ÍTEM BE1/BE2: SERVICIOS PROPIOS Y CONSUMO EXTERNO
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
    """
    return {
        "id_evento": id_evento, 
        "stock_actual": 148, 
        "tipo_entrada": "PAGADA", # Cumple HU-01: Exponer si requiere pago o es directa
        "precio_unitario": 10000
    }

@app.post(
    "/api/v1/entradas/procesar-compra", 
    tags=["Reservas y Compras (BE1 / BE2)"], 
    response_model=ProcesarCompraResponse,
    responses={
        200: {"description": "Compra procesada y stock actualizado"}, 
        400: {"description": "Parámetro ausente o inválido (ej. cantidad <= 0)"}, 
        401: {"description": "Token de sesión del cliente no válido o expirado"}, 
        403: {"description": "Sesión válida pero sin permisos según dominio Entradas"},
        404: {"description": "El evento o el tipo de entrada solicitado no existe"},
        500: {"description": "Error interno del servicio de Entradas / Inventario"},
        503: {"description": "Servicio Auth no disponible (Timeout / Caída)"}
    }
)
async def procesar_compra(compra: ProcesarCompraRequest, cookie: Optional[str] = Header(None)):
    """
    **Propósito:** Inicia la reserva y el flujo de procesamiento de compra de las entradas seleccionadas por el cliente.
    (Implementación del Contrato Catálogo v2.0, Promociones v1.0, y Notificaciones v1.1).
    """
    # Si no hay cookie en los headers, usamos el token de sesión inyectado por el payload del Catálogo 
    auth_token = cookie if cookie else compra.token_sesion
    if not auth_token:
        raise HTTPException(status_code=401, detail="Falta el token de sesión o cookie requerida.")
        
    # ==========================
    # Paso 1: Contrato Auth v3.0 (Introspección Centralizada)
    # ==========================
    usuario_auth = await AuthService.validar_sesion(auth_token)
        
    id_usuario = usuario_auth.get("id_usuario")
    nombre_usuario = usuario_auth.get("nombre_completo", "Usuario Desconocido")
    correo_usuario = usuario_auth.get("correo_electronico", "correo@ejemplo.com")
    rol_usuario = usuario_auth.get("rol", "").upper()

    if rol_usuario not in ["CLIENTE", "USUARIO"]:
        raise HTTPException(status_code=403, detail="Prohibido: Su rol no tiene permisos para realizar compras.")

    # Simulación de datos de la base de datos
    stock_actual = 148
    precio_unitario = 10000
    precio_base = precio_unitario * compra.cantidad

    if compra.cantidad > stock_actual:
        raise HTTPException(status_code=400, detail="No hay stock suficiente para esta selección.")

    nuevo_stock = stock_actual - compra.cantidad

    if compra.tipo_entrada.upper() == "GRATUITA":
        # Flujo de emisión directa (Sin pasar por pagos)
        await CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, id_usuario)
        
        # Contrato Notificaciones v1.1 (Asincronía vía RabbitMQ)
        print(f"[RabbitMQ - Mock] Evento 'entradas_emitidas' publicado para Notificaciones -> {{'correo': '{correo_usuario}', 'evento': '{compra.id_evento}'}}")
        
        # Contrato Panel v1.2 (Asincronía vía RabbitMQ)
        if nuevo_stock == 0:
            print(f"[RabbitMQ - Mock] Evento 'entradas.evento.stock.v1' publicado para Panel -> {{'id_evento': '{compra.id_evento}', 'stock': 0}}")
        
        qr_data = f"https://storage.midominio.com/qr/gratis-{compra.id_evento}.png"
        await CheckinService.registrar_ticket_puerta("tk-gratis-111", compra.id_evento, id_usuario, nombre_usuario, qr_data)

        # Retorna estrictamente el esquema que exige Catálogo
        return {"nuevo_stock": nuevo_stock}
    else:
        # ==========================
        # Contrato Promociones v1.0
        # ==========================
        if compra.codigo_promocional:
            promo = await PromocionesService.validar_codigo(
                nombre_codigo=compra.codigo_promocional,
                id_evento=compra.id_evento,
                cantidad_entradas=compra.cantidad,
                id_usuario=id_usuario,
                rol_usuario=rol_usuario,
                precio_base=precio_base
            )
            descuento = promo.get("porcentaje_descuento", 0)
        else:
            descuento = 0

        monto_total = precio_base * (1 - descuento/100)
        
        # Iniciar cobro
        pago = await PagosService.iniciar_cobro("res-98765", int(monto_total), id_usuario)
        await CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, id_usuario)

        # Contrato Panel v1.2 (Asincronía vía RabbitMQ)
        if nuevo_stock == 0:
            print(f"[RabbitMQ - Mock] Evento 'entradas.evento.stock.v1' publicado para Panel -> {{'id_evento': '{compra.id_evento}', 'stock': 0}}")

        # Retorna estrictamente el esquema que exige Catálogo
        return {"nuevo_stock": nuevo_stock}

# ==========================================
# ÍTEM BE3: SERVICIOS REQUERIDOS POR OTROS MÓDULOS
# ==========================================

@app.get(
    "/api/v1/entradas/eventos/{id_evento}/stock", 
    tags=["Integración Externa (BE3) - Para Panel Organizador"], 
    response_model=StockPanelResponse,
    responses={
        200: {"description": "Stock obtenido exitosamente"}, 
        400: {"description": "Formato de id_evento inválido"},
        404: {"description": "Evento no encontrado en Entradas / Inventario"},
        500: {"description": "Error interno de Entradas / Inventario"}
    }
)
async def consultar_stock_panel(id_evento: str):
    """
    **Propósito:** Proveer al Panel Organizador el stock actual de un evento. Se utiliza para sincronización y como validación previa antes de que Panel permita eliminar un evento.
    """
    return {
        "id_evento": id_evento,
        "stock": 148 # Simulación de stock actual
    }

@app.post(
    "/api/v1/reservas/{id_reserva}/webhook-pago", 
    tags=["Simulación RabbitMQ - Pago Aprobado"],
    responses={200: {"description": "Proceso de emisión completado"}, 400: {"description": "Pago rechazado o inválido"}}
)
async def procesar_pago_aprobado(id_reserva: str):
    """
    **Propósito:** Simular el evento de PagoAprobado para disparar la emisión definitiva.
    """
    id_usuario = "usr-12345"
    nombre_usuario = "Esteban Quinteros"
    correo_usuario = "esteban@ticketu.com"
    id_evento = "evt-77889"
    qr_data = "https://storage.midominio.com/qr/tk-998877.png"

    await CheckinService.registrar_ticket_puerta("tk-998877", id_evento, id_usuario, nombre_usuario, qr_data)
    
    # Contrato Notificaciones v1.1 (Asincronía vía RabbitMQ)
    print(f"[RabbitMQ - Mock] Evento 'entradas_emitidas' publicado para Notificaciones -> {{'correo': '{correo_usuario}', 'evento': '{id_evento}'}}")

    return {"message": "Ticket emitido y notificaciones distribuidas correctamente."}
