# 🎟️ TicketU - Backend API (Entradas e Inventario)

Bienvenido a la rama `backend` del microservicio de **Entradas e Inventario** del proyecto TicketU. Esta rama contiene exclusivamente el código fuente y las integraciones API de nuestro módulo, desarrollado con **FastAPI**.

## 👥 Responsable del Rol Backend
* **Esteban Quinteros** - Desarrollador Backend

## 🛠️ Stack Tecnológico
* **Framework:** FastAPI (Python 3.14+)
* **Servidor ASGI:** Uvicorn
* **Validación de Datos:** Pydantic
* **Cliente HTTP Asíncrono:** HTTPX (para invocación a otros microservicios)

---

## 📦 Resumen de esta Rama (Evaluación 1)

Esta rama ha sido adaptada y limpiada estrictamente para cumplir con la Rúbrica de la Evaluación 1, cubriendo al 100% los ítems **BE1**, **BE2** y **BE3**:

1. **BE1 (Servicios Propios):** Se implementaron los endpoints principales para soportar las historias de usuario **HU-01** (Visualización de disponibilidad) y **HU-02** (Selección y reserva), incluyendo lógicas de negocio, límites de compra y enrutamiento inteligente (gratuito vs. pago). Documentación OpenAPI (Swagger) autogenerada.
2. **BE2 (Invocación a Servicios Externos):** Implementación de la capa `services/` utilizando la librería `httpx` para realizar llamadas asíncronas hacia los módulos dependientes, respetando los contratos oficiales:
   * `CatalogoService`: Actualización estricta de stock vía `PUT`.
   * `PromocionesService`: Consulta de descuentos aplicables según reglas de negocio.
   * `PagosService`: Inicio de la orden de cobro.
   * `CheckinService` y `NotificacionesService`: Distribución paralela del código QR.
3. **BE3 (Servicios Requeridos por Otros):** Se expusieron endpoints tipo `GET` de solo lectura (como plan de contingencia/Pull) para que Panel Organizador, Check-in y Notificaciones puedan consultar la data estructurada que genera nuestro módulo, dejando el registro explícito en el Swagger de lo que enviamos.

---

## ⚙️ Ejecución Local (Entorno de Desarrollo)

Para levantar el servidor backend de manera local y visualizar la documentación interactiva de la API, sigue estos pasos:

### 1. Clonar el repositorio y cambiar de rama
```bash
git clone https://github.com/Microservicios-Entradas-Inventario/arquitectura_ms_entradas_inventario.git
cd arquitectura_ms_entradas_inventario
git checkout backend
```

### 2. Crear y activar el entorno virtual
Es altamente recomendado utilizar un entorno virtual para no ensuciar tu instalación global de Python.

**En Windows (PowerShell/CMD):**
```bash
python -m venv venv
.\venv\Scripts\activate
```
**En Windows (Bash/Git Bash):**
```bash
source venv/Scripts/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Levantar la Base de Datos (MongoDB)
El microservicio ahora está conectado a una base de datos MongoDB local con datos reales inicializados (semilla). Para levantar el contenedor de la base de datos junto a Mongo Express (interfaz gráfica), ejecuta:
```bash
docker compose up -d
```
*(Nota: Para detener los contenedores cuando termines, usa `docker compose down`)*

### 5. Levantar el servidor
El siguiente comando iniciará el servidor utilizando Uvicorn con modo de recarga automática (`--reload`), útil para ver cambios en tiempo real durante el desarrollo:
```bash
uvicorn main:app --reload
```

### 6. Acceder a la Documentación (Swagger)
Una vez el servidor y la base de datos hayan arrancado exitosamente, abre tu navegador web y visita la siguiente dirección:

👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

Dentro del Swagger podrás desplegar cada endpoint, leer su documentación exhaustiva (propósitos, parámetros, flujos y códigos HTTP) y probar la comunicación interactiva mediante el botón "Try it out".
