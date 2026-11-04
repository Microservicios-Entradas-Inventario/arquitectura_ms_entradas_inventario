# 🎟️ TicketU - Microservicio de Entradas e Inventario

Repositorio oficial del microservicio de **Entradas e Inventario** (`entradas-service`) de la plataforma de gestión de eventos **TicketU** (TITEC 2026-2), desarrollado con **FastAPI (Python 3.12)**, **MongoDB (Motor)** y **RabbitMQ (aio-pika)**, e integrado en la red Docker compartida `plataforma-eventos-net`.

📄 **Evidencias de integración en vivo en Docker:** [docs/EVIDENCIAS_INTEGRACION.md](docs/EVIDENCIAS_INTEGRACION.md)

---

## 🛠️ Stack Tecnológico

* **Framework Web:** FastAPI (Python 3.12)
* **Servidor ASGI:** Uvicorn (`PORT=3000` en contenedor Docker)
* **Base de Datos Propia (Database per Service):** MongoDB 7.0 con driver asíncrono `motor` (`ticketu_entradas_db`)
* **Mensajería Asíncrona:** RabbitMQ (`aio-pika`) sobre el exchange `ticketu.events`
* **Cliente HTTP Asíncrono:** HTTPX (con timeouts y manejo de resiliencia entre microservicios)
* **Validación y Serialización:** Pydantic v2
* **Infraestructura:** Docker & Docker Compose (`plataforma-eventos-net` + red interna `entradas-internal-net`)

---

## 🏛️ Estructura del Repositorio

```text
├── back-end/
│   ├── Dockerfile                   # Imagen Docker de entradas-service (Python 3.12-slim, puerto 3000)
│   ├── .env.example                 # Variables de entorno de ejemplo para ejecución local
│   ├── database.py                  # Conexión asíncrona a MongoDB (Motor)
│   ├── main.py                      # App FastAPI, workers en segundo plano (expiración Hold + polling Pagos) y rutas
│   ├── requirements.txt             # Dependencias Python (FastAPI, Uvicorn, Motor, HTTPX, aio-pika, Pytest)
│   ├── routers/                     # Controladores HTTP por dominio
│   │   ├── entradas.py              # Compra de entradas (gratuita/pagada), detalle, historial, QR y consultas
│   │   ├── inventario.py            # Consulta, creación y actualización de inventario y stock por evento
│   │   └── reservas.py              # Reserva temporal (Hold), inicio/consulta/anulación de pago y webhook
│   ├── schemas/                     # Modelos y DTOs Pydantic v2
│   │   └── entradas.py              # Esquemas de entrada/salida (Inventario, Compra, Reserva Hold, QR)
│   ├── services/                    # Clientes de integración con microservicios externos
│   │   ├── auth_service.py          # Validación de sesión con Auth (GET /internal/validar-sesion + Cookie jwt + x-api-key)
│   │   ├── broker_service.py        # Publicación y consumo de eventos en RabbitMQ (ticketu.events)
│   │   ├── catalogo_service.py      # Sincronización de stock hacia Catálogo de Eventos (puerto 4000)
│   │   ├── checkin_service.py       # Registro de tickets emitidos en Check-in (puerto 3001)
│   │   ├── notificaciones_service.py# Publicación de eventos para envío de tickets por correo
│   │   ├── pagos_service.py         # Integración Contrato Pagos <-> Entradas v2.3 (transacciones, estado y reembolso)
│   │   └── panel_service.py         # Notificación de métricas al Panel Organizador (puerto 3000)
│   └── tests/                       # Pruebas automatizadas (Pytest) y colección Postman
├── database/
│   ├── init_db.js                   # Inicialización de colecciones ($jsonSchema), índices TTL y datos semilla
│   └── schema.dbml                  # Modelo documental de base de datos en DBML
├── docs/
│   └── EVIDENCIAS_INTEGRACION.md    # Informe detallado de pruebas de integración en la red Docker
├── Contratos (endpoints que consumimos)/ # Especificación de contratos consumidos (Auth, Pagos, Catálogo, Check-in, Notificaciones)
├── Contratos (endpoints que damos)/      # Especificación de contratos provistos al resto de equipos
├── .env.example                     # Plantilla de variables de entorno para Docker / local
├── docker-compose.yml               # Orquestación de entradas-service, MongoDB y Mongo Express
└── README.md
```

---

## 🔗 Integraciones del Microservicio en `plataforma-eventos-net`

