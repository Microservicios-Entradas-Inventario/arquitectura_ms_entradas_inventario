# Diccionario de Datos — Microservicio de Entradas e Inventario (`ticketu_entradas_db`)

- **Motor de Base de Datos:** MongoDB 7.0.43
- **Base de Datos:** `ticketu_entradas_db` (instancia dedicada en red aislada `entradas-internal-net`)
- **Fecha de extracción automática:** `2026-11-23 19:10:20 UTC`
- **Script de creación de la BD (referencia oficial):** [`scripts/init_db_creacion_bd.js`](../scripts/init_db_creacion_bd.js)
- **Script generador de este diccionario:** [`scripts/generar_diccionario_datos.py`](../scripts/generar_diccionario_datos.py)
- **Criterios de rúbrica cubiertos:** **BD3** (Nomenclatura y documentación) y **BD4** (Diseño técnico: PK, FK, tipos, nulabilidad, índices y sin ciclos).

---

## 1. Estándares de Nomenclatura Aplicados (BD3)

| Elemento | Convención oficial | Ejemplos reales verificados en MongoDB |
| :--- | :--- | :--- |
| **Base de datos** | `snake_case` con prefijo de plataforma y dominio | `ticketu_entradas_db` |
| **Colecciones** | `snake_case`, sustantivo singular descriptivo | `inventario_evento`, `reserva_entrada`, `entrada` |
| **Atributos** | `snake_case` en español sin tildes | `id_evento`, `precio_unitario`, `estado_reserva`, `fecha_emision` |
| **Llaves primarias de negocio** | Prefijo `id_` + índice único `pk_<entidad>_<campo>` | `pk_inventario_id_evento`, `pk_reserva_id_reserva`, `pk_entrada_id_entrada` |
| **Llaves foráneas internas** | Mismo nombre del identificador referenciado + índice `fk_*` o `idx_*` | `fk_reserva_inventario_evento`, `fk_entrada_reserva`, `idx_entrada_evento` |
| **Índices secundarios** | Prefijo `idx_<entidad>_<propósito>` | `idx_inventario_organizador`, `idx_reserva_estado_expiracion`, `idx_reserva_id_pago`, `idx_entrada_usuario` |
| **Estados y tipos (ENUM)** | `UPPER_SNAKE_CASE` (roles aceptan normalización Auth en minúsculas/mayúsculas) | `PAGADA`, `GRATUITA`, `PUBLICADO`, `RESERVADO`, `CONSOLIDADO`, `EMITIDA`, `ANULADA` |
| **Prefijos de identificadores** | Prefijo semántico de entidad | `evt-*`, `res-*` / `hold-*`, `tk-*`, `usr-*`, `pay-*`, `promo-*` |
| **Política de esquema estricto** | `$jsonSchema` con `additionalProperties: false` en las 3 colecciones | Impide persistir campos no declarados, tokens JWT o entidades de otros squads |

---

## 2. Resumen General de Colecciones

| # | Colección | Nivel DAG | Documentos semilla | Atributos documentados | Obligatorios (`required`) | Índices | `additionalProperties` |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | `inventario_evento` | Nivel 0 (Raíz) | 11 | 18 | 12 | 3 | `false` |
| 2 | `reserva_entrada` | Nivel 1 (Intermedio) | 7 | 19 | 13 | 6 | `false` |
| 3 | `entrada` | Nivel 2 (Hoja) | 3 | 17 | 12 | 5 | `false` |

**Totales verificados:** `3` colecciones propias del dominio Entradas · `54` atributos documentados (100% de cobertura) · `14` índices totales · `0` colecciones de otros microservicios.

---

## 3. Detalle por Colección

### 3.1. Colección `inventario_evento`

Administra el inventario de cupos, tarifas unitarias, límites por compra y estado operativo de venta por evento. Constituye la colección raíz (Nivel 0) del grafo relacional y se sincroniza con Panel Organizador y Catálogo de Eventos mediante el identificador `id_evento`.

- **Validador activo:** `$jsonSchema` (`additionalProperties: false`)
- **Documentos registrados en semilla oficial:** `11`

#### Atributos

