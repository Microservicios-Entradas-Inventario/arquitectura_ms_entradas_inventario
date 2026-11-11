# Guía de Ejecución de Pruebas de Calidad e Integración (CA1 y CA2)

## 1. Pruebas Funcionales Internas (CA1 - Automáticas con Pytest)
Estas pruebas validan la lógica interna de las Historias de Usuario del microservicio de **Entradas e Inventario** (Inventario, Reservas Hold, Historial y Seguridad).

- Activa el entorno virtual e instala las dependencias necesarias:
```bash
pip install pytest pytest-asyncio httpx pytest-html
```

- Desde la carpeta `back-end/`, ejecuta la suite con este comando para actualizar el reporte:
```bash
python -m pytest tests/ -v --html=tests/evidencia_QA_CA1.html --self-contained-html
```

- El resultado detallado se puede visualizar abriendo el archivo `tests/evidencia_QA_CA1.html` en cualquier navegador.

---

## 2. Pruebas de Integración entre Microservicios (CA2 - Postman Collection Runner)

El archivo [`tests/TicketU - QA Integracion.postman_collection.json`](./TicketU%20-%20QA%20Integracion.postman_collection.json) contiene **27 solicitudes automatizadas** organizadas en **3 carpetas** que prueban en vivo la comunicación entre **`entradas-service` (MongoDB)**, **`ms-catalogo-eventos` (Catálogo DB)**, **`checkin-service` (MySQL)**, **`pagos-service` (PostgreSQL)** y **`organizador-service` (MongoDB)** a través del **API Gateway (`http://localhost:8080`)**.

### Matriz de Trazabilidad: Historias de Usuario y Contratos de Integración Probados

| Carpeta / Paso | Microservicios Involucrados | Historia de Usuario (Entradas) | Historia de Usuario (Contraparte) | Contrato / Issue | Qué se Demuestra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1.1 a 1.4** | `Catálogo` ↔ `Entradas` | **HU-01** (Disponibilidad de inventario) | **HU-01, HU-02, HU-04, BE1, BE3** (Catálogo) | Contrato Catálogo v3.0 | Consulta cruzada de vitrina, detalle, metadatos comerciales (`info-servicio`) y stock inicial de `evt-101`. |
| **1.5 y 1.6** | `Entradas` → `Catálogo` | **HU-03** (Reserva Temporal *Hold*) | **HU-04** (Stock en Ficha Detalle de Catálogo) | **Integración I8** (Issue #24) | Al crear un *Hold* por 2 entradas en `entradas-service`, éste descuenta en MongoDB y llama a `PUT /api/v1/catalogo/eventos/evt-101/stock`, disminuyendo en 2 el `stock_actual` en `ms-catalogo-eventos`. |
| **1.7 y 1.8** | `Entradas` → `Catálogo` | **HU-03** (Liberación de *Hold*) | **HU-04** (Stock en Ficha Detalle de Catálogo) | **Integración I8** (Issue #24) | Al cancelar el *Hold* en `entradas-service`, se liberan los 2 cupos en MongoDB y se restaura automáticamente el `stock_actual` en `ms-catalogo-eventos`. |
| **1.9 a 1.11** | `Entradas` → `Catálogo` | **HU-01** (Control de Agotamiento) | **HU-04** (Estado `'agotado'` / `'disponible'`) | **Integración I8** (Issue #24) | Envío de `nuevo_stock: 0` cambia automáticamente `estado_evento` a `'agotado'`; `nuevo_stock: 8` lo reactiva a `'disponible'`; `nuevo_stock: -5` es rechazado con `400 Bad Request`. |
| **1.12** | `Catálogo` → `Entradas` ↔ `Auth` | **HU-02** (Seguridad en Compra) | Inicio de compra desde Catálogo | **Integración I9** (Issue #25) | `POST /api/entradas/procesar-compra` sin cookie `jwt` de Auth es bloqueado con `401 NO_AUTENTICADO`. |
| **2.1** | `Entradas` → `Check-in` + `Catálogo` | **HU-02 y HU-05** (Emisión de Entrada y QR) | **HU-01 Check-in** (Registro de Ticket Emitido) | **Integración I3** (Issue #19) | `POST /api/entradas/emision-directa` inserta la entrada en MongoDB y la registra en vivo en el MySQL de `checkin-service` (`registradoEnCheckin: true`). |
| **2.2 a 2.4** | `Check-in` → `Entradas` | **HU-04 y HU-05** (Detalle Inmutable y QR) | **HU-02 Check-in** (Verificación de Titular) | **Integración I4** (Issue #20) | `GET /api/entradas/{id_ticket}`, `/qr` y `/detalle` retornan titular, rol y payload QR en `< 500ms`. |
| **2.5 y 2.6** | `Check-in` (MySQL) | **HU-05** (Uso de QR en Puerta) | **HU-02 Check-in** (Validación en Torniquete y Antifraude) | Contrato Check-in v0.2.0 | 1er escaneo de `{{id_entrada_emitida}}` en `POST /api/checkin/validaciones` devuelve `valido: true (TICKET_FOUND)`; 2do escaneo devuelve `valido: false (TICKET_ALREADY_USED)`. |
| **2.7a a 2.7c** | `Entradas` → `Check-in` | **HU-03 y HU-05** (Hold Pagado → Webhook → QR) | **HU-01 y HU-02 Check-in** | **Integración I3** (Issue #19) | Crea un *Hold* pagado (`evt-77889`), aprueba el pago por `webhook-pago`, emite el ticket hacia MySQL de Check-in y lo valida exitosamente en puerta (`TICKET_FOUND`). |
| **2.8 a 2.11** | `Entradas` ↔ `Check-in` | **HU-04 y HU-05** | **HU-01 y HU-02 Check-in** (Reglas de Rechazo) | **Contratos I3 e I4** | Idempotencia en Check-in (`409 TICKET_ALREADY_EXISTS`), rechazo de URL en `qr_data` (`400 QR_MISMATCH`), evento equivocado (`EVENT_MISMATCH`) y ticket inexistente en Entradas (`404 Not Found`). |
| **2.12** | `Check-in` → `RabbitMQ` | — | **HU-03 Check-in** (Cierre de Evento y Asistencia) | Tópico `checkin.asistencia_final` | `POST /api/checkin/eventos/evt-002/finalizar` publica el lote de asistentes validados en el exchange `ticketu.events` de RabbitMQ. |
| **3.1 a 3.3** | `Entradas` ↔ `Pagos` y `Panel` | **HU-01, HU-03, HU-04** | **INT-01 Pagos** y **Métricas Panel** | **Contratos I2 e I6** | Consulta de reserva por Pagos (`res-demo-pagos`), consulta de stock por Panel (`evt-77889`) e historial del comprador (`usr-12345`). |

### Cómo Ejecutar la Colección en Postman
1. Abre **Postman** y haz clic en **Import**.
2. Selecciona el archivo `repo/back-end/tests/TicketU - QA Integracion.postman_collection.json`.
3. Haz clic derecho sobre la colección **`TicketU - QA Integración E2E (Entradas ↔ Catálogo ↔ Check-in ↔ Pagos ↔ Panel)`** y selecciona **Run collection** (Collection Runner).
4. Haz clic en **Run TicketU - QA Integración E2E...** (no necesitas configurar variables adicionales: la colección incluye `gateway_url = http://localhost:8080` y encadena dinámicamente los IDs generados entre cada petición).
