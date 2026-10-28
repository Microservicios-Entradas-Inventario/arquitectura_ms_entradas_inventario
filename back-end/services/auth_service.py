import os
import httpx
from typing import Dict
from fastapi import HTTPException

class AuthService:
    BASE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

    @staticmethod
    def extraer_jwt(token_o_cookie: str) -> str:
        """
        Extrae el JWT limpio emitido por Auth, ya sea que venga como:
        - 'Bearer <jwt>'
        - 'jwt=<jwt>' (o cookie header con múltiples pares)
        - '<jwt>' directo
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

    @classmethod
    async def validar_sesion(cls, cookie_header: str) -> Dict:
        """
        Contrato: Entradas/Inventario <-> Autenticación (Auth) v3.0 / Pagos v2.2
        Verifica la identidad del cliente mediante Introspección Centralizada (GET /internal/validar-sesion).
        Además recupera los datos del usuario (id_usuario, rol, nombre, RUT y correo) directamente desde Auth.
        """
        url = f"{cls.BASE_URL}/internal/validar-sesion"
        jwt_limpio = cls.extraer_jwt(cookie_header)
        if not jwt_limpio:
            raise HTTPException(status_code=401, detail="Falta el token de sesión emitido por Auth.")

        # Enviar tanto Cookie como Authorization Bearer para compatibilidad total con Auth
        headers = {
            "Cookie": f"jwt={jwt_limpio}",
            "Authorization": f"Bearer {jwt_limpio}"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 200ms (hasta 1000ms de corte máximo en red interna)
                response = await client.get(url, headers=headers, timeout=1.0)
                
                if response.status_code == 200:
                    data = response.json()
                    if "valido" in data and not data.get("valido", False):
                        raise HTTPException(status_code=401, detail="Sesión inválida o revocada por Auth.")
                    usuario = data.get("usuario", data) if isinstance(data, dict) else {}
                    # Normalizar campos entregados por Auth (nombre, RUT y correo)
                    nombre = (
                        usuario.get("nombre")
                        or usuario.get("nombre_completo")
                        or usuario.get("nombre_usuario")
                        or "Usuario Desconocido"
                    )
                    correo = (
                        usuario.get("correo")
                        or usuario.get("correo_electronico")
                        or usuario.get("email")
                        or "correo@ejemplo.com"
                    )
                    rut = usuario.get("rut") or usuario.get("RUT")
                    rol = (usuario.get("rol") or "usuario").upper()
                    id_usr = usuario.get("id_usuario") or usuario.get("id") or usuario.get("sub")
                    return {
                        **usuario,
                        "id_usuario": id_usr,
                        "rol": rol,
                        "nombre": nombre,
                        "nombre_completo": nombre,
                        "rut": rut,
                        "correo": correo,
                        "correo_electronico": correo,
                        "token_jwt": jwt_limpio
                    }
                elif response.status_code == 401:
                    raise HTTPException(status_code=401, detail="NO_AUTENTICADO: Token inválido, vencido, revocado o no emitido por Auth.")
                elif response.status_code == 403:
                    raise HTTPException(status_code=403, detail="Prohibido: No autorizado a consultar la red interna.")
                else:
                    raise HTTPException(status_code=503, detail="AUTH_NO_DISPONIBLE: Error en el servicio de Auth.")
                    
            except httpx.TimeoutException:
                raise HTTPException(status_code=503, detail="AUTH_NO_DISPONIBLE: Servicio de Autenticación no disponible (Timeout).")
            except httpx.RequestError as exc:
                print(f"Error de red comunicando con Auth: {exc}")
                raise HTTPException(status_code=503, detail="AUTH_NO_DISPONIBLE: Servicio de Autenticación inaccesible.")