El servicio `entradas-service` se comunica dentro de la red Docker `plataforma-eventos-net` con los siguientes módulos y componentes:

### 1. Autenticación (`auth-service:10000` - Contrato Auth / Pagos v2.3)
* **Método:** [`AuthService.validar_sesion`](back-end/services/auth_service.py)
* **Endpoint consumido:** `GET http://auth-service:10000/internal/validar-sesion`
* **Cabeceras enviadas:**
  * `Cookie: jwt=<token>` (reenviada tal cual llega del navegador)
  * `x-api-key: <INTERNAL_API_KEY>`
* **Comportamiento:** Obtiene `id_usuario`, `rol` (`USUARIO`, `ORGANIZADOR`, `STAFF`, `CLIENTE`), `nombre`, `rut` y `correo`. Si Auth rechaza la cookie devuelve `401 NO_AUTENTICADO`; si Auth no está disponible o falla la red devuelve `503 AUTH_NO_DISPONIBLE`.

### 2. Pasarela de Pagos (`pagos-service:3000` - Contrato Pagos ↔ Entradas v2.3)
* **Método:** [`PagosService`](back-end/services/pagos_service.py) y [`routers/reservas.py`](back-end/routers/reservas.py)
* **Operación 1 (Provista a Pagos - INT-01):** `GET /api/v1/entradas/reservas/{id_reserva}` y `GET /api/entradas/reservas/{id_reserva}`. Responde `200 OK` con `id_reserva`, `id_evento`, `total` (y `monto_total`), `cantidad_entradas` (y `cantidad_entrada`), `estado_reserva` y `tiempo_restante_segundos`.
* **Operación 2 (Consumida - Crear intención de cobro):** `POST http://pagos-service:3000/api/v1/pagos/transacciones` reenviando el header `Cookie` (`jwt`) del comprador. Guarda únicamente `id_pago` como referencia en la reserva (ignorando `client_secret`) y retorna `url_checkout`.
* **Operación 3 (Consumida - Polling de estado cada 5s):** Worker en segundo plano (`tarea_polling_pagos_pendientes` en [`main.py`](back-end/main.py)) y endpoint `GET /api/entradas/reservas/{id_reserva}/estado-pago` que consultan `GET http://pagos-service:3000/api/v1/pagos/{id_pago}`. Si pasa a `APROBADO`, consolida la reserva y emite las entradas con QR; si pasa a `RECHAZADO`/`ANULADO`/`REEMBOLSADO`, libera los cupos.
* **Operación 4 (Consumida - Anulación / Reembolso por expiración o cancelación):** `POST http://pagos-service:3000/api/v1/pagos/{id_pago}/reembolso` reenviando el header `Cookie` (`jwt`) cuando vence el TTL de 15 minutos del Hold (`tarea_liberacion_reservas_expiradas`) o el usuario cancela su reserva.

### 3. Catálogo de Eventos (`catalogo-service:4000` / `ms-catalogo-eventos:4000`)
* **Método:** [`CatalogoService.actualizar_stock_catalogo`](back-end/services/catalogo_service.py)
* **Endpoint consumido:** `PUT http://catalogo-service:4000/api/v1/catalogo/eventos/{id_evento}/stock` enviando `{"nuevo_stock": int, "token_sesion": str}`.
* **Endpoint provisto a Catálogo:** `POST /api/entradas/procesar-compra` (y `/api/v1/entradas/procesar-compra`).

### 4. Check-in (`checkin-service:3001`)
* **Método:** [`CheckinService.registrar_ticket_puerta`](back-end/services/checkin_service.py)
* **Endpoint consumido:** `POST http://checkin-service:3001/api/checkin/tickets` enviando `id_entrada`, `id_evento`, `id_usuario`, `nombre_usuario` y `qr_data` (string idéntico a `id_entrada`).
* **Endpoint provisto a Check-in:** `GET /api/entradas/{id_ticket}` (y `/api/v1/entradas/{id_ticket}`).

### 5. Panel Organizador (`organizador-service:3000`)
* **Endpoints provistos al Panel Organizador:**
  * `POST /api/entradas/inventario` (y `/api/v1/inventario`): Inicialización de stock y precio de un evento.
  * `PUT /api/entradas/inventario/{id_evento}`: Actualización de stock/estado del evento.
  * `GET /api/entradas/eventos/{id_evento}/stock`: Consulta de disponibilidad en tiempo real.

