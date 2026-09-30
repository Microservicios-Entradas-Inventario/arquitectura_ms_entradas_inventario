# 📄 Directorio de Contratos de Interfaz — Endpoints que Proveemos (Endpoints que Damos)

Este directorio centraliza las especificaciones técnicas formales y contratos de interfaz en formato **PDF** donde el microservicio de **Entradas e Inventario** actúa como **Proveedor (Provider / Publisher)** de servicios y datos para los demás módulos del ecosistema **TicketU**.

El propósito de estos contratos es definir la API pública y privada que nuestro microservicio expone, formalizar las estructuras de datos (Request / Response / Eventos emitidos), garantizar la idempotencia de las operaciones, cumplir con los SLAs pactados y asegurar el desacoplamiento entre equipos.

---

## 📌 Protocolos y Mecanismos de Exposición

Las interfaces provistas por Entradas e Inventario se clasifican en dos modalidades de arquitectura:

1. **Síncrono (HTTP REST con FastAPI):** Endpoints RESTful para consultas directas y transacciones que requieren confirmación atómica e inmediata (ej. solicitud de compra y reserva desde Catálogo, lectura de QR desde Check-in, consulta de aforo para Panel Organizador y verificación de reserva para Pagos).
2. **Asíncrono (Broker RabbitMQ):** Emisión y publicación de eventos de dominio hacia colas/tópicos dedicados para desacoplar flujos secundarios o notificar eventos críticos de negocio (ej. despacho de entradas emitidas para envío de correo en Notificaciones y alerta de stock en cero para Panel Organizador).

---

## 📑 Tabla Resumen de Contratos (Archivos PDF)

| Microservicio Consumidor | Archivo de Contrato (PDF) | Versión | Tipo / Protocolo | Endpoint / Tópico Expuesto | SLA |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Catálogo de Eventos** | [`Contrato_Proveedor_Catalogo_Entradas_v2.pdf`](./Contrato_Proveedor_Catalogo_Entradas_v2.pdf) | v2.0 | REST (POST) | `POST /api/v1/entradas/procesar-compra` | < 300 ms (bilateral < 500 ms) |
| **Check-in** | [`Contrato_Proveedor_Interfaz_Inventario_Check-in.pdf`](./Contrato_Proveedor_Interfaz_Inventario_Check-in.pdf) | v1.1 | REST (GET) | `GET /api/v1/entradas/{id_ticket}` | Rápido / Flujo continuo en puerta |
| **Panel Organizador** | [`Contrato_Entradas_Panel_Unificado_v3.pdf`](./Contrato_Entradas_Panel_Unificado_v3.pdf) | v3.0 | Híbrido (REST + RabbitMQ) | `GET /api/v1/entradas/eventos/{id_evento}/stock`<br>Tópico emitido: `entradas.evento.stock.v1` | < 300 ms (REST) |
| **Notificaciones** | [`Contrato Notificaciones Entradas.pdf`](./Contrato%20Notificaciones%20Entradas.pdf) | v1.1 | Eventos (RabbitMQ) | Evento publicado: `entradas_emitidas` | < 200 ms (encolamiento) |
| **Pasarela de Pagos** | [`Contrato_Proveedor_Entradas_Pagos_v2.1.pdf`](./Contrato_Proveedor_Entradas_Pagos_v2.1.pdf) | v2.1 | REST (GET / Verificación) | `GET /api/v1/entradas/reservas/{id_reserva}` | < 500 ms |

---

## 📂 Detalle de Especificaciones por Integración

### 1. 🎪 Catálogo de Eventos — Procesamiento de Compra y Reserva
* **Documento:** [`Contrato_Proveedor_Catalogo_Entradas_v2.pdf`](./Contrato_Proveedor_Catalogo_Entradas_v2.pdf)
* **Roles:** Entradas / Inventario (Proveedor) ➔ Catálogo de Eventos (Consumidor)
* **Endpoint expuesto:** `POST /api/v1/entradas/procesar-compra`
* **Propósito:** Iniciar la reserva y el flujo de compra cuando un usuario confirma en el Catálogo la cantidad y el tipo de entrada que desea adquirir. Entradas valida la disponibilidad, descuenta temporalmente el cupo y retorna el stock restante.
* **SLA Acordado:** < 300 ms (con límite de corte bilateral menor a 500 ms).

