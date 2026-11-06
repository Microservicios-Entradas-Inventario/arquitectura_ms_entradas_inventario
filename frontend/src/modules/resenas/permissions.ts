import type { CurrentUser, Review, ReviewEvent } from "./types";

/**
 * Reglas de negocio de reseñas, aplicadas en el front para guiar al usuario.
 * IMPORTANTE: el backend debe validarlas de nuevo (check-in, una reseña por
 * usuario, organizador del evento). Aquí solo decidimos qué mostrar.
 */

export type ReviewBlockReason =
  | "guest" // sin sesión
  | "organizer" // el organizador responde, no reseña
  | "event-not-finished" // solo se reseña al finalizar el evento
  | "no-check-in" // HU1: solo asistentes con check-in confirmado
  | "already-reviewed"; // HU1: una reseña por usuario por evento

export type ReviewEligibility =
  | { canReview: true }
  | { canReview: false; reason: ReviewBlockReason };

interface EligibilityArgs {
  event: ReviewEvent;
  user: CurrentUser | null;
  hasCheckIn: boolean;
  reviews: Review[];
}

export function getReviewEligibility({
  event,
  user,
  hasCheckIn,
  reviews,
}: EligibilityArgs): ReviewEligibility {
  if (!user) return { canReview: false, reason: "guest" };
  if (user.id === event.organizerId) {
    return { canReview: false, reason: "organizer" };
  }
  if (event.status !== "finalizado") {
    return { canReview: false, reason: "event-not-finished" };
  }
  if (!hasCheckIn) return { canReview: false, reason: "no-check-in" };
  if (reviews.some((r) => r.userId === user.id)) {
    return { canReview: false, reason: "already-reviewed" };
  }
  return { canReview: true };
}

/** HU4: solo el organizador de ese evento puede responder reseñas. */
export function canReplyToReviews(
  user: CurrentUser | null,
  event: ReviewEvent,
): boolean {
  return user !== null && user.id === event.organizerId;
}

export const BLOCK_MESSAGES: Record<ReviewBlockReason, string> = {
  guest: "Inicia sesión para dejar tu reseña.",
  organizer: "Como organizador, puedes responder las reseñas de tu evento.",
  "event-not-finished": "Podrás reseñar este evento cuando finalice.",
  "no-check-in": "Solo pueden reseñar quienes hicieron check-in en el evento.",
  "already-reviewed":
    "Ya reseñaste este evento. Se permite una reseña por asistente.",
};
