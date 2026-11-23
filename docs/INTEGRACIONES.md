# Declaración de Integraciones – Entradas e Inventario

> Documento espejo de [`INTEGRACIONES.md`](../INTEGRACIONES.md) para mantener consistencia en `docs/`.

| Código | Contraparte | Rol de Entradas | Canal | Servicio, endpoint o tópico |
| :--- | :--- | :--- | :--- | :--- |
| **I1** | **Auth** (`auth-service`) | Consumidor (BE2) | HTTP interno | `GET /internal/validar-sesion` (`Cookie: jwt` + `x-api-key`) |
| **I2** | **Pasarela de Pagos** (`pagos-service`) | Consumidor (BE2) y Proveedor (BE3) | API Gateway + RabbitMQ | Provisto: `GET /api/entradas/reservas/{id_reserva}`<br>Consumido: `POST /api/pagos/transacciones`, `GET /api/pagos/{id_pago}`, `POST /api/pagos/{id_pago}/reembolso`<br>Broker: `pago.realizado`, `pago.rechazado`, `pago.anulado`, `pago.reembolsado` |
| **I3** | **Check-in** (`checkin-service`) | Consumidor (BE2) y Proveedor (BE3) | API Gateway | Consumido: `POST /api/checkin/tickets`<br>Provisto: `GET /api/entradas/{id_ticket}`, `GET /api/entradas/{id_ticket}/detalle`, `GET /api/entradas/{id_ticket}/qr` |
| **I4** | **Catálogo de Eventos** (`ms-catalogo-eventos`) | Consumidor (BE2) y Proveedor (BE3) | API Gateway | Consumido: `PUT /api/catalogo/eventos/{id_evento}/stock`<br>Provisto: `POST /api/entradas/procesar-compra`, `GET /api/entradas/eventos/{id_evento}/disponibilidad` |
| **I5** | **Panel Organizador** (`organizador-service`) | Consumidor (BE2) y Proveedor (BE3) | RabbitMQ + API Gateway | Broker consumido: `panel.evento.entradas.v1`, `panel.#`, `evento.*`<br>Broker publicado: `entradas.evento.stock.v1`, `stock.agotado`<br>Provisto: `GET /api/entradas/eventos/{id_evento}/stock` |
| **I6** | **Notificaciones** (`notificaciones-service`) | Proveedor de eventos (BE3) | RabbitMQ | Exchange `entradas.events` · Routing key `entradas_emitidas` |
| **I7** | **Promociones** (`promociones-service`) | Consumidor (BE2) | API Gateway | `POST /api/promociones/evaluar` |
