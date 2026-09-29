import httpx

class CatalogoService:
    BASE_URL = "http://catalogo-service:8000"

    @classmethod
    async def actualizar_stock_catalogo(cls, id_evento: str, stock_actual: int, token: str) -> bool:
        """
        Contrato: Contrato_Entradas_Catalogo_REST_PUT.docx
        Entradas (Consumidor) -> Catálogo (Proveedor)
        Actualización estricta vía PUT HTTP REST enviando el token de sesión.
        """
        url = f"{cls.BASE_URL}/api/v1/catalogo/eventos/{id_evento}/stock"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"stock_actual": stock_actual}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=payload, headers=headers)
                return response.status_code in [200, 204]
            except httpx.RequestError as exc:
                print(f"Error comunicando con Catálogo: {exc}")
                return False
