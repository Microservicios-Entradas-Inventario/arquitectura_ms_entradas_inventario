import json

class NotificacionesService:
    @classmethod
    async def enviar_ticket_correo(cls, correo_comprador: str, nombre_comprador: str, nombre_evento: str, fecha_evento: str, hora_evento: str, qr_data: str) -> bool:
        """
        Contrato: Notificaciones (Consumidor) <-> Entradas (Proveedor) v1.1
        Tipo: Asíncrono (RabbitMQ) - Evento: entradas_emitidas
        """
        payload = {
            "correo_comprador": correo_comprador,
            "nombre_comprador": nombre_comprador,
            "nombre_evento": nombre_evento,
            "fecha_evento": fecha_evento,
            "hora_evento": hora_evento,
            "qr_data": qr_data
        }
        
        # Simulación de publicación en RabbitMQ
        mensaje = json.dumps(payload, ensure_ascii=False)
        print(f"[RabbitMQ - Mock] Evento 'entradas_emitidas' publicado para Notificaciones -> {mensaje}")
        
        return True
