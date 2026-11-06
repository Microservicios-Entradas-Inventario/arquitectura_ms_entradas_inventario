# TicketU — Front-end

Este repositorio es la **base común del front-end** de TicketU, entregada por el _Platform Team_. Está desarrollado en **Next.js** y funciona como la interfaz compartida de los 9 módulos del proyecto.

Cada grupo trabaja principalmente en sus propias carpetas. El front **no conoce las URLs individuales de los microservicios**: todas las peticiones al backend pasan por un único **API Gateway**.

---

## 1. Antes de empezar — desarrollo sin Docker

Instalen las dependencias:

```bash
npm install
```

Luego creen el archivo de variables de entorno a partir del ejemplo.

En Linux, macOS o Git Bash:

```bash
cp .env.example .env.local
```

En PowerShell:

```powershell
Copy-Item .env.example .env.local
```

Finalmente:

```bash
npm run dev
```

El front quedará disponible en:

```text
http://localhost:3000
```

El archivo `.env.local` debe contener la dirección pública del API Gateway:

```env
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080
```

Mientras el Gateway esté ejecutándose en la misma máquina, ese valor es suficiente.

> `NEXT_PUBLIC_GATEWAY_URL` debe ser una dirección que pueda abrir el navegador. Por eso, para desarrollo local se utiliza `http://localhost:8080`.

---

## 2. Idea general de la estructura

Hay tres zonas importantes dentro de `src/`:

```text
src/
├── app/            ← rutas y páginas de Next.js
├── components/     ← componentes compartidos como Header y Footer
├── modules/        ← código correspondiente a cada uno de los 9 grupos
└── lib/
    └── env.ts      ← URL única del API Gateway
```

### `src/app/`

Define qué URL muestra cada página.

Por ejemplo:

```text
app/pagos/ → /pagos
```

Los archivos de esta carpeta deben contener poca lógica. Principalmente importan y muestran componentes del módulo correspondiente.

### `src/modules/`

Aquí vive el trabajo principal de cada grupo:

```text
modules/<modulo>/
├── api.ts
└── components/
```

- `api.ts`: contiene las llamadas al backend.
- `components/`: contiene la interfaz y lógica visual del módulo.

### `src/lib/env.ts`

Centraliza la única dirección que necesita conocer el front: la del **API Gateway**.

El front **no almacena las URLs de los 9 microservicios**.

---

## 3. Qué carpetas usa cada grupo

Cada grupo trabaja principalmente en:

```text
src/app/<su-ruta>/
src/modules/<su-modulo>/
```

| #   | Grupo                 | Ruta                                         | Carpeta del módulo        |
| --- | --------------------- | -------------------------------------------- | ------------------------- |
| 1   | Auth                  | `app/auth/`                                  | `modules/auth/`           |
| 2   | Catálogo de eventos   | `app/catalogo/` y `app/catalogo/[eventoId]/` | `modules/catalogo/`       |
| 3   | Entradas / Inventario | `app/entradas/`                              | `modules/entradas/`       |
| 4   | Pagos                 | `app/pagos/`                                 | `modules/pagos/`          |
| 5   | Check-in              | `app/checkin/`                               | `modules/checkin/`        |
| 6   | Reseñas               | `app/catalogo/[eventoId]/resenas/`           | `modules/resenas/`        |
| 7   | Panel organizador     | `app/organizador/`                           | `modules/organizador/`    |
| 8   | Notificaciones        | `app/notificaciones/`                        | `modules/notificaciones/` |
| 9   | Promociones           | `app/promociones/`                           | `modules/promociones/`    |

Dentro de `modules/<su-modulo>/` encontrarán normalmente:

```text
api.ts
components/
```

`api.ts` es el lugar donde deben concentrarse las llamadas HTTP de su módulo.

No escriban directamente la dirección de su microservicio.

---

## 4. Módulos que se relacionan con Catálogo

La página de detalle de un evento necesita información que pertenece a otros módulos, por ejemplo disponibilidad de entradas, promociones y reseñas.

Esto no significa que Catálogo sea responsable de esas funcionalidades. Cada equipo continúa siendo dueño de su propio módulo.

