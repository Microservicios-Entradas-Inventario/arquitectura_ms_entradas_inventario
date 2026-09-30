# 🎟️ TicketU - Backend API (Entradas e Inventario)

Bienvenido a la rama `backend` del microservicio de **Entradas e Inventario** del proyecto TicketU. Esta rama contiene exclusivamente el código fuente, base de datos e integraciones de API de nuestro módulo, desarrollado con **FastAPI** y **MongoDB**.

## 👥 Responsable del Rol Backend
* **Esteban Quinteros** - Desarrollador Backend

## 🛠️ Stack Tecnológico
* **Framework Web:** FastAPI (Python 3.12+)
* **Servidor ASGI:** Uvicorn con recarga en caliente (`--reload`)
* **Base de Datos NoSQL:** MongoDB con driver asíncrono `motor`
* **Validación & Serialización:** Pydantic v2
* **Cliente HTTP Asíncrono:** HTTPX (con SLAs y timeouts estrictos para comunicación inter-servicios)
* **Contenedores:** Docker & Docker Compose (para despliegue local de MongoDB y Mongo Express)

---

## 🏛️ Estructura del Proyecto

El backend sigue una arquitectura modular en capas para mantener separación de responsabilidades y alta cohesión:

```text
├── back-end/
│   ├── database.py              # Gestión del ciclo de vida y conexión asíncrona a MongoDB (Motor)
│   ├── main.py                  # Punto de entrada de la aplicación FastAPI y registro de routers
│   ├── requirements.txt         # Dependencias del proyecto
│   ├── routers/                 # Controladores y endpoints organizados por dominio
│   │   ├── entradas.py          # Emisión, compra (flujo libre/pago), reportes y consulta por usuario
│   │   ├── inventario.py        # Consulta de disponibilidad en tiempo real para Catálogo
│   │   └── reservas.py          # Webhook de confirmación transaccional desde Pagos
│   ├── schemas/                 # Esquemas de validación y DTOs (Pydantic)
│   │   └── entradas.py          # Modelos de solicitud y respuesta
│   ├── services/                # Capa de integración desacoplada con otros microservicios (HTTPX)
│   │   ├── auth_service.py          # Validación de sesiones, JWT y roles con Autenticación
│   │   ├── catalogo_service.py      # Actualización de stock en Catálogo de Eventos
│   │   ├── checkin_service.py       # Emisión de tickets y códigos QR en Check-in
│   │   ├── notificaciones_service.py# Envío asíncrono de tickets por correo
│   │   ├── pagos_service.py         # Creación e inicio de órdenes de pago con Pasarela
│   │   └── panel_service.py         # Notificación de métricas y ventas al Panel Organizador
│   └── tests/                   # Pruebas automatizadas (Pytest) y colección Postman
├── database/                    # Capa desacoplada de persistencia y base de datos
│   ├── init_db.js               # Script de inicialización y datos semilla (Seed) de colecciones
│   └── schema.dbml              # Modelado relacional/documental de base de datos
├── docker-compose.yml           # Orquestación de contenedores para MongoDB y Mongo Express
```
* **Backend:** FastAPI
* **Base de Datos:** MongoDB
* **Mensajería Asíncrona:** RabbitMQ (Broker de eventos)
* **Infraestructura:** Docker & Docker Compose (Despliegue On-Premise)

---

## 📦 Cumplimiento de la Rúbrica (Evaluación 1)

Esta rama ha sido adaptada y refactorizada estrictamente para cumplir al 100% con la Rúbrica de la Evaluación 1, cubriendo los ítems **BE1**, **BE2** y **BE3**:

### 1. BE1: Servicios Propios
Se implementaron los endpoints principales para soportar las historias de usuario del módulo:
* **HU-01 (Visualización de disponibilidad):** Consulta en tiempo real de capacidad por zona, límites por compra y disponibilidad actual.
* **HU-02 (Selección y compra/reserva):** Validación de autenticación JWT y roles (`CLIENTE`/`USUARIO`), control de cupos, límites máximos de compra por usuario y derivación inteligente:
  * **Eventos gratuitos:** Emisión inmediata de tickets y respuesta directa al cliente.
  * **Eventos de pago:** Creación de reserva con estado `PENDIENTE` e inicio de pasarela en Pagos.
* **Historial de tickets:** Endpoint para que los clientes consulten sus entradas adquiridas (`GET /api/v1/entradas/usuario/{id_usuario}`).

### 2. BE2: Invocación a Servicios Externos (Integraciones como Consumidor)
Implementación mediante la capa `services/` con clientes asíncronos `httpx.AsyncClient` y control estricto de SLAs:
* **Autenticación (`AuthService`):**
  * Invoca `POST /api/v1/auth/verify` enviando el token en formato cookie (`Cookie: jwt=<token>`).
  * Valida que el usuario tenga rol `CLIENTE` o `USUARIO` y estado activo antes de permitir compras.
* **Catálogo (`CatalogoService`):**
  * Invoca `PUT /api/v1/eventos/{id_evento}/entradas` para sincronizar la reducción de cupos (SLA < 200 ms).
