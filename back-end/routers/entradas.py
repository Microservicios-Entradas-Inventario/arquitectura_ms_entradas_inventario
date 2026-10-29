from fastapi import APIRouter, HTTPException, Header, Cookie
from schemas.entradas import (
    ProcesarCompraRequest, 
    ProcesarCompraResponse,
    DetalleEntradaAdquirida,
    CodigoQRAccesoResponse
)
from database import get_database
from services.auth_service import AuthService
from services.notificaciones_service import NotificacionesService
from services.pagos_service import PagosService
from services.catalogo_service import CatalogoService
from services.checkin_service import CheckinService
from services.broker_service import BrokerService
from typing import List, Optional
import asyncio
from datetime import datetime, timedelta
import uuid

router = APIRouter()

@router.post(
    "/procesar-compra", 
    tags=["Servicios Provistos (BE3) - Catálogo"], 
    response_model=ProcesarCompraResponse,
    responses={
        200: {"description": "Compra procesada, stock actualizado e intención de pago iniciada (incluye url_checkout)"}, 
        400: {"description": "Parámetro ausente o inválido (ej. cantidad <= 0 o > 100)"}, 
        401: {"description": "NO_AUTENTICADO: Cookie 'jwt' ausente, inválida, expirada o rechazada por Auth"}, 
        404: {"description": "El evento o el tipo de entrada solicitado no existe"},
        503: {"description": "AUTH_NO_DISPONIBLE o servicio externo temporalmente no disponible (reintentar)"},
        500: {"description": "Error interno del servicio de Entradas / Inventario"}
    }
)
async def procesar_compra(
    compra: ProcesarCompraRequest,
    cookie: Optional[str] = Header(default=None),
    jwt: Optional[str] = Cookie(default=None)
):
    """
    ###  Propósito
    Punto de entrada principal para procesar una intención de compra iniciada desde el Catálogo. Descuenta el stock, valida la identidad en Auth reenviando el header `Cookie` (`jwt`), inicializa reservas y delega el cobro (si aplica) a Pagos (Soporte a Contrato Catálogo v2.0 y Contrato Pagos ↔ Entradas v2.3).

    ###  Parámetros
    - **`Cookie`** *(Header)*: Header `Cookie` recibido del navegador con la cookie `jwt` emitida por Auth (reenviado tal cual a Auth y a Pagos según Contrato Pagos v2.3).
    - **`compra`** *(ProcesarCompraRequest) (Body)*: Objeto JSON con `id_evento`, `tipo_entrada`, `cantidad` y opcionalmente `metodo`.

    ###  Flujo de Funcionamiento
    1. Se valida la sesión del usuario contra el microservicio de Autenticación (`GET /internal/validar-sesion`) enviando el header `Cookie` (`jwt`). De esa respuesta se obtienen los datos del comprador (**nombre, RUT y correo**) sin pedirlos a mano en pantalla. Se verifica que el rol sea válido (`USUARIO`, `CLIENTE` o `STAFF`).
    2. Se comprueba que el evento exista, no esté cancelado y cuente con stock suficiente (1 a 100 entradas según Contrato Pagos v2.3).
    3. Se descuenta el stock absoluto (`stock_actual`) de inmediato para evitar concurrencia.
    4. **(Si es Gratuita)**: Se consolida, se emite directamente el QR y se notifica en paralelo a Check-in y Catálogo.
    5. **(Si es Pagada)**: Se genera una reserva con TTL temporal y se invoca síncronamente a Pagos (**Contrato Pagos v2.3**) reenviando el header `Cookie` tal cual llegó del navegador (sin `Authorization: Bearer` ni `token_sesion` en el body). Se almacena únicamente `id_pago` como referencia (ignorando `client_secret`) y se devuelve `url_checkout` para redirigir al comprador.
    6. Si Pagos responde `503 AUTH_NO_DISPONIBLE` o `401 NO_AUTENTICADO`, no se crea ningún pago, se revierte la reserva local y se propaga el código para que el cliente pueda reintentar limpiamente.
    """
    # Contrato Pagos v2.3: Reenviar el header Cookie que llegó del navegador tal cual (con fallback si Catálogo envía jwt/token_sesion)
    origen_cookie = cookie or (f"jwt={jwt}" if jwt else None) or compra.token_sesion
    cookie_reenvio = AuthService.formatear_cookie_header(origen_cookie or "")
    token_jwt = AuthService.extraer_jwt(cookie_reenvio)
    if not cookie_reenvio or not token_jwt:
        raise HTTPException(status_code=401, detail="NO_AUTENTICADO: Falta la cookie 'jwt' de sesión emitida por Auth.")
        
    usuario_auth = await AuthService.validar_sesion(cookie_reenvio)
        
    id_usuario = usuario_auth.get("id_usuario")
    rol_usuario = usuario_auth.get("rol", "").upper()
    # Auth entrega directamente nombre, RUT y correo en la validación de sesión
    nombre_usuario = usuario_auth.get("nombre") or usuario_auth.get("nombre_completo") or "Usuario Desconocido"
    rut_usuario = usuario_auth.get("rut")
    correo_usuario = usuario_auth.get("correo") or usuario_auth.get("correo_electronico") or "correo@ejemplo.com"

    # Auth maneja usuario, organizador y staff (dejando de existir SERVICIO y ADMIN; se mantiene CLIENTE por compatibilidad)
    if rol_usuario not in ["CLIENTE", "USUARIO", "STAFF"]:
        raise HTTPException(status_code=403, detail="El rol del usuario no tiene permisos para comprar entradas.")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")
        
    evento_db = await db.inventario_evento.find_one({"id_evento": compra.id_evento})
    if not evento_db:
        raise HTTPException(status_code=404, detail="El evento solicitado no existe.")

    if evento_db.get("estado_gestion") == "CANCELADO":
        raise HTTPException(status_code=400, detail="El evento se encuentra CANCELADO.")

    stock_actual = evento_db.get("stock_actual", 0)
    precio_unitario = evento_db.get("precio_unitario", 0)
    precio_base = precio_unitario * compra.cantidad
    nombre_evento = evento_db.get("nombre_evento", f"Evento {compra.id_evento}")
    fecha_evento = evento_db.get("fecha_evento", "2026-12-01")
    hora_evento = evento_db.get("hora_evento", "20:00")

    if compra.cantidad <= 0 or compra.cantidad > 100 or compra.cantidad > stock_actual:
        raise HTTPException(status_code=400, detail="Parámetro ausente o inválido (ej. cantidad <= 0, > 100 o stock insuficiente).")

    nuevo_stock = stock_actual - compra.cantidad
    id_reserva = f"res-{uuid.uuid4().hex[:8]}"

    if compra.tipo_entrada.upper() == "GRATUITA":
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$set": {"stock_actual": nuevo_stock}, "$inc": {"cantidad_entrada_comprada": compra.cantidad}}
        )
        
        # Persistencia de nombre_usuario, rut_usuario y correo_usuario obtenidos desde Auth
        await db.reserva_entrada.insert_one({
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_usuario,
            "rol_usuario": rol_usuario.lower(),
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
        qr_data_url = f"https://storage.midominio.com/qr/gratis-{id_entrada}.png"
        qr_obj = {
            "url": qr_data_url,
            "hash": uuid.uuid4().hex[:7]
        }
        
        await db.entrada.insert_one({
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_usuario,
            "rol_usuario": rol_usuario.lower(),
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": 0,
            "estado_entrada": "EMITIDA",
            "nombre_archivo_qr": f"gratis-{id_entrada}.png",
            "qr_data": qr_obj,
            "fecha_emision": datetime.utcnow()
        })
        
        qr_checkin = id_entrada
        
        asyncio.create_task(NotificacionesService.enviar_ticket_correo(
            correo_comprador=correo_usuario,
            nombre_comprador=nombre_usuario,
            id_usuario=id_usuario,
            nombre_evento=nombre_evento,
            id_evento=compra.id_evento,
            fecha_evento=fecha_evento,
            hora_evento=hora_evento,
            qr_data=qr_data_url
        ))
        asyncio.create_task(CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, token_jwt))
        asyncio.create_task(CheckinService.registrar_ticket_puerta(
            id_entrada=id_entrada,
            id_evento=compra.id_evento,
            id_usuario=id_usuario,
            nombre_usuario=nombre_usuario,
            qr_data=qr_checkin
        ))
        asyncio.create_task(BrokerService.publish_event("entrada.emitida", {
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
            "fecha_emision": datetime.utcnow().isoformat()
        }))
        
        if nuevo_stock == 0:
            asyncio.create_task(BrokerService.publish_event("stock.agotado", {
                "id_evento": compra.id_evento,
                "stock": 0
            }))
        
        return {
            "nuevo_stock": nuevo_stock,
            "id_reserva": id_reserva,
            "estado_pago": "GRATUITA"
        }
    else:
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$set": {"stock_actual": nuevo_stock}, "$inc": {"cantidad_entrada_reservada": compra.cantidad}}
        )
        
        expira_en = datetime.utcnow() + timedelta(minutes=15)
        # Persistencia de datos de comprador obtenidos de Auth y cookie_header para reenvío en polling/anulación con Pagos v2.3
        await db.reserva_entrada.insert_one({
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "rut_usuario": rut_usuario,
            "correo_usuario": correo_usuario,
            "rol_usuario": rol_usuario.lower(),
            "cantidad_entrada": compra.cantidad,
            "id_promocion": None,
            "porcentaje_descuento": 0,
            "monto_total": precio_base,
            "id_pago": None,
            "cookie_header": cookie_reenvio,
            "estado_reserva": "RESERVADO",
            "fecha_creacion": datetime.utcnow(),
            "fecha_expiracion": expira_en
        })
        
        # Ejecutar inicio de cobro (Contrato Pagos v2.3: reenviar header Cookie tal cual)
        pago = await PagosService.iniciar_cobro(
            id_reserva=id_reserva, 
            total=int(precio_base), 
            cantidad_entradas=compra.cantidad,
            cookie_header=cookie_reenvio,
            id_evento=compra.id_evento,
            metodo=compra.metodo
        )

        # Si Pagos rechaza por 401 (NO_AUTENTICADO) o 503 (AUTH_NO_DISPONIBLE), revertir el descuento local para permitir reintento limpio
        codigo_http_pago = pago.get("codigo_http") if isinstance(pago, dict) else None
        error_codigo_pago = pago.get("error") if isinstance(pago, dict) else None

        if codigo_http_pago == 401 or error_codigo_pago == "NO_AUTENTICADO":
            await db.reserva_entrada.delete_one({"id_reserva": id_reserva})
            await db.inventario_evento.update_one(
                {"id_evento": compra.id_evento},
                {"$inc": {"stock_actual": compra.cantidad, "cantidad_entrada_reservada": -compra.cantidad}}
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "NO_AUTENTICADO",
                    "mensaje": pago.get("mensaje", "La cookie 'jwt' fue rechazada por Auth en Pagos (inválida, vencida o no emitida por Auth)."),
                    "detalles": pago.get("detalles", [])
                }
            )

        if codigo_http_pago == 503 and error_codigo_pago == "AUTH_NO_DISPONIBLE":
            await db.reserva_entrada.delete_one({"id_reserva": id_reserva})
            await db.inventario_evento.update_one(
                {"id_evento": compra.id_evento},
                {"$inc": {"stock_actual": compra.cantidad, "cantidad_entrada_reservada": -compra.cantidad}}
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "AUTH_NO_DISPONIBLE",
                    "mensaje": pago.get("mensaje", "Pagos no pudo validar la sesión con Auth. No se creó el pago; reintente más tarde."),
                    "detalles": pago.get("detalles", [])
                }
            )
        
        id_pago_generado = pago.get("id_pago") if isinstance(pago, dict) else None
        if id_pago_generado:
            # Regla Sección 2.6 y 5: Guardar solo id_pago como referencia; no replicar tabla de pagos ni client_secret
            await db.reserva_entrada.update_one(
                {"id_reserva": id_reserva},
                {"$set": {"id_pago": id_pago_generado}}
            )
             
        # Paralelo: Notificar al catálogo el nuevo stock reservado
        asyncio.create_task(CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, token_jwt))
             
        if nuevo_stock == 0:
            asyncio.create_task(BrokerService.publish_event("entradas.evento.stock.v1", {"id_evento": compra.id_evento, "stock": 0}))
            asyncio.create_task(BrokerService.publish_event("stock.agotado", {"id_evento": compra.id_evento, "stock": 0}))

        return {
            "nuevo_stock": nuevo_stock,
            "id_reserva": id_reserva,
            "id_pago": id_pago_generado,
            "estado_pago": pago.get("estado_pago", "PENDIENTE") if isinstance(pago, dict) else "PENDIENTE",
            "url_checkout": pago.get("url_checkout") if isinstance(pago, dict) else None,
            "metodo": pago.get("metodo") if isinstance(pago, dict) else compra.metodo,
            "fecha_creacion": pago.get("fecha_creacion") if isinstance(pago, dict) else None,
            "fecha_expiracion": pago.get("fecha_expiracion") if isinstance(pago, dict) else expira_en.isoformat()
        }

