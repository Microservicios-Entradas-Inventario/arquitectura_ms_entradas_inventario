// ============================================================================
// modules/entradas/components/ModalReservaHold.tsx
// Modal de Reserva Temporal de Cupos con temporizador regresivo y paso a Pagos.
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ReservaTemporal } from "../types";
import { liberarReservaTemporal } from "../api";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

interface ModalReservaHoldProps {
  reserva: ReservaTemporal | null;
  nombreEvento?: string;
  onClose: () => void;
  onExpirada?: () => void;
}

export default function ModalReservaHold({
  reserva,
  nombreEvento = "Evento seleccionado",
  onClose,
  onExpirada,
}: ModalReservaHoldProps) {
  const router = useRouter();
  const [segundosRestantes, setSegundosRestantes] = useState<number>(900);
  const [procesando, setProcesando] = useState(false);
  const [mensajeExpirado, setMensajeExpirado] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);

  useEffect(() => {
    if (reserva) {
      setSegundosRestantes(
        reserva.segundosRestantes ?? (reserva.expiraEnMinutos ? reserva.expiraEnMinutos * 60 : 900)
      );
      setMensajeExpirado(null);
      setErrorAccion(null);
    }
  }, [reserva]);

  useEffect(() => {
    if (!reserva || segundosRestantes <= 0 || mensajeExpirado) return;

    const timer = setInterval(() => {
      setSegundosRestantes((prev) => {
        if (prev <= 1) {
          void liberarReservaTemporal(reserva.idEvento, reserva.cantidadEntradas, reserva.idReserva);
          setMensajeExpirado(
            "El tiempo límite de tu reserva ha expirado y los cupos fueron liberados."
          );
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

  const handleCancelarReserva = async () => {
    setProcesando(true);
    setErrorAccion(null);
    try {
      await liberarReservaTemporal(reserva.idEvento, reserva.cantidadEntradas, reserva.idReserva);
      if (onExpirada) onExpirada();
      onClose();
    } catch {
      setErrorAccion("No fue posible cancelar la reserva en este momento. Intenta nuevamente.");
    } finally {
      setProcesando(false);
    }
  };

  const handleIrAPagar = () => {
    const query = new URLSearchParams({
      idReserva: reserva.idReserva,
      total: String(reserva.total),
      cantidad: String(reserva.cantidadEntradas),
      idEvento: reserva.idEvento,
    });
    router.push(`/pagos?${query.toString()}`);
  };

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "16px",
          }}
        >
          <span className={`${styles.badge} ${styles.badgeInfo}`}>Reserva activa</span>
          <span
            style={{
              fontSize: "18px",
              fontWeight: 700,
              color: segundosRestantes < 180 ? THEME.colors.danger.text : THEME.colors.primary,
              fontFamily: THEME.fonts.titles,
            }}
          >
            Tiempo restante: {formatoTiempo(segundosRestantes)}
          </span>
        </div>

        <h2 className={styles.titleH2} style={{ margin: "0 0 8px 0" }}>
          Tus cupos están reservados
        </h2>
        <p className={styles.textMuted} style={{ fontSize: "14px", marginBottom: "16px" }}>
          Retuvimos {reserva.cantidadEntradas} entrada(s) para ti. Completa el pago antes de que termine el contador para confirmar tu compra y recibir tu código QR.
        </p>

        {mensajeExpirado ? (
          <div className={`${styles.alert} ${styles.alertDanger}`} style={{ marginBottom: "20px" }}>
            <span>{mensajeExpirado}</span>
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
              <span style={{ color: THEME.colors.secondary }}>Código de reserva:</span>
              <strong>{reserva.idReserva}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: THEME.colors.secondary }}>Evento:</span>
              <strong>{nombreEvento}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: THEME.colors.secondary }}>Cantidad:</span>
              <strong>{reserva.cantidadEntradas} entrada(s)</strong>
            </div>
            {reserva.descuento > 0 && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                  color: THEME.colors.success.text,
                }}
              >
                <span>Descuento aplicado:</span>
                <strong>-${reserva.descuento.toLocaleString("es-CL")}</strong>
              </div>
            )}
            {reserva.avisoPromocion && (
              <div
                style={{
                  marginBottom: "10px",
                  padding: "8px 10px",
                  borderRadius: "6px",
                  backgroundColor: "#FEF3C7",
                  color: "#92400E",
                  fontSize: "12px",
                  border: "1px solid #F59E0B",
                }}
              >
                {reserva.avisoPromocion}
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ color: THEME.colors.secondary }}>Total a pagar:</span>
              <strong style={{ fontSize: "16px", color: THEME.colors.primary }}>
                ${reserva.total.toLocaleString("es-CL")}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: THEME.colors.secondary }}>Estado:</span>
              <span className={`${styles.badge} ${styles.badgeMuted}`}>{reserva.estado}</span>
            </div>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {errorAccion && (
            <div className={`${styles.alert} ${styles.alertDanger}`} style={{ fontSize: "13px", marginTop: 0 }}>
              {errorAccion}
            </div>
          )}

          {!mensajeExpirado ? (
            <>
              <button
                type="button"
                disabled={procesando}
                onClick={handleIrAPagar}
                className={styles.buttonPrimary}
                style={{ width: "100%", height: "46px" }}
              >
                Continuar al pago
              </button>

              <button
                type="button"
                disabled={procesando}
                onClick={handleCancelarReserva}
                className={styles.buttonSecondary}
                style={{ width: "100%", height: "42px" }}
              >
                {procesando ? "Cancelando reserva..." : "Cancelar reserva y liberar cupos"}
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
