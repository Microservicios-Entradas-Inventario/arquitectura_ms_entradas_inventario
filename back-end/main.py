from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from database import connect_to_mongo, close_mongo_connection, get_database

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
    await connect_to_mongo()
    # Iniciar monitor de expiración de reservas en segundo plano (HU-03)
    worker_expiracion = asyncio.create_task(tarea_liberacion_reservas_expiradas())
    yield
    worker_expiracion.cancel()
    await close_mongo_connection()

app = FastAPI(
    title="TicketU - API de Entradas e Inventario",
    description="Microservicio central de Entradas e Inventario. "
                "Soporta HU-01 (Inventario), HU-02 (Compra), HU-03 (Reserva Temporal Hold), "
                "HU-04 (Detalle de Entrada) y HU-05 (Recepción de QR).",
    version="2.0.0",
    lifespan=lifespan
)

app.include_router(inventario_router, prefix="/api/v1/inventario")
app.include_router(entradas_router, prefix="/api/v1/entradas")
app.include_router(reservas_router, prefix="/api/v1/reservas")

