# Entrega de Integración Frontend + Backend — Módulo Catálogo de Eventos (Equipo 2 / 7) ↔ Entradas (Grupo 3)

Este documento detalla los archivos ajustados y el flujo de demostración para conectar el microservicio **`ms-catalogo-eventos`** (`:4000`), el microservicio **`entradas-service`** (`:3003->:3000`) y el Frontend unificado **`FrontendTitec-main`** (`:3000`) a través del **API Gateway** (`:8080`).

---

## 1. Archivos Modificados en el Backend de Catálogo (`catalogo/ms-catalogo-eventos-main`)

| # | Archivo | Qué se solucionó |
| :--- | :--- | :--- |
| **1** | [`.env`](../../catalogo/ms-catalogo-eventos-main/.env) | Creado a partir de `.env.example` para que `docker compose up -d --build` levante sin error de `env_file` faltante en el puerto `4000` dentro de la red `plataforma-eventos-net` (con alias `catalogo-service` y `ms-catalogo-eventos`). |
| **2** | [`src/config/supabase.js`](../../catalogo/ms-catalogo-eventos-main/src/config/supabase.js) | Se agregó un motor de base de datos local persistente (`/tmp/catalogo_eventos_db.json`) con la misma interfaz encadenable de Supabase (`from('eventos').select().or().eq().in().gte().lt().lte().order().range().single()` y `update()`). Si no hay credenciales cloud de Supabase en `.env`, utiliza automáticamente esta BD local pre-cargada con los eventos sincronizados con `entradas-service` (`evt-101`, `evt-102`, `evt-103`, `evt-104`, `evt-105`, `evt-109`, `evt-001`, `evt-002`, `evt-003`, `evt-004`, `evt-77889`) y con fechas futuras vigentes para que los botones **Reservar / Comprar** estén activos. |

---

## 2. Archivos Modificados en el Frontend General (`repoAyu/FrontendTitec-main`)

| # | Ruta donde pegar en `FrontendTitec-main` | Qué se solucionó |
| :--- | :--- | :--- |
| **1** | `src/modules/catalogo/api.ts` | Como `CatalogoPlaceholder` y `DetalleEventoPlaceholder` son **Server Components** de Next.js (`async function`), al ejecutarse dentro del contenedor Docker `front`, `http://localhost:8080` apuntaba al propio contenedor `front` y fallaba con `ECONNREFUSED`. Se agregó `fetchDesdeCatalogo()` que en servidor resuelve `http://ticketu-api-gateway:8080` (y `http://catalogo-service:4000`) en la red Docker `plataforma-eventos-net`, y en el navegador usa `GATEWAY_URL` (`http://localhost:8080`). |
| **2** | `src/app/catalogo/page.tsx` | Se agregó `export const dynamic = "force-dynamic";` para evitar que Next.js congele una vista estática durante el `docker build` y consulte siempre el stock actualizado a `ms-catalogo-eventos`. |
| **3** | `src/app/catalogo/[eventoId]/page.tsx` | Se agregó `export const dynamic = "force-dynamic";` para que la ficha de detalle `/catalogo/[eventoId]` refleje en tiempo real cada descuento o liberación de stock proveniente de `entradas-service`. |
| **4** | `src/modules/catalogo/components/DetalleEventoPlaceholder.tsx` | Se insertó el bloque `<DisponibilidadPlaceholder eventoId={evento.id_evento} />` (Grupo 3) junto a la información de Catálogo y al botón **Reservar / Comprar** que redirige a `/entradas?eventoId={id_evento}`. |

---

## 3. Cómo Demostrar la Integración en Vivo (Frontend + Catálogo + Entradas + Check-in)

1. **Abrir el Catálogo de Eventos en el navegador:**
   - Ir a: `http://localhost:3000/catalogo`
   - Se listan los eventos reales servidos por el contenedor `ms-catalogo-eventos` (`:4000`) a través del API Gateway (`:8080`).
2. **Entrar al detalle de un evento en Catálogo:**
   - Hacer clic en **"Feria de Innovación TITEC"** (`evt-101`, gratuito, **150 entradas disponibles**) o en **"Fiesta de Generación Informática"** (`evt-102`, pagado \$5.000, **300 entradas disponibles**) o **"Charla: IA y Ética"** (`evt-104`, gratuito, **8 entradas disponibles**).
   - En `http://localhost:3000/catalogo/evt-101` verás tanto el dato de **Catálogo** (`Entradas disponibles: 150`) como el widget en vivo de **Entradas** (`DisponibilidadPlaceholder`).
3. **Pasar de Catálogo a Entradas:**
   - Hacer clic en el botón **"Reservar"** (o **"Comprar"**).
   - El navegador redirige a `http://localhost:3000/entradas?eventoId=evt-101` pre-seleccionando automáticamente ese mismo evento desde MongoDB (`entradas-service`).
4. **Adquirir / Reservar entradas y ver el impacto en las 3 bases de datos:**
   - Seleccionar por ejemplo `2` entradas y hacer clic en **"Emitir Entrada Gratuita + Registrar en Check-in ➔"** (o **"Reservar Cupo (Hold)"** en un evento pagado).
   - Internamente `entradas-service`:
     1. Descuenta el stock en **MongoDB** (`150 -> 148`).
     2. Envía `PUT http://catalogo-service:4000/api/v1/catalogo/eventos/evt-101/stock` con `{"nuevo_stock": 148, "token_sesion": "..."}`, actualizando la base de datos de **Catálogo** (`150 -> 148`, y si llega a `0` cambia `estado_evento` a `"agotado"`).
     3. Envía `POST http://checkin-service:3005/api/checkin/tickets` registrando el ticket en **MySQL de Check-in**.
5. **Comprobar el cambio en Catálogo y en Check-in:**
   - Hacer clic en el botón superior **"🔎 Ver en Catálogo"** (que lleva de vuelta a `http://localhost:3000/catalogo/evt-101`): verás que **Entradas disponibles** en Catálogo bajó automáticamente de **150 a 148**.
   - Hacer clic en **"🔍 Validar en Check-in"** (que lleva a `http://localhost:3000/checkin`): puedes validar el acceso en puerta y ver cómo cambia a `INGRESADO` en MySQL.

