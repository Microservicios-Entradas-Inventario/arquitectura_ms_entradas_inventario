# Contrato de Interfaz HTTP: Entradas e Inventario ↔ Catálogo de Eventos

**Módulos:** Entradas e Inventario (`entradas-service:3000`) ↔ Catálogo de Eventos (`ms-catalogo-eventos:4000` / `catalogo-service:4000`)  
**Red Docker Compartida:** `plataforma-eventos-net`  
**Implementación en código:** [`back-end/services/catalogo_service.py`](../../back-end/services/catalogo_service.py) y [`back-end/routers/entradas.py`](../../back-end/routers/entradas.py)  

---

## 1. Integración como Consumidor (Tipo A): Actualización de Stock hacia Catálogo

Cada vez que `entradas-service` procesa una compra o reserva en `POST /api/entradas/procesar-compra`, descuenta atómicamente el stock en su base de datos MongoDB y notifica de inmediato en paralelo al microservicio de **Catálogo de Eventos** para mantener sincronizada la disponibilidad visible en la vitrina pública.

### 1.1. Especificación del Endpoint Consumido
* **Proveedor:** `ms-catalogo-eventos` (`http://catalogo-service:4000`)
* **Consumidor:** `entradas-service`
* **Método y Ruta:** `PUT /api/v1/catalogo/eventos/{id_evento}/stock` (y `/api/catalogo/eventos/{id_evento}/stock`)
* **Cabeceras:** `Content-Type: application/json`
* **Timeout (SLA):** `< 500 ms`

### 1.2. Esquema JSON del Payload Enviado (`Request Body`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ActualizarStockCatalogoRequest",
  "type": "object",
  "required": ["nuevo_stock", "token_sesion"],
  "properties": {
    "nuevo_stock": {
      "type": "integer",
      "minimum": 0,
      "description": "Cantidad exacta de entradas disponibles luego de descontar la compra.",
      "example": 147
    },
    "token_sesion": {
      "type": "string",
      "minLength": 1,
      "description": "Token JWT de la sesión activa del comprador.",
      "example": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
  }
}
```

### 1.3. Respuestas y Códigos de Estado (`PUT /api/v1/catalogo/eventos/{id_evento}/stock`)

| Código HTTP | Descripción / Comportamiento en Catálogo y Entradas |
| :---: | :--- |
| **`200 OK` / `204 No Content`** | Stock actualizado en Catálogo. Si `nuevo_stock == 0`, Catálogo cambia automáticamente `estado_evento` a `"agotado"`. |
| **`400 Bad Request`** | `nuevo_stock` inválido (negativo o no entero). |
| **`401 Unauthorized`** | `token_sesion` ausente o vacío. |
| **`404 Not Found`** | El `id_evento` no existe en la base de datos de Catálogo. |
| **`500 Internal Server Error` / Timeout** | Capturado en `CatalogoService` mediante `httpx.RequestError` (*Graceful Degradation*), registrando la traza en consola sin interrumpir la compra del usuario. |

---

## 2. Integración como Proveedor (Tipo B): Procesamiento de Compra desde Catálogo

El microservicio o frontend de **Catálogo de Eventos** inicia el flujo de adquisición de entradas invocando el endpoint transaccional expuesto por `entradas-service`.

### 2.1. Especificación del Endpoint Provisto
* **Proveedor:** `entradas-service` (`http://entradas-service:3000`)
* **Consumidor:** Catálogo de Eventos / Checkout
* **Método y Rutas:**
  * `POST /api/entradas/procesar-compra`
  * `POST /api/v1/entradas/procesar-compra`
* **Cabeceras:** `Cookie: jwt=<token>` (validada contra `auth-service:10000`)
* **Contrato OpenAPI:** [`docs/contratos/openapi.json`](openapi.json)

### 2.2. Ejemplo de Request y Response (`200 OK`)

**Request Body:**
```json
{
  "id_evento": "evt-77889",
  "tipo_entrada": "PAGADA",
  "cantidad": 1,
  "metodo": "formulario"
}
```

**Response (`200 OK`):**
```json
{
  "nuevo_stock": 147,
  "id_reserva": "res-a1b2c3d4",
  "id_pago": "pay-998877",
  "estado_pago": "PENDIENTE",
  "url_checkout": "http://localhost:3004/checkout/pay-998877",
  "metodo": "formulario",
  "fecha_creacion": "2026-11-04T03:00:00Z",
  "fecha_expiracion": "2026-11-04T03:15:00Z"
}
```