| Atributo | Tipo BSON | Nulabilidad | Llave / Referencia | Restricciones / Dominio | Origen / Descripción |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `_id` | `objectId` | **NOT NULL** | ID (PK interna) | — | **MongoDB (Entradas).** Identificador interno autogenerado por MongoDB (`ObjectId`). |
| `id_evento` | `string` | **NOT NULL** | PK / FK Ext (Panel, Catálogo) | — | **Referencia externa → Panel Organizador / Catálogo.** Identificador único de negocio del evento. Índice único `pk_inventario_id_evento`. Referenciado desde `reserva_entrada` y `entrada`. |
| `nombre_evento` | `string` | NULLABLE | - | — | **Sincronización Panel (snapshot operativo).** Título descriptivo del evento sincronizado para visualización de inventario y comprobante de emisión. |
| `descripcion` | `string` | NULLABLE | - | — | **Sincronización Panel (snapshot operativo).** Descripción resumida del evento recibida en eventos `panel.evento.entradas.v1`. |
| `fecha_evento` | `string` | NULLABLE | - | — | **Sincronización Panel (snapshot operativo).** Fecha programada del evento en formato `YYYY-MM-DD`, requerida también para el payload del evento `entradas_emitidas` hacia Notificaciones. |
| `hora_evento` | `string` | NULLABLE | - | — | **Sincronización Panel (snapshot operativo).** Hora de inicio del evento en formato `HH:MM`, requerida para detalle de entrada (HU-04) y Notificaciones. |
| `lugar_ingreso` | `string` | NULLABLE | - | — | **Sincronización Panel (snapshot operativo).** Ubicación o punto de acceso al recinto para mostrar en la entrada adquirida (HU-04/HU-05). |
| `id_usuario` | `string` | **NOT NULL** | FK Ext (Auth) | — | **Referencia externa → Auth.** Identificador de referencia del organizador o staff responsable de gestionar el inventario del evento. |
| `rol_usuario` | `string` | **NOT NULL** | IDX compuesto | ENUM: `ORGANIZADOR`, `organizador`, `STAFF`, `staff` | **Referencia rol Auth.** Rol autorizado del gestor del inventario (`ORGANIZADOR` / `STAFF`). Parte del índice `idx_inventario_organizador`. |
| `tipo_entrada` | `string` | **NOT NULL** | - | ENUM: `PAGADA`, `GRATUITA` | **Entradas (Dominio propio).** Modalidad comercial del inventario: `PAGADA` (requiere Hold + Pagos) o `GRATUITA` (emisión directa `$0`). |
| `precio_unitario` | `int` | **NOT NULL** | - | `>= 0` | **Entradas (Dominio propio).** Valor unitario en pesos chilenos (CLP entero `>= 0`). Para eventos `GRATUITA` es `0`. |
| `stock_inicial` | `int` | **NOT NULL** | - | `>= 0` | **Entradas (Dominio propio).** Capacidad total de entradas asignadas inicialmente al evento (`>= 0`). |
| `stock_actual` | `int` | **NOT NULL** | - | `>= 0` | **Entradas (Dominio propio).** Cupos disponibles en tiempo real (`>= 0`). Cumple invariante: `stock_inicial = stock_actual + cantidad_entrada_reservada + cantidad_entrada_comprada`. |
| `cantidad_entrada_reservada` | `int` | **NOT NULL** | - | `>= 0` | **Entradas (Dominio propio).** Cupos retenidos temporalmente en reservas activas (`estado_reserva = RESERVADO`). |
| `cantidad_entrada_comprada` | `int` | **NOT NULL** | - | `>= 0` | **Entradas (Dominio propio).** Total acumulado de entradas vendidas/emitidas definitivamente (`CONSOLIDADO`). |
| `maximo_ticket` | `int` | **NOT NULL** | - | `>= 1` | **Entradas (Dominio propio).** Límite máximo de entradas permitidas por transacción o solicitud (`>= 1`). |
| `estado_gestion` | `string` | **NOT NULL** | - | ENUM: `BORRADOR`, `PUBLICADO`, `FINALIZADO`, `CANCELADO` | **Entradas / Sincronización Panel.** Estado del ciclo de vida del inventario: `BORRADOR`, `PUBLICADO`, `FINALIZADO` o `CANCELADO`. Solo `PUBLICADO` admite compras/reservas. |
| `fecha_actualizacion` | `date` | **NOT NULL** | - | — | **Entradas (Auditoría).** Marca de tiempo UTC (`ISODate`) de la última sincronización o actualización del inventario. |

