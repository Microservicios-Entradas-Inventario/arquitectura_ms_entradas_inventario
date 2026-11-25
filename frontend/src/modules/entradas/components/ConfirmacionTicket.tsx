// ============================================================================
// modules/entradas/components/ConfirmacionTicket.tsx
// Vista de confirmación y Pase de Acceso Oficial con código QR imprimible.
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { obtenerEntradaEmitida } from "../api";
import { EntradaEmitida } from "../types";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

export default function ConfirmacionTicket() {
  const searchParams = useSearchParams();
  const idEntradaParam = searchParams.get("idEntrada");

  const [ticket, setTicket] = useState<EntradaEmitida | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    async function cargar() {
      if (!idEntradaParam) {
        setTicket(null);
        setCargando(false);
        return;
      }
      setCargando(true);
      try {
        const data = await obtenerEntradaEmitida(idEntradaParam);
        setTicket(data);
      } catch (err) {
        console.error("Error al cargar entrada:", err);
      } finally {
        setCargando(false);
      }
    }
    cargar();
  }, [idEntradaParam]);

  if (cargando) {
    return (
      <div className={styles.entradasModuleScope}>
        <div className={styles.container} style={{ textAlign: "center", padding: "64px 0" }}>
          <h2 className={styles.titleH2}>Cargando tu pase de acceso...</h2>
          <p className={styles.textMuted}>Estamos preparando los datos y el código QR de tu entrada.</p>
        </div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className={styles.entradasModuleScope}>
        <div className={styles.container} style={{ textAlign: "center", padding: "64px 0" }}>
          <h2 className={styles.titleH2}>Entrada no encontrada</h2>
          <p className={styles.textMuted} style={{ marginBottom: "20px" }}>
            No pudimos encontrar el pase solicitado. Verifica el enlace o revisa tu historial en Mis Entradas.
          </p>
          <Link href="/entradas?tab=mis-entradas" className={styles.buttonPrimary}>
            Ir a Mis Entradas
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.entradasModuleScope}>
      <style>{`
        @media print {
          header, footer { display: none !important; }
          body, main { padding: 0 !important; margin: 0 !important; background: #FFFFFF !important; }
        }
      `}</style>
      <div className={styles.container} style={{ maxWidth: "680px", margin: "24px auto" }}>
        <div className={styles.noPrint} style={{ textAlign: "center", marginBottom: "24px" }}>
          <span className={`${styles.badge} ${styles.badgeSuccess}`} style={{ fontSize: "13px", padding: "6px 16px" }}>
            Entrada emitida y habilitada para ingreso
          </span>
          <h1 className={styles.titleH1} style={{ marginTop: "12px", marginBottom: "6px" }}>
            Pase de Acceso Oficial
          </h1>
          <p className={styles.textMuted}>
            Presenta este código QR en el acceso del evento para validar tu ingreso.
          </p>
        </div>

        <div
          className={`${styles.card} ${styles.ticketPrintable}`}
          style={{
            padding: "32px",
            background: "linear-gradient(180deg, #FFFFFF 0%, #F8F9FA 100%)",
            border: `2px dashed ${THEME.colors.border}`,
            boxShadow: THEME.shadows.cardHover,
            position: "relative",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: `1px solid ${THEME.colors.border}`,
              paddingBottom: "16px",
              marginBottom: "20px",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: THEME.colors.secondary,
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                }}
              >
                TicketU · Pase Oficial
              </span>
              <div style={{ fontSize: "16px", fontWeight: 700, color: THEME.colors.primary }}>
                Universidad de Valparaíso
              </div>
            </div>

            <div style={{ textAlign: "right" }}>
              <span style={{ fontSize: "11px", color: THEME.colors.secondary }}>Código de entrada:</span>
              <div
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  fontFamily: THEME.fonts.titles,
                  color: THEME.colors.primary,
                }}
              >
                {ticket.idEntrada}
              </div>
            </div>
          </div>

          <div style={{ marginBottom: "24px" }}>
            <h2 className={styles.titleH2} style={{ fontSize: "22px", margin: "0 0 10px 0" }}>
              {ticket.nombreEvento}
            </h2>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", fontSize: "14px", color: THEME.colors.secondary }}>
              <span>Fecha: {ticket.fechaEvento}</span>
              <span>Hora: {ticket.horaEvento}</span>
              <span>Lugar: {ticket.lugarEvento}</span>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "24px",
              backgroundColor: "#FFFFFF",
              borderRadius: THEME.radius.card,
              border: `1px solid ${THEME.colors.border}`,
              boxShadow: "0 4px 14px rgba(47, 67, 116, 0.06)",
              marginBottom: "24px",
            }}
          >
            <div
              style={{
                padding: "12px",
                border: `2px solid ${THEME.colors.primary}`,
                borderRadius: "12px",
                backgroundColor: "#FFFFFF",
                marginBottom: "12px",
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={ticket.qrData}
                alt={`Código QR para la entrada ${ticket.idEntrada}`}
                width={220}
                height={220}
                style={{ display: "block" }}
              />
            </div>

            <div
              style={{
                fontFamily: THEME.fonts.titles,
                fontSize: "16px",
                fontWeight: 700,
                color: THEME.colors.primary,
                letterSpacing: "1.5px",
              }}
            >
              {ticket.idEntrada}
            </div>
            <span style={{ fontSize: "12px", color: THEME.colors.secondary, marginTop: "4px" }}>
              Código único e intransferible para control de acceso
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "12px",
              backgroundColor: THEME.colors.bgPanel,
              padding: "16px",
              borderRadius: THEME.radius.card,
              border: `1px solid ${THEME.colors.border}`,
              fontSize: "13px",
            }}
          >
            <div>
              <span style={{ color: THEME.colors.secondary }}>Titular:</span>
              <div style={{ fontWeight: 600, color: THEME.colors.primary }}>{ticket.nombreComprador}</div>
            </div>
            <div>
              <span style={{ color: THEME.colors.secondary }}>Correo electrónico:</span>
              <div style={{ fontWeight: 600, color: THEME.colors.primary }}>
                {ticket.correoComprador || "Registrado en tu cuenta"}
              </div>
            </div>
            <div>
              <span style={{ color: THEME.colors.secondary }}>Tipo de acceso:</span>
              <div style={{ fontWeight: 600, color: THEME.colors.primary }}>{ticket.tipoAcceso}</div>
            </div>
            <div>
              <span style={{ color: THEME.colors.secondary }}>Valor pagado:</span>
              <div style={{ fontWeight: 700, color: THEME.colors.primary, fontSize: "14px" }}>
                {ticket.precioFinal === 0 ? "Gratis ($0)" : `$${ticket.precioFinal.toLocaleString("es-CL")}`}
              </div>
            </div>
          </div>
        </div>

        <div
          className={styles.noPrint}
          style={{ display: "flex", gap: "12px", justifyContent: "center", marginTop: "24px", flexWrap: "wrap" }}
        >
          <button
            type="button"
            onClick={() => window.print()}
            className={styles.buttonPrimary}
            style={{ height: "44px", padding: "0 24px" }}
          >
            Imprimir / Guardar PDF
          </button>

          <Link
            href="/entradas?tab=mis-entradas"
            className={styles.buttonSecondary}
            style={{ height: "44px", padding: "0 24px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
          >
            Ver Mis Entradas
          </Link>

          <Link
            href="/catalogo"
            className={styles.buttonSecondary}
            style={{ height: "44px", padding: "0 24px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
          >
            Volver al Catálogo
          </Link>
        </div>
      </div>
    </div>
  );
}
