# Declaración de Integraciones – Entradas e Inventario (Evaluación 3: Ambiente de Pruebas / Workstation)

## 1. Integraciones declaradas para evaluación

De acuerdo con la especificación de la **Evaluación 3** (una integración por cada tipo: **A. Autenticación**, **B. API Gateway** y **C. Broker**), el módulo **Entradas e Inventario (`entradas-service`)** declara las siguientes **3 integraciones**:

| Integración | Tipo | Módulo contraparte | Servicio, ruta en el gateway o tópico | Cómo se evidencia | Dónde verificarlo |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **I1** | **A. Autenticación** | **Auth** (`auth-service`) | `GET /internal/validar-sesion` (`Cookie: jwt` + `x-api-key`) vía `AUTH_SERVICE_URL` | Funcionalidad + Trazas | Inicio de sesión en Frontend (`http://localhost:3000`) con `comprador1@ticketu.test`; logs `docker logs entradas-service` / `ticketu-auth-service`; rechazo `401` con token alterado |
| **I2** | **B. API Gateway** | **Check-in** (`checkin-service`) | Consumido: `POST /api/checkin/tickets` (vía `http://ticketu-api-gateway:8080/api/checkin/tickets`) · Provisto: `GET /api/entradas/{id_ticket}` y `GET /api/entradas/{id_ticket}/qr` | Funcionalidad + Trazas + Base de datos | Emisión de entrada (`POST /api/entradas/emision-directa` o compra pagada), registro automático en MySQL de Check-in (`registradoEnCheckin: true`), validación en puerta (`POST /api/checkin/validaciones`) y logs de `ticketu-api-gateway` / `entradas-service` / `checkin-checkin-service-1` |
| **I3** | **C. Broker** | **Notificaciones** (`notificaciones-ticketu`) | Exchange `entradas.events` (`topic`, durable) · Routing key `entradas_emitidas` → Cola `notificaciones.entradas_emitidas` | Trazas + Consola del broker | Consola RabbitMQ (`http://localhost:15672`, vhost `ticketu`, exchange `entradas.events` / cola `notificaciones.entradas_emitidas`) y logs `docker logs entradas-service` + `docker logs notificaciones-ticketu-notificaciones-1` al emitir una entrada |

---

## 2. Verificación detallada por ítem de rúbrica

