// ============================================================================
// modules/entradas/components/ConfirmacionTicket.tsx
// ----------------------------------------------------------------------------
// Muestra el Pase de Acceso Oficial desde MongoDB (GET /api/entradas/{id}/detalle)
// y permite verificar en 1 clic su sincronización en el MySQL de Check-in
// (POST /api/checkin/validaciones).
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { GATEWAY_URL } from "@/lib/env";
import { obtenerEntradaEmitida } from "../api";
import { EntradaEmitida } from "../types";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

export default function ConfirmacionTicket() {
  const searchParams = useSearchParams();
  const idEntradaParam = searchParams.get("idEntrada") || "tk-998877";

  const [ticket, setTicket] = useState<EntradaEmitida | null>(null);
  const [cargando, setCargando] = useState(true);
  const [validandoCheckin, setValidandoCheckin] = useState(false);
  const [resultadoCheckin, setResultadoCheckin] = useState<{
    valido: boolean;
    motivo: string;
    ticket?: { id_entrada: string; id_evento: string; nombre_usuario: string };
  } | null>(null);

  useEffect(() => {
    async function cargar() {
      setCargando(true);
      setResultadoCheckin(null);
      try {
        const data = await obtenerEntradaEmitida(idEntradaParam);
        setTicket(data);
      } catch (err) {
        console.error("Error al cargar ticket:", err);
      } finally {
        setCargando(false);
      }
    }
    cargar();
  }, [idEntradaParam]);

  const handleValidarEnCheckin = async () => {
    if (!ticket) return;
    setValidandoCheckin(true);
    try {
      const res = await fetch(`${GATEWAY_URL}/api/checkin/validaciones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id_entrada: ticket.idEntrada,
          id_evento: ticket.idEvento,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResultadoCheckin(data);
      } else {
        setResultadoCheckin({ valido: false, motivo: `HTTP_${res.status}` });
      }
    } catch {
      setResultadoCheckin({ valido: false, motivo: "CHECKIN_UNAVAILABLE" });
    } finally {
      setValidandoCheckin(false);
    }
  };

  if (cargando) {
    return (
      <div className={styles.entradasModuleScope}>
        <div className={styles.container} style={{ textAlign: "center", padding: "64px 0" }}>
          <div style={{ fontSize: "40px", marginBottom: "16px" }}>🎟️</div>
          <h2 className={styles.titleH2}>Consultando ticket en MongoDB (entradas-service)...</h2>
          <p className={styles.textMuted}>Conectando con el servicio de control de acceso e inventario</p>
        </div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className={styles.entradasModuleScope}>
        <div className={styles.container} style={{ textAlign: "center", padding: "64px 0" }}>
          <h2 className={styles.titleH2}>Entrada no encontrada</h2>
          <p className={styles.textMuted}>No se pudo recuperar la información del ticket solicitado.</p>
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
            ✓ Entrada Emitida en Entradas (MongoDB) y Sincronizada con Check-in (MySQL)
          </span>
          <h1 className={styles.titleH1} style={{ marginTop: "12px", marginBottom: "6px" }}>
            Pase de Acceso Oficial
          </h1>
          <p className={styles.textMuted}>
            Presenta este código QR en la puerta del evento al momento del Check-in.
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
            }}
          >
            <div>
              <span style={{ fontSize: "11px", fontWeight: 700, color: THEME.colors.secondary, textTransform: "uppercase", letterSpacing: "1px" }}>
                TicketU · Entradas (Grupo 3) ↔ Check-in (Grupo 5)
              </span>
              <div style={{ fontSize: "16px", fontWeight: 700, color: THEME.colors.primary }}>
                Universidad de Valparaíso
              </div>
            </div>

            <div style={{ textAlign: "right" }}>
              <span style={{ fontSize: "11px", color: THEME.colors.secondary }}>ID Ticket (`id_entrada`):</span>
              <div style={{ fontSize: "15px", fontWeight: 700, fontFamily: THEME.fonts.titles, color: THEME.colors.primary }}>
                {ticket.idEntrada}
              </div>
            </div>
          </div>

          <div style={{ marginBottom: "24px" }}>
            <h2 className={styles.titleH2} style={{ fontSize: "22px", margin: "0 0 10px 0" }}>
              {ticket.nombreEvento} <span style={{ fontSize: "14px", color: THEME.colors.secondary }}>({ticket.idEvento})</span>
            </h2>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", fontSize: "14px", color: THEME.colors.secondary }}>
              <span>📅 {ticket.fechaEvento}</span>
              <span>⏰ {ticket.horaEvento}</span>
              <span>📍 {ticket.lugarEvento}</span>
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
                alt={`Código QR para ticket ${ticket.idEntrada}`}
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
              QR sincronizado con MySQL de Check-in (`qr_data = &quot;{ticket.idEntrada}&quot;`)
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
              <span style={{ color: THEME.colors.secondary }}>Asistente / Titular:</span>
              <div style={{ fontWeight: 600, color: THEME.colors.primary }}>{ticket.nombreComprador}</div>
            </div>
            <div>
              <span style={{ color: THEME.colors.secondary }}>Correo Electrónico:</span>
              <div style={{ fontWeight: 600, color: THEME.colors.primary }}>{ticket.correoComprador}</div>
            </div>
            <div>
              <span style={{ color: THEME.colors.secondary }}>Tipo de Acceso:</span>
              <div style={{ fontWeight: 600, color: THEME.colors.primary }}>{ticket.tipoAcceso}</div>
            </div>
            <div>
              <span style={{ color: THEME.colors.secondary }}>Monto Total Pagado:</span>
              <div style={{ fontWeight: 700, color: THEME.colors.primary, fontSize: "14px" }}>
                {ticket.precioFinal === 0 ? "Gratis ($0)" : `$${ticket.precioFinal.toLocaleString("es-CL")}`}
              </div>
            </div>
          </div>
        </div>

        {/* Panel de Comprobación en Vivo con el Microservicio de Check-in */}
        <div className={`${styles.card} ${styles.noPrint}`} style={{ marginTop: "20px", padding: "20px" }}>
          <h3 className={styles.titleH3} style={{ margin: "0 0 8px 0" }}>
            🔗 Prueba de Integración en Vivo con Microservicio Check-in (Grupo 5)
          </h3>
          <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "14px" }}>
            Comprueba desde aquí mismo que este ticket (<code>{ticket.idEntrada}</code>) fue guardado en la base de datos MySQL de <code>checkin-service</code> a través del API Gateway (<code>POST /api/checkin/validaciones</code>):
          </p>

          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button
              type="button"
              disabled={validandoCheckin}
              onClick={handleValidarEnCheckin}
              className={styles.buttonPrimary}
              style={{ height: "40px", padding: "0 18px" }}
            >
              {validandoCheckin ? "Consultando MySQL de Check-in..." : "✅ Validar Ticket en Check-in (MySQL)"}
            </button>

            <Link
              href={`/checkin?idEntrada=${encodeURIComponent(ticket.idEntrada)}&idEvento=${encodeURIComponent(ticket.idEvento)}`}
              className={styles.buttonSecondary}
              style={{ height: "40px", padding: "0 18px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
            >
              🚪 Abrir Vista Completa de Check-in (`/checkin`) ➔
            </Link>
          </div>

          {resultadoCheckin && (
            <div
              className={`${styles.alert} ${resultadoCheckin.valido ? styles.alertSuccess : styles.alertDanger}`}
              style={{ marginTop: "14px", fontSize: "13px" }}
            >
              <div>
                <strong>
                  Respuesta de <code>checkin-service</code> (MySQL):{" "}
                  {resultadoCheckin.valido ? "ACCESO VÁLIDO (TICKET_FOUND)" : `RECHAZADO (${resultadoCheckin.motivo})`}
                </strong>
                {resultadoCheckin.ticket && (
                  <div style={{ marginTop: "4px" }}>
                    Asistente en MySQL: <strong>{resultadoCheckin.ticket.nombre_usuario}</strong> · Evento:{" "}
                    <code>{resultadoCheckin.ticket.id_evento}</code> · Ticket: <code>{resultadoCheckin.ticket.id_entrada}</code>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className={styles.noPrint} style={{ display: "flex", gap: "12px", justifyContent: "center", marginTop: "24px", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => window.print()}
            className={styles.buttonPrimary}
            style={{ height: "44px", padding: "0 24px" }}
          >
            🖨️ Imprimir / Guardar como PDF
          </button>

          <Link
            href="/entradas"
            className={styles.buttonSecondary}
            style={{ height: "44px", padding: "0 24px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
          >
            ← Volver a Entradas
          </Link>
        </div>
      </div>
    </div>
  );
}