@router.get(
    "/{id_ticket}", 
    tags=["Servicios Provistos (BE3) - Check-in"],
    responses={
        200: {"description": "Datos de la entrada retornados exitosamente"},
        400: {"description": "Datos de solicitud incompletos o id_ticket con formato inválido"},
        404: {"description": "La entrada asociada al id_ticket no existe"},
        500: {"description": "Error interno del servicio de Entradas / Inventario"},
        503: {"description": "Servicio temporalmente no disponible"}
    }
)
async def consultar_entrada_checkin(id_ticket: str):
    """
    ###  Propósito
    Permite al microservicio de Check-in consultar la validez y los datos de una entrada física o digital mediante su ID o QR (Soporte a Contrato Check-in v1.1).
    """
    if not id_ticket:
        raise HTTPException(status_code=400, detail="El id_ticket es obligatorio.")
        
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
        
    entrada = await db.entrada.find_one({"id_entrada": id_ticket})
    if not entrada:
        raise HTTPException(status_code=404, detail="La entrada no existe.")
        
    return {
        "id_ticket": entrada["id_entrada"],
        "nombre_usuario": entrada.get("nombre_usuario", "Sebastián Fuentes"), 
        "usuario": {
            "id_usuario": entrada["id_usuario"],
            "rol_usuario": entrada.get("rol_usuario", "usuario").lower()
        }
    }

