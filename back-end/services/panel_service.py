import os
import httpx
from typing import Optional, Dict

class PanelService:
    BASE_URL = os.getenv("PANEL_SERVICE_URL", "http://organizador-service:3000")

    @classmethod
    async def obtener_info_evento(cls, id_evento: str, token_sesion: Optional[str] = None) -> Optional[Dict]:
        """
        Contrato: Panel Organizador <-> Entradas / Inventario v3.0
        Consumidor: Entradas / Inventario
        Propósito: Fallback para rehidratar BD, o consultar estado ("CANCELADO") antes de operar.
        """
        url = f"{cls.BASE_URL}/api/v1/panel/eventos/{id_evento}"
        headers = {}
        if token_sesion:
            headers["Cookie"] = f"jwt={token_sesion}"
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 300ms según contrato
                response = await client.get(url, headers=headers, timeout=0.3)
                if response.status_code == 200:
                    return response.json()
                return None
            except httpx.RequestError as exc:
                print(f"Error comunicando con Panel Organizador: {exc}")
                return None
