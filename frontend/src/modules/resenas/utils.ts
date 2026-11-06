const rtf = new Intl.RelativeTimeFormat("es", { numeric: "always" });

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;
const MONTH = 30 * DAY;
const YEAR = 365 * DAY;

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** "Hace 2 días", "Hace 1 semana"… */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const diff = Math.max(0, now - new Date(iso).getTime());
  if (diff < MINUTE) return "Hace un momento";
  if (diff < HOUR) return capitalize(rtf.format(-Math.floor(diff / MINUTE), "minute"));
  if (diff < DAY) return capitalize(rtf.format(-Math.floor(diff / HOUR), "hour"));
  if (diff < WEEK) return capitalize(rtf.format(-Math.floor(diff / DAY), "day"));
  if (diff < MONTH) return capitalize(rtf.format(-Math.floor(diff / WEEK), "week"));
  if (diff < YEAR) return capitalize(rtf.format(-Math.floor(diff / MONTH), "month"));
  return capitalize(rtf.format(-Math.floor(diff / YEAR), "year"));
}

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0].charAt(0);
  const second = parts.length > 1 ? parts[1].charAt(0) : "";
  return (first + second).toUpperCase();
}

/**
 * Colores de avatar con contraste >= 4.5:1 contra texto blanco (WCAG AA).
 * Mantienen la paleta del mockup (azul, verde, naranja) en tonos más oscuros.
 */
const AVATAR_COLORS = ["#2563EB", "#047857", "#B45309", "#7C3AED", "#BE123C"];

export function getAvatarColor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}
