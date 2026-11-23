# Guía de Ejecución de Pruebas de Calidad (CA1 y CA2)

## 1. Pruebas Funcionales Automatizadas (CA1 — Pytest)

La suite [`tests/test_funcionalidades.py`](./test_funcionalidades.py) valida de forma determinista el comportamiento real de los routers, esquemas, reglas de negocio y seguridad del microservicio **Entradas e Inventario**:

- **HU-01:** Consulta de inventario (`200`), evento inexistente (`404`), disponibilidad y stock para Panel.
- **HU-02:** Bloqueo sin sesión (`401`), rechazo de emisión directa para eventos pagados (`400`), emisión gratuita múltiple con descuento atómico de stock y registro en Check-in.
- **HU-03:** Bloqueo sin sesión (`401`), rechazo de eventos cancelados (`400`), creación de reserva temporal (Hold) con revalidación de cupón (`nombre_codigo`), verificación de que no se persisten cookies JWT en BD, contrato `GET /reservas/{id_reserva}` hacia Pagos, cancelación con devolución de stock, y bloqueo por defecto del webhook simulado (`403`).
- **HU-04 y HU-05:** Protección de `/mis-entradas` (`401`), historial inmutable con fecha/hora, generación de payload QR estructurado y consulta para Check-in.
- **Integración Broker y Pagos:** Procesamiento real de `pago.realizado` (emisión múltiple, limpieza de `fecha_expiracion` y registro en Check-in), reenvío de cookie `jwt` sin `Authorization: Bearer`, descarte de `client_secret` y reintento idempotente ante `503 AUTH_NO_DISPONIBLE`.

### Cómo ejecutar y regenerar el reporte HTML (`evidencia_QA_CA1.html`)

Con Python local (desde `back-end/`):
```bash
python -m pytest tests/test_funcionalidades.py -v --html=tests/evidencia_QA_CA1.html --self-contained-html
```

O directamente dentro del contenedor Docker en workstation:
```bash
docker exec entradas-service python -m pytest tests/test_funcionalidades.py -v --html=tests/evidencia_QA_CA1.html --self-contained-html
```

---

## 2. Pruebas de Integración en Workstation (CA2 — Postman / Newman)

La colección [`tests/TicketU - QA Integracion.postman_collection.json`](./TicketU%20-%20QA%20Integracion.postman_collection.json) se ejecuta contra el **API Gateway de workstation (`http://localhost:8080`)** y cubre casos exitosos y casos de error contra las contrapartes reales:

- **Auth:** Bloqueo sin cookie (`401`), rechazo con cookie `jwt` inválida/alterada (`401`), inicio de sesión comprador y `STAFF`.
- **Catálogo ↔ Entradas:** Consulta de disponibilidad, sincronización de stock al crear/cancelar Hold, agotamiento (`0`) y stock negativo (`400`).
- **Promociones ↔ Entradas:** Evaluación de código promocional inválido/inexistente y validación en flujo de reserva.
- **Pagos ↔ Entradas:** Procesamiento real de compra con sesión Auth, consulta de reserva (`INT-01`) y reserva inexistente (`404`).
- **Check-in ↔ Entradas:** Emisión gratuita con registro en Check-in, consulta de titularidad (`200` y `404`), validación en puerta (`STAFF`), rechazo por doble escaneo (`TICKET_ALREADY_USED`), rechazo por evento equivocado (`EVENT_MISMATCH`) y duplicado (`409`).
- **Panel Organizador ↔ Entradas:** Consulta de stock (`200` y `404`).

### Cómo ejecutar con Newman y guardar evidencia HTML/JSON en workstation

```bash
npx newman run "tests/TicketU - QA Integracion.postman_collection.json" --reporters cli,json --reporter-json-export tests/evidencia_QA_CA2_workstation.json
```
