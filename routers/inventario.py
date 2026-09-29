from fastapi import APIRouter, HTTPException
from schemas.entradas import InventarioResponse
from database import get_database

router = APIRouter()

@router.get(
    "/{id_evento}", 
    tags=["Inventario (BE1)"], 
    response_model=InventarioResponse,
    responses={200: {"description": "Disponibilidad obtenida exitosamente"}, 404: {"description": "Evento no encontrado"}}
)
async def obtener_disponibilidad(id_evento: str):
    """
    ###  Propósito
    Permite consultar la disponibilidad de stock actual y detalles comerciales de un evento en específico. Es el servicio propio fundamental (Soporte a HU-01) para que los usuarios puedan ver si hay entradas disponibles antes de intentar comprarlas.

    ###  Parámetros
    - **`id_evento`** *(str) (Path)*: Identificador único del evento que se desea consultar.

    ###  Flujo de Funcionamiento
    1. Se recibe el `id_evento` por la ruta.
    2. Se abre una conexión asíncrona con la base de datos MongoDB.
    3. Se busca el documento del evento en la colección `inventario_evento`.
    4. Se retorna la información estructurada mediante el esquema `InventarioResponse`.

    ###  Códigos HTTP Posibles
    - **`200 OK`**: La disponibilidad fue obtenida y retornada exitosamente.
    - **`404 Not Found`**: El `id_evento` especificado no existe en la colección de inventario.
    - **`500 Internal Server Error`**: Ocurrió un problema de conexión con la base de datos MongoDB.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")
        
    evento = await db.inventario_evento.find_one({"id_evento": id_evento})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
        
    return {
        "id_evento": id_evento, 
        "stock_actual": evento.get("stock_actual", 0), 
        "tipo_entrada": evento.get("tipo_entrada", "PAGADA"), 
        "precio_unitario": evento.get("precio_unitario", 0)
    }
