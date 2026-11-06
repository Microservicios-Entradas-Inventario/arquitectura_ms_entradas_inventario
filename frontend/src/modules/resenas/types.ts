import type { StaticImageData } from "next/image";

export type EventStatus = "borrador" | "publicado" | "finalizado" | "cancelado";

export interface ReviewEvent {
  id: string;
  name: string;
  status: EventStatus;
  /** Id del usuario organizador del evento (único que puede responder reseñas). */
  organizerId: string;
  /** Imagen del evento (import estático o URL) */
  imageSrc: string | StaticImageData;
}

export interface CurrentUser {
  id: string;
  name: string;
}

export interface ReviewReply {
  id: string;
  authorName: string;
  text: string;
  /** Fecha ISO */
  createdAt: string;
}

export interface Review {
  id: string;
  eventId: string;
  userId: string;
  userName: string;
  /** Obligatoria: entero de 1 a 5 */
  rating: number;
  /** Opcional */
  comment?: string;
  /** Fecha ISO */
  createdAt: string;
  /** Respuesta pública del organizador (HU4) */
  reply?: ReviewReply;
}

export interface NewReviewInput {
  rating: number;
  comment?: string;
}
