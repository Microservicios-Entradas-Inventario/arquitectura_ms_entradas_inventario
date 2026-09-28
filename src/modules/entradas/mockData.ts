// ============================================================================
// modules/entradas/mockData.ts
// ----------------------------------------------------------------------------
// Datos simulados (Mocks) para pruebas locales y presentaciones en vivo.
// Todos los campos en camelCase estricto.
// ============================================================================

import { EventoEntradas, PromocionAplicada } from "./types";

export const MOCK_EVENTOS_ENTRADAS: EventoEntradas[] = [
  {
    id: "evt-001",
    titulo: "Gala Aniversario Civil Informática UV 2026",
    fecha: "18 de Noviembre, 2026",
    hora: "20:00 hrs",
    lugar: "Salón de Honor, Sede Central UV",
    descripcion: "Cena de camaradería, balance del año y fiesta de clausura para la comunidad de informática.",
    tipoEntrada: "PAGADA",
    precio: 6000,
    stockTotal: 200,
    stockDisponible: 74,
    maxTickets: 6, // Máximo por compra 
    estadoGestion: "PUBLICADO",
  },
  {
    id: "evt-002",
    titulo: "Torneo eSports Inter-Carreras UV 2026",
    fecha: "25 de Octubre, 2026",
    hora: "14:00 hrs",
    lugar: "Laboratorio Central de Computación, Facultad de Ingeniería",
    descripcion: "Competencia oficial de videojuegos universitarios. Acceso gratuito para toda la comunidad.",
    tipoEntrada: "GRATUITA",
    precio: 0,
    stockTotal: 100,
    stockDisponible: 25,
    maxTickets: 2,
    limiteGratuitoUsuario: 2, // HU-08: Límite estricto de entradas gratuitas por alumno
    estadoGestion: "PUBLICADO",
  },
  {
    id: "evt-003",
    titulo: "Workshop: Inteligencia Artificial en Microservicios",
    fecha: "05 de Noviembre, 2026",
    hora: "10:30 hrs",
    lugar: "Auditorio de Postgrado, Campus Playa Ancha",
    descripcion: "Taller práctico intensivo con despliegue de modelos en contenedores Docker.",
    tipoEntrada: "GRATUITA",
    precio: 0,
    stockTotal: 50,
    stockDisponible: 0, // Aforo en 0 para probar HU-07 (Notificación de stock agotado)
    maxTickets: 1,
    limiteGratuitoUsuario: 1,
    estadoGestion: "PUBLICADO",
  },
  {
    id: "evt-004",
    titulo: "Fiesta Mechona Info 2026",
    fecha: "20 de Noviembre, 2026",
    hora: "22:00 hrs",
    lugar: "Centro de Eventos El Canelo",
    descripcion: "Bienvenida oficial a la nueva generación de estudiantes de ingeniería.",
    tipoEntrada: "PAGADA",
    precio: 4500,
    stockTotal: 300,
    stockDisponible: 148,
    maxTickets: 6,
    estadoGestion: "PUBLICADO",
  },
];

/**
 * Promociones de prueba local
 */
export const MOCK_PROMOCIONES: Record<string, PromocionAplicada> = {
  INFO2026: {
    codigo: "INFO2026",
    idPromocion: "promo-info-2026",
    porcentajeDescuento: 15,
    descripcion: "15% de Descuento Especial Alumnos Civil Informática",
  },
  TITEC20: {
    codigo: "TITEC20",
    idPromocion: "promo-titec-20",
    porcentajeDescuento: 20,
    descripcion: "20% OFF Convenio Taller de Integración Tecnológica",
  },
  MECHON: {
    codigo: "MECHON",
    idPromocion: "promo-mechon-10",
    porcentajeDescuento: 10,
    descripcion: "10% Descuento Bienvenida Mechona",
  },
};
