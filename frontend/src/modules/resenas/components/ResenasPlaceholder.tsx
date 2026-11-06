"use client";

// ============================================================================
// modules/resenas/components/ResenasPlaceholder.tsx
// ----------------------------------------------------------------------------
// Grupo 6 — Reseñas de un evento (HU1: calificar y comentar, HU4: respuesta
// pública del organizador).
//
// Se conserva el nombre y el export por defecto para no romper los imports que
// ya existen en:
//   - app/catalogo/[eventoId]/page.tsx          (detalle del evento, Grupo 2)
//   - app/catalogo/[eventoId]/resenas/page.tsx  (ruta propia, Grupo 6)
// Si se quiere renombrar a "Resenas", hay que coordinarlo con el Grupo 2.
// ============================================================================

import { getMockEvent } from "../mockData";
import { useCurrentUser } from "../useCurrentUser";
import { ReviewsSection } from "./ReviewsSection";

export default function ResenasPlaceholder({ eventoId }: { eventoId: string }) {
  const currentUser = useCurrentUser();
  // TODO: el evento vendrá de Catálogo.
  const event = getMockEvent(eventoId);

  return <ReviewsSection event={event} currentUser={currentUser} />;
}