### 4.1 Reseñas — Grupo 6

Las reseñas de un evento tienen una ruta propia:

```text
/catalogo/<eventoId>/resenas
```

La estructura es:

```text
app/catalogo/
├── page.tsx
├── [eventoId]/
│   ├── page.tsx
│   └── resenas/
│       └── page.tsx
```

Responsabilidades:

```text
Grupo 2 — Catálogo
/catalogo
/catalogo/<eventoId>

Grupo 6 — Reseñas
/catalogo/<eventoId>/resenas
```

La lógica de Reseñas vive en:

```text
src/modules/resenas/
```

y sus llamadas al backend usan:

```text
/api/resenas/...
```

Aunque visualmente las reseñas estén relacionadas con un evento del catálogo, el microservicio sigue siendo el de **Reseñas**.

### 4.2 Entradas y Promociones dentro del detalle de un evento

Catálogo puede necesitar mostrar información resumida de otros módulos, por ejemplo:

```text
Entradas disponibles: 142
Promoción activa: 20 % de descuento
```

Para eso existen componentes pequeños pertenecientes a esos equipos:

```text
modules/entradas/components/DisponibilidadPlaceholder.tsx
modules/promociones/components/PromocionPlaceholder.tsx
```

Catálogo puede importarlos dentro del detalle del evento:

```tsx
import DisponibilidadPlaceholder from "@/modules/entradas/components/DisponibilidadPlaceholder";

import PromocionPlaceholder from "@/modules/promociones/components/PromocionPlaceholder";
```

La regla sigue siendo:

```text
Catálogo decide dónde se muestra el bloque.
Entradas decide qué información de entradas muestra.
Promociones decide qué información de promociones muestra.
```

El Grupo 2 no debe implementar la lógica interna de Entradas ni Promociones.

---

## 5. Header y Footer

Los archivos compartidos:

```text
src/components/layout/Header.tsx
src/components/layout/Footer.tsx
```

aparecen en toda la aplicación mediante el layout raíz de Next.js.

Como estos archivos afectan a todos los grupos:

1. su contenido debe acordarse entre los equipos;
2. idealmente una sola persona o el Platform Team realiza el cambio;
3. los cambios posteriores deberían hacerse mediante Pull Request.

Esto evita conflictos donde varios grupos modifican simultáneamente los mismos archivos.

---

## 6. Reglas generales de Git

Nunca se trabaja directo sobre `main`.

Cada cambio debería realizarse en una rama:

```text
feature/<grupo>-<descripcion>
```

Ejemplo:

```text
feature/pagos-formulario-checkout
```

Luego:

```text
branch
  ↓
Pull Request
  ↓
revisión
  ↓
main
```

Es preferible realizar cambios pequeños e integrarlos frecuentemente en lugar de acumular muchos cambios durante varias semanas.

---

## 7. Comunicación con el backend

El front utiliza **un único API Gateway**.

```text
Front
  │
  │ HTTP
  ▼
API Gateway
  │
  ├── Auth
  ├── Catálogo
  ├── Entradas
  ├── Pagos
  ├── Check-in
  ├── Reseñas
  ├── Organizador
  ├── Notificaciones
  └── Promociones
```

El front solamente conoce:

```env
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080
```

El archivo `src/lib/env.ts` expone:

```ts
export const GATEWAY_URL =
  process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8080";
```

Cada módulo agrega su propio path.

---

## 8. Paths de los 9 módulos

La convención acordada es:

| Grupo                 | Path en el Gateway    |
| --------------------- | --------------------- |
| Auth                  | `/api/auth`           |
| Catálogo              | `/api/catalogo`       |
| Entradas / Inventario | `/api/entradas`       |
| Pagos                 | `/api/pagos`          |
| Check-in              | `/api/checkin`        |
| Reseñas               | `/api/resenas`        |
| Panel organizador     | `/api/organizador`    |
| Notificaciones        | `/api/notificaciones` |
| Promociones           | `/api/promociones`    |

Por ejemplo, Catálogo usa:

