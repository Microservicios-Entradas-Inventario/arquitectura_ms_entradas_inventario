# Contrato de Mensajería Asíncrona: Entradas e Inventario ↔ Panel Organizador

**Módulos:** Entradas e Inventario (`entradas-service`) ↔ Panel Organizador (`organizador-service`)  
**Broker de Eventos:** RabbitMQ (`ticketu-rabbitmq:5672`, vhost `/ticketu`)  
**Implementación en código:** [`back-end/services/broker_service.py`](../../back-end/services/broker_service.py)  

---

## 1. Configuración del Broker, Exchange y Cola

| Parámetro | Valor Configurado | Descripción |
| :--- | :--- | :--- |
| **Broker URL (Docker)** | `amqp://ticketu:ticketu_dev@ticketu-rabbitmq:5672/ticketu` | Instancia compartida en la red `plataforma-eventos-net` |
| **Exchange** | `ticketu.events` | Exchange compartido de tipo **`topic`** (`durable: true`) |
| **Cola en Entradas** | `entradas.pagos` | Cola propia de `entradas-service` (`durable: true`) |
| **Formato de Mensaje** | `application/json` (UTF-8) | Persistencia en disco (`delivery_mode = PERSISTENT`) |

---

## 2. Routing Keys (Tópicos)

### 2.1. Tópicos Consumidos por `entradas-service` (Bindings en cola `entradas.pagos`)

| Routing Key | Emisor | Propósito en `entradas-service` |
| :--- | :--- | :--- |
| `panel.evento.entradas.v1` | `organizador-service` | Sincronizar la creación, publicación, actualización de aforo/precio o cancelación de un evento en la colección `inventario_evento`. |
| `panel.#` | `organizador-service` | Comodín para eventos de ciclo de vida emitidos desde el Outbox del Panel Organizador. |
| `evento.*` | `organizador-service` | Soporte compatible para eventos `evento_creado`, `evento_publicado` y `evento_actualizado`. |
| `pago.*` | `pagos-service` | Consolidación (`pago.realizado`) o liberación de reserva (`pago.rechazado`). |

### 2.2. Tópicos Publicados por `entradas-service` (Hacia `ticketu.events`)

| Routing Key | Consumidor(es) | Condición de Disparo |
| :--- | :--- | :--- |
| `entradas.evento.stock.v1` | `organizador-service` | Se emite automáticamente cuando `stock_actual` de un evento llega a `0` tras una compra o reserva. |
| `stock.agotado` | `organizador-service` | Alias estándar del ecosistema emitido en paralelo cuando el stock llega a `0`. |
| `entrada.reservada` | Ecosistema TicketU | Se emite al crear una reserva temporal (Hold) en `POST /api/entradas/reservas/hold`. |
| `entrada.emitida` | `checkin-service` / `notificaciones` | Se emite al consolidar y generar un ticket definitivo con código QR. |

---

## 3. Esquema JSON del Payload Enviado por Panel Organizador (Consumido por Entradas)

Cuando el Panel Organizador crea, publica, edita o cancela un evento, publica un mensaje en el exchange `ticketu.events` con la routing key `panel.evento.entradas.v1` (o `panel.*` / `evento.*`).

