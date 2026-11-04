# Informe de Pruebas de Integración en Docker (`entradas-service` ↔ Ecosistema TicketU)

**Microservicio Evaluado:** Entradas e Inventario (`entradas-service`)  
**Red Compartida Docker:** `plataforma-eventos-net` (`172.18.0.0/16`)  
**Red Interna de Datos:** `entradas-internal-net` (aislamiento Database-per-Service para MongoDB)  
**Fecha de Ejecución:** Noviembre 2026  

---

## 1. Topología de Red y Contenedores Conectados en Docker

Todos los microservicios del ecosistema se encuentran levantados y unidos a la red externa compartida `plataforma-eventos-net`, comunicándose mediante resolución DNS interna de Docker por sus nombres/alias de servicio y puertos internos.

```mermaid
flowchart TD
    GW["ticketu-api-gateway<br/>(172.18.0.3 : 8080)"]
    ENT["entradas-service<br/>(172.18.0.5 : 3000)"]
    MONGO[("ticketu_entradas_mongo<br/>(entradas-internal-net : 27017)")]
    AUTH["auth-service<br/>(172.18.0.8 : 10000)"]
    PAGOS["pagos-service<br/>(172.18.0.9 : 3000 / Host 3004)"]
    CAT["ms-catalogo-eventos / catalogo-service<br/>(172.18.0.2 : 4000)"]
    CHK["checkin-service<br/>(172.18.0.7 : 3001)"]
    ORG["organizador-service<br/>(172.18.0.6 : 3000)"]
    RMQ[["ticketu-rabbitmq<br/>(172.18.0.4 : 5672)"]]

    GW -->|"/api/entradas/*"| ENT
    ENT --- MONGO
    ENT <-->|"GET /internal/validar-sesion<br/>(Cookie: jwt + x-api-key)"| AUTH
    ENT <-->|"POST /api/v1/pagos/transacciones<br/>GET /api/v1/entradas/reservas/{id}"| PAGOS
    ENT <-->|"PUT /api/v1/catalogo/eventos/{id}/stock<br/>POST /api/entradas/procesar-compra"| CAT
    ENT <-->|"POST /api/checkin/tickets<br/>GET /api/entradas/{id_ticket}"| CHK
    ENT <-->|"POST /api/entradas/inventario<br/>GET /api/entradas/eventos/{id}/stock"| ORG
    ENT <-->|"AMQP Exchange: ticketu.events"| RMQ
```

### Estado verificado de contenedores en `plataforma-eventos-net`

| Servicio / Alias DNS | Contenedor Docker | IP en `plataforma-eventos-net` | Puerto Interno | Puerto Host | Variable en [`docker-compose.yml`](../docker-compose.yml) |
|---|---|---|---|---|---|
| `entradas-service` | `entradas-service` | `172.18.0.5/16` | `3000` | `3000` | `PORT=3000` |
| `auth-service` | `auth-service` | `172.18.0.8/16` | `10000` | `10000` | `AUTH_SERVICE_URL=http://auth-service:10000` |
| `pagos-service` | `pagos-service` | `172.18.0.9/16` | `3000` | `3004` | `PAGOS_SERVICE_URL=http://pagos-service:3000` |
| `catalogo-service` | `ms-catalogo-eventos` | `172.18.0.2/16` | `4000` | `4000` | `CATALOGO_SERVICE_URL=http://catalogo-service:4000` |
| `checkin-service` | `backend-main-checkin-service-1` | `172.18.0.7/16` | `3001` | `3001` | `CHECKIN_SERVICE_URL=http://checkin-service:3001` |
| `organizador-service` | `panel-organizador-integracion-organizador-service-1` | `172.18.0.6/16` | `3000` | N/A | `PANEL_SERVICE_URL=http://organizador-service:3000` |
| `ticketu-api-gateway` | `ticketu-api-gateway` | `172.18.0.3/16` | `8080` | `8080` | Enrutamiento `/api/entradas/*` |
| `ticketu-rabbitmq` | `ticketu-rabbitmq` | `172.18.0.4/16` | `5672` | `5672 / 15672` | `BROKER_URL=amqp://ticketu:...@ticketu-rabbitmq:5672/ticketu` |

