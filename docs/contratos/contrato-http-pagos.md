# Contrato de Interfaz HTTP: Entradas e Inventario ↔ Pasarela de Pagos (v2.3)

**Módulos:** Entradas e Inventario (`entradas-service:3000`) ↔ Pasarela de Pagos (`pagos-service:3000`, Host `3004`)  
**Red Docker Compartida:** `plataforma-eventos-net`  
**Implementación en código:** [`back-end/services/pagos_service.py`](../../back-end/services/pagos_service.py), [`back-end/routers/reservas.py`](../../back-end/routers/reservas.py), [`back-end/routers/entradas.py`](../../back-end/routers/entradas.py) y [`back-end/main.py`](../../back-end/main.py)  

---

## 1. Integración como Proveedor (Tipo B - Operación 1 / INT-01): Consulta de Reserva desde Pagos

Antes de crear o confirmar una transacción de cobro, `pagos-service` consulta síncronamente a `entradas-service` para verificar que la reserva exista, esté vigente y que el monto (`total`) y cantidad de tickets (`cantidad_entradas`) coincidan.

### 1.1. Especificación del Endpoint Provisto
* **Proveedor:** `entradas-service` (`http://entradas-service:3000`)
* **Consumidor:** `pagos-service`
* **Método y Rutas:**
  * `GET /api/v1/entradas/reservas/{id_reserva}`
  * `GET /api/entradas/reservas/{id_reserva}`
* **Cabeceras:** No exige `x-api-key`. Recibe opcionalmente `Cookie: jwt=<token>` por si el Hold venció al momento de la lectura.
* **Contrato OpenAPI:** [`docs/contratos/openapi.json`](openapi.json)

### 1.2. Ejemplo de Respuesta Exitosa (`200 OK`)

```json
{
  "id_reserva": "res-98765",
  "hold_id": "res-98765",
  "id_evento": "evt-77889",
  "id_usuario": "usr-12345",
  "nombre_usuario": "Sebastián Fuentes",
  "rut_usuario": "20.123.456-7",
  "correo_usuario": "sebastian.fuentes@ticketu.cl",
  "cantidad_entrada": 1,
  "cantidad_entradas": 1,
  "monto_total": 10000,
  "total": 10000,
  "id_pago": "pay-112233",
  "estado_reserva": "RESERVADO",
  "fecha_expiracion": "2026-11-04T03:30:00Z",
  "tiempo_restante_segundos": 845,
  "expirada": false
}
```

### 1.3. Códigos de Respuesta (`GET /api/v1/entradas/reservas/{id_reserva}`)

| Código HTTP | Descripción |
| :---: | :--- |
| **`200 OK`** | Reserva encontrada; incluye simultáneamente `total`/`monto_total` y `cantidad_entradas`/`cantidad_entrada`. |
| **`404 Not Found`** | `{"detail": "Reserva no encontrada."}` |
| **`500 Internal Server Error`** | Error de disponibilidad en base de datos MongoDB. |

---

## 2. Integración como Consumidor (Tipo A - Operaciones 2, 3 y 4): Inicio, Polling y Reembolso en Pagos

### 2.1. Operación 2: Crear Intención de Pago (`POST /api/v1/pagos/transacciones`)
* **Proveedor:** `pagos-service` (`http://pagos-service:3000`)
* **Cabeceras enviadas:**
  * `Content-Type: application/json`
  * `Cookie: jwt=<token>` (reenviado tal cual llegó del navegador del comprador)
* **Request Body enviado por Entradas:**
  ```json
  {
    "id_reserva": "res-a1b2c3d4",
    "id_evento": "evt-77889",
    "total": 10000,
    "cantidad_entradas": 1,
    "metodo": "formulario"
  }
  ```
* **Respuesta `201 Created` / `200 OK`:**
  * Entradas almacena **únicamente `id_pago`** en `reserva_entrada`, descarta `client_secret` antes de responder al cliente y entrega `url_checkout`, `estado_pago` y `fecha_expiracion`.
* **Manejo de errores:**
  * `401 NO_AUTENTICADO` o `503 AUTH_NO_DISPONIBLE`: Entradas revierte la reserva temporal y devuelve el cupo al stock para permitir un reintento limpio.
  * `409 CONFLICTO_IDEMPOTENCIA`, `422 ORDEN_INCONSISTENTE`, `502 ERROR_PASARELA`: Propagados con su código y detalle estructurado.

### 2.2. Operación 3: Consulta de Estado y Polling Cada 5 Segundos (`GET /api/v1/pagos/{id_pago}`)
* **Mecanismo:** El worker en segundo plano `tarea_polling_pagos_pendientes` ([`back-end/main.py`](../../back-end/main.py)) y el endpoint `GET /api/entradas/reservas/{id_reserva}/estado-pago` consultan `GET http://pagos-service:3000/api/v1/pagos/{id_pago}` reenviando el header `Cookie` (`jwt`).
* **Transiciones de negocio:**
  * `APROBADO`: Consolida la reserva (`CONSOLIDADO`), emite las entradas con código QR y notifica a Check-in, Notificaciones y RabbitMQ.
  * `RECHAZADO` / `ANULADO` / `REEMBOLSADO`: Libera los cupos reservados devolviéndolos a `stock_actual`.
  * `PENDIENTE` o `503 AUTH_NO_DISPONIBLE`: Mantiene la reserva intacta y reintenta en el siguiente ciclo.

### 2.3. Operación 4: Anulación o Reembolso por Expiración de Hold (`POST /api/v1/pagos/{id_pago}/reembolso`)
* **Mecanismo:** Cuando una reserva en estado `RESERVADO` supera sus 15 minutos de vigencia (`tarea_liberacion_reservas_expiradas` o cancelación manual en `POST /api/entradas/reservas/{id_reserva}/cancelar`), `entradas-service` libera el stock y envía:
  ```json
  {
    "motivo": "Hold de la reserva vencido: el usuario pagó fuera de plazo"
  }
  ```
  hacia `POST http://pagos-service:3000/api/v1/pagos/{id_pago}/reembolso` reenviando el header `Cookie: jwt=<token>`.

