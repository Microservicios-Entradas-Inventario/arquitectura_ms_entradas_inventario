// ============================================================================
// modules/entradas/components/DisponibilidadPlaceholder.tsx
// Bloque resumen de disponibilidad y precio incrustado en el detalle de Catálogo.
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { obtenerDisponibilidad } from "../api";
import { EstadoGestionEvento } from "../types";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

interface DisponibilidadData {
  idEvento: string;
  stockDisponible: number;
  stockTotal: number;
  tipoEntrada: "PAGADA" | "GRATUITA";
  precio: number;
  estadoGestion?: EstadoGestionEvento;
}

export default function DisponibilidadPlaceholder({
  eventoId,
  mostrarBotonAccion = true,
}: {
  eventoId: string;
  mostrarBotonAccion?: boolean;
}) {
  const [data, setData] = useState<DisponibilidadData | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(false);

  useEffect(() => {
    let activo = true;
    async function cargar() {
      setCargando(true);
      setErrorCarga(false);
      try {
        const res = await obtenerDisponibilidad(eventoId);
        if (activo) setData(res);
      } catch {
        if (activo) {
          setData(null);
          setErrorCarga(true);
        }
      } finally {
        if (activo) setCargando(false);
      }
    }
    cargar();
    return () => {
      activo = false;
    };
  }, [eventoId]);

  if (cargando) {
    return (
      <div
        className={`${styles.entradasModuleScope} ${styles.card}`}
        style={{
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          backgroundColor: THEME.colors.bgPanel,
        }}
      >
        <span style={{ fontSize: "14px", color: THEME.colors.secondary }}>
          Consultando disponibilidad de entradas...
        </span>
      </div>
    );
  }

  if (errorCarga || !data) {
    return (
      <div
        className={`${styles.entradasModuleScope} ${styles.card}`}
        style={{
          padding: "18px 22px",
          backgroundColor: THEME.colors.bgPanel,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <div style={{ fontWeight: 600, color: THEME.colors.primary, fontSize: "15px" }}>
            Disponibilidad en sincronización
          </div>
          <div style={{ fontSize: "13px", color: THEME.colors.secondary, marginTop: "2px" }}>
            No pudimos obtener el aforo en este instante. Puedes revisar el evento directamente en Entradas.
          </div>
        </div>
        {mostrarBotonAccion && (
          <Link
            href={`/entradas?eventoId=${encodeURIComponent(eventoId)}`}
            className={styles.buttonPrimary}
            style={{ height: "40px", padding: "0 18px", textDecoration: "none" }}
          >
            Ver entradas
          </Link>
        )}
      </div>
    );
  }

  const stockDisponible = data.stockDisponible;
  const stockTotal = Math.max(1, data.stockTotal);
  const esGratuito = data.tipoEntrada === "GRATUITA";
  const estado = data.estadoGestion || "PUBLICADO";
  const noDisponiblePorEstado = estado !== "PUBLICADO";
  const estaAgotado = stockDisponible <= 0;
  const porcentaje = Math.max(0, Math.min(100, Math.round((stockDisponible / stockTotal) * 100)));

  return (
    <div
      className={`${styles.entradasModuleScope} ${styles.card}`}
      style={{
        padding: "20px 24px",
        borderLeft: `4px solid ${
          noDisponiblePorEstado || estaAgotado
            ? THEME.colors.danger.text
            : esGratuito
            ? THEME.colors.success.text
            : THEME.colors.primary
        }`,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ flex: "1 1 240px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <span
              className={`${styles.badge} ${
                noDisponiblePorEstado || estaAgotado
                  ? styles.badgeDanger
                  : esGratuito
                  ? styles.badgeSuccess
                  : styles.badgeInfo
              }`}
            >
              {estado === "CANCELADO"
                ? "Evento cancelado"
                : estado === "FINALIZADO"
                ? "Evento finalizado"
                : estaAgotado
                ? "Agotado"
                : esGratuito
                ? "Entrada gratuita"
                : "Entrada pagada"}
            </span>
          </div>

          <div
            style={{
              fontSize: "18px",
              fontWeight: 700,
              fontFamily: THEME.fonts.titles,
              color: noDisponiblePorEstado || estaAgotado ? THEME.colors.danger.text : THEME.colors.primary,
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexWrap: "wrap",
            }}
          >
            <span>
              {estado === "CANCELADO"
                ? "Venta suspendida por cancelación"
                : estado === "FINALIZADO"
                ? "Este evento ya finalizó"
                : estaAgotado
                ? "Sin cupos disponibles"
                : `${stockDisponible} entradas disponibles`}
            </span>
            {!noDisponiblePorEstado && !estaAgotado && (
              <span style={{ fontSize: "13px", fontWeight: 400, color: THEME.colors.secondary }}>
                (de {data.stockTotal} cupos totales)
              </span>
            )}
          </div>

          {!noDisponiblePorEstado && !estaAgotado && (
            <div
              style={{
                width: "100%",
                maxWidth: "260px",
                height: "6px",
                backgroundColor: THEME.colors.border,
                borderRadius: "3px",
                marginTop: "8px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${porcentaje}%`,
                  height: "100%",
                  backgroundColor: porcentaje < 20 ? THEME.colors.danger.text : THEME.colors.primary,
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          )}

          <div style={{ marginTop: "6px", fontSize: "13px", color: THEME.colors.secondary }}>
            {noDisponiblePorEstado ? (
              <span>No es posible adquirir entradas para este evento.</span>
            ) : estaAgotado ? (
              <span>Todas las entradas de este evento fueron adquiridas o reservadas.</span>
            ) : esGratuito ? (
              <span style={{ color: THEME.colors.success.text, fontWeight: 600 }}>
                Acceso gratuito con emisión inmediata de código QR
              </span>
            ) : (
              <span>
                Valor por entrada:{" "}
                <strong style={{ color: THEME.colors.primary, fontSize: "15px" }}>
                  ${data.precio.toLocaleString("es-CL")}
                </strong>
              </span>
            )}
          </div>
        </div>

        {mostrarBotonAccion && !noDisponiblePorEstado && !estaAgotado && (
          <div>
            <Link
              href={`/entradas?eventoId=${encodeURIComponent(eventoId)}`}
              className={styles.buttonPrimary}
              style={{
                height: "42px",
                padding: "0 22px",
                textDecoration: "none",
              }}
            >
              {esGratuito ? "Obtener entradas" : "Adquirir entradas"}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
