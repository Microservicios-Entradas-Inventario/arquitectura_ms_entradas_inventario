# TicketU - Microservicio de Entradas e Inventario

Repositorio oficial del microservicio de **Entradas e Inventario** (`entradas-service`) de la plataforma **TicketU** (TITEC 2026-2), desarrollado con **FastAPI (Python 3.12)**, **MongoDB (Motor)** y **RabbitMQ (aio-pika)**, integrado en la red Docker compartida `plataforma-eventos-net`.

- **Guía de instalación:** [INSTALACION.md](INSTALACION.md)
- **Declaración de integraciones:** [INTEGRACIONES.md](INTEGRACIONES.md)
- **Responsables por rol (Evaluación 4):** [RESPONSABLES.md](RESPONSABLES.md)
- **Guía de pruebas QA (CA1 y CA2):** [back-end/tests/INSTRUCCIONES_QA.md](back-end/tests/INSTRUCCIONES_QA.md)
- **Coordinaciones con otros microservicios:** [CAMBIOS_OTROS_MICROSERVICIOS.md](CAMBIOS_OTROS_MICROSERVICIOS.md)

---

## Stack Tecnológico

* **Framework Web:** FastAPI (Python 3.12) + Uvicorn (`PORT=3000` en contenedor)
* **Base de Datos Propia:** MongoDB 7.0 con driver asíncrono `motor` (`ticketu_entradas_db`)
* **Mensajería Asíncrona:** RabbitMQ (`aio-pika`) sobre `ticketu.events` y `entradas.events` (con reconexión automática en segundo plano)
* **Cliente HTTP Asíncrono:** HTTPX con timeouts y reintentos idempotentes
* **Validación:** Pydantic v2
* **Infraestructura:** Docker & Docker Compose (`plataforma-eventos-net` + `entradas-internal-net`)

---

## Estructura del Repositorio (Backend y Operación)

```text
├── back-end/
│   ├── Dockerfile                   # Imagen Docker de entradas-service (Python 3.12-slim)
│   ├── .env.example                 # Plantilla de variables para ejecución local
│   ├── database.py                  # Conexión asíncrona a MongoDB (Motor)
│   ├── main.py                      # App FastAPI, lifespan, workers en background y registro de routers
│   ├── requirements.txt             # Dependencias Python (FastAPI, Uvicorn, Motor, HTTPX, aio-pika, Pytest)
│   ├── routers/
│   │   ├── entradas.py              # Eventos, disponibilidad, stock, compra, emisión gratuita, historial y QR
│   │   ├── inventario.py            # Consulta de inventario por evento (HU-01)
│   │   └── reservas.py              # Hold temporal (HU-03), consulta INT-01, inicio/estado de pago y cancelación
│   ├── schemas/
│   │   └── entradas.py              # Esquemas Pydantic v2 de request y response para Swagger/OpenAPI
│   ├── services/
│   │   ├── auth_service.py          # Introspección de sesión contra Auth (Cookie jwt + x-api-key)
│   │   ├── broker_service.py        # Publicación y consumo en RabbitMQ con reconexión automática
│   │   ├── catalogo_service.py      # Sincronización de stock hacia Catálogo vía API Gateway
│   │   ├── checkin_service.py       # Registro de tickets emitidos y generación de QR JSON
│   │   ├── notificaciones_service.py# Publicación de entradas_emitidas hacia Notificaciones
│   │   ├── pagos_service.py         # Integración HTTP con Pagos (iniciar cobro, polling y reembolso)
│   │   ├── panel_service.py         # Sincronización y consulta de respaldo contra Panel Organizador
│   │   └── promociones_service.py   # Revalidación server-side de códigos promocionales
│   └── tests/
│       ├── test_funcionalidades.py  # Suite funcional Pytest (CA1)
│       ├── INSTRUCCIONES_QA.md      # Guía de ejecución QA (CA1 y CA2)
│       └── TicketU - QA Integracion.postman_collection.json
├── database/
│   └── init_db.js                   # Script de inicialización de colecciones, validadores e índices
├── FELIPE ARREGLALO/                # Archivos modificados del módulo entradas en el frontend principal
├── CAMBIOS_OTROS_MICROSERVICIOS.md  # Ajustes/coordinaciones pendientes con otros squads
├── docker-compose.yml               # Orquestación de entradas-service, MongoDB y Mongo Express
├── INSTALACION.md
├── INTEGRACIONES.md
├── RESPONSABLES.md
└── README.md
```

