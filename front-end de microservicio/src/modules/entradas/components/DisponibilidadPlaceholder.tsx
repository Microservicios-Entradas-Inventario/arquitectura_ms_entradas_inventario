// ============================================================================
// modules/entradas/components/DisponibilidadPlaceholder.tsx
// ----------------------------------------------------------------------------
// Grupo 3 — Entradas / Inventario.
//
// Componente RESUMEN chico (solo lectura) que Catálogo (Grupo 2)
// incrusta en el detalle de un evento (DetalleEventoPlaceholder.tsx).
// Muestra aforo en tiempo real, tipo de entrada y botón de acción.
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { obtenerDisponibilidad } from "../api";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

interface DisponibilidadData {
  idEvento: string;
  stockDisponible: number;
  stockTotal: number;
  tipoEntrada: "PAGADA" | "GRATUITA";
  precio: number;
}

export default function DisponibilidadPlaceholder({ eventoId }: { eventoId: string }) {
  const [data, setData] = useState<DisponibilidadData | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let activo = true;
    async function cargar() {
      setCargando(true);
      try {
        const res = await obtenerDisponibilidad(eventoId);
        if (activo) setData(res);
      } catch (err) {
        console.error("Error al obtener disponibilidad:", err);
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
        className={styles.card}
        style={{
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          backgroundColor: THEME.colors.bgPanel,
        }}
      >
        <span style={{ fontSize: "18px" }}>🎟️</span>
        <span style={{ fontSize: "14px", color: THEME.colors.secondary }}>
          Consultando aforo disponible...
        </span>
      </div>
    );
  }

  const stockDisponible = data?.stockDisponible ?? 0;
  const stockTotal = data?.stockTotal ?? 1;
  const esGratuito = data?.tipoEntrada === "GRATUITA";
  const estaAgotado = stockDisponible <= 0;

  // Porcentaje de stock restante para indicador visual
  const porcentaje = Math.max(0, Math.min(100, Math.round((stockDisponible / stockTotal) * 100)));

  return (
    <div
      className={styles.card}
      style={{
        padding: "20px 24px",
        borderLeft: `4px solid ${estaAgotado
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
        {/* Información de Aforo y Tipo */}
        <div style={{ flex: "1 1 240px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <span
              className={`${styles.badge} ${estaAgotado
                  ? styles.badgeDanger
                  : esGratuito
                    ? styles.badgeSuccess
                    : styles.badgeInfo
                }`}
            >
              {estaAgotado ? "Agotado" : esGratuito ? "Entrada Gratuita" : "Entrada Pagada"}
            </span>

            <span style={{ fontSize: "12px", color: THEME.colors.secondary, fontWeight: 500 }}>
              Inventario oficial · Grupo 3
            </span>
          </div>

          <div
            style={{
              fontSize: "18px",
              fontWeight: 700,
              fontFamily: THEME.fonts.titles,
              color: estaAgotado ? THEME.colors.danger.text : THEME.colors.primary,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <span>{estaAgotado ? "🚫 Sin cupos disponibles" : `🎟️ ${stockDisponible} entradas disponibles`}</span>
            {!estaAgotado && (
              <span style={{ fontSize: "13px", fontWeight: 400, color: THEME.colors.secondary }}>
                (de {stockTotal} aforo total)
              </span>
            )}
          </div>

          {/* Barra sutil de aforo restante */}
          {!estaAgotado && (
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
            {estaAgotado ? (
              <span>Puedes registrar tu correo para recibir alerta si se libera stock.</span>
            ) : esGratuito ? (
              <span style={{ color: THEME.colors.success.text, fontWeight: 600 }}>
                Acceso 100% gratuito (emisión directa con QR)
              </span>
            ) : (
              <span>
                Precio de entrada:{" "}
                <strong style={{ color: THEME.colors.primary, fontSize: "15px" }}>
                  ${data?.precio ? data.precio.toLocaleString("es-CL") : "0"}
                </strong>
              </span>
            )}
          </div>
        </div>

        {/* Botón de Llamado a la Acción hacia el Módulo de Entradas */}
        <div>
          <Link
            href={`/entradas?eventoId=${eventoId}`}
            className={styles.buttonPrimary}
            style={{
              height: "42px",
              padding: "0 22px",
              textDecoration: "none",
              backgroundColor: estaAgotado ? THEME.colors.secondary : THEME.colors.primary,
            }}
          >
            {estaAgotado ? "Ver Evento / Avisarme ➔" : "Adquirir Entradas ➔"}
          </Link>
        </div>
      </div>
    </div>
  );
}
