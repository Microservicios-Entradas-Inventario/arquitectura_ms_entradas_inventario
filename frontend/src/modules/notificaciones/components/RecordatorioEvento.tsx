import type { Notificacion } from "../api";
import { notificaciones_design } from "./notificacionesDesign";

type RecordatorioEventoProps = {
  notificacion: Notificacion;
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

export default function RecordatorioEvento({ notificacion }: RecordatorioEventoProps) {
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
    "fecha_evento",
    "fechaEvento",
    "fecha_cambio"
  );
  const hora_evento = obtener_texto_dato(
    notificacion.datos,
    "hora_evento",
    "horaEvento",
    "hora_cambio"
  );
  const ubicacion = obtener_texto_dato(
    notificacion.datos,
    "ubicacion_evento",
    "ubicacion"
  );
  const enlace_evento = obtener_texto_dato(
    notificacion.datos,
    "enlace_evento",
    "enlaceEvento"
  );

  return (
    <div className="notificacion-contenido">
      <div className="notificacion-texto">
        {nombre_evento && (
          <p className="notificacion-detalle">{nombre_evento}</p>
        )}
        {fecha_evento && (
          <p className="notificacion-detalle">
            Fecha del evento: {fecha_evento}
          </p>
        )}
        {hora_evento && (
          <p className="notificacion-detalle">Hora: {hora_evento}</p>
        )}
        {ubicacion && (
          <p className="notificacion-detalle">Lugar: {ubicacion}</p>
        )}
        {enlace_evento && (
          <a className="notificacion-enlace" href={enlace_evento}>
            Ver evento
          </a>
        )}
        {!nombre_evento && (
          <p className="notificacion-detalle">{notificacion.mensaje}</p>
        )}
        <p className="notificacion-fecha">{fecha_emision}</p>
      </div>
      <style jsx>{`
        .notificacion-contenido,
        .notificacion-texto {
          min-width: 0;
        }

        .notificacion-contenido {
          font-family: ${notificaciones_design.tipografia_interfaz};
        }

        .notificacion-detalle {
          margin: 4px 0 0;
          color: ${notificaciones_design.color_texto_secundario};
          font-size: 14px;
          line-height: 1.5;
        }

        .notificacion-fecha {
          margin: 8px 0 0;
          color: ${notificaciones_design.color_texto_secundario};
          font-size: 12px;
        }

        .notificacion-enlace {
          display: inline-block;
          min-height: 44px;
          padding: 12px 0;
          color: ${notificaciones_design.color_acento};
          font-size: 14px;
          font-weight: 600;
          text-decoration: underline;
        }

        .notificacion-enlace:focus-visible {
          outline: 2px solid ${notificaciones_design.color_acento};
          outline-offset: 2px;
        }
      `}</style>
    </div>
  );
}