### 6. Event Broker Compartido (`ticketu-rabbitmq:5672`) y API Gateway (`ticketu-api-gateway:8080`)
* **API Gateway:** Enruta todo el tráfico bajo `/api/entradas/*` hacia `http://entradas-service:3000`.
* **RabbitMQ (`BrokerService`):**
  * **Exchange:** `ticketu.events` (`topic`, durable), cola propia `entradas.pagos`.
  * **Eventos publicados:** `entrada.reservada`, `entrada.emitida`, `stock.agotado`, `entradas.evento.stock.v1`, `entradas_emitidas`.
  * **Eventos escuchados:** `pago.realizado`, `pago.rechazado`, `evento.publicado`, `evento.actualizado`, `evento.cancelado`.

---

## 📋 Catálogo Completo de Endpoints

Todas las rutas están expuestas tanto con el prefijo del API Gateway (`/api/entradas/...`) como con los prefijos directos `/api/v1/...`:

| Método | Ruta API Gateway | Ruta Directa v1 | Descripción | Consumidor Principal |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/health` y `/api/entradas/health` | `/health` | Estado de salud del contenedor (`UP`) | Docker / API Gateway |
| **GET** | `/api/entradas/inventario/{id_evento}` | `/api/v1/inventario/{id_evento}` | Consultar stock actual, tipo y precio unitario (HU-01) | Frontend / Catálogo |
| **POST** | `/api/entradas/inventario` | `/api/v1/inventario` | Crear/inicializar inventario para un evento | Panel Organizador |
| **PUT** | `/api/entradas/inventario/{id_evento}` | `/api/v1/inventario/{id_evento}` | Actualizar stock o estado de gestión de un evento | Panel Organizador |
| **POST** | `/api/entradas/procesar-compra` | `/api/v1/entradas/procesar-compra` | Procesar compra gratuita o pagada con validación en Auth (HU-02) | Catálogo / Checkout |
| **POST** | `/api/entradas/reservas/hold` | `/api/v1/entradas/reservas/hold` | Crear reserva temporal (Hold) con TTL de 15 min (HU-03) | Frontend Checkout |
| **GET** | `/api/entradas/reservas/{id_reserva}` | `/api/v1/entradas/reservas/{id_reserva}` | Consultar reserva (`total`, `cantidad_entradas`, TTL) (INT-01) | Pagos / Frontend |
| **POST** | `/api/entradas/reservas/{id_reserva}/iniciar-pago` | `/api/v1/entradas/reservas/{id_reserva}/iniciar-pago` | Iniciar transacción en Pagos v2.3 para una reserva existente | Frontend Checkout |
| **GET** | `/api/entradas/reservas/{id_reserva}/estado-pago` | `/api/v1/entradas/reservas/{id_reserva}/estado-pago` | Consultar estado en Pagos v2.3 y consolidar/liberar reserva | Frontend Checkout |
| **POST** | `/api/entradas/reservas/{id_reserva}/cancelar` | `/api/v1/entradas/reservas/{id_reserva}/cancelar` | Cancelar reserva temporal, devolver stock y reembolsar en Pagos | Frontend / Pagos |
| **POST** | `/api/entradas/reservas/{id_reserva}/webhook-pago` | `/api/v1/reservas/{id_reserva}/webhook-pago` | Consolidar reserva y emitir entradas con QR tras pago aprobado | Pagos / Simulación |
| **GET** | `/api/entradas/usuario/{id_usuario}` | `/api/v1/entradas/usuario/{id_usuario}` | Historial de entradas adquiridas por un usuario (HU-04) | Clientes / Frontend |
| **GET** | `/api/entradas/{id_ticket}/detalle` | `/api/v1/entradas/{id_ticket}/detalle` | Detalle inmutable de una entrada adquirida (HU-04) | Clientes / Frontend |
| **GET** | `/api/entradas/{id_ticket}/qr` | `/api/v1/entradas/{id_ticket}/qr` | Obtener código QR de acceso y payload de validación (HU-05) | Clientes / Frontend |
| **GET** | `/api/entradas/{id_ticket}` | `/api/v1/entradas/{id_ticket}` | Validar existencia y titular de una entrada emitida | Check-in |
| **GET** | `/api/entradas/eventos/{id_evento}/stock` | `/api/v1/entradas/eventos/{id_evento}/stock` | Consultar stock disponible de un evento | Panel Organizador |

---

## 🗄️ Base de Datos y Datos Semilla (`database/init_db.js`)

Al levantar el contenedor `ticketu_entradas_mongo`, el script [`database/init_db.js`](database/init_db.js) crea la base de datos `ticketu_entradas_db` con validación `$jsonSchema` en tres colecciones (`inventario_evento`, `reserva_entrada`, `entrada`) y carga los siguientes datos de prueba:

* **Eventos en `inventario_evento`:**
  * `evt-77889`: Evento **`PAGADA`**, `precio_unitario: 10000`, `stock_actual: 148`, `estado_gestion: "PUBLICADO"`.
  * `evt-002`: Evento **`GRATUITA`**, `precio_unitario: 0`, `stock_actual: 99`, `estado_gestion: "PUBLICADO"`.
* **Reservas en `reserva_entrada`:**
  * `res-98765`: Reserva en estado `CONSOLIDADO` para `evt-77889` (`monto_total: 8500`, `id_pago: "pay-112233"`).
  * `res-98766`: Reserva en estado `RESERVADO` para `evt-77889` (`monto_total: 10000`, `id_pago: "pay-112234"`).
* **Entradas en `entrada`:**
  * `tk-998877`: Entrada `EMITIDA` asociada a `res-98765` y al usuario `usr-12345` (`Sebastián Fuentes`).

---

## ⚙️ Variables de Entorno (`.env.example`)

Puedes copiar [`.env.example`](.env.example) a `.env` en la raíz o en `back-end/.env`:

| Variable | Valor en Docker (`docker-compose.yml`) | Descripción |
| :--- | :--- | :--- |
| `PORT` | `3000` | Puerto interno donde escucha `entradas-service` |
| `MONGO_URI` | `mongodb://mongodb:27017` | URI de conexión a MongoDB en `entradas-internal-net` |
| `MONGO_DB` | `ticketu_entradas_db` | Nombre de la base de datos MongoDB |
| `BROKER_URL` | `amqp://ticketu:ticketu_dev@ticketu-rabbitmq:5672/ticketu` | URI de conexión al broker RabbitMQ |
| `EVENT_EXCHANGE` | `ticketu.events` | Exchange compartido de eventos |
| `QUEUE_NAME` | `entradas.pagos` | Cola de consumo del microservicio de Entradas |
| `AUTH_SERVICE_URL` | `http://auth-service:10000` | URL interna del microservicio de Autenticación |
| `INTERNAL_API_KEY` | `CAMBIAR_CLAVE_COMPARTIDA_SEGURA` | API Key compartida para `GET /internal/validar-sesion` en Auth |
| `PAGOS_SERVICE_URL` | `http://pagos-service:3000` | URL interna del microservicio de Pagos |
| `CATALOGO_SERVICE_URL` | `http://catalogo-service:4000` | URL interna del microservicio de Catálogo de Eventos |
| `CHECKIN_SERVICE_URL` | `http://checkin-service:3001` | URL interna del microservicio de Check-in |
| `PANEL_SERVICE_URL` | `http://organizador-service:3000` | URL interna del microservicio de Panel Organizador |

