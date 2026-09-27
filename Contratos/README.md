# 📄 Directorio de Contratos de Interfaz - Entradas e Inventario

Este directorio centraliza las definiciones formales (contratos de API) que establecen cómo el microservicio de **Entradas e Inventario** se comunica con los demás módulos del ecosistema **TicketU**. El objetivo de estos documentos es garantizar la interoperabilidad, definir las responsabilidades (Consumidor vs. Proveedor) y estandarizar las estructuras de datos (Request/Response).

## 📌 Protocolos de Comunicación (REST & RabbitMQ)
Las integraciones operan mediante un modelo híbrido adaptado a las necesidades de cada interacción:
*   **Síncrono (REST HTTP):** Utilizado para operaciones críticas que requieren bloqueo y respuesta inmediata en el flujo de compra (ej. procesar cobros, evaluar descuentos, rehidratar bases de datos y actualizar el catálogo)[cite: 19, 20, 22].
*   **Asíncrono (RabbitMQ):** Utilizado para notificaciones de estado y procesos en segundo plano que no deben bloquear al usuario (ej. sincronización de ciclo de vida del evento, resolución de pagos bancarios y notificaciones de stock agotado)[cite: 18, 22].

## 📂 Listado de Contratos y Cambios Principales

### ↔️ Integración con Catálogo de Eventos (v3.0)
*   **`Contrato_Entradas_Catalogo_REST_PUT.docx`** [Entradas (Consumidor) -> Catálogo (Proveedor)]
*   **Actualizaciones principales:** Se eliminó el uso de la petición PATCH en favor de una actualización estricta vía **PUT** HTTP REST, rechazando el uso del broker para este paso[cite: 19]. Se añadió la obligatoriedad de enviar el **token de sesión** para mantener la trazabilidad de la compra[cite: 19].

### ↔️ Integración con Pagos (v2.0 - Flujo Asíncrono)
*   **`Contrato_Entradas_Pagos_v2_Asincrono.docx`** [Entradas (Consumidor) -> Pagos (Proveedor)]
*   **Actualizaciones principales:** El contrato pasó de ser completamente síncrono a un **flujo asíncrono** debido a los tiempos de latencia de la pasarela bancaria externa[cite: 18]. Entradas inicia el cobro por REST (obteniendo un estado inicial PENDIENTE en menos de 2000 ms) y luego consolida o libera la compra escuchando pasivamente los eventos `PagoAprobado` o `PagoRechazado` emitidos por Pagos a través de RabbitMQ[cite: 18].

### ↔️ Integración con Panel Organizador (v3.0 - Acuerdo Unificado)
*   **`Contrato_Entradas_Panel_Unificado_v3.docx`** [Comunicación Bidireccional Híbrida]
*   **Actualizaciones principales:** Se unificó el glosario de términos (`tipo_entrada`, `estado_gestion`)[cite: 22]. Se adoptó **RabbitMQ** como mecanismo principal: Entradas escucha el tópico `panel.evento.entradas.v1` para bloquear ventas si el evento es cancelado, y Entradas publica en `entradas.evento.stock.v1` cuando el aforo llega a 0[cite: 22]. Se mantienen endpoints REST para fallback de datos y para que Panel valide el stock antes de eliminar un evento físicamente[cite: 22].

### ↔️ Integración con Notificaciones (v2.0)
*   **`Contrato_Entradas_Notificaciones_v2.docx`** [Entradas (Consumidor) -> Notificaciones (Proveedor)]
*   **Actualizaciones principales:** Se ajustó el payload de la petición, **eliminando el campo `cantidad_entradas`**, ya que el microservicio de Notificaciones determinó que no requería ese dato para el despacho del correo electrónico con el código QR[cite: 21].

### ↔️ Integración con Promociones (v1.0)
*   **`Contrato_Entradas_Promociones.docx`** [Entradas (Consumidor) -> Promociones (Proveedor)]
*   Define la consulta previa al pago donde Entradas envía los datos de la transacción para que Promociones evalúe sus reglas de negocio y retorne el porcentaje de descuento a aplicar (SLA < 200 ms)[cite: 20].

### ↔️ Integración con Check-in (v1.0)
*   **`Contrato_Entradas_Checkin.docx`** [Entradas (Consumidor) -> Check-in (Proveedor)]
*   Define el envío en paralelo del ticket consolidado (con id, evento, usuario y código QR) para que Check-in registre la entrada en su propia base de datos, habilitando el escaneo rápido en puerta[cite: 17].

---

## 🛠️ Reglas de Versionado
Cualquier modificación estructural en los endpoints, esquemas JSON, o eventos del broker descritos en estos documentos **debe ser comunicada y acordada previamente con el equipo afectado**. Los cambios que rompan la compatibilidad (*breaking changes*) requerirán un incremento de versión (ej. de `/v1/` a `/v2/`).