---

## 2. Pruebas de Integración por Microservicio

### 2.1. Integración `entradas-service` ↔ `auth-service` (Contrato Auth / Pagos v2.3)

* **Implementación en Entradas:** [`back-end/services/auth_service.py`](../back-end/services/auth_service.py)
* **Mecanismo:** Entradas invoca `GET http://auth-service:10000/internal/validar-sesion` enviando la cabecera `x-api-key` (`INTERNAL_API_KEY`) y reenviando el header `Cookie: jwt=<token>` del comprador.

#### Evidencias ejecutadas en Docker:
1. **Disponibilidad HTTP del contenedor `auth-service` desde `entradas-service`:**
   ```powershell
   docker exec entradas-service curl -i -s http://auth-service:10000/
   ```
   **Respuesta obtenida:**
   ```http
   HTTP/1.1 200 OK
   Content-Type: text/html; charset=utf-8

   Hello World!
   ```

2. **Validación de sesión en `/internal/validar-sesion` con `x-api-key` compartida:**
   ```powershell
   docker exec entradas-service curl -i -s http://auth-service:10000/internal/validar-sesion `
     -H "x-api-key: CAMBIAR_CLAVE_COMPARTIDA_SEGURA" `
     -H "Cookie: jwt=token_de_prueba"
   ```
   **Respuesta obtenida (`401 Unauthorized` de Auth confirmando que la API Key fue aceptada y el JWT fue evaluado):**
   ```json
   {
     "message": "Token inválido o expirado",
     "error": "Unauthorized",
     "statusCode": 401
   }
   ```

---

### 2.2. Integración `entradas-service` ↔ `pagos-service` (Contrato Pagos ↔ Entradas v2.3)

* **Implementación en Entradas:** [`back-end/services/pagos_service.py`](../back-end/services/pagos_service.py) y [`back-end/routers/reservas.py`](../back-end/routers/reservas.py).
* **Operaciones verificadas:**
  * **Salud y conectividad:** `GET http://pagos-service:3000/api/pagos/health`
  * **Operación 1 (`Pagos → Entradas`):** `GET http://entradas-service:3000/api/v1/entradas/reservas/{id_reserva}` (devuelve `id_reserva`, `id_evento`, `total`/`monto_total`, `cantidad_entradas`/`cantidad_entrada`).
  * **Operación 2 (`Entradas → Pagos`):** `POST http://pagos-service:3000/api/v1/pagos/transacciones` reenviando `Cookie: jwt=...`.
  * **Operación 3 (`Entradas → Pagos`):** Polling cada 5s en [`back-end/main.py`](../back-end/main.py) vía `GET /api/v1/pagos/{id_pago}`.
  * **Operación 4 (`Entradas → Pagos`):** Anulación/reembolso al expirar reserva en [`back-end/main.py`](../back-end/main.py) vía `POST /api/v1/pagos/{id_pago}/reembolso`.

#### Evidencias ejecutadas en Docker:
1. **Healthcheck de `entradas-service` → `pagos-service`:**
   ```powershell
   docker exec entradas-service curl -s http://pagos-service:3000/api/pagos/health
   ```
   **Respuesta obtenida:**
   ```json
   {
     "estado": "ok",
     "servicio": "microservicio-pagos",
     "base_datos": "ok",
     "pasarela": "mock",
     "entradas": "http",
     "auth": "validar-sesion",
     "broker": "rabbitmq"
   }
   ```

2. **Consulta de reserva desde `pagos-service` → `entradas-service` (Operación 1 - INT-01):**
   ```powershell
   docker exec pagos-service wget -qO- http://entradas-service:3000/api/v1/entradas/reservas/res-98765
   ```
   **Respuesta obtenida (`200 OK`):**
   ```json
   {
     "id_reserva": "res-98765",
     "hold_id": "res-98765",
     "id_evento": "evt-77889",
     "id_usuario": "usr-12345",
     "nombre_usuario": "Sebastián Fuentes",
     "rut_usuario": null,
     "correo_usuario": null,
     "cantidad_entrada": 1,
     "cantidad_entradas": 1,
     "monto_total": 8500,
     "total": 8500,
     "id_pago": "pay-112233",
     "estado_reserva": "CONSOLIDADO",
     "fecha_expiracion": null,
     "tiempo_restante_segundos": 0,
     "expirada": false
   }
   ```

