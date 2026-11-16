import re
from datetime import datetime
from typing import Dict, Any
from services.broker_service import BrokerService

_MESES_ES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
}


def _normalizar_fecha(fecha: str) -> str:
    """Convierte fechas ISO o en español ('20 de Noviembre, 2026') a 'YYYY-MM-DD'."""
    if not fecha or not isinstance(fecha, str):
        return datetime.utcnow().strftime("%Y-%m-%d")
    limpia = fecha.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", limpia):
        return limpia[:10]
    match = re.search(r"(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+)[,\s]+(\d{4})", limpia, re.IGNORECASE)
    if match:
        dia, mes_txt, anio = match.groups()
        mes = _MESES_ES.get(mes_txt.lower())
        if mes:
            return f"{anio}-{mes}-{int(dia):02d}"
    return datetime.utcnow().strftime("%Y-%m-%d")


def _normalizar_hora(hora: str) -> str:
    """Extrae 'HH:MM' desde strings como '20:00 hrs' o '20:00:00'."""
    if not hora or not isinstance(hora, str):
        return "20:00"
    match = re.search(r"(\d{1,2}:\d{2})", hora)
    if match:
        hh, mm = match.group(1).split(":")
        return f"{int(hh):02d}:{mm}"
    return "20:00"


class NotificacionesService:
    """
    Contrato de interfaz: Entradas <-> Notificaciones (Versión 3)
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
            "correo_comprador": correo_comprador or "sin-correo@ticketu.cl",
            "nombre_comprador": nombre_comprador or "Cliente TicketU",
            "id_usuario": str(id_usuario),
            "nombre_evento": nombre_evento or f"Evento {id_evento}",
            "id_evento": str(id_evento),
            "fecha_evento": _normalizar_fecha(fecha_evento),
            "hora_evento": _normalizar_hora(hora_evento),
            "qr_data": str(qr_data),
        }

        publicado = await BrokerService.publish_notificaciones(payload)
        return {
            "estado": "en_cola" if publicado else "mock_offline",
            "mensaje": "Evento entradas_emitidas publicado en RabbitMQ" if publicado else "Broker no conectado",
        }

