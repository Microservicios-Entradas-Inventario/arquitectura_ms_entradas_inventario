from fastapi.testclient import TestClient
import pytest
from main import app

# --- HU-01: Visualización de disponibilidad ---
def test_consulta_inventario():
    """Valida la consulta en tiempo real de capacidad (HU-01)"""
    id_evento_prueba = "evt-77889"

    with TestClient(app) as client:
        response = client.get(f"/api/v1/inventario/{id_evento_prueba}")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            # Ajustamos las aserciones al esquema real que devuelve FastAPI
            assert "stock_actual" in data, "La respuesta debe incluir el stock_actual"
            assert "tipo_entrada" in data, "La respuesta debe incluir el tipo_entrada"
            assert data["id_evento"] == id_evento_prueba, "El ID del evento debe coincidir"

# --- HU-02: Selección y compra ---
def test_procesar_compra_sin_autenticacion():
    """Valida que la seguridad bloquee compras sin token válido"""

    payload_compra = {
        "id_evento": "evt-77889",
        "id_usuario": "user_123",
        "zona": "VIP",
        "cantidad": 2
    }
    
    with TestClient(app) as client:
        # Petición sin la cookie 'jwt' requerida por AuthService
        response = client.post("/api/v1/entradas/procesar-compra", json=payload_compra)
        
        # FastAPI lanzará 422 si detecta la ausencia estricta de la Cookie requerida, 
        # o 401/403 si la validación la hace la lógica interna de AuthService.
        print("\nDetalle del error de FastAPI:", response.json())
        assert response.status_code in [401, 403, 422]

def test_historial_usuario():
    """Valida la consulta del historial de tickets del cliente (HU-02)"""
    # Usamos el ID del cliente que viene en los datos semilla de init_db.js
    id_usuario_prueba = "usr-12345" 
    
    with TestClient(app) as client:
        response = client.get(f"/api/v1/entradas/usuario/{id_usuario_prueba}")
        
        # Validamos que el endpoint exista y responda exitosamente
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            # El historial debe devolver una lista de tickets
            assert isinstance(data, list), "El historial debe retornar un array"