```ts
import { GATEWAY_URL } from "@/lib/env";

const BASE_PATH = "/api/catalogo";

export async function buscarEventos(query?: string) {
  const url = query
    ? `${GATEWAY_URL}${BASE_PATH}/eventos?q=${encodeURIComponent(query)}`
    : `${GATEWAY_URL}${BASE_PATH}/eventos`;

  const res = await fetch(url);

  if (!res.ok) {
    throw new Error("Error al conectar con el módulo de catálogo");
  }

  return res.json();
}
```

Si:

```text
GATEWAY_URL = http://localhost:8080
```

el navegador enviará:

```text
GET http://localhost:8080/api/catalogo/eventos
```

El Gateway recibe la petición y sabe que `/api/catalogo/*` pertenece al microservicio de Catálogo.

---

## 9. Flujo completo de una petición

Ejemplo: el usuario abre el catálogo y el front necesita obtener los eventos.

### Paso 1 — Front

```ts
fetch(`${GATEWAY_URL}/api/catalogo/eventos`);
```

Con:

```text
GATEWAY_URL=http://localhost:8080
```

la petición queda:

```text
GET http://localhost:8080/api/catalogo/eventos
```

### Paso 2 — API Gateway

El Gateway reconoce `/api/catalogo` y reenvía la petición al microservicio de Catálogo.

Por ejemplo, internamente podría tener:

```text
CATALOGO_SERVICE_URL=http://catalogo-service:3000
```

El Gateway reenvía:

```text
GET /api/catalogo/eventos
```

### Paso 3 — Microservicio

Catálogo procesa la petición y responde.

### Paso 4 — Gateway

El Gateway recibe la respuesta y la devuelve al front.

### Paso 5 — Front

El navegador recibe los datos y actualiza la interfaz.

Flujo completo:

```text
Navegador
   │
   │ GET /api/catalogo/eventos
   ▼
API Gateway :8080
   │
   ▼
Microservicio Catálogo
   │
   ▼
API Gateway
   │
   ▼
Navegador
```

---

## 10. Regla importante: no acceder directamente a un microservicio

Esto está mal:

```ts
fetch("http://localhost:3002/eventos");
```

También está mal:

```ts
fetch("http://catalogo-service:3000/eventos");
```

El front nunca debe conocer esas direcciones.

Debe utilizar:

```ts
fetch(`${GATEWAY_URL}/api/catalogo/eventos`);
```

Esto permite cambiar la ubicación interna de un microservicio sin modificar el front.

---

## 11. CORS

CORS se configura centralmente en el API Gateway.

Por lo tanto, la comunicación relevante para el navegador es:

```text
Front → Gateway
```

Los microservicios no necesitan habilitar CORS específicamente para el navegador, porque el navegador no debería acceder directamente a ellos.

---

## 12. Build de producción sin Docker

Antes de compilar deben existir las variables de entorno.

En Linux, macOS o Git Bash:

```bash
cp .env.example .env.local
```

En PowerShell:

```powershell
Copy-Item .env.example .env.local
```

Después:

```bash
npm run build
npm run start
```

El front quedará disponible en:

```text
http://localhost:3000
```

### Importante sobre `NEXT_PUBLIC_*`

Las variables de Next.js cuyo nombre comienza con `NEXT_PUBLIC_` son utilizadas por código que puede ejecutarse en el navegador.

Por eso deben tener su valor correcto **antes de ejecutar**:

```bash
npm run build
```

No basta con cambiar la variable después de que el proyecto ya fue compilado.

---

## 13. Docker

El front tiene su propio `Dockerfile` y `docker-compose.yml`.

El API Gateway tiene otro `docker-compose.yml`. RabbitMQ también se levanta desde el repositorio de backend/infraestructura. Cada uno de los 9 microservicios tendrá su propio `docker-compose.yml`.

Aun así, todos forman parte del mismo ecosistema.

### 13.1 Crear la red compartida

Todos los componentes utilizan una red externa llamada:

```text
plataforma-eventos-net
```

Debe crearse una sola vez por máquina:

```bash
docker network create plataforma-eventos-net
```

Si ya existe, no es necesario volver a crearla.

### 13.2 Configurar el Gateway que utilizará el front

Para Docker Compose, creen `.env` a partir del ejemplo.

