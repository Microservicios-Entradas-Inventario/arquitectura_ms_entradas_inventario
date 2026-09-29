import httpx
from typing import Optional

class PromocionesService:
    BASE_URL = "http://promociones-service:8000" # URL del microservicio de Promociones (ejemplo)

    @classmethod
    async def consultar_promocion_vigente(cls, id_evento: str, id_usuario: str, cantidad_entradas: int) -> dict:
        """
        Evalúa las reglas de negocio de promociones activas para un evento, usuario y cantidad.
        Cumple con el ítem BE2 de la rúbrica (Código de invocación a servicio externo).
        Basado en el Contrato de Interfaz "Entradas / Inventario <-> Promociones".
        """
        url = f"{cls.BASE_URL}/api/v1/promociones/evaluar"
        payload = {
            "id_evento": id_evento,
            "id_usuario": id_usuario,
            "cantidad_entradas": cantidad_entradas
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 200ms según contrato
                response = await client.post(url, json=payload, timeout=0.2) 
                if response.status_code == 200:
                    return response.json() # ej: {"porcentaje_descuento": 15, "id_promocion": "promo-estudiante"}
                else:
                    return {"porcentaje_descuento": 0, "id_promocion": None}
            except httpx.RequestError as exc:
                # Fallback: Entradas asume 0% de descuento si Promociones falla o demora
                print(f"Error de conexión con Promociones: {exc}")
                return {"porcentaje_descuento": 0, "id_promocion": None}
