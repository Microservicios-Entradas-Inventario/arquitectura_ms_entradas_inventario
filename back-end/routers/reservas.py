from fastapi import APIRouter, HTTPException
from database import get_database
from schemas.entradas import (
    CrearReservaHoldRequest, 
    CrearReservaHoldResponse, 
    DetalleReservaResponse
)
from services.notificaciones_service import NotificacionesService
from services.checkin_service import CheckinService
from services.broker_service import BrokerService
from datetime import datetime, timedelta
import asyncio
import uuid

router = APIRouter()

# ============================================================================
# HU-03: Reserva Temporal de Cupo (Hold)
# ============================================================================
@router.post(
    "/hold",
    tags=["Reservas (HU-03)"],
    response_model=CrearReservaHoldResponse,
    responses={
        200: {"description": "Cupo reservado temporalmente con holdId generado"},
        400: {"description": "Stock insuficiente, cantidad inválida o evento cancelado"},
        404: {"description": "El evento especificado no existe"},
        500: {"description": "Error interno del servidor o BD"}
    }
)
async def crear_reserva_hold(solicitud: CrearReservaHoldRequest):
    """
    ### 🎟️ HU-03: Reserva Temporal de Cupo
    **Propósito:** Descuenta temporalmente los cupos solicitados del stock disponible y genera
    un identificador único de reserva (`holdId` / `id_reserva`) con un tiempo límite de vigencia
    para permitir al cliente completar el proceso de checkout.
    
    ### ⏱️ Reglas de Negocio:
    1. Descuenta temporalmente del stock disponible (`stock_actual`) y lo añade a `cantidad_entrada_reservada`.
    2. Establece un tiempo de expiración (por defecto 15 minutos).
    3. Si no se recibe pago dentro del plazo, el sistema libera automáticamente los cupos al pool disponible.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    if solicitud.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")

    evento = await db.inventario_evento.find_one({"id_evento": solicitud.id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="El evento solicitado no existe")

    if evento.get("estado_gestion") == "CANCELADO":
        raise HTTPException(status_code=400, detail="El evento se encuentra cancelado")

    stock_disponible = evento.get("stock_actual", 0)
    if solicitud.cantidad > stock_disponible:
        raise HTTPException(
            status_code=400, 
            detail=f"Stock insuficiente. Disponibles: {stock_disponible}, solicitados: {solicitud.cantidad}"
        )

    # Descuento atómico temporal de cupos
    await db.inventario_evento.update_one(
        {"id_evento": solicitud.id_evento},
        {
            "$inc": {
                "stock_actual": -solicitud.cantidad,
                "cantidad_entrada_reservada": solicitud.cantidad
            }
        }
    )

    hold_id = f"hold-{uuid.uuid4().hex[:8]}"
    ahora = datetime.utcnow()
    expira_en = ahora + timedelta(minutes=solicitud.tiempo_limite_minutos)
    precio_unitario = evento.get("precio_unitario", 0)
    monto_total = precio_unitario * solicitud.cantidad

    nombre_usuario = solicitud.nombre_usuario or "Cliente en Checkout"

    doc_reserva = {
        "id_reserva": hold_id,
        "id_evento": solicitud.id_evento,
        "id_usuario": solicitud.id_usuario,
        "nombre_usuario": nombre_usuario,
        "rol_usuario": "CLIENTE",
        "cantidad_entrada": solicitud.cantidad,
        "id_promocion": None,
        "porcentaje_descuento": 0,
        "monto_total": monto_total,
        "id_pago": None,
        "estado_reserva": "RESERVADO",
        "fecha_creacion": ahora,
        "fecha_expiracion": expira_en
    }
    await db.reserva_entrada.insert_one(doc_reserva)

    # Publicar evento asíncrono al Event Broker compartido (RabbitMQ)
    asyncio.create_task(BrokerService.publish_event("entrada.reservada", {
        "id_reserva": hold_id,
        "hold_id": hold_id,
        "id_evento": solicitud.id_evento,
        "id_usuario": solicitud.id_usuario,
        "cantidad": solicitud.cantidad,
        "monto_total": monto_total,
        "fecha_expiracion": expira_en.isoformat()
    }))

    tiempo_restante_segundos = int((expira_en - ahora).total_seconds())

    return {
        "hold_id": hold_id,
        "id_reserva": hold_id,
        "id_evento": solicitud.id_evento,
        "id_usuario": solicitud.id_usuario,
        "cantidad_entrada": solicitud.cantidad,
        "monto_total": monto_total,
        "estado_reserva": "RESERVADO",
        "fecha_creacion": ahora,
        "fecha_expiracion": expira_en,
        "tiempo_restante_segundos": tiempo_restante_segundos
    }

@router.post(
    "/{id_reserva}/cancelar",
    tags=["Reservas (HU-03)"],
    responses={
        200: {"description": "Reserva cancelada y cupos liberados de inmediato"},
        400: {"description": "La reserva no está en estado RESERVADO"},
        404: {"description": "Reserva no encontrada"}
    }
)
async def cancelar_reserva_hold(id_reserva: str):
    """
    ### 🛑 HU-03: Liberación Anticipada de Cupo
    Permite al usuario o al checkout liberar voluntariamente los cupos reservados
    antes de la expiración del tiempo límite, devolviendo el stock al pool disponible.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if reserva.get("estado_reserva") != "RESERVADO":
        raise HTTPException(
            status_code=400, 
            detail=f"La reserva ya está en estado {reserva.get('estado_reserva')} y no puede cancelarse"
        )

    cantidad = reserva.get("cantidad_entrada", 1)
    id_evento = reserva["id_evento"]

    # Liberación atómica de cupos
    await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva},
        {"$set": {"estado_reserva": "CANCELADO", "fecha_cancelacion": datetime.utcnow()}}
    )
    await db.inventario_evento.update_one(
        {"id_evento": id_evento},
        {"$inc": {"stock_actual": cantidad, "cantidad_entrada_reservada": -cantidad}}
    )

    return {
        "mensaje": "Reserva cancelada exitosamente y cupos devueltos al pool disponible",
        "id_reserva": id_reserva,
        "cupos_liberados": cantidad
    }

