// ============================================================================
// modules/entradas/api.ts
// Capa de comunicación HTTP para el módulo de Entradas e Inventario vía API Gateway.
// ============================================================================

import { GATEWAY_URL } from "@/lib/env";
import {
  EventoEntradas,
  EstadoGestionEvento,
  ReservaTemporal,
  EntradaEmitida,
  ResultadoEvaluacionPromocion,
} from "./types";

const BASE_PATH = "/api/entradas";
const PANEL_PROXIMOS_PATH = "/api/organizador/v1/organizador/eventos/proximos";

interface PanelEventoRaw {
  id_evento: string;
  nombre_evento: string;
  descripcion?: string;
  direccion_evento?: string;
  fecha_evento?: string;
  hora_evento?: string;
  precio?: number | null;
  tipo_entrada?: string;
  estado_gestion?: string;
  cantidad_entradas?: number;
}

function construirQrUrl(idEntrada: string, idEvento: string): string {
  const payload = JSON.stringify({
    id_entrada: idEntrada.trim(),
    id_evento: idEvento.trim(),
  });
  return `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(payload)}`;
}

function mapPanelToEventoEntradas(ev: PanelEventoRaw): EventoEntradas {
  const esGratuita = ev.tipo_entrada !== "PAGADA";
  return {
    id: ev.id_evento,
    titulo: ev.nombre_evento,
    fecha: ev.fecha_evento || "Por confirmar",
    hora: ev.hora_evento || "Por confirmar",
    lugar: ev.direccion_evento || "Por confirmar",
    descripcion: ev.descripcion,
    tipoEntrada: esGratuita ? "GRATUITA" : "PAGADA",
    precio: esGratuita ? 0 : Number(ev.precio ?? 0),
    stockTotal: Number(ev.cantidad_entradas ?? 100),
    stockDisponible: Number(ev.cantidad_entradas ?? 100),
    maxTickets: 6,
    limiteGratuitoUsuario: esGratuita ? 2 : undefined,
    estadoGestion: (ev.estado_gestion as EstadoGestionEvento) || "PUBLICADO",
    origen: "PANEL",
  };
}

function mapDetalleBackendAEntradaEmitida(data: Record<string, unknown>): EntradaEmitida {
  const idEntrada = String(data.id_entrada || "");
  const idEvento = String(data.id_evento || "");
  const qrField = data.qr_data;
  let qrUrl = construirQrUrl(idEntrada, idEvento);
  if (typeof qrField === "string" && qrField.trim()) {
    qrUrl = qrField;
  } else if (qrField && typeof qrField === "object" && "url" in qrField && typeof (qrField as { url?: unknown }).url === "string") {
    qrUrl = (qrField as { url: string }).url;
  }

  return {
    idEntrada,
    idEvento,
    nombreEvento: String(data.nombre_evento || `Evento ${idEvento}`),
    nombreComprador: String(data.nombre_usuario || "Asistente"),
    correoComprador: String(data.correo_usuario || ""),
    tipoAcceso: String(data.tipo_acceso || "GENERAL"),
    precioFinal: Number(data.precio_final_pagado ?? 0),
    cantidadEntradas: 1,
    qrData: qrUrl,
    fechaEvento: String(data.fecha_evento || "Por confirmar"),
    horaEvento: String(data.hora_evento || "Por confirmar"),
    lugarEvento: String(data.lugar_ingreso || "Puerta Principal - Acceso General"),
    fechaEmision: data.fecha_emision
      ? new Date(String(data.fecha_emision)).toLocaleDateString("es-CL")
      : new Date().toLocaleDateString("es-CL"),
    estadoEntrada: String(data.estado_entrada || "EMITIDA"),
  };
}

/**
 * Obtiene únicamente los eventos reales creados y publicados en Panel Organizador,
 * enriquecidos con su stock y disponibilidad real desde el microservicio de Entradas.
 */
export async function obtenerEventos(): Promise<EventoEntradas[]> {
  const [resPanel, resEntradas] = await Promise.allSettled([
    fetch(`${GATEWAY_URL}${PANEL_PROXIMOS_PATH}?limite=50`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    }),
    fetch(`${GATEWAY_URL}${BASE_PATH}/eventos`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    }),
  ]);

  if (resPanel.status !== "fulfilled" || !resPanel.value.ok) {
    throw new Error("No fue posible consultar los eventos publicados en Panel Organizador.");
  }

  const panelJson = await resPanel.value.json();
  const listaPanel: PanelEventoRaw[] = Array.isArray(panelJson) ? panelJson : [];

  const mapaEventos = new Map<string, EventoEntradas>();
  for (const p of listaPanel) {
    if (p?.id_evento) {
      mapaEventos.set(p.id_evento, mapPanelToEventoEntradas(p));
    }
  }

  if (resEntradas.status === "fulfilled" && resEntradas.value.ok) {
    const listaEntradas: EventoEntradas[] = await resEntradas.value.json();
    for (const ev of listaEntradas) {
      const existente = mapaEventos.get(ev.id);
      if (!existente) continue;
      mapaEventos.set(ev.id, {
        ...existente,
        ...ev,
        titulo: ev.titulo && !ev.titulo.startsWith("Evento ") ? ev.titulo : existente.titulo,
        fecha: ev.fecha && ev.fecha !== "Por confirmar" ? ev.fecha : existente.fecha,
        hora: ev.hora && ev.hora !== "Por confirmar" ? ev.hora : existente.hora,
        lugar: ev.lugar && ev.lugar !== "Por confirmar" ? ev.lugar : existente.lugar,
        origen: "PANEL",
      });
    }
  }

  return Array.from(mapaEventos.values());
}

