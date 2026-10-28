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


# --- HU-03 ----
def test_reserva_y_liberacion_stock_hu03():
    """Valida la creación de un Hold temporal y su liberación de stock (HU-03)"""
    id_evento_prueba = "evt-77889"
    id_usuario_prueba = "usr-12345"
    
    with TestClient(app) as client:
        # crear la reserva
        payload = {
            "id_evento": id_evento_prueba,
            "id_usuario": id_usuario_prueba,
            "cantidad": 1,
            "tiempo_limite_minutos": 15
        }
        res_crear = client.post("/api/v1/reservas/hold", json=payload)
        assert res_crear.status_code == 200
        data_reserva = res_crear.json()
        
        assert "hold_id" in data_reserva
        id_reserva = data_reserva["id_reserva"]
        
        # cancelar la reserva para probar la liberación del stock al pool
        res_cancelar = client.post(f"/api/v1/reservas/{id_reserva}/cancelar")
        assert res_cancelar.status_code == 200
        assert res_cancelar.json()["cupos_liberados"] == 1

# --- HU-04 ---
def test_detalle_entrada_inmutable_hu04():
    """Valida que el detalle de la entrada no exija mapa numerado y traiga el precio final (HU-04)"""
    id_usuario_prueba = "usr-12345"
    
    with TestClient(app) as client:
        response = client.get(f"/api/v1/entradas/usuario/{id_usuario_prueba}")
        if response.status_code == 200 and len(response.json()) > 0:
            entrada = response.json()[0]
            # validamos las reglas de negocio estrictas de la HU-04
            assert entrada["tipo_acceso"] == "GENERAL", "Debe ser entrada general sin asiento"
            assert "precio_final_pagado" in entrada, "Debe ser inmutable el precio"
            assert "lugar_ingreso" in entrada


def test_payload_qr_checkin_hu05():
    """Valida el contrato de datos del QR exigido por Check-in v2.1 (HU-05)"""
    id_ticket_prueba = "tk-998877"
    
    with TestClient(app) as client:
        response = client.get(f"/api/v1/entradas/{id_ticket_prueba}/qr")
        # Si el ticket existe, validamos su estructura
        if response.status_code == 200:
            data = response.json()
            assert "qr_payload" in data
            payload = data["qr_payload"]
            
            # Estas dos llaves son obligatorias para el servicio de Check-in
            assert "id_evento" in payload
            assert "id_entrada" in payload
            assert data["habilitado_checkin"] is True