# ============================================================================
# Simulación RabbitMQ - Webhook Pago Aprobado (HU-05)
# ============================================================================
@router.post(
    "/{id_reserva}/webhook-pago", 
    tags=["Simulación RabbitMQ - Pago Aprobado"],
    responses={200: {"description": "Proceso de emisión completado"}, 400: {"description": "Pago rechazado o inválido"}}
)
async def procesar_pago_aprobado(id_reserva: str):
    """
    ###  Propósito
    Simula la recepción asíncrona de un evento RabbitMQ ("PagoAprobado") proveniente del microservicio de Pagos. Consolida la reserva, emite las entradas definitivas y despacha operaciones en paralelo a otros microservicios.

    ###  Parámetros
    - **`id_reserva`** *(str) (Path)*: Identificador único de la reserva bloqueada temporalmente.

    ###  Flujo de Funcionamiento
    1. Se valida que la reserva exista y esté en estado `RESERVADO`.
    2. Se cambia el estado de la reserva a `CONSOLIDADO` y se remueve el tiempo de expiración (TTL).
    3. Se mueve el stock interno de la cubeta `reservada` a la cubeta `comprada`.
    4. Por cada entrada comprada, se genera un ID único, un QR (URL) y se inserta el documento definitivo en la colección `entrada`.
    5. **(Distribución Paralela)** Se ejecutan de forma asíncrona y no bloqueante las notificaciones por correo (vía mock de RabbitMQ) y el registro en puerta del microservicio Check-in.

    ###  Códigos HTTP Posibles
    - **`200 OK`**: Proceso de consolidación, emisión y distribución completado exitosamente.
    - **`400 Bad Request`**: La reserva ya fue procesada, expiró o no está en estado `RESERVADO`.
    - **`404 Not Found`**: El `id_reserva` no existe en la base de datos.
    - **`500 Internal Server Error`**: Ocurrió un problema de conexión con la base de datos MongoDB.
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
        {"$inc": {"cantidad_entrada_reservada": -cantidad, "cantidad_entrada_comprada": cantidad}}
    )
    
    id_usuario = reserva.get("id_usuario", "usr-12345")
    nombre_usuario = reserva.get("nombre_usuario", "Esteban Quinteros (Simulado)")
    correo_usuario = reserva.get("correo_usuario", "esteban@ticketu.com")
    id_evento = reserva["id_evento"]
    
    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    nombre_evento = evento.get("nombre_evento", f"Evento {id_evento}") if evento else f"Evento {id_evento}"
    fecha_evento = evento.get("fecha_evento", "2026-11-20") if evento else "2026-11-20"
    hora_evento = evento.get("hora_evento", "20:00") if evento else "20:00"
    lugar_ingreso = evento.get("lugar_ingreso", "Puerta Principal - Acceso General") if evento else "Puerta Principal - Acceso General"
    
    entradas_generadas = []

    for i in range(cantidad):
        id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
        qr_data_url = f"https://storage.midominio.com/qr/{id_entrada}.png"
        # Estructura del QR para Check-in conforme a regla de negocio v2.1 (objeto JSON con id_evento e id_entrada)
        qr_checkin = {
            "id_evento": id_evento,
            "id_entrada": id_entrada
        }
        
        qr_obj = {
            "url": qr_data_url,
            "hash": uuid.uuid4().hex[:7]
        }
        
        doc_entrada = {
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rol_usuario": "CLIENTE",
            "tipo_acceso": "GENERAL",  # Criterio 1 HU-04: Acceso general sin mapas numerados
            "precio_final_pagado": reserva.get("monto_total", 0) // cantidad,  # Criterio 2 HU-04: Precio final inmutable
            "estado_entrada": "EMITIDA",
            "nombre_archivo_qr": f"{id_entrada}.png",
            "qr_data": qr_obj,
            "fecha_emision": datetime.utcnow()
        }
        await db.entrada.insert_one(doc_entrada)
        entradas_generadas.append(id_entrada)
        
        # Despacho en paralelo a Check-in (v2.1) y Notificaciones (v3) - HU-05
        asyncio.create_task(CheckinService.registrar_ticket_puerta(
            id_entrada=id_entrada, 
            id_evento=id_evento, 
            nombre_usuario=nombre_usuario, 
            qr_data=qr_checkin
        ))
        asyncio.create_task(NotificacionesService.enviar_ticket_correo(
            correo_comprador=correo_usuario, 
            nombre_comprador=nombre_usuario, 
            id_usuario=id_usuario,
            nombre_evento=nombre_evento, 
            id_evento=id_evento,
            fecha_evento=fecha_evento, 
            hora_evento=hora_evento, 
            qr_data=qr_data_url
        ))
        # Publicar evento entrada.emitida al Event Broker compartido
        asyncio.create_task(BrokerService.publish_event("entrada.emitida", {
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_evento": id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": reserva.get("monto_total", 0) // cantidad,
            "qr_data": qr_obj,
            "fecha_emision": doc_entrada["fecha_emision"].isoformat()
        }))

    return {
        "message": "Ticket emitido y notificaciones distribuidas correctamente.",
        "entradas_emitidas": entradas_generadas
    }

# ============================================================================
# Consulta de Reserva (BE3 Pagos y HU-03 Hold con tiempo restante)
# ============================================================================
@router.get(
    "/{id_reserva}", 
    tags=["Servicios Provistos (BE3) - Pagos", "Reservas (HU-03)"],
    response_model=DetalleReservaResponse,
    responses={
        200: {"description": "Datos de la reserva retornados exitosamente con tiempo restante"},
        404: {"description": "Reserva no encontrada"},
        500: {"description": "Error interno del servidor"}
    }
)
async def consultar_reserva_pagos(id_reserva: str):
    """
    ###  Propósito
    Proporciona al microservicio de Pagos y al Checkout del Frontend la información esencial
    de una reserva (monto total, cantidad, estado y tiempo restante en pantalla).
    
    ### ⏱️ Control Automático de Expiración (HU-03):
    Si el tiempo límite de la reserva transcurrió sin confirmación de pago, el cupo se libera
    inmediatamente al pool de stock disponible y se retorna el estado `EXPIRADO`.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")
        
    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada.")

    estado_reserva = reserva.get("estado_reserva", "DESCONOCIDO")
    fecha_expiracion = reserva.get("fecha_expiracion")
    ahora = datetime.utcnow()
    expirada = False
    tiempo_restante_segundos = 0

    if fecha_expiracion is not None:
        if ahora > fecha_expiracion and estado_reserva == "RESERVADO":
            # Liberación automática inmediata por timeout (Criterio 2 HU-03)
            expirada = True
            estado_reserva = "EXPIRADO"
            cantidad = reserva.get("cantidad_entrada", 1)
            id_evento = reserva["id_evento"]

            await db.reserva_entrada.update_one(
                {"id_reserva": id_reserva},
                {"$set": {"estado_reserva": "EXPIRADO"}}
            )
            await db.inventario_evento.update_one(
                {"id_evento": id_evento},
                {"$inc": {"stock_actual": cantidad, "cantidad_entrada_reservada": -cantidad}}
            )
            print(f"[HU-03 On-Read Release] Reserva '{id_reserva}' expiró al ser consultada. Se liberaron {cantidad} cupo(s).")
        else:
            tiempo_restante_segundos = max(0, int((fecha_expiracion - ahora).total_seconds()))
        
    return {
        "id_reserva": reserva["id_reserva"],
        "hold_id": reserva.get("hold_id", reserva["id_reserva"]),
        "id_evento": reserva.get("id_evento", ""),
        "id_usuario": reserva.get("id_usuario", ""),
        "monto_total": reserva.get("monto_total", 0),
        "cantidad_entrada": reserva.get("cantidad_entrada", 0),
        "estado_reserva": estado_reserva,
        "fecha_expiracion": fecha_expiracion,
        "tiempo_restante_segundos": tiempo_restante_segundos,
        "expirada": expirada
    }

