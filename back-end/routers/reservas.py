from fastapi import APIRouter, HTTPException, Header, Cookie
from database import get_database
from schemas.entradas import (
    CrearReservaHoldRequest, 
    CrearReservaHoldResponse, 
    DetalleReservaResponse,
    IniciarPagoReservaRequest,
    AnularPagoReservaRequest
)
from services.auth_service import AuthService
from services.pagos_service import PagosService
from services.notificaciones_service import NotificacionesService
from services.checkin_service import CheckinService
from services.broker_service import BrokerService
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import asyncio
import uuid

router = APIRouter()


async def consolidar_y_emitir_entradas(
    db,
    reserva: Dict[str, Any],
    id_pago: Optional[str] = None
) -> List[str]:
    """
    Consolida una reserva en estado RESERVADO cuando el pago pasa a APROBADO (Contrato Pagos v2.2, Sección 3 y 5)
    y emite las entradas con código QR, notificando a Check-in, Notificaciones y RabbitMQ.
    """
    id_reserva = reserva["id_reserva"]
    update_fields: Dict[str, Any] = {
        "estado_reserva": "CONSOLIDADO",
        "fecha_expiracion": None
    }
    if id_pago:
        update_fields["id_pago"] = id_pago

    res_update = await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva, "estado_reserva": "RESERVADO"},
        {"$set": update_fields}
    )
    if res_update.modified_count == 0:
        # Si ya fue consolidada previamente (idempotencia), retornar las entradas ya emitidas
        cursor = db.entrada.find({"id_reserva": id_reserva})
        existentes = await cursor.to_list(length=100)
        return [e["id_entrada"] for e in existentes if "id_entrada" in e]

    cantidad = reserva.get("cantidad_entrada", 1)
    id_evento = reserva["id_evento"]

    await db.inventario_evento.update_one(
        {"id_evento": id_evento},
        {"$inc": {"cantidad_entrada_reservada": -cantidad, "cantidad_entrada_comprada": cantidad}}
    )

    id_usuario = reserva.get("id_usuario", "usr-12345")
    nombre_usuario = reserva.get("nombre_usuario", "Cliente")
    rut_usuario = reserva.get("rut_usuario")
    correo_usuario = reserva.get("correo_usuario", "cliente@ticketu.com")

    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    nombre_evento = evento.get("nombre_evento", f"Evento {id_evento}") if evento else f"Evento {id_evento}"
    fecha_evento = evento.get("fecha_evento", "2026-11-20") if evento else "2026-11-20"
    hora_evento = evento.get("hora_evento", "20:00") if evento else "20:00"

    entradas_generadas: List[str] = []

    for _ in range(cantidad):
        id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
        qr_data_url = f"https://storage.midominio.com/qr/{id_entrada}.png"
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
            "id_evento": id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_usuario,
            "rol_usuario": reserva.get("rol_usuario", "usuario"),
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": reserva.get("monto_total", 0) // max(1, cantidad),
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
        asyncio.create_task(BrokerService.publish_event("entrada.emitida", {
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_evento": id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_usuario,
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": doc_entrada["precio_final_pagado"],
            "qr_data": qr_obj,
            "fecha_emision": doc_entrada["fecha_emision"].isoformat()
        }))

    return entradas_generadas