---

## 🚀 Cómo Levantar el Proyecto con Docker (Recomendado para Integración)

### 1. Clonar el repositorio
```bash
git clone -b backend https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario.git
cd arquitectura_ms_entradas_inventario
```

### 2. Crear la red compartida del ecosistema (si no existe)
```bash
docker network create plataforma-eventos-net 2>/dev/null || true
```

### 3. Construir y levantar los contenedores
```bash
docker compose up -d --build
```
Esto levantará:
* **`entradas-service`:** `http://localhost:3000` (y `http://entradas-service:3000` dentro de `plataforma-eventos-net`)
* **Swagger UI (OpenAPI 3.0):** [http://localhost:3000/docs](http://localhost:3000/docs)
* **Healthcheck:** [http://localhost:3000/health](http://localhost:3000/health)
* **`ticketu_entradas_mongo` (MongoDB):** `localhost:27017`
* **`ticketu_entradas_gui` (Mongo Express):** [http://localhost:8082](http://localhost:8082)

---

## 💻 Ejecución Local (Sin contenedor para FastAPI)

Si deseas correr FastAPI directamente en tu máquina conectándose al contenedor de MongoDB:

```powershell
cd back-end
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 3000
```
*(La documentación interactiva estará disponible en [http://localhost:3000/docs](http://localhost:3000/docs)).*
