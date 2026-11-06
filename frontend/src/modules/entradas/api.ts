// ============================================================================
// modules/entradas/api.ts
// ----------------------------------------------------------------------------
// Capa de API para el Microservicio de Entradas e Inventario (Grupo 3).
// Se conecta a través del API Gateway (lib/env.ts) hacia:
//   - entradas-service (MongoDB)
//   - checkin-service (MySQL)
// ============================================================================

import { GATEWAY_URL } from "@/lib/env";
import { EventoEntradas, ReservaTemporal, EntradaEmitida, PromocionAplicada } from "./types";
import { MOCK_EVENTOS_ENTRADAS, MOCK_PROMOCIONES } from "./mockData";

const BASE_PATH = "/api/entradas";

let eventosLocal = [...MOCK_EVENTOS_ENTRADAS.map((e) => ({ ...e }))];
let ticketsEmitidosLocal: Record<string, EntradaEmitida> = {};

/**
 * Obtiene la lista completa de eventos con su stock y aforo disponible desde MongoDB (HU-01)
 */
export async function obtenerEventos(): Promise<EventoEntradas[]> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/eventos`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (error) {
    console.warn("API Gateway no disponible, usando fallback local:", error);
  }
  return eventosLocal;
}

/**
 * Obtiene un evento específico por su ID desde MongoDB
 */
export async function obtenerEventoPorId(eventoId: string): Promise<EventoEntradas | null> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/eventos/${eventoId}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (error) {
    console.warn("API Gateway no disponible para evento por ID, usando fallback local:", error);
  }
  return eventosLocal.find((e) => e.id === eventoId) || eventosLocal[0] || null;
}

/**
 * Usada por Catálogo (Grupo 2) en su vista de Detalle de Evento.
 * Retorna resumen liviano de solo lectura sobre stock, tipo y precio único desde MongoDB.
 */
export async function obtenerDisponibilidad(eventoId: string): Promise<{
  idEvento: string;
  stockDisponible: number;
  stockTotal: number;
  tipoEntrada: "PAGADA" | "GRATUITA";
  precio: number;
}> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/eventos/${eventoId}/disponibilidad`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (error) {
    console.warn("API Gateway no disponible para disponibilidad, usando fallback local:", error);
  }

  const ev = eventosLocal.find((e) => e.id === eventoId) || eventosLocal[0];

  return {
    idEvento: ev.id,
    stockDisponible: ev.stockDisponible,
    stockTotal: ev.stockTotal,
    tipoEntrada: ev.tipoEntrada,
    precio: ev.precio,
  };
}

/**
 * Contrato con Promociones (Grupo 9): POST /api/promociones/evaluar
 */
