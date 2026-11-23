from fastapi import APIRouter, HTTPException, Header, Cookie
from pymongo import ReturnDocument
from schemas.entradas import (
    ProcesarCompraRequest,
    ProcesarCompraResponse,
    DetalleEntradaAdquirida,
    CodigoQRAccesoResponse,
    EmisionDirectaRequest,
    EmisionDirectaResponse,
    EventoFrontendResponse,
    DisponibilidadFrontendResponse,
    StockPanelResponse,
    ConsultaEntradaCheckinResponse,
)
from database import get_database
from services.auth_service import AuthService
from services.notificaciones_service import NotificacionesService
from services.pagos_service import PagosService
from services.promociones_service import PromocionesService
from services.catalogo_service import CatalogoService
from services.checkin_service import CheckinService
from services.broker_service import BrokerService
from services.panel_service import PanelService
from routers.reservas import guardar_cookie_reserva
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta
import uuid

router = APIRouter()


def _extraer_qr_url(entrada: dict, id_evento: str) -> str:
    id_entrada = entrada.get("id_entrada", "")
    qr_field = entrada.get("qr_data")
    if isinstance(qr_field, dict) and qr_field.get("url"):
        url = str(qr_field["url"])
    elif isinstance(qr_field, str) and qr_field.strip():
        url = qr_field.strip()
    else:
        url = ""

    if not url or "storage.midominio.com" in url or "data=" not in url:
        return CheckinService.generar_qr_url(id_entrada, id_evento)
    return url


async def _construir_detalle_entrada(db, ent: dict, id_usuario_fallback: str = "") -> dict:
    id_res = ent.get("id_reserva", "")
    id_evt = ent.get("id_evento") or ""
    reserva = None
    if (not id_evt or not ent.get("rut_usuario") or not ent.get("correo_usuario")) and id_res:
        reserva = await db.reserva_entrada.find_one({"id_reserva": id_res})
        if reserva and not id_evt:
            id_evt = reserva.get("id_evento", "")

    evento = await db.inventario_evento.find_one({"id_evento": id_evt}) if id_evt else None
    nombre_evento = (
        ent.get("nombre_evento")
        or (evento.get("nombre_evento") if evento else None)
        or f"Evento {id_evt}"
    )
    fecha_evento = evento.get("fecha_evento") if evento else None
    hora_evento = evento.get("hora_evento") if evento else None
    lugar_ingreso = (
        ent.get("lugar_ingreso")
        or (evento.get("lugar_ingreso") if evento else None)
        or "Puerta Principal - Acceso General"
    )

    return {
        "id_entrada": ent.get("id_entrada"),
        "id_reserva": id_res,
        "id_evento": id_evt,
        "nombre_evento": nombre_evento,
        "fecha_evento": fecha_evento,
        "hora_evento": hora_evento,
        "id_usuario": ent.get("id_usuario") or id_usuario_fallback,
        "nombre_usuario": ent.get("nombre_usuario") or "Asistente",
        "rut_usuario": ent.get("rut_usuario") or (reserva.get("rut_usuario") if reserva else None),
        "correo_usuario": ent.get("correo_usuario") or (reserva.get("correo_usuario") if reserva else None),
        "tipo_acceso": ent.get("tipo_acceso", "GENERAL"),
        "lugar_ingreso": lugar_ingreso,
        "precio_final_pagado": int(ent.get("precio_final_pagado", 0)),
        "estado_entrada": ent.get("estado_entrada", "EMITIDA"),
        "nombre_archivo_qr": ent.get("nombre_archivo_qr", f"{ent.get('id_entrada')}.png"),
        "qr_data": _extraer_qr_url(ent, id_evt),
        "fecha_emision": ent.get("fecha_emision") or datetime.utcnow(),
    }


