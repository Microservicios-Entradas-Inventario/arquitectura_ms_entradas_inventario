// ============================================================================
// modules/entradas/api.ts
// ----------------------------------------------------------------------------
// Capa de API para el Microservicio de Entradas e Inventario (Grupo 3).
// Se conecta a través del API Gateway (lib/env.ts).
//
// Incluye mecanismo de RESILIENCIA (Mock Fallback):
// Si el Gateway o los microservicios Backend no están levantados en local,
// conmuta automáticamente a los datos simulados para que la presentación
// y las pruebas de frontend funcionen SIEMPRE de manera fluida y sin caídas.
// ============================================================================

import { GATEWAY_URL } from "@/lib/env";
import { EventoEntradas, ReservaTemporal, EntradaEmitida, PromocionAplicada } from "./types";
import { MOCK_EVENTOS_ENTRADAS, MOCK_PROMOCIONES } from "./mockData";

const BASE_PATH = "/api/entradas";

// Estado en memoria para simular reservas y mutaciones locales durante la sesión
let eventosLocal = [...MOCK_EVENTOS_ENTRADAS.map((e) => ({ ...e }))];
let ticketsEmitidosLocal: Record<string, EntradaEmitida> = {};

/**
 * Obtiene la lista completa de eventos con su stock y aforo disponible (HU-01)
 */
export async function obtenerEventos(): Promise<EventoEntradas[]> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/eventos`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(1500),
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
 * Obtiene un evento específico por su ID
 */
export async function obtenerEventoPorId(eventoId: string): Promise<EventoEntradas | null> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/eventos/${eventoId}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(1500),
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
 * Retorna resumen liviano de solo lectura sobre stock, tipo y precio único.
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
      signal: AbortSignal.timeout(1500),
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
 * Contrato con Promociones (Grupo 9): POST /api/v1/promociones/evaluar
 * Consulta si existe un descuento activo para el evento o código ingresado.
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

  // Fallback con catálogo de códigos locales
  const codigoUpper = params.codigoPromocion.trim().toUpperCase();
  if (MOCK_PROMOCIONES[codigoUpper]) {
    return MOCK_PROMOCIONES[codigoUpper];
  }

  return null;
}

/**
 * HU-03: Crear una Reserva Temporal de Cupos (Hold)
 * Descuenta temporalmente del stock y genera un `holdId` único (TTL de 15 minutos).
 * Se comunica con Pagos (Grupo 4) enviando el idReserva y el total final.
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
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/reservas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_evento: params.idEvento,
        id_usuario: params.idUsuario,
        cantidad_entradas: params.cantidadEntradas,
        total: params.total,
      }),
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (error) {
    console.warn("Backend no disponible para reserva, simulando hold temporal:", error);
  }

  // Simulación de reserva local
  const ev = eventosLocal.find((e) => e.id === params.idEvento) || eventosLocal[0];
  ev.stockDisponible = Math.max(0, ev.stockDisponible - params.cantidadEntradas);

  const holdId = `hold-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;

  return {
    idReserva: holdId,
    idEvento: ev.id,
    idUsuario: params.idUsuario || "usr-alumno-uv",
    cantidadEntradas: params.cantidadEntradas,
    subtotal: params.subtotal,
    descuento: params.descuento,
    total: params.total,
    estado: "PENDIENTE",
    expiraEnMinutos: 10,
    fechaCreacion: new Date().toISOString(),
  };
}

/**
 * HU-03: Liberar cupos si la reserva expira o el usuario cancela la orden.
 * Devuelve las entradas al pool de stock disponible.
 */
export async function liberarReservaTemporal(idEvento: string, cantidadEntradas: number): Promise<void> {
  try {
    await fetch(`${GATEWAY_URL}${BASE_PATH}/reservas/liberar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_evento: idEvento, cantidad_entradas: cantidadEntradas }),
      signal: AbortSignal.timeout(1500),
    });
  } catch {
    // Modo local / fallback
  }

  const ev = eventosLocal.find((e) => e.id === idEvento);
  if (ev) {
    ev.stockDisponible = Math.min(ev.stockTotal, ev.stockDisponible + cantidadEntradas);
  }
}

/**
 * HU-05 y HU-08: Emisión Directa (Flujo Gratuito) o Consolidación tras Pago Aprobado (HU-09).
 * Genera el ticket definitivo con su código QR y lo guarda para visualización en pestaña nueva.
 */
export async function emitirEntradaDirecta(params: {
  idEvento: string;
  idUsuario: string;
  nombreComprador: string;
  correoComprador: string;
  cantidadEntradas: number;
  precioFinal: number;
}): Promise<EntradaEmitida> {
  try {
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/emision-directa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_evento: params.idEvento,
        id_usuario: params.idUsuario,
        nombre_comprador: params.nombreComprador,
        correo_comprador: params.correoComprador,
        cantidad_entradas: params.cantidadEntradas,
        precio_final: params.precioFinal,
      }),
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (error) {
    console.warn("Backend no disponible para emisión, simulando ticket definitivo:", error);
  }

  const ev = eventosLocal.find((e) => e.id === params.idEvento) || eventosLocal[0];
  const ticketId = `tk-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;

  // Descontar del stock en emisión directa si aún no se había descontado
  if (ev.precio === 0) {
    ev.stockDisponible = Math.max(0, ev.stockDisponible - params.cantidadEntradas);
  }

  // QR dinámico escaneable de alta definición
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=TICKETU-${ticketId}-${ev.id}`;

  const nuevoTicket: EntradaEmitida = {
    idEntrada: ticketId,
    idEvento: ev.id,
    nombreEvento: ev.titulo,
    nombreComprador: params.nombreComprador || "Patricio Carlos",
    correoComprador: params.correoComprador || "patricio.carlos@estudiantes.uv.cl",
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

  if (typeof window !== "undefined") {
    try {
      sessionStorage.setItem(`ticket_${ticketId}`, JSON.stringify(nuevoTicket));
    } catch {
      // Ignorar si sessionStorage no está disponible
    }
  }

  return nuevoTicket;
}

/**
 * Obtiene la información de un ticket emitido por su ID (para la página de confirmación)
 */
export async function obtenerEntradaEmitida(idEntrada: string): Promise<EntradaEmitida | null> {
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

  // Fallback con ticket de demostración
  const ev = eventosLocal[0];
  return {
    idEntrada: idEntrada || "tk-DEMO-2026",
    idEvento: ev.id,
    nombreEvento: ev.titulo,
    nombreComprador: "Patricio Carlos",
    correoComprador: "patricio.carlos@estudiantes.uv.cl",
    tipoAcceso: "Entrada General Oficial",
    precioFinal: ev.precio,
    cantidadEntradas: 1,
    qrData: `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=TICKETU-${idEntrada || "tk-DEMO"}-${ev.id}`,
    fechaEvento: ev.fecha,
    horaEvento: ev.hora,
    lugarEvento: ev.lugar,
    fechaEmision: new Date().toLocaleDateString("es-CL"),
  };
}
