"use client";

import Image from "next/image";
import { useId, useState } from "react";
import { CheckIcon, InfoIcon, TriangleIcon } from "./icons";
import { inter, poppins } from "../fonts";
import {
  BLOCK_MESSAGES,
  canReplyToReviews,
  getReviewEligibility,
} from "../permissions";
import { ReviewCard } from "./ReviewCard";
import { ReviewForm } from "./ReviewForm";
import { StarDisplay } from "./Stars";
import type { CurrentUser, NewReviewInput, ReviewEvent } from "../types";
import { useReviews } from "../useReviews";
import styles from "./reviews.module.css";

/** Cuántas reseñas se ven antes de pulsar "Ver todas las reseñas". */
const PREVIEW_COUNT = 3;

interface ReviewsSectionProps {
  event: ReviewEvent;
  /** Usuario con sesión iniciada (null = visitante). Lo entrega el módulo de autenticación. */
  currentUser: CurrentUser | null;
}

export function ReviewsSection({ event, currentUser }: ReviewsSectionProps) {
  const panelId = useId();
  const { reviews, loading, error, addReview, addReply } = useReviews(event.id);

  // open: lo que el usuario quiere (abierto/cerrado).
  // mounted: si el panel existe en la página. Al cerrar se mantiene hasta que
  // termina la animación de salida, y recién entonces se elimina.
  const [open, setOpen] = useState(false); // Estado 1: colapsado por defecto
  const [mounted, setMounted] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [justPublishedBy, setJustPublishedBy] = useState<string | null>(null);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const eligibility = getReviewEligibility({
    event,
    user: currentUser,
    // El check-in lo valida el backend (responde 403 si el usuario no asistió) y
    // el mensaje se muestra al intentar publicar. TODO: consultar Check-in antes
    // de mostrar el formulario (Contrato Check-in).
    hasCheckIn: true,
    reviews,
  });
  const canReply = canReplyToReviews(currentUser, event);

  const total = reviews.length;
  const average = total > 0 ? reviews.reduce((sum, r) => sum + r.rating, 0) / total : 0;
  const visible = showAll ? reviews : reviews.slice(0, PREVIEW_COUNT);

  function toggle() {
    if (open) {
      setOpen(false); // inicia la animación de salida; el panel se quita al terminar
    } else {
      setMounted(true);
      setOpen(true);
    }
  }

  async function handleSubmit(input: NewReviewInput) {
    if (!currentUser) return;
    setSubmittingReview(true);
    setActionError(null);
    try {
      await addReview(currentUser, input);
      setJustPublishedBy(currentUser.id);
    } catch (submitError) {
      setActionError(
        submitError instanceof Error
          ? submitError.message
          : "No se pudo publicar la reseña.",
      );
    } finally {
      setSubmittingReview(false);
    }
  }

  function renderReviewArea() {
    if (loading) {
      return <p className={styles.notice} role="status">Conectando con la API de reseñas…</p>;
    }
    if (error) {
      return (
        <p className={`${styles.notice} ${styles.noticeInfo}`} role="alert">
          No se pudo conectar con la API de reseñas: {error}
        </p>
      );
    }
    if (eligibility.canReview) {
      return (
        <>
          {actionError && (
            <p className={`${styles.notice} ${styles.noticeInfo}`} role="alert">
              {actionError}
            </p>
          )}
          <ReviewForm onSubmit={handleSubmit} isSubmitting={submittingReview} />
        </>
      );
    }
    if (
      eligibility.reason === "already-reviewed" &&
      currentUser &&
      justPublishedBy === currentUser.id
    ) {
      return (
        <p className={`${styles.notice} ${styles.noticeSuccess}`} role="status">
          <CheckIcon />
          Tu reseña ya está publicada. ¡Gracias por compartir tu experiencia!
        </p>
      );
    }
    return (
      <p
        className={`${styles.notice} ${
          eligibility.reason === "already-reviewed" ? styles.noticeSuccess : styles.noticeInfo
        }`}
        role="status"
      >
        {eligibility.reason === "already-reviewed" ? <CheckIcon /> : <InfoIcon />}
        {BLOCK_MESSAGES[eligibility.reason]}
      </p>
    );
  }

  return (
    <section
      className={`${styles.root} ${inter.variable} ${poppins.variable}`}
      aria-label="Reseñas del evento"
    >
      <div className={styles.toggleRow}>
        <span className={styles.line} aria-hidden="true" />
        <button
          type="button"
          className={styles.toggleButton}
          aria-expanded={open}
          aria-controls={panelId}
          onClick={toggle}
        >
          {open ? "Ocultar reseñas" : "Ver reseñas"}
          <TriangleIcon up={open} />
        </button>
        <span className={styles.line} aria-hidden="true" />
      </div>

      {mounted && (
        <div
          id={panelId}
          className={`${styles.panel} ${open ? "" : styles.panelClosing}`}
          onAnimationEnd={(e) => {
            // Solo la animación del propio panel (no la de elementos internos)
            if (e.target === e.currentTarget && !open) setMounted(false);
          }}
        >
          <div className={styles.header}>
            <div className={styles.headerText}>
              <h2 className={styles.title}>Reseñas del evento</h2>
              <p className={styles.subtitle}>
                Opiniones y calificaciones reales de asistentes que vivieron el evento en
                primera fila.
              </p>
            </div>

            <div className={styles.summary}>
              <Image
                className={styles.summaryImage}
                src={event.imageSrc}
                alt={`Imagen de ${event.name}`}
                width={101}
                height={108}
              />
              <div className={styles.summaryBody}>
                {total > 0 ? (
                  <>
                    <p className={styles.score}>
                      <span className={styles.scoreValue}>{average.toFixed(1)}</span>
                      <span className={styles.scoreMax}>/ 5.0</span>
                    </p>
                    <StarDisplay rating={average} size={14} />
                    <p className={styles.summaryCaption}>
                      Basado en {total.toLocaleString("es-CL")}{" "}
                      {total === 1 ? "reseña real" : "reseñas reales"}
                    </p>
                  </>
                ) : (
                  <p className={styles.summaryCaption}>
                    {error ? "No se pudo cargar el promedio" : "Aún sin calificaciones"}
                  </p>
                )}
              </div>
            </div>
          </div>

          {renderReviewArea()}

          {loading ? (
            <p className={styles.empty} role="status">Cargando reseñas…</p>
          ) : error ? null : total === 0 ? (
            <p className={styles.empty}>Aún no hay reseñas para este evento.</p>
          ) : (
            <div className={styles.list}>
              {visible.map((review) => (
                <ReviewCard
                  key={review.id}
                  review={review}
                  canReply={canReply}
                  onReply={(reviewId, text) =>
                    currentUser
                      ? addReply(reviewId, currentUser, text)
                      : Promise.resolve()
                  }
                />
              ))}
            </div>
          )}

          {total > PREVIEW_COUNT && (
            <div className={styles.moreRow}>
              <button
                type="button"
                className={styles.primaryButton}
                onClick={() => setShowAll((v) => !v)}
              >
                {showAll ? "Ver menos reseñas" : "Ver todas las reseñas"}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}