from fastapi import APIRouter, HTTPException
from schemas.entradas import InventarioResponse
from database import get_database

router = APIRouter()


@router.get(
    "/{id_evento}",
    tags=["Servicios Propios (BE1)"],
    response_model=InventarioResponse,
    responses={
        200: {"description": "Disponibilidad obtenida exitosamente"},
        404: {"description": "Evento no encontrado"},
        500: {"description": "Error interno al consultar la base de datos"},
    },
)
@router.get(
    "/disponibilidad/{id_evento}",
    tags=["Servicios Propios (BE1)"],
    response_model=InventarioResponse,
    include_in_schema=False,
)
async def obtener_disponibilidad(id_evento: str):
    """
    Permite consultar la disponibilidad de stock actual, tipo de entrada y precio unitario de un evento (HU-01).
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")

    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    return {
        "id_evento": id_evento,
        "stock_actual": int(evento.get("stock_actual", 0)),
        "tipo_entrada": evento.get("tipo_entrada", "PAGADA"),
        "precio_unitario": int(evento.get("precio_unitario", 0)),
    }
