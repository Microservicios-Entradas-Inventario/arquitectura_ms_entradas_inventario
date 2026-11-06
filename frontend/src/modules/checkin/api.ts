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
