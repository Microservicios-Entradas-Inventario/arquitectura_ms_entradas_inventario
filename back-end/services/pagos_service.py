import os
import asyncio
import httpx
from typing import Dict, Any, Optional
from services.auth_service import AuthService


class PagosService:
    """
    Contrato de interfaz: Pagos <-> Entradas/Inventario v2.2 (API v1)
    Equipo consumidor: Entradas/Inventario
    Equipo proveedor: Pagos
    Cambios clave en v2.2:
    1. Pagos valida la sesión con Auth (GET /internal/validar-sesion) en cada llamada.
    2. El token debe ser el JWT emitido por Auth al iniciar sesión (en Authorization: Bearer <jwt> o token_sesion).
    3. Los roles SERVICIO y ADMIN dejan de existir; consultar y anular usan el JWT del comprador o rol staff.
    4. Nuevo código 503 AUTH_NO_DISPONIBLE cuando Auth no responde (no se crea ni modifica ningún pago; reintentar).
    5. Manejo de errores por el campo 'error' del cuerpo ({ 'error': 'CODIGO', 'mensaje': '...', 'detalles': [...] }).
    6. Entradas ignora 'client_secret' y solo persiste 'id_pago' como referencia.
    """

    BASE_URL = os.getenv("PAGOS_SERVICE_URL", "http://pagos-service:8000")
    STAFF_TOKEN = os.getenv("PAGOS_STAFF_TOKEN", "")

    @classmethod
    def _preparar_token(cls, token_sesion: Optional[str] = None) -> str:
        """Obtiene el JWT limpio emitido por Auth o utiliza el token staff de respaldo si aplica."""
        jwt_limpio = AuthService.extraer_jwt(token_sesion or "")
        if not jwt_limpio and cls.STAFF_TOKEN:
            jwt_limpio = AuthService.extraer_jwt(cls.STAFF_TOKEN)
        return jwt_limpio

    @staticmethod
    def _parsear_error_pagos(response: httpx.Response) -> Dict[str, Any]:
        """
        Extrae la estructura estándar de error del contrato v2.2:
        { "error": "CODIGO", "mensaje": "...", "detalles": [...] }
        """
        try:
            body = response.json()
            if isinstance(body, dict):
                return {
                    "codigo_http": response.status_code,
                    "error": body.get("error", f"HTTP_{response.status_code}"),
                    "mensaje": body.get("mensaje") or body.get("detail") or "Error en el servicio de Pagos",
                    "detalles": body.get("detalles", [])
                }
        except Exception:
            pass
        return {
            "codigo_http": response.status_code,
            "error": f"HTTP_{response.status_code}",
            "mensaje": response.text or "Error inesperado en el servicio de Pagos",
            "detalles": []
        }

    @classmethod
    async def iniciar_cobro(
        cls,
        id_reserva: str,
        total: int,
        cantidad_entradas: int,
        token_sesion: str,
        id_evento: Optional[str] = None,
        metodo: Optional[str] = None,
        max_reintentos: int = 2
    ) -> Dict[str, Any]:
        """
        Operación 2: Crear intención de pago (Contrato Pagos <-> Entradas v2.2)
        Endpoint: POST /api/v1/pagos/transacciones
        SLA: < 2000 ms (incluye validación de sesión con Auth y creación en Stripe).
        Idempotencia: Reintentar con el mismo id_reserva y los mismos datos es seguro y devuelve 200 sin duplicar cobro.
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/transacciones"
        jwt_limpio = cls._preparar_token(token_sesion)

        headers = {}
        if jwt_limpio:
            headers["Authorization"] = f"Bearer {jwt_limpio}"

        payload: Dict[str, Any] = {
            "id_reserva": str(id_reserva)[:64],
            "total": int(total),
            "cantidad_entradas": int(cantidad_entradas),
            "token_sesion": jwt_limpio
        }
        if id_evento:
            payload["id_evento"] = str(id_evento)[:64]
        if metodo in ("formulario", "checkout"):
            payload["metodo"] = metodo

        async with httpx.AsyncClient() as client:
            for intento in range(1, max_reintentos + 1):
                try:
                    # SLA < 2000 ms según sección 2.8 del contrato v2.2
                    response = await client.post(url, headers=headers, json=payload, timeout=2.0)

                    if response.status_code in (200, 201):
                        data = response.json()
                        # Regla sección 2.6: client_secret es de uso interno del front de Pagos; Entradas debe ignorarlo y no almacenarlo
                        data.pop("client_secret", None)
                        return data

                    err_info = cls._parsear_error_pagos(response)
                    codigo_error = err_info["error"]
                    status = response.status_code

                    # 503 AUTH_NO_DISPONIBLE o ENTRADAS_NO_DISPONIBLE: no se creó ni modificó ningún pago, basta con reintentar
                    if status == 503 and intento < max_reintentos:
                        print(f"[Pagos v2.2] 503 {codigo_error} en intento {intento}/{max_reintentos} para reserva '{id_reserva}'. Reintentando...")
                        await asyncio.sleep(0.3 * intento)
                        continue

                    if status == 401:
                        print(f"[Pagos v2.2] 401 NO_AUTENTICADO ({codigo_error}): El token fue rechazado por Auth o no fue emitido por Auth.")
                    elif status == 503 and codigo_error == "AUTH_NO_DISPONIBLE":
                        print(f"[Pagos v2.2] 503 AUTH_NO_DISPONIBLE: Auth no respondió al validar la sesión. No se creó el pago.")
                    else:
                        print(f"[Pagos v2.2] Error {status} ({codigo_error}) al crear intención de pago: {err_info['mensaje']}")

                    return {
                        "id_pago": None,
                        "id_reserva": id_reserva,
                        "estado_pago": "ERROR",
                        "reintentable": status in (502, 503),
                        **err_info
                    }

                except (httpx.TimeoutException, httpx.RequestError) as exc:
                    print(f"[Pagos v2.2] Error de red/timeout en intento {intento}/{max_reintentos} comunicando con Pagos: {exc}")
                    if intento < max_reintentos:
                        # Reintento idempotente seguro con el mismo id_reserva (Sección 5)
                        await asyncio.sleep(0.3 * intento)
                        continue
                    return {
                        "id_pago": None,
                        "id_reserva": id_reserva,
                        "estado_pago": "ERROR",
                        "codigo_http": 503,
                        "error": "PAGOS_NO_DISPONIBLE",
                        "mensaje": f"No fue posible comunicarse con el servicio de Pagos: {exc}",
                        "detalles": [],
                        "reintentable": True
                    }

        return {"id_pago": None, "estado_pago": "ERROR"}

    @classmethod
    async def consultar_estado_pago(cls, id_pago: str, token_sesion: Optional[str] = None) -> Dict[str, Any]:
        """
        Operación 3: Consultar estado del pago (Contrato Pagos <-> Entradas v2.2)
        Endpoint: GET /api/v1/pagos/{id_pago}
        Headers: Authorization: Bearer <JWT de Auth del comprador dueño del pago, o de un usuario staff>
        SLA: < 300 ms cuando el estado es final; < 2000 ms si Pagos debe confirmar con Stripe un pago PENDIENTE.
        Estados posibles: PENDIENTE, APROBADO, RECHAZADO, ANULADO, REEMBOLSADO.
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/{id_pago}"
        jwt_limpio = cls._preparar_token(token_sesion)
        headers = {"Authorization": f"Bearer {jwt_limpio}"} if jwt_limpio else {}

        async with httpx.AsyncClient() as client:
            try:
                # SLA hasta 2000 ms cuando Pagos confirma estado PENDIENTE con Stripe (Sección 3.8)
                response = await client.get(url, headers=headers, timeout=2.0)
                if response.status_code == 200:
                    data = response.json()
                    data.pop("client_secret", None)
                    return data

                err_info = cls._parsear_error_pagos(response)
                codigo_error = err_info["error"]

                if response.status_code == 503 and codigo_error == "AUTH_NO_DISPONIBLE":
                    # Si Auth no responde temporalmente durante el polling, mantener como PENDIENTE/reintentable
                    print(f"[Pagos v2.2] 503 AUTH_NO_DISPONIBLE al consultar pago '{id_pago}'. Se reintentará en el siguiente ciclo.")
                    return {
                        "id_pago": id_pago,
                        "estado_pago": "PENDIENTE",
                        "reintentable": True,
                        **err_info
                    }

                print(f"[Pagos v2.2] Error {response.status_code} ({codigo_error}) consultando pago '{id_pago}': {err_info['mensaje']}")
                return {
                    "id_pago": id_pago,
                    "estado_pago": "DESCONOCIDO",
                    "reintentable": response.status_code in (502, 503),
                    **err_info
                }
            except httpx.RequestError as exc:
                print(f"[Pagos v2.2] Error de red consultando estado de pago '{id_pago}': {exc}")
                return {
                    "id_pago": id_pago,
                    "estado_pago": "DESCONOCIDO",
                    "error": "PAGOS_NO_DISPONIBLE",
                    "reintentable": True
                }

    @classmethod
    async def anular_pago(
        cls,
        id_pago: str,
        motivo: str,
        token_sesion: Optional[str] = None,
        token_servicio: Optional[str] = None,
        max_reintentos: int = 2
    ) -> Dict[str, Any]:
        """
        Operación 4: Anular o reembolsar un pago (Contrato Pagos <-> Entradas v2.2)
        Endpoint: POST /api/v1/pagos/{id_pago}/reembolso
        Headers: Authorization: Bearer <JWT de Auth del comprador dueño del pago, o de un usuario staff>
        Nota v2.2: Los roles SERVICIO y ADMIN dejaron de existir; se usa el JWT del comprador o de un usuario staff.
        SLA: < 2000 ms.
        """
        url = f"{cls.BASE_URL}/api/v1/pagos/{id_pago}/reembolso"
        jwt_limpio = cls._preparar_token(token_sesion or token_servicio)
        headers = {"Authorization": f"Bearer {jwt_limpio}"} if jwt_limpio else {}

        # Asegurar restricción del contrato (3 a 255 caracteres)
        motivo_limpio = (motivo or "Hold de la reserva vencido: el usuario pagó fuera de plazo").strip()
        if len(motivo_limpio) < 3:
            motivo_limpio = "Reserva vencida o cancelada"
        motivo_limpio = motivo_limpio[:255]

        payload = {"motivo": motivo_limpio}

        async with httpx.AsyncClient() as client:
            for intento in range(1, max_reintentos + 1):
                try:
                    response = await client.post(url, headers=headers, json=payload, timeout=2.0)
                    if response.status_code == 200:
                        data = response.json()
                        return {"ok": True, **data}

                    err_info = cls._parsear_error_pagos(response)
                    codigo_error = err_info["error"]
                    status = response.status_code

                    # Reintentar si Auth no estuvo disponible (503 AUTH_NO_DISPONIBLE) o si hubo cambio concurrente (409 CAMBIO_CONCURRENTE)
                    if (status == 503 or (status == 409 and codigo_error == "CAMBIO_CONCURRENTE")) and intento < max_reintentos:
                        print(f"[Pagos v2.2] {status} {codigo_error} al anular/reembolsar pago '{id_pago}'. Reintentando ({intento}/{max_reintentos})...")
                        await asyncio.sleep(0.3 * intento)
                        continue

                    # Si el pago estaba RECHAZADO (409 PAGO_NO_REEMBOLSABLE), no hubo cobro, por lo que no requiere reembolso
                    if status == 409 and codigo_error == "PAGO_NO_REEMBOLSABLE":
                        print(f"[Pagos v2.2] Pago '{id_pago}' ya estaba RECHAZADO (PAGO_NO_REEMBOLSABLE, sin cobro).")
                        return {"ok": True, "id_pago": id_pago, "estado_pago": "RECHAZADO", **err_info}

                    print(f"[Pagos v2.2] Error {status} ({codigo_error}) anulando/reembolsando pago '{id_pago}': {err_info['mensaje']}")
                    return {"ok": False, "id_pago": id_pago, "reintentable": status in (502, 503), **err_info}

                except httpx.RequestError as exc:
                    print(f"[Pagos v2.2] Error de red anulando pago '{id_pago}' (intento {intento}/{max_reintentos}): {exc}")
                    if intento < max_reintentos:
                        await asyncio.sleep(0.3 * intento)
                        continue
                    return {
                        "ok": False,
                        "id_pago": id_pago,
                        "error": "PAGOS_NO_DISPONIBLE",
                        "mensaje": str(exc),
                        "reintentable": True
                    }

        return {"ok": False, "id_pago": id_pago}
