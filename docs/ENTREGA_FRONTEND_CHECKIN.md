# Guía de Integración Frontend — Módulo Check-in (Grupo 5) ↔ Entradas (Grupo 3)

Este documento contiene los **3 archivos listos para copiar y pegar** en el repositorio unificado del Frontend (`FrontendTitec-main`) y la configuración del **API Gateway** para que el módulo de **Check-in (`/checkin`)** funcione conectado en vivo con el backend de Check-in (`:3005`, MySQL) y el backend de Entradas (`:3000`, MongoDB).

> **Nota:** El microservicio backend de Check-in (`checkin/backend-main`) **no requiere ningún cambio**. Todo se adaptó a sus rutas actuales (`POST /api/checkin/tickets` y `POST /api/checkin/validaciones`) y a su puerto `3005`.

---

## 1. Configuración en el API Gateway (`api-gateway/.env`)

Como el contenedor `checkin-service` escucha internamente en el puerto **`3005`**, en el archivo `.env` del API Gateway asegúrense de tener:

```env
CHECKIN_SERVICE_URL=http://checkin-service:3005
```

---

## 2. Tabla de Archivos a Reemplazar en `FrontendTitec-main`

| # | Archivo | Ruta exacta dentro de `FrontendTitec-main` | Propósito |
|---|---|---|---|
| **1** | `page.tsx` | `src/app/checkin/page.tsx` | Envuelve el componente en `<Suspense>` para que `npm run build` en Docker compile sin errores con `useSearchParams()`. |
| **2** | `api.ts` | `src/modules/checkin/api.ts` | Conecta con el API Gateway (`POST /api/checkin/validaciones`, `POST /api/checkin/tickets` y `GET /api/entradas/{id}`). |
| **3** | `CheckinPlaceholder.tsx` | `src/modules/checkin/components/CheckinPlaceholder.tsx` | Interfaz visual de validación de tickets en puerta mostrando la respuesta de MySQL (Check-in) y MongoDB (Entradas). |

---

## 3. Código Completo de los 3 Archivos (Copiar y Pegar)

### Archivo 1: `src/app/checkin/page.tsx`

```tsx
import { Suspense } from "react";
import CheckinPlaceholder from "@/modules/checkin/components/CheckinPlaceholder";

export default function CheckinPage() {
  return (
    <Suspense fallback={<div style={{ padding: "48px", textAlign: "center" }}>Cargando módulo de Check-in...</div>}>
      <CheckinPlaceholder />
    </Suspense>
  );
}
```

---

### Archivo 2: `src/modules/checkin/api.ts`

```ts
// ============================================================================
// modules/checkin/api.ts
// ----------------------------------------------------------------------------
// Capa de API para el módulo de Check-in (Grupo 5) integrada con Entradas (Grupo 3)
// a través del API Gateway (http://localhost:8080).
// ============================================================================

import { GATEWAY_URL } from "@/lib/env";

const BASE_PATH = "/api/checkin";

export interface ValidacionCheckinResponse {
  valido: boolean;
  motivo: string;
  ticket?: {
    id_entrada: string;
    id_evento: string;
    nombre_usuario: string;
  };
}

export interface ConsultaEntradaCheckinResponse {
  id_ticket: string;
  nombre_usuario: string;
  usuario: {
    id_usuario: string;
    rol_usuario: string;
  };
}

/**
 * Valida un ticket en puerta contra la base de datos MySQL de Check-in
 * (POST /api/checkin/validaciones)
 */
export async function validarTicketEnPuerta(params: {
  idEntrada: string;
  idEvento: string;
}): Promise<ValidacionCheckinResponse> {
  const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/validaciones`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_entrada: params.idEntrada.trim(),
      id_evento: params.idEvento.trim(),
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error?.message || `Error HTTP ${res.status} al validar en Check-in`);
  }
  return data;
}