---

### 2.3. Integración `entradas-service` ↔ `ms-catalogo-eventos` (`catalogo-service:4000`)

* **Implementación en Entradas:** [`back-end/services/catalogo_service.py`](../back-end/services/catalogo_service.py) y [`back-end/routers/entradas.py`](../back-end/routers/entradas.py).
* **Operaciones verificadas:**
  * **Salud bidireccional:** `entradas-service:3000/health` ↔ `catalogo-service:4000/health`.
  * **Actualización de stock (`Entradas → Catálogo`):** `PUT http://catalogo-service:4000/api/v1/catalogo/eventos/{id_evento}/stock` enviando `{"nuevo_stock": int, "token_sesion": str}`.

#### Evidencias ejecutadas en Docker:
1. **Salud desde `entradas-service` hacia `catalogo-service:4000`:**
   ```powershell
   docker exec entradas-service curl -s http://catalogo-service:4000/health
   ```
   **Respuesta obtenida (`200 OK`):**
   ```json
   {
     "status": "OK",
     "service": "ms-catalogo-eventos",
     "timestamp": "2026-11-04T03:00:22.292Z"
   }
   ```

2. **Salud desde `ms-catalogo-eventos` hacia `entradas-service:3000`:**
   ```powershell
   docker exec ms-catalogo-eventos node -e "fetch(process.env.ENTRADAS_SERVICE_URL + '/health').then(async r => console.log(r.status, await r.text()))"
   ```
   **Respuesta obtenida (`200 OK`):**
   ```text
   200 {"status":"UP","service":"entradas-service","timestamp":"2026-10-29T22:46:50.709348"}
   ```

3. **Validación del contrato `PUT /api/v1/catalogo/eventos/{id}/stock` desde `entradas-service`:**
   ```powershell
   docker exec entradas-service curl -i -s -X PUT http://catalogo-service:4000/api/v1/catalogo/eventos/evt-101/stock `
     -H "Content-Type: application/json" `
     -d '{\"nuevo_stock\": -1, \"token_sesion\": \"jwt_test\"}'
   ```
   **Respuesta obtenida desde el controlador de Catálogo (`400 Bad Request` validando reglas de negocio):**
   ```json
   {
     "success": false,
     "message": "Datos inválidos. El campo nuevo_stock es obligatorio y debe ser un número entero mayor o igual a 0."
   }
   ```

---

### 2.4. Integración `entradas-service` ↔ `checkin-service` (`checkin-service:3001`)

* **Implementación en Entradas:** [`back-end/services/checkin_service.py`](../back-end/services/checkin_service.py) y [`back-end/routers/entradas.py`](../back-end/routers/entradas.py).
* **Operaciones verificadas:**
  * **Registro de ticket emitido (`Entradas → Check-in`):** `POST http://checkin-service:3001/api/checkin/tickets` con `id_entrada`, `id_evento`, `id_usuario`, `nombre_usuario` y `qr_data` (string idéntico a `id_entrada`), persistiendo en la base de datos MySQL de Check-in.
  * **Validación de ticket en puerta (`POST /api/checkin/validaciones`):** Comprobación del ticket insertado en MySQL de Check-in.
  * **Consulta de ticket (`Check-in → Entradas`):** `GET http://entradas-service:3000/api/entradas/{id_ticket}`.

#### Evidencias ejecutadas en Docker:
1. **Salud bidireccional entre `entradas-service` y `checkin-service`:**
   ```powershell
   docker exec entradas-service curl -s http://checkin-service:3001/health
   ```
   **Respuesta obtenida (`200 OK`):**
   ```json
   {"status":"ok","storage":"mysql"}
   ```

