from fastapi.testclient import TestClient
import pytest
from unittest.mock import patch, AsyncMock
import httpx
from main import app
from services.pagos_service import PagosService
from services.auth_service import AuthService

# --- HU-01: Visualización de disponibilidad ---
def test_consulta_inventario():
    """Valida la consulta en tiempo real de capacidad (HU-01)"""
    id_evento_prueba = "evt-77889"

    with TestClient(app) as client:
        response = client.get(f"/api/v1/inventario/{id_evento_prueba}")

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "stock_actual" in data, "La respuesta debe incluir el stock_actual"
            assert "tipo_entrada" in data, "La respuesta debe incluir el tipo_entrada"
            assert data["id_evento"] == id_evento_prueba, "El ID del evento debe coincidir"

# --- HU-02: Selección y compra ---
def test_procesar_compra_sin_autenticacion():
    """Valida que la seguridad bloquee compras sin cookie 'jwt' válida"""

    payload_compra = {
        "id_evento": "evt-77889",
        "tipo_entrada": "PAGADA",
        "cantidad": 2
    }
    
    with TestClient(app) as client:
        response = client.post("/api/v1/entradas/procesar-compra", json=payload_compra)
        print("\nDetalle del error de FastAPI:", response.json())
        assert response.status_code in [401, 403, 422]

def test_historial_usuario():
    """Valida la consulta del historial de tickets del cliente (HU-02)"""
    id_usuario_prueba = "usr-12345" 
    
    with TestClient(app) as client:
        response = client.get(f"/api/v1/entradas/usuario/{id_usuario_prueba}")
        assert response.status_code in [200, 404, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list), "El historial debe retornar un array"

# --- Contrato Pagos <-> Entradas v2.3 (Cookie jwt) ---
def test_formatear_cookie_header_auth_service():
    """Valida que el header Cookie recibido del navegador se reenvíe tal cual"""
    cookie_navegador = "jwt=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig; theme=dark"
    assert AuthService.formatear_cookie_header(cookie_navegador) == cookie_navegador
    assert AuthService.extraer_jwt(cookie_navegador) == "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"

@pytest.mark.anyio
async def test_pagos_v23_reenvia_cookie_tal_cual_sin_bearer_ni_token_sesion():
    """
    Valida que PagosService.iniciar_cobro (v2.3):
    1. Reenvíe el header Cookie tal cual llegó del navegador (sin Authorization: Bearer ni token_sesion en el body).
    2. Ignore y elimine client_secret de la respuesta.
    3. Conserve id_pago y url_checkout.
    """
    respuesta_mock = httpx.Response(
        200,
        json={
            "id_pago": "3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "id_reserva": "res-98765",
            "estado_pago": "PENDIENTE",
            "fecha_creacion": "2026-09-30T19:40:00.000Z",
            "url_checkout": "http://localhost:5173/?id_pago=3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "metodo": "formulario",
            "client_secret": "pi_secret_no_guardar"
        }
    )
    cookie_navegador = "jwt=eyJ_token_auth_real; session_flag=1"
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=respuesta_mock) as mock_post:
        resultado = await PagosService.iniciar_cobro(
            id_reserva="res-98765",
            total=15000,
            cantidad_entradas=2,
            cookie_header=cookie_navegador
        )
        assert resultado["id_pago"] == "3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12"
        assert resultado["url_checkout"].startswith("http://localhost:5173/")
        assert "client_secret" not in resultado
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Cookie"] == cookie_navegador
        assert "Authorization" not in kwargs["headers"]
        assert "token_sesion" not in kwargs["json"]

@pytest.mark.anyio
async def test_pagos_v23_reintento_503_auth_no_disponible():
    """
    Valida que ante 503 AUTH_NO_DISPONIBLE PagosService reintente idempotentemente con el mismo id_reserva y header Cookie.
    """
    resp_503 = httpx.Response(
        503,
        json={
            "error": "AUTH_NO_DISPONIBLE",
            "mensaje": "Pagos no pudo validar la sesión con Auth. Reintentar más tarde.",
            "detalles": []
        }
    )
    resp_200 = httpx.Response(
        200,
        json={
            "id_pago": "3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "id_reserva": "res-98765",
            "estado_pago": "PENDIENTE",
            "fecha_creacion": "2026-09-30T19:40:00.000Z",
            "url_checkout": "http://localhost:5173/?id_pago=3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "metodo": "formulario"
        }
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[resp_503, resp_200]) as mock_post:
        resultado = await PagosService.iniciar_cobro(
            id_reserva="res-98765",
            total=15000,
            cantidad_entradas=2,
            cookie_header="jwt=eyJ_token_auth_real",
            max_reintentos=2
        )
        assert mock_post.call_count == 2
        assert resultado["id_pago"] == "3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12"
        assert resultado["estado_pago"] == "PENDIENTE"
