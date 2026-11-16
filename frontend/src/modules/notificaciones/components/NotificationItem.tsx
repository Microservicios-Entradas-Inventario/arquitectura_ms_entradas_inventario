import type { Notificacion } from "../api";
import { notificaciones_design } from "./notificacionesDesign";
import { useRef } from "react";
import RecordatorioEvento from "./RecordatorioEvento";

type NotificationItemProps = {
  notificacion: Notificacion;
  modo_seleccion: boolean;
  seleccionada: boolean;
  al_abrir: () => void;
  al_mantener_presionada: () => void;
  al_alternar_seleccion: () => void;
};

function obtener_texto_dato(
  datos: Record<string, unknown>,
  ...claves: string[]
): string | undefined {
  for (const clave of claves) {
    if (typeof datos[clave] === "string") return datos[clave];
  }
  return undefined;
}

export default function NotificationItem({
  notificacion,
  modo_seleccion,
  seleccionada,
  al_abrir,
  al_mantener_presionada,
  al_alternar_seleccion,
}: NotificationItemProps) {
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pulsacion_larga = useRef(false);
  const fecha = new Date(notificacion.fecha_emision);
  const fecha_emision = Number.isNaN(fecha.getTime())
    ? notificacion.fecha_emision
    : new Intl.DateTimeFormat("es", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(fecha);
  const nombre_evento = obtener_texto_dato(
    notificacion.datos,
    "nombre_evento",
    "nombreEvento"
  );
  const fecha_evento = obtener_texto_dato(
    notificacion.datos,
    "fecha_cambio",
    "fecha_evento",
    "fechaEvento"
  );
  const hora_evento = obtener_texto_dato(
    notificacion.datos,
    "hora_cambio",
    "hora_evento",
    "horaEvento"
  );
  const cantidad_entradas =
    typeof notificacion.datos.cantidad_entradas === "number"
      ? notificacion.datos.cantidad_entradas
      : typeof notificacion.datos.cantidadEntradas === "number"
        ? notificacion.datos.cantidadEntradas
        : undefined;
  const nuevo_estado = obtener_texto_dato(notificacion.datos, "nuevo_estado");
  const tipo_normalizado = notificacion.tipo.toUpperCase();
  const es_cambio_panel =
    ["EVENTO_CAMBIO", "CAMBIO_EVENTO", "CANCELACION_EVENTO", "EVENTO_ACTUALIZADO", "EVENTO_REPROGRAMADO"]
      .includes(tipo_normalizado) ||
    (typeof notificacion.datos.id_evento === "string" && Boolean(nuevo_estado));
  const es_reprogramacion_panel =
    es_cambio_panel && nuevo_estado?.toLowerCase() === "publicado";
  const estado_panel_esperado = es_reprogramacion_panel ? "publicado" : "cancelado";
  const estado_panel_valido = nuevo_estado?.toLowerCase() === estado_panel_esperado;
  const es_cancelacion_panel =
    es_cambio_panel && !es_reprogramacion_panel && estado_panel_valido;
  const usuarios_notificados =
    typeof notificacion.datos.usuarios_notificados === "number"
      ? notificacion.datos.usuarios_notificados
      : undefined;
  const usuarios_faltantes =
    typeof notificacion.datos.usuarios_faltantes === "number"
      ? notificacion.datos.usuarios_faltantes
      : undefined;
  const id_evento = obtener_texto_dato(notificacion.datos, "id_evento");
  const es_resumen_panel =
    es_cambio_panel &&
    (usuarios_notificados !== undefined || usuarios_faltantes !== undefined);
  const es_recordatorio = [
    "RECORDATORIO",
    "RECORDATORIO_24H",
    "RECORDATORIO_30M",
  ].includes(tipo_normalizado);
  const titulo = es_recordatorio
    ? "Recordatorio evento"
    : es_cambio_panel
      ? "Evento cambiado"
      : notificacion.titulo;

  function iniciar_pulsacion_larga() {
    pulsacion_larga.current = false;
    if (temporizador.current) clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => {
      pulsacion_larga.current = true;
      al_mantener_presionada();
    }, 1000);
  }

  function limpiar_pulsacion_larga() {
    if (temporizador.current) {
      clearTimeout(temporizador.current);
      temporizador.current = null;
    }
  }

  return (
    <div className={`notificacion ${notificacion.estado === "no_leida" ? "no-leida" : ""} ${seleccionada ? "seleccionada" : ""}`}>
      {modo_seleccion && (
        <input
          className="selector"
          type="checkbox"
          checked={seleccionada}
          onChange={al_alternar_seleccion}
          aria-label={`Seleccionar ${notificacion.titulo}`}
        />
      )}
      <div
        className="contenido-notificacion"
        role="button"
        tabIndex={0}
        aria-pressed={modo_seleccion ? seleccionada : undefined}
        onPointerDown={iniciar_pulsacion_larga}
        onMouseDown={iniciar_pulsacion_larga}
        onTouchStart={iniciar_pulsacion_larga}
        onPointerUp={limpiar_pulsacion_larga}
        onMouseUp={limpiar_pulsacion_larga}
        onTouchEnd={limpiar_pulsacion_larga}
        onPointerLeave={limpiar_pulsacion_larga}
        onPointerCancel={limpiar_pulsacion_larga}
        onContextMenu={(event) => event.preventDefault()}
        onClick={() => {
          if (pulsacion_larga.current) {
            pulsacion_larga.current = false;
            return;
          }
          if (modo_seleccion) al_alternar_seleccion();
          else al_abrir();
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            if (modo_seleccion) al_alternar_seleccion();
            else al_abrir();
          }
        }}
      >
      <div className="icono">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {notificacion.tipo === "COMPRA" ? (
            <path d="m5 12 4 4L19 6" />
          ) : es_recordatorio ? (
            <>
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3 2" />
            </>
          ) : (
            <>
              <circle cx="12" cy="12" r="9" />
              <path d="M12 11v5M12 8h.01" />
            </>
          )}
        </svg>
      </div>
      <div className="contenido">
        <div className="titulo-fila">
          <h3>{titulo}</h3>
          {notificacion.estado === "no_leida" && (
            <span className="punto-no-leida" aria-label="Sin leer" />
          )}
        </div>
        {es_recordatorio ? (
          <RecordatorioEvento notificacion={notificacion} />
        ) : (
          <>
            {es_cancelacion_panel ? (
              <>
                <p className="detalle">Cancelado</p>
                {nombre_evento && <p className="detalle">{nombre_evento}</p>}
                {cantidad_entradas !== undefined && (
                  <p className="detalle">
                    {cantidad_entradas} {cantidad_entradas === 1 ? "entrada" : "entradas"}
                  </p>
                )}
              </>
            ) : es_resumen_panel ? (
              <>
                {nuevo_estado && (
                  <p className="detalle">Estado: {nuevo_estado}</p>
                )}
                {(nombre_evento || id_evento) && (
                  <p className="detalle">Evento: {nombre_evento ?? id_evento}</p>
                )}
                {(usuarios_notificados !== undefined ||
                  usuarios_faltantes !== undefined) && (
                  <p className="detalle">
                    Usuarios notificados: {usuarios_notificados ?? 0};
                    {" "}usuarios faltantes: {usuarios_faltantes ?? 0}
                  </p>
                )}
              </>
            ) : es_reprogramacion_panel ? (
              <>
                {nombre_evento && <p className="evento">{nombre_evento}</p>}
                {hora_evento && (
                  <p className="detalle">Nueva hora: {hora_evento}</p>
                )}
                {fecha_evento && (
                  <p className="detalle">Nueva fecha: {fecha_evento}</p>
                )}
              </>
            ) : (
              <>
                {nombre_evento && (
                  <p className="evento">{nombre_evento}</p>
                )}
                {fecha_evento && (
                  <p className="detalle">
                    {notificacion.datos.fecha_cambio ? "Nueva fecha" : "Evento"}: {fecha_evento}
                    {hora_evento ? ` · ${hora_evento}` : ""}
                  </p>
                )}
                {es_cambio_panel && estado_panel_valido && nuevo_estado && (
                  <p className="detalle">Estado: {nuevo_estado}</p>
                )}
              </>
            )}
            {cantidad_entradas !== undefined && (
              <p className="detalle">
                {cantidad_entradas} {cantidad_entradas === 1 ? "entrada" : "entradas"}
              </p>
            )}
            {!nombre_evento && !es_cancelacion_panel && !es_reprogramacion_panel && !es_resumen_panel && (
              <p className="detalle">{notificacion.mensaje}</p>
            )}
            <p className="detalle">{fecha_emision}</p>
          </>
        )}
      </div>
      </div>
      <style jsx>{`
        .notificacion {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 16px 20px;
          border-bottom: 1px solid ${notificaciones_design.color_banner};
          background: ${notificaciones_design.color_superficie};
        }

        .notificacion.seleccionada {
          background: ${notificaciones_design.color_banner};
        }

        .selector {
          flex: 0 0 16px;
          width: 16px;
          height: 16px;
          margin: 10px 0 0;
          accent-color: ${notificaciones_design.color_acento};
          cursor: pointer;
        }

        .contenido-notificacion {
          display: flex;
          flex: 1;
          min-width: 0;
          gap: 12px;
          cursor: pointer;
          outline-offset: 3px;
          touch-action: pan-y;
          user-select: none;
        }

        .contenido-notificacion:focus-visible {
          outline: 2px solid ${notificaciones_design.color_acento};
        }

        .notificacion.no-leida {
          background: ${notificaciones_design.color_banner};
        }

        .icono {
          display: flex;
          flex: 0 0 36px;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: ${notificaciones_design.color_exito_fondo};
          color: ${notificaciones_design.color_exito_texto};
        }

        .icono svg {
          width: 20px;
          height: 20px;
        }

        .notificacion.no-leida .icono {
          background: ${notificaciones_design.color_superficie};
          color: ${notificaciones_design.color_texto_primario};
        }

        .contenido {
          flex: 1;
          min-width: 0;
        }

        .notificacion.no-leida .contenido {
          font-weight: 600;
        }

        .titulo-fila {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .titulo-fila h3 {
          margin: 0;
          color: ${notificaciones_design.color_texto_primario};
          font-family: ${notificaciones_design.tipografia_titulos};
          font-size: 14px;
          font-weight: ${notificacion.estado === "no_leida" ? "700" : "600"};
        }

        .punto-no-leida {
          flex: 0 0 7px;
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: ${notificaciones_design.color_acento};
        }

        .evento {
          margin: 5px 0 0;
          color: ${notificaciones_design.color_texto_primario};
          font-size: 14px;
          font-weight: 600;
        }

        .detalle {
          margin: 3px 0 0;
          color: ${notificaciones_design.color_texto_secundario};
          font-size: 12px;
        }
      `}</style>
    </div>
  );
}