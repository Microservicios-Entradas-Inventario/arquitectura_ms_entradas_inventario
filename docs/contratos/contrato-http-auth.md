# Contrato de Integración HTTP: Entradas e Inventario ↔ Autenticación (Auth)

**Módulos:** Entradas e Inventario (`entradas-service:3000`) ➔ Autenticación (`auth-service:10000`)  
**Red Docker Compartida:** `plataforma-eventos-net`  
**Tipo de Integración:** **Tipo C (Autenticación)** / **Tipo A (Servicio HTTP Consumido)**  
**Implementación en código:** [`back-end/services/auth_service.py`](../../back-end/services/auth_service.py), [`back-end/routers/entradas.py`](../../back-end/routers/entradas.py), [`back-end/routers/reservas.py`](../../back-end/routers/reservas.py) y [`back-end/routers/inventario.py`](../../back-end/routers/inventario.py)  

---

## 1. Propósito de la Integración

El microservicio `entradas-service` delega la validación de sesiones, verificación de firmas RSA (`RS256`), control de revocación de tokens y obtención de datos maestros del usuario al microservicio central de **Autenticación (`auth-service`)**.

Antes de procesar cualquier operación protegida (compra de entradas en `POST /api/entradas/procesar-compra`, reserva temporal en `POST /api/entradas/reservas/hold` o gestión de inventario en `POST/PUT /api/entradas/inventario`), `entradas-service` invoca el endpoint interno de introspección de Auth reenviando la cookie `jwt` del navegador y autenticándose como microservicio mediante `x-api-key`.

---

## 2. Especificación Técnica del Endpoint Consumido

| Parámetro | Valor Configurado | Descripción |
| :--- | :--- | :--- |
| **Proveedor** | `auth-service` (`ticketu-auth:1.1`) | `http://auth-service:10000` en `plataforma-eventos-net` |
| **Consumidor** | `entradas-service` | Microservicio de Entradas e Inventario |
| **Método y Ruta** | `GET /internal/validar-sesion` | Endpoint privado de introspección de sesión entre microservicios |
| **Cabecera de Sesión** | `Cookie: jwt=<token_jwt>` | Se reenvía el header `Cookie` recibido del cliente con la cookie `jwt` |
| **Cabecera de Servicio** | `x-api-key: <INTERNAL_API_KEY>` | Clave compartida entre microservicios (`INTERNAL_API_KEY`) |
| **Timeout (SLA)** | `< 2000 ms` (SLA objetivo `< 100 ms`) | Controlado en `httpx.AsyncClient(timeout=2.0)` |

---

## 3. Esquema JSON de la Respuesta Exitosa (`200 OK`)

Cuando la cookie `jwt` es válida, no ha expirado ni ha sido revocada, `auth-service` retorna los datos de identidad del usuario autenticado. De esta respuesta `entradas-service` extrae directamente **nombre, RUT, correo y rol** sin solicitarlos manualmente en el formulario de compra:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ValidarSesionAuthResponse",
  "type": "object",
  "required": ["id_usuario", "rol"],
  "properties": {
    "valido": {
      "type": "boolean",
      "example": true
    },
    "id_usuario": {
      "type": "string",
      "description": "UUID o identificador único del usuario en Auth / Keycloak.",
      "example": "usr-12345"
    },
    "rol": {
      "type": "string",
      "enum": ["usuario", "organizador", "staff", "cliente"],
      "description": "Rol del usuario autenticado.",
      "example": "usuario"
    },
    "nombre": {
      "type": "string",
      "description": "Nombre completo del usuario titular de la sesión.",
      "example": "Sebastián Fuentes"
    },
    "rut": {
      "type": "string",
      "description": "RUT del comprador validado en su registro.",
      "example": "20.123.456-7"
    },
    "correo": {
      "type": "string",
      "format": "email",
      "description": "Correo electrónico del usuario titular.",
      "example": "sebastian.fuentes@ticketu.cl"
    },
    "activo": {
      "type": "boolean",
      "default": true,
      "description": "Indica si la cuenta del usuario se encuentra activa."
    }
  }
}
```

---

## 4. Manejo de Códigos de Respuesta, Errores y Resiliencia

| Código HTTP de Auth | Código propagado por Entradas | Descripción y Comportamiento en `entradas-service` |
| :---: | :---: | :--- |
| **`200 OK`** | Continúa operación (`200` / `201`) | Sesión válida. Se verifica que `activo != False` y que el rol esté autorizado (`USUARIO`/`CLIENTE`/`STAFF` para compras; `ORGANIZADOR`/`STAFF` para inventario). |
| **`401 Unauthorized`** | **`401 Unauthorized`** (`NO_AUTENTICADO`) | Cookie `jwt` ausente, firma inválida, token vencido o sesión revocada. Entradas rechaza inmediatamente la operación sin descontar stock. |
| **`403 Forbidden`** | **`401` / `403`** | `x-api-key` inválida o usuario con cuenta suspendida (`activo: false`). |
| **`5xx` / Timeout / Error de Red** | **`503 Service Unavailable`** (`AUTH_NO_DISPONIBLE`) | Si `auth-service` no responde o sufre una caída temporal, `AuthService.validar_sesion` captura `httpx.RequestError` y devuelve `503 AUTH_NO_DISPONIBLE` (`reintentable: true`), asegurando que no se descuenten cupos ni se generen cobros huérfanos. |