#### Índices configurados

| Nombre del índice | Campos y orden | Único | Propósito técnico |
| :--- | :--- | :---: | :--- |
| `_id_` | `_id: ASC (1)` | Sí (`unique: true`) | Índice primario interno automático de MongoDB. |
| `pk_inventario_id_evento` | `id_evento: ASC (1)` | Sí (`unique: true`) | Garantiza unicidad de negocio por `id_evento` y acelera búsquedas O(log n) de disponibilidad/stock. |
| `idx_inventario_organizador` | `id_usuario: ASC (1)`, `rol_usuario: ASC (1)` | No | Acelera consultas de inventario filtradas por organizador y rol. |

### 3.2. Colección `reserva_entrada`

Registra las reservas temporales de cupo (Hold, HU-03) y las órdenes consolidadas o liberadas de compra. Descuenta stock atómicamente, persiste el cálculo validado de descuento con Promociones y mantiene el vínculo con la Pasarela de Pagos (`id_pago`). No utiliza índice TTL destructivo ni almacena cookies JWT ni secretos de pago.

- **Validador activo:** `$jsonSchema` (`additionalProperties: false`)
- **Documentos registrados en semilla oficial:** `7`

#### Atributos

| Atributo | Tipo BSON | Nulabilidad | Llave / Referencia | Restricciones / Dominio | Origen / Descripción |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `_id` | `objectId` | **NOT NULL** | ID (PK interna) | — | **MongoDB (Entradas).** Identificador interno autogenerado por MongoDB (`ObjectId`). |
| `id_reserva` | `string` | **NOT NULL** | PK | — | **Entradas (Dominio propio).** Identificador único de negocio de la reserva (`res-*` o `hold-*`). Índice único `pk_reserva_id_reserva`. Consultado por Pagos en INT-01. |
| `hold_id` | `string` | NULLABLE | - | — | **Entradas (Dominio propio).** Alias opcional de reserva temporal (HU-03) para trazabilidad con el frontend y Pagos. |
| `id_evento` | `string` | **NOT NULL** | FK → inventario_evento.id_evento | — | **Referencia interna y externa (Panel/Catálogo).** Llave foránea hacia `inventario_evento.id_evento`. Indexada mediante `fk_reserva_inventario_evento` e `idx_reserva_usuario_evento`. |
| `id_usuario` | `string` | **NOT NULL** | FK Ext (Auth) | — | **Referencia externa → Auth.** Identificador de referencia del comprador obtenido exclusivamente mediante introspección de sesión en Auth (`/internal/validar-sesion`). |
| `nombre_usuario` | `string` | **NOT NULL** | - | — | **Proyección sesión Auth (comprobante/Check-in).** Nombre del asistente titular al momento de la reserva para emisión de ticket, registro en Check-in y correo de Notificaciones. |
| `rut_usuario` | `string` | NULLABLE | - | — | **Proyección sesión Auth (opcional).** RUT referencial del asistente si fue informado por Auth en la introspección de sesión. |
| `correo_usuario` | `string` | NULLABLE | - | — | **Proyección sesión Auth (Notificaciones).** Correo electrónico de entrega utilizado para publicar el evento `entradas_emitidas` hacia Notificaciones. |
| `rol_usuario` | `string` | **NOT NULL** | - | ENUM: `USUARIO`, `STAFF`, `ORGANIZADOR`, `usuario`, `staff`, `organizador` | **Referencia rol Auth.** Rol del usuario que realiza la reserva (`usuario`, `staff`, `organizador` y variantes en mayúsculas). |
| `cantidad_entrada` | `int` | **NOT NULL** | - | `>= 1` | **Entradas (Dominio propio).** Número de cupos reservados en la orden (`>= 1`, máximo según `maximo_ticket` y contrato Pagos `<= 100`). |
| `id_promocion` | `string` | NULLABLE | FK Ext (Promociones) | — | **Referencia externa → Promociones.** Identificador de referencia de la promoción validada por `POST /api/promociones/evaluar` (`null` si no aplica descuento). |
| `nombre_codigo` | `string` | NULLABLE | - | — | **Referencia contrato Pagos/Promociones.** Código promocional validado (ej. `ESTUDIANTE15`) expuesto a Pagos en `GET /api/entradas/reservas/{id_reserva}` (INT-01) para propagación a `pago.completado`. |
| `porcentaje_descuento` | `int` | **NOT NULL** | - | `>= 0`; `<= 100` | **Entradas (Cálculo validado server-side).** Porcentaje de descuento entero (`0..100`) revalidado server-side con Promociones (`0` si no aplica). |
| `monto_total` | `int` | **NOT NULL** | - | `>= 0` | **Entradas (Dominio propio).** Monto total final a pagar en CLP (`>= 0`), calculado como `precio_unitario * cantidad_entrada * (1 - porcentaje_descuento/100)`. Validado por Pagos en INT-01. |
| `id_pago` | `string` | NULLABLE | FK Ext (Pagos) | — | **Referencia externa → Pasarela de Pagos.** Identificador de referencia de la transacción en Pagos (`pay-*`). `null` en reservas gratuitas o antes de iniciar pago. Indexado por `idx_reserva_id_pago`. |
| `estado_reserva` | `string` | **NOT NULL** | IDX compuesto | ENUM: `RESERVADO`, `CONSOLIDADO`, `EXPIRADO`, `CANCELADO` | **Entradas (Máquina de estados).** Estado de la reserva: `RESERVADO` (hold activo), `CONSOLIDADO` (pagada/emitida), `EXPIRADO` (vencida/rechazada) o `CANCELADO` (cancelada por usuario/reembolso). |
| `fecha_cancelacion` | `date` | NULLABLE | - | — | **Entradas (Auditoría).** Marca de tiempo UTC de cancelación manual o expiración automática por el worker de liberación. |
| `fecha_creacion` | `date` | **NOT NULL** | - | — | **Entradas (Auditoría).** Marca de tiempo UTC de creación de la reserva. |
| `fecha_expiracion` | `date` | NULLABLE | IDX compuesto | — | **Entradas (Control Hold HU-03).** Fecha límite UTC del Hold temporal (`null` cuando la reserva ya está `CONSOLIDADO`). Monitoreada por el worker en segundo plano usando `idx_reserva_estado_expiracion` (sin TTL destructivo). |

