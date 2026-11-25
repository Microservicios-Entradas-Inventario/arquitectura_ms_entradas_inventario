// ============================================================================
// modules/entradas/types.ts
// Modelos y tipos de datos del módulo de Entradas e Inventario
// ============================================================================

export type TipoEntrada = "PAGADA" | "GRATUITA";

export type EstadoGestionEvento = "BORRADOR" | "PUBLICADO" | "FINALIZADO" | "CANCELADO";

export interface EventoEntradas {
  id: string;
  titulo: string;
  fecha: string;
  hora: string;
  lugar: string;
  descripcion?: string;
  tipoEntrada: TipoEntrada;
  precio: number;
  stockTotal: number;
  stockDisponible: number;
  maxTickets: number;
  limiteGratuitoUsuario?: number;
  estadoGestion: EstadoGestionEvento;
  origen?: "PANEL" | "CATALOGO";
}

export interface PromocionAplicada {
  codigo: string;
  idPromocion: string;
  porcentajeDescuento: number;
  descripcion: string;
}

export interface ResultadoEvaluacionPromocion {
  promocion: PromocionAplicada | null;
  mensaje?: string;
}

export interface ResumenCalculo {
  cantidad: number;
  precioUnitario: number;
  subtotal: number;
  porcentajeDescuento: number;
  montoDescuento: number;
  totalFinal: number;
  promocion?: PromocionAplicada;
}

export interface ReservaTemporal {
  idReserva: string;
  idEvento: string;
  idUsuario: string;
  cantidadEntradas: number;
  subtotal: number;
  descuento: number;
  total: number;
  avisoPromocion?: string;
  estado: "PENDIENTE" | "RESERVADO" | "CONSOLIDADO" | "CANCELADO" | "EXPIRADO" | string;
  expiraEnMinutos: number;
  segundosRestantes?: number;
  fechaCreacion: string;
}

export interface EntradaEmitida {
  idEntrada: string;
  entradasEmitidas?: string[];
  idEvento: string;
  nombreEvento: string;
  nombreComprador: string;
  correoComprador: string;
  tipoAcceso: string;
  precioFinal: number;
  cantidadEntradas: number;
  qrData: string;
  fechaEvento: string;
  horaEvento: string;
  lugarEvento: string;
  fechaEmision: string;
  estadoEntrada?: string;
}
