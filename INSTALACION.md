# Guía de Instalación y Operación – Entradas e Inventario (`entradas-service`)

Documento de instalación del microservicio **Entradas e Inventario** para el ambiente de pruebas (**workstation**).

---

## 1. Requisitos previos
* Docker y Docker Compose v2+.
* Red compartida Docker `plataforma-eventos-net` creada previamente.
* Servicios de plataforma disponibles en la red compartida (`ticketu-api-gateway`, `ticketu-rabbitmq`).

---

## 2. Variables de entorno configuradas en `docker-compose.yml`

| Variable | Valor en `docker-compose.yml` | Descripción |
| :--- | :--- | :--- |
| `PORT` | `3000` | Puerto interno de FastAPI/Uvicorn |
| `MONGO_URI` | `mongodb://mongodb:27017` | Conexión a MongoDB en la red interna `entradas-internal-net` |
| `MONGO_DB` | `ticketu_entradas_db` | Nombre de la base de datos MongoDB |
| `BROKER_URL` | `amqp://ticketu:ticketu_dev@ticketu-rabbitmq:5672/ticketu` | Broker RabbitMQ compartido (vhost `ticketu`) |
| `EVENT_EXCHANGE` | `ticketu.events` | Exchange compartido de eventos de plataforma |
| `QUEUE_NAME` | `entradas.pagos` | Cola durable propia del consumidor de Entradas |
| `AUTH_SERVICE_URL` | `http://auth-service:10000` | URL interna del servicio de Autenticación |
| `INTERNAL_API_KEY` | `${INTERNAL_API_KEY:-CAMBIAR_CLAVE_COMPARTIDA_SEGURA}` | Clave compartida `x-api-key` con Auth |
| `PAGOS_SERVICE_URL` | `http://ticketu-api-gateway:8080` | Ruta hacia Pagos vía API Gateway |
| `CATALOGO_SERVICE_URL` | `http://ticketu-api-gateway:8080` | Ruta hacia Catálogo vía API Gateway |
| `CHECKIN_SERVICE_URL` | `http://ticketu-api-gateway:8080` | Ruta hacia Check-in vía API Gateway |
| `PANEL_SERVICE_URL` | `http://ticketu-api-gateway:8080` | Ruta hacia Panel Organizador vía API Gateway |
| `PROMOCIONES_SERVICE_URL` | `http://ticketu-api-gateway:8080` | Ruta hacia Promociones vía API Gateway |

**Puertos expuestos al host:**
* `entradas-service` (API + Swagger UI): `http://localhost:3003` (`http://localhost:3003/docs`, `http://localhost:3003/health`)
* A través del API Gateway: `http://localhost:8080/api/entradas/...`
* Mongo Express: `http://localhost:8082`

---

## 3. Pasos de instalación

```bash
# 1. Crear la red compartida si no existe
docker network create plataforma-eventos-net || true

# 2. Levantar MongoDB, Mongo Express y entradas-service
docker compose up -d --build

# 3. Verificar estado saludable del servicio
curl -s http://localhost:3003/health
```

Para recargar manualmente los datos semilla e índices de [`database/init_db.js`](database/init_db.js):

```bash
docker exec -i ticketu_entradas_mongo mongosh --quiet < database/init_db.js
```

---

## 4. Pruebas automatizadas locales (CA1)

Desde la carpeta `back-end/` (o dentro del contenedor `entradas-service`):

```bash
docker exec entradas-service python -m pytest tests/test_funcionalidades.py -v --html=tests/evidencia_QA_CA1.html --self-contained-html
```
