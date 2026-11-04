# Declaración de Integraciones – Entradas e Inventario

| Integración | Tipo (A, B o C) | Módulo contraparte | Servicio, endpoint o tópico | Contrato (ruta en el repo) | Ítem en GitHub |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **I1** | **C** (Mensajería por Broker) | Panel Organizador | Exchange: `ticketu.events`<br>Tópicos: `panel.evento.entradas.v1` (consumido en cola `entradas.pagos`) y `entradas.evento.stock.v1` / `stock.agotado` (publicado) | [`docs/contratos/contrato-mensajeria-panel.md`](contratos/contrato-mensajeria-panel.md) | PR #13 / #15 ([Repositorio GitHub](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/pulls)) |
| **I2** | **B** (Servicio ofrecido) | Panel Organizador | `GET /api/entradas/eventos/{id_evento}/stock` (y `/api/v1/entradas/eventos/{id_evento}/stock`) | [`docs/contratos/openapi.json`](contratos/openapi.json) | PR #13 / #15 ([Repositorio GitHub](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/pulls)) |
