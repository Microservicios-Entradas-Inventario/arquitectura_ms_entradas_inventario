"use client";

import { useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { StarIcon } from "./icons";
import styles from "./reviews.module.css";

const LABELS = ["Muy malo", "Malo", "Regular", "Bueno", "Excelente"];

/** Estrellas de solo lectura (tarjetas y resumen). */
export function StarDisplay({ rating, size = 16 }: { rating: number; size?: number }) {
  const rounded = Math.round(rating);
  return (
    <span
      className={styles.stars}
      role="img"
      aria-label={`${rating.toFixed(rating % 1 === 0 ? 0 : 1)} de 5 estrellas`}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={n <= rounded ? styles.starOn : styles.starOff}>
          <StarIcon size={size} />
        </span>
      ))}
    </span>
  );
}

interface StarInputProps {
  value: number;
  onChange: (value: number) => void;
  labelledBy: string;
  describedBy?: string;
  invalid?: boolean;
}

/** Selector de calificación 1–5 (radiogroup con teclado: flechas, Home, End). */
export function StarInput({ value, onChange, labelledBy, describedBy, invalid }: StarInputProps) {
  const [hover, setHover] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const shown = hover || value;

  function move(next: number) {
    const clamped = Math.min(5, Math.max(1, next));
    onChange(clamped);
    refs.current[clamped - 1]?.focus();
  }

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, n: number) {
    switch (e.key) {
      case "ArrowRight":
      case "ArrowUp":
        e.preventDefault();
        move(n + 1);
        break;
      case "ArrowLeft":
      case "ArrowDown":
        e.preventDefault();
        move(n - 1);
        break;
      case "Home":
        e.preventDefault();
        move(1);
        break;
      case "End":
        e.preventDefault();
        move(5);
        break;
    }
  }

  return (
    <div className={styles.starInputRow}>
      <div
        role="radiogroup"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
        className={styles.starGroup}
        onMouseLeave={() => setHover(0)}
      >
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            ref={(el) => {
              refs.current[n - 1] = el;
            }}
            type="button"
            role="radio"
            aria-checked={value === n}
            aria-label={`${n} ${n === 1 ? "estrella" : "estrellas"}`}
            tabIndex={n === (value || 1) ? 0 : -1}
            className={`${styles.starButton} ${n <= shown ? styles.starOn : styles.starOff}`}
            onClick={() => onChange(n)}
            onMouseEnter={() => setHover(n)}
            onKeyDown={(e) => onKeyDown(e, n)}
          >
            <StarIcon size={28} />
          </button>
        ))}
      </div>
      <span className={styles.starHint} aria-hidden="true">
        {shown ? LABELS[shown - 1] : "Elige de 1 a 5 estrellas"}
      </span>
    </div>
  );
}