* **Pasarela de Pagos (`PagosService`):**
  * Invoca `POST /api/v1/pagos` para iniciar la orden de compra con `id_usuario`, `id_reserva` y `monto_total`.
* **Check-in (`CheckinService`):**
  * Invoca `POST /api/v1/entradas/emitir` para registrar los códigos de entrada/QR habilitados para validación física en puertas (SLA < 500 ms).
* **Notificaciones (`NotificacionesService`):**
  * Notificación asíncrona para despacho de confirmación y tickets por correo electrónico.
* **Procesamiento Asíncrono no bloqueante (`asyncio.create_task`):**
  * Las llamadas post-compra hacia Check-in, Catálogo y Notificaciones se ejecutan concurrentemente en segundo plano para garantizar tiempos de respuesta ultrarrápidos al cliente final.
* *Nota sobre Promociones:* Conforme al Contrato de Integración oficial v1.0, el consumidor de Promociones es directamente el Frontend (Web/Mobile), por lo cual el cálculo y aplicación de cupones se procesa en el Checkout previo y no añade acoplamiento innecesario a este microservicio.

### 3. BE3: Servicios Requeridos por Otros (Integraciones como Proveedor)
Se expusieron endpoints documentados para la interoperabilidad con los demás módulos:
* **Para Catálogo:** `POST /api/v1/entradas/procesar-compra` para procesar y registrar compras.
* **Para Check-in:** `GET /api/v1/entradas/{id_ticket}` para validación individual de una entrada emitida.
* **Para Panel Organizador:** `GET /api/v1/entradas/eventos/{id_evento}/stock` con métricas de stock y disponibilidad actualizadas.
* **Para Pagos:** `GET /api/v1/reservas/{id_reserva}` para consultar estado de reservas previo a pago.
* **Simulación RabbitMQ:** `POST /api/v1/reservas/{id_reserva}/webhook-pago` como webhook de recepción de aprobaciones de pago.

---

## 📋 Catálogo de Endpoints de la API

| Método | Ruta | Descripción / Propósito | Sección / Consumidor |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/inventario/{id_evento}` | Obtener Disponibilidad | Inventario (BE1) |
| **POST** | `/api/v1/entradas/procesar-compra` | Procesar Compra | Servicios Provistos (BE3) - Catálogo |
| **GET** | `/api/v1/entradas/{id_ticket}` | Consultar Entrada Checkin | Servicios Provistos (BE3) - Check-in |
| **GET** | `/api/v1/entradas/eventos/{id_evento}/stock` | Consultar Stock Panel | Servicios Provistos (BE3) - Panel Organizador |
| **POST** | `/api/v1/reservas/{id_reserva}/webhook-pago` | Procesar Pago Aprobado | Simulación RabbitMQ - Pago Aprobado |
| **GET** | `/api/v1/reservas/{id_reserva}` | Consultar Reserva Pagos | Servicios Provistos (BE3) - Pagos |
* **Sprint 1 (Avance 1 - 01/10):** Base de Datos, Stock y Selección (~~HU-06~~, HU-01, HU-02).
* **Sprint 2 (Avance 2 - 22/10):** Ciclo de Reserva y Emisión de Entradas (HU-03, HU-04, HU-05).
* **Sprint 3 (Avance 3 - 05/11):** Asincronía (RabbitMQ) y Reglas de Negocio (HU-07, HU-09, HU-08).
* **Sprint 4 (Entrega Final - 25/11):** Integración E2E a través del API Gateway, Estabilización y Despliegue On-Premise.

---

## ⚙️ Ejecución Local (Entorno de Desarrollo)

Para levantar el microservicio de manera local y visualizar la documentación interactiva OpenAPI/Swagger, sigue estos pasos:

### 1. Clonar el repositorio y situarse en la rama backend
```bash
git clone https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario.git
cd arquitectura_ms_entradas_inventario/Backend
git checkout backend
```

### 2. Crear y activar el entorno virtual
Es altamente recomendado utilizar un entorno virtual para aislar las dependencias:

**En Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
**En Linux / macOS / Git Bash:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Levantar la Base de Datos (MongoDB)
El microservicio requiere MongoDB con los datos semilla inicializados. Para levantar el contenedor de base de datos junto con Mongo Express (GUI web), ejecuta:
```bash
docker compose up -d
```
* **MongoDB:** `localhost:27017`
* **Mongo Express (Panel Web):** [http://localhost:8081](http://localhost:8081)
*(Para detener los contenedores al finalizar, ejecuta `docker compose down`)*

### 5. Iniciar el servidor FastAPI
Inicia el servidor en modo desarrollo con recarga automática:
```bash
uvicorn main:app --reload
```

### 6. Explorar la Documentación Swagger UI
Abre tu navegador web y accede a:

👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

Dentro de la interfaz de Swagger UI podrás examinar la especificación detallada de cada endpoint (descripciones en formato Markdown, modelos Pydantic, parámetros requeridos, códigos de respuesta HTTP `200`, `400`, `401`, `404`, `500`) y realizar pruebas interactivas con el botón **"Try it out"**.
