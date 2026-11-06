// ============================================================================
// modules/notificaciones/api.ts
// ----------------------------------------------------------------------------
// Este módulo usa el API Gateway igual que el resto de la aplicación.
// ============================================================================

import { GATEWAY_URL } from "@/lib/env";

const BASE_PATH = "/api/notificaciones";

export type Notificacion = {
  id_notificacion: string | number;
  id_usuario: string;
  tipo: string;
  titulo: string;
  mensaje: string;
  estado: "no_leida" | "leida" | "eliminada";
  fecha_emision: string;
  datos: Record<string, unknown>;
  canal: "APP" | "EMAIL";
};

type NotificacionApi = {
  id_notificacion: string | number;
  id_usuario?: string;
  tipo?: string;
  titulo?: string;
  mensaje: string;
  estado?: string;
  estado_lectura?: string;
  fecha_emision?: string;
  created_at?: string;
  datos?: Record<string, unknown> | null;
  canal?: string;
};

function normalizar_notificacion(valor: unknown): Notificacion {
  if (typeof valor !== "object" || valor === null) {
    throw new Error("El servicio devolvió una notificación inválida.");
  }

  const notificacion = valor as Partial<NotificacionApi>;
  const tipo = notificacion.tipo ?? notificacion.titulo;
  const estado = (notificacion.estado_lectura ?? notificacion.estado)?.toLowerCase();
  const fecha_emision = notificacion.fecha_emision ?? notificacion.created_at;
  const canal = notificacion.canal ?? "APP";

  if (
    (typeof notificacion.id_notificacion !== "string" &&
      typeof notificacion.id_notificacion !== "number") ||
    typeof notificacion.id_usuario !== "string" ||
    typeof tipo !== "string" ||
    typeof notificacion.mensaje !== "string" ||
    (estado !== "no_leida" && estado !== "leida" && estado !== "eliminada") ||
    typeof fecha_emision !== "string" ||
    (canal !== "APP" && canal !== "EMAIL") ||
    (notificacion.datos !== undefined &&
      notificacion.datos !== null &&
      (typeof notificacion.datos !== "object" || Array.isArray(notificacion.datos)))
  ) {
    throw new Error("El servicio devolvió una notificación con un formato inesperado.");
  }

  return {
    id_notificacion: notificacion.id_notificacion,
    id_usuario: notificacion.id_usuario,
    tipo,
    titulo: tipo,
    mensaje: notificacion.mensaje,
    estado,
    fecha_emision,
    datos: notificacion.datos ?? {},
    canal,
  };
}

function verificar_respuesta(res: Response, mensaje_error: string): void {
  if (res.status === 401) {
    window.location.assign("/auth");
    throw new Error("La sesión expiró. Inicia sesión nuevamente.");
  }
  if (res.status === 403) {
    throw new Error("No tienes permiso para acceder a estas notificaciones.");
  }
  if (res.status === 503) {
    throw new Error("El servicio de notificaciones no está disponible temporalmente.");
  }
  if (!res.ok) {
    throw new Error(mensaje_error);
  }
}

export async function obtener_notificaciones(signal?: AbortSignal): Promise<Notificacion[]> {
  const res = await fetch(`${GATEWAY_URL}/api/notificaciones/eventos`, {
    signal,
    credentials: "include",
  });
  verificar_respuesta(res, "Error al obtener las notificaciones del usuario");
  const respuesta: unknown = await res.json();
  if (!Array.isArray(respuesta)) {
    throw new Error("El servicio devolvió una lista de notificaciones inválida.");
  }
  return respuesta.map(normalizar_notificacion);
}

async function solicitar_actualizacion(
  url: string,
  method: "POST" | "DELETE",
  body?: unknown
): Promise<void> {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  verificar_respuesta(res, "No se pudo actualizar la notificación");
}

export async function marcar_notificacion_leida(
  id_notificacion: string | number
): Promise<void> {
  await solicitar_actualizacion(
    `${GATEWAY_URL}${BASE_PATH}/${encodeURIComponent(String(id_notificacion))}/leida`,
    "POST"
  );
}

export async function marcar_todas_leidas(): Promise<void> {
  await solicitar_actualizacion(
    `${GATEWAY_URL}${BASE_PATH}/marcar-todas-leidas`,
    "POST"
  );
}

export async function eliminar_notificaciones(
  ids_notificacion: Array<string | number>
): Promise<void> {
  await Promise.all(
    ids_notificacion.map((id_notificacion) =>
      solicitar_actualizacion(
        `${GATEWAY_URL}${BASE_PATH}/${encodeURIComponent(String(id_notificacion))}`,
        "DELETE"
      )
    )
  );
}