#### Índices configurados

| Nombre del índice | Campos y orden | Único | Propósito técnico |
| :--- | :--- | :---: | :--- |
| `_id_` | `_id: ASC (1)` | Sí (`unique: true`) | Índice primario interno automático de MongoDB. |
| `pk_reserva_id_reserva` | `id_reserva: ASC (1)` | Sí (`unique: true`) | Garantiza unicidad de negocio por `id_reserva` (consultado por Pagos INT-01 y Checkout). |
| `fk_reserva_inventario_evento` | `id_evento: ASC (1)` | No | Soporta integridad referencial y `$lookup` hacia `inventario_evento`. |
| `idx_reserva_usuario_evento` | `id_usuario: ASC (1)`, `id_evento: ASC (1)` | No | Optimiza búsquedas de reservas por comprador y evento. |
| `idx_reserva_estado_expiracion` | `estado_reserva: ASC (1)`, `fecha_expiracion: ASC (1)` | No | Optimiza el barrido periódico del worker de expiración de Holds (`RESERVADO` + `fecha_expiracion < ahora`) sin borrado TTL destructivo. |
| `idx_reserva_id_pago` | `id_pago: ASC (1)` | No | Acelera la correlación con transacciones reportadas por Pagos (`pago.realizado`, `pago.rechazado`, polling). |

### 3.3. Colección `entrada`

