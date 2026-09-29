from fastapi import APIRouter, HTTPException
from database import get_database
from services.notificaciones_service import NotificacionesService
from services.checkin_service import CheckinService
from datetime import datetime
import asyncio
import uuid

router = APIRouter()

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
        
        asyncio.create_task(CheckinService.registrar_ticket_puerta(id_entrada, id_evento, nombre_usuario, qr_data))
        asyncio.create_task(NotificacionesService.enviar_ticket_correo(correo_usuario, nombre_usuario, f"Evento {id_evento}", "2026-11-15", "20:00", qr_data))

    return {"message": "Ticket emitido y notificaciones distribuidas correctamente."}

@router.get(
    "/{id_reserva}", 
    tags=["Servicios Provistos (BE3) - Pagos"],
    responses={
        200: {"description": "Datos de la reserva retornados exitosamente para verificación de orden"},
        404: {"description": "Reserva no encontrada"},
        500: {"description": "Error interno del servidor"}
    }
)
async def consultar_reserva_pagos(id_reserva: str):
    """
    ###  Propósito
    Proporciona al microservicio de Pagos la información esencial de una reserva (monto total y cantidad) para que puedan inicializar y auditar la transacción en su propia base de datos (Soporte a Contrato Pagos v2.1).

    ###  Parámetros
    - **`id_reserva`** *(str) (Path)*: Identificador único de la reserva que Pagos necesita consultar.

    ###  Flujo de Funcionamiento
    1. Se recibe el `id_reserva` por la ruta.
    2. Se busca el documento de la reserva en la colección `reserva_entrada`.
    3. Se retorna un subconjunto seguro de datos (`id_reserva`, `monto_total`, `cantidad_entrada`, `estado_reserva`) sin exponer datos sensibles del usuario.

    ###  Códigos HTTP Posibles
    - **`200 OK`**: Datos de la reserva retornados exitosamente.
    - **`404 Not Found`**: El `id_reserva` no fue encontrado (pudo haber expirado por TTL o ser inválido).
    - **`500 Internal Server Error`**: Ocurrió un problema de conexión con la base de datos MongoDB.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")
        
    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada.")
        
    return {
        "id_reserva": reserva["id_reserva"],
        "monto_total": reserva.get("monto_total", 0),
        "cantidad_entrada": reserva.get("cantidad_entrada", 0),
        "estado_reserva": reserva.get("estado_reserva", "DESCONOCIDO")
    }
