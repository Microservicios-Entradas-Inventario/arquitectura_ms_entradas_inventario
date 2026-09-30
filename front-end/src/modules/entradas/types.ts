// ============================================================================
// modules/entradas/types.ts
// ----------------------------------------------------------------------------
// Modelos y tipos de datos del Microservicio de Entradas e Inventario
// Alineados con los Contratos de Interfaz (Catálogo, Pagos, Panel, Promociones)
// y con nomenclatura estandarizada en camelCase.
// ============================================================================

/**
 * Glosario homologado estricto con Panel Organizador y Catálogo
 */
export type TipoEntrada = "PAGADA" | "GRATUITA";

export type EstadoGestionEvento = "BORRADOR" | "PUBLICADO" | "FINALIZADO" | "CANCELADO";

/**
 * Información de aforo y stock de un evento (HU-01 y Contrato con Panel)
 */
export interface EventoEntradas {
  id: string;
  titulo: string;
  fecha: string;
  hora: string;
  lugar: string;
  descripcion?: string;
  tipoEntrada: TipoEntrada;
  precio: number;                      // 0 si es GRATUITA
  stockTotal: number;
  stockDisponible: number;
  maxTickets: number;                 // Máximo de tickets por transacción (HU-02 y tabla dependencias)
  limiteGratuitoUsuario?: number;    // HU-08: Límite por usuario para entradas gratuitas
  estadoGestion: EstadoGestionEvento;
}

/**
 * Contrato con Promociones (Grupo 9):
 * Permite aplicar reglas de descuento a una compra antes de emitir la reserva.
 */
export interface PromocionAplicada {
  codigo: string;
  idPromocion: string;
  porcentajeDescuento: number;        // Porcentaje entre 1 y 100
  descripcion: string;
}

/**
 * Desglose financiero con cálculo de descuentos
 */
export interface ResumenCalculo {
  cantidad: number;
  precioUnitario: number;
  subtotal: number;
  porcentajeDescuento: number;
  montoDescuento: number;
  totalFinal: number;
  promocion?: PromocionAplicada;
}

/**
 * Reserva temporal de cupo (HU-03 y Contrato con Pagos)
 */
export interface ReservaTemporal {
  idReserva: string;                  // holdId único
  idEvento: string;
  idUsuario: string;
  cantidadEntradas: number;
  subtotal: number;
  descuento: number;
  total: number;
  estado: "PENDIENTE" | "APROBADO" | "CANCELADO" | "EXPIRADO";
  expiraEnMinutos: number;             // TTL de retención (15 minutos)
  fechaCreacion: string;
}

/**
 * Entrada consolidada con QR de acceso (HU-04, HU-05 y Contrato Check-in / Notificaciones)
 */
export interface EntradaEmitida {
  idEntrada: string;                  // Identificador único (tk-...)
  idEvento: string;
  nombreEvento: string;
  nombreComprador: string;
  correoComprador: string;
  tipoAcceso: string;
  precioFinal: number;
  cantidadEntradas: number;
  qrData: string;                     // URL o hash de acceso para escaneo en puerta
  fechaEvento: string;
  horaEvento: string;
  lugarEvento: string;
  fechaEmision: string;
}
