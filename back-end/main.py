from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from database import connect_to_mongo, close_mongo_connection, get_database
from schemas.entradas import HealthResponse
from services.broker_service import BrokerService
from services.pagos_service import PagosService
from services.panel_service import PanelService

from routers.inventario import router as inventario_router
from routers.entradas import router as entradas_router
from routers.reservas import (
    router as reservas_router,
    consolidar_y_emitir_entradas,
    liberar_reserva_y_anular_pago,
    obtener_cookie_reserva,
)


async def tarea_liberacion_reservas_expiradas():
    """
    Tarea en segundo plano (HU-03 + Contrato Pagos Operación 4):
    Revisa periódicamente reservas temporales vencidas, cambia su estado a EXPIRADO,
    libera los cupos al stock disponible y, si tenía un id_pago, solicita anulación/reembolso en Pagos.
    """
    while True:
        try:
            await asyncio.sleep(15)
            db = get_database()
            if db is not None:
                ahora = datetime.utcnow()
                cursor = db.reserva_entrada.find(
                    {
                        "estado_reserva": "RESERVADO",
                        "fecha_expiracion": {"$lt": ahora, "$ne": None},
                    }
                )
                reservas_vencidas = await cursor.to_list(length=100)
                for res in reservas_vencidas:
                    cant = int(res.get("cantidad_entrada", 1))
                    id_res = res.get("id_reserva")
                    id_evt = res.get("id_evento")

                    await liberar_reserva_y_anular_pago(
                        db=db,
                        reserva=res,
                        nuevo_estado="EXPIRADO",
                        motivo="Hold de la reserva vencido: el usuario pagó fuera de plazo",
                        cookie_header=obtener_cookie_reserva(id_res),
                        anular_en_pagos=True,
                    )
                    print(
                        f"[HU-03 Auto-Release] Reserva '{id_res}' expirada. Se liberaron {cant} cupo(s) al stock de '{id_evt}'."
                    )
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[HU-03 Auto-Release] Error en monitoreo de expiraciones: {e}")


async def tarea_polling_pagos_pendientes():
    """
    Tarea en segundo plano de respaldo (Contrato Pagos Operación 3):
    Complementa los eventos RabbitMQ (`pago.realizado` / `pago.rechazado`) consultando
    periódicamente el estado de reservas activas con `id_pago`.
    """
    while True:
        try:
            await asyncio.sleep(5)
            db = get_database()
            if db is not None:
                ahora = datetime.utcnow()
                cursor = db.reserva_entrada.find(
                    {
                        "estado_reserva": "RESERVADO",
                        "id_pago": {"$ne": None},
                        "$or": [
                            {"fecha_expiracion": {"$gt": ahora}},
                            {"fecha_expiracion": None},
                        ],
                    }
                )
                reservas_con_pago = await cursor.to_list(length=100)
                for res in reservas_con_pago:
                    id_pago = res.get("id_pago")
                    id_res = res.get("id_reserva")
                    cookie_reenvio = obtener_cookie_reserva(id_res)
                    if not id_pago or (not cookie_reenvio and not PagosService.STAFF_COOKIE):
                        continue

                    info_pago = await PagosService.consultar_estado_pago(
                        id_pago=id_pago,
                        cookie_header=cookie_reenvio,
                    )
                    estado_pago = info_pago.get("estado_pago", "PENDIENTE")

                    if estado_pago == "APROBADO":
                        entradas = await consolidar_y_emitir_entradas(db, res, id_pago=id_pago)
                        print(
                            f"[Polling Pagos] Pago '{id_pago}' APROBADO. Reserva '{id_res}' consolidada y {len(entradas)} entrada(s) emitida(s)."
                        )
                    elif estado_pago in ("RECHAZADO", "ANULADO", "REEMBOLSADO"):
                        await liberar_reserva_y_anular_pago(
                            db=db,
                            reserva=res,
                            nuevo_estado="EXPIRADO" if estado_pago == "RECHAZADO" else "CANCELADO",
                            anular_en_pagos=False,
                        )
                        print(
                            f"[Polling Pagos] Pago '{id_pago}' en estado '{estado_pago}'. Reserva '{id_res}' liberada."
                        )
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Polling Pagos] Error en monitoreo de pagos pendientes: {e}")


async def tarea_sincronizacion_panel():
    """Sincroniza periódicamente eventos publicados desde Panel Organizador como respaldo a RabbitMQ."""
    while True:
        try:
            await asyncio.sleep(30)
            db = get_database()
            if db is not None:
                await PanelService.sincronizar_eventos_panel(db)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Panel Sync] Error en sincronización periódica: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    asyncio.create_task(PanelService.sincronizar_eventos_panel(get_database()))
    await BrokerService.connect()
    worker_expiracion = asyncio.create_task(tarea_liberacion_reservas_expiradas())
    worker_polling_pagos = asyncio.create_task(tarea_polling_pagos_pendientes())
    worker_sync_panel = asyncio.create_task(tarea_sincronizacion_panel())
    yield
    worker_expiracion.cancel()
    worker_polling_pagos.cancel()
    worker_sync_panel.cancel()
    await BrokerService.close()
    await close_mongo_connection()


app = FastAPI(
    title="TicketU - API de Entradas e Inventario",
    description=(
        "Microservicio de Entradas e Inventario de TicketU. "
        "Soporta HU-01 (Disponibilidad), HU-02 (Compra), HU-03 (Reserva Temporal Hold), "
        "HU-04 (Historial y Detalle de Entrada) y HU-05 (Código QR de Acceso). "
        "Integrado con Auth, Pagos, Catálogo, Check-in, Panel Organizador, Promociones, "
        "Notificaciones, API Gateway y RabbitMQ."
    ),
    version="2.4.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Salud del Servicio"], response_model=HealthResponse, include_in_schema=False)
@app.get("/api/entradas/health", tags=["Salud del Servicio"], response_model=HealthResponse)
async def health_check():
    return {
        "status": "UP",
        "service": "entradas-service",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Rutas oficiales del API Gateway de TicketU (/api/entradas/*) — documentadas en Swagger
app.include_router(inventario_router, prefix="/api/entradas/inventario")
app.include_router(reservas_router, prefix="/api/entradas/reservas")
app.include_router(entradas_router, prefix="/api/entradas")

# Alias v1 de retrocompatibilidad (ocultos en Swagger para evitar duplicación)
app.include_router(inventario_router, prefix="/api/v1/inventario", include_in_schema=False)
app.include_router(inventario_router, prefix="/api/v1/entradas/inventario", include_in_schema=False)
app.include_router(reservas_router, prefix="/api/v1/reservas", include_in_schema=False)
app.include_router(reservas_router, prefix="/api/v1/entradas/reservas", include_in_schema=False)
app.include_router(entradas_router, prefix="/api/v1/entradas", include_in_schema=False)