/**
 * Obtiene un evento específico de Panel Organizador con su disponibilidad actualizada en Entradas.
 */
export async function obtenerEventoPorId(eventoId: string): Promise<EventoEntradas | null> {
  try {
    const resEnt = await fetch(`${GATEWAY_URL}${BASE_PATH}/eventos/${encodeURIComponent(eventoId)}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (resEnt.ok) {
      const ev: EventoEntradas = await resEnt.json();
      return { ...ev, origen: "PANEL" };
    }
  } catch {
    // Continuar consultando Panel Organizador si aún no se refleja en Entradas
  }

  try {
    const resPanel = await fetch(`${GATEWAY_URL}${PANEL_PROXIMOS_PATH}?limite=50`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!resPanel.ok) return null;
    const panelJson = await resPanel.json();
    const listaPanel: PanelEventoRaw[] = Array.isArray(panelJson) ? panelJson : [];
    const encontrado = listaPanel.find((p) => p?.id_evento === eventoId);
    if (!encontrado) return null;

    const evento = mapPanelToEventoEntradas(encontrado);
    try {
      const disp = await obtenerDisponibilidad(eventoId);
      evento.stockDisponible = disp.stockDisponible;
      evento.stockTotal = disp.stockTotal;
      evento.tipoEntrada = disp.tipoEntrada;
      evento.precio = disp.precio;
      if (disp.estadoGestion) {
        evento.estadoGestion = disp.estadoGestion;
      }
    } catch {
      // Mantener los datos de Panel si la sincronización sigue en curso
    }
    return evento;
  } catch {
    return null;
  }
}

/**
 * Consulta la disponibilidad en tiempo real del evento.
 */
export async function obtenerDisponibilidad(eventoId: string): Promise<{
  idEvento: string;
  stockDisponible: number;
  stockTotal: number;
  tipoEntrada: "PAGADA" | "GRATUITA";
  precio: number;
  estadoGestion?: EstadoGestionEvento;
}> {
  const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/eventos/${encodeURIComponent(eventoId)}/disponibilidad`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    signal: AbortSignal.timeout(4000),
  });

  if (!res.ok) {
    throw new Error(`No se pudo consultar la disponibilidad del evento (HTTP ${res.status}).`);
  }
  return await res.json();
}

/**
 * Evalúa un código promocional contra el microservicio de Promociones.
 */
export async function evaluarPromocion(params: {
  idEvento: string;
  idUsuario: string;
  cantidadEntradas: number;
  codigoPromocion?: string;
}): Promise<ResultadoEvaluacionPromocion> {
  const codigo = params.codigoPromocion?.trim().toUpperCase();
  if (!codigo) return { promocion: null, mensaje: "Ingresa un código promocional." };

  try {
    const res = await fetch(`${GATEWAY_URL}/api/promociones/evaluar`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_evento: params.idEvento,
        id_usuario: params.idUsuario,
        cantidad_entradas: params.cantidadEntradas,
        codigo_promocion: codigo,
      }),
      signal: AbortSignal.timeout(4000),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return {
        promocion: null,
        mensaje: data?.mensaje || "No se pudo validar el código promocional.",
      };
    }

    if (Number(data.porcentaje_descuento) > 0) {
      return {
        promocion: {
          codigo,
          idPromocion: data.id_promocion || "promo-api",
          porcentajeDescuento: Number(data.porcentaje_descuento),
          descripcion: data.descripcion || `Descuento del ${data.porcentaje_descuento}% aplicado`,
        },
      };
    }

    return {
      promocion: null,
      mensaje: data?.mensaje || "El código promocional no es válido para esta compra.",
    };
  } catch {
    return {
      promocion: null,
      mensaje: "El servicio de promociones no está disponible en este momento.",
    };
  }
}

/**
 * Crea una reserva temporal de cupos (Hold) para iniciar el flujo de pago real.
 */