async def liberar_reserva_y_anular_pago(
    db,
    reserva: Dict[str, Any],
    nuevo_estado: str = "EXPIRADO",
    motivo: str = "Hold de la reserva vencido: el usuario pagó fuera de plazo",
    token_sesion: Optional[str] = None,
    anular_en_pagos: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Libera los cupos de una reserva en estado RESERVADO y, si tiene un id_pago asociado,
    invoca a Pagos (Operación 4: POST /api/v1/pagos/{id_pago}/reembolso) para anular o reembolsar el pago.
    """
    id_reserva = reserva["id_reserva"]
    cantidad = reserva.get("cantidad_entrada", 1)
    id_evento = reserva["id_evento"]
    id_pago = reserva.get("id_pago")
    token_para_pagos = token_sesion or reserva.get("token_sesion")

    res_update = await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva, "estado_reserva": "RESERVADO"},
        {"$set": {"estado_reserva": nuevo_estado, "fecha_cancelacion": datetime.utcnow()}}
    )
    if res_update.modified_count > 0:
        await db.inventario_evento.update_one(
            {"id_evento": id_evento},
            {"$inc": {"stock_actual": cantidad, "cantidad_entrada_reservada": -cantidad}}
        )

    resultado_pagos = None
    if anular_en_pagos and id_pago:
        resultado_pagos = await PagosService.anular_pago(
            id_pago=id_pago,
            motivo=motivo,
            token_sesion=token_para_pagos
        )
    return resultado_pagos


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
        401: {"description": "NO_AUTENTICADO: Token inválido o rechazado por Auth"},
        404: {"description": "El evento especificado no existe"},
        503: {"description": "AUTH_NO_DISPONIBLE: Servicio de Auth no disponible"},
        500: {"description": "Error interno del servidor o BD"}
    }
)
async def crear_reserva_hold(
    solicitud: CrearReservaHoldRequest,
    authorization: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None)
):
    """
    ### 🎟️ HU-03: Reserva Temporal de Cupo
    **Propósito:** Descuenta temporalmente los cupos solicitados del stock disponible y genera
    un identificador único de reserva (`holdId` / `id_reserva`) con un tiempo límite de vigencia
    para permitir al cliente completar el proceso de checkout.
    
    ### 🔐 Integración con Auth (Contrato Pagos v2.2):
    Si se envía el token de sesión (`Authorization: Bearer`, `token_sesion` o cookie `jwt`), se valida
    la sesión con Auth y se obtienen de ahí los datos del comprador (**nombre, RUT y correo**), sin
    que el cliente tenga que rellenarlos a mano en la pantalla de pago.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    if solicitud.cantidad <= 0 or solicitud.cantidad > 100:
        raise HTTPException(status_code=400, detail="La cantidad debe estar entre 1 y 100")

    token_bruto = authorization or solicitud.token_sesion or jwt
    token_jwt = AuthService.extraer_jwt(token_bruto or "")

    id_usuario = solicitud.id_usuario
    nombre_usuario = solicitud.nombre_usuario
    rut_usuario = solicitud.rut_usuario
    correo_usuario = solicitud.correo_usuario
    rol_usuario = "usuario"

    if token_jwt:
        usuario_auth = await AuthService.validar_sesion(token_jwt)
        id_usuario = usuario_auth.get("id_usuario") or id_usuario
        nombre_usuario = usuario_auth.get("nombre") or usuario_auth.get("nombre_completo") or nombre_usuario
        rut_usuario = usuario_auth.get("rut") or rut_usuario
        correo_usuario = usuario_auth.get("correo") or usuario_auth.get("correo_electronico") or correo_usuario
        rol_usuario = (usuario_auth.get("rol") or "usuario").lower()

    if not id_usuario:
        raise HTTPException(status_code=400, detail="Se requiere un token_sesion válido de Auth o el campo id_usuario.")

    nombre_usuario = nombre_usuario or "Cliente en Checkout"

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

    doc_reserva = {
        "id_reserva": hold_id,
        "id_evento": solicitud.id_evento,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "rut_usuario": rut_usuario,
        "correo_usuario": correo_usuario,
        "rol_usuario": rol_usuario,
        "cantidad_entrada": solicitud.cantidad,
        "id_promocion": None,
        "porcentaje_descuento": 0,
        "monto_total": monto_total,
        "id_pago": None,
        "token_sesion": token_jwt or None,
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
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "rut_usuario": rut_usuario,
        "correo_usuario": correo_usuario,
        "cantidad": solicitud.cantidad,
        "monto_total": monto_total,
        "fecha_expiracion": expira_en.isoformat()
    }))

    tiempo_restante_segundos = int((expira_en - ahora).total_seconds())

    return {
        "hold_id": hold_id,
        "id_reserva": hold_id,
        "id_evento": solicitud.id_evento,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "rut_usuario": rut_usuario,
        "correo_usuario": correo_usuario,
        "cantidad_entrada": solicitud.cantidad,
        "monto_total": monto_total,
        "estado_reserva": "RESERVADO",
        "fecha_creacion": ahora,
        "fecha_expiracion": expira_en,
        "tiempo_restante_segundos": tiempo_restante_segundos
    }