@router.get(
    "/eventos/{id_evento}/stock", 
    tags=["Servicios Provistos (BE3) - Panel Organizador"],
    responses={
        200: {"description": "Stock retornado exitosamente"},
        404: {"description": "Evento no encontrado"},
        500: {"description": "Error interno del servidor"}
    }
)
async def consultar_stock_panel(id_evento: str):
    """
    ###  Propósito
    Expone la disponibilidad exacta y real de un evento para que el Panel Organizador pueda auditar o validar lógicas de negocio (Soporte a Contrato Panel v3.0).
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")
        
    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
        
    return {
        "id_evento": evento["id_evento"],
        "stock": evento["stock_actual"]
    }

# ==========================================
# HU-04: Visualización de Detalles de la Entrada Adquirida (#5)
# ==========================================

@router.get(
    "/usuario/{id_usuario}",
    tags=["Servicios Provistos (BE3) - Clientes / Entradas"],
    response_model=List[DetalleEntradaAdquirida],
    responses={
        200: {"description": "Historial de entradas adquiridas por el cliente retornado con éxito."},
        500: {"description": "Error al conectar con la base de datos."}
    }
)
async def obtener_historial_entradas_usuario(id_usuario: str):
    """
    ### 🎟️ Propósito (HU-04)
    Permite al cliente visualizar el historial completo de entradas adquiridas vinculadas a su cuenta.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")
        
    cursor = db.entrada.find({"id_usuario": id_usuario}).sort("fecha_emision", -1)
    entradas = await cursor.to_list(length=100)
    
    resultado = []
    for ent in entradas:
        id_res = ent.get("id_reserva", "")
        id_evt = ent.get("id_evento", "")
        if not id_evt and id_res:
            res_doc = await db.reserva_entrada.find_one({"id_reserva": id_res})
            if res_doc:
                id_evt = res_doc.get("id_evento", "")

        qr_field = ent.get("qr_data")
        qr_val = qr_field.get("url") if isinstance(qr_field, dict) else (qr_field or f"https://storage.midominio.com/qr/{ent.get('id_entrada')}.png")

        resultado.append({
            "id_entrada": ent.get("id_entrada"),
            "id_reserva": id_res,
            "id_evento": id_evt,
            "nombre_evento": ent.get("nombre_evento") or f"Evento {id_evt}",
            "id_usuario": ent.get("id_usuario", id_usuario),
            "nombre_usuario": ent.get("nombre_usuario", "Cliente"),
            "rut_usuario": ent.get("rut_usuario"),
            "correo_usuario": ent.get("correo_usuario"),
            "tipo_acceso": ent.get("tipo_acceso", "GENERAL"),
            "lugar_ingreso": ent.get("lugar_ingreso", "Puerta Principal - Acceso General"),
            "precio_final_pagado": ent.get("precio_final_pagado", 0),
            "estado_entrada": ent.get("estado_entrada", "EMITIDA"),
            "nombre_archivo_qr": ent.get("nombre_archivo_qr", f"{ent.get('id_entrada')}.png"),
            "qr_data": qr_val,
            "fecha_emision": ent.get("fecha_emision") or datetime.utcnow()
        })
        
    return resultado

