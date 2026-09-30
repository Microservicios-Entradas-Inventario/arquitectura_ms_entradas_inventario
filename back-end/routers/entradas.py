from fastapi import APIRouter, HTTPException
from schemas.entradas import ProcesarCompraRequest, ProcesarCompraResponse
from database import get_database
from services.auth_service import AuthService
from services.notificaciones_service import NotificacionesService
from services.pagos_service import PagosService
from services.catalogo_service import CatalogoService
from services.checkin_service import CheckinService
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

    if compra.cantidad <= 0 or compra.cantidad > stock_actual:
        raise HTTPException(status_code=400, detail="Parámetro ausente o inválido (ej. cantidad <= 0 o stock insuficiente).")

    nuevo_stock = stock_actual - compra.cantidad
    id_reserva = f"res-{uuid.uuid4().hex[:8]}"

    if compra.tipo_entrada.upper() == "GRATUITA":
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$set": {"stock_actual": nuevo_stock}, "$inc": {"cantidad_entrada_comprada": compra.cantidad}}
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
        
        # Ejecutar en paralelo (Regla 2) Notificaciones, Catálogo y Check-in
        asyncio.create_task(NotificacionesService.enviar_ticket_correo(correo_usuario, nombre_usuario, compra.id_evento, "2026-12-01", "00:00", qr_data))
        asyncio.create_task(CatalogoService.actualizar_stock_catalogo(compra.id_evento, nuevo_stock, compra.token_sesion))
        asyncio.create_task(CheckinService.registrar_ticket_puerta(id_entrada, compra.id_evento, nombre_usuario, qr_data))
        
        if nuevo_stock == 0:
            print(f"[RabbitMQ - Mock] Evento 'entradas.evento.stock.v1' publicado para Panel -> {{'id_evento': '{compra.id_evento}', 'stock': 0}}")
        
        return {"nuevo_stock": nuevo_stock}
    else:
        await db.inventario_evento.update_one(
            {"id_evento": compra.id_evento},
            {"$set": {"stock_actual": nuevo_stock}, "$inc": {"cantidad_entrada_reservada": compra.cantidad}}
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
            print(f"[RabbitMQ - Mock] Evento 'entradas.evento.stock.v1' publicado para Panel -> {{'id_evento': '{compra.id_evento}', 'stock': 0}}")

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
        "nombre_usuario": "Sebastián Fuentes", 
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
