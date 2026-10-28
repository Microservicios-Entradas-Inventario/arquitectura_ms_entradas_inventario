from fastapi import APIRouter, HTTPException
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
from typing import List
import asyncio
from datetime import datetime, timedelta
import uuid

router = APIRouter()

@router.post(
    "/procesar-compra", 
    tags=["Servicios Provistos (BE3) - Catálogo"], 
    response_model=ProcesarCompraResponse,
    responses={
        200: {"description": "Compra procesada y stock actualizado"}, 
        400: {"description": "Parámetro ausente o inválido (ej. cantidad <= 0)"}, 
        401: {"description": "Token de sesión del cliente no válido o expirado"}, 
        404: {"description": "El evento o el tipo de entrada solicitado no existe"},
        500: {"description": "Error interno del servicio de Entradas / Inventario"}
    }
)
async def procesar_compra(compra: ProcesarCompraRequest):
    """
    ###  Propósito
    Punto de entrada principal para procesar una intención de compra iniciada desde el Catálogo. Descuenta el stock, valida la identidad, inicializa reservas y delega el cobro (si aplica) a Pagos, integrándose con todo el ecosistema (Soporte a Contrato Catálogo v2.0).

    ###  Parámetros
    - **`compra`** *(ProcesarCompraRequest) (Body)*: Objeto JSON con el `id_evento`, `tipo_entrada`, `cantidad` y `token_sesion`.

    ###  Flujo de Funcionamiento
    1. Se valida la sesión del usuario contra el microservicio de Autenticación (Auth v3.0). Se verifica que el rol tenga permisos (`CLIENTE`, `USUARIO`).
    2. Se comprueba que el evento exista, no esté cancelado y cuente con stock suficiente.
    3. Se descuenta el stock absoluto (`stock_actual`) de inmediato para evitar concurrencia.
    4. **(Si es Gratuita)**: Se consolida, se emite directamente el QR y se notifica en paralelo a Check-in y Catálogo.
    5. **(Si es Pagada)**: Se genera una reserva con TTL temporal y se invoca síncronamente a Pagos (Pagos v2.1) para iniciar el cobro. Posteriormente, se notifica en paralelo a Catálogo.
    6. Si el stock llega a 0, se publica proactivamente el mensaje de agotado al broker para el Panel Organizador.

    ###  Códigos HTTP Posibles
    - **`200 OK`**: Proceso completado, retorna el `nuevo_stock`.
    - **`400 Bad Request`**: Cantidad inválida, stock insuficiente o evento CANCELADO.
    - **`401 Unauthorized`**: Token de sesión ausente, inválido o expirado (Autenticación rechazada).
    - **`403 Forbidden`**: El usuario no tiene el rol necesario para comprar.
    - **`404 Not Found`**: El evento no existe.
    - **`500/503`**: Errores internos de BD o indisponibilidad de microservicios.
    """
    if not compra.token_sesion:
        raise HTTPException(status_code=401, detail="Falta el token de sesión requerido.")
        
    usuario_auth = await AuthService.validar_sesion(compra.token_sesion)
        
    id_usuario = usuario_auth.get("id_usuario")
    rol_usuario = usuario_auth.get("rol", "").upper()
    nombre_usuario = usuario_auth.get("nombre_completo", "Usuario Desconocido")
    correo_usuario = usuario_auth.get("correo_electronico", "correo@ejemplo.com")

    if rol_usuario not in ["CLIENTE", "USUARIO"]:
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

    if compra.cantidad <= 0 or compra.cantidad > stock_actual:
        raise HTTPException(status_code=400, detail="Parámetro ausente o inválido (ej. cantidad <= 0 o stock insuficiente).")

    nuevo_stock = stock_actual - compra.cantidad
    id_reserva = f"res-{uuid.uuid4().hex[:8]}"

    if compra.tipo_entrada.upper() == "GRATUITA":
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$set": {"stock_actual": nuevo_stock}, "$inc": {"cantidad_entrada_comprada": compra.cantidad}}
        )
        
        # Persistencia de nombre_usuario y correo_usuario acordada con Check-in (v2.1) y Notificaciones (v3)
        await db.reserva_entrada.insert_one({
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
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
            "rol_usuario": "CLIENTE",
            "tipo_acceso": "GENERAL",
            "precio_final_pagado": 0,
            "estado_entrada": "EMITIDA",
            "nombre_archivo_qr": f"gratis-{id_entrada}.png",
            "qr_data": qr_obj,
            "fecha_emision": datetime.utcnow()
        })
        
        # Estructura de QR para Check-in (Regla de negocio Contrato v2.1: Objeto JSON con id_evento e id_entrada)
        qr_checkin = {
            "id_evento": compra.id_evento,
            "id_entrada": id_entrada
        }
        
        # Ejecutar en paralelo (Regla 2): Notificaciones (v3), Catálogo y Check-in (v2.1)
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
        asyncio.create_task(CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, compra.token_sesion))
        asyncio.create_task(CheckinService.registrar_ticket_puerta(
            id_entrada=id_entrada,
            id_evento=compra.id_evento,
            nombre_usuario=nombre_usuario,
            qr_data=qr_checkin
        ))
        # Publicar evento entrada.emitida al Event Broker compartido
        asyncio.create_task(BrokerService.publish_event("entrada.emitida", {
            "id_entrada": id_entrada,
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
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
        
        return {"nuevo_stock": nuevo_stock}
    else:
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$set": {"stock_actual": nuevo_stock}, "$inc": {"cantidad_entrada_reservada": compra.cantidad}}
        )
        
        expira_en = datetime.utcnow() + timedelta(minutes=15)
        # Persistencia de nombre_usuario y correo_usuario al momento de la reserva (Acuerdo Check-in v2.1)
        await db.reserva_entrada.insert_one({
            "id_reserva": id_reserva,
            "id_evento": compra.id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
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
        
        # Ejecutar inicio de cobro (síncrono, necesitamos el id_pago)
        pago = await PagosService.iniciar_cobro(
            id_reserva=id_reserva, 
            total=int(precio_base), 
            cantidad_entradas=compra.cantidad,
            token_sesion=compra.token_sesion
        )
        
        if pago and "id_pago" in pago:
             await db.reserva_entrada.update_one(
                 {"id_reserva": id_reserva},
                 {"$set": {"id_pago": pago["id_pago"]}}
             )
             
        # Paralelo: Notificar al catálogo el nuevo stock reservado
        asyncio.create_task(CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, compra.token_sesion))
             
        if nuevo_stock == 0:
            asyncio.create_task(BrokerService.publish_event("entradas.evento.stock.v1", {"id_evento": compra.id_evento, "stock": 0}))
            asyncio.create_task(BrokerService.publish_event("stock.agotado", {"id_evento": compra.id_evento, "stock": 0}))

        return {"nuevo_stock": nuevo_stock}

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

    ###  Parámetros
    - **`id_ticket`** *(str) (Path)*: Identificador único de la entrada (ej. tk-998877).

    ###  Flujo de Funcionamiento
    1. Se valida el formato de entrada del `id_ticket`.
    2. Se busca la entrada en la colección `entrada` de la base de datos.
    3. Se estructura y formatea la respuesta anidada según los requerimientos estrictos de lectura que necesita el personal de puerta.

    ###  Códigos HTTP Posibles
    - **`200 OK`**: Entrada válida. Retorna ID, nombre y rol del usuario asociado.
    - **`400 Bad Request`**: No se proporcionó el parámetro obligatorio.
    - **`404 Not Found`**: El ticket no existe o no fue emitido legalmente.
    - **`503 Service Unavailable`**: La base de datos no se encuentra operativa.
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
            "rol_usuario": entrada["rol_usuario"].lower()
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
    Expone la disponibilidad exacta y real de un evento para que el Panel Organizador pueda auditar o validar lógicas de negocio, como por ejemplo, si puede eliminar físicamente un evento que aún no tiene ventas (Soporte a Contrato Panel v3.0).

    ###  Parámetros
    - **`id_evento`** *(str) (Path)*: Identificador único del evento que el Panel desea auditar.

    ###  Flujo de Funcionamiento
    1. Se recibe el ID por path parameter.
    2. Se consulta la base de datos de inventarios.
    3. Se devuelve inmediatamente la cantidad de `stock_actual` (fuente de verdad absoluta).

    ###  Códigos HTTP Posibles
    - **`200 OK`**: El stock fue consultado exitosamente.
    - **`404 Not Found`**: El evento consultado no fue encontrado.
    - **`500 Internal Server Error`**: Ocurrió un error general de conexión con la base de datos.
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
    
    ### 📋 Criterios de Aceptación (HU-04):
    1. **Detalle Completo e Inmutable**: Incluye el código alfanumérico único (`id_entrada`), precio final pagado (`precio_final_pagado`), tipo de acceso general (`tipo_acceso: GENERAL`), nombre del evento (`nombre_evento`), lugar físico de ingreso (`lugar_ingreso`), fecha de emisión y código QR.
    2. **Omisión de Asiento Numerado**: Dado que el tipo de evento es de entrada general, no se incluye ni se exige selección de asiento en mapa numerado.
    
    ### 📥 Parámetros
    - **`id_usuario`** *(str) (Path)*: Identificador único del usuario o cliente autenticado.
    
    ### 📤 Códigos HTTP
    - **`200 OK`**: Retorna el listado de entradas emitidas para el usuario (array vacío si aún no posee compras).
    - **`500 Internal Server Error`**: Falla en la persistencia o servicio de base de datos.
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
    
    ### 📋 Criterios de Aceptación (HU-04):
    - Presenta el identificador único (`id_entrada`), monto final pagado auditado, nombre del evento, y condiciones físicas de acceso (`lugar_ingreso`).
    - Omite selección de asientos numerados, indicando `tipo_acceso: GENERAL`.
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
        "correo_usuario": entrada.get("correo_usuario"),
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
    Proporciona al cliente su código QR de acceso inmediatamente después de la emisión de la entrada
    (inmediato en flujo gratuito o tras confirmación de pago en flujo pagado) y valida su habilitación
    para el control de acceso físico en Check-in.
    
    ### 📋 Criterios de Aceptación (HU-05):
    1. **Generación Inmediata / Post-Pago**: La entrada debe estar en estado `EMITIDA`.
    2. **Estructura del Código QR**: Contiene un payload JSON con `id_evento` e `id_entrada`, vinculado al nombre del asistente.
    3. **Habilitación en Check-in**: Se confirma que el ticket está listo y habilitado para lectura en torniquetes o escáneres de acceso.
    
    ### 📥 Parámetros
    - **`id_ticket`** *(str) (Path)*: Identificador único de la entrada (ej. `tk-998877`).
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
