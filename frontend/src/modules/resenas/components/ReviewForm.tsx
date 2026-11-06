"use client";

import { useId, useState } from "react";
import type { FormEvent } from "react";
import { AlertIcon } from "./icons";
import { StarInput } from "./Stars";
import type { NewReviewInput } from "../types";
import styles from "./reviews.module.css";

const MAX_COMMENT = 500;

export function ReviewForm({
  onSubmit,
  isSubmitting = false,
}: {
  onSubmit: (input: NewReviewInput) => void | Promise<void>;
  isSubmitting?: boolean;
}) {
  const uid = useId();
  const ratingLabelId = `${uid}-rating-label`;
  const ratingErrorId = `${uid}-rating-error`;
  const commentId = `${uid}-comment`;

  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [ratingError, setRatingError] = useState<string | null>(null);

  function handleRating(value: number) {
    setRating(value);
    setRatingError(null);
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // La calificación es obligatoria; el comentario es opcional.
    if (rating < 1) {
      setRatingError("Selecciona una calificación de 1 a 5 estrellas.");
      return;
    }
    const trimmed = comment.trim();
    onSubmit({ rating, comment: trimmed ? trimmed : undefined });
  }

  return (
    <form className={styles.formCard} onSubmit={handleSubmit} noValidate>
      <h3 className={styles.formTitle}>Deja tu reseña</h3>

      <div className={styles.field}>
        <span id={ratingLabelId} className={styles.label}>
          Calificación <span className={styles.required}>(obligatoria)</span>
        </span>
        <StarInput
          value={rating}
          onChange={handleRating}
          labelledBy={ratingLabelId}
          describedBy={ratingError ? ratingErrorId : undefined}
          invalid={Boolean(ratingError)}
        />
        {ratingError && (
          <p id={ratingErrorId} role="alert" className={styles.error}>
            <AlertIcon />
            {ratingError}
          </p>
        )}
      </div>

      <div className={styles.field}>
        <label htmlFor={commentId} className={styles.label}>
          Comentario <span className={styles.optional}>(opcional)</span>
        </label>
        <textarea
          id={commentId}
          className={styles.textarea}
          value={comment}
          maxLength={MAX_COMMENT}
          rows={3}
          placeholder="¿Qué te pareció el evento?"
          onChange={(e) => setComment(e.target.value)}
        />
        <span className={styles.counter}>
          {comment.length}/{MAX_COMMENT}
        </span>
      </div>

      <div className={styles.actions}>
        <button type="submit" className={styles.primaryButton} disabled={isSubmitting}>
          {isSubmitting ? "Publicando…" : "Publicar reseña"}
        </button>
      </div>
    </form>
  );
}