@router.post(
    "/procesar-compra",
    tags=["Servicios Provistos (BE3) - Catálogo"],
    response_model=ProcesarCompraResponse,
    responses={
        200: {"description": "Compra procesada, stock actualizado e intención de pago iniciada (si es pagada)"},
        400: {"description": "Parámetro ausente/inválido, stock insuficiente o evento no disponible"},
        401: {"description": "NO_AUTENTICADO: Cookie 'jwt' ausente, inválida, expirada o rechazada por Auth"},
        403: {"description": "El rol o estado de cuenta del usuario no permite comprar entradas"},
        404: {"description": "El evento solicitado no existe"},
        503: {"description": "AUTH_NO_DISPONIBLE o servicio externo temporalmente no disponible"},
        500: {"description": "Error interno del servicio de Entradas / Inventario"},
    },
)
async def procesar_compra(
    compra: ProcesarCompraRequest,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """
    ### Propósito (HU-02 + Contrato Catálogo + Contrato Pagos)
    Procesa una intención de compra iniciada desde Catálogo o Checkout:
    1. Valida la sesión con Auth (`Cookie: jwt`).
    2. Descuenta atómicamente el stock en MongoDB (`stock_actual >= cantidad`).
    3. Si es **GRATUITA**: emite todas las entradas solicitadas con QR, registra en Check-in y publica en RabbitMQ.
    4. Si es **PAGADA**: crea reserva temporal (`RESERVADO`), revalida código promocional con Promociones e inicia cobro en Pagos.
    """
    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None) or compra.token_sesion
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    token_jwt = AuthService.extraer_jwt(cookie_reenvio)
    if not cookie_reenvio or not token_jwt:
        raise HTTPException(
            status_code=401,
            detail="NO_AUTENTICADO: Falta la cookie 'jwt' de sesión emitida por Auth.",
        )

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)

    id_usuario = usuario_auth["id_usuario"]
    rol_usuario = usuario_auth.get("rol", "").upper()
    nombre_usuario = usuario_auth.get("nombre") or "Usuario"
    rut_usuario = usuario_auth.get("rut")
    correo_usuario = usuario_auth.get("correo") or ""

    if rol_usuario not in ("CLIENTE", "USUARIO", "STAFF", "ORGANIZADOR"):
        raise HTTPException(status_code=403, detail="El rol del usuario no tiene permisos para comprar entradas.")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    evento_db = await db.inventario_evento.find_one({"id_evento": compra.id_evento})
    if not evento_db:
        raise HTTPException(status_code=404, detail="El evento solicitado no existe.")

    estado_gestion = str(evento_db.get("estado_gestion", "PUBLICADO")).upper()
    if estado_gestion != "PUBLICADO":
        raise HTTPException(status_code=400, detail=f"El evento se encuentra en estado '{estado_gestion}' y no admite compras.")

    maximo_ticket = int(evento_db.get("maximo_ticket") or 6)
    if compra.cantidad <= 0 or compra.cantidad > 100 or compra.cantidad > maximo_ticket:
        raise HTTPException(
            status_code=400,
            detail=f"Cantidad inválida. Debe ser entre 1 y {min(100, maximo_ticket)} entrada(s).",
        )

    tipo_evento_real = str(evento_db.get("tipo_entrada", "PAGADA")).upper()
    es_gratuita = tipo_evento_real == "GRATUITA"
    if compra.tipo_entrada.upper() == "GRATUITA" and not es_gratuita:
        raise HTTPException(status_code=400, detail="Este evento es de tipo PAGADA y no admite emisión gratuita.")

    precio_unitario = int(evento_db.get("precio_unitario", 0))
    precio_base = precio_unitario * compra.cantidad
    nombre_evento = evento_db.get("nombre_evento") or f"Evento {compra.id_evento}"
    fecha_evento = evento_db.get("fecha_evento") or ""
    hora_evento = evento_db.get("hora_evento") or "20:00"
    lugar_ingreso = evento_db.get("lugar_ingreso") or "Puerta Principal - Acceso General"

    inc_fields = (
        {"stock_actual": -compra.cantidad, "cantidad_entrada_comprada": compra.cantidad}
        if es_gratuita
        else {"stock_actual": -compra.cantidad, "cantidad_entrada_reservada": compra.cantidad}
    )

    evento_actualizado = await db.inventario_evento.find_one_and_update(
        {
            "id_evento": compra.id_evento,
            "estado_gestion": "PUBLICADO",
            "stock_actual": {"$gte": compra.cantidad},
        },
        {"$inc": inc_fields},
        return_document=ReturnDocument.AFTER,
    )
    if not evento_actualizado:
        raise HTTPException(status_code=400, detail="Stock insuficiente para completar la solicitud.")

    nuevo_stock = int(evento_actualizado.get("stock_actual", 0))
    id_reserva = f"res-{uuid.uuid4().hex[:8]}"

    rol_bd = "usuario" if rol_usuario.lower() == "cliente" else rol_usuario.lower()

    if es_gratuita:
        await db.reserva_entrada.insert_one(
            {
                "id_reserva": id_reserva,
                "id_evento": compra.id_evento,
                "id_usuario": id_usuario,
                "nombre_usuario": nombre_usuario,
                "rut_usuario": rut_usuario,
                "correo_usuario": correo_usuario or None,
                "rol_usuario": rol_bd,
                "cantidad_entrada": compra.cantidad,
                "id_promocion": None,
                "nombre_codigo": None,
                "porcentaje_descuento": 0,
                "monto_total": 0,
                "id_pago": None,
                "estado_reserva": "CONSOLIDADO",
                "fecha_creacion": datetime.utcnow(),
                "fecha_expiracion": None,
            }
        )

        entradas_emitidas: List[str] = []
        for _ in range(compra.cantidad):
            id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
            qr_data_url = CheckinService.generar_qr_url(id_entrada, compra.id_evento)
            qr_obj = {
                "url": qr_data_url,
                "hash": uuid.uuid4().hex[:7],
            }
            fecha_emision = datetime.utcnow()

            await db.entrada.insert_one(
                {
                    "id_entrada": id_entrada,
                    "id_reserva": id_reserva,
                    "id_evento": compra.id_evento,
                    "nombre_evento": nombre_evento,
                    "lugar_ingreso": lugar_ingreso,
                    "id_usuario": id_usuario,
                    "nombre_usuario": nombre_usuario,
                    "rut_usuario": rut_usuario,
                    "correo_usuario": correo_usuario or None,
                    "rol_usuario": rol_bd,
                    "tipo_acceso": "GENERAL",
                    "precio_final_pagado": 0,
                    "estado_entrada": "EMITIDA",
                    "nombre_archivo_qr": f"gratis-{id_entrada}.png",
                    "qr_data": qr_obj,
                    "fecha_emision": fecha_emision,
                }
            )
            entradas_emitidas.append(id_entrada)

            await CheckinService.registrar_ticket_puerta(
                id_entrada=id_entrada,
                id_evento=compra.id_evento,
                id_usuario=id_usuario,
                nombre_usuario=nombre_usuario,
                qr_data={"id_entrada": id_entrada, "id_evento": compra.id_evento},
            )
            if correo_usuario:
                asyncio.create_task(
                    NotificacionesService.enviar_ticket_correo(
                        correo_comprador=correo_usuario,
                        nombre_comprador=nombre_usuario,
                        id_usuario=id_usuario,
                        nombre_evento=nombre_evento,
                        id_evento=compra.id_evento,
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
                        "id_evento": compra.id_evento,
                        "id_usuario": id_usuario,
                        "nombre_usuario": nombre_usuario,
                        "rut_usuario": rut_usuario,
                        "correo_usuario": correo_usuario,
                        "tipo_acceso": "GENERAL",
                        "precio_final_pagado": 0,
                        "qr_data": qr_obj,
                        "fecha_emision": fecha_emision.isoformat(),
                    },
                )
            )

        asyncio.create_task(CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, token_jwt))
        if nuevo_stock == 0:
            asyncio.create_task(
                BrokerService.publish_event("entradas.evento.stock.v1", {"id_evento": compra.id_evento, "stock": 0})
            )
            asyncio.create_task(
                BrokerService.publish_event("stock.agotado", {"id_evento": compra.id_evento, "stock": 0})
            )

        return {
            "nuevo_stock": nuevo_stock,
            "id_reserva": id_reserva,
            "estado_pago": "GRATUITA",
            "entradas_emitidas": entradas_emitidas,
        }

    # Flujo PAGADA
    codigo_promo, id_promocion_real, pct_descuento, monto_final = await PromocionesService.revalidar_descuento(
        id_evento=compra.id_evento,
        id_usuario=id_usuario,
        cantidad_entradas=compra.cantidad,
        precio_base=precio_base,
        nombre_codigo=compra.nombre_codigo,
        id_promocion=compra.id_promocion,
        porcentaje_descuento=compra.porcentaje_descuento,
    )
    expira_en = datetime.utcnow() + timedelta(minutes=15)

    await db.reserva_entrada.insert_one(
        {
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_usuario or None,
            "rol_usuario": rol_bd,
            "cantidad_entrada": compra.cantidad,
            "id_promocion": id_promocion_real,
            "nombre_codigo": codigo_promo,
            "porcentaje_descuento": pct_descuento,
            "monto_total": monto_final,
            "id_pago": None,
            "estado_reserva": "RESERVADO",
            "fecha_creacion": datetime.utcnow(),
            "fecha_expiracion": expira_en,
        }
    )
    guardar_cookie_reserva(id_reserva, cookie_reenvio)

    pago = await PagosService.iniciar_cobro(
        id_reserva=id_reserva,
        total=monto_final,
        cantidad_entradas=compra.cantidad,
        cookie_header=cookie_reenvio,
        id_evento=compra.id_evento,
        metodo=compra.metodo,
        nombre_codigo=codigo_promo,
    )

    codigo_http_pago = pago.get("codigo_http") if isinstance(pago, dict) else None
    error_codigo_pago = pago.get("error") if isinstance(pago, dict) else None

    if codigo_http_pago == 401 or error_codigo_pago == "NO_AUTENTICADO":
        await db.reserva_entrada.delete_one({"id_reserva": id_reserva})
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$inc": {"stock_actual": compra.cantidad, "cantidad_entrada_reservada": -compra.cantidad}},
        )
        raise HTTPException(
            status_code=401,
            detail={
                "error": "NO_AUTENTICADO",
                "mensaje": pago.get("mensaje", "La cookie 'jwt' fue rechazada por Auth en Pagos."),
                "detalles": pago.get("detalles", []),
            },
        )

    if codigo_http_pago == 503 and error_codigo_pago == "AUTH_NO_DISPONIBLE":
        await db.reserva_entrada.delete_one({"id_reserva": id_reserva})
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$inc": {"stock_actual": compra.cantidad, "cantidad_entrada_reservada": -compra.cantidad}},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AUTH_NO_DISPONIBLE",
                "mensaje": pago.get("mensaje", "Pagos no pudo validar la sesión con Auth. Reintente más tarde."),
                "detalles": pago.get("detalles", []),
            },
        )

    id_pago_generado = pago.get("id_pago") if isinstance(pago, dict) else None
    if id_pago_generado:
        await db.reserva_entrada.update_one(
            {"id_reserva": id_reserva},
            {"$set": {"id_pago": id_pago_generado}},
        )

    asyncio.create_task(CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, token_jwt))

    if nuevo_stock == 0:
        asyncio.create_task(
            BrokerService.publish_event("entradas.evento.stock.v1", {"id_evento": compra.id_evento, "stock": 0})
        )
        asyncio.create_task(
            BrokerService.publish_event("stock.agotado", {"id_evento": compra.id_evento, "stock": 0})
        )

    return {
        "nuevo_stock": nuevo_stock,
        "id_reserva": id_reserva,
        "id_pago": id_pago_generado,
        "estado_pago": pago.get("estado_pago", "PENDIENTE") if isinstance(pago, dict) else "PENDIENTE",
        "url_checkout": pago.get("url_checkout") if isinstance(pago, dict) else None,
        "metodo": pago.get("metodo") if isinstance(pago, dict) else compra.metodo,
        "fecha_creacion": pago.get("fecha_creacion") if isinstance(pago, dict) else None,
        "fecha_expiracion": pago.get("fecha_expiracion") if isinstance(pago, dict) else expira_en.isoformat(),
    }


