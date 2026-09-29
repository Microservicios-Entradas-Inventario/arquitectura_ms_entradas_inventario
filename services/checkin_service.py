import httpx

class CheckinService:
    BASE_URL = "http://checkin-service:8000"

    @classmethod
    async def registrar_ticket_puerta(cls, id_entrada: str, id_evento: str, id_usuario: str, nombre_usuario: str, qr_data: str) -> bool:
        """
        Contrato: Contrato_Entradas_Checkin.docx
        Entradas (Consumidor) -> Check-in (Proveedor)
        Envío en paralelo del ticket consolidado para registro rápido en puerta.
        """
        url = f"{cls.BASE_URL}/api/v1/checkin/tickets"
        payload = {
            "id_entrada": id_entrada,
            "id_evento": id_evento,
            "id_usuario": id_usuario,
            "nombre_usuario": nombre_usuario,
            "qr_data": qr_data
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload)
                return response.status_code == 200
            except httpx.RequestError as exc:
                print(f"Error comunicando con Checkin: {exc}")
                return False
