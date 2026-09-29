import httpx

class NotificacionesService:
    BASE_URL = "http://notificaciones-service:8000"

    @classmethod
    async def enviar_ticket_correo(cls, correo_comprador: str, nombre_comprador: str, nombre_evento: str, fecha_evento: str, hora_evento: str, qr_data: str) -> bool:
        """
        Contrato: Entradas/Inventario <-> Notificaciones v3.0 (Reafirmación de arquitectura REST HTTP)
        Consumidor: Entradas / Inventario
        """
        url = f"{cls.BASE_URL}/api/v1/notificaciones/envio-ticket"
        payload = {
            "correo_comprador": correo_comprador,
            "nombre_comprador": nombre_comprador,
            "nombre_evento": nombre_evento,
            "fecha_evento": fecha_evento,
            "hora_evento": hora_evento,
            "qr_data": qr_data
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 200 ms
                response = await client.post(url, json=payload, timeout=0.2)
                return response.status_code in [200, 202]
            except httpx.RequestError as exc:
                print(f"Error comunicando con Notificaciones: {exc}")
                return False