Almacena de forma inmutable cada ticket emitido tras la consolidación de un pago o emisión directa gratuita (HU-04 y HU-05), junto con su código QR estructurado (`qr_data`) para control de acceso en puerta por Check-in y entrega por Notificaciones.

- **Validador activo:** `$jsonSchema` (`additionalProperties: false`)
- **Documentos registrados en semilla oficial:** `3`

#### Atributos

| Atributo | Tipo BSON | Nulabilidad | Llave / Referencia | Restricciones / Dominio | Origen / Descripción |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `_id` | `objectId` | **NOT NULL** | ID (PK interna) | — | **MongoDB (Entradas).** Identificador interno autogenerado por MongoDB (`ObjectId`). |
| `id_entrada` | `string` | **NOT NULL** | PK / FK Ext (Check-in) | — | **Entradas (Dominio propio).** Código único e inmutable del ticket emitido (`tk-*`). Índice único `pk_entrada_id_entrada`. Referenciado por Check-in para validación en torniquete. |
| `id_reserva` | `string` | **NOT NULL** | FK → reserva_entrada.id_reserva | — | **Entradas (Integridad referencial).** Llave foránea hacia la reserva consolidada que originó el ticket. Indexada por `fk_entrada_reserva`. |
| `id_evento` | `string` | **NOT NULL** | FK → inventario_evento.id_evento | — | **Referencia interna y externa (Panel/Check-in).** Llave foránea directa hacia `inventario_evento.id_evento` (misma dirección topológica del DAG, sin ciclos). Indexada por `idx_entrada_evento`. |
| `nombre_evento` | `string` | NULLABLE | - | — | **Snapshot inmutable de comprobante (HU-04).** Título del evento congelado al instante de emisión del ticket para consulta histórica inmutable. |
| `id_usuario` | `string` | **NOT NULL** | FK Ext (Auth) | — | **Referencia externa → Auth.** Identificador de referencia del titular de la entrada. Parte del índice `idx_entrada_usuario` (`{id_usuario: 1, fecha_emision: -1}`). |
| `nombre_usuario` | `string` | **NOT NULL** | - | — | **Snapshot inmutable de comprobante / Check-in.** Nombre del asistente acreditado en el comprobante inmutable y devuelto en el contrato HTTP hacia Check-in (`GET /api/entradas/{id_ticket}`). |
| `rut_usuario` | `string` | NULLABLE | - | — | **Snapshot inmutable de comprobante (opcional).** RUT del asistente titular capturado al momento de emitir el comprobante. |
| `correo_usuario` | `string` | NULLABLE | - | — | **Snapshot inmutable de comprobante (opcional).** Correo del asistente titular utilizado en la notificación de emisión. |
| `rol_usuario` | `string` | **NOT NULL** | - | ENUM: `USUARIO`, `STAFF`, `ORGANIZADOR`, `usuario`, `staff`, `organizador` | **Referencia rol Auth.** Rol del titular acreditado devuelto a Check-in (`usuario`, `staff`, `organizador`). |
| `tipo_acceso` | `string` | **NOT NULL** | - | ENUM: `GENERAL` | **Entradas (Dominio propio).** Categoría de acceso físico del ticket. Valor permitido actual: `GENERAL`. |
| `lugar_ingreso` | `string` | NULLABLE | - | — | **Snapshot inmutable de comprobante (HU-04/05).** Puerta o sector de ingreso al recinto mostrado en el pase digital. |
| `precio_final_pagado` | `int` | **NOT NULL** | - | `>= 0` | **Entradas (Inmutable financiero).** Precio unitario final efectivamente pagado en CLP (`>= 0`), persistido de forma inmutable al emitir el ticket. |
| `estado_entrada` | `string` | **NOT NULL** | - | ENUM: `EMITIDA`, `ANULADA` | **Entradas (Ciclo de vida ticket).** Estado operativo de la entrada: `EMITIDA` (habilitada para QR/Check-in) o `ANULADA` (inhabilitada). |
| `nombre_archivo_qr` | `string` | **NOT NULL** | - | — | **Entradas (Dominio propio).** Nombre de archivo asociado a la representación gráfica del QR (`<id_entrada>.png`). |
| `qr_data` | `object` | **NOT NULL** | - | Subdocumento (`url: string`, `hash: string`; required: `url, hash`) | **Entradas / Contrato Check-in (HU-05).** Subdocumento BSON obligatorio con `url` (URL del código QR que codifica JSON `{id_entrada, id_evento}`) y `hash` (huella de verificación). |
| `fecha_emision` | `date` | **NOT NULL** | IDX compuesto | — | **Entradas (Auditoría).** Marca de tiempo UTC de emisión definitiva del ticket. Usada para orden descendente en `idx_entrada_usuario`. |

