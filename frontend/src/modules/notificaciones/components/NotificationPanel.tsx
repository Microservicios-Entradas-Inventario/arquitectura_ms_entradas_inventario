import { useState } from "react";
import NotificationItem from "./NotificationItem";
import { notificaciones_design } from "./notificacionesDesign";
import type { Notificacion } from "../api";

type NotificationPanelProps = {
  atributo_notificaciones: Notificacion[];
  cantidad_no_leidas: number;
  atributo_cargando: boolean;
  atributo_error: boolean;
  atributo_error_accion: string;
  al_marcar_leida: (id_notificacion: string | number) => Promise<void>;
  al_marcar_todas_leidas: () => Promise<void>;
  al_eliminar: (ids_notificacion: Array<string | number>) => Promise<boolean>;
};

export default function NotificationPanel({
  atributo_notificaciones,
  cantidad_no_leidas,
  atributo_cargando,
  atributo_error,
  atributo_error_accion,
  al_marcar_leida,
  al_marcar_todas_leidas,
  al_eliminar,
}: NotificationPanelProps) {
  const [modo_seleccion, establecer_modo_seleccion] = useState(false);
  const [seleccionadas, establecer_seleccionadas] = useState<Array<string | number>>([]);

  function alternar_seleccion(id_notificacion: string | number) {
    establecer_seleccionadas((actuales) =>
      actuales.some((id) => String(id) === String(id_notificacion))
        ? actuales.filter((id) => String(id) !== String(id_notificacion))
        : [...actuales, id_notificacion]
    );
  }

  async function confirmar_eliminacion() {
    if (seleccionadas.length === 0) return;
    const confirmada = window.confirm(
      `¿Eliminar ${seleccionadas.length} ${seleccionadas.length === 1 ? "notificación" : "notificaciones"}?`
    );
    if (!confirmada) return;
    if (await al_eliminar(seleccionadas)) {
      establecer_seleccionadas([]);
      establecer_modo_seleccion(false);
    }
  }

  return (
    <div className="panel-notificaciones" id="centro-notificaciones" role="region" aria-label="Centro de notificaciones">
      <div className="encabezado">
        <div>
          <h2>Notificaciones</h2>
          <p>
            {cantidad_no_leidas}{" "}
            {cantidad_no_leidas === 1
              ? "notificación sin leer"
              : "notificaciones sin leer"}
            <button
              type="button"
              className="marcar-todas"
              onClick={() => void al_marcar_todas_leidas()}
              disabled={cantidad_no_leidas === 0}
              aria-label="Marcar todas las notificaciones como leídas"
            >
              <span aria-hidden="true">{cantidad_no_leidas === 0 ? "✓" : ""}</span>
              Marcar todas como leídas
            </button>
          </p>
        </div>
      </div>
      {modo_seleccion && (
        <div className="barra-seleccion">
          <span>{seleccionadas.length} seleccionadas</span>
          <button type="button" onClick={() => void confirmar_eliminacion()} disabled={seleccionadas.length === 0}>
            Eliminar
          </button>
          <button
            type="button"
            className="cancelar-seleccion"
            onClick={() => {
              establecer_modo_seleccion(false);
              establecer_seleccionadas([]);
            }}
          >
            Cancelar
          </button>
        </div>
      )}
      {atributo_error_accion && <p className="error-accion" role="alert">{atributo_error_accion}</p>}
      <div className="lista-notificaciones" aria-live="polite">
        {atributo_cargando && <p className="estado">Cargando notificaciones...</p>}
        {atributo_error && (
          <p className="estado estado-error">Error al mostrar notificaciones</p>
        )}
        {!atributo_cargando && !atributo_error && atributo_notificaciones.length === 0 && (
          <p className="estado">No tienes notificaciones nuevas.</p>
        )}
        {!atributo_cargando && !atributo_error && atributo_notificaciones.map((notificacion) => (
          <NotificationItem
            key={notificacion.id_notificacion}
            notificacion={notificacion}
            modo_seleccion={modo_seleccion}
            seleccionada={seleccionadas.some((id) => String(id) === String(notificacion.id_notificacion))}
            al_abrir={() => void al_marcar_leida(notificacion.id_notificacion)}
            al_mantener_presionada={() => {
              establecer_modo_seleccion(true);
              establecer_seleccionadas((actuales) =>
                actuales.some((id) => String(id) === String(notificacion.id_notificacion))
                  ? actuales
                  : [...actuales, notificacion.id_notificacion]
              );
            }}
            al_alternar_seleccion={() => alternar_seleccion(notificacion.id_notificacion)}
          />
        ))}
      </div>
      <style jsx>{`
        .panel-notificaciones {
          position: fixed;
          z-index: 1100;
          top: 72px;
          right: 24px;
          width: min(390px, calc(100vw - 32px));
          max-height: 520px;
          overflow: hidden;
          border: 1px solid ${notificaciones_design.color_borde};
          border-radius: ${notificaciones_design.radio_tarjeta};
          background: ${notificaciones_design.color_superficie};
          box-shadow: ${notificaciones_design.sombra_tarjeta};
        }

        .encabezado {
          padding: 20px 20px 16px;
          border-bottom: 1px solid ${notificaciones_design.color_borde};
        }

        .encabezado h2 {
          margin: 0;
          color: ${notificaciones_design.color_texto_primario};
          font-family: ${notificaciones_design.tipografia_titulos};
          font-size: 20px;
          font-weight: 700;
        }

        .encabezado p {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 5px 8px;
          margin: 4px 0 0;
          color: ${notificaciones_design.color_texto_secundario};
          font-size: 12px;
        }

        .marcar-todas {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 0;
          border: 0;
          background: transparent;
          color: ${notificaciones_design.color_acento};
          font: inherit;
          cursor: pointer;
        }

        .marcar-todas:disabled {
          color: ${notificaciones_design.color_texto_secundario};
          cursor: default;
        }

        .marcar-todas span {
          display: inline-flex;
          width: 12px;
          height: 12px;
          align-items: center;
          justify-content: center;
          border: 1px solid currentColor;
          border-radius: 2px;
          font-size: 10px;
          line-height: 1;
        }

        .barra-seleccion {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 16px;
          border-bottom: 1px solid ${notificaciones_design.color_borde};
          color: ${notificaciones_design.color_texto_primario};
          font-size: 12px;
        }

        .barra-seleccion span {
          flex: 1;
        }

        .barra-seleccion button {
          border: 0;
          background: transparent;
          color: ${notificaciones_design.color_peligro_texto};
          font: inherit;
          font-weight: 600;
          cursor: pointer;
        }

        .barra-seleccion button:disabled {
          opacity: 0.5;
          cursor: default;
        }

        .barra-seleccion .cancelar-seleccion {
          color: ${notificaciones_design.color_texto_secundario};
        }

        .error-accion {
          margin: 0;
          padding: 8px 16px;
          color: ${notificaciones_design.color_peligro_texto};
          background: ${notificaciones_design.color_peligro_fondo};
          font-size: 12px;
        }

        .lista-notificaciones {
          max-height: 390px;
          overflow-y: auto;
        }

        .estado {
          margin: 0;
          padding: 32px 20px;
          color: ${notificaciones_design.color_texto_secundario};
          font-size: 14px;
          line-height: 1.5;
          text-align: center;
        }

        .estado-error {
          color: ${notificaciones_design.color_peligro_texto};
          background: ${notificaciones_design.color_peligro_fondo};
        }

        @media (max-width: 640px) {
          .panel-notificaciones {
            position: fixed;
            top: 130px;
            right: 16px;
            left: 16px;
            width: auto;
            max-height: calc(100vh - 150px);
          }

          .lista-notificaciones {
            max-height: calc(100vh - 280px);
          }
        }
      `}</style>
    </div>
  );
}