def _formatear_evento_frontend(ev: dict) -> dict:
    tipo_entrada = ev.get("tipo_entrada", "PAGADA")
    max_tickets = int(ev.get("maximo_ticket", 4))
    return {
        "id": ev["id_evento"],
        "titulo": ev.get("nombre_evento") or f"Evento {ev['id_evento']}",
        "fecha": ev.get("fecha_evento") or "Por confirmar",
        "hora": ev.get("hora_evento") or "Por confirmar",
        "lugar": ev.get("lugar_ingreso") or "Por confirmar",
        "descripcion": ev.get("descripcion") or "",
        "tipoEntrada": tipo_entrada,
        "precio": int(ev.get("precio_unitario", 0)),
        "stockTotal": int(ev.get("stock_inicial", 0)),
        "stockDisponible": int(ev.get("stock_actual", 0)),
        "maxTickets": max_tickets,
        "limiteGratuitoUsuario": max_tickets if tipo_entrada == "GRATUITA" else None,
        "estadoGestion": ev.get("estado_gestion", "PUBLICADO"),
    }


@router.get(
    "/eventos",
    tags=["Servicios Propios (BE1)"],
    response_model=List[EventoFrontendResponse],
    responses={
        200: {"description": "Lista de eventos disponibles en inventario"},
        500: {"description": "Error de conexión con la base de datos"},
    },
)
async def listar_eventos_frontend():
    """Retorna los eventos registrados en el inventario de entradas."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    cursor = db.inventario_evento.find({})
    eventos = await cursor.to_list(length=100)
    return [_formatear_evento_frontend(ev) for ev in eventos]


@router.get(
    "/eventos/{id_evento}",
    tags=["Servicios Propios (BE1)"],
    response_model=EventoFrontendResponse,
    responses={
        200: {"description": "Detalle del evento en inventario"},
        404: {"description": "Evento no encontrado"},
        500: {"description": "Error de conexión con la base de datos"},
    },
)
async def obtener_evento_frontend(id_evento: str):
    """Retorna el detalle de inventario de un evento específico."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        await PanelService.sincronizar_eventos_panel(db)
        evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")

    return _formatear_evento_frontend(evento)


@router.get(
    "/eventos/{id_evento}/disponibilidad",
    tags=["Servicios Provistos (BE3) - Catálogo"],
    response_model=DisponibilidadFrontendResponse,
    responses={
        200: {"description": "Disponibilidad en tiempo real del evento"},
        404: {"description": "Evento no encontrado"},
        500: {"description": "Error de conexión con la base de datos"},
    },
)
async def consultar_disponibilidad_frontend(id_evento: str):
    """Expone la disponibilidad y precio oficial de un evento para el widget incrustado en Catálogo."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        await PanelService.sincronizar_eventos_panel(db)
        evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")

    return {
        "idEvento": evento["id_evento"],
        "stockDisponible": int(evento.get("stock_actual", 0)),
        "stockTotal": int(evento.get("stock_inicial", 0)),
        "tipoEntrada": evento.get("tipo_entrada", "PAGADA"),
        "precio": int(evento.get("precio_unitario", 0)),
        "estadoGestion": evento.get("estado_gestion", "PUBLICADO"),
    }


@router.get(
    "/eventos/{id_evento}/stock",
    tags=["Servicios Provistos (BE3) - Panel Organizador"],
    response_model=StockPanelResponse,
    responses={
        200: {"description": "Stock retornado exitosamente"},
        404: {"description": "Evento no encontrado"},
        500: {"description": "Error interno del servidor"},
    },
)
async def consultar_stock_panel(id_evento: str):
    """Expone la disponibilidad real de un evento para validaciones del Panel Organizador."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")

    return {
        "id_evento": evento["id_evento"],
        "stock": int(evento["stock_actual"]),
    }