#### Request (Cuerpo JSON enviado por Catálogo)
| Campo | Tipo | Obligatorio | Descripción |
| :--- | :--- | :---: | :--- |
| `id_evento` | `string` | Sí | Identificador único del evento seleccionado. |
| `tipo_entrada` | `string` | Sí | Modalidad de entrada (ej. `"General"`, `"VIP"`). |
| `cantidad` | `integer` | Sí | Número de entradas a comprar/reservar. |
| `token_sesion` | `string` | Sí | JWT de autenticación del usuario en sesión. |

```json
{
  "id_evento": "evt-101",
  "tipo_entrada": "General",
  "cantidad": 2,
  "token_sesion": "tok-999"
}
```

#### Response (200 OK emitido por Entradas)
| Campo | Tipo | Obligatorio | Descripción |
| :--- | :--- | :---: | :--- |
| `nuevo_stock` | `integer` | Sí | Cantidad de entradas que quedan disponibles tras procesar la orden. |

```json
{
  "nuevo_stock": 148
}
```

#### Códigos de Error
| Código | Causa / Significado |
| :---: | :--- |
| `400` | Parámetros inválidos o ausentes (ej. `cantidad <= 0`). |
| `401` | Token de sesión no válido, ausente o expirado. |
| `404` | El evento o el tipo de entrada solicitado no existe en el inventario. |
| `500` | Error interno del servicio de Entradas / Inventario. |

---

### 2. 🎟️ Check-in — Consulta de Información de Entrada por QR
* **Documento:** [`Contrato_Proveedor_Interfaz_Inventario_Check-in.pdf`](./Contrato_Proveedor_Interfaz_Inventario_Check-in.pdf)
* **Roles:** Entradas / Inventario (Proveedor) ➔ Check-in (Consumidor)
* **Endpoint expuesto:** `GET /api/v1/entradas/{id_ticket}`
* **Propósito:** Proveer a Check-in los datos de usuario y validez asociados a un ticket luego de que el staff escanea el código QR en los accesos del evento. Check-in no accede directamente a la base de datos de Entradas; únicamente consume esta API para validar el ingreso.
* **SLA Acordado:** Compatible con tiempo real en portería para evitar congestión y filas en el acceso.

#### Request (Parámetro de Ruta)
| Parámetro | Tipo | Ubicación | Descripción |
| :--- | :--- | :---: | :--- |
| `id_ticket` | `string` | Path | Identificador único del ticket obtenido a partir de la lectura del QR (ej. `tk-998877`). |

#### Response (200 OK emitido por Entradas)
| Campo | Tipo | Obligatorio | Descripción |
| :--- | :--- | :---: | :--- |
| `id_ticket` | `string` | Sí | Identificador único de la entrada. |
| `nombre_usuario` | `string` | Sí | Nombre del comprador/asistente asociado a la entrada. |
| `usuario` | `object` | Sí | Objeto con la información del usuario titular. |
| `usuario.id_usuario` | `string` | Sí | Identificador único del usuario. |
| `usuario.rol_usuario` | `string` | Sí | Rol del usuario (`"cliente"`, etc.). |

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

#### Códigos de Error
| Código | Causa / Significado |
| :---: | :--- |
| `400` | Solicitud incompleta o `id_ticket` con formato inválido. |
| `404` | La entrada asociada al `id_ticket` no existe. |
| `500` | Error interno del servicio de Entradas / Inventario. |
| `503` | Servicio de Entradas temporalmente no disponible. |

---

### 3. 📊 Panel Organizador — Consulta de Stock y Notificación de Agotado
* **Documento:** [`Contrato_Entradas_Panel_Unificado_v3.pdf`](./Contrato_Entradas_Panel_Unificado_v3.pdf)
* **Roles:** Integración Híbrida Unificada (Entradas como Proveedor de Stock)
* **Mecanismo:**

#### A. Endpoint Síncrono (Consulta de Stock):
* **Endpoint expuesto:** `GET /api/v1/entradas/eventos/{id_evento}/stock`
* **Propósito:** Permitir que el Panel Organizador audite el aforo disponible o verifique si un evento puede ser eliminado de forma segura (únicamente permitido si `stock == cantidad_entradas` inicial, es decir, sin tickets vendidos).
* **SLA Acordado:** < 300 ms.
* **Response (200 OK):**
```json
{
  "id_evento": "evt-001",
  "stock": 37
}
```

#### B. Evento Asíncrono (Publicación de Evento Agotado vía RabbitMQ):
* **Tópico de publicación:** `entradas.evento.stock.v1`
* **Regla de negocio:** Entradas/Inventario es el dueño exclusivo del stock. En el instante en que el aforo llega exactamente a `0`, publica proactivamente este mensaje para que el Panel (y demás componentes) actualicen su vista a **AGOTADO** automáticamente sin requerir sondeo constante.
* **Payload emitido:**
```json
{
  "id_evento": "evt-001",
  "stock": 0
}
```

