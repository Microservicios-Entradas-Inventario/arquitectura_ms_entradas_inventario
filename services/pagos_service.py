import httpx
from typing import Dict

class PagosService:
    BASE_URL = "http://pagos-service:8000" # URL del microservicio de Pagos (ejemplo)

    @classmethod
    async def iniciar_cobro(cls, id_reserva: str, total: int, cantidad_entradas: int, token_sesion: str) -> Dict:
        """
        Contrato: Entradas/Inventario <-> Pagos v2.0 (Flujo Asíncrono)
        Consumidor: Entradas / Inventario
        Inicia la intención de pago síncrona, esperando consolidación vía RabbitMQ.
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/transacciones"
        payload = {
            "id_reserva": id_reserva,
            "total": total,
            "cantidad_entradas": cantidad_entradas,
            "token_sesion": token_sesion
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 2000ms según contrato
                response = await client.post(url, json=payload, timeout=2.0)
                if response.status_code == 200:
                    return response.json()
                return {"id_pago": None, "estado_pago": "ERROR"}
            except httpx.RequestError as exc:
                print(f"Error comunicando con Pagos: {exc}")
                return {"id_pago": None, "estado_pago": "ERROR"}

    @classmethod
    async def consultar_estado_pago(cls, id_pago: str) -> Dict:
        """
        Operación de Fallback (Opcional): Si Entradas no recibe evento por el broker 
        después del tiempo máximo (15 mins), puede consultar el estado final.
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/{id_pago}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=1.0)
                if response.status_code == 200:
                    return response.json()
                return {"estado_pago": "DESCONOCIDO"}
            except httpx.RequestError as exc:
                print(f"Error de fallback comunicando con Pagos: {exc}")
                return {"estado_pago": "DESCONOCIDO"}