### I1 · Autenticación (`AU1` — Auth)
* **Implementación:** [`AuthService.validar_sesion`](back-end/services/auth_service.py#L43-L95) consulta `GET ${AUTH_SERVICE_URL}/internal/validar-sesion` enviando `Cookie: jwt=<token>` y `x-api-key: ${INTERNAL_API_KEY}` (`timeout=1.0`).
* **Configuración por entorno:** `AUTH_SERVICE_URL` e `INTERNAL_API_KEY` configuradas en [`docker-compose.yml`](docker-compose.yml) (sin valores fijos a `localhost`).
* **Transparencia para el usuario:** El frontend usa `credentials: "include"` con la cookie `jwt` emitida por Auth; el usuario no copia ni pega tokens.
* **Cómo verificar el rechazo de token inválido o vencido (`AU1 (b)`):**
  ```bash
  # 1. Sin cookie jwt -> 401 NO_AUTENTICADO
  curl -i -X POST http://localhost:8080/api/entradas/procesar-compra \
    -H "Content-Type: application/json" \
    -d '{"id_evento":"evt-101","tipo_entrada":"GRATUITA","cantidad":1}'

  # 2. Con cookie jwt alterada / inválida -> 401
  curl -i -X POST http://localhost:8080/api/entradas/procesar-compra \
    -H "Content-Type: application/json" \
    -H "Cookie: jwt=token.invalido.firmamala" \
    -d '{"id_evento":"evt-101","tipo_entrada":"GRATUITA","cantidad":1}'
  ```

---

### I2 · API Gateway (`GW1` — Check-in)
* **Rutas vía Gateway (`http://ticketu-api-gateway:8080`):**
  * **Consumida por Entradas:** `POST ${CHECKIN_SERVICE_URL}/api/checkin/tickets` desde [`CheckinService.registrar_ticket_puerta`](back-end/services/checkin_service.py#L20-L66).
  * **Provista por Entradas a Check-in:** `GET /api/entradas/{id_ticket}` y `GET /api/entradas/{id_ticket}/qr` en [`routers/entradas.py`](back-end/routers/entradas.py).
* **Contratos y OpenAPI:** [`docs/contratos/contrato-http-checkin.md`](docs/contratos/contrato-http-checkin.md), [`docs/contratos/openapi.json`](docs/contratos/openapi.json) y Swagger UI en `/docs`.
* **Cómo verificar manejo de errores (`GW1 (d)`):**
  * **En vivo (`404` / `401`):**
    ```bash
    # Ticket inexistente -> 404 Not Found
    curl -i http://localhost:8080/api/entradas/tk-inexistente-000

    # Validación en Check-in sin sesión STAFF -> 401
    curl -i -X POST http://localhost:8080/api/checkin/validaciones \
      -H "Content-Type: application/json" \
      -d '{"id_entrada":"tk-demo","id_evento":"66f1a0000000000000000003"}'
    ```
  * **En código (timeout y no disponibilidad):** [`back-end/services/checkin_service.py`](back-end/services/checkin_service.py#L50-L66) configura `timeout=0.5`, maneja `400`/`409`/`500` y captura `httpx.RequestError` devolviendo `False` y registrando el error en stdout sin interrumpir el servicio.

---

### I3 · Broker RabbitMQ (`BR1` — Notificaciones)
* **Tópico / Exchange / Cola:**
  * **Exchange:** `entradas.events` (`topic`, `durable=True`)
  * **Routing key:** `entradas_emitidas`
  * **Cola consumidora (Notificaciones):** `notificaciones.entradas_emitidas`
  * **Contrato:** [`Contratos (endpoints que consumimos)/Notificaciones`](./Contratos%20(endpoints%20que%20consumimos)) y [`NotificacionesService`](back-end/services/notificaciones_service.py#L41-L85).
* **Esquema JSON publicado en `entradas_emitidas`:**
  ```json
  {
    "correo_comprador": "string",
    "nombre_comprador": "string",
    "id_usuario": "string",
    "nombre_evento": "string",
    "id_evento": "string",
    "fecha_evento": "YYYY-MM-DD",
    "hora_evento": "HH:MM",
    "qr_data": "string (URL QR)"
  }
  ```
* **Configuración y caída del broker (`BR1 (d)`):**
  * `BROKER_URL` se obtiene por variable de entorno en [`back-end/services/broker_service.py`](back-end/services/broker_service.py#L9).
  * Si RabbitMQ no está disponible al iniciar o publicar, [`BrokerService.connect`](back-end/services/broker_service.py#L54-L56) y `BrokerService.publish_notificaciones` capturan la excepción, dejan `_is_connected = False` y registran la advertencia `[RabbitMQ] Advertencia: No se pudo conectar al broker (...)` sin botar la aplicación.

---

## 3. Otras integraciones activas en el ecosistema (referencia)

| Integración | Tipo | Módulo contraparte | Servicio / tópico | Contrato |
| :--- | :--- | :--- | :--- | :--- |
| **R1** | B (API Gateway) | **Catálogo de Eventos** | `POST /api/entradas/procesar-compra`, `GET /api/entradas/eventos/{id_evento}/disponibilidad` y `PUT /api/v1/catalogo/eventos/{id_evento}/stock` | [`docs/contratos/contrato-http-catalogo.md`](docs/contratos/contrato-http-catalogo.md) |
| **R2** | B (API Gateway) | **Pasarela de Pagos** | `POST /api/pagos/transacciones` (con soporte `nombre_codigo`), `GET /api/pagos/{id_pago}` y `GET /api/entradas/reservas/{id_reserva}` | [`docs/contratos/contrato-http-pagos.md`](docs/contratos/contrato-http-pagos.md) |
| **R3** | C (Broker) | **Panel Organizador** | `ticketu.events` (`panel.evento.entradas.v1` / `entradas.evento.stock.v1`) | [`docs/contratos/contrato-mensajeria-panel.md`](docs/contratos/contrato-mensajeria-panel.md) |
