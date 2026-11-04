# Contrato de Interfaz HTTP: Entradas e Inventario ↔ Check-in

**Módulos:** Entradas e Inventario (`entradas-service:3000`) ↔ Check-in (`checkin-service:3001`)  
**Red Docker Compartida:** `plataforma-eventos-net`  
**Implementación en código:** [`back-end/services/checkin_service.py`](../../back-end/services/checkin_service.py) y [`back-end/routers/entradas.py`](../../back-end/routers/entradas.py)  

---

## 1. Integración como Consumidor (Tipo A): Registro de Ticket Emitido en Check-in

Cada vez que `entradas-service` emite una entrada definitiva (ya sea de forma inmediata en un evento gratuito o tras la confirmación de pago aprobado), invoca asíncronamente al microservicio de **Check-in** para registrar el ticket en su base de datos MySQL y habilitar el control de acceso en puerta.

### 1.1. Especificación del Endpoint Consumido
* **Proveedor:** `checkin-service` (`http://checkin-service:3001`)
* **Consumidor:** `entradas-service`
* **Método y Ruta:** `POST /api/checkin/tickets`
* **Cabeceras:** `Content-Type: application/json`
* **Timeout (SLA):** `< 500 ms`

### 1.2. Esquema JSON del Payload Enviado (`Request Body`)

Todos los campos son strings obligatorios sin espacios iniciales ni finales (`additionalProperties: false`). El campo `qr_data` debe coincidir exactamente con `id_entrada`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RegistrarTicketCheckinRequest",
  "type": "object",
  "additionalProperties": false,
  "required": ["id_entrada", "id_evento", "id_usuario", "nombre_usuario", "qr_data"],
  "properties": {
    "id_entrada": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "example": "tk-998877"
    },
    "id_evento": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "example": "evt-77889"
    },
    "id_usuario": {
      "type": "string",
      "minLength": 1,
      "maxLength": 255,
      "example": "usr-12345"
    },
    "nombre_usuario": {
      "type": "string",
      "minLength": 1,
      "maxLength": 200,
      "example": "Sebastián Fuentes"
    },
    "qr_data": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "description": "Identificador contenido en el QR; debe ser idéntico a id_entrada.",
      "example": "tk-998877"
    }
  }
}
```

### 1.3. Respuestas y Códigos de Estado (`POST /api/checkin/tickets`)

| Código HTTP | Código Interno | Descripción / Manejo en `entradas-service` |
| :---: | :--- | :--- |
| **`201 Created`** | `OK` | `{"mensaje": "Ticket registrado exitosamente para control de acceso."}` |
| **`400 Bad Request`** | `INVALID_REQUEST` / `QR_MISMATCH` | Datos faltantes, strings con espacios extremos o `qr_data != id_entrada`. Se registra en logs para auditoría. |
| **`409 Conflict`** | `TICKET_ALREADY_EXISTS` | El `id_entrada` ya existe en MySQL de Check-in (garantía de idempotencia sin sobrescritura). |
| **`413 Payload Too Large`** | `PAYLOAD_TOO_LARGE` | Cuerpo superior a 16 KiB. |
| **`500 Internal Server Error`** | `INTERNAL_ERROR` | Falla interna en la base de datos MySQL de Check-in. |

---

## 2. Integración como Proveedor (Tipo B): Consulta de Validez y Titular de Entrada

El microservicio de **Check-in** puede consultar directamente a `entradas-service` para verificar la existencia e información del titular de un ticket emitido.

### 2.1. Especificación del Endpoint Provisto
* **Proveedor:** `entradas-service` (`http://entradas-service:3000`)
* **Consumidor:** `checkin-service`
* **Método y Ruta:** `GET /api/entradas/{id_ticket}` (y `/api/v1/entradas/{id_ticket}`)
* **Contrato OpenAPI:** [`docs/contratos/openapi.json`](openapi.json)

### 2.2. Ejemplo de Respuesta Exitosa (`200 OK`)

```json
{
  "id_ticket": "tk-998877",
  "nombre_usuario": "Sebastián Fuentes",
  "usuario": {
    "id_usuario": "usr-12345",
    "rol_usuario": "cliente"
  }
}
```

### 2.3. Códigos de Respuesta (`GET /api/entradas/{id_ticket}`)

| Código HTTP | Descripción |
| :---: | :--- |
| **`200 OK`** | Entrada encontrada en la colección `entrada` de MongoDB; retorna titular y rol. |
| **`400 Bad Request`** | Parámetro `id_ticket` inválido o vacío. |
| **`404 Not Found`** | `{"detail": "La entrada no existe."}` |
| **`503 Service Unavailable`** | Base de datos MongoDB temporalmente no disponible. |

