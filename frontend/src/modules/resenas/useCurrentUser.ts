"use client";

import type { CurrentUser } from "./types";

/**
 * Usuario con sesión iniciada (null = visitante).
 *
 * TODO: conectar con el módulo Auth (Grupo 1) cuando exponga la sesión.
 * Es el ÚNICO punto del módulo que debe cambiar para eso: el resto ya recibe
 * un CurrentUser { id, name } y decide qué mostrar según su rol.
 * Mientras no haya sesión, todos son visitantes.
 */
export function useCurrentUser(): CurrentUser | null {
  return null;
}
