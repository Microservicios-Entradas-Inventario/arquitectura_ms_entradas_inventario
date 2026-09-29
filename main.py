from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List, Optional
from services.promociones_service import PromocionesService
from services.catalogo_service import CatalogoService
from services.pagos_service import PagosService
from services.checkin_service import CheckinService
from services.notificaciones_service import NotificacionesService
from services.panel_service import PanelService
from services.auth_service import AuthService
from contextlib import asynccontextmanager
from database import connect_to_mongo, close_mongo_connection, get_database
from datetime import datetime, timedelta
import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="TicketU - API de Entradas e Inventario",
    description="Microservicio central de Entradas e Inventario. Expone servicios propios (BE1) y requeridos por otros (BE3).",
    version="1.0.0",
    lifespan=lifespan
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

class ValidarPromocionRequest(BaseModel):
    codigo_promocional: str = Field(..., description="Código de descuento ingresado por el usuario.")
    id_evento: str = Field(..., description="ID del evento asociado.")
    cantidad: int = Field(gt=0, description="Cantidad de entradas seleccionadas.")
    precio_base: int = Field(gt=0, description="Precio base o unitario total.")

class ProcesarCompraResponse(BaseModel):
    nuevo_stock: int

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
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")
        
    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
        
    return {
        "id_evento": id_evento, 
        "stock_actual": evento.get("stock_actual", 0), 
        "tipo_entrada": evento.get("tipo_entrada", "PAGADA"), 
        "precio_unitario": evento.get("precio_unitario", 0)
    }

@app.post(
    "/api/v1/entradas/promociones/validar",
    tags=["Reservas y Compras (BE1 / BE2)"],
    responses={
        200: {"description": "Validación exitosa del código promocional"},
        401: {"description": "Cookie de sesión inválida"},
        403: {"description": "No tiene permisos para validar promociones"}
    }
)
async def validar_promocion(promo_req: ValidarPromocionRequest, cookie: Optional[str] = Header(None)):
    """
    **Propósito:** Interfaz expuesta para que el Frontend de Checkout valide un código promocional en tiempo real 
    (Implementación del Contrato Promociones v1.0).
    """
    if not cookie:
        raise HTTPException(status_code=401, detail="Falta cookie de sesión requerida por Auth.")
        
    usuario_auth = await AuthService.validar_sesion(cookie)
    id_usuario = usuario_auth.get("id_usuario")
    rol_usuario = usuario_auth.get("rol", "").upper()

    if rol_usuario not in ["CLIENTE", "USUARIO"]:
        raise HTTPException(status_code=403, detail="Prohibido: Su rol no tiene permisos.")

    resultado = await PromocionesService.validar_codigo(
        nombre_codigo=promo_req.codigo_promocional,
        id_evento=promo_req.id_evento,
        cantidad_entradas=promo_req.cantidad,
        id_usuario=id_usuario,
        rol_usuario=rol_usuario,
        precio_base=promo_req.precio_base
    )
    return resultado

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

    # ==========================
    # Contrato Panel v3.0 (Validación Síncrona REST)
    # ==========================
    info_evento_panel = await PanelService.obtener_info_evento(compra.id_evento)
    if info_evento_panel and info_evento_panel.get("estado_gestion") == "CANCELADO":
        # Regla: Aplicar bloqueo automático al recibir estado_gestion: CANCELADO
        raise HTTPException(status_code=400, detail="El evento se encuentra CANCELADO. No se permiten nuevas reservas.")
    
    nombre_evt = info_evento_panel.get("nombre_evento", "Evento Desconocido") if info_evento_panel else "Evento Desconocido"
    fecha_evt = info_evento_panel.get("fecha_evento", "2026-12-01") if info_evento_panel else "2026-12-01"
    hora_evt = info_evento_panel.get("hora_evento", "00:00") if info_evento_panel else "00:00"

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")
        
    evento_db = await db.inventario_evento.find_one({"id_evento": compra.id_evento})
    if not evento_db:
        raise HTTPException(status_code=404, detail="El evento solicitado no existe en el inventario.")

    stock_actual = evento_db.get("stock_actual", 0)
    precio_unitario = evento_db.get("precio_unitario", 0)
    precio_base = precio_unitario * compra.cantidad

    if compra.cantidad > stock_actual:
        raise HTTPException(status_code=400, detail="No hay stock suficiente para esta selección.")

    nuevo_stock = stock_actual - compra.cantidad
    id_reserva = f"res-{uuid.uuid4().hex[:8]}"

    if compra.tipo_entrada.upper() == "GRATUITA":
        # Flujo de emisión directa (Sin pasar por pagos)
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {
                "$set": {"stock_actual": nuevo_stock},
                "$inc": {"cantidad_entrada_comprada": compra.cantidad}
            }
        )
        
        await db.reserva_entrada.insert_one({
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "rol_usuario": "CLIENTE",
            "cantidad_entrada": compra.cantidad,
            "id_promocion": None,
            "porcentaje_descuento": 0,
            "monto_total": 0,
            "id_pago": None,
            "estado_reserva": "CONSOLIDADO",
            "fecha_creacion": datetime.utcnow(),
            "fecha_expiracion": None
        })
        
        id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
        qr_data = f"https://storage.midominio.com/qr/gratis-{id_entrada}.png"
        
        await db.entrada.insert_one({
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_usuario": id_usuario,
            "rol_usuario": "CLIENTE",
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": 0,
            "estado_entrada": "EMITIDA",
            "nombre_archivo_qr": f"gratis-{id_entrada}.png",
            "qr_data": qr_data,
            "fecha_emision": datetime.utcnow()
        })
        
        await CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, compra.token_sesion)
        await NotificacionesService.enviar_ticket_correo(correo_usuario, nombre_usuario, nombre_evt, fecha_evt, hora_evt, qr_data)
        
        # Contrato Panel v3.0 (Asincronía vía RabbitMQ)
        if nuevo_stock == 0:
            print(f"[RabbitMQ - Mock] Evento 'entradas.evento.stock.v1' publicado para Panel -> {{'id_evento': '{compra.id_evento}', 'stock': 0}}")
        
        # Contrato Check-in v1.0
        await CheckinService.registrar_ticket_puerta(id_entrada, compra.id_evento, nombre_usuario, qr_data)

        return {"nuevo_stock": nuevo_stock}
    else:
        # Flujo Asíncrono PAGADA
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {
                "$set": {"stock_actual": nuevo_stock},
                "$inc": {"cantidad_entrada_reservada": compra.cantidad}
            }
        )
        
        expira_en = datetime.utcnow() + timedelta(minutes=15)
        await db.reserva_entrada.insert_one({
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "rol_usuario": "CLIENTE",
            "cantidad_entrada": compra.cantidad,
            "id_promocion": None,
            "porcentaje_descuento": 0,
            "monto_total": precio_base,
            "id_pago": None,
            "estado_reserva": "RESERVADO",
            "fecha_creacion": datetime.utcnow(),
            "fecha_expiracion": expira_en
        })
        
        pago = await PagosService.iniciar_cobro(
            id_reserva=id_reserva, 
            total=int(precio_base), 
            cantidad_entradas=compra.cantidad,
            token_sesion=auth_token
        )
        
        if pago and "id_seguimiento" in pago:
             await db.reserva_entrada.update_one(
                 {"id_reserva": id_reserva},
                 {"$set": {"id_pago": pago["id_seguimiento"]}}
             )
             
        await CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, compra.token_sesion)

        if nuevo_stock == 0:
            print(f"[RabbitMQ - Mock] Evento 'entradas.evento.stock.v1' publicado para Panel -> {{'id_evento': '{compra.id_evento}', 'stock': 0}}")

        return {"nuevo_stock": nuevo_stock}

