# Declaración de Integraciones – Entradas e Inventario

| Integración | Tipo (A, B o C) | Módulo contraparte | Servicio, endpoint o tópico | Contrato (ruta en el repo) | Ítem en GitHub |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **I1** | **C** (Mensajería por Broker) | Panel Organizador | Exchange: `ticketu.events`<br>Tópicos: `panel.evento.entradas.v1` / `evento.*` (consumido en cola `entradas.pagos`) y `entradas.evento.stock.v1` / `stock.agotado` (publicado) | [`Contratos (endpoints que consumimos)/Contrato_Entradas_Panel_Unificado_v3.pdf`](../Contratos%20(endpoints%20que%20consumimos)/Contrato_Entradas_Panel_Unificado_v3.pdf) | PR #13 / #15 ([Repositorio GitHub](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/pulls)) |
| **I2** | **B** (Servicio ofrecido) | Panel Organizador | `GET /api/entradas/eventos/{id_evento}/stock` (y `/api/v1/entradas/eventos/{id_evento}/stock`) | [`Contratos (endpoints que damos)/Contrato_Entradas_Panel_Unificado_v3.pdf`](../Contratos%20(endpoints%20que%20damos)/Contrato_Entradas_Panel_Unificado_v3.pdf) | PR #13 / #15 ([Repositorio GitHub](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/pulls)) |

