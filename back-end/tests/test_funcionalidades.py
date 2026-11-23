from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
import copy
import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from services.auth_service import AuthService
from services.broker_service import BrokerService
from services.pagos_service import PagosService
from routers.reservas import _RESERVA_COOKIES


# ============================================================================
# BD en memoria determinista para pruebas funcionales unitarias/de API (CA1)
# Valida lógica real de routers, esquemas, reglas de negocio y seguridad sin
# depender de servicios externos encendidos.
# ============================================================================
class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key) or datetime.min, reverse=(direction == -1))
        return self

    async def to_list(self, length=100):
        return copy.deepcopy(self._docs[:length])


class _FakeResult:
    def __init__(self, modified_count=0, upserted_id=None):
        self.modified_count = modified_count
        self.upserted_id = upserted_id


def _match(doc, query):
    for k, v in query.items():
        if k == "$or":
            if not any(_match(doc, sub) for sub in v):
                return False
            continue
        val = doc.get(k)
        if isinstance(v, dict):
            for op, target in v.items():
                if op == "$gte" and not (val is not None and val >= target):
                    return False
                if op == "$gt" and not (val is not None and val > target):
                    return False
                if op == "$lt" and not (val is not None and val < target):
                    return False
                if op == "$ne" and not (val != target):
                    return False
        else:
            if val != v:
                return False
    return True


def _apply_update(doc, update):
    if "$set" in update:
        for k, v in update["$set"].items():
            doc[k] = copy.deepcopy(v)
    if "$inc" in update:
        for k, v in update["$inc"].items():
            doc[k] = doc.get(k, 0) + v


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(d) for d in (docs or [])]

    async def find_one(self, query):
        for d in self.docs:
            if _match(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query):
        return _FakeCursor([d for d in self.docs if _match(d, query)])

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))
        return _FakeResult(modified_count=1)

    async def update_one(self, query, update, upsert=False):
        for d in self.docs:
            if _match(d, query):
                _apply_update(d, update)
                return _FakeResult(modified_count=1)
        if upsert:
            nuevo = {}
            if "$setOnInsert" in update:
                nuevo.update(copy.deepcopy(update["$setOnInsert"]))
            if "$set" in update:
                nuevo.update(copy.deepcopy(update["$set"]))
            self.docs.append(nuevo)
            return _FakeResult(modified_count=1, upserted_id="fake-id")
        return _FakeResult(modified_count=0)

    async def find_one_and_update(self, query, update, return_document=None):
        for d in self.docs:
            if _match(d, query):
                _apply_update(d, update)
                return copy.deepcopy(d)
        return None

    async def delete_one(self, query):
        for idx, d in enumerate(self.docs):
            if _match(d, query):
                self.docs.pop(idx)
                return _FakeResult(modified_count=1)
        return _FakeResult(modified_count=0)


