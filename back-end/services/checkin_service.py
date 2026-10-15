import httpx
from typing import Any, Dict, Union

class CheckinService:
    BASE_URL = "http://checkin-service:8000"

    @classmethod
    async def registrar_ticket_puerta(
        cls, 
        id_entrada: str, 
        id_evento: str, 
        nombre_usuario: str, 
        qr_data: Union[Dict[str, Any], None] = None
    ) -> bool:
        """
        Contrato de interfaz: Entradas / Inventario <-> Check-in v2.1
        Consumidor: Entradas / Inventario
        Proveedor: Check-in
        Operación: Enviar QR de Acceso (enviar_qr_generado)
        Endpoint: POST /api/v1/checkin/tickets
        SLA: < 300 ms

        Envío en paralelo del ticket consolidado para registro y validación rápida en puerta.
        Reglas de Negocio v2.1:
        1. Se envía una vez validada la compra y descontado el stock.
        2. Estructura del QR: qr_data es un objeto JSON estructurado que debe contener 
           estrictamente las llaves 'id_evento' e 'id_entrada'.
        3. Persistencia de nombre_usuario: Entradas/Inventario guarda y provee este dato directamente.
        """
        url = f"{cls.BASE_URL}/api/v1/checkin/tickets"
        
        # Validar y estructurar el objeto JSON qr_data conforme a la regla de negocio del contrato v2.1
        if isinstance(qr_data, dict) and "id_evento" in qr_data and "id_entrada" in qr_data:
            qr_object = qr_data
        else:
            qr_object = {
                "id_evento": id_evento,
                "id_entrada": id_entrada
            }
            
        payload = {
            "id_entrada": id_entrada,
            "id_evento": id_evento,
            "nombre_usuario": nombre_usuario,
            "qr_data": qr_object
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA esperado < 300 ms (inserción directa en BD de Check-in)
                response = await client.post(url, json=payload, timeout=0.3)
                if response.status_code in (200, 201):
                    return True
                elif response.status_code == 400:
                    print(f"[Check-in v2.1] 400 Bad Request: Datos incompletos o malformados para ticket {id_entrada}")
                elif response.status_code == 409:
                    print(f"[Check-in v2.1] 409 Conflict: El ticket {id_entrada} ya se encuentra registrado en Check-in")
                elif response.status_code == 500:
                    print(f"[Check-in v2.1] 500 Internal Error: Error interno en base de datos de Check-in")
                else:
                    print(f"[Check-in v2.1] Respuesta inesperada HTTP {response.status_code} para ticket {id_entrada}")
                return False
            except httpx.RequestError as exc:
                print(f"[Check-in v2.1] Error comunicando con Check-in ({url}): {exc}")
                return False

