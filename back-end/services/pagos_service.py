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
    async def consultar_estado_pago(cls, id_pago: str, token_sesion: str) -> Dict:
        """
        Operación de Fallback (Opcional): Si Entradas no recibe evento por el broker 
        después del tiempo máximo (15 mins), puede consultar el estado final.
        (Contrato Pagos v2.1)
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/{id_pago}"
        headers = {"Authorization": f"Bearer {token_sesion}"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=1.0)
                if response.status_code == 200:
                    return response.json()
                return {"estado_pago": "DESCONOCIDO"}
            except httpx.RequestError as exc:
                print(f"Error de fallback comunicando con Pagos: {exc}")
                return {"estado_pago": "DESCONOCIDO"}

    @classmethod
    async def anular_pago(cls, id_pago: str, motivo: str, token_servicio: str) -> bool:
        """
        Operación 4 (Anular o reembolsar un pago): Si la reserva vence o nos quedamos sin stock.
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/{id_pago}/reembolso"
        headers = {"Authorization": f"Bearer {token_servicio}"}
        payload = {"motivo": motivo}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload, timeout=2.0)
                return response.status_code == 200
            except httpx.RequestError as exc:
                print(f"Error anulando pago: {exc}")
                return False