export async function evaluarPromocion(params: {
  idEvento: string;
  idUsuario: string;
  cantidadEntradas: number;
  codigoPromocion?: string;
}): Promise<PromocionAplicada | null> {
  if (!params.codigoPromocion) return null;

  try {
    const res = await fetch(`${GATEWAY_URL}/api/promociones/evaluar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_evento: params.idEvento,
        id_usuario: params.idUsuario,
        cantidad_entradas: params.cantidadEntradas,
        codigo_promocion: params.codigoPromocion,
      }),
      signal: AbortSignal.timeout(1500),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.porcentaje_descuento > 0) {
        return {
          codigo: params.codigoPromocion.toUpperCase(),
          idPromocion: data.id_promocion || "promo-api",
          porcentajeDescuento: data.porcentaje_descuento,
          descripcion: data.descripcion || `Descuento del ${data.porcentaje_descuento}% aplicado`,
        };
      }
    }
  } catch (error) {
    console.warn("Microservicio de Promociones no disponible, evaluando en catálogo local:", error);
  }

  const codigoUpper = params.codigoPromocion.trim().toUpperCase();
  if (MOCK_PROMOCIONES[codigoUpper]) {
    return MOCK_PROMOCIONES[codigoUpper];
  }

  return null;
}

/**
 * HU-03: Crear una Reserva Temporal de Cupos (Hold) en MongoDB
 */
export async function crearReservaTemporal(params: {
  idEvento: string;
  idUsuario: string;
  cantidadEntradas: number;
  subtotal: number;
  descuento: number;
  total: number;
}): Promise<ReservaTemporal> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/reservas/hold`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_evento: params.idEvento,
        id_usuario: params.idUsuario || "usr-12345",
        nombre_usuario: "Sebastian Fuentes",
        correo_usuario: "sebastian.fuentes@ticketu.cl",
        cantidad: params.cantidadEntradas,
        tiempo_limite_minutos: 10,
      }),
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return {
        idReserva: data.hold_id || data.id_reserva,
        idEvento: data.id_evento || params.idEvento,
        idUsuario: data.id_usuario || params.idUsuario,
        cantidadEntradas: data.cantidad_entrada || params.cantidadEntradas,
        subtotal: params.subtotal,
        descuento: params.descuento,
        total: data.monto_total ?? params.total,
        estado: data.estado_reserva || "RESERVADO",
        expiraEnMinutos: 10,
        segundosRestantes: data.tiempo_restante_segundos ?? 600,
        fechaCreacion: data.fecha_creacion || new Date().toISOString(),
      };
    }
  } catch (error) {
    console.warn("Backend no disponible para reserva, simulando hold temporal:", error);
  }

  const ev = eventosLocal.find((e) => e.id === params.idEvento) || eventosLocal[0];
  ev.stockDisponible = Math.max(0, ev.stockDisponible - params.cantidadEntradas);

  const holdId = `hold-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;

  return {
    idReserva: holdId,
    idEvento: ev.id,
    idUsuario: params.idUsuario || "usr-12345",
    cantidadEntradas: params.cantidadEntradas,
    subtotal: params.subtotal,
    descuento: params.descuento,
    total: params.total,
    estado: "PENDIENTE",
    expiraEnMinutos: 10,
    segundosRestantes: 600,
    fechaCreacion: new Date().toISOString(),
  };
}

/**
 * HU-03: Liberar cupos en MongoDB si la reserva expira o el usuario cancela la orden.
 */
export async function liberarReservaTemporal(
  idEvento: string,
  cantidadEntradas: number,
  idReserva?: string
): Promise<void> {
  try {
    if (idReserva) {
      await fetch(`${GATEWAY_URL}${BASE_PATH}/reservas/${idReserva}/cancelar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ motivo: "Reserva liberada desde el Frontend" }),
        signal: AbortSignal.timeout(3000),
      });
    }
  } catch {
    // Modo local / fallback
  }

  const ev = eventosLocal.find((e) => e.id === idEvento);
  if (ev) {
    ev.stockDisponible = Math.min(ev.stockTotal, ev.stockDisponible + cantidadEntradas);
  }
}

/**
 * Consolida una reserva existente en MongoDB (POST /api/entradas/reservas/{idReserva}/webhook-pago),
 * emite la entrada real en MongoDB y la registra automáticamente en el MySQL de Check-in.
 */