### 3.1. Estructura del Mensaje (JSON Schema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EventoPanelOrganizadorMessage",
  "type": "object",
  "required": ["payload"],
  "properties": {
    "envelope": {
      "type": "object",
      "properties": {
        "id_mensaje": { "type": "string", "format": "uuid" },
        "tipo": {
          "type": "string",
          "enum": ["evento_creado", "evento_publicado", "evento_actualizado", "evento_cancelado"]
        },
        "id_evento": { "type": "string", "minLength": 1 },
        "timestamp": { "type": "string", "format": "date-time" }
      }
    },
    "payload": {
      "type": "object",
      "required": ["id_evento", "cantidad_entradas"],
      "properties": {
        "id_evento": {
          "type": "string",
          "minLength": 1,
          "description": "Identificador único del evento en el ecosistema TicketU."
        },
        "id_usuario": {
          "type": "string",
          "default": "org-panel",
          "description": "ID del usuario con rol ORGANIZADOR dueño del evento."
        },
        "cantidad_entradas": {
          "type": "integer",
          "minimum": 0,
          "description": "Aforo / stock total asignado al evento."
        },
        "precio": {
          "type": "integer",
          "minimum": 0,
          "default": 0,
          "description": "Precio unitario de la entrada en CLP."
        },
        "tipo_entrada": {
          "type": "string",
          "enum": ["PAGADA", "GRATUITA"],
          "default": "PAGADA"
        },
        "estado_gestion": {
          "type": "string",
          "enum": ["BORRADOR", "PUBLICADO", "FINALIZADO", "CANCELADO", "AGOTADO"],
          "default": "PUBLICADO"
        }
      }
    }
  }
}
```

### 3.2. Ejemplo de Payload Recibido desde Panel Organizador

```json
{
  "envelope": {
    "id_mensaje": "6f9c2b10-91a4-4c55-8e11-32908a41b001",
    "tipo": "evento_publicado",
    "id_evento": "evt-77889",
    "timestamp": "2026-11-03T22:15:00Z"
  },
  "payload": {
    "id_evento": "evt-77889",
    "id_usuario": "usr-org-001",
    "cantidad_entradas": 150,
    "precio": 10000,
    "tipo_entrada": "PAGADA",
    "estado_gestion": "PUBLICADO"
  }
}
```

### 3.3. Acción de Negocio en `entradas-service`
1. Verifica si `id_evento` ya existe en la colección `inventario_evento` de MongoDB.
2. **Operación Idempotente (Upsert):**
   * Si el evento **no existe**, inserta el documento inicializando `stock_inicial = cantidad_entradas`, `stock_actual = cantidad_entradas`, `cantidad_entrada_reservada = 0` y `cantidad_entrada_comprada = 0`.
   * Si el evento **ya existe**, actualiza `stock_actual`, `stock_inicial`, `tipo_entrada`, `estado_gestion` y `fecha_actualizacion`.

---

## 4. Esquema JSON del Payload Emitido por Entradas hacia Panel Organizador

Cuando una compra o reserva en [`routers/entradas.py`](../../back-end/routers/entradas.py) deja `nuevo_stock == 0`, `entradas-service` publica en `ticketu.events` con las routing keys `entradas.evento.stock.v1` y `stock.agotado`.

### 4.1. Estructura del Sobre Estándar Emitido (JSON Schema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "StockAgotadoEventEnvelope",
  "type": "object",
  "required": ["eventId", "eventName", "occurredAt", "source", "data"],
  "properties": {
    "eventId": {
      "type": "string",
      "format": "uuid",
      "description": "UUID v4 único del evento emitido."
    },
    "eventName": {
      "type": "string",
      "enum": ["entradas.evento.stock.v1", "stock.agotado"]
    },
    "occurredAt": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp UTC en formato ISO 8601."
    },
    "source": {
      "type": "string",
      "const": "entradas-service"
    },
    "data": {
      "type": "object",
      "required": ["id_evento", "stock"],
      "properties": {
        "id_evento": {
          "type": "string",
          "description": "Identificador único del evento que agotó su stock."
        },
        "stock": {
          "type": "integer",
          "const": 0,
          "description": "Stock restante (0 indica agotado)."
        }
      }
    }
  }
}
```

### 4.2. Ejemplo de Payload Emitido por `entradas-service`

```json
{
  "eventId": "d3f1a8c2-48b9-4e1a-9f22-8c7b6a5d4e3f",
  "eventName": "entradas.evento.stock.v1",
  "occurredAt": "2026-11-04T03:00:00.000000",
  "source": "entradas-service",
  "data": {
    "id_evento": "evt-77889",
    "stock": 0
  }
}
```

---

## 5. Manejo de Mensajes Inválidos, Errores y Resiliencia

El consumidor en [`BrokerService._consume`](../../back-end/services/broker_service.py) implementa las siguientes garantías para evitar bloqueos de cola (*Poison Messages*) o corrupción de inventario:

1. **Descarte sin Reencolamiento Infinito (`requeue=False`):**
   * Cada mensaje entrante se procesa dentro del bloque `async with message.process(requeue=False):`.
   * Si el cuerpo del mensaje no es un JSON válido (`json.JSONDecodeError`) o presenta una estructura corrupta, se captura la excepción, se registra en el log (`[RabbitMQ] Error procesando mensaje (...)`) y se envía `NACK/ACK` con `requeue=False` para evitar que un mensaje malformado bloquee permanentemente la cola `entradas.pagos`.
2. **Validación de Campos Obligatorios (`id_evento`):**
   * Si un mensaje de `panel.*` no contiene `id_evento` ni en `payload.id_evento` ni en `envelope.id_evento`, el manejador `_handle_event` ignora la operación sin modificar la base de datos.
3. **Normalización y Sanitización de Enumeraciones:**
   * Si `estado_gestion` contiene un valor fuera del dominio permitido (`BORRADOR`, `PUBLICADO`, `FINALIZADO`, `CANCELADO`, `AGOTADO`), se normaliza automáticamente a `"PUBLICADO"` para respetar el validador `$jsonSchema` de MongoDB.
   * Si `tipo_entrada` contiene un valor fuera de `["PAGADA", "GRATUITA"]`, se normaliza a `"PAGADA"`.
4. **Reconexión Robusta y Degradación Elegante (*Graceful Degradation*):**
   * Se utiliza `aio_pika.connect_robust(BROKER_URL, timeout=3.0)` para reconectar automáticamente si el contenedor `ticketu-rabbitmq` se reinicia.
   * Si el broker no se encuentra disponible, el microservicio registra la advertencia en consola y continúa operando normalmente en sus endpoints HTTP REST (`/api/entradas/inventario`, `/api/entradas/eventos/{id_evento}/stock`).

