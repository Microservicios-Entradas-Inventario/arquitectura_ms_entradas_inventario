import os
from fastapi import APIRouter, HTTPException, Header, Cookie
from pymongo import ReturnDocument
from database import get_database
from schemas.entradas import (
    CrearReservaHoldRequest,
    CrearReservaHoldResponse,
    DetalleReservaResponse,
    IniciarPagoReservaRequest,
    AnularPagoReservaRequest,
    CancelarReservaResponse,
    EstadoPagoReservaResponse,
)
from services.auth_service import AuthService
from services.pagos_service import PagosService
from services.promociones_service import PromocionesService
from services.notificaciones_service import NotificacionesService
from services.checkin_service import CheckinService
from services.catalogo_service import CatalogoService
from services.broker_service import BrokerService
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import asyncio
import uuid

router = APIRouter()

# Almacenamiento efímero en memoria (nunca persistido en MongoDB) para reenviar cookie jwt
# durante el ciclo de vida corto de una reserva activa en estado RESERVADO.
_RESERVA_COOKIES: Dict[str, str] = {}


def guardar_cookie_reserva(id_reserva: str, cookie_header: Optional[str]) -> None:
    if id_reserva and cookie_header:
        _RESERVA_COOKIES[id_reserva] = cookie_header


def obtener_cookie_reserva(id_reserva: str) -> Optional[str]:
    return _RESERVA_COOKIES.get(id_reserva)


def limpiar_cookie_reserva(id_reserva: str) -> None:
    _RESERVA_COOKIES.pop(id_reserva, None)


