import httpx
from typing import Optional, Dict

class AuthService:
    BASE_URL = "http://auth-service:8000"

    @classmethod
    async def validar_sesion(cls, cookie_header: str) -> Optional[Dict]:
        """
        Contrato: Entradas/Inventario <-> Autenticación (Auth) v2.0
        Verifica la identidad del cliente mediante Cookie HttpOnly.
        """
        url = f"{cls.BASE_URL}/api/auth/me"
        headers = {"Cookie": cookie_header}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
                return None
            except httpx.RequestError as exc:
                print(f"Error comunicando con Auth: {exc}")
                return None
