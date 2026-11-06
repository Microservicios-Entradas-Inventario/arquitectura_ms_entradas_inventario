// ============================================================================
// modules/entradas/components/EntradasPlaceholder.tsx
// ----------------------------------------------------------------------------
// Microservicio de Entradas e Inventario (Grupo 3)
// Vista principal del módulo (/entradas) para demostración y banco de pruebas
// de las tres funcionalidades oficiales (HU-01, HU-03, HU-04 y HU-05).
// ============================================================================

"use client";

import { useState } from "react";
import Link from "next/link";
import DisponibilidadPlaceholder from "./DisponibilidadPlaceholder";
import ModalReservaHold from "./ModalReservaHold";
import { ReservaTemporal } from "../types";
import { crearReservaTemporal } from "../api";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

export default function EntradasPlaceholder() {
  const [reservaActiva, setReservaActiva] = useState<ReservaTemporal | null>(null);
  const [cargandoHold, setCargandoHold] = useState(false);
  const [errorHold, setErrorHold] = useState<string | null>(null);

  // Simular la solicitud de reserva temporal (Hold de 10 min)
  const handleProbarHold = async () => {
    setCargandoHold(true);
    setErrorHold(null);
    try {
      const res = await crearReservaTemporal({
        idEvento: "evt-001",
        idUsuario: "usr-alumno-uv",
        cantidadEntradas: 2,
        subtotal: 50000,
        descuento: 0,
        total: 50000,
      });
      setReservaActiva(res);
    } catch (err: unknown) {
      setErrorHold(err instanceof Error ? err.message : "Error al crear la reserva temporal.");
    } finally {
      setCargandoHold(false);
    }
  };

  return (
    <div className={styles.entradasModuleScope} style={{ minHeight: "80vh", padding: "40px 0" }}>
      <div className={styles.container}>
        {/* Banner Superior de Identificación del Módulo */}
        <div className={styles.bannerContext}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span className={`${styles.badge} ${styles.badgeInfo}`}>Grupo 3</span>
              <span style={{ fontSize: "13px", fontWeight: 600, color: THEME.colors.primary }}>
                Sprint 2 · Evaluación de Arquitectura
              </span>
            </div>
            <h1 className={styles.titleH1} style={{ margin: "4px 0" }}>
              Módulo de Entradas e Inventario
            </h1>
            <p className={styles.textMuted}>
              Microservicio responsable del control de aforo en tiempo real, bloqueo temporal de cupos (Hold) y entrega de tickets definitivos con QR.
            </p>
          </div>
          <div>
            <span className={`${styles.badge} ${styles.badgeSuccess}`}>
              ✓ Contratos de Interfaz Activos
            </span>
          </div>
        </div>

        {/* ==================================================================
            SECCIÓN 1: HU-01 - Disponibilidad de Aforo (Widget para Catálogo)
            ================================================================== */}
        <div style={{ marginBottom: "32px" }}>
          <div style={{ marginBottom: "12px" }}>
            <h2 className={styles.titleH2}>1. Disponibilidad de Aforo (HU-01)</h2>
            <p className={styles.textMuted}>
              Componente ligero que Catálogo (Grupo 2) importa dentro de la vista de detalle de cualquier evento para consultar el stock disponible en tiempo real:
            </p>
          </div>

          {/* Renderizado en vivo del componente oficial que usa Catálogo */}
          <DisponibilidadPlaceholder eventoId="evt-001" />
        </div>

        {/* ==================================================================
            SECCIÓN 2: HU-03 - Reserva Temporal de Cupos (Modal de 10 min)
            ================================================================== */}
        <div style={{ marginBottom: "32px" }}>
          <div style={{ marginBottom: "12px" }}>
            <h2 className={styles.titleH2}>2. Reserva Temporal de Cupos — Hold de 10 Minutos (HU-03)</h2>
            <p className={styles.textMuted}>
              Congela temporalmente los cupos seleccionados en la base de datos (MongoDB) para evitar sobreventas concurrentes mientras el cliente completa el pago en la pasarela (Grupo 4):
            </p>
          </div>

          <div className={styles.card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
              <div style={{ maxWidth: "600px" }}>
                <h3 className={styles.titleH3}>Prueba de Generación de Hold y Temporizador</h3>
                <p className={styles.textMuted} style={{ fontSize: "13px" }}>
                  Al presionar el botón se solicita al backend el bloqueo de 2 cupos para el evento <em>&quot;Congreso Internacional de Tecnología UV&quot;</em> y se abre el modal con el countdown en tiempo real.
                </p>
                {errorHold && (
                  <p style={{ color: THEME.colors.danger.text, fontSize: "13px", marginTop: "8px" }}>
                    ⚠️ {errorHold}
                  </p>
                )}
              </div>
              <div>
                <button
                  type="button"
                  disabled={cargandoHold}
                  onClick={handleProbarHold}
                  className={styles.buttonPrimary}
                  style={{ height: "44px", padding: "0 24px" }}
                >
                  {cargandoHold ? "Generando Hold..." : "⏳ Probar Reserva Temporal (Hold 10 min) ➔"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ==================================================================
            SECCIÓN 3: HU-04 y HU-05 - Detalle de Entrada y Código QR
            ================================================================== */}
        <div>
          <div style={{ marginBottom: "12px" }}>
            <h2 className={styles.titleH2}>3. Emisión de Entradas y Código QR de Acceso (HU-04 / HU-05)</h2>
            <p className={styles.textMuted}>
              Una vez aprobado el pago (o en eventos gratuitos), se consolida la reserva y se emite la entrada oficial con QR de alta definición para el microservicio de Check-in (Grupo 5):
            </p>
          </div>

          <div className={styles.card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
              <div style={{ maxWidth: "600px" }}>
                <h3 className={styles.titleH3}>Visualización de Entrada Oficial y Código QR</h3>
                <p className={styles.textMuted} style={{ fontSize: "13px" }}>
                  Cumple con los criterios de aceptación: precio final inmutable auditado, acceso general sin mapas de asientos numerados, datos del comprador y código QR habilitado para lectura en torniquetes.
                </p>
              </div>
              <div>
                <Link
                  href="/entradas/confirmacion?idEntrada=tk-DEMO-2026"
                  target="_blank"
                  className={styles.buttonSecondary}
                  style={{ height: "44px", padding: "0 20px", textDecoration: "none" }}
                >
                  🎟️ Abrir Ejemplo de Entrada con QR (Nueva Pestaña) ➔
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Modal de Reserva Temporal (HU-03) si hay un hold activo */}
        {reservaActiva && (
          <ModalReservaHold
            reserva={reservaActiva}
            nombreEvento="Congreso Internacional de Tecnología UV"
            onClose={() => setReservaActiva(null)}
            onExpirada={() => {
              setReservaActiva(null);
            }}
          />
        )}
      </div>
    </div>
  );
}
