import json
from typing import Dict, Any

class NotificacionesService:
    """
    Contrato de interfaz: <-> Notificaciones (Versión 3)
    Equipo consumidor: Notificaciones
    Equipo proveedor: Entradas
    Basado en: HU1 - Recibir notificación de compra
    Tipo: Asíncrono orientado a eventos (RabbitMQ)
    Exchange: entradas.events
    Evento / Routing Key: entradas_emitidas
    SLA: < 200 ms (recepción y encolamiento de solicitud)
    """

    @classmethod
    async def enviar_ticket_correo(
        cls, 
        correo_comprador: str, 
        nombre_comprador: str, 
        id_usuario: str,
        nombre_evento: str, 
        id_evento: str,
        fecha_evento: str, 
        hora_evento: str, 
        qr_data: str
    ) -> Dict[str, Any]:
        """
        Publica el evento 'entradas_emitidas' en el exchange 'entradas.events' de RabbitMQ
        conforme al Contrato v3 de Notificaciones.
        """
        payload = {
            "correo_comprador": correo_comprador,
            "nombre_comprador": nombre_comprador,
            "id_usuario": id_usuario,
            "nombre_evento": nombre_evento,
            "id_evento": id_evento,
            "fecha_evento": fecha_evento,
            "hora_evento": hora_evento,
            "qr_data": qr_data
        }
        
        # Simulación de publicación en RabbitMQ (Exchange: entradas.events, Evento: entradas_emitidas)
        mensaje = json.dumps(payload, ensure_ascii=False)
        print(f"[RabbitMQ - Exchange: entradas.events] Evento 'entradas_emitidas' publicado -> {mensaje}")
        
        # Simulación de confirmación asíncrona recibida a través del Exchange notificaciones.confirmacion_envio
        confirmacion = {
            "estado": "programado",
            "mensaje": "El envío del correo fue exitoso"
        }
        print(f"[RabbitMQ - Exchange: notificaciones.confirmacion_envio] Confirmación de encolamiento recibida -> {confirmacion}")
        
        return confirmacion

