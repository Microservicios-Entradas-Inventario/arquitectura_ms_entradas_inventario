# Declaración de Integraciones – Entradas e Inventario (Evaluación 2: Interoperabilidad)

## Integraciones principales declaradas para evaluación

De acuerdo con la especificación de la Evaluación 2 (mínimo 2 integraciones de **tipos distintos**), el módulo **Entradas e Inventario** declara las siguientes **dos integraciones** para evaluación con **Check-in** y **Catálogo de Eventos**:

| Integración | Tipo (A, B o C) | Módulo contraparte | Servicio, endpoint o tópico | Contrato (ruta en el repo) | Ítem en GitHub |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **I1** | **A** (Servicio consumido) | **Check-in** (`checkin-service`) | `POST /api/checkin/tickets` (vía API Gateway `http://ticketu-api-gateway:8080/api/checkin/tickets`) | [`docs/contratos/contrato-http-checkin.md`](docs/contratos/contrato-http-checkin.md) | [Issue #19](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/19) |
| **I2** | **B** (Servicio ofrecido) | **Catálogo de Eventos** (`ms-catalogo-eventos`) | `GET /api/entradas/eventos/{id_evento}/disponibilidad` y `POST /api/entradas/procesar-compra` (expuestos vía API Gateway `:8080`) | [`docs/contratos/openapi.json`](docs/contratos/openapi.json) / [`docs/contratos/contrato-http-catalogo.md`](docs/contratos/contrato-http-catalogo.md) | [Issue #25](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/25) |

---

## Otras integraciones implementadas en el ecosistema (referencia)

| Integración | Tipo | Módulo contraparte | Servicio, endpoint o tópico | Contrato (ruta en el repo) | Ítem en GitHub |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **R1** | A (Servicio consumido) | Catálogo de Eventos | `PUT /api/v1/catalogo/eventos/{id_evento}/stock` (vía Gateway) | [`docs/contratos/contrato-http-catalogo.md`](docs/contratos/contrato-http-catalogo.md) | [Issue #24](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/24) |
| **R2** | B (Servicio ofrecido) | Check-in | `GET /api/entradas/{id_ticket}` y `/api/v1/entradas/{id_ticket}/detalle` | [`docs/contratos/openapi.json`](docs/contratos/openapi.json) | [Issue #20](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/20) |
| **R3** | C (Mensajería Broker) | Panel Organizador | Exchange `ticketu.events` (`panel.evento.entradas.v1` / `entradas.evento.stock.v1`) | [`docs/contratos/contrato-mensajeria-panel.md`](docs/contratos/contrato-mensajeria-panel.md) | [Issue #17](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/17) |
| **R4** | B (Servicio ofrecido) | Panel Organizador | `GET /api/entradas/eventos/{id_evento}/stock` | [`docs/contratos/openapi.json`](docs/contratos/openapi.json) | [Issue #18](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/18) |
| **R5** | C (Autenticación) | Auth (`auth-service`) | `GET /internal/validar-sesion` (`Cookie: jwt` + `x-api-key`) | [`docs/contratos/contrato-http-auth.md`](docs/contratos/contrato-http-auth.md) | [Issue #21](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/21) |
| **R6** | A / B | Pasarela de Pagos | `POST /api/v1/pagos/transacciones` y `GET /api/v1/entradas/reservas/{id_reserva}` | [`docs/contratos/contrato-http-pagos.md`](docs/contratos/contrato-http-pagos.md) | [Issue #22](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/22) / [Issue #23](https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario/issues/23) |
