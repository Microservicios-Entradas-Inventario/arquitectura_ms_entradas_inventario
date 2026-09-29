import httpx
from typing import Optional, Dict

class PanelService:
    BASE_URL = "http://panel-service:8000"

    @classmethod
    async def obtener_info_evento(cls, id_evento: str) -> Optional[Dict]:
        """
        Contrato: Panel Organizador <-> Entradas / Inventario v1.2
        Consumidor: Entradas / Inventario
        Propósito: Recuperar o validar información maestra del evento ante desincronización.
        """
        url = f"{cls.BASE_URL}/api/v1/panel/eventos/{id_evento}"
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 300ms según contrato
                response = await client.get(url, timeout=0.3)
                if response.status_code == 200:
                    return response.json()
                return None
            except httpx.RequestError as exc:
                print(f"Error comunicando con Panel Organizador: {exc}")
                return None
