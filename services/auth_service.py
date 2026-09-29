import httpx
from typing import Optional, Dict

class AuthService:
    BASE_URL = "http://auth-service:8000"

    @classmethod
    async def validar_sesion(cls, token: str) -> Optional[Dict]:
        """
        Contrato: Entradas/Inventario <-> Autenticación (Auth)
        Verifica la identidad del cliente. Retorna los datos seguros del usuario.
        """
        url = f"{cls.BASE_URL}/api/v1/auth/me"
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
                return None
            except httpx.RequestError as exc:
                print(f"Error comunicando con Auth: {exc}")
                return None