class _FakeDB:
    def __init__(self):
        ahora = datetime.utcnow()
        self.inventario_evento = _FakeCollection(
            [
                {
                    "id_evento": "evt-77889",
                    "nombre_evento": "Concierto Sinfonico TicketU",
                    "descripcion": "Evento de prueba pagado",
                    "fecha_evento": "2026-11-20",
                    "hora_evento": "20:00",
                    "lugar_ingreso": "Teatro Municipal",
                    "id_usuario": "usr-org-001",
                    "rol_usuario": "organizador",
                    "tipo_entrada": "PAGADA",
                    "precio_unitario": 10000,
                    "stock_inicial": 100,
                    "stock_actual": 10,
                    "cantidad_entrada_reservada": 0,
                    "cantidad_entrada_comprada": 90,
                    "maximo_ticket": 4,
                    "estado_gestion": "PUBLICADO",
                    "fecha_actualizacion": ahora,
                },
                {
                    "id_evento": "evt-gratis-01",
                    "nombre_evento": "Charla Abierta UV",
                    "descripcion": "Evento gratuito de prueba",
                    "fecha_evento": "2026-12-10",
                    "hora_evento": "15:00",
                    "lugar_ingreso": "Auditorio UV",
                    "id_usuario": "usr-org-001",
                    "rol_usuario": "organizador",
                    "tipo_entrada": "GRATUITA",
                    "precio_unitario": 0,
                    "stock_inicial": 50,
                    "stock_actual": 5,
                    "cantidad_entrada_reservada": 0,
                    "cantidad_entrada_comprada": 45,
                    "maximo_ticket": 2,
                    "estado_gestion": "PUBLICADO",
                    "fecha_actualizacion": ahora,
                },
                {
                    "id_evento": "evt-cancelado",
                    "nombre_evento": "Evento Cancelado",
                    "descripcion": "No disponible",
                    "fecha_evento": "2026-12-12",
                    "hora_evento": "19:00",
                    "lugar_ingreso": "Sala 1",
                    "id_usuario": "usr-org-001",
                    "rol_usuario": "organizador",
                    "tipo_entrada": "PAGADA",
                    "precio_unitario": 5000,
                    "stock_inicial": 20,
                    "stock_actual": 20,
                    "cantidad_entrada_reservada": 0,
                    "cantidad_entrada_comprada": 0,
                    "maximo_ticket": 4,
                    "estado_gestion": "CANCELADO",
                    "fecha_actualizacion": ahora,
                },
            ]
        )
        self.reserva_entrada = _FakeCollection(
            [
                {
                    "id_reserva": "res-98765",
                    "id_evento": "evt-77889",
                    "id_usuario": "usr-12345",
                    "nombre_usuario": "Comprador Prueba",
                    "rut_usuario": "12.345.678-5",
                    "correo_usuario": "comprador@ticketu.test",
                    "rol_usuario": "usuario",
                    "cantidad_entrada": 1,
                    "id_promocion": "promo-01",
                    "nombre_codigo": "DESC15",
                    "porcentaje_descuento": 15,
                    "monto_total": 8500,
                    "id_pago": "pay-112233",
                    "estado_reserva": "CONSOLIDADO",
                    "fecha_creacion": ahora,
                    "fecha_expiracion": None,
                },
            ]
        )
        self.entrada = _FakeCollection(
            [
                {
                    "id_entrada": "tk-998877",
                    "id_reserva": "res-98765",
                    "id_evento": "evt-77889",
                    "nombre_evento": "Concierto Sinfonico TicketU",
                    "lugar_ingreso": "Teatro Municipal",
                    "id_usuario": "usr-12345",
                    "nombre_usuario": "Comprador Prueba",
                    "rut_usuario": "12.345.678-5",
                    "correo_usuario": "comprador@ticketu.test",
                    "rol_usuario": "usuario",
                    "tipo_acceso": "GENERAL",
                    "precio_final_pagado": 8500,
                    "estado_entrada": "EMITIDA",
                    "nombre_archivo_qr": "tk-998877.png",
                    "qr_data": {
                        "url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=%7B%22id_entrada%22%3A%22tk-998877%22%2C%22id_evento%22%3A%22evt-77889%22%7D",
                        "hash": "abc1234",
                    },
                    "fecha_emision": ahora,
                },
            ]
        )


USUARIO_MOCK = {
    "id_usuario": "usr-12345",
    "rol": "USUARIO",
    "nombre": "Comprador Prueba",
    "nombre_completo": "Comprador Prueba",
    "rut": "12.345.678-5",
    "correo": "comprador@ticketu.test",
    "correo_electronico": "comprador@ticketu.test",
    "cookie_header": "jwt=token.valido.test",
    "token_jwt": "token.valido.test",
}


@pytest.fixture
def fake_db():
    _RESERVA_COOKIES.clear()
    return _FakeDB()


@pytest.fixture
def client(fake_db):
    with (
        patch("main.connect_to_mongo", new_callable=AsyncMock),
        patch("main.close_mongo_connection", new_callable=AsyncMock),
        patch("main.BrokerService.connect", new_callable=AsyncMock),
        patch("main.BrokerService.close", new_callable=AsyncMock),
        patch("main.PanelService.sincronizar_eventos_panel", new_callable=AsyncMock, return_value=0),
        patch("routers.inventario.get_database", return_value=fake_db),
        patch("routers.entradas.get_database", return_value=fake_db),
        patch("routers.reservas.get_database", return_value=fake_db),
        patch("services.broker_service.get_database", return_value=fake_db),
    ):
        with TestClient(app) as test_client:
            yield test_client


# ============================================================================
# HU-01: Consulta de disponibilidad y stock
# ============================================================================
def test_hu01_consulta_inventario_exitosa(client):
    resp = client.get("/api/entradas/inventario/evt-77889")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id_evento"] == "evt-77889"
    assert data["stock_actual"] == 10
    assert data["tipo_entrada"] == "PAGADA"
    assert data["precio_unitario"] == 10000


def test_hu01_consulta_inventario_evento_inexistente(client):
    resp = client.get("/api/entradas/inventario/evt-inexistente")
    assert resp.status_code == 404