export async function crearReservaTemporal(params: {
  idEvento: string;
  idUsuario: string;
  nombreUsuario: string;
  correoUsuario: string;
  cantidadEntradas: number;
  subtotal: number;
  descuento: number;
  total: number;
  nombreCodigo?: string;
  idPromocion?: string;
  porcentajeDescuento?: number;
}): Promise<ReservaTemporal> {
  const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/reservas/hold`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_evento: params.idEvento,
      cantidad: params.cantidadEntradas,
      tiempo_limite_minutos: 15,
      ...(params.nombreCodigo ? { nombre_codigo: params.nombreCodigo } : {}),
      ...(params.idPromocion ? { id_promocion: params.idPromocion } : {}),
      ...(params.porcentajeDescuento ? { porcentaje_descuento: params.porcentajeDescuento } : {}),
    }),
    signal: AbortSignal.timeout(6000),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    const detalle =
      typeof errBody?.detail === "string"
        ? errBody.detail
        : errBody?.detail?.mensaje || errBody?.message || "No se pudo crear la reserva temporal.";
    throw new Error(detalle);
  }

  const data = await res.json();
  const totalReal = data.monto_total ?? params.total;
  const descuentoReal =
    typeof data.porcentaje_descuento === "number" && data.porcentaje_descuento === 0
      ? 0
      : Math.max(0, params.subtotal - totalReal);
  const avisoPromocion =
    params.nombreCodigo && descuentoReal === 0
      ? `El código "${params.nombreCodigo}" no pudo aplicarse; la reserva se generó por el monto normal.`
      : undefined;

  return {
    idReserva: data.hold_id || data.id_reserva,
    idEvento: data.id_evento || params.idEvento,
    idUsuario: data.id_usuario || params.idUsuario,
    cantidadEntradas: data.cantidad_entrada || params.cantidadEntradas,
    subtotal: params.subtotal,
    descuento: descuentoReal,
    total: totalReal,
    avisoPromocion,
    estado: data.estado_reserva || "RESERVADO",
    expiraEnMinutos: 15,
    segundosRestantes: data.tiempo_restante_segundos ?? 900,
    fechaCreacion: data.fecha_creacion || new Date().toISOString(),
  };
}

/**
 * Cancela la reserva temporal y devuelve los cupos al inventario disponible.
 */
export async function liberarReservaTemporal(
  _idEvento: string,
  _cantidadEntradas: number,
  idReserva?: string
): Promise<void> {
  if (!idReserva) return;
  await fetch(`${GATEWAY_URL}${BASE_PATH}/reservas/${encodeURIComponent(idReserva)}/cancelar`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ motivo: "Reserva cancelada por el usuario" }),
    signal: AbortSignal.timeout(5000),
  });
}

/**
 * Emisión directa exclusiva para eventos gratuitos (requiere sesión iniciada).
 */
export async function emitirEntradaDirecta(params: {
  idEvento: string;
  cantidadEntradas: number;
}): Promise<EntradaEmitida> {
  const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/emision-directa`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_evento: params.idEvento,
      cantidad_entradas: params.cantidadEntradas,
      precio_final: 0,
    }),
    signal: AbortSignal.timeout(6000),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    const detalle =
      typeof errBody?.detail === "string"
        ? errBody.detail
        : errBody?.detail?.mensaje || errBody?.message || "No se pudo emitir la entrada gratuita.";
    throw new Error(detalle);
  }

  const emitida: EntradaEmitida = await res.json();
  if (typeof window !== "undefined") {
    try {
      sessionStorage.setItem(`ticket_${emitida.idEntrada}`, JSON.stringify(emitida));
    } catch {
      // Ignorar errores de almacenamiento del navegador
    }
  }
  return emitida;
}

/**
 * Obtiene el historial de entradas emitidas del usuario autenticado (HU-04).
 */
export async function obtenerMisEntradas(): Promise<EntradaEmitida[]> {
  const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/mis-entradas`, {
    method: "GET",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });

  if (res.status === 401) {
    return [];
  }
  if (!res.ok) {
    throw new Error("No se pudo cargar tu historial de entradas.");
  }

  const lista = await res.json();
  if (!Array.isArray(lista)) return [];
  return lista.map((item) => mapDetalleBackendAEntradaEmitida(item));
}

/**
 * Obtiene el detalle inmutable de una entrada emitida por su identificador.
 */
export async function obtenerEntradaEmitida(idEntrada: string): Promise<EntradaEmitida | null> {
  const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/${encodeURIComponent(idEntrada)}/detalle`, {
    method: "GET",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });

  if (res.ok) {
    const data = await res.json();
    return mapDetalleBackendAEntradaEmitida(data);
  }

  if (typeof window !== "undefined") {
    try {
      const guardado = sessionStorage.getItem(`ticket_${idEntrada}`);
      if (guardado) return JSON.parse(guardado);
    } catch {
      // Ignorar
    }
  }

  return null;
}
