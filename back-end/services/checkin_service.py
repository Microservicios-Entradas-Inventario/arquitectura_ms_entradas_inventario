import os
import httpx
from typing import Any, Optional, Union

class CheckinService:
    BASE_URL = os.getenv("CHECKIN_SERVICE_URL", "http://checkin-service:3001")

    @classmethod
    async def registrar_ticket_puerta(
        cls, 
        id_entrada: str, 
        id_evento: str, 
        id_usuario: str,
        nombre_usuario: str, 
        qr_data: Optional[Union[str, Any]] = None
    ) -> bool:
        """
        Contrato HTTP de Check-in (v0.2.0 / Integración)
        Consumidor: Entradas / Inventario
        Proveedor: Check-in
        Operación: Recibir y guardar un ticket desde Entradas
        Endpoint: POST /api/checkin/tickets
        Campos requeridos (strings sin espacios extremos): id_entrada, id_evento, id_usuario, nombre_usuario y qr_data (= id_entrada).
        """
        url = f"{cls.BASE_URL}/api/checkin/tickets"
        
        id_entrada_str = str(id_entrada or "").strip()
        id_evento_str = str(id_evento or "").strip()
        id_usuario_str = str(id_usuario or "usr-desconocido").strip()
        nombre_usuario_str = str(nombre_usuario or "Asistente").strip()
        # Check-in exige que qr_data sea string y coincida exactamente con id_entrada
        qr_string = str(qr_data).strip() if isinstance(qr_data, str) and str(qr_data).strip() == id_entrada_str else id_entrada_str
            
        payload = {
            "id_entrada": id_entrada_str,
            "id_evento": id_evento_str,
            "id_usuario": id_usuario_str,
            "nombre_usuario": nombre_usuario_str,
            "qr_data": qr_string
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=0.5)
                if response.status_code in (200, 201):
                    return True
                elif response.status_code == 400:
                    print(f"[Check-in] 400 Bad Request: Datos incompletos o malformados para ticket {id_entrada_str}: {response.text}")
                elif response.status_code == 409:
                    print(f"[Check-in] 409 Conflict: El ticket {id_entrada_str} ya se encuentra registrado en Check-in")
                elif response.status_code == 500:
                    print(f"[Check-in] 500 Internal Error: Error interno en base de datos de Check-in")
                else:
                    print(f"[Check-in] Respuesta inesperada HTTP {response.status_code} para ticket {id_entrada_str}: {response.text}")
                return False
            except httpx.RequestError as exc:
                print(f"[Check-in] Error comunicando con Check-in ({url}): {exc}")
                return False
