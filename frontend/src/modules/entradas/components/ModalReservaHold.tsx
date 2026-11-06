// ============================================================================
// modules/entradas/components/ModalReservaHold.tsx
// ----------------------------------------------------------------------------
// Microservicio de Entradas e Inventario (Grupo 3) - HU-03
// Modal de Reserva Temporal de Cupos (Hold) con temporizador regresivo de 10 min.
// Conectado en vivo con entradas-service (MongoDB) y checkin-service (MySQL).
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ReservaTemporal } from "../types";
import { liberarReservaTemporal, consolidarReservaYEmitirTicket } from "../api";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

interface ModalReservaHoldProps {
  reserva: ReservaTemporal | null;
  nombreEvento?: string;
  onClose: () => void;
  onExpirada?: () => void;
  onPagoCompletado?: (idEntrada: string) => void;
}

export default function ModalReservaHold({
  reserva,
  nombreEvento = "Evento Seleccionado",
  onClose,
  onExpirada,
  onPagoCompletado,
}: ModalReservaHoldProps) {
  const router = useRouter();
  const [segundosRestantes, setSegundosRestantes] = useState<number>(600);
  const [procesando, setProcesando] = useState(false);
  const [mensajeExpirado, setMensajeExpirado] = useState<string | null>(null);

  useEffect(() => {
    if (reserva) {
      setSegundosRestantes(reserva.segundosRestantes ?? (reserva.expiraEnMinutos ? reserva.expiraEnMinutos * 60 : 600));
      setMensajeExpirado(null);
    }
  }, [reserva]);

  useEffect(() => {
    if (!reserva || segundosRestantes <= 0 || mensajeExpirado) return;

    const timer = setInterval(() => {
      setSegundosRestantes((prev) => {
        if (prev <= 1) {
          liberarReservaTemporal(reserva.idEvento, reserva.cantidadEntradas, reserva.idReserva);
          setMensajeExpirado("El tiempo límite de 10 minutos ha expirado. Tu cupo ha sido liberado automáticamente.");
          if (onExpirada) onExpirada();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [reserva, segundosRestantes, mensajeExpirado, onExpirada]);

  if (!reserva) return null;

  const formatoTiempo = (totalSegundos: number) => {
    const mins = Math.floor(totalSegundos / 60);
    const segs = totalSegundos % 60;
    return `${mins.toString().padStart(2, "0")}:${segs.toString().padStart(2, "0")}`;
  };

  const handleLiberarYSalir = async () => {
    setProcesando(true);
    try {
      await liberarReservaTemporal(reserva.idEvento, reserva.cantidadEntradas, reserva.idReserva);
      if (onExpirada) onExpirada();
      onClose();
    } finally {
      setProcesando(false);
    }
  };

  const handleIrAPagos = () => {
    router.push(`/pagos?idReserva=${reserva.idReserva}&total=${reserva.total}&cantidad=${reserva.cantidadEntradas}`);
  };

  const handleSimularPagoDemo = async () => {
    setProcesando(true);
    try {
      // Consolidar reserva en entradas-service (MongoDB) y registrar en checkin-service (MySQL)
      const ticketEmitidoBackend = await consolidarReservaYEmitirTicket(reserva.idReserva);
      const ticketId = ticketEmitidoBackend || "tk-DEMO-2026";
      if (onPagoCompletado) {
        onPagoCompletado(ticketId);
      }
      if (typeof window !== "undefined") {
        window.open(`/entradas/confirmacion?idEntrada=${ticketId}`, "_blank");
      }
      onClose();
    } finally {
      setProcesando(false);
    }
  };

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <span className={`${styles.badge} ${styles.badgeInfo}`}>Hold Activo en MongoDB · HU-03</span>
          <span
            style={{
              fontSize: "18px",
              fontWeight: 700,
              color: segundosRestantes < 180 ? THEME.colors.danger.text : THEME.colors.primary,
              fontFamily: THEME.fonts.titles,
            }}
          >
            ⏳ {formatoTiempo(segundosRestantes)}
          </span>
        </div>

        <h2 className={styles.titleH2} style={{ margin: "0 0 8px 0" }}>
          Cupo Reservado Temporalmente
        </h2>
        <p className={styles.textMuted} style={{ fontSize: "14px", marginBottom: "16px" }}>
          Hemos descontado temporalmente {reserva.cantidadEntradas} entrada(s) en MongoDB (<code>ticketu_entradas_db</code>) mientras completas el pago.
        </p>

        {mensajeExpirado ? (
          <div className={`${styles.alert} ${styles.alertDanger}`} style={{ marginBottom: "20px" }}>
            <span>⚠️ {mensajeExpirado}</span>
          </div>
        ) : (
          <div
            style={{
              backgroundColor: THEME.colors.bgPanel,
              border: `1px solid ${THEME.colors.border}`,
              borderRadius: THEME.radius.card,
              padding: "16px",
              fontSize: "13px",
              marginBottom: "20px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: THEME.colors.secondary }}>Identificador de Reserva (holdId):</span>
              <strong>{reserva.idReserva}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: THEME.colors.secondary }}>Evento:</span>
              <strong>{nombreEvento} ({reserva.idEvento})</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: THEME.colors.secondary }}>Cantidad:</span>
              <strong>{reserva.cantidadEntradas} entrada(s)</strong>
            </div>
            {reserva.descuento > 0 && (
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", color: THEME.colors.success.text }}>
                <span>Descuento aplicado:</span>
                <strong>-${reserva.descuento.toLocaleString("es-CL")}</strong>
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: THEME.colors.secondary }}>Monto a Cobrar:</span>
              <strong style={{ fontSize: "16px", color: THEME.colors.primary }}>
                ${reserva.total.toLocaleString("es-CL")}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: THEME.colors.secondary }}>Estado en BD:</span>
              <span className={`${styles.badge} ${styles.badgeMuted}`}>{reserva.estado}</span>
            </div>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {!mensajeExpirado ? (
            <>
              <button
                type="button"
                disabled={procesando}
                onClick={handleSimularPagoDemo}
                className={styles.buttonPrimary}
                style={{ width: "100%", height: "46px" }}
              >
                {procesando
                  ? "Emitiendo en Entradas y registrando en Check-in..."
                  : "🎟️ Confirmar Pago, Emitir QR y Sincronizar con Check-in ➔"}
              </button>

              <button
                type="button"
                onClick={handleIrAPagos}
                className={styles.buttonSecondary}
                style={{ width: "100%", height: "42px" }}
              >
                💳 Ir a Pasarela de Pagos (Grupo 4) ➔
              </button>

              <button
                type="button"
                disabled={procesando}
                onClick={handleLiberarYSalir}
                style={{
                  background: "none",
                  border: "none",
                  color: THEME.colors.secondary,
                  fontSize: "13px",
                  cursor: "pointer",
                  padding: "8px",
                  textDecoration: "underline",
                }}
              >
                Liberar cupo en MongoDB y cancelar reserva
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className={styles.buttonPrimary}
              style={{ width: "100%" }}
            >
              Cerrar y volver
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
