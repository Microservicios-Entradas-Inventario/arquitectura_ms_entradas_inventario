# Informe de Pruebas de Integración y Guía Paso a Paso con Datos Semilla (`entradas-service` ↔ Ecosistema TicketU)

**Microservicio Evaluado:** Entradas e Inventario (`entradas-service`)  
**Red Compartida Docker:** `plataforma-eventos-net` (`172.18.0.0/16`)  
**Red Interna de Datos:** `entradas-internal-net` (aislamiento Database-per-Service para MongoDB)  
**Archivo de Datos Semilla:** [`database/init_db.js`](../database/init_db.js)  
**Entorno de Ejecución:** macOS (`zsh` / `bash`) y Windows (`PowerShell`)  

---

## 1. Preparación Rápida en macOS (`zsh` / `bash`)

Abre la **Terminal** de tu MacBook en la raíz de este repositorio y ejecuta este bloque para cargar los datos semilla en MongoDB, detectar los nombres de los contenedores de Check-in y sincronizar los 2 tickets semilla iniciales en MySQL:

```bash
# 1. Cargar datos semilla en MongoDB de Entradas
docker exec -i ticketu_entradas_mongo mongosh --quiet < database/init_db.js

# 2. Detectar automáticamente los contenedores de Check-in en tu Mac
CHECKIN_DB=$(docker ps --filter "ancestor=mysql:8.0" --format "{{.Names}}" | head -n 1)
CHECKIN_APP=$(docker ps --filter "publish=3001" --format "{{.Names}}" | head -n 1)
echo "MySQL Check-in: $CHECKIN_DB | App Check-in: $CHECKIN_APP"

# 3. Sincronizar los 2 tickets semilla iniciales en el MySQL de Check-in
curl -s -X POST http://localhost:3001/api/checkin/tickets \
  -H "Content-Type: application/json" \
  -d '{"id_entrada":"tk-998877","id_evento":"evt-77889","id_usuario":"usr-12345","nombre_usuario":"Sebastian Fuentes","qr_data":"tk-998877"}'

curl -s -X POST http://localhost:3001/api/checkin/tickets \
  -H "Content-Type: application/json" \
  -d '{"id_entrada":"tk-demo-001","id_evento":"evt-002","id_usuario":"usr-12345","nombre_usuario":"Sebastian Fuentes","qr_data":"tk-demo-001"}'
```

*(Si necesitas reiniciar los datos semilla en cualquier momento durante la presentación, vuelve a ejecutar `docker exec -i ticketu_entradas_mongo mongosh --quiet < database/init_db.js`).*

---

## 2. Resumen de los Datos Semilla ([`database/init_db.js`](../database/init_db.js))

### 2.1. Eventos Semilla (`inventario_evento`)
| `id_evento` | `nombre_evento` | `tipo_entrada` | `precio_unitario` | `stock_actual` | Propósito en Pruebas |
|---|---|---|---|---|---|
| `evt-77889` | Concierto Sinfonico TicketU | `PAGADA` | `$10.000` | `144` | Evento principal para Hold, Pagos y Check-in |
| `evt-002` | Charla Abierta de Innovacion | `GRATUITA` | `$0` | `99` | Evento gratuito para emisión directa |
| `evt-101` | Festival Universitario TITEC | `PAGADA` | `$15.000` | `200` | Sincronización de stock con Catálogo (`catalogo-service:4000`) |
| `66f1a0000000000000000002` | Feria de Innovacion TITEC | `PAGADA` | `$10.000` | `300` | Evento sincronizado con Panel Organizador (`organizador-service:3000`) |

### 2.2. Reservas Semilla (`reserva_entrada` — vigencia de 7 días)
| `id_reserva` | `id_evento` | `id_usuario` | `estado_reserva` | `cantidad_entrada` | `monto_total` | `id_pago` | Uso directo en el Instructivo |
|---|---|---|---|---|---|---|---|
| `res-98765` | `evt-77889` | `usr-12345` | `CONSOLIDADO` | `1` | `$8.500` | `pay-112233` | Reserva ya pagada con ticket `tk-998877` emitido |
| `res-98766` | `evt-77889` | `usr-54321` | `RESERVADO` | `1` | `$10.000` | `pay-112234` | **Lista para emitir ticket a Check-in** (`POST /api/entradas/reservas/res-98766/webhook-pago`) |
| `res-demo-checkin` | `evt-77889` | `usr-12345` | `RESERVADO` | `1` | `$10.000` | `pay-demo-checkin` | **Reserva extra lista para emitir ticket a Check-in** (`webhook-pago`) |
| `res-demo-pagos` | `evt-77889` | `usr-12345` | `RESERVADO` | `2` | `$20.000` | `null` | **Lista para consulta desde Pagos** (`GET /api/v1/entradas/reservas/res-demo-pagos`) |
| `res-demo-cancelar` | `evt-77889` | `usr-12345` | `RESERVADO` | `1` | `$10.000` | `pay-demo-cancel` | **Lista para probar liberación de cupo** (`POST /api/entradas/reservas/res-demo-cancelar/cancelar`) |

### 2.3. Entradas Semilla (`entrada` en MongoDB y `ticket` en MySQL de Check-in)
| `id_entrada` | `id_reserva` | `id_evento` | `id_usuario` | `nombre_usuario` | `estado_entrada` | Estado en MySQL Check-in |
|---|---|---|---|---|---|---|
| `tk-998877` | `res-98765` | `evt-77889` | `usr-12345` | `Sebastian Fuentes` | `EMITIDA` | Registrado (`PENDIENTE`) |
| `tk-demo-001` | `res-98765` | `evt-002` | `usr-12345` | `Sebastian Fuentes` | `EMITIDA` | Registrado (`PENDIENTE`) |

---

## 3. Instructivo Paso a Paso en macOS: `Entradas` (MongoDB) ↔ `Check-in` (MySQL)

### Flujo 1: Comprobar que `Entradas` inserta automáticamente un ticket en la BD MySQL de `Check-in`

#### Paso 1.1: Ver el estado inicial de la tabla `ticket` en MySQL de Check-in
```bash
docker exec "$CHECKIN_DB" mysql -u checkin_user -pcheckin_password checkin_db \
  -e "SELECT id_entrada, id_evento, id_usuario, nombre_usuario, qr_data, estado FROM ticket;"
```
**Resultado inicial:**
```text
id_entrada    id_evento   id_usuario   nombre_usuario      qr_data         estado
tk-998877     evt-77889   usr-12345    Sebastian Fuentes   "tk-998877"     PENDIENTE
tk-demo-001   evt-002     usr-12345    Sebastian Fuentes   "tk-demo-001"   PENDIENTE
```

#### Paso 1.2 (Opción A - Con Reserva Semilla `res-98766`): Emitir ticket hacia Check-in
Desde Swagger (`http://localhost:3000/docs` → `POST /api/entradas/reservas/{id_reserva}/webhook-pago` con `res-98766`) o desde la Terminal del Mac:

```bash
curl -s -X POST http://localhost:3000/api/entradas/reservas/res-98766/webhook-pago | python3 -m json.tool
```
**Respuesta (`200 OK`):**
```json
{
    "message": "Ticket emitido y notificaciones distribuidas correctamente.",
    "entradas_emitidas": [
        "tk-ab577ad8"
    ]
}
```

*(Opción B - Si deseas crear un Hold nuevo desde cero y emitirlo:)*
```bash
HOLD_ID=$(curl -s -X POST http://localhost:3000/api/entradas/reservas/hold \
  -H "Content-Type: application/json" \
  -d '{"id_evento":"evt-77889","id_usuario":"usr-12345","nombre_usuario":"Sebastian Fuentes","cantidad":1,"tiempo_limite_minutos":15}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['id_reserva'])")
echo "Reserva creada: $HOLD_ID"

curl -s -X POST "http://localhost:3000/api/entradas/reservas/$HOLD_ID/webhook-pago" | python3 -m json.tool
```

#### Paso 1.3: Comprobar que el nuevo ticket se guardó en MongoDB (`entradas`) y en MySQL (`checkin`)
1. **En MySQL de Check-in:**
   ```bash
   docker exec "$CHECKIN_DB" mysql -u checkin_user -pcheckin_password checkin_db \
     -e "SELECT id_entrada, id_evento, id_usuario, nombre_usuario, qr_data, estado FROM ticket;"
   ```
2. **En MongoDB de Entradas:**
   ```bash
   docker exec ticketu_entradas_mongo mongosh ticketu_entradas_db --quiet \
     --eval "db.entrada.find({}, {_id:0, id_entrada:1, id_reserva:1, id_evento:1, id_usuario:1, estado_entrada:1}).toArray()"
   ```

---

### Flujo 2: Validar Ticket en `Check-in` y Consultar Validez desde `Check-in` hacia `Entradas`

#### Paso 2.1: Validar en puerta un ticket semilla (`tk-998877` o el recién emitido) en `Check-in`
```bash
curl -s -X POST http://localhost:3001/api/checkin/validaciones \
  -H "Content-Type: application/json" \
  -d '{"id_entrada":"tk-998877","id_evento":"evt-77889"}' | python3 -m json.tool
```
**Respuesta de `checkin-service` (`200 OK`):**
```json
{
    "valido": true,
    "motivo": "TICKET_FOUND",
    "ticket": {
        "id_entrada": "tk-998877",
        "id_evento": "evt-77889",
        "id_usuario": "usr-12345",
        "nombre_usuario": "Sebastian Fuentes"
    }
}
```

#### Paso 2.2: Consultar desde el contenedor `checkin-service` hacia `entradas-service` (`GET /api/entradas/tk-998877`)
```bash
docker exec "$CHECKIN_APP" node -e "fetch('http://entradas-service:3000/api/entradas/tk-998877').then(async r => console.log(r.status, await r.text()))"
```
**Respuesta obtenida desde `entradas-service` (`200 OK`):**
```json
200 {"id_ticket":"tk-998877","nombre_usuario":"Sebastian Fuentes","usuario":{"id_usuario":"usr-12345","rol_usuario":"cliente"}}
```

---

## 4. Pruebas Rápidas en macOS con Datos Semilla para el Resto de Microservicios

### 4.1. `Pagos` ↔ `Entradas` (`res-demo-pagos` y `res-demo-cancelar`)
```bash
# Consultar reserva semilla res-demo-pagos desde pagos-service (Operación 1 - INT-01)
docker exec pagos-service wget -qO- http://entradas-service:3000/api/v1/entradas/reservas/res-demo-pagos | python3 -m json.tool

# Cancelar reserva semilla res-demo-cancelar y devolver cupos al stock disponible
curl -s -X POST http://localhost:3000/api/entradas/reservas/res-demo-cancelar/cancelar \
  -H "Content-Type: application/json" \
  -d '{"motivo":"Prueba de liberacion con datos semilla"}' | python3 -m json.tool
```

### 4.2. `Panel Organizador` ↔ `Entradas` (`evt-77889` y `66f1a0000000000000000002`)
```bash
curl -s http://localhost:3000/api/entradas/eventos/66f1a0000000000000000002/stock | python3 -m json.tool
```

### 4.3. Historial y QR de Entradas Semilla (`HU-04` y `HU-05`)
```bash
curl -s http://localhost:3000/api/entradas/usuario/usr-12345 | python3 -m json.tool
curl -s http://localhost:3000/api/entradas/tk-998877/qr | python3 -m json.tool
```

---

## 5. Comando Único en macOS de Verificación Integral en Consola

```bash
docker exec entradas-service python -c "import urllib.request;
for name, url in [
    ('Auth', 'http://auth-service:10000/'),
    ('Pagos', 'http://pagos-service:3000/api/pagos/health'),
    ('Catalogo', 'http://catalogo-service:4000/health'),
    ('Check-in', 'http://checkin-service:3001/health'),
    ('Panel Organizador', 'http://organizador-service:3000/health'),
    ('API Gateway -> Entradas', 'http://ticketu-api-gateway:8080/api/entradas/health')
]:
    r = urllib.request.urlopen(url, timeout=3)
    print(f'[OK {r.status}] {name}: {r.read().decode().strip()}')"
```
