import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 20, ...rest }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    "aria-hidden": true,
    focusable: false,
    ...rest,
  } as const;
}

/** Estrella rellena (la usan las calificaciones). */
export function StarIcon(props: IconProps) {
  return (
    <svg
      {...base(props)}
      fill="currentColor"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinejoin="round"
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

/** Triángulo relleno del botón de mostrar/ocultar (▼ / ▲ del mockup). */
export function TriangleIcon({ up, ...props }: IconProps & { up?: boolean }) {
  return (
    <svg {...base({ size: 10, ...props })} fill="currentColor" viewBox="0 0 10 10">
      {up ? <path d="M5 1.5 9 8.5H1z" /> : <path d="M5 8.5 1 1.5h8z" />}
    </svg>
  );
}

/** Alerta (círculo con "!") para mensajes de error. */
export function AlertIcon(props: IconProps) {
  return (
    <svg
      {...base({ size: 16, ...props })}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

/** Información (círculo con "i"). */
export function InfoIcon(props: IconProps) {
  return (
    <svg
      {...base({ size: 18, ...props })}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

/** Check (para mensajes de éxito). */
export function CheckIcon(props: IconProps) {
  return (
    <svg
      {...base({ size: 18, ...props })}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="8 12.5 11 15.5 16 9" />
    </svg>
  );
}
