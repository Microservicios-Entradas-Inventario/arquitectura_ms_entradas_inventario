import httpx
from typing import Dict

class PagosService:
    BASE_URL = "http://pagos-service:8000"

    @classmethod
    async def iniciar_cobro(cls, id_reserva: str, monto_total: int, id_usuario: str) -> Dict:
        """
        Contrato: Contrato_Entradas_Pagos_v2_Asincrono.docx
        Entradas (Consumidor) -> Pagos (Proveedor)
        Inicia el cobro por REST (obteniendo estado PENDIENTE).
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/iniciar"
        payload = {
            "id_reserva": id_reserva,
            "monto_total": monto_total,
            "id_usuario": id_usuario
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=2.0) # SLA < 2000 ms
                if response.status_code == 200:
                    return response.json() # ej: {"id_pago": "pay-123", "estado": "PENDIENTE"}
                return {"id_pago": None, "estado": "ERROR"}
            except httpx.RequestError as exc:
                print(f"Error comunicando con Pagos: {exc}")
                return {"id_pago": None, "estado": "ERROR"}
