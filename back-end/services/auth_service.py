import os
import httpx
from typing import Dict
from fastapi import HTTPException


class AuthService:
    BASE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:10000")
    INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
    TIMEOUT_SECONDS = float(os.getenv("AUTH_TIMEOUT_SECONDS", "1.5"))

    @staticmethod
    def extraer_jwt(token_o_cookie: str) -> str:
        """
        Extrae el valor del JWT desde una cabecera Cookie ('jwt=<token>; ...') o un token raw.
        """
        if not token_o_cookie:
            return ""
        valor = token_o_cookie.strip()
        if valor.lower().startswith("bearer "):
            valor = valor[7:].strip()
        if "jwt=" in valor:
            partes = valor.split("jwt=", 1)[1]
            valor = partes.split(";", 1)[0].strip()
        return valor

    @staticmethod
    def formatear_cookie_header(cookie_o_token: str) -> str:
        """
        Contrato Auth / Pagos v2.3:
        Auth y Pagos validan la sesión desde el header Cookie (cookie 'jwt').
        - Si ya viene el header Cookie del navegador (conteniendo 'jwt='), se reenvía tal cual.
        - Si viene el JWT suelto (por retrocompatibilidad interna), lo formatea como 'jwt=<token>'.
        """
        if not cookie_o_token:
            return ""
        valor = cookie_o_token.strip()
        if "jwt=" in valor:
            return valor
        if valor.lower().startswith("bearer "):
            valor = valor[7:].strip()
        return f"jwt={valor}" if valor else ""

    @classmethod
    async def validar_sesion(cls, cookie_header: str) -> Dict:
        """
        Contrato: Entradas/Inventario <-> Autenticación (Auth)
        Verifica la identidad del cliente mediante introspección centralizada (GET /internal/validar-sesion),
        reenviando el header Cookie con la cookie 'jwt' y la clave interna x-api-key.
        """
        base_url = os.getenv("AUTH_SERVICE_URL", cls.BASE_URL)
        api_key = os.getenv("INTERNAL_API_KEY", cls.INTERNAL_API_KEY)
        url = f"{base_url}/internal/validar-sesion"

        cookie_reenvio = cls.formatear_cookie_header(cookie_header)
        if not cookie_reenvio or not cls.extraer_jwt(cookie_reenvio):
            raise HTTPException(
                status_code=401,
                detail="NO_AUTENTICADO: Falta la cookie 'jwt' de sesión emitida por Auth.",
            )

        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="AUTH_NO_DISPONIBLE: Clave interna de autenticación no configurada.",
            )

        headers = {
            "Cookie": cookie_reenvio,
            "x-api-key": api_key,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=cls.TIMEOUT_SECONDS)

                if response.status_code == 200:
                    data = response.json()
                    if "valido" in data and not data.get("valido", False):
                        raise HTTPException(
                            status_code=401,
                            detail="NO_AUTENTICADO: Sesión inválida o revocada por Auth.",
                        )
                    usuario = data.get("usuario", data) if isinstance(data, dict) else {}
                    if usuario.get("activo") is False:
                        raise HTTPException(
                            status_code=403,
                            detail="CUENTA_INACTIVA: La cuenta del usuario se encuentra suspendida o inactiva.",
                        )
                    nombre = (
                        usuario.get("nombre")
                        or usuario.get("nombre_completo")
                        or usuario.get("nombre_usuario")
                        or "Usuario"
                    )
                    correo = (
                        usuario.get("correo")
                        or usuario.get("correo_electronico")
                        or usuario.get("email")
                        or ""
                    )
                    rut = usuario.get("rut") or usuario.get("RUT")
                    rol = (usuario.get("rol") or "usuario").upper()
                    id_usr = usuario.get("id_usuario") or usuario.get("id") or usuario.get("sub")
                    if not id_usr:
                        raise HTTPException(
                            status_code=503,
                            detail="AUTH_NO_DISPONIBLE: Respuesta de identidad incompleta desde Auth.",
                        )
                    return {
                        **usuario,
                        "id_usuario": str(id_usr),
                        "rol": rol,
                        "nombre": nombre,
                        "nombre_completo": nombre,
                        "rut": rut,
                        "correo": correo,
                        "correo_electronico": correo,
                        "cookie_header": cookie_reenvio,
                        "token_jwt": cls.extraer_jwt(cookie_reenvio),
                    }
                elif response.status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail="NO_AUTENTICADO: Cookie 'jwt' ausente, inválida, vencida o revocada por Auth.",
                    )
                elif response.status_code == 403:
                    raise HTTPException(
                        status_code=403,
                        detail="PROHIBIDO: No autorizado para consultar el servicio interno de Auth.",
                    )
                else:
                    raise HTTPException(
                        status_code=503,
                        detail="AUTH_NO_DISPONIBLE: Error temporal en el servicio de Auth.",
                    )

            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=503,
                    detail="AUTH_NO_DISPONIBLE: Servicio de Autenticación no disponible (Timeout).",
                )
            except httpx.RequestError as exc:
                print(f"[Auth] Error de red comunicando con Auth: {type(exc).__name__}")
                raise HTTPException(
                    status_code=503,
                    detail="AUTH_NO_DISPONIBLE: Servicio de Autenticación inaccesible.",
                )
