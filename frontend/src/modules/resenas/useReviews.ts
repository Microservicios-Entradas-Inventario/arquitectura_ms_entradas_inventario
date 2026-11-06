"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { CurrentUser, NewReviewInput, Review } from "./types";
import { crearResena, crearRespuesta, obtenerResenasDeEvento } from "./api";

export function useReviews(eventId: string) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setReviews([]);

    obtenerResenasDeEvento(eventId)
      .then((data) => {
        if (!cancelled) setReviews(data);
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "No se pudieron cargar las reseñas.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [eventId]);

  /** Reseñas ordenadas de la más nueva a la más antigua. */
  const sorted = useMemo(
    () =>
      [...reviews].sort(
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
      ),
    [reviews],
  );

  const addReview = useCallback(
    async (user: CurrentUser, input: NewReviewInput) => {
      const review = await crearResena(eventId, user.id, input);
      setReviews((prev) => [review, ...prev.filter((item) => item.id !== review.id)]);
    },
    [eventId],
  );

  const addReply = useCallback(
    async (reviewId: string, author: CurrentUser, text: string) => {
      const reply = await crearRespuesta(reviewId, author.id, text);
      setReviews((prev) =>
        prev.map((review) =>
          review.id === reviewId
            ? {
                ...review,
                reply: {
                  id: String(reply.id_resena),
                  authorName: reply.nombre_responsable ?? author.name,
                  text: reply.texto,
                  createdAt: reply.fecha_respuesta,
                },
              }
            : review,
        ),
      );
    },
    [],
  );

  return { reviews: sorted, loading, error, addReview, addReply };
}