/**
 * Registra un ticket en la base de datos MySQL de Check-in
 * (POST /api/checkin/tickets)
 */
export async function registrarTicketEnCheckin(params: {
  idEntrada: string;
  idEvento: string;
  idUsuario: string;
  nombreUsuario: string;
}): Promise<{ mensaje: string }> {
  const idLimpio = params.idEntrada.trim();
  const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/tickets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_entrada: idLimpio,
      id_evento: params.idEvento.trim(),
      id_usuario: params.idUsuario.trim(),
      nombre_usuario: params.nombreUsuario.trim(),
      qr_data: idLimpio,
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error?.message || `Error HTTP ${res.status} al registrar en Check-in`);
  }
  return data;
}

/**
 * Consulta la validez y titularidad de un ticket en el microservicio de Entradas (MongoDB)
 * (GET /api/entradas/{id_ticket})
 */
export async function consultarTicketEnEntradas(idEntrada: string): Promise<ConsultaEntradaCheckinResponse> {
  const res = await fetch(`${GATEWAY_URL}/api/entradas/${encodeURIComponent(idEntrada.trim())}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.detail || `Ticket no encontrado en Entradas (HTTP ${res.status})`);
  }
  return data;
}
```

---

### Archivo 3: `src/modules/checkin/components/CheckinPlaceholder.tsx`

```tsx
// ============================================================================
// modules/checkin/components/CheckinPlaceholder.tsx
// ----------------------------------------------------------------------------
// Vista interactiva de Check-in (Grupo 5) conectada en tiempo real con:
//   - Microservicio Check-in (MySQL) via /api/checkin/validaciones y /api/checkin/tickets
//   - Microservicio Entradas (MongoDB) via /api/entradas/{id_ticket}
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  validarTicketEnPuerta,
  consultarTicketEnEntradas,
  ValidacionCheckinResponse,
  ConsultaEntradaCheckinResponse,
} from "../api";

export default function CheckinPlaceholder() {
  const searchParams = useSearchParams();
  const idEntradaParam = searchParams.get("idEntrada") || "tk-998877";
  const idEventoParam = searchParams.get("idEvento") || "evt-77889";

  const [idEntrada, setIdEntrada] = useState(idEntradaParam);
  const [idEvento, setIdEvento] = useState(idEventoParam);
  const [cargando, setCargando] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [resCheckin, setResCheckin] = useState<ValidacionCheckinResponse | null>(null);
  const [resEntradas, setResEntradas] = useState<ConsultaEntradaCheckinResponse | null>(null);

  useEffect(() => {
    if (searchParams.get("idEntrada")) {
      setIdEntrada(searchParams.get("idEntrada") || "tk-998877");
    }
    if (searchParams.get("idEvento")) {
      setIdEvento(searchParams.get("idEvento") || "evt-77889");
    }
  }, [searchParams]);

  const handleValidarAmbos = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setCargando(true);
    setErrorMsg(null);
    setResCheckin(null);
    setResEntradas(null);

    try {
      const [validacionMysql, consultaMongo] = await Promise.allSettled([
        validarTicketEnPuerta({ idEntrada, idEvento }),
        consultarTicketEnEntradas(idEntrada),
      ]);

      if (validacionMysql.status === "fulfilled") {
        setResCheckin(validacionMysql.value);
      } else {
        setErrorMsg(validacionMysql.reason?.message || "Error consultando Check-in MySQL");
      }

      if (consultaMongo.status === "fulfilled") {
        setResEntradas(consultaMongo.value);
      }
    } finally {
      setCargando(false);
    }
  };

  const seleccionarSemilla = (tk: string, evt: string) => {
    setIdEntrada(tk);
    setIdEvento(evt);
    setResCheckin(null);
    setResEntradas(null);
    setErrorMsg(null);
  };

  return (
    <div style={{ maxWidth: "920px", margin: "32px auto", padding: "0 20px", fontFamily: "system-ui, sans-serif" }}>
      <div
        style={{
          backgroundColor: "#F4F6FA",
          border: "1px solid #D5DCE6",
          borderRadius: "12px",
          padding: "20px 24px",
          marginBottom: "24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <span
            style={{
              backgroundColor: "#E1EFFE",
              color: "#1E429F",
              padding: "4px 10px",
              borderRadius: "999px",
              fontSize: "12px",
              fontWeight: 700,
            }}
          >
            Grupo 5 · Check-in ↔ Grupo 3 · Entradas
          </span>
          <h1 style={{ fontSize: "24px", color: "#2F4374", margin: "8px 0 4px 0" }}>
            Control de Acceso y Validación de Tickets (Check-in)
          </h1>
          <p style={{ margin: 0, fontSize: "14px", color: "#586A84" }}>
            Valida en tiempo real los tickets emitidos por <code>entradas-service</code> (MongoDB) y sincronizados en <code>checkin-service</code> (MySQL).
          </p>
        </div>
        <Link
          href="/entradas"
          style={{
            backgroundColor: "#2F4374",
            color: "#FFFFFF",
            padding: "10px 18px",
            borderRadius: "8px",
            textDecoration: "none",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          ← Emitir Nueva Entrada en /entradas
        </Link>
      </div>

      {/* Botones rápidos de tickets semilla */}
      <div style={{ marginBottom: "20px", display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "#2F4374" }}>Tickets Semilla Rápidos:</span>
        <button
          type="button"
          onClick={() => seleccionarSemilla("tk-998877", "evt-77889")}
          style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #CBD5E1", background: "#FFF", cursor: "pointer", fontSize: "13px" }}
        >
          🎟️ tk-998877 (evt-77889)
        </button>
        <button
          type="button"
          onClick={() => seleccionarSemilla("tk-demo-001", "evt-002")}
          style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #CBD5E1", background: "#FFF", cursor: "pointer", fontSize: "13px" }}
        >
          🎟️ tk-demo-001 (evt-002)
        </button>
        <button
          type="button"
          onClick={() => seleccionarSemilla("tk-DEMO-2026", "evt-001")}
          style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #CBD5E1", background: "#FFF", cursor: "pointer", fontSize: "13px" }}
        >
          🎟️ tk-DEMO-2026 (evt-001)
        </button>
      </div>

      {/* Formulario de Validación en Puerta */}
      <form
        onSubmit={handleValidarAmbos}
        style={{
          backgroundColor: "#FFFFFF",
          border: "1px solid #D5DCE6",
          borderRadius: "12px",
          padding: "24px",
          marginBottom: "24px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <h2 style={{ fontSize: "18px", color: "#2F4374", margin: "0 0 16px 0" }}>
          Escanear / Validar Código QR en Torniquete
        </h2>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", marginBottom: "16px" }}>
          <div>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 600, color: "#2F4374", marginBottom: "6px" }}>
              ID de Entrada / QR (<code>id_entrada</code>):
            </label>
            <input
              type="text"
              required
              value={idEntrada}
              onChange={(e) => setIdEntrada(e.target.value)}
              placeholder="Ej: tk-998877"
              style={{
                width: "100%",
                height: "42px",
                padding: "0 12px",
                borderRadius: "8px",
                border: "1px solid #CBD5E1",
                fontSize: "14px",
              }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 600, color: "#2F4374", marginBottom: "6px" }}>
              ID del Evento (<code>id_evento</code>):
            </label>
            <input
              type="text"
              required
              value={idEvento}
              onChange={(e) => setIdEvento(e.target.value)}
              placeholder="Ej: evt-001 o evt-77889"
              style={{
                width: "100%",
                height: "42px",
                padding: "0 12px",
                borderRadius: "8px",
                border: "1px solid #CBD5E1",
                fontSize: "14px",
              }}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={cargando}
          style={{
            backgroundColor: "#2F4374",
            color: "#FFFFFF",
            border: "none",
            borderRadius: "8px",
            height: "44px",
            padding: "0 24px",
            fontWeight: 600,
            fontSize: "15px",
            cursor: "pointer",
          }}
        >
          {cargando ? "Validando en Check-in (MySQL) y Entradas (MongoDB)..." : "🔍 Validar Entrada en Puerta"}
        </button>
      </form>

      {errorMsg && (
        <div
          style={{
            backgroundColor: "#FDE8E8",
            color: "#9B1C1C",
            padding: "14px 18px",
            borderRadius: "8px",
            marginBottom: "20px",
            fontSize: "14px",
          }}
        >
          ⚠️ {errorMsg}
        </div>
      )}

      {/* Resultados de ambos microservicios */}
      {(resCheckin || resEntradas) && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
          <div
            style={{
              backgroundColor: "#FFFFFF",
              border: `2px solid ${resCheckin?.valido ? "#0E9F6E" : "#E02424"}`,
              borderRadius: "12px",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "12px", fontWeight: 700, color: "#586A84", textTransform: "uppercase" }}>
              Microservicio 1: Check-in (MySQL · :3005)
            </div>
            <h3 style={{ margin: "6px 0 12px 0", color: resCheckin?.valido ? "#03543F" : "#9B1C1C" }}>
              {resCheckin?.valido ? "✅ ACCESO AUTORIZADO" : `❌ ACCESO DENEGADO (${resCheckin?.motivo})`}
            </h3>
            <p style={{ fontSize: "13px", color: "#586A84", marginBottom: "12px" }}>
              Endpoint: <code>POST /api/checkin/validaciones</code>
            </p>
            {resCheckin?.ticket ? (
              <div style={{ fontSize: "14px", lineHeight: 1.7 }}>
                <div><strong>ID Entrada:</strong> <code>{resCheckin.ticket.id_entrada}</code></div>
                <div><strong>ID Evento:</strong> <code>{resCheckin.ticket.id_evento}</code></div>
                <div><strong>Asistente Registrado:</strong> {resCheckin.ticket.nombre_usuario}</div>
                <div><strong>Motivo:</strong> <code>{resCheckin.motivo}</code></div>
              </div>
            ) : (
              <div style={{ fontSize: "13px", color: "#9B1C1C" }}>
                El ticket no coincide con el evento indicado o no existe en la tabla <code>ticket</code> de MySQL.
              </div>
            )}
          </div>

          <div
            style={{
              backgroundColor: "#FFFFFF",
              border: `2px solid ${resEntradas ? "#2F4374" : "#CBD5E1"}`,
              borderRadius: "12px",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "12px", fontWeight: 700, color: "#586A84", textTransform: "uppercase" }}>
              Microservicio 2: Entradas e Inventario (MongoDB · :3000)
            </div>
            <h3 style={{ margin: "6px 0 12px 0", color: "#2F4374" }}>
              {resEntradas ? "🎟️ Respaldo en MongoDB Verificado" : "⚠️ No encontrado en MongoDB"}
            </h3>
            <p style={{ fontSize: "13px", color: "#586A84", marginBottom: "12px" }}>
              Endpoint: <code>GET /api/entradas/{idEntrada}</code>
            </p>
            {resEntradas ? (
              <div style={{ fontSize: "14px", lineHeight: 1.7 }}>
                <div><strong>ID Ticket:</strong> <code>{resEntradas.id_ticket}</code></div>
                <div><strong>Titular:</strong> {resEntradas.nombre_usuario}</div>
                <div><strong>ID Usuario:</strong> <code>{resEntradas.usuario.id_usuario}</code></div>
                <div><strong>Rol:</strong> <code>{resEntradas.usuario.rol_usuario}</code></div>
              </div>
            ) : (
              <div style={{ fontSize: "13px", color: "#586A84" }}>
                Sin registro en la colección <code>entrada</code> de MongoDB.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

