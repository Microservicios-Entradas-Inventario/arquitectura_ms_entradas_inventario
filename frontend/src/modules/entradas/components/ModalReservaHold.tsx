// ============================================================================
// modules/entradas/components/ModalReservaHold.tsx
// ----------------------------------------------------------------------------
// Microservicio de Entradas e Inventario (Grupo 3) - HU-03
// Modal de Reserva Temporal de Cupos (Hold) con temporizador regresivo de 10 min.
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
  onPagoCompletado?: (idEntrada: string) => void;
}

export default function ModalReservaHold({
  reserva,
  nombreEvento = "Evento Seleccionado",
  onClose,
  onExpirada,
}: ModalReservaHoldProps) {
  const router = useRouter();
  const [segundosRestantes, setSegundosRestantes] = useState<number>(600);
  const [procesando, setProcesando] = useState(false);
  const [mensajeExpirado, setMensajeExpirado] = useState<string | null>(null);

  // Inicializar tiempo según respuesta del backend o por defecto 10 minutos (600s)
  useEffect(() => {
    if (reserva) {
      setSegundosRestantes(reserva.segundosRestantes ?? (reserva.expiraEnMinutos ? reserva.expiraEnMinutos * 60 : 600));
      setMensajeExpirado(null);
    }
  }, [reserva]);

  // Temporizador regresivo en tiempo real con liberación automática al llegar a 0
  useEffect(() => {
    if (!reserva || segundosRestantes <= 0 || mensajeExpirado) return;

    const timer = setInterval(() => {
      setSegundosRestantes((prev) => {
        if (prev <= 1) {
          // El tiempo expiró: liberar en el backend y notificar
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
      // Simular notificación webhook al backend si está disponible
      try {
        await fetch(`/api/entradas/reservas/${reserva.idReserva}/webhook-pago`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
      } catch {
        // Fallback local
      }

      const ticketId = `tk-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
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
        {/* Cabecera del Modal con Temporizador */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <span className={`${styles.badge} ${styles.badgeInfo}`}>Hold Activo · HU-03</span>
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
          Hemos congelado temporalmente {reserva.cantidadEntradas} entrada(s) en el inventario para que puedas completar el pago sin riesgo de que se agoten.
        </p>

        {mensajeExpirado ? (
          <div className={`${styles.alert} ${styles.alertDanger}`} style={{ marginBottom: "20px" }}>
            <span>⚠️ {mensajeExpirado}</span>
          </div>
        ) : (
          /* Ficha de Detalles de la Reserva */
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
              <strong>{nombreEvento}</strong>
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
              <span style={{ color: THEME.colors.secondary }}>Estado:</span>
              <span className={`${styles.badge} ${styles.badgeMuted}`}>Reservado Temporalmente</span>
            </div>
          </div>
        )}

        {/* Acciones del Modal */}
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {!mensajeExpirado ? (
            <>
              {/* Botón hacia Pagos (Grupo 4) */}
              <button
                type="button"
                onClick={handleIrAPagos}
                className={styles.buttonPrimary}
                style={{ width: "100%", height: "44px" }}
              >
                💳 Continuar a Pasarela de Pagos (Grupo 4) ➔
              </button>

              {/* Botón de Simulación para Demo de Sprint 2 */}
              <button
                type="button"
                disabled={procesando}
                onClick={handleSimularPagoDemo}
                className={styles.buttonSecondary}
                style={{ width: "100%", height: "40px" }}
              >
                {procesando ? "Emitiendo ticket..." : "🎟️ Simular Pago Aprobado y Abrir Entrada con QR"}
              </button>

              {/* Botón de Cancelación y Liberación */}
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
                Liberar cupo y cancelar reserva
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

