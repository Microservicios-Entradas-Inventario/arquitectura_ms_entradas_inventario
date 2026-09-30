from pydantic import BaseModel, Field

class InventarioResponse(BaseModel):
    id_evento: str
    stock_actual: int
    tipo_entrada: str
    precio_unitario: int

class ProcesarCompraRequest(BaseModel):
    id_evento: str = Field(..., description="Identificador único del evento seleccionado.")
    tipo_entrada: str = Field(..., description="Tipo de entrada seleccionada (ej. General, VIP).")
    cantidad: int = Field(gt=0, description="Cantidad de entradas a comprar.")
    token_sesion: str = Field(..., description="Token de autenticación enviado por Catálogo.")

class ProcesarCompraResponse(BaseModel):
    nuevo_stock: int
