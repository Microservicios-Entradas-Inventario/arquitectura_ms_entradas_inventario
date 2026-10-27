from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from database import connect_to_mongo, close_mongo_connection, get_database
from services.broker_service import BrokerService

from routers.inventario import router as inventario_router
from routers.entradas import router as entradas_router
from routers.reservas import router as reservas_router

async def tarea_liberacion_reservas_expiradas():
    """
    Tarea en segundo plano (HU-03): Revisa periódicamente reservas temporales vencidas
    y libera automáticamente los cupos al pool de stock disponible si no se confirmó el pago.
    """
    while True:
        try:
            await asyncio.sleep(15)  # Chequeo cada 15 segundos
            db = get_database()
            if db is not None:
                ahora = datetime.utcnow()
                # Buscar reservas en estado RESERVADO cuya fecha de expiración haya pasado
                cursor = db.reserva_entrada.find({
                    "estado_reserva": "RESERVADO",
                    "fecha_expiracion": {"$lt": ahora, "$ne": None}
                })
                reservas_vencidas = await cursor.to_list(length=100)
                for res in reservas_vencidas:
                    cant = res.get("cantidad_entrada", 1)
                    id_res = res.get("id_reserva")
                    id_evt = res.get("id_evento")
                    
                    # Actualizar estado a EXPIRADO
                    await db.reserva_entrada.update_one(
                        {"_id": res["_id"]},
                        {"$set": {"estado_reserva": "EXPIRADO"}}
                    )
                    # Retornar cupo al pool de stock disponible
                    await db.inventario_evento.update_one(
                        {"id_evento": id_evt},
                        {"$inc": {"stock_actual": cant, "cantidad_entrada_reservada": -cant}}
                    )
                    print(f"[HU-03 Auto-Release] Reserva '{id_res}' expirada. Se liberaron {cant} cupo(s) al stock de '{id_evt}'.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[HU-03 Auto-Release] Error en monitoreo de expiraciones: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conectar a MongoDB
    await connect_to_mongo()
    # Conectar al Event Broker compartido (RabbitMQ)
    await BrokerService.connect()
    # Iniciar monitor de expiración de reservas en segundo plano (HU-03)
    worker_expiracion = asyncio.create_task(tarea_liberacion_reservas_expiradas())
    yield
    worker_expiracion.cancel()
    # Cerrar broker y base de datos
    await BrokerService.close()
    await close_mongo_connection()

app = FastAPI(
    title="TicketU - API de Entradas e Inventario",
    description="Microservicio central de Entradas e Inventario. "
                "Soporta HU-01 (Inventario), HU-02 (Compra), HU-03 (Reserva Temporal Hold), "
                "HU-04 (Detalle de Entrada) y HU-05 (Recepción de QR). "
                "Integrado con el API Gateway de TicketU y el Event Broker compartido (RabbitMQ).",
    version="2.1.0",
    lifespan=lifespan
)

# Endpoint de diagnóstico para el Gateway y Docker Healthcheck
@app.get("/health", tags=["Salud del Servicio"])
async def health_check():
    return {
        "status": "UP",
        "service": "entradas-service",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# Rutas oficiales del API Gateway de TicketU (/api/entradas/*)
# ============================================================================
app.include_router(entradas_router, prefix="/api/entradas")
app.include_router(inventario_router, prefix="/api/entradas/inventario")
app.include_router(reservas_router, prefix="/api/entradas/reservas")

# ============================================================================
# Rutas v1 (Compatibilidad directa y retrocompatibilidad de contratos)
# ============================================================================
app.include_router(inventario_router, prefix="/api/v1/inventario")
app.include_router(entradas_router, prefix="/api/v1/entradas")
app.include_router(reservas_router, prefix="/api/v1/reservas")