async def consolidar_y_emitir_entradas(
    db,
    reserva: Dict[str, Any],
    id_pago: Optional[str] = None,
    destinatario: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Consolida una reserva en estado RESERVADO cuando el pago pasa a APROBADO
    (por evento RabbitMQ pago.realizado o polling contra Pagos) y emite las entradas
    con código QR, registrando en Check-in y notificando a Notificaciones y RabbitMQ.
    """
    id_reserva = reserva["id_reserva"]
    update_fields: Dict[str, Any] = {
        "estado_reserva": "CONSOLIDADO",
        "fecha_expiracion": None,
    }
    if id_pago:
        update_fields["id_pago"] = id_pago

    res_update = await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva, "estado_reserva": "RESERVADO"},
        {"$set": update_fields},
    )
    limpiar_cookie_reserva(id_reserva)

    if res_update.modified_count == 0:
        cursor = db.entrada.find({"id_reserva": id_reserva})
        existentes = await cursor.to_list(length=100)
        return [e["id_entrada"] for e in existentes if "id_entrada" in e]

    cantidad = int(reserva.get("cantidad_entrada", 1))
    id_evento = reserva["id_evento"]

    await db.inventario_evento.update_one(
        {"id_evento": id_evento},
        {"$inc": {"cantidad_entrada_reservada": -cantidad, "cantidad_entrada_comprada": cantidad}},
    )

    id_usuario = reserva.get("id_usuario", "")
    nombre_usuario = (
        (destinatario.get("nombre") if destinatario else None)
        or reserva.get("nombre_usuario")
        or "Asistente"
    )
    rut_usuario = (destinatario.get("rut") if destinatario else None) or reserva.get("rut_usuario")
    correo_usuario = (
        (destinatario.get("email") if destinatario else None)
        or reserva.get("correo_usuario")
        or ""
    )
    rol_usuario = (reserva.get("rol_usuario") or "usuario").lower()

    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    nombre_evento = evento.get("nombre_evento", f"Evento {id_evento}") if evento else f"Evento {id_evento}"
    fecha_evento = evento.get("fecha_evento", "") if evento else ""
    hora_evento = evento.get("hora_evento", "20:00") if evento else "20:00"
    lugar_ingreso = evento.get("lugar_ingreso", "Puerta Principal - Acceso General") if evento else "Puerta Principal - Acceso General"

    entradas_generadas: List[str] = []
    precio_unitario_pagado = int(reserva.get("monto_total", 0)) // max(1, cantidad)

    for _ in range(cantidad):
        id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
        qr_data_url = CheckinService.generar_qr_url(id_entrada, id_evento)
        qr_checkin = {"id_entrada": id_entrada, "id_evento": id_evento}
        qr_obj = {
            "url": qr_data_url,
            "hash": uuid.uuid4().hex[:7],
        }
        fecha_emision = datetime.utcnow()

        doc_entrada = {
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_evento": id_evento,
            "nombre_evento": nombre_evento,
            "lugar_ingreso": lugar_ingreso,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_usuario or None,
            "rol_usuario": rol_usuario,
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": precio_unitario_pagado,
            "estado_entrada": "EMITIDA",
            "nombre_archivo_qr": f"{id_entrada}.png",
            "qr_data": qr_obj,
            "fecha_emision": fecha_emision,
        }
        await db.entrada.insert_one(doc_entrada)
        entradas_generadas.append(id_entrada)

        await CheckinService.registrar_ticket_puerta(
            id_entrada=id_entrada,
            id_evento=id_evento,
            id_usuario=id_usuario,
            nombre_usuario=nombre_usuario,
            qr_data=qr_checkin,
        )
        if correo_usuario:
            asyncio.create_task(
                NotificacionesService.enviar_ticket_correo(
                    correo_comprador=correo_usuario,
                    nombre_comprador=nombre_usuario,
                    id_usuario=id_usuario,
                    nombre_evento=nombre_evento,
                    id_evento=id_evento,
                    fecha_evento=fecha_evento,
                    hora_evento=hora_evento,
                    qr_data=qr_data_url,
                )
            )
        asyncio.create_task(
            BrokerService.publish_event(
                "entrada.emitida",
                {
                    "id_entrada": id_entrada,
                    "id_reserva": id_reserva,
                    "id_evento": id_evento,
                    "id_usuario": id_usuario,
                    "nombre_usuario": nombre_usuario,
                    "rut_usuario": rut_usuario,
                    "correo_usuario": correo_usuario,
                    "tipo_acceso": "GENERAL",
                    "precio_final_pagado": precio_unitario_pagado,
                    "qr_data": qr_obj,
                    "fecha_emision": fecha_emision.isoformat(),
                },
            )
        )

    return entradas_generadas


async def liberar_reserva_y_anular_pago(
    db,
    reserva: Dict[str, Any],
    nuevo_estado: str = "EXPIRADO",
    motivo: str = "Hold de la reserva vencido: el usuario pagó fuera de plazo",
    cookie_header: Optional[str] = None,
    anular_en_pagos: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Libera los cupos de una reserva en estado RESERVADO, devuelve stock a MongoDB,
    sincroniza Catálogo y Panel Organizador y, si corresponde, solicita reembolso/anulación en Pagos.
    """
    id_reserva = reserva["id_reserva"]
    cantidad = int(reserva.get("cantidad_entrada", 1))
    id_evento = reserva["id_evento"]
    id_pago = reserva.get("id_pago")
    cookie_para_pagos = cookie_header or obtener_cookie_reserva(id_reserva)

    res_update = await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva, "estado_reserva": "RESERVADO"},
        {"$set": {"estado_reserva": nuevo_estado, "fecha_cancelacion": datetime.utcnow()}},
    )
    if res_update.modified_count > 0:
        evento_previo = await db.inventario_evento.find_one({"id_evento": id_evento})
        stock_anterior = int(evento_previo.get("stock_actual", 0)) if evento_previo else 0

        evento_actualizado = await db.inventario_evento.find_one_and_update(
            {"id_evento": id_evento},
            {
                "$inc": {
                    "stock_actual": cantidad,
                    "cantidad_entrada_reservada": -cantidad,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if evento_actualizado:
            nuevo_stock = int(evento_actualizado.get("stock_actual", 0))
            await CatalogoService.actualizar_stock_catalogo(
                id_evento,
                nuevo_stock,
                AuthService.extraer_jwt(cookie_para_pagos or ""),
            )
            if stock_anterior == 0 and nuevo_stock > 0:
                asyncio.create_task(
                    BrokerService.publish_event(
                        "entradas.evento.stock.v1",
                        {"id_evento": id_evento, "stock": nuevo_stock},
                    )
                )

    resultado_pagos = None
    if anular_en_pagos and id_pago:
        resultado_pagos = await PagosService.anular_pago(
            id_pago=id_pago,
            motivo=motivo,
            cookie_header=cookie_para_pagos,
        )

    limpiar_cookie_reserva(id_reserva)
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
        400: {"description": "Stock insuficiente, cantidad inválida o evento no disponible"},
        401: {"description": "NO_AUTENTICADO: Cookie 'jwt' ausente, inválida o rechazada por Auth"},
        403: {"description": "Rol o cuenta sin permisos para reservar"},
        404: {"description": "El evento especificado no existe"},
        503: {"description": "AUTH_NO_DISPONIBLE: Servicio de Auth no disponible"},
        500: {"description": "Error interno del servidor o BD"},
    },
)
async def crear_reserva_hold(
    solicitud: CrearReservaHoldRequest,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """
    ### HU-03: Reserva Temporal de Cupo (Hold)
    Descuenta atómicamente los cupos solicitados del stock disponible y genera una reserva temporal
    con vigencia controlada. Valida obligatoriamente la sesión contra Auth (`Cookie: jwt`) y
    revalida cualquier código promocional directamente contra Promociones.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    if solicitud.cantidad <= 0 or solicitud.cantidad > 100:
        raise HTTPException(status_code=400, detail="La cantidad debe estar entre 1 y 100.")

    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None) or solicitud.token_sesion
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    if not cookie_reenvio or not AuthService.extraer_jwt(cookie_reenvio):
        raise HTTPException(
            status_code=401,
            detail="NO_AUTENTICADO: Se requiere iniciar sesión (cookie 'jwt') para crear una reserva.",
        )

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)
    id_usuario = usuario_auth["id_usuario"]
    nombre_usuario = usuario_auth.get("nombre") or "Asistente"
    rut_usuario = usuario_auth.get("rut")
    correo_usuario = usuario_auth.get("correo") or None
    rol_usuario = (usuario_auth.get("rol") or "usuario").upper()

    if rol_usuario not in ("USUARIO", "CLIENTE", "STAFF", "ORGANIZADOR"):
        raise HTTPException(status_code=403, detail="El rol del usuario no tiene permisos para reservar entradas.")

    evento = await db.inventario_evento.find_one({"id_evento": solicitud.id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="El evento solicitado no existe.")

    estado_gestion = str(evento.get("estado_gestion", "PUBLICADO")).upper()
    if estado_gestion != "PUBLICADO":
        raise HTTPException(
            status_code=400,
            detail=f"El evento no admite reservas en estado '{estado_gestion}'.",
        )

    maximo_ticket = int(evento.get("maximo_ticket") or 6)
    if solicitud.cantidad > maximo_ticket:
        raise HTTPException(
            status_code=400,
            detail=f"Cantidad excede el máximo permitido de {maximo_ticket} entrada(s) por transacción.",
        )

    # Descuento atómico de stock para evitar sobreventa ante concurrencia
    evento_actualizado = await db.inventario_evento.find_one_and_update(
        {
            "id_evento": solicitud.id_evento,
            "estado_gestion": "PUBLICADO",
            "stock_actual": {"$gte": solicitud.cantidad},
        },
        {
            "$inc": {
                "stock_actual": -solicitud.cantidad,
                "cantidad_entrada_reservada": solicitud.cantidad,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not evento_actualizado:
        evento_ref = await db.inventario_evento.find_one({"id_evento": solicitud.id_evento})
        stock_disp = int(evento_ref.get("stock_actual", 0)) if evento_ref else 0
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente. Disponibles: {stock_disp}, solicitados: {solicitud.cantidad}.",
        )

    nuevo_stock = int(evento_actualizado.get("stock_actual", 0))
    await CatalogoService.actualizar_stock_catalogo(
        solicitud.id_evento,
        nuevo_stock,
        AuthService.extraer_jwt(cookie_reenvio),
    )

    if nuevo_stock == 0:
        asyncio.create_task(
            BrokerService.publish_event(
                "entradas.evento.stock.v1", {"id_evento": solicitud.id_evento, "stock": 0}
            )
        )
        asyncio.create_task(
            BrokerService.publish_event(
                "stock.agotado", {"id_evento": solicitud.id_evento, "stock": 0}
            )
        )

    hold_id = f"hold-{uuid.uuid4().hex[:8]}"
    ahora = datetime.utcnow()
    expira_en = ahora + timedelta(minutes=solicitud.tiempo_limite_minutos)
    precio_unitario = int(evento.get("precio_unitario", 0))
    precio_base = precio_unitario * solicitud.cantidad

    codigo_promo, id_promocion_real, pct_descuento, monto_total = await PromocionesService.revalidar_descuento(
        id_evento=solicitud.id_evento,
        id_usuario=id_usuario,
        cantidad_entradas=solicitud.cantidad,
        precio_base=precio_base,
        nombre_codigo=solicitud.nombre_codigo,
        id_promocion=solicitud.id_promocion,
        porcentaje_descuento=solicitud.porcentaje_descuento,
    )

    rol_bd = "usuario" if rol_usuario.lower() == "cliente" else rol_usuario.lower()

    doc_reserva = {
        "id_reserva": hold_id,
        "id_evento": solicitud.id_evento,
        "id_usuario": id_usuario,
        "nombre_usuario": nombre_usuario,
        "rut_usuario": rut_usuario,
        "correo_usuario": correo_usuario,
        "rol_usuario": rol_bd,
        "cantidad_entrada": solicitud.cantidad,
        "id_promocion": id_promocion_real,
        "nombre_codigo": codigo_promo,
        "porcentaje_descuento": pct_descuento,
        "monto_total": monto_total,
        "id_pago": None,
        "estado_reserva": "RESERVADO",
        "fecha_creacion": ahora,
        "fecha_expiracion": expira_en,
    }
    await db.reserva_entrada.insert_one(doc_reserva)
    guardar_cookie_reserva(hold_id, cookie_reenvio)

    asyncio.create_task(
        BrokerService.publish_event(
            "entrada.reservada",
            {
                "id_reserva": hold_id,
                "hold_id": hold_id,
                "id_evento": solicitud.id_evento,
                "id_usuario": id_usuario,
                "nombre_usuario": nombre_usuario,
                "rut_usuario": rut_usuario,
                "correo_usuario": correo_usuario,
                "cantidad": solicitud.cantidad,
                "monto_total": monto_total,
                "nombre_codigo": codigo_promo,
                "fecha_expiracion": expira_en.isoformat(),
            },
        )
    )

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
        "id_promocion": id_promocion_real,
        "nombre_codigo": codigo_promo,
        "porcentaje_descuento": pct_descuento,
        "monto_total": monto_total,
        "estado_reserva": "RESERVADO",
        "fecha_creacion": ahora,
        "fecha_expiracion": expira_en,
        "tiempo_restante_segundos": tiempo_restante_segundos,
    }


@router.post(
    "/{id_reserva}/iniciar-pago",
    tags=["Reservas (HU-03)", "Integración Pagos"],
    responses={
        200: {"description": "Intención de pago creada en Pagos (devuelve id_pago y url_checkout)"},
        400: {"description": "La reserva no está en estado RESERVADO o ya expiró"},
        401: {"description": "NO_AUTENTICADO: Falta la cookie 'jwt' o Auth la rechazó"},
        403: {"description": "No autorizado para iniciar pago de una reserva ajena"},
        404: {"description": "Reserva no encontrada"},
        409: {"description": "CONFLICTO_IDEMPOTENCIA: La reserva ya tiene un pago con datos distintos"},
        422: {"description": "ORDEN_INCONSISTENTE: Total o cantidad no coinciden"},
        502: {"description": "ERROR_PASARELA: Stripe rechazó la operación o no respondió"},
        503: {"description": "AUTH_NO_DISPONIBLE o ENTRADAS_NO_DISPONIBLE"},
    },
)
async def iniciar_pago_reserva(
    id_reserva: str,
    solicitud: Optional[IniciarPagoReservaRequest] = None,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """
    ### Operación 2 (Contrato Pagos ↔ Entradas): Crear intención de pago para una reserva
    Invoca `POST /api/pagos/transacciones` vía API Gateway reenviando el header `Cookie` (`jwt`).
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    token_body = solicitud.token_sesion if solicitud else None
    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None) or token_body or obtener_cookie_reserva(id_reserva)
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    if not cookie_reenvio or not AuthService.extraer_jwt(cookie_reenvio):
        raise HTTPException(
            status_code=401,
            detail={"error": "NO_AUTENTICADO", "mensaje": "Falta el header Cookie con la cookie 'jwt' emitida por Auth."},
        )

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)

    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada.")

    if reserva.get("id_usuario") != usuario_auth["id_usuario"] and usuario_auth["rol"] != "STAFF":
        raise HTTPException(status_code=403, detail="No tienes permisos para operar sobre esta reserva.")

    if reserva.get("estado_reserva") != "RESERVADO":
        raise HTTPException(
            status_code=400,
            detail=f"La reserva se encuentra en estado {reserva.get('estado_reserva')} y no admite iniciar cobro.",
        )

    metodo = solicitud.metodo if solicitud and solicitud.metodo else "formulario"

    pago = await PagosService.iniciar_cobro(
        id_reserva=id_reserva,
        total=int(reserva.get("monto_total", 0)),
        cantidad_entradas=int(reserva.get("cantidad_entrada", 1)),
        cookie_header=cookie_reenvio,
        id_evento=reserva.get("id_evento"),
        metodo=metodo,
        nombre_codigo=reserva.get("nombre_codigo"),
    )

    if not pago or pago.get("estado_pago") == "ERROR" or not pago.get("id_pago"):
        status_code = pago.get("codigo_http", 503) if isinstance(pago, dict) else 503
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": pago.get("error", "ERROR_PAGOS") if isinstance(pago, dict) else "ERROR_PAGOS",
                "mensaje": pago.get("mensaje", "No se pudo iniciar el pago") if isinstance(pago, dict) else "No se pudo iniciar el pago",
                "detalles": pago.get("detalles", []) if isinstance(pago, dict) else [],
                "reintentable": pago.get("reintentable", status_code == 503) if isinstance(pago, dict) else True,
            },
        )

    await db.reserva_entrada.update_one(
        {"id_reserva": id_reserva},
        {"$set": {"id_pago": pago["id_pago"]}},
    )
    guardar_cookie_reserva(id_reserva, cookie_reenvio)

    return pago