2. **Envío de ticket desde `entradas-service` a `checkin-service` y validación en MySQL:**
   ```powershell
   docker exec entradas-service python -c "import asyncio; from services.checkin_service import CheckinService; print(asyncio.run(CheckinService.registrar_ticket_puerta(id_entrada='tk-test-001', id_evento='evt-101', id_usuario='usr-001', nombre_usuario='Sebastián Fuentes', qr_data='tk-test-001')))"
   ```
   **Respuesta obtenida (`201 Created` → `True`) y verificación inmediata en `/api/checkin/validaciones`:**
   ```json
   {
     "valido": true,
     "motivo": "TICKET_FOUND",
     "ticket": {
       "id_entrada": "tk-test-001",
       "id_evento": "evt-101",
       "nombre_usuario": "Sebastián Fuentes"
     }
   }
   ```

3. **Consulta desde `checkin-service` hacia `entradas-service` (`GET /api/entradas/tk-998877`):**
   ```powershell
   docker exec backend-main-checkin-service-1 node -e "fetch('http://entradas-service:3000/api/entradas/tk-998877').then(async r => console.log(r.status, await r.text()))"
   ```
   **Respuesta obtenida (`200 OK`):**
   ```json
   200 {"id_ticket":"tk-998877","nombre_usuario":"Sebastián Fuentes","usuario":{"id_usuario":"usr-12345","rol_usuario":"cliente"}}
   ```

---

### 2.5. Integración `entradas-service` ↔ `organizador-service` (`organizador-service:3000`) e Infraestructura (`API Gateway` + `RabbitMQ`)

* **Implementación en Entradas:** [`back-end/routers/inventario.py`](../back-end/routers/inventario.py), [`back-end/routers/entradas.py`](../back-end/routers/entradas.py) y [`back-end/services/broker_service.py`](../back-end/services/broker_service.py).

#### Evidencias ejecutadas en Docker:
1. **Salud desde `entradas-service` hacia `organizador-service:3000`:**
   ```powershell
   docker exec entradas-service curl -s http://organizador-service:3000/health
   ```
   **Respuesta obtenida (`200 OK`):**
   ```json
   {"status":"ok","service":"panel-organizador"}
   ```

2. **Enrutamiento a través del API Gateway (`ticketu-api-gateway:8080` → `entradas-service:3000`):**
   ```powershell
   docker exec entradas-service curl -s http://ticketu-api-gateway:8080/api/entradas/health
   ```
   **Respuesta obtenida (`200 OK`):**
   ```json
   {"status":"UP","service":"entradas-service","timestamp":"2026-11-04T03:00:22.344083"}
   ```

3. **Conexión activa con `ticketu-rabbitmq` (`amqp://ticketu-rabbitmq:5672/ticketu`) y `ticketu_entradas_mongo` (`mongodb://mongodb:27017`):**
   En los logs de arranque de `entradas-service`:
   ```text
   Conectando a MongoDB en: mongodb://mongodb:27017
   Conexión exitosa a la base de datos: ticketu_entradas_db
   [Broker] Conectado exitosamente a RabbitMQ (amqp://ticketu:ticketu_dev@ticketu-rabbitmq:5672/ticketu) - Exchange: ticketu.events
   ```

---

## 3. Comando único de verificación integral en consola

Puedes ejecutar este comando desde PowerShell en cualquier momento para demostrar en vivo que `entradas-service` tiene conexión directa con todos los microservicios de la red `plataforma-eventos-net`:

```powershell
docker exec entradas-service python -c "import urllib.request;
for name, url in [
    ('Auth', 'http://auth-service:10000/'),
    ('Pagos', 'http://pagos-service:3000/api/pagos/health'),
    ('Catalogo', 'http://catalogo-service:4000/health'),
    ('Check-in', 'http://checkin-service:3001/health'),
    ('Panel Organizador', 'http://organizador-service:3000/health'),
    ('API Gateway -> Entradas', 'http://ticketu-api-gateway:8080/api/entradas/health')
]:
    r = urllib.request.urlopen(url, timeout=3)
    print(f'[OK {r.status}] {name}: {r.read().decode().strip()}')"
```

