import os
import httpx


class CatalogoService:
    BASE_URL = os.getenv("CATALOGO_SERVICE_URL", "http://ticketu-api-gateway:8080")
    TIMEOUT_SECONDS = float(os.getenv("CATALOGO_TIMEOUT_SECONDS", "2.0"))

    @classmethod
    async def actualizar_stock_catalogo(cls, id_evento: str, nuevo_stock: int, token_sesion: str = "") -> bool:
        """
        Contrato: Entradas <-> Catálogo de Eventos v3.0
        Consumidor: Entradas / Inventario
        Actualización estricta vía PUT HTTP REST enviando el nuevo stock y token_sesion en el body.
        """
        base_url = os.getenv("CATALOGO_SERVICE_URL", cls.BASE_URL)
        url = f"{base_url}/api/catalogo/eventos/{id_evento}/stock"
        token_efectivo = (token_sesion or os.getenv("CATALOGO_SYNC_TOKEN", "entradas-service-sync")).strip()
        payload = {
            "nuevo_stock": int(nuevo_stock),
            "token_sesion": token_efectivo,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=payload, timeout=cls.TIMEOUT_SECONDS)
                if response.status_code in (200, 204):
                    return True
                print(
                    f"[Catálogo] Error HTTP {response.status_code} al actualizar stock de '{id_evento}' a {nuevo_stock}: {response.text}"
                )
                return False
            except httpx.RequestError as exc:
                print(f"[Catálogo] Error de red comunicando con Catálogo ({url}): {exc}")
                return False