@router.get(
    "/{id_reserva}/estado-pago",
    tags=["Reservas (HU-03)", "Integración Pagos"],
    response_model=EstadoPagoReservaResponse,
    responses={
        200: {"description": "Estado actual del pago consultado en Pagos"},
        401: {"description": "NO_AUTENTICADO: Falta la cookie 'jwt' o Auth la rechazó"},
        403: {"description": "No autorizado para consultar el pago de otra cuenta"},
        404: {"description": "Reserva o pago no encontrado"},
        503: {"description": "AUTH_NO_DISPONIBLE o Pagos no disponible"},
    },
)
async def consultar_estado_pago_reserva(
    id_reserva: str,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """
    ### Operación 3 (Contrato Pagos ↔ Entradas): Consultar estado del pago
    Consulta `GET /api/pagos/{id_pago}` vía API Gateway y consolida o libera la reserva si alcanzó estado final.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None) or obtener_cookie_reserva(id_reserva)
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    if not cookie_reenvio or not AuthService.extraer_jwt(cookie_reenvio):
        raise HTTPException(status_code=401, detail="NO_AUTENTICADO: Se requiere cookie 'jwt' válida.")

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)

    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada.")

    if reserva.get("id_usuario") != usuario_auth["id_usuario"] and usuario_auth["rol"] != "STAFF":
        raise HTTPException(status_code=403, detail="No tienes permisos para consultar esta reserva.")

    id_pago = reserva.get("id_pago")
    if not id_pago:
        raise HTTPException(status_code=404, detail="La reserva aún no tiene un id_pago asociado.")

    info_pago = await PagosService.consultar_estado_pago(id_pago=id_pago, cookie_header=cookie_reenvio)
    codigo_http = info_pago.get("codigo_http")
    codigo_error = info_pago.get("error")

    if codigo_http == 401 or codigo_error == "NO_AUTENTICADO":
        raise HTTPException(status_code=401, detail=info_pago)
    if codigo_http == 503 and codigo_error == "AUTH_NO_DISPONIBLE":
        raise HTTPException(status_code=503, detail=info_pago)

    estado_pago = info_pago.get("estado_pago", "DESCONOCIDO")
    entradas_emitidas: List[str] = []
    estado_reserva_final = reserva.get("estado_reserva", "RESERVADO")

    if estado_pago == "APROBADO" and estado_reserva_final == "RESERVADO":
        entradas_emitidas = await consolidar_y_emitir_entradas(db, reserva, id_pago=id_pago)
        estado_reserva_final = "CONSOLIDADO"
    elif estado_pago in ("RECHAZADO", "ANULADO", "REEMBOLSADO") and estado_reserva_final == "RESERVADO":
        nuevo_est = "EXPIRADO" if estado_pago == "RECHAZADO" else "CANCELADO"
        await liberar_reserva_y_anular_pago(
            db,
            reserva,
            nuevo_estado=nuevo_est,
            anular_en_pagos=False,
        )
        estado_reserva_final = nuevo_est

    return {
        "id_reserva": id_reserva,
        "id_pago": id_pago,
        "estado_pago": estado_pago,
        "estado_reserva": estado_reserva_final,
        "entradas_emitidas": entradas_emitidas,
        "detalle_pago": info_pago,
    }


@router.post(
    "/{id_reserva}/cancelar",
    tags=["Reservas (HU-03)"],
    response_model=CancelarReservaResponse,
    responses={
        200: {"description": "Reserva cancelada, cupos liberados y pago anulado/reembolsado si existía"},
        400: {"description": "La reserva no está en estado RESERVADO"},
        401: {"description": "NO_AUTENTICADO: Falta cookie 'jwt' o Auth la rechazó"},
        403: {"description": "No autorizado para cancelar una reserva ajena"},
        404: {"description": "Reserva no encontrada"},
    },
)
async def cancelar_reserva_hold(
    id_reserva: str,
    solicitud: Optional[AnularPagoReservaRequest] = None,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """
    ### HU-03 y Operación 4 (Contrato Pagos): Liberación de Cupo y Anulación/Reembolso
    Libera los cupos reservados devolviendo el stock al inventario y notificando a Catálogo/Panel.
    Si la reserva tenía un `id_pago` asociado, invoca `POST /api/pagos/{id_pago}/reembolso`.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    token_body = solicitud.token_sesion if solicitud else None
    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None) or token_body
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    if not cookie_reenvio or not AuthService.extraer_jwt(cookie_reenvio):
        raise HTTPException(status_code=401, detail="NO_AUTENTICADO: Se requiere cookie 'jwt' válida para cancelar la reserva.")

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)

    reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada.")

    if reserva.get("id_usuario") != usuario_auth["id_usuario"] and usuario_auth["rol"] not in ("STAFF", "ORGANIZADOR"):
        raise HTTPException(status_code=403, detail="No tienes permisos para cancelar esta reserva.")

    if reserva.get("estado_reserva") != "RESERVADO":
        raise HTTPException(
            status_code=400,
            detail=f"La reserva ya está en estado {reserva.get('estado_reserva')} y no puede cancelarse.",
        )

    cantidad = int(reserva.get("cantidad_entrada", 1))
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
        cookie_header=cookie_reenvio,
        anular_en_pagos=True,
    )

    return {
        "mensaje": "Reserva cancelada exitosamente y cupos devueltos al pool disponible.",
        "id_reserva": id_reserva,
        "cupos_liberados": cantidad,
        "id_pago": reserva.get("id_pago"),
        "resultado_reembolso_pagos": resultado_pagos,
    }