@router.get(
    "/{id_ticket}/detalle",
    tags=["Servicios Provistos (BE3) - Clientes / Entradas"],
    response_model=DetalleEntradaAdquirida,
    responses={
        200: {"description": "Detalle inmutable de la entrada obtenido correctamente."},
        404: {"description": "Entrada no encontrada."},
        500: {"description": "Error al conectar con la base de datos."}
    }
)
async def obtener_detalle_entrada(id_ticket: str):
    """
    ### 🎟️ Propósito (HU-04)
    Permite al cliente o al sistema visualizar en detalle los datos inmutables de una entrada adquirida específica.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")
        
    entrada = await db.entrada.find_one({"id_entrada": id_ticket})
    if not entrada:
        raise HTTPException(status_code=404, detail="La entrada solicitada no existe.")
        
    reserva = await db.reserva_entrada.find_one({"id_reserva": entrada.get("id_reserva")})
    id_evento = entrada.get("id_evento") or (reserva.get("id_evento", "") if reserva else "")
    qr_field = entrada.get("qr_data")
    qr_val = qr_field.get("url") if isinstance(qr_field, dict) else (qr_field or f"https://storage.midominio.com/qr/{entrada.get('id_entrada')}.png")

    return {
        "id_entrada": entrada.get("id_entrada"),
        "id_reserva": entrada.get("id_reserva", ""),
        "id_evento": id_evento,
        "nombre_evento": entrada.get("nombre_evento") or f"Evento {id_evento}",
        "id_usuario": entrada.get("id_usuario", ""),
        "nombre_usuario": entrada.get("nombre_usuario", "Cliente"),
        "rut_usuario": entrada.get("rut_usuario") or (reserva.get("rut_usuario") if reserva else None),
        "correo_usuario": entrada.get("correo_usuario") or (reserva.get("correo_usuario") if reserva else None),
        "tipo_acceso": entrada.get("tipo_acceso", "GENERAL"),
        "lugar_ingreso": entrada.get("lugar_ingreso", "Puerta Principal - Acceso General"),
        "precio_final_pagado": entrada.get("precio_final_pagado", 0),
        "estado_entrada": entrada.get("estado_entrada", "EMITIDA"),
        "nombre_archivo_qr": entrada.get("nombre_archivo_qr", f"{entrada.get('id_entrada')}.png"),
        "qr_data": qr_val,
        "fecha_emision": entrada.get("fecha_emision") or datetime.utcnow()
    }

# ==========================================
# HU-05: Recepción de Código QR de Acceso (#6)
# ==========================================

@router.get(
    "/{id_ticket}/qr",
    tags=["Servicios Provistos (BE3) - Clientes / Entradas"],
    response_model=CodigoQRAccesoResponse,
    responses={
        200: {"description": "Código QR de acceso y habilitación en Check-in retornados con éxito."},
        400: {"description": "La entrada está anulada o no válida para acceso."},
        404: {"description": "Entrada no encontrada."},
        500: {"description": "Error al conectar con la base de datos."}
    }
)
async def obtener_qr_acceso(id_ticket: str):
    """
    ### 📱 Propósito (HU-05)
    Proporciona al cliente su código QR de acceso inmediatamente después de la emisión de la entrada.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Servicio de base de datos no disponible.")
        
    entrada = await db.entrada.find_one({"id_entrada": id_ticket})
    if not entrada:
        raise HTTPException(status_code=404, detail="La entrada solicitada no existe.")
        
    if entrada.get("estado_entrada") == "ANULADA":
        raise HTTPException(status_code=400, detail="La entrada se encuentra anulada y no puede ser utilizada para acceso.")
        
    reserva = await db.reserva_entrada.find_one({"id_reserva": entrada.get("id_reserva")})
    id_evento = entrada.get("id_evento") or (reserva.get("id_evento", "") if reserva else "")
    qr_field = entrada.get("qr_data")
    qr_val = qr_field.get("url") if isinstance(qr_field, dict) else (qr_field or f"https://storage.midominio.com/qr/{entrada['id_entrada']}.png")

    return {
        "id_entrada": entrada["id_entrada"],
        "id_evento": id_evento,
        "nombre_asistente": entrada.get("nombre_usuario", "Asistente"),
        "nombre_evento": entrada.get("nombre_evento") or f"Evento {id_evento}",
        "lugar_ingreso": entrada.get("lugar_ingreso", "Puerta Principal - Acceso General"),
        "tipo_acceso": entrada.get("tipo_acceso", "GENERAL"),
        "qr_data": qr_val,
        "qr_payload": {
            "id_evento": id_evento,
            "id_entrada": entrada["id_entrada"]
        },
        "habilitado_checkin": entrada.get("estado_entrada") == "EMITIDA"
    }