# ==========================================
# SIMULACIÓN DE ASINCRONÍA (RABBITMQ)
# ==========================================

@app.post(
    "/api/v1/reservas/{id_reserva}/webhook-pago", 
    tags=["Simulación RabbitMQ - Pago Aprobado"],
    responses={200: {"description": "Proceso de emisión completado"}, 400: {"description": "Pago rechazado o inválido"}}
)
async def procesar_pago_aprobado(id_reserva: str):
    """
    **Propósito:** Simular el evento de PagoAprobado para disparar la emisión definitiva.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")
        
    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
        
    if reserva.get("estado_reserva") != "RESERVADO":
        raise HTTPException(status_code=400, detail="La reserva no está en estado RESERVADO")
        
    await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva},
        {"$set": {"estado_reserva": "CONSOLIDADO", "fecha_expiracion": None}}
    )
    
    cantidad = reserva.get("cantidad_entrada", 1)
    await db.inventario_evento.update_one(
        {"id_evento": reserva["id_evento"]},
        {
            "$inc": {
                "cantidad_entrada_reservada": -cantidad,
                "cantidad_entrada_comprada": cantidad
            }
        }
    )
    
    id_usuario = reserva.get("id_usuario", "usr-12345")
    # En un entorno real consultaríamos a Auth el perfil de usuario. 
    nombre_usuario = "Esteban Quinteros (Simulado)"
    correo_usuario = "esteban@ticketu.com"
    id_evento = reserva["id_evento"]
    
    for i in range(cantidad):
        id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
        qr_data = f"https://storage.midominio.com/qr/{id_entrada}.png"
        
        await db.entrada.insert_one({
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_usuario": id_usuario,
            "rol_usuario": "CLIENTE",
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": reserva.get("monto_total", 0) // cantidad,
            "estado_entrada": "EMITIDA",
            "nombre_archivo_qr": f"{id_entrada}.png",
            "qr_data": qr_data,
            "fecha_emision": datetime.utcnow()
        })
        
        await CheckinService.registrar_ticket_puerta(id_entrada, id_evento, nombre_usuario, qr_data)
    
    # Contrato Notificaciones v3.0 (REST HTTP)
    await NotificacionesService.enviar_ticket_correo(correo_usuario, nombre_usuario, f"Evento {id_evento}", "2026-11-15", "20:00", f"Tickets emitidos para reserva {id_reserva}")

    return {"message": "Ticket emitido y notificaciones distribuidas correctamente."}