@router.post(
    "/{id_reserva}/iniciar-pago",
    tags=["Reservas (HU-03)", "Integración Pagos v2.2"],
    responses={
        200: {"description": "Intención de pago creada en Pagos (devuelve id_pago y url_checkout)"},
        400: {"description": "La reserva no está en estado RESERVADO o ya expiró"},
        401: {"description": "NO_AUTENTICADO: Falta el token o Auth lo rechazó"},
        404: {"description": "Reserva no encontrada"},
        409: {"description": "CONFLICTO_IDEMPOTENCIA: La reserva ya tiene un pago con datos distintos"},
        422: {"description": "ORDEN_INCONSISTENTE: Total o cantidad no coinciden"},
        502: {"description": "ERROR_PASARELA: Stripe rechazó la operación o no respondió"},
        503: {"description": "AUTH_NO_DISPONIBLE o ENTRADAS_NO_DISPONIBLE (no se creó el pago; basta con reintentar)"}
    }
)
async def iniciar_pago_reserva(
    id_reserva: str,
    solicitud: Optional[IniciarPagoReservaRequest] = None,
    authorization: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None)
):
    """
    ### 💳 Operación 2 (Contrato Pagos ↔ Entradas v2.2): Crear intención de pago para una reserva
    Invoca `POST /api/v1/pagos/transacciones` enviando el JWT del comprador emitido por Auth.
    - Almacena únicamente `id_pago` como referencia en la reserva (ignora `client_secret`).
    - Retorna `url_checkout` para redirigir al comprador a la pantalla de pago.
    - Si Pagos responde `503 AUTH_NO_DISPONIBLE`, no se crea ni modifica ningún pago y basta con reintentar.
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
            detail=f"La reserva se encuentra en estado {reserva.get('estado_reserva')} y no admite iniciar cobro."
        )

    # Priorizar header Authorization si vienen ambos (Sección 2.5 Contrato Pagos v2.2)
    token_body = solicitud.token_sesion if solicitud else None
    token_bruto = authorization or token_body or jwt or reserva.get("token_sesion")
    token_jwt = AuthService.extraer_jwt(token_bruto or "")
    if not token_jwt:
        raise HTTPException(
            status_code=401,
            detail={"error": "NO_AUTENTICADO", "mensaje": "Falta el token de sesión emitido por Auth."}
        )

    metodo = solicitud.metodo if solicitud and solicitud.metodo else "formulario"

    pago = await PagosService.iniciar_cobro(
        id_reserva=id_reserva,
        total=int(reserva.get("monto_total", 0)),
        cantidad_entradas=int(reserva.get("cantidad_entrada", 1)),
        token_sesion=token_jwt,
        id_evento=reserva.get("id_evento"),
        metodo=metodo
    )

    if not pago or pago.get("estado_pago") == "ERROR" or not pago.get("id_pago"):
        status_code = pago.get("codigo_http", 503) if isinstance(pago, dict) else 503
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": pago.get("error", "ERROR_PAGOS") if isinstance(pago, dict) else "ERROR_PAGOS",
                "mensaje": pago.get("mensaje", "No se pudo iniciar el pago") if isinstance(pago, dict) else "No se pudo iniciar el pago",
                "detalles": pago.get("detalles", []) if isinstance(pago, dict) else [],
                "reintentable": pago.get("reintentable", status_code == 503) if isinstance(pago, dict) else True
            }
        )

    # Guardar solo id_pago como referencia (Regla Sección 2.6 y 5) y actualizar token_sesion para polling
    await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva},
        {"$set": {"id_pago": pago["id_pago"], "token_sesion": token_jwt}}
    )

    return pago


@router.get(
    "/{id_reserva}/estado-pago",
    tags=["Reservas (HU-03)", "Integración Pagos v2.2"],
    responses={
        200: {"description": "Estado actual del pago consultado en Pagos (consolidando o liberando reserva si es final)"},
        401: {"description": "NO_AUTENTICADO: Falta el token o Auth lo rechazó"},
        404: {"description": "Reserva o pago no encontrado"},
        503: {"description": "AUTH_NO_DISPONIBLE: Auth no respondió; reintentar más tarde"}
    }
)
async def consultar_estado_pago_reserva(
    id_reserva: str,
    authorization: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None)
):
    """
    ### 🔍 Operación 3 (Contrato Pagos ↔ Entradas v2.2): Consultar estado del pago (Polling)
    Consulta `GET /api/v1/pagos/{id_pago}` enviando `Authorization: Bearer <JWT>`.
    - Si `estado_pago == "APROBADO"`, consolida la reserva y emite las entradas con QR automáticamente.
    - Si `estado_pago` es `"RECHAZADO"`, `"ANULADO"` o `"REEMBOLSADO"`, libera el stock reservado.
    - Si Pagos responde `503 AUTH_NO_DISPONIBLE`, informa que es reintentable sin alterar la reserva.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    id_pago = reserva.get("id_pago")
    if not id_pago:
        raise HTTPException(status_code=404, detail="La reserva aún no tiene un id_pago asociado")

    token_bruto = authorization or jwt or reserva.get("token_sesion")
    token_jwt = AuthService.extraer_jwt(token_bruto or "")

    info_pago = await PagosService.consultar_estado_pago(id_pago=id_pago, token_sesion=token_jwt)
    codigo_http = info_pago.get("codigo_http")
    codigo_error = info_pago.get("error")

    if codigo_http == 401 or codigo_error == "NO_AUTENTICADO":
        raise HTTPException(status_code=401, detail=info_pago)
    if codigo_http == 503 and codigo_error == "AUTH_NO_DISPONIBLE":
        raise HTTPException(status_code=503, detail=info_pago)

    estado_pago = info_pago.get("estado_pago", "DESCONOCIDO")
    entradas_emitidas: List[str] = []

    if estado_pago == "APROBADO" and reserva.get("estado_reserva") == "RESERVADO":
        entradas_emitidas = await consolidar_y_emitir_entradas(db, reserva, id_pago=id_pago)
    elif estado_pago in ("RECHAZADO", "ANULADO", "REEMBOLSADO") and reserva.get("estado_reserva") == "RESERVADO":
        await liberar_reserva_y_anular_pago(
            db,
            reserva,
            nuevo_estado="EXPIRADO" if estado_pago == "RECHAZADO" else "CANCELADO",
            anular_en_pagos=False
        )

    return {
        "id_reserva": id_reserva,
        "id_pago": id_pago,
        "estado_pago": estado_pago,
        "estado_reserva": "CONSOLIDADO" if estado_pago == "APROBADO" else reserva.get("estado_reserva"),
        "entradas_emitidas": entradas_emitidas,
        "detalle_pago": info_pago
    }