@router.post(
    "/emision-directa",
    tags=["Servicios Propios (BE1)"],
    response_model=EmisionDirectaResponse,
    responses={
        200: {"description": "Entrada(s) gratuita(s) emitida(s) y registrada(s) en Check-in"},
        400: {"description": "Evento pagado, no publicado, límite excedido o stock insuficiente"},
        401: {"description": "NO_AUTENTICADO: Cookie 'jwt' ausente, inválida o rechazada por Auth"},
        403: {"description": "Rol o cuenta sin permisos"},
        404: {"description": "El evento solicitado no existe"},
        503: {"description": "AUTH_NO_DISPONIBLE"},
        500: {"description": "Error interno del servidor"},
    },
)
async def emitir_entrada_directa_frontend(
    solicitud: EmisionDirectaRequest,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """
    Emite una o más entradas para **eventos gratuitos**, validando obligatoriamente la sesión con Auth,
    descontando stock atómicamente, registrando cada entrada en Check-in y publicando hacia Notificaciones.
    Los eventos pagados deben pasar por reserva temporal (`POST /reservas/hold`) y Pasarela de Pagos.
    """
    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None)
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    token_jwt = AuthService.extraer_jwt(cookie_reenvio)
    if not cookie_reenvio or not token_jwt:
        raise HTTPException(
            status_code=401,
            detail="NO_AUTENTICADO: Debes iniciar sesión (cookie 'jwt') para emitir entradas.",
        )

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)
    id_usuario = usuario_auth["id_usuario"]
    nombre_comprador = usuario_auth.get("nombre") or "Asistente"
    rut_usuario = usuario_auth.get("rut")
    correo_comprador = usuario_auth.get("correo") or (solicitud.correo_comprador or "")
    rol_raw = (usuario_auth.get("rol") or "usuario").lower()
    rol_usuario = "usuario" if rol_raw == "cliente" else rol_raw

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    evento = await db.inventario_evento.find_one({"id_evento": solicitud.id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="El evento solicitado no existe.")

    estado_gestion = str(evento.get("estado_gestion", "PUBLICADO")).upper()
    if estado_gestion != "PUBLICADO":
        raise HTTPException(
            status_code=400,
            detail=f"El evento se encuentra en estado '{estado_gestion}' y no admite emisión de entradas.",
        )

    if str(evento.get("tipo_entrada", "PAGADA")).upper() != "GRATUITA":
        raise HTTPException(
            status_code=400,
            detail="Los eventos pagados no permiten emisión directa. Crea una reserva y completa el pago en la pasarela.",
        )

    maximo_ticket = int(evento.get("maximo_ticket") or 2)
    if solicitud.cantidad_entradas > maximo_ticket:
        raise HTTPException(
            status_code=400,
            detail=f"Límite excedido: máximo {maximo_ticket} entrada(s) gratuita(s) por solicitud.",
        )

    evento_actualizado = await db.inventario_evento.find_one_and_update(
        {
            "id_evento": solicitud.id_evento,
            "estado_gestion": "PUBLICADO",
            "stock_actual": {"$gte": solicitud.cantidad_entradas},
        },
        {
            "$inc": {
                "stock_actual": -solicitud.cantidad_entradas,
                "cantidad_entrada_comprada": solicitud.cantidad_entradas,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not evento_actualizado:
        raise HTTPException(status_code=400, detail="Stock insuficiente para emitir la entrada.")

    nuevo_stock = int(evento_actualizado.get("stock_actual", 0))
    id_reserva = f"res-{uuid.uuid4().hex[:8]}"

    await db.reserva_entrada.insert_one(
        {
            "id_reserva": id_reserva,
            "id_evento": solicitud.id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_comprador,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_comprador or None,
            "rol_usuario": rol_usuario,
            "cantidad_entrada": solicitud.cantidad_entradas,
            "id_promocion": None,
            "nombre_codigo": None,
            "porcentaje_descuento": 0,
            "monto_total": 0,
            "id_pago": None,
            "estado_reserva": "CONSOLIDADO",
            "fecha_creacion": datetime.utcnow(),
            "fecha_expiracion": None,
        }
    )

    await CatalogoService.actualizar_stock_catalogo(solicitud.id_evento, nuevo_stock, token_jwt)
    if nuevo_stock == 0:
        asyncio.create_task(
            BrokerService.publish_event("entradas.evento.stock.v1", {"id_evento": solicitud.id_evento, "stock": 0})
        )
        asyncio.create_task(
            BrokerService.publish_event("stock.agotado", {"id_evento": solicitud.id_evento, "stock": 0})
        )

    nombre_evento = evento.get("nombre_evento") or f"Evento {solicitud.id_evento}"
    fecha_evento = evento.get("fecha_evento") or "Por confirmar"
    hora_evento = evento.get("hora_evento") or "Por confirmar"
    lugar_evento = evento.get("lugar_ingreso") or "Puerta Principal - Acceso General"

    entradas_emitidas: List[str] = []
    primer_qr_url = ""
    todos_registrados_checkin = True

    for idx in range(solicitud.cantidad_entradas):
        id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
        qr_url = CheckinService.generar_qr_url(id_entrada, solicitud.id_evento)
        if idx == 0:
            primer_qr_url = qr_url
        fecha_emision = datetime.utcnow()

        await db.entrada.insert_one(
            {
                "id_entrada": id_entrada,
                "id_reserva": id_reserva,
                "id_evento": solicitud.id_evento,
                "nombre_evento": nombre_evento,
                "lugar_ingreso": lugar_evento,
                "id_usuario": id_usuario,
                "nombre_usuario": nombre_comprador,
                "rut_usuario": rut_usuario,
                "correo_usuario": correo_comprador or None,
                "rol_usuario": rol_usuario,
                "tipo_acceso": "GENERAL",
                "precio_final_pagado": 0,
                "estado_entrada": "EMITIDA",
                "nombre_archivo_qr": f"{id_entrada}.png",
                "qr_data": {
                    "url": qr_url,
                    "hash": uuid.uuid4().hex[:7],
                },
                "fecha_emision": fecha_emision,
            }
        )
        entradas_emitidas.append(id_entrada)

        registrado = await CheckinService.registrar_ticket_puerta(
            id_entrada=id_entrada,
            id_evento=solicitud.id_evento,
            id_usuario=id_usuario,
            nombre_usuario=nombre_comprador,
            qr_data={"id_entrada": id_entrada, "id_evento": solicitud.id_evento},
        )
        if not registrado:
            todos_registrados_checkin = False

        if correo_comprador:
            asyncio.create_task(
                NotificacionesService.enviar_ticket_correo(
                    correo_comprador=correo_comprador,
                    nombre_comprador=nombre_comprador,
                    id_usuario=id_usuario,
                    nombre_evento=nombre_evento,
                    id_evento=solicitud.id_evento,
                    fecha_evento=fecha_evento,
                    hora_evento=hora_evento,
                    qr_data=qr_url,
                )
            )
        asyncio.create_task(
            BrokerService.publish_event(
                "entrada.emitida",
                {
                    "id_entrada": id_entrada,
                    "id_reserva": id_reserva,
                    "id_evento": solicitud.id_evento,
                    "id_usuario": id_usuario,
                    "nombre_usuario": nombre_comprador,
                    "correo_usuario": correo_comprador,
                    "tipo_acceso": "GENERAL",
                    "precio_final_pagado": 0,
                    "qr_data": {"url": qr_url},
                    "fecha_emision": fecha_emision.isoformat(),
                },
            )
        )

    return {
        "idEntrada": entradas_emitidas[0],
        "entradasEmitidas": entradas_emitidas,
        "idEvento": solicitud.id_evento,
        "nombreEvento": nombre_evento,
        "nombreComprador": nombre_comprador,
        "correoComprador": correo_comprador,
        "tipoAcceso": "Entrada Gratuita",
        "precioFinal": 0,
        "cantidadEntradas": solicitud.cantidad_entradas,
        "qrData": primer_qr_url,
        "fechaEvento": fecha_evento,
        "horaEvento": hora_evento,
        "lugarEvento": lugar_evento,
        "fechaEmision": datetime.utcnow().strftime("%d-%m-%Y"),
        "registradoEnCheckin": todos_registrados_checkin,
    }


# ==========================================
# HU-04: Mis Entradas / Historial del usuario autenticado
# ==========================================
@router.get(
    "/mis-entradas",
    tags=["Servicios Propios (BE1)"],
    response_model=List[DetalleEntradaAdquirida],
    responses={
        200: {"description": "Historial de entradas del usuario autenticado"},
        401: {"description": "NO_AUTENTICADO: Cookie 'jwt' ausente o inválida"},
        503: {"description": "AUTH_NO_DISPONIBLE"},
        500: {"description": "Error al conectar con la base de datos"},
    },
)
async def obtener_mis_entradas(
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """Retorna todas las entradas emitidas pertenecientes al usuario autenticado (vía cookie `jwt`)."""
    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None)
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    if not cookie_reenvio or not AuthService.extraer_jwt(cookie_reenvio):
        raise HTTPException(status_code=401, detail="NO_AUTENTICADO: Debes iniciar sesión para ver tus entradas.")

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)
    id_usuario = usuario_auth["id_usuario"]

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    cursor = db.entrada.find({"id_usuario": id_usuario}).sort("fecha_emision", -1)
    entradas = await cursor.to_list(length=100)
    return [await _construir_detalle_entrada(db, ent, id_usuario) for ent in entradas]


@router.get(
    "/usuario/{id_usuario}",
    tags=["Servicios Propios (BE1)"],
    response_model=List[DetalleEntradaAdquirida],
    responses={
        200: {"description": "Historial de entradas adquiridas por el cliente retornado con éxito"},
        401: {"description": "NO_AUTENTICADO: Cookie 'jwt' ausente o inválida"},
        403: {"description": "No autorizado para consultar el historial de otro usuario"},
        500: {"description": "Error al conectar con la base de datos"},
    },
)
async def obtener_historial_entradas_usuario(
    id_usuario: str,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None),
):
    """Permite al usuario autenticado (o a STAFF/ORGANIZADOR) consultar el historial de entradas de una cuenta."""
    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None)
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    if not cookie_reenvio or not AuthService.extraer_jwt(cookie_reenvio):
        raise HTTPException(status_code=401, detail="NO_AUTENTICADO: Se requiere cookie 'jwt' válida.")

    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)
    if usuario_auth["id_usuario"] != id_usuario and usuario_auth["rol"] not in ("STAFF", "ORGANIZADOR"):
        raise HTTPException(status_code=403, detail="No tienes permisos para consultar las entradas de otro usuario.")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    cursor = db.entrada.find({"id_usuario": id_usuario}).sort("fecha_emision", -1)
    entradas = await cursor.to_list(length=100)
    return [await _construir_detalle_entrada(db, ent, id_usuario) for ent in entradas]


