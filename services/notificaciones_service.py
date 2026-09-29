import httpx

class NotificacionesService:
    BASE_URL = "http://notificaciones-service:8000"

    @classmethod
    async def enviar_ticket_correo(cls, id_usuario: str, nombre_evento: str, fecha_evento: str, qr_data: str) -> bool:
        """
        Contrato: Contrato_Entradas_Notificaciones_v2.docx
        Entradas (Consumidor) -> Notificaciones (Proveedor)
        Se eliminó cantidad_entradas del payload según contrato v2.
        """
        url = f"{cls.BASE_URL}/api/v1/notificaciones/ticket"
        payload = {
            "id_usuario": id_usuario,
            "nombre_evento": nombre_evento,
            "fecha_evento": fecha_evento,
            "qr_data": qr_data
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload)
                return response.status_code == 200
            except httpx.RequestError as exc:
                print(f"Error comunicando con Notificaciones: {exc}")
                return False
