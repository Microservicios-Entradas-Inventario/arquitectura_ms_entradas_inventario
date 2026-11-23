# Declaración de Integraciones – Entradas e Inventario (`entradas-service`)

Resumen unificado de las integraciones implementadas por el microservicio **Entradas e Inventario** en la red compartida `plataforma-eventos-net`.

---

## 1. Matriz de integraciones implementadas

| Código | Contraparte | Rol de Entradas | Canal / Protocolo | Endpoints o Tópicos | Implementación en código |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **I1** | **Auth** (`auth-service`) | Consumidor (BE2) | HTTP interno | `GET /internal/validar-sesion` (`Cookie: jwt` + `x-api-key`) | [`back-end/services/auth_service.py`](back-end/services/auth_service.py) |
| **I2** | **Pasarela de Pagos** (`pagos-service`) | Consumidor (BE2) y Proveedor (BE3) | API Gateway + RabbitMQ | Provisto: `GET /api/entradas/reservas/{id_reserva}` (`total`, `cantidad_entradas`, `nombre_codigo`)<br>Consumido HTTP: `POST /api/pagos/transacciones`, `GET /api/pagos/{id_pago}`, `POST /api/pagos/{id_pago}/reembolso`<br>Broker consumido (`ticketu.events`): `pago.realizado`, `pago.rechazado`, `pago.anulado`, `pago.reembolsado` | [`back-end/services/pagos_service.py`](back-end/services/pagos_service.py)<br>[`back-end/routers/reservas.py`](back-end/routers/reservas.py)<br>[`back-end/services/broker_service.py`](back-end/services/broker_service.py) |
| **I3** | **Check-in** (`checkin-service`) | Consumidor (BE2) y Proveedor (BE3) | API Gateway | Consumido: `POST /api/checkin/tickets` (`qr_data` JSON `{id_entrada, id_evento}`)<br>Provisto: `GET /api/entradas/{id_ticket}`, `GET /api/entradas/{id_ticket}/detalle`, `GET /api/entradas/{id_ticket}/qr` | [`back-end/services/checkin_service.py`](back-end/services/checkin_service.py)<br>[`back-end/routers/entradas.py`](back-end/routers/entradas.py) |
| **I4** | **Catálogo de Eventos** (`ms-catalogo-eventos`) | Consumidor (BE2) y Proveedor (BE3) | API Gateway | Consumido: `PUT /api/catalogo/eventos/{id_evento}/stock`<br>Provisto: `POST /api/entradas/procesar-compra`, `GET /api/entradas/eventos/{id_evento}/disponibilidad` | [`back-end/services/catalogo_service.py`](back-end/services/catalogo_service.py)<br>[`back-end/routers/entradas.py`](back-end/routers/entradas.py) |
| **I5** | **Panel Organizador** (`organizador-service`) | Consumidor (BE2) y Proveedor (BE3) | RabbitMQ + API Gateway | Broker consumido (`ticketu.events`): `panel.evento.entradas.v1`, `panel.#`, `evento.*`<br>Broker publicado (`ticketu.events`): `entradas.evento.stock.v1` y `stock.agotado`<br>Provisto HTTP: `GET /api/entradas/eventos/{id_evento}/stock`<br>Consumido HTTP: `GET /api/organizador/v1/organizador/eventos/proximos` y `/v1/panel/eventos/{id_evento}` | [`back-end/services/broker_service.py`](back-end/services/broker_service.py)<br>[`back-end/services/panel_service.py`](back-end/services/panel_service.py)<br>[`back-end/routers/entradas.py`](back-end/routers/entradas.py) |
| **I6** | **Notificaciones** (`notificaciones-service`) | Proveedor de eventos (BE3) | RabbitMQ | Exchange `entradas.events` (`topic`, durable) · Routing key `entradas_emitidas` | [`back-end/services/notificaciones_service.py`](back-end/services/notificaciones_service.py)<br>[`back-end/services/broker_service.py`](back-end/services/broker_service.py) |
| **I7** | **Promociones** (`promociones-service`) | Consumidor (BE2) | API Gateway | `POST /api/promociones/evaluar` (revalidación server-side de código promocional antes de fijar `monto_total`) | [`back-end/services/promociones_service.py`](back-end/services/promociones_service.py) |

---

## 2. Manejo de errores y resiliencia implementada

- **Auth (`AuthService`):** Política *fail-secure*; ante `401` rechaza con `401 NO_AUTENTICADO`, ante usuario inactivo responde `403 CUENTA_INACTIVA`, y ante timeout/error de red responde `503 AUTH_NO_DISPONIBLE` sin modificar stock ni crear reservas.
- **Pagos (`PagosService`):** Reenvía el header `Cookie` (`jwt`) sin exponer `client_secret` ni guardar cookies JWT en MongoDB; reintenta idempotentemente ante `503` y revierte stock local si Pagos rechaza la sesión.
- **Check-in (`CheckinService`):** Timeout configurable (`2.5s` por defecto), reintento seguro ante errores de red/5xx e idempotencia ante `409 TICKET_ALREADY_EXISTS`.
- **RabbitMQ (`BrokerService`):** Cola durable propia `entradas.pagos`, descarte controlado sin loop infinito (`requeue=False`), reconexión automática en segundo plano si el broker no está listo al iniciar el contenedor.
- **Promociones (`PromocionesService`):** Revalida siempre en servidor el porcentaje de descuento; si el servicio no responde o el código no es válido, aplica `0%` sin confiar en montos enviados por el cliente.
