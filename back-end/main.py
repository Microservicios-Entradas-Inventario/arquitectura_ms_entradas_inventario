from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import connect_to_mongo, close_mongo_connection

from routers.inventario import router as inventario_router
from routers.entradas import router as entradas_router
from routers.reservas import router as reservas_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="TicketU - API de Entradas e Inventario",
    description="Microservicio central de Entradas e Inventario. Expone servicios propios (BE1) y requeridos por otros (BE3).",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(inventario_router, prefix="/api/v1/inventario")
app.include_router(entradas_router, prefix="/api/v1/entradas")
app.include_router(reservas_router, prefix="/api/v1/reservas")