def test_hu01_consulta_disponibilidad_y_stock_panel(client):
    r_disp = client.get("/api/entradas/eventos/evt-77889/disponibilidad")
    assert r_disp.status_code == 200
    assert r_disp.json()["stockDisponible"] == 10
    assert r_disp.json()["estadoGestion"] == "PUBLICADO"

    r_stock = client.get("/api/entradas/eventos/evt-77889/stock")
    assert r_stock.status_code == 200
    assert r_stock.json() == {"id_evento": "evt-77889", "stock": 10}


# ============================================================================
# HU-02: Seguridad y emisión gratuita múltiple
# ============================================================================
def test_hu02_procesar_compra_sin_cookie_rechaza_401(client):
    resp = client.post(
        "/api/entradas/procesar-compra",
        json={"id_evento": "evt-77889", "tipo_entrada": "PAGADA", "cantidad": 1},
    )
    assert resp.status_code == 401
    assert "NO_AUTENTICADO" in resp.text


def test_hu02_emision_directa_requiere_auth_y_bloquea_pagadas(client):
    r_sin_auth = client.post(
        "/api/entradas/emision-directa",
        json={"id_evento": "evt-gratis-01", "cantidad_entradas": 1, "precio_final": 0},
    )
    assert r_sin_auth.status_code == 401

    with patch("services.auth_service.AuthService.validar_sesion", new_callable=AsyncMock, return_value=USUARIO_MOCK):
        r_pagada = client.post(
            "/api/entradas/emision-directa",
            headers={"Cookie": "jwt=token.valido.test"},
            json={"id_evento": "evt-77889", "cantidad_entradas": 1, "precio_final": 0},
        )
        assert r_pagada.status_code == 400


