import { Inter, Poppins } from "next/font/google";

/**
 * Tipografías del design system Ticket-U: Poppins (títulos, números) e Inter (cuerpo).
 * Si el layout raíz del proyecto ya carga estas fuentes con las variables
 * --font-poppins y --font-inter, este archivo se puede eliminar.
 */
export const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "600"],
  variable: "--font-inter",
  display: "swap",
});

export const poppins = Poppins({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-poppins",
  display: "swap",
});
