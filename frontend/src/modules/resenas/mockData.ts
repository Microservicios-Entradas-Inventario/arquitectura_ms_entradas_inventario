import expoUvImage from "./assets/expo-uv-2026.png";
import type { ReviewEvent } from "./types";

/**
 * DATOS PROVISIONALES DEL EVENTO.
 * Mientras Catálogo no entregue estos datos (nombre, estado, organizador,
 * imagen), se usan valores fijos. Las reseñas ya vienen del backend.
 * TODO: reemplazar por la API de Catálogo (GET /eventos/{eventoId}).
 */
export const MOCK_EVENT: ReviewEvent = {
  id: "1",
  name: "Expo UV 2026 Valparaíso",
  status: "finalizado",
  organizerId: "1",
  imageSrc: expoUvImage,
};

export function getMockEvent(eventoId: string): ReviewEvent {
  return { ...MOCK_EVENT, id: eventoId };
}
