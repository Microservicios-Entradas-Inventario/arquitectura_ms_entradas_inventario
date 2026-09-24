# 📄 Directorio de Contratos de Interfaz - Entradas e Inventario

Este directorio centraliza las definiciones formales (contratos de API) que establecen cómo el microservicio de **Entradas e Inventario** se comunica con los demás módulos del ecosistema **TicketU**. El objetivo de estos documentos es garantizar la interoperabilidad, definir las responsabilidades (Consumidor vs. Proveedor) y estandarizar las estructuras de datos (Request/Response).

## 📌 Protocolo de Comunicación
La mayoría de las interacciones descritas en estos contratos operan de manera **síncrona** bajo el estándar **REST (HTTP)**, utilizando formato JSON para el intercambio de datos. Aquellos procesos que no requieren bloqueo (como notificaciones o sincronización final) están diseñados para operar en paralelo o delegarse a la mensajería asíncrona (RabbitMQ) según lo defina la arquitectura final.

## 📂 Listado de Contratos

### ↔️ Integración con Catálogo de Eventos
* **`Contrato_Inventario_Catalogo.docx`**: **Catálogo (Consumidor) -> Entradas (Proveedor).** Define el endpoint mediante el cual Catálogo envía la intención de compra del cliente, bloqueando el stock y esperando la confirmación final.
* **`Contrato_Entradas_Consumiendo_Catalogo.docx`**: **Entradas (Consumidor) -> Catálogo (Proveedor).** Define la actualización de estado donde Entradas informa a Catálogo el nuevo stock disponible tras una venta exitosa, para que refresque su vista.

### ↔️ Integración con Pagos
* **`Contrato_Entradas_Pagos.docx`**: **Entradas (Consumidor) -> Pagos (Proveedor).** Define el envío de la orden valorizada desde Entradas hacia Pagos, y la estructura de respuesta que confirma el éxito o rechazo de la transacción financiera con el sistema externo.

### ↔️ Integración con Promociones
* **`Contrato_Entradas_Promociones.docx`**: **Entradas (Consumidor) -> Promociones (Proveedor).** Define la consulta previa al pago donde Entradas envía los datos de la compra para que Promociones evalúe sus reglas de negocio y retorne el porcentaje de descuento a aplicar.

### ↔️ Integración con Panel Organizador
* **`Contrato_Panel_Entradas.docx`**: **Panel (Consumidor) -> Entradas (Proveedor).** Define la carga inicial (Push) donde Panel envía los datos maestros de un nuevo evento recién creado para que Entradas reserve el stock inicial en su base de datos.
* **`Contrato_Entradas_Consumiendo_Panel.docx`**: **Entradas (Consumidor) -> Panel (Proveedor).** Define la consulta (Pull) para que Entradas pueda validar detalles inmutables del evento (fecha, hora, aforo total) ante cualquier pérdida de sincronización.

### ↔️ Integración con Check-in
* **`Contrato_Entradas_Checkin.docx`**: **Entradas (Consumidor) -> Check-in (Proveedor).** Define el envío del ticket consolidado (con id, datos del usuario y código QR) para que Check-in lo registre en su base de datos y permita el escaneo rápido en puerta.

### ↔️ Integración con Notificaciones
* **`Contrato_Entradas_Notificaciones.docx`**: **Entradas (Consumidor) -> Notificaciones (Proveedor).** Define el empaquetado final de datos (correo, nombre, evento, QR) que Entradas envía para que Notificaciones despache el correo electrónico al cliente de forma asíncrona.

---

## 🛠️ Reglas de Versionado
Cualquier modificación estructural en los endpoints, requests, responses o códigos de error detallados en estos documentos **debe ser comunicada y acordada previamente con el equipo afectado**. Los cambios que rompan la compatibilidad (*breaking changes*) requerirán un cambio de versión en la URL de la API (ej. de `/api/v1/` a `/api/v2/`).