@router.get(
    "/{id_ticket}/detalle",
    tags=["Servicios Provistos (BE3) - Check-in", "Servicios Propios (BE1)"],
    response_model=DetalleEntradaAdquirida,
    responses={
        200: {"description": "Detalle inmutable de la entrada obtenido correctamente"},
        404: {"description": "Entrada no encontrada"},
        500: {"description": "Error al conectar con la base de datos"},
    },
)
async def obtener_detalle_entrada(id_ticket: str):
    """Retorna los datos inmutables de una entrada específica (usado por Clientes y Check-in)."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    entrada = await db.entrada.find_one({"id_entrada": id_ticket})
    if not entrada:
        raise HTTPException(status_code=404, detail="La entrada solicitada no existe.")

    return await _construir_detalle_entrada(db, entrada)


# ==========================================
# HU-05: Recepción de Código QR de Acceso
# ==========================================
@router.get(
    "/{id_ticket}/qr",
    tags=["Servicios Propios (BE1)"],
    response_model=CodigoQRAccesoResponse,
    responses={
        200: {"description": "Código QR de acceso y habilitación en Check-in retornados con éxito"},
        400: {"description": "La entrada está anulada o no válida para acceso"},
        404: {"description": "Entrada no encontrada"},
        500: {"description": "Error al conectar con la base de datos"},
    },
)
async def obtener_qr_acceso(id_ticket: str):
    """Proporciona el código QR de acceso y su payload estructurado para validación en puerta."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")

    entrada = await db.entrada.find_one({"id_entrada": id_ticket})
    if not entrada:
        raise HTTPException(status_code=404, detail="La entrada solicitada no existe.")

    if entrada.get("estado_entrada") == "ANULADA":
        raise HTTPException(status_code=400, detail="La entrada se encuentra anulada y no puede ser utilizada para acceso.")

    detalle = await _construir_detalle_entrada(db, entrada)

    return {
        "id_entrada": detalle["id_entrada"],
        "id_evento": detalle["id_evento"],
        "nombre_asistente": detalle["nombre_usuario"],
        "nombre_evento": detalle["nombre_evento"],
        "lugar_ingreso": detalle["lugar_ingreso"],
        "tipo_acceso": detalle["tipo_acceso"],
        "qr_data": detalle["qr_data"],
        "qr_payload": {
            "id_evento": detalle["id_evento"],
            "id_entrada": detalle["id_entrada"],
        },
        "habilitado_checkin": detalle["estado_entrada"] == "EMITIDA",
    }


