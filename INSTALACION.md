# Guía de Instalación y Operación – Entradas e Inventario (`entradas-service`)

Documento de instalación para ambiente de pruebas (**workstation**) conforme a la Evaluación 3.

---

## 1. Requisitos previos
* Docker y Docker Compose v2+
* Red compartida Docker `plataforma-eventos-net` creada previamente y servicios base de plataforma activos (`ticketu-api-gateway`, `ticketu-auth-service`, `ticketu-rabbitmq`).

---

## 2. Variables de entorno en workstation

Configuradas en [`docker-compose.yml`](docker-compose.yml) (y plantilla [`.env.example`](.env.example)):

| Variable | Valor en workstation | Descripción |
| :--- | :--- | :--- |
| `MONGO_URI` | `mongodb://ticketu_entradas_mongo:27017` | Base de datos MongoDB aislada del servicio |
| `MONGO_DB_NAME` | `ticketu_entradas_db` | Nombre de la base de datos |
| `AUTH_SERVICE_URL` | `http://auth-service:10000` | URL interna del microservicio Auth |
| `INTERNAL_API_KEY` | `${INTERNAL_API_KEY:-CAMBIAR_CLAVE_COMPARTIDA_SEGURA}` | Clave interna compartida `x-api-key` con Auth |
| `PAGOS_SERVICE_URL` | `http://ticketu-api-gateway:8080` | URL hacia Pagos vía API Gateway |
| `CATALOGO_SERVICE_URL` | `http://ticketu-api-gateway:8080` | URL hacia Catálogo vía API Gateway |
| `CHECKIN_SERVICE_URL` | `http://ticketu-api-gateway:8080` | URL hacia Check-in vía API Gateway |
| `PANEL_SERVICE_URL` | `http://ticketu-api-gateway:8080` | URL hacia Panel Organizador vía API Gateway |
| `BROKER_URL` | `amqp://ticketu:ticketu_dev@ticketu-rabbitmq:5672/ticketu` | Conexión al broker RabbitMQ (vhost `ticketu`) |
| `EVENT_EXCHANGE` | `ticketu.events` | Exchange principal de eventos de plataforma |
| `QUEUE_NAME` | `entradas.pagos` | Cola propia de consumo de Entradas |

**Puertos expuestos:**
* `entradas-service` (API + Swagger UI): `http://localhost:3003` (`http://localhost:3003/docs`, `http://localhost:3003/health`)
* A través del API Gateway: `http://localhost:8080/api/entradas/...`
* Mongo Express (GUI de BD): `http://localhost:8082`

---

## 3. Pasos y comandos de instalación

```bash
# 1. Crear la red compartida si aún no existe
docker network create plataforma-eventos-net || true

# 2. Levantar MongoDB, Mongo Express y entradas-service
docker compose up -d --build

# 3. Verificar estado saludable del servicio
curl -s http://localhost:3003/health
```

> El script [`database/init_db.js`](database/init_db.js) inicializa automáticamente las colecciones (`inventario_evento`, `reserva_entrada`, `entrada`), esquemas `$jsonSchema` y datos semilla al primer arranque de MongoDB. Si necesitas recargar la semilla manualmente:
> ```bash
> docker exec -i ticketu_entradas_mongo mongosh --quiet < database/init_db.js
> ```

---

## 4. Usuarios de prueba de Auth

| Rol | Correo | Contraseña | Nota de login (`POST /api/auth/login`) |
| :--- | :--- | :--- | :--- |
| **Comprador (`USUARIO`)** | `comprador1@ticketu.test` | `TicketuQA2026!` | `{"email":"comprador1@ticketu.test","password":"TicketuQA2026!"}` |
| **Staff (`STAFF`)** | `staff1@ticketu.test` | `TicketuQA2026!` | `{"email":"staff1@ticketu.test","password":"TicketuQA2026!","admin":true}` |

---

## 5. Flujo principal del módulo (para verificación)

### Desde el Frontend Unificado (`http://localhost:3000`)
1. Iniciar sesión en Auth con **`comprador1@ticketu.test`** / `TicketuQA2026!`.
2. Entrar al módulo de **Entradas** y seleccionar un evento disponible (ej. *Charla de Ciberseguridad* o *Festival de Música Primavera*).
3. Seleccionar cantidad de entradas y presionar **Reservar / Obtener entrada**:
   * Si es gratuito, emite la entrada con su código QR, la registra en **Check-in** y publica el evento `entradas_emitidas` hacia **Notificaciones**.
   * Si es pagado, crea una reserva temporal (*Hold* de 15 min) con opción de pago en **Pagos**.

### Alternativa directa por API Gateway (`http://localhost:8080`)
1. Login comprador: `POST /api/auth/login` con `comprador1@ticketu.test`.
2. Emitir entrada: `POST /api/entradas/emision-directa` (registra ticket en Check-in y publica `entradas_emitidas` en RabbitMQ).
3. Validar ticket en Check-in con sesión `STAFF` (`staff1@ticketu.test`): `POST /api/checkin/validaciones`.
4. Ver suite completa en [`back-end/tests/TicketU - QA Integracion.postman_collection.json`](back-end/tests/TicketU%20-%20QA%20Integracion.postman_collection.json) y guía [`back-end/tests/INSTRUCCIONES_QA.md`](back-end/tests/INSTRUCCIONES_QA.md).