---

## Catálogo de Endpoints Oficiales (`/api/entradas/*`)

La documentación interactiva Swagger UI se sirve en `http://localhost:3003/docs` (y el esquema JSON en `/openapi.json`).

| Método | Ruta API Gateway | Autenticación | Descripción |
| :--- | :--- | :---: | :--- |
| **GET** | `/api/entradas/health` | Pública | Estado de salud del microservicio (`UP`) |
| **GET** | `/api/entradas/eventos` | Pública | Listado de eventos registrados en inventario |
| **GET** | `/api/entradas/eventos/{id_evento}` | Pública | Detalle de inventario de un evento |
| **GET** | `/api/entradas/eventos/{id_evento}/disponibilidad` | Pública | Disponibilidad y precio para el widget de Catálogo |
| **GET** | `/api/entradas/eventos/{id_evento}/stock` | Pública | Stock actual para validaciones del Panel Organizador |
| **GET** | `/api/entradas/inventario/{id_evento}` | Pública | Consulta de disponibilidad, tipo y precio (HU-01) |
| **POST** | `/api/entradas/procesar-compra` | Cookie `jwt` | Procesa compra gratuita (emite N tickets) o pagada (Hold + Pagos) |
| **POST** | `/api/entradas/emision-directa` | Cookie `jwt` | Emisión inmediata exclusiva para eventos gratuitos (emite N tickets) |
| **POST** | `/api/entradas/reservas/hold` | Cookie `jwt` | Crea reserva temporal (Hold) descontando stock atómicamente (HU-03) |
| **GET** | `/api/entradas/reservas/{id_reserva}` | Pública / Pagos | Consulta oficial de reserva (`total`, `cantidad_entradas`, `nombre_codigo`, TTL) |
| **POST** | `/api/entradas/reservas/{id_reserva}/iniciar-pago` | Cookie `jwt` | Crea intención de pago en Pagos reenviando cookie `jwt` |
| **GET** | `/api/entradas/reservas/{id_reserva}/estado-pago` | Cookie `jwt` | Consulta estado en Pagos y consolida/libera la reserva |
| **POST** | `/api/entradas/reservas/{id_reserva}/cancelar` | Cookie `jwt` | Cancela reserva, devuelve cupos y solicita reembolso en Pagos si aplica |
| **GET** | `/api/entradas/mis-entradas` | Cookie `jwt` | Historial de entradas emitidas del usuario autenticado (HU-04) |
| **GET** | `/api/entradas/usuario/{id_usuario}` | Cookie `jwt` | Historial de entradas de un usuario (propio o `STAFF`/`ORGANIZADOR`) |
| **GET** | `/api/entradas/{id_ticket}/detalle` | Pública / Check-in | Detalle inmutable de una entrada emitida (HU-04 / Check-in) |
| **GET** | `/api/entradas/{id_ticket}/qr` | Pública | Código QR de acceso y payload estructurado (HU-05) |
| **GET** | `/api/entradas/{id_ticket}` | Pública / Check-in | Verificación de existencia, evento y titular para Check-in |

> Por retrocompatibilidad interna también se mantienen alias bajo `/api/v1/...` (ocultos en Swagger para evitar duplicación visual). El endpoint de simulación `webhook-pago` permanece deshabilitado por defecto (`ALLOW_SIMULATED_WEBHOOK=false`).

---

## Ejecución con Docker

```bash
# 1. Crear red compartida (si no existe)
docker network create plataforma-eventos-net

# 2. Construir y levantar el servicio
docker compose up -d --build

# 3. Verificar salud y Swagger
curl -s http://localhost:3003/health
```

- **API directa:** `http://localhost:3003`
- **Swagger UI:** `http://localhost:3003/docs`
- **Vía API Gateway:** `http://localhost:8080/api/entradas/...`
- **Mongo Express:** `http://localhost:8082`
