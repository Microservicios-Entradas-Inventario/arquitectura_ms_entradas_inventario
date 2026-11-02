# 📄 Directorio de Contratos de Interfaz — Endpoints que Consumimos

Este directorio centraliza las definiciones formales y especificaciones técnicas (contratos de API) en formato **PDF** que rigen cómo el microservicio de **Entradas e Inventario** se integra como **consumidor** (y en flujos bidireccionales) con los demás módulos del ecosistema **TicketU**.

El propósito de estos contratos es garantizar la interoperabilidad sin acoplamiento, definir responsabilidades contractuales, acordar tiempos de respuesta (SLAs) y estandarizar las estructuras de datos (Request / Response / Eventos).

---

## 📌 Protocolos de Comunicación

Las integraciones de Entradas e Inventario operan bajo una arquitectura híbrida:

1. **Síncrono (HTTP REST):** Operaciones atómicas que requieren respuesta inmediata para validar reglas de negocio antes de proceder (ej. validación de sesión de usuario, consulta de descuentos o actualización de aforo).
2. **Asíncrono (Broker RabbitMQ):** Eventos no bloqueantes para desacoplar procesos prolongados o notificaciones en segundo plano (ej. resolución de pagos bancarios, sincronización de ciclo de vida del evento y envío de correos).

---

## 📑 Tabla Resumen de Contratos (Archivos PDF)

| Microservicio Proveedor | Archivo de Contrato (PDF) | Versión | Tipo / Protocolo | Endpoint / Canal | SLA |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Autenticación (Auth)** | [`Contrato_Entradas_Auth_v3_Introspeccion (1).pdf`](./Contrato_Entradas_Auth_v3_Introspeccion%20(1).pdf) | v3.0 | REST (GET) | `/internal/validar-sesion` | < 100 ms |
| **Catálogo de Eventos** | [`Contrato_Entradas_Catalogo_v4.pdf`](./Contrato_Entradas_Catalogo_v4.pdf) | v4.0 | REST (PUT) | `/api/v1/catalogo/eventos/{id_evento}/stock` | < 200 ms |
| **Pasarela de Pagos** | [`Contrato_Entradas_Pagos_v2_Asincrono.pdf`](./Contrato_Entradas_Pagos_v2_Asincrono.pdf) | v2.0 | Híbrido (REST + RabbitMQ) | `POST /api/v1/pagos/transacciones`<br>Eventos: `PagoAprobado` / `PagoRechazado` | < 2000 ms (REST) |
| **Promociones** | [`Contrato_Consumidor_Entradas_Promociones.pdf`](./Contrato_Consumidor_Entradas_Promociones.pdf) | v1.0 | REST (POST) | `/promociones/validar/{nombre_codigo}` | < 200 ms |
| **Check-in** | [`Contrato_Entradas_Checkin.pdf`](./Contrato_Entradas_Checkin.pdf) | v1.0 | REST (POST) | `/api/v1/checkin/tickets` | < 500 ms |
| **Panel Organizador** | [`Contrato_Entradas_Panel_Unificado_v3.pdf`](./Contrato_Entradas_Panel_Unificado_v3.pdf) | v3.0 | Bidireccional (REST + RabbitMQ) | `GET /api/v1/panel/eventos/{id_evento}` (Fallback REST)<br>Tópicos: `panel.evento.entradas.v1` / `entradas.evento.stock.v1` | < 300 ms (REST) |
| **Notificaciones** | [`Contrato Notificaciones Entradas.pdf`](./Contrato%20Notificaciones%20Entradas.pdf) | v1.1 | Eventos (RabbitMQ) | Evento: `entradas_emitidas` | < 200 ms (Encolado) |

---

## 📂 Detalle de Especificaciones por Integración

### 1. 🔐 Autenticación (Auth) — Introspección Centralizada
* **Documento:** [`Contrato_Entradas_Auth_v3_Introspeccion (1).pdf`](./Contrato_Entradas_Auth_v3_Introspeccion%20(1).pdf)
* **Roles:** Entradas / Inventario (Consumidor) ➔ Auth (Proveedor)
* **Endpoint:** `GET /internal/validar-sesion` (Red interna, cabecera `Cookie: jwt=<token>`)
* **Propósito:** Validar la firma, vigencia y rol del usuario (`CLIENTE` o `ORGANIZADOR`) antes de autorizar reservas o compras de tickets, asegurando que un token revocado sea rechazado inmediatamente.
* **SLA Acordado:** < 100 ms.

---

