import asyncio
import json
import os
from urllib.parse import quote
import httpx
from typing import Any, Optional, Union


class CheckinService:
    BASE_URL = os.getenv("CHECKIN_SERVICE_URL", "http://ticketu-api-gateway:8080")
    TIMEOUT_SECONDS = float(os.getenv("CHECKIN_TIMEOUT_SECONDS", "2.5"))

    @staticmethod
    def generar_qr_url(id_entrada: str, id_evento: str) -> str:
        """Genera la URL del QR con JSON {id_entrada, id_evento} para el lector de Check-in."""
        payload = json.dumps(
            {"id_entrada": str(id_entrada).strip(), "id_evento": str(id_evento).strip()},
            separators=(",", ":"),
        )
        return f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={quote(payload, safe='')}"

    @classmethod
    async def registrar_ticket_puerta(
        cls,
        id_entrada: str,
        id_evento: str,
        id_usuario: str,
        nombre_usuario: str,
        qr_data: Optional[Union[str, Any]] = None,
        max_reintentos: int = 2,
    ) -> bool:
        """
        Contrato HTTP de Check-in (v2 / Integración)
        Consumidor: Entradas / Inventario
        Proveedor: Check-in
        Operación: Recibir y guardar un ticket desde Entradas
        Endpoint: POST /api/checkin/tickets
        """
        base_url = os.getenv("CHECKIN_SERVICE_URL", cls.BASE_URL)
        url = f"{base_url}/api/checkin/tickets"

        id_entrada_str = str(id_entrada or "").strip()
        id_evento_str = str(id_evento or "").strip()
        id_usuario_str = str(id_usuario or "").strip()
        nombre_usuario_str = str(nombre_usuario or "Asistente").strip()

        if not id_entrada_str or not id_evento_str or not id_usuario_str:
            print(
                f"[Check-in] Datos incompletos para registrar ticket: id_entrada='{id_entrada_str}', id_evento='{id_evento_str}', id_usuario='{id_usuario_str}'"
            )
            return False

        payload = {
            "id_entrada": id_entrada_str,
            "id_evento": id_evento_str,
            "id_usuario": id_usuario_str,
            "nombre_usuario": nombre_usuario_str,
            "qr_data": {"id_entrada": id_entrada_str, "id_evento": id_evento_str},
        }

        async with httpx.AsyncClient() as client:
            for intento in range(1, max_reintentos + 1):
                try:
                    response = await client.post(url, json=payload, timeout=cls.TIMEOUT_SECONDS)
                    if response.status_code in (200, 201):
                        return True
                    if response.status_code == 409:
                        print(f"[Check-in] 409 Conflict (idempotente): El ticket {id_entrada_str} ya existe en Check-in.")
                        return True
                    if response.status_code == 400:
                        print(
                            f"[Check-in] 400 Bad Request para ticket {id_entrada_str}: {response.text}"
                        )
                        return False
                    print(
                        f"[Check-in] HTTP {response.status_code} para ticket {id_entrada_str} (intento {intento}/{max_reintentos}): {response.text}"
                    )
                    if response.status_code >= 500 and intento < max_reintentos:
                        await asyncio.sleep(0.25 * intento)
                        continue
                    return False
                except httpx.RequestError as exc:
                    print(
                        f"[Check-in] Error comunicando con Check-in ({url}) en intento {intento}/{max_reintentos}: {exc}"
                    )
                    if intento < max_reintentos:
                        await asyncio.sleep(0.25 * intento)
                        continue
                    return False

        return False