@router.get(
    "/{id_ticket}",
    tags=["Servicios Provistos (BE3) - Check-in"],
    response_model=ConsultaEntradaCheckinResponse,
    responses={
        200: {"description": "Datos de la entrada retornados exitosamente"},
        400: {"description": "Datos de solicitud incompletos o id_ticket con formato inválido"},
        404: {"description": "La entrada asociada al id_ticket no existe"},
        500: {"description": "Error interno del servicio de Entradas / Inventario"},
        503: {"description": "Servicio temporalmente no disponible"},
    },
)
async def consultar_entrada_checkin(id_ticket: str):
    """Permite al microservicio de Check-in consultar validez, evento y titular de una entrada emitida."""
    if not id_ticket or not id_ticket.strip():
        raise HTTPException(status_code=400, detail="El id_ticket es obligatorio.")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")

    entrada = await db.entrada.find_one({"id_entrada": id_ticket})
    if not entrada:
        raise HTTPException(status_code=404, detail="La entrada no existe.")

    detalle = await _construir_detalle_entrada(db, entrada)

    return {
        "id_ticket": detalle["id_entrada"],
        "id_entrada": detalle["id_entrada"],
        "id_evento": detalle["id_evento"],
        "estado_entrada": detalle["estado_entrada"],
        "nombre_usuario": detalle["nombre_usuario"],
        "usuario": {
            "id_usuario": detalle["id_usuario"],
            "rol_usuario": str(entrada.get("rol_usuario", "usuario")).lower(),
        },
    }