# ============================================================================
# Webhook simulado deshabilitado por defecto en workstation (solo pruebas locales explícitas)
# ============================================================================
@router.post(
    "/{id_reserva}/webhook-pago",
    tags=["Pruebas Internas"],
    include_in_schema=False,
    responses={
        200: {"description": "Proceso de emisión completado (solo si ALLOW_SIMULATED_WEBHOOK=true)"},
        403: {"description": "Endpoint de simulación deshabilitado en este entorno"},
    },
)
async def procesar_pago_aprobado(id_reserva: str):
    if os.getenv("ALLOW_SIMULATED_WEBHOOK", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="El webhook de pago simulado está deshabilitado. La emisión de entradas pagadas requiere confirmación real desde Pagos.",
        )

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
        "entradas_emitidas": entradas_generadas,
    }


# ============================================================================
# Consulta de Reserva (BE3 Pagos INT-01 y HU-03 Hold con tiempo restante)
# ============================================================================
@router.get(
    "/{id_reserva}",
    tags=["Servicios Provistos (BE3) - Pagos", "Reservas (HU-03)"],
    response_model=DetalleReservaResponse,
    responses={
        200: {"description": "Datos de la reserva retornados exitosamente con tiempo restante y nombre_codigo"},
        404: {"description": "Reserva no encontrada"},
        500: {"description": "Error interno del servidor"},
    },
)
async def consultar_reserva_pagos(
    id_reserva: str,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """
    ### Propósito
    Proporciona al microservicio de Pagos (`GET /api/entradas/reservas/{id_reserva}`, INT-01) y al Checkout
    la información oficial de una reserva (`total`, `cantidad_entradas`, `nombre_codigo`, `estado_reserva` y TTL).
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
            expirada = True
            estado_reserva = "EXPIRADO"
            cantidad = int(reserva.get("cantidad_entrada", 1))
            origen_cookie = cookie or (f"jwt={jwt}" if jwt else None) or obtener_cookie_reserva(id_reserva)
            cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")

            await liberar_reserva_y_anular_pago(
                db=db,
                reserva=reserva,
                nuevo_estado="EXPIRADO",
                motivo="Hold de la reserva vencido: el usuario pagó fuera de plazo",
                cookie_header=cookie_reenvio,
                anular_en_pagos=True,
            )
            print(f"[HU-03 On-Read Release] Reserva '{id_reserva}' expiró al ser consultada. Se liberaron {cantidad} cupo(s).")
        else:
            tiempo_restante_segundos = max(0, int((fecha_expiracion - ahora).total_seconds()))

    monto_total = int(reserva.get("monto_total", 0))
    cantidad_entrada = int(reserva.get("cantidad_entrada", 0))

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
        "nombre_codigo": reserva.get("nombre_codigo"),
        "id_promocion": reserva.get("id_promocion"),
        "porcentaje_descuento": int(reserva.get("porcentaje_descuento", 0)),
        "id_pago": reserva.get("id_pago"),
        "estado_reserva": estado_reserva,
        "estado": estado_reserva,
        "fecha_expiracion": fecha_expiracion,
        "tiempo_restante_segundos": tiempo_restante_segundos,
        "expirada": expirada,
    }
