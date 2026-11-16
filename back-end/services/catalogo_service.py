import os
import httpx

class CatalogoService:
    BASE_URL = os.getenv("CATALOGO_SERVICE_URL", "http://ticketu-api-gateway:8080")

    @classmethod
    async def actualizar_stock_catalogo(cls, id_evento: str, nuevo_stock: int, token_sesion: str) -> bool:
        """
        Contrato: Entradas <-> Catálogo de Eventos v3.0
        Consumidor: Entradas / Inventario
        Actualización estricta vía PUT HTTP REST enviando el nuevo stock y el token en el body.
        """
        url = f"{cls.BASE_URL}/api/catalogo/eventos/{id_evento}/stock"
        payload = {
            "nuevo_stock": nuevo_stock,
            "token_sesion": token_sesion
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=payload, timeout=2.0)
                return response.status_code in [200, 204]
            except httpx.RequestError as exc:
                print(f"Error comunicando con Catálogo: {exc}")
                return False