---

### 4. 📬 Notificaciones — Emisión de Entradas y Envío por Correo
* **Documento:** [`Contrato Notificaciones Entradas.pdf`](./Contrato%20Notificaciones%20Entradas.pdf)
* **Roles:** Entradas (Proveedor del Evento de Dominio) ➔ Notificaciones (Consumidor)
* **Canal / Evento RabbitMQ:** `entradas_emitidas`
* **Propósito:** Transmitir a Notificaciones todos los datos del comprador, evento y código QR una vez que el ticket ha sido emitido de manera definitiva (post-pago aprobado), para que Notificaciones ensamble el correo con el ticket adjunto.
* **SLA de Encolamiento:** < 200 ms.

#### Payload Emitido por Entradas (`entradas_emitidas`)
| Campo | Tipo | Obligatorio | Descripción |
| :--- | :--- | :---: | :--- |
| `correo_comprador` | `string` | Sí | Correo electrónico validado del cliente destinatario. |
| `nombre_comprador` | `string` | Sí | Nombre completo del comprador. |
| `nombre_evento` | `string` | Sí | Nombre oficial del evento. |
| `fecha_evento` | `string` | Sí | Fecha del evento (`YYYY-MM-DD`). |
| `hora_evento` | `string` | Sí | Hora de inicio (`HH:MM`). |
| `qr_data` | `string` | Sí | URL pública del archivo QR o cadena Base64 para renderizado. |

```json
{
  "correo_comprador": "a@gmail.com",
  "nombre_comprador": "Gabriela",
  "nombre_evento": "Fiesta",
  "fecha_evento": "2026-11-20",
  "hora_evento": "22:00",
  "qr_data": "https://storage.ticketu.cl/qr/tk-12345.png"
}
```

#### Respuesta esperada del consumidor (Notificaciones)
* Confirma recepción y encolamiento (`{ "estado": "programado", "mensaje": "El envío del correo fue exitoso" }`).
* Notificaciones asume la política de resiliencia ejecutando **hasta 3 reintentos automáticos** en caso de falla con el servidor SMTP.

---

### 5. 💳 Pasarela de Pagos — Verificación de Reserva y Orden
* **Documento:** [`Contrato_Proveedor_Entradas_Pagos_v2.1.pdf`](./Contrato_Proveedor_Entradas_Pagos_v2.1.pdf)
* **Roles:** Entradas / Inventario (Proveedor de Verificación) ➔ Pagos (Consumidor)
* **Endpoint expuesto:** `GET /api/v1/entradas/reservas/{id_reserva}` (Referencia técnica INT-01 / #29)
* **Propósito:** Pagos requiere verificar de forma síncrona contra Entradas la existencia, validez, monto total y cantidad de tickets de la reserva antes de confirmar una transacción o procesar un pago pendiente.
* **SLA Acordado:** < 500 ms (tiempo de corte estricto configurado en el cliente de Pagos).

#### Request
* `GET /api/v1/entradas/reservas/res-98765`
* Cabecera: `Authorization: Bearer <JWT con rol SERVICIO>`

#### Response esperada (200 OK)
```json
{
  "id_reserva": "res-98765",
  "id_evento": "evt-101",
  "cantidad_entradas": 2,
  "total": 15000,
  "estado": "RESERVADA",
  "expiracion_reserva": "2026-09-30T19:55:00.000Z"
}
```

---

## 🛡️ Seguridad, Autenticación y Gobernanza

1. **Autenticación entre Servicios:**
   * Las peticiones REST internas deben incluir cabeceras de autorización `Authorization: Bearer <token>` o cookies firmadas por el microservicio de **Auth**, validando que el servicio o usuario posea los permisos necesarios (`CLIENTE`, `ORGANIZADOR` o `SERVICIO`).
2. **Idempotencia:**
   * En operaciones de reserva o compra, el identificador `id_reserva` se utiliza como llave única de idempotencia para evitar duplicación de retenciones de cupo ante reintentos de red.
3. **Manejo Estandarizado de Errores:**
   * Los errores HTTP se devuelven en formato estructurado:
     ```json
     {
       "error": "CODIGO_ERROR",
       "mensaje": "Descripción legible de la causa",
       "detalles": []
     }
     ```
4. **Política de Versionamiento:**
   * Cualquier modificación en rutas, esquemas o campos requiere consenso bilateral con el equipo consumidor y actualización del número de versión en la ruta (`/api/v1` ➔ `/api/v2`) y en el contrato formal PDF.