def test_hu02_emision_directa_gratuita_emite_multiples_entradas(client, fake_db):
    with (
        patch("services.auth_service.AuthService.validar_sesion", new_callable=AsyncMock, return_value=USUARIO_MOCK),
        patch("services.catalogo_service.CatalogoService.actualizar_stock_catalogo", new_callable=AsyncMock, return_value=True),
        patch("services.checkin_service.CheckinService.registrar_ticket_puerta", new_callable=AsyncMock, return_value=True) as mock_checkin,
        patch("services.notificaciones_service.NotificacionesService.enviar_ticket_correo", new_callable=AsyncMock, return_value={"estado": "en_cola"}),
        patch("services.broker_service.BrokerService.publish_event", new_callable=AsyncMock, return_value=True),
    ):
        resp = client.post(
            "/api/entradas/emision-directa",
            headers={"Cookie": "jwt=token.valido.test"},
            json={"id_evento": "evt-gratis-01", "cantidad_entradas": 2, "precio_final": 0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entradasEmitidas"]) == 2
        assert body["idEntrada"] == body["entradasEmitidas"][0]
        assert body["registradoEnCheckin"] is True
        assert mock_checkin.call_count == 2

        # Stock de evt-gratis-01 bajó de 5 a 3
        ev = [e for e in fake_db.inventario_evento.docs if e["id_evento"] == "evt-gratis-01"][0]
        assert ev["stock_actual"] == 3


# ============================================================================
# HU-03: Reserva temporal (Hold), promoción revalidada, consulta Pagos y cancelación
# ============================================================================
def test_hu03_hold_requiere_auth_y_bloquea_evento_cancelado(client):
    r_unauth = client.post(
        "/api/entradas/reservas/hold",
        json={"id_evento": "evt-77889", "cantidad": 1, "tiempo_limite_minutos": 15},
    )
    assert r_unauth.status_code == 401

    with patch("services.auth_service.AuthService.validar_sesion", new_callable=AsyncMock, return_value=USUARIO_MOCK):
        r_cancelado = client.post(
            "/api/entradas/reservas/hold",
            headers={"Cookie": "jwt=token.valido.test"},
            json={"id_evento": "evt-cancelado", "cantidad": 1, "tiempo_limite_minutos": 15},
        )
        assert r_cancelado.status_code == 400


def test_hu03_reserva_hold_expone_nombre_codigo_y_libera_stock_al_cancelar(client, fake_db):
    with (
        patch("services.auth_service.AuthService.validar_sesion", new_callable=AsyncMock, return_value=USUARIO_MOCK),
        patch("services.catalogo_service.CatalogoService.actualizar_stock_catalogo", new_callable=AsyncMock, return_value=True),
        patch("services.promociones_service.PromocionesService.revalidar_descuento", new_callable=AsyncMock, return_value=("DESC20", "promo-20", 20, 16000)),
        patch("services.broker_service.BrokerService.publish_event", new_callable=AsyncMock, return_value=True),
    ):
        res_crear = client.post(
            "/api/entradas/reservas/hold",
            headers={"Cookie": "jwt=token.valido.test"},
            json={
                "id_evento": "evt-77889",
                "cantidad": 2,
                "tiempo_limite_minutos": 15,
                "nombre_codigo": "DESC20",
            },
        )
        assert res_crear.status_code == 200
        reserva = res_crear.json()
        id_reserva = reserva["id_reserva"]
        assert reserva["estado_reserva"] == "RESERVADO"
        assert reserva["monto_total"] == 16000
        assert reserva["nombre_codigo"] == "DESC20"

        # Verificar que NO se persistió cookie_header en BD
        doc_res = [r for r in fake_db.reserva_entrada.docs if r["id_reserva"] == id_reserva][0]
        assert "cookie_header" not in doc_res

        # Verificar contrato BE3 hacia Pagos (INT-01): incluye nombre_codigo, total y cantidad_entradas
        res_pagos = client.get(f"/api/entradas/reservas/{id_reserva}")
        assert res_pagos.status_code == 200
        datos_pagos = res_pagos.json()
        assert datos_pagos["total"] == 16000
        assert datos_pagos["cantidad_entradas"] == 2
        assert datos_pagos["nombre_codigo"] == "DESC20"
        assert datos_pagos["estado"] == "RESERVADO"

        # Cancelar reserva y comprobar liberación de stock (de 8 vuelve a 10)
        res_cancelar = client.post(
            f"/api/entradas/reservas/{id_reserva}/cancelar",
            headers={"Cookie": "jwt=token.valido.test"},
            json={"motivo": "Cancelación de prueba funcional"},
        )
        assert res_cancelar.status_code == 200
        assert res_cancelar.json()["cupos_liberados"] == 2

        ev = [e for e in fake_db.inventario_evento.docs if e["id_evento"] == "evt-77889"][0]
        assert ev["stock_actual"] == 10


def test_hu03_webhook_simulado_deshabilitado_por_defecto(client):
    resp = client.post("/api/entradas/reservas/res-98765/webhook-pago")
    assert resp.status_code == 403


# ============================================================================
# HU-04 y HU-05: Historial, detalle inmutable, QR y Check-in
# ============================================================================
def test_hu04_mis_entradas_y_detalle_inmutable(client):
    r_sin_auth = client.get("/api/entradas/mis-entradas")
    assert r_sin_auth.status_code == 401

    with patch("services.auth_service.AuthService.validar_sesion", new_callable=AsyncMock, return_value=USUARIO_MOCK):
        r_hist = client.get("/api/entradas/mis-entradas", headers={"Cookie": "jwt=token.valido.test"})
        assert r_hist.status_code == 200
        entradas = r_hist.json()
        assert len(entradas) >= 1
        assert entradas[0]["tipo_acceso"] == "GENERAL"
        assert entradas[0]["precio_final_pagado"] == 8500
        assert entradas[0]["fecha_evento"] == "2026-11-20"


def test_hu05_payload_qr_y_consulta_checkin(client):
    r_qr = client.get("/api/entradas/tk-998877/qr")
    assert r_qr.status_code == 200
    qr = r_qr.json()
    assert qr["qr_payload"] == {"id_evento": "evt-77889", "id_entrada": "tk-998877"}
    assert qr["habilitado_checkin"] is True

    r_chk = client.get("/api/entradas/tk-998877")
    assert r_chk.status_code == 200
    chk = r_chk.json()
    assert chk["id_ticket"] == "tk-998877"
    assert chk["id_evento"] == "evt-77889"
    assert chk["estado_entrada"] == "EMITIDA"
    assert chk["usuario"]["id_usuario"] == "usr-12345"


# ============================================================================
# Integración Broker (pago.realizado -> emisión múltiple + Check-in + Notificaciones)
# ============================================================================
@pytest.mark.anyio
async def test_broker_pago_realizado_emite_todas_las_entradas_y_limpia_expiracion(fake_db):
    ahora = datetime.utcnow()
    await fake_db.reserva_entrada.insert_one(
        {
            "id_reserva": "hold-pago-01",
            "id_evento": "evt-77889",
            "id_usuario": "usr-12345",
            "nombre_usuario": "Comprador Prueba",
            "rut_usuario": "12.345.678-5",
            "correo_usuario": "comprador@ticketu.test",
            "rol_usuario": "usuario",
            "cantidad_entrada": 2,
            "id_promocion": None,
            "nombre_codigo": None,
            "porcentaje_descuento": 0,
            "monto_total": 20000,
            "id_pago": None,
            "estado_reserva": "RESERVADO",
            "fecha_creacion": ahora,
            "fecha_expiracion": ahora + timedelta(minutes=15),
        }
    )

    with (
        patch("services.broker_service.get_database", return_value=fake_db),
        patch("services.checkin_service.CheckinService.registrar_ticket_puerta", new_callable=AsyncMock, return_value=True) as mock_checkin,
        patch("services.notificaciones_service.NotificacionesService.enviar_ticket_correo", new_callable=AsyncMock, return_value={"estado": "en_cola"}),
        patch("services.broker_service.BrokerService.publish_event", new_callable=AsyncMock, return_value=True),
    ):
        await BrokerService._handle_event(
            "pago.realizado",
            {
                "eventName": "pago.realizado",
                "data": {"id_reserva": "hold-pago-01", "id_pago": "pay-real-999"},
            },
        )

    res_doc = await fake_db.reserva_entrada.find_one({"id_reserva": "hold-pago-01"})
    assert res_doc["estado_reserva"] == "CONSOLIDADO"
    assert res_doc["id_pago"] == "pay-real-999"
    assert res_doc["fecha_expiracion"] is None

    entradas = [e for e in fake_db.entrada.docs if e["id_reserva"] == "hold-pago-01"]
    assert len(entradas) == 2
    assert all(e["id_evento"] == "evt-77889" for e in entradas)
    assert mock_checkin.call_count == 2


# ============================================================================
# Contrato Pagos <-> Entradas (Cookie jwt y resiliencia 503)
# ============================================================================
def test_formatear_cookie_header_auth_service():
    cookie_navegador = "jwt=eyJhbGciJSUzI1NiJ9.payload.sig; theme=dark"
    assert AuthService.formatear_cookie_header(cookie_navegador) == cookie_navegador
    assert AuthService.extraer_jwt(cookie_navegador) == "eyJhbGciJSUzI1NiJ9.payload.sig"


@pytest.mark.anyio
async def test_pagos_reenvia_cookie_sin_bearer_y_descarta_client_secret():
    respuesta_mock = httpx.Response(
        200,
        json={
            "id_pago": "3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "id_reserva": "res-98765",
            "estado_pago": "PENDIENTE",
            "fecha_creacion": "2026-09-30T19:40:00.000Z",
            "url_checkout": "http://localhost:3000/pagos?id_pago=3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "metodo": "formulario",
            "client_secret": "pi_secret_no_guardar",
        },
    )
    cookie_navegador = "jwt=eyJ_token_auth_real; session_flag=1"
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=respuesta_mock) as mock_post:
        resultado = await PagosService.iniciar_cobro(
            id_reserva="res-98765",
            total=15000,
            cantidad_entradas=2,
            cookie_header=cookie_navegador,
        )
        assert resultado["id_pago"] == "3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12"
        assert "client_secret" not in resultado
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Cookie"] == cookie_navegador
        assert "Authorization" not in kwargs["headers"]
        assert "token_sesion" not in kwargs["json"]


@pytest.mark.anyio
async def test_pagos_reintento_idempotente_503_auth_no_disponible():
    resp_503 = httpx.Response(
        503,
        json={"error": "AUTH_NO_DISPONIBLE", "mensaje": "Reintentar", "detalles": []},
    )
    resp_200 = httpx.Response(
        200,
        json={
            "id_pago": "3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "id_reserva": "res-98765",
            "estado_pago": "PENDIENTE",
            "fecha_creacion": "2026-09-30T19:40:00.000Z",
            "url_checkout": "http://localhost:3000/pagos?id_pago=3f2b8c1e-6a4d-4e2f-9b1a-7c5d8e9f0a12",
            "metodo": "formulario",
        },
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[resp_503, resp_200]) as mock_post:
        resultado = await PagosService.iniciar_cobro(
            id_reserva="res-98765",
            total=15000,
            cantidad_entradas=2,
            cookie_header="jwt=eyJ_token_auth_real",
            max_reintentos=2,
        )
        assert mock_post.call_count == 2
        assert resultado["estado_pago"] == "PENDIENTE"