#### Subdocumentos embebidos

| Subatributo (`qr_data.*`) | Tipo BSON | Nulabilidad | Descripción |
| :--- | :--- | :---: | :--- |
| `qr_data.url` | `string` | **NOT NULL** | URL generadora del código QR que codifica el payload JSON `{"id_entrada","id_evento"}` para lectura en torniquete por Check-in. |
| `qr_data.hash` | `string` | **NOT NULL** | Huella hexadecimal corta de verificación e integridad del QR emitido. |

#### Índices configurados

| Nombre del índice | Campos y orden | Único | Propósito técnico |
| :--- | :--- | :---: | :--- |
| `_id_` | `_id: ASC (1)` | Sí (`unique: true`) | Índice primario interno automático de MongoDB. |
| `pk_entrada_id_entrada` | `id_entrada: ASC (1)` | Sí (`unique: true`) | Garantiza unicidad e inmutabilidad por `id_entrada` (consultado por Check-in y QR). |
| `fk_entrada_reserva` | `id_reserva: ASC (1)` | No | Soporta integridad referencial y `$lookup` hacia `reserva_entrada`. |
| `idx_entrada_evento` | `id_evento: ASC (1)` | No | Soporta integridad referencial directa hacia `inventario_evento` y reportes por evento. |
| `idx_entrada_usuario` | `id_usuario: ASC (1)`, `fecha_emision: DESC (-1)` | No | Optimiza historial `GET /api/entradas/mis-entradas` ordenado cronológicamente descendente (HU-04). |

---

## 4. Mapa de Integridad Referencial Interna y Referencias Externas (BD2 y BD4)

### 4.1. Relaciones internas (Grafo Acíclico Dirigido — 0 ciclos)

| Colección padre (1) | Colección hija (0..N) | Campo FK | Índice en hija | Dirección topológica |
| :--- | :--- | :--- | :--- | :--- |
| `inventario_evento.id_evento` | `reserva_entrada.id_evento` | `id_evento` | `fk_reserva_inventario_evento` | Nivel 0 → Nivel 1 |
| `reserva_entrada.id_reserva` | `entrada.id_reserva` | `id_reserva` | `fk_entrada_reserva` | Nivel 1 → Nivel 2 |
| `inventario_evento.id_evento` | `entrada.id_evento` | `id_evento` | `idx_entrada_evento` | Nivel 0 → Nivel 2 |

### 4.2. Referencias externas hacia otros microservicios

| Microservicio contraparte | Identificador de referencia | Colección(es) en Entradas | ¿Se replican colecciones o credenciales? |
| :--- | :--- | :--- | :---: |
| **Panel Organizador & Catálogo** | `id_evento` | `inventario_evento`, `reserva_entrada`, `entrada` | **No** (solo ID y snapshot operativo) |
| **Autenticación (Auth)** | `id_usuario` | `inventario_evento`, `reserva_entrada`, `entrada` | **No** (0 passwords, 0 JWT en BD) |
| **Promociones** | `id_promocion` | `reserva_entrada` | **No** (0 reglas de cupones; revalidación server-side) |
| **Pasarela de Pagos** | `id_pago` (y `id_reserva` en INT-01) | `reserva_entrada` | **No** (0 tarjetas, 0 `client_secret`) |
| **Check-in** | `id_entrada`, `id_evento` (payload QR) | `entrada` | **No** (estado de torniquete vive en MySQL de Check-in) |
| **Notificaciones** | `id_usuario`, `id_evento`, `qr_data` | `entrada` (publicación RabbitMQ) | **No** (logs de correo viven en Notificaciones) |
