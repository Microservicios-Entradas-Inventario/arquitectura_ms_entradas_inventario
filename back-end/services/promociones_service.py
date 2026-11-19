import os
from typing import Optional
import httpx
from services.pagos_service import PagosService


class PromocionesService:
    """Cliente HTTP para revalidar descuentos con el microservicio de Promociones vía API Gateway."""

    BASE_URL = os.getenv("PROMOCIONES_SERVICE_URL", "http://ticketu-api-gateway:8080")

    @classmethod
    async def revalidar_descuento(
        cls,
        id_evento: str,
        id_usuario: str,
        cantidad_entradas: int,
        precio_base: int,
        nombre_codigo: Optional[str] = None,
        id_promocion: Optional[str] = None,
        porcentaje_descuento: float = 0.0,
    ) -> tuple[Optional[str], Optional[str], int, int]:
        """
        Revalida el descuento contra `POST /api/promociones/evaluar` cuando hay código promocional.
        Nunca confía en el porcentaje enviado desde el frontend: si no hay código válido o si
        Promociones no responde/rechaza, no aplica descuento (0% sobre precio_base).
        """
        monto_sin_descuento = max(0, int(precio_base))
        codigo_promo, _, _ = PagosService.normalizar_promocion(precio_base, nombre_codigo, 0)
        if not codigo_promo:
            return None, None, 0, monto_sin_descuento

        url = f"{cls.BASE_URL}/api/promociones/evaluar"
        payload = {
            "id_evento": str(id_evento),
            "id_usuario": str(id_usuario),
            "cantidad_entradas": int(cantidad_entradas),
            "codigo_promocion": codigo_promo,
            "nombre_codigo": codigo_promo,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=3.0)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        _, pct_real, monto_real = PagosService.normalizar_promocion(
                            precio_base, codigo_promo, data.get("porcentaje_descuento", 0)
                        )
                        if pct_real > 0:
                            id_promo_real = data.get("id_promocion") or id_promocion
                            return codigo_promo, id_promo_real, pct_real, monto_real
                        return None, None, 0, monto_sin_descuento
                else:
                    print(f"[Promociones] Respuesta HTTP {response.status_code} al evaluar '{codigo_promo}'; no se aplica descuento.")
            except httpx.RequestError as exc:
                print(f"[Promociones] No disponible ({url}): {exc}; no se aplica descuento sin validación.")

        return None, None, 0, monto_sin_descuento
