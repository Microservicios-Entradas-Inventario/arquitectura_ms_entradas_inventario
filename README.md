# 🎟️ TicketU - Microservicio de Entradas e Inventario

Microservicio central del ecosistema **TicketU** (plataforma de venta y gestión de eventos para la comunidad de Ingeniería Civil Informática y la universidad en general). Este módulo es responsable de la administración del aforo, la reserva temporal de cupos, la consolidación de compras y la emisión definitiva de tickets con código QR.

El proyecto está construido bajo una arquitectura de microservicios, operando con su propia base de datos independiente (*Database per Service*) y comunicándose con el resto del sistema mediante el API Gateway (REST) y un broker de eventos asíncronos.

## 👥 Equipo de Desarrollo (Grupo 3)
* **Sebastián Fuentes** - Scrum Master
* **Felipe Castro** - Desarrollador Frontend
* **Renato Herrera** - Desarrollador Base de datos
* **Esteban Quinteros** - Desarrollador Backend
* **Bastián Parra** - QA

## 🛠️ Stack Tecnológico
* **Backend:** Node.js
* **Base de Datos:** MongoDB
* **Mensajería Asíncrona:** RabbitMQ (Broker de eventos)
* **Infraestructura:** Docker & Docker Compose (Despliegue On-Premise)

---

## 📂 Estructura de Documentación

Toda la documentación ágil, requerimientos y definiciones de arquitectura técnica se encuentran versionadas en este repositorio.

### 📖 Historias de Usuario (Backlog)
El alcance funcional del microservicio está definido en 9 historias de usuario principales, gestionadas y trazadas a través de los *Milestones* de este repositorio:
1. **HU-01:** Visualización de disponibilidad y tipo de entrada.
2. **HU-02:** Selección de entradas para adquisición.
3. **HU-03:** Reserva temporal de cupo (Hold).
4. **HU-04:** Visualización de detalles de la entrada adquirida.
5. **HU-05:** Recepción de código QR de acceso.
6. ~~**HU-06:** Ajuste manual de stock por el administrador.~~
7. **HU-07:** Solicitud de notificación por stock agotado.
8. **HU-08:** Límite de obtención de entradas gratuitas.
9. **HU-09:** Emisión definitiva tras pago aprobado.

### 🤝 Contratos de Interfaz (OpenAPI / REST / Eventos)
Para asegurar la interoperabilidad sin acoplamiento, este servicio mantiene contratos estrictos (ubicados en la carpeta `/docs/contratos`) con los siguientes equipos:
* **Catálogo de Eventos:** Contrato para procesar la intención de compra del cliente (recibir datos) y contrato de distribución paralela para enviar el stock actualizado.
* **Pagos:** Contrato para enviar órdenes valorizadas y recibir la confirmación (éxito/rechazo) de la transacción financiera.
* **Panel Organizador:** Contrato de carga inicial de stock al momento de crear un evento y consulta (Pull) de validación de datos maestros.
* **Auth:** Validación segura de tokens de sesión para obtener la identidad real del comprador (nombre y correo).
* **Check-in & Notificaciones:** Distribución paralela del QR generado para el control en puerta y el envío por correo electrónico al usuario.

---

## 🚀 Planificación y Entregas (Sprints)
El desarrollo está estructurado en 4 Sprints iterativos, alineados con las entregas y presentaciones oficiales del semestre:

* **Sprint 1 (Avance 1 - 01/10):** Base de Datos, Stock y Selección (HU-06, HU-01, HU-02).
* **Sprint 2 (Avance 2 - 22/10):** Ciclo de Reserva y Emisión de Entradas (HU-03, HU-04, HU-05).
* **Sprint 3 (Avance 3 - 05/11):** Asincronía (RabbitMQ) y Reglas de Negocio (HU-07, HU-09, HU-08).
* **Sprint 4 (Entrega Final - 25/11):** Integración E2E a través del API Gateway, Estabilización y Despliegue On-Premise.

---

## ⚙️ Ejecución Local (Desarrollo)

```bash
# 1. Clonar el repositorio
git clone https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario.git

# 2. Entrar al directorio del servicio
cd ticketu-entradas

# 3. Copiar el archivo de variables de entorno y configurar credenciales
cp .env.example .env

# 4. Levantar los servicios con Docker Compose (Node.js + MongoDB local)
docker-compose up --build