En Linux, macOS o Git Bash:

```bash
cp .env.example .env
```

En PowerShell:

```powershell
Copy-Item .env.example .env
```

Por defecto contiene:

```env
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080
```

Luego ejecuten:

```bash
docker compose up --build
```

El front quedará disponible en:

```text
http://localhost:3000
```

### 13.3 ¿Por qué `localhost:8080` y no `gateway:8080`?

Gran parte de las llamadas del front se ejecutan desde el **navegador del usuario**.

El navegador conoce direcciones como:

```text
localhost
192.168.x.x
api.midominio.cl
```

pero normalmente no conoce nombres DNS internos creados por Docker, como:

```text
gateway
catalogo-service
pagos-service
```

Por eso esto no debe utilizarse como URL pública del front:

```env
NEXT_PUBLIC_GATEWAY_URL=http://gateway:8080
```

En desarrollo local se utiliza:

```env
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080
```

El puerto `8080` del Gateway debe estar publicado hacia la máquina host.

### 13.4 Entonces, ¿para qué sirve `plataforma-eventos-net`?

La red Docker sigue siendo necesaria para la comunicación interna del backend.

Por ejemplo:

```text
API Gateway
     │
     ├── http://auth-service:3000
     ├── http://catalogo-service:3000
     ├── http://entradas-service:3000
     ├── http://pagos-service:3000
     └── ...
```

Esos nombres sí funcionan porque Gateway y microservicios están dentro de la misma red Docker.

Por eso todos los `docker-compose.yml` deben declarar:

```yaml
networks:
  plataforma-eventos-net:
    external: true
```

### 13.5 Desarrollo local

Si todo se ejecuta en el mismo computador:

```text
Front:    http://localhost:3000
Gateway:  http://localhost:8080
```

Entonces:

```env
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080
```

### 13.6 Ambiente remoto

Si el proyecto se despliega en un servidor, no utilicen automáticamente `localhost:8080`, porque para una persona que abre TicketU desde otro computador, `localhost` sería su propio computador.

En ese caso debe utilizarse una dirección accesible desde el navegador, por ejemplo:

```text
http://192.168.1.50:8080
```

o:

```text
https://api.ticketu.cl
```

dependiendo del ambiente utilizado por el curso.

---

## 14. Orden para levantar TicketU con Docker

La primera vez:

```bash
docker network create plataforma-eventos-net
```

Después:

1. Levantar RabbitMQ desde el repositorio de backend.
2. Levantar el único API Gateway compartido.
3. Levantar los microservicios disponibles.
4. Levantar el front:

```bash
docker compose up --build
```

---

## 15. Gateway y RabbitMQ cumplen funciones distintas

Para comunicación HTTP:

```text
Front → Gateway → Microservicio
```

Para comunicación asíncrona entre microservicios:

```text
Microservicio → RabbitMQ → otro microservicio
```

Ejemplo:

```text
Pagos
  │
  │ publica pago.realizado
  ▼
RabbitMQ
  │
  ▼
Notificaciones
```

RabbitMQ no reemplaza al Gateway.

El Gateway se utiliza para peticiones HTTP que necesitan una respuesta. RabbitMQ se utiliza para publicar eventos que pueden ser procesados de forma asíncrona por otros servicios.

El front **no se conecta directamente a RabbitMQ**.

---

## 16. Reglas principales del front

1. El front conoce **una sola URL de backend**: `NEXT_PUBLIC_GATEWAY_URL`.
2. Nunca se escriben directamente URLs de microservicios.
3. Cada módulo utiliza `GATEWAY_URL + /api/<modulo>/...`.
4. Los paths oficiales son:

```text
/api/auth
/api/catalogo
/api/entradas
/api/pagos
/api/checkin
/api/resenas
/api/organizador
/api/notificaciones
/api/promociones
```

5. CORS se configura en el Gateway.
6. Todos los componentes Docker del ecosistema utilizan `plataforma-eventos-net`.
7. Cada grupo mantiene la lógica de su propio módulo.
8. Las modificaciones a componentes compartidos deben coordinarse entre los grupos o con el Platform Team.
