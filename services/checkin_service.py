import httpx

class CheckinService:
    BASE_URL = "http://checkin-service:8000"

    @classmethod
    async def registrar_ticket_puerta(cls, id_entrada: str, id_evento: str, nombre_usuario: str, qr_data: str) -> bool:
        """
        Contrato: Entradas/Inventario <-> Check-in v1.0
        Consumidor: Entradas / Inventario
        Envío en paralelo del ticket consolidado para registro rápido en puerta.
        """
        url = f"{cls.BASE_URL}/api/v1/checkin/tickets"
        payload = {
            "id_entrada": id_entrada,
            "id_evento": id_evento,
            "nombre_usuario": nombre_usuario,
            "qr_data": qr_data
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 300 ms
                response = await client.post(url, json=payload, timeout=0.3)
                return response.status_code == 200
            except httpx.RequestError as exc:
                print(f"Error comunicando con Checkin: {exc}")
                return False
