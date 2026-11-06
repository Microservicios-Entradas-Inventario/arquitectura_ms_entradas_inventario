"use client";

import { useId, useState } from "react";
import type { FormEvent } from "react";
import { AlertIcon } from "./icons";
import { StarDisplay } from "./Stars";
import type { Review } from "../types";
import { getAvatarColor, getInitials, timeAgo } from "../utils";
import styles from "./reviews.module.css";

const MAX_REPLY = 500;

interface ReviewCardProps {
  review: Review;
  /** true solo si el usuario actual es el organizador del evento. */
  canReply: boolean;
  onReply: (reviewId: string, text: string) => void | Promise<void>;
}

export function ReviewCard({ review, canReply, onReply }: ReviewCardProps) {
  const uid = useId();
  const replyFieldId = `${uid}-reply`;
  const replyErrorId = `${uid}-reply-error`;

  const [replying, setReplying] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function closeForm() {
    setReplying(false);
    setText("");
    setError(null);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) {
      setError("Escribe una respuesta antes de publicarla.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onReply(review.id, trimmed);
      closeForm();
    } catch (replyError) {
      setError(
        replyError instanceof Error
          ? replyError.message
          : "No se pudo publicar la respuesta.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <article className={styles.card}>
      <header className={styles.cardHead}>
        <span
          className={styles.avatar}
          style={{ backgroundColor: getAvatarColor(review.userId) }}
          aria-hidden="true"
        >
          {getInitials(review.userName)}
        </span>
        <div className={styles.who}>
          <p className={styles.name}>{review.userName}</p>
          <p className={styles.time}>{timeAgo(review.createdAt)}</p>
        </div>
        <StarDisplay rating={review.rating} />
      </header>

      {review.comment && <p className={styles.comment}>{review.comment}</p>}

      {review.reply && (
        <div className={styles.reply}>
          <div className={styles.replyHead}>
            <span className={styles.badge}>Organizador</span>
            <span className={styles.replyAuthor}>{review.reply.authorName}</span>
            <span className={styles.time}>{timeAgo(review.reply.createdAt)}</span>
          </div>
          <p className={styles.replyText}>{review.reply.text}</p>
        </div>
      )}

      {canReply && !review.reply && !replying && (
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => setReplying(true)}
          >
            Responder
          </button>
        </div>
      )}

      {canReply && !review.reply && replying && (
        <form className={styles.replyForm} onSubmit={handleSubmit} noValidate>
          <label htmlFor={replyFieldId} className={styles.label}>
            Tu respuesta pública
          </label>
          <textarea
            id={replyFieldId}
            className={`${styles.textarea} ${error ? styles.textareaInvalid : ""}`}
            value={text}
            maxLength={MAX_REPLY}
            rows={3}
            placeholder={`Responde a ${review.userName.split(" ")[0]}…`}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? replyErrorId : undefined}
            onChange={(e) => {
              setText(e.target.value);
              if (error) setError(null);
            }}
            disabled={submitting}
            autoFocus
          />
          {error && (
            <p id={replyErrorId} role="alert" className={styles.error}>
              <AlertIcon />
              {error}
            </p>
          )}
          <div className={styles.actions}>
            <button type="submit" className={styles.primaryButton} disabled={submitting}>
              {submitting ? "Publicando…" : "Publicar respuesta"}
            </button>
            <button type="button" className={styles.secondaryButton} onClick={closeForm} disabled={submitting}>
              Cancelar
            </button>
          </div>
        </form>
      )}
    </article>
  );
}