@router.post(
    "/{id_reserva}/cancelar",
    tags=["Reservas (HU-03)"],
    responses={
        200: {"description": "Reserva cancelada, cupos liberados y pago anulado/reembolsado si existía"},
        400: {"description": "La reserva no está en estado RESERVADO"},
        404: {"description": "Reserva no encontrada"}
    }
)
async def cancelar_reserva_hold(
    id_reserva: str,
    solicitud: Optional[AnularPagoReservaRequest] = None,
    authorization: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None)
):
    """
    ### 🛑 HU-03 y Operación 4 (Pagos v2.2): Liberación de Cupo y Anulación/Reembolso de Pago
    Permite liberar voluntariamente los cupos reservados antes o al expirar el tiempo límite,
    devolviendo el stock al pool disponible. Si la reserva ya tenía un `id_pago` creado en Pagos,
    invoca `POST /api/v1/pagos/{id_pago}/reembolso` con el JWT del comprador o staff para anular o reembolsar el pago.
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
    token_body = solicitud.token_sesion if solicitud else None
    token_bruto = authorization or token_body or jwt or reserva.get("token_sesion")
    token_jwt = AuthService.extraer_jwt(token_bruto or "")
    motivo = (
        solicitud.motivo
        if solicitud and solicitud.motivo
        else "Reserva cancelada: liberación de cupos y anulación de pago"
    )

    resultado_pagos = await liberar_reserva_y_anular_pago(
        db=db,
        reserva=reserva,
        nuevo_estado="CANCELADO",
        motivo=motivo,
        token_sesion=token_jwt,
        anular_en_pagos=True
    )

    return {
        "mensaje": "Reserva cancelada exitosamente y cupos devueltos al pool disponible",
        "id_reserva": id_reserva,
        "cupos_liberados": cantidad,
        "id_pago": reserva.get("id_pago"),
        "resultado_reembolso_pagos": resultado_pagos
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
    Simula la recepción asíncrona de un evento RabbitMQ ("PagoAprobado") o confirmación desde Pagos. Consolida la reserva, emite las entradas definitivas y despacha operaciones en paralelo a otros microservicios.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")
        
    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
        
    if reserva.get("estado_reserva") != "RESERVADO":
        raise HTTPException(status_code=400, detail="La reserva no está en estado RESERVADO")
        
    entradas_generadas = await consolidar_y_emitir_entradas(db, reserva)

    return {
        "message": "Ticket emitido y notificaciones distribuidas correctamente.",
        "entradas_emitidas": entradas_generadas
    }


# ============================================================================
# Consulta de Reserva (BE3 Pagos INT-01 y HU-03 Hold con tiempo restante)
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
async def consultar_reserva_pagos(
    id_reserva: str,
    authorization: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None)
):
    """
    ###  Propósito
    Proporciona al microservicio de Pagos (`GET /api/v1/entradas/reservas/{id_reserva}`, INT-01 #29) y al Checkout del Frontend
    la información esencial de una reserva (monto total, cantidad, estado y tiempo restante en pantalla).
    
    ### ⏱️ Control Automático de Expiración y Anulación en Pagos (HU-03 + Contrato Pagos v2.2):
    Si el tiempo límite de la reserva transcurrió sin confirmación de pago, el cupo se libera
    inmediatamente al pool de stock disponible, se retorna el estado `EXPIRADO` y, si existía un `id_pago`,
    se solicita la anulación/reembolso a Pagos (`POST /api/v1/pagos/{id_pago}/reembolso`).
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
            # Liberación automática inmediata por timeout (Criterio 2 HU-03) + Anulación en Pagos v2.2
            expirada = True
            estado_reserva = "EXPIRADO"
            cantidad = reserva.get("cantidad_entrada", 1)
            token_bruto = authorization or jwt or reserva.get("token_sesion")
            token_jwt = AuthService.extraer_jwt(token_bruto or "")

            await liberar_reserva_y_anular_pago(
                db=db,
                reserva=reserva,
                nuevo_estado="EXPIRADO",
                motivo="Hold de la reserva vencido: el usuario pagó fuera de plazo",
                token_sesion=token_jwt,
                anular_en_pagos=True
            )
            print(f"[HU-03 On-Read Release] Reserva '{id_reserva}' expiró al ser consultada. Se liberaron {cantidad} cupo(s).")
        else:
            tiempo_restante_segundos = max(0, int((fecha_expiracion - ahora).total_seconds()))

    monto_total = reserva.get("monto_total", 0)
    cantidad_entrada = reserva.get("cantidad_entrada", 0)
        
    return {
        "id_reserva": reserva["id_reserva"],
        "hold_id": reserva.get("hold_id", reserva["id_reserva"]),
        "id_evento": reserva.get("id_evento", ""),
        "id_usuario": reserva.get("id_usuario", ""),
        "nombre_usuario": reserva.get("nombre_usuario"),
        "rut_usuario": reserva.get("rut_usuario"),
        "correo_usuario": reserva.get("correo_usuario"),
        "monto_total": monto_total,
        "total": monto_total,
        "cantidad_entrada": cantidad_entrada,
        "cantidad_entradas": cantidad_entrada,
        "id_pago": reserva.get("id_pago"),
        "estado_reserva": estado_reserva,
        "fecha_expiracion": fecha_expiracion,
        "tiempo_restante_segundos": tiempo_restante_segundos,
        "expirada": expirada
    }
