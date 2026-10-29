from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from database import connect_to_mongo, close_mongo_connection, get_database
from services.broker_service import BrokerService
from services.pagos_service import PagosService

from routers.inventario import router as inventario_router
from routers.entradas import router as entradas_router
from routers.reservas import (
    router as reservas_router,
    consolidar_y_emitir_entradas,
    liberar_reserva_y_anular_pago
)


async def tarea_liberacion_reservas_expiradas():
    """
    Tarea en segundo plano (HU-03 + Contrato Pagos v2.3 Operación 4):
    Revisa periódicamente reservas temporales vencidas, libera automáticamente los cupos al pool
    de stock disponible y, si la reserva tenía un pago creado en Pagos (`id_pago`), invoca
    `POST /api/v1/pagos/{id_pago}/reembolso` reenviando el header `Cookie` (`jwt`) para anular o reembolsar el cobro.
    """
    while True:
        try:
            await asyncio.sleep(15)  # Chequeo cada 15 segundos
            db = get_database()
            if db is not None:
                ahora = datetime.utcnow()
                cursor = db.reserva_entrada.find({
                    "estado_reserva": "RESERVADO",
                    "fecha_expiracion": {"$lt": ahora, "$ne": None}
                })
                reservas_vencidas = await cursor.to_list(length=100)
                for res in reservas_vencidas:
                    cant = res.get("cantidad_entrada", 1)
                    id_res = res.get("id_reserva")
                    id_evt = res.get("id_evento")

                    await liberar_reserva_y_anular_pago(
                        db=db,
                        reserva=res,
                        nuevo_estado="EXPIRADO",
                        motivo="Hold de la reserva vencido: el usuario pagó fuera de plazo",
                        cookie_header=res.get("cookie_header") or res.get("token_sesion"),
                        anular_en_pagos=True
                    )
                    print(f"[HU-03 Auto-Release] Reserva '{id_res}' expirada. Se liberaron {cant} cupo(s) al stock de '{id_evt}'.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[HU-03 Auto-Release] Error en monitoreo de expiraciones: {e}")


async def tarea_polling_pagos_pendientes():
    """
    Tarea en segundo plano (Contrato Pagos <-> Entradas v2.3, Sección 3.3, 5 y 9):
    Mientras Pagos no publique eventos en el broker, Entradas consulta cada 5 segundos
    `GET /api/v1/pagos/{id_pago}` reenviando el header `Cookie` (`jwt`) del comprador.
    - Si `estado_pago == APROBADO`: consolida la reserva y emite la entrada con QR.
    - Si `estado_pago == RECHAZADO / ANULADO / REEMBOLSADO`: libera el stock reservado.
    - Si Pagos responde `503 AUTH_NO_DISPONIBLE` o `PENDIENTE`: reintenta en el siguiente ciclo.
    """
    while True:
        try:
            await asyncio.sleep(5)  # Intervalo propuesto en Contrato Pagos v2.3: 5 segundos
            db = get_database()
            if db is not None:
                ahora = datetime.utcnow()
                cursor = db.reserva_entrada.find({
                    "estado_reserva": "RESERVADO",
                    "id_pago": {"$ne": None},
                    "$or": [
                        {"fecha_expiracion": {"$gt": ahora}},
                        {"fecha_expiracion": None}
                    ]
                })
                reservas_con_pago = await cursor.to_list(length=100)
                for res in reservas_con_pago:
                    id_pago = res.get("id_pago")
                    id_res = res.get("id_reserva")
                    cookie_reenvio = res.get("cookie_header") or res.get("token_sesion")
                    if not id_pago:
                        continue

                    info_pago = await PagosService.consultar_estado_pago(id_pago=id_pago, cookie_header=cookie_reenvio)
                    estado_pago = info_pago.get("estado_pago", "PENDIENTE")

                    if estado_pago == "APROBADO":
                        entradas = await consolidar_y_emitir_entradas(db, res, id_pago=id_pago)
                        print(f"[Polling Pagos v2.3] Pago '{id_pago}' APROBADO. Reserva '{id_res}' consolidada y {len(entradas)} entrada(s) emitida(s).")
                    elif estado_pago in ("RECHAZADO", "ANULADO", "REEMBOLSADO"):
                        await liberar_reserva_y_anular_pago(
                            db=db,
                            reserva=res,
                            nuevo_estado="EXPIRADO" if estado_pago == "RECHAZADO" else "CANCELADO",
                            anular_en_pagos=False
                        )
                        print(f"[Polling Pagos v2.3] Pago '{id_pago}' en estado '{estado_pago}'. Reserva '{id_res}' liberada.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Polling Pagos v2.3] Error en monitoreo de pagos pendientes: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conectar a MongoDB
    await connect_to_mongo()
    # Conectar al Event Broker compartido (RabbitMQ)
    await BrokerService.connect()
    # Iniciar monitor de expiración de reservas (HU-03 + Pagos v2.3 Op 4) y polling de pagos (Pagos v2.3 Op 3)
    worker_expiracion = asyncio.create_task(tarea_liberacion_reservas_expiradas())
    worker_polling_pagos = asyncio.create_task(tarea_polling_pagos_pendientes())
    yield
    worker_expiracion.cancel()
    worker_polling_pagos.cancel()
    # Cerrar broker y base de datos
    await BrokerService.close()
    await close_mongo_connection()


app = FastAPI(
    title="TicketU - API de Entradas e Inventario",
    description="Microservicio central de Entradas e Inventario. "
                "Soporta HU-01 (Inventario), HU-02 (Compra), HU-03 (Reserva Temporal Hold), "
                "HU-04 (Detalle de Entrada) y HU-05 (Recepción de QR). "
                "Integrado con Contrato Pagos <-> Entradas v2.3 (Cookie jwt), Auth, API Gateway y Event Broker (RabbitMQ).",
    version="2.3.0",
    lifespan=lifespan
)


# Endpoint de diagnóstico para Docker interno (/health) y a través del Gateway (/api/entradas/health)
@app.get("/health", tags=["Salud del Servicio"])
@app.get("/api/entradas/health", tags=["Salud del Servicio"])
async def health_check():
    return {
        "status": "UP",
        "service": "entradas-service",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Rutas oficiales del API Gateway de TicketU (/api/entradas/*)
# Se registran inventario y reservas antes de entradas_router para evitar colisión con /{id_ticket}
# ============================================================================
app.include_router(inventario_router, prefix="/api/entradas/inventario")
app.include_router(reservas_router, prefix="/api/entradas/reservas")
app.include_router(entradas_router, prefix="/api/entradas")

# ============================================================================
# Rutas v1 (Compatibilidad directa y Contrato Pagos v2.3 INT-01: /api/v1/entradas/reservas/{id_reserva})
# ============================================================================
app.include_router(inventario_router, prefix="/api/v1/inventario")
app.include_router(inventario_router, prefix="/api/v1/entradas/inventario")
app.include_router(reservas_router, prefix="/api/v1/reservas")
app.include_router(reservas_router, prefix="/api/v1/entradas/reservas")
app.include_router(entradas_router, prefix="/api/v1/entradas")