export async function consolidarReservaYEmitirTicket(idReserva: string): Promise<string | null> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/reservas/${idReserva}/webhook-pago`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(4000),
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.entradas_emitidas) && data.entradas_emitidas.length > 0) {
        return data.entradas_emitidas[0];
      }
    }
  } catch (error) {
    console.warn("Error consolidando reserva en backend:", error);
  }
  return null;
}

/**
 * HU-05 y HU-08: Emisión Directa (Flujo Gratuito) o Consolidación tras Pago Aprobado (HU-09).
 * Persiste en MongoDB de Entradas y registra síncronamente en MySQL de Check-in.
 */
export async function emitirEntradaDirecta(params: {
  idEvento: string;
  idUsuario: string;
  nombreComprador: string;
  correoComprador: string;
  cantidadEntradas: number;
  precioFinal: number;
  idReserva?: string;
}): Promise<EntradaEmitida> {
  // Si viene con un idReserva real del backend, consolidar vía webhook-pago primero
  if (params.idReserva) {
    const idTicketBackend = await consolidarReservaYEmitirTicket(params.idReserva);
    if (idTicketBackend) {
      const detalle = await obtenerEntradaEmitida(idTicketBackend);
      if (detalle) return detalle;
    }
  }

  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/emision-directa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_evento: params.idEvento,
        id_usuario: params.idUsuario || "usr-12345",
        nombre_comprador: params.nombreComprador || "Sebastian Fuentes",
        correo_comprador: params.correoComprador || "sebastian.fuentes@ticketu.cl",
        cantidad_entradas: params.cantidadEntradas,
        precio_final: params.precioFinal,
        id_reserva: params.idReserva || null,
      }),
      signal: AbortSignal.timeout(4000),
    });
    if (res.ok) {
      const emitida: EntradaEmitida = await res.json();
      if (typeof window !== "undefined") {
        try {
          sessionStorage.setItem(`ticket_${emitida.idEntrada}`, JSON.stringify(emitida));
        } catch {
          // Ignorar
        }
      }
      return emitida;
    }
  } catch (error) {
    console.warn("Backend no disponible para emisión, simulando ticket definitivo:", error);
  }

  const ev = eventosLocal.find((e) => e.id === params.idEvento) || eventosLocal[0];
  const ticketId = `tk-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;

  if (ev.precio === 0) {
    ev.stockDisponible = Math.max(0, ev.stockDisponible - params.cantidadEntradas);
  }

  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${ticketId}`;

  const nuevoTicket: EntradaEmitida = {
    idEntrada: ticketId,
    idEvento: ev.id,
    nombreEvento: ev.titulo,
    nombreComprador: params.nombreComprador || "Sebastian Fuentes",
    correoComprador: params.correoComprador || "sebastian.fuentes@ticketu.cl",
    tipoAcceso: ev.tipoEntrada === "GRATUITA" ? "Entrada Gratuita" : "Entrada General",
    precioFinal: params.precioFinal,
    cantidadEntradas: params.cantidadEntradas,
    qrData: qrUrl,
    fechaEvento: ev.fecha,
    horaEvento: ev.hora,
    lugarEvento: ev.lugar,
    fechaEmision: new Date().toLocaleDateString("es-CL"),
  };

  ticketsEmitidosLocal[ticketId] = nuevoTicket;
  return nuevoTicket;
}

/**
 * Obtiene la información de un ticket emitido por su ID desde MongoDB (GET /api/entradas/{idEntrada}/detalle)
 */
export async function obtenerEntradaEmitida(idEntrada: string): Promise<EntradaEmitida | null> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/${idEntrada}/detalle`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return {
        idEntrada: data.id_entrada,
        idEvento: data.id_evento,
        nombreEvento: data.nombre_evento,
        nombreComprador: data.nombre_usuario || "Sebastian Fuentes",
        correoComprador: data.correo_usuario || "sebastian.fuentes@ticketu.cl",
        tipoAcceso: data.tipo_acceso || "Entrada General",
        precioFinal: data.precio_final_pagado || 0,
        cantidadEntradas: 1,
        qrData:
          typeof data.qr_data === "string"
            ? data.qr_data
            : `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${data.id_entrada}`,
        fechaEvento: "20 de Noviembre, 2026",
        horaEvento: "20:00 hrs",
        lugarEvento: data.lugar_ingreso || "Puerta Principal - Acceso General",
        fechaEmision: data.fecha_emision
          ? new Date(data.fecha_emision).toLocaleDateString("es-CL")
          : new Date().toLocaleDateString("es-CL"),
      };
    }
  } catch {
    // Backend no disponible, revisar sessionStorage / memoria
  }

  if (typeof window !== "undefined") {
    try {
      const guardado = sessionStorage.getItem(`ticket_${idEntrada}`);
      if (guardado) return JSON.parse(guardado);
    } catch {
      // Fallback a memoria
    }
  }

  if (ticketsEmitidosLocal[idEntrada]) {
    return ticketsEmitidosLocal[idEntrada];
  }

  const ev = eventosLocal[0];
  return {
    idEntrada: idEntrada || "tk-DEMO-2026",
    idEvento: ev.id,
    nombreEvento: ev.titulo,
    nombreComprador: "Sebastian Fuentes",
    correoComprador: "sebastian.fuentes@ticketu.cl",
    tipoAcceso: "Entrada General Oficial",
    precioFinal: ev.precio,
    cantidadEntradas: 1,
    qrData: `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${idEntrada || "tk-DEMO-2026"}`,
    fechaEvento: ev.fecha,
    horaEvento: ev.hora,
    lugarEvento: ev.lugar,
    fechaEmision: new Date().toLocaleDateString("es-CL"),
  };
}
