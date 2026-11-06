"use client";

import { useEffect, useState } from "react";
import {
  eliminar_notificaciones,
  marcar_notificacion_leida,
  marcar_todas_leidas,
  obtener_notificaciones,
  type Notificacion,
} from "../api";
import NotificationPanel from "./NotificationPanel";

export default function NotificacionesPlaceholder() {
  const [abierto] = useState(true);
  const [notificaciones, establecer_notificaciones] = useState<Notificacion[]>([]);
  const [cargando, establecer_cargando] = useState(true);
  const [error, establecer_error] = useState(false);
  const [error_accion, establecer_error_accion] = useState("");

  function publicar_cantidad_no_leidas(lista: Notificacion[]) {
    window.dispatchEvent(
      new CustomEvent("ticketu:notifications-count", {
        detail: lista.filter((notificacion) => notificacion.estado === "no_leida").length,
      })
    );
  }

  useEffect(() => {
    const controlador = new AbortController();

    obtener_notificaciones(controlador.signal)
      .then((resultado) => {
        const visibles = resultado.filter((notificacion) => notificacion.estado !== "eliminada");
        establecer_notificaciones(visibles);
        establecer_error(false);
        publicar_cantidad_no_leidas(visibles);
      })
      .catch((error_carga: Error) => {
        if (error_carga.name !== "AbortError") {
          establecer_error(true);
        }
      })
      .finally(() => {
        if (!controlador.signal.aborted) establecer_cargando(false);
      });

    return () => {
      controlador.abort();
    };
  }, []);

  const cantidad_no_leidas = notificaciones.filter(
    (notificacion) => notificacion.estado === "no_leida"
  ).length;

  async function al_marcar_leida(id_notificacion: string | number) {
    try {
      await marcar_notificacion_leida(id_notificacion);
      const actualizadas = notificaciones.map((notificacion) =>
        notificacion.id_notificacion === id_notificacion
          ? { ...notificacion, estado: "leida" as const }
          : notificacion
      );
      establecer_notificaciones(actualizadas);
      publicar_cantidad_no_leidas(actualizadas);
      establecer_error_accion("");
    } catch {
      establecer_error_accion("No se pudo marcar la notificación como leída.");
    }
  }

  async function al_marcar_todas_leidas() {
    try {
      await marcar_todas_leidas();
      const actualizadas = notificaciones.map((notificacion) => ({
        ...notificacion,
        estado: "leida" as const,
      }));
      establecer_notificaciones(actualizadas);
      publicar_cantidad_no_leidas(actualizadas);
      establecer_error_accion("");
    } catch {
      establecer_error_accion("No se pudieron marcar todas como leídas.");
    }
  }

  async function al_eliminar(ids_notificacion: Array<string | number>) {
    try {
      await eliminar_notificaciones(ids_notificacion);
      const ids_eliminados = new Set(ids_notificacion.map(String));
      const visibles = notificaciones.filter(
        (notificacion) => !ids_eliminados.has(String(notificacion.id_notificacion))
      );
      establecer_notificaciones(visibles);
      publicar_cantidad_no_leidas(visibles);
      establecer_error_accion("");
      return true;
    } catch {
      establecer_error_accion("No se pudieron eliminar las notificaciones seleccionadas.");
      return false;
    }
  }

  return (
    abierto ? (
      <NotificationPanel
        atributo_notificaciones={notificaciones}
        cantidad_no_leidas={cantidad_no_leidas}
        atributo_cargando={cargando}
        atributo_error={error}
        atributo_error_accion={error_accion}
        al_marcar_leida={al_marcar_leida}
        al_marcar_todas_leidas={al_marcar_todas_leidas}
        al_eliminar={al_eliminar}
      />
    ) : null
  );
}