### 2. 🎪 Catálogo de Eventos — Sincronización de Stock
* **Documento:** [`Contrato_Entradas_Catalogo_v4.pdf`](./Contrato_Entradas_Catalogo_v4.pdf)
* **Roles:** Entradas / Inventario (Consumidor) ➔ Catálogo (Proveedor)
* **Endpoint:** `PUT /api/v1/catalogo/eventos/{id_evento}/stock`
* **Propósito:** Informar de forma determinista el stock actualizado del evento luego de concretar una compra o reserva. Retorna `204 No Content`.
* **Acuerdo Técnico:** Se acordó utilizar el verbo estricto **PUT** sobre HTTP REST (descartando PATCH y broker para este flujo directo).
* **SLA Acordado:** < 200 ms.

---

### 3. 💳 Pasarela de Pagos — Flujo Asíncrono
* **Documento:** [`Contrato_Entradas_Pagos_v2_Asincrono.pdf`](./Contrato_Entradas_Pagos_v2_Asincrono.pdf)
* **Roles:** Entradas / Inventario (Consumidor) ➔ Pagos (Proveedor)
* **Mecanismo:**
  * **Inicio del cobro (REST):** `POST /api/v1/pagos/transacciones` crea la orden y retorna inmediatamente el estado inicial `PENDIENTE`.
  * **Resolución bancaria (RabbitMQ):** Entradas escucha de forma reactiva los eventos `PagoAprobado` (para consolidar y emitir el ticket) o `PagoRechazado` (para liberar el cupo retenido).
  * **Polling de rescate (REST):** `GET /api/v1/pagos/{id_pago}` como fallback si se cumple el tiempo límite de reserva (15 minutos TTL).
* **SLA Acordado:** < 2000 ms para la invocación REST inicial.

---

### 4. 🏷️ Promociones — Validación de Cupones
* **Documento:** [`Contrato_Consumidor_Entradas_Promociones.pdf`](./Contrato_Consumidor_Entradas_Promociones.pdf)
* **Roles:** Entradas / Inventario (Consumidor) ➔ Promociones (Proveedor)
* **Endpoint:** `POST /promociones/validar/{nombre_codigo}`
* **Propósito:** Enviar los datos del evento, usuario y tipo de entrada para que Promociones valide vigencia, límites y retorne el porcentaje o monto de descuento aplicable antes de valorizar la orden en Pagos.
* **SLA Acordado:** < 200 ms.

---

### 5. 🎟️ Check-in — Registro de Entradas y QR
* **Documento:** [`Contrato_Entradas_Checkin.pdf`](./Contrato_Entradas_Checkin.pdf)
* **Roles:** Entradas / Inventario (Consumidor) ➔ Check-in (Proveedor)
* **Endpoint:** `POST /api/v1/checkin/tickets`
* **Propósito:** Enviar en paralelo el ticket emitido junto con su identificador único y URL/código QR (`qr_data`) para que Check-in lo persista en su base de datos local y habilite el escaneo rápido en los accesos del recinto.
* **SLA Acordado:** < 500 ms.

---

### 6. 📊 Panel Organizador — Acuerdo Unificado Bidireccional
* **Documento:** [`Contrato_Entradas_Panel_Unificado_v3.pdf`](./Contrato_Entradas_Panel_Unificado_v3.pdf)
* **Roles:** Integración Híbrida Bidireccional
* **Mecanismo:**
  * **RabbitMQ (Canal principal):** Entradas se suscribe al tópico `panel.evento.entradas.v1` para suspender ventas ante cancelación de evento, y publica en `entradas.evento.stock.v1` cuando el aforo llega a cero.
  * **REST (Fallback y validación):** Entradas consume `GET /api/v1/panel/eventos/{id_evento}` para rehidratar datos maestros, y Panel consulta `GET /api/v1/entradas/eventos/{id_evento}/stock` antes de permitir eliminar un evento.
* **SLA Acordado:** < 300 ms en operaciones REST.

---

### 7. 📬 Notificaciones — Despacho de Ticket por Correo
* **Documento:** [`Contrato Notificaciones Entradas.pdf`](./Contrato%20Notificaciones%20Entradas.pdf)
* **Roles:** Entradas (Proveedor de datos) ➔ Notificaciones (Consumidor/Despachador)
* **Mecanismo:** Evento asíncrono `entradas_emitidas`.
* **Propósito:** Transmitir los datos consolidados de la compra (`correo_comprador`, `nombre_comprador`, `nombre_evento`, `fecha_evento`, `hora_evento`, `qr_data`) para que Notificaciones ensamble el correo con el ticket y gestione la cola de envío con reintentos automáticos (hasta 3 intentos).
* **SLA Acordado:** < 200 ms para la recepción y encolamiento.

---

## 🛠️ Reglas de Versionado y Gobernanza
* Toda modificación en endpoints, esquemas JSON (BSON) o canales de mensajería **debe consensuarse y aprobarse bilateralmente** con el equipo contraparte.
* Cualquier cambio que rompa la compatibilidad (*breaking change*) exige un incremento mayor en la versión del contrato (ej. de `v2` a `v3`).
