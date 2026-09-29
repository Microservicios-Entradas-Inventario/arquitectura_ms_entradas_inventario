import httpx
from typing import Dict

class PromocionesService:
    BASE_URL = "http://promociones-service:8000"

    @classmethod
    async def validar_codigo(cls, nombre_codigo: str, id_evento: str, cantidad_entradas: int, id_usuario: str, rol_usuario: str, precio_base: int) -> Dict:
        """
        Contrato: Entradas <-> Promociones v1.0
        Consumidor: Entradas
        """
        url = f"{cls.BASE_URL}/promociones/validar/{nombre_codigo}"
        payload = {
            "id_evento": id_evento,
            "cantidad_entradas": cantidad_entradas,
            "usuario": {
                "id_usuario": id_usuario,
                "rol_usuario": rol_usuario
            },
            "precio_base": precio_base
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=0.3)
                if response.status_code == 200:
                    return response.json()
                return {"valido": False, "porcentaje_descuento": 0}
            except httpx.RequestError as exc:
                print(f"Error comunicando con Promociones: {exc}")
                return {"valido": False, "porcentaje_descuento": 0}
