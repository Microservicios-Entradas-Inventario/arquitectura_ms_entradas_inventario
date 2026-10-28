import httpx
from typing import Dict
from fastapi import HTTPException

class AuthService:
    BASE_URL = "http://auth-service:8000"

    @classmethod
    async def validar_sesion(cls, cookie_header: str) -> Dict:
        """
        Contrato: Entradas/Inventario <-> Autenticación (Auth) v3.0
        Verifica la identidad del cliente mediante Introspección Centralizada.
        """
        url = f"{cls.BASE_URL}/internal/validar-sesion"
        
        # Formatear como cabecera Cookie si viene como token raw (según contrato Auth v3.0)
        cookie_value = cookie_header if "jwt=" in cookie_header else f"jwt={cookie_header}"
        headers = {"Cookie": cookie_value}
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 200ms
                response = await client.get(url, headers=headers, timeout=0.2)
                
                if response.status_code == 200:
                    data = response.json()
                    if not data.get("valido", False):
                        raise HTTPException(status_code=401, detail="Sesión inválida o revocada.")
                    return data.get("usuario", {})
                elif response.status_code == 401:
                    raise HTTPException(status_code=401, detail="No autorizado: Cookie ausente o expirada.")
                elif response.status_code == 403:
                    raise HTTPException(status_code=403, detail="Prohibido: No autorizado a consultar la red interna.")
                else:
                    raise HTTPException(status_code=500, detail="Error interno en el servicio de Auth.")
                    
            except httpx.TimeoutException:
                raise HTTPException(status_code=503, detail="Servicio de Autenticación no disponible (Timeout).")
            except httpx.RequestError as exc:
                print(f"Error de red comunicando con Auth: {exc}")
                raise HTTPException(status_code=503, detail="Servicio de Autenticación inaccesible.")
