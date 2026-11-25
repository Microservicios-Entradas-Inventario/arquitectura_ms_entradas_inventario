// ============================================================================
// modules/entradas/components/EntradasPlaceholder.tsx
// Vista principal del módulo de Entradas:
//   - Selección y adquisición de entradas (gratuitas y pagadas con reserva temporal)
//   - Aplicación de códigos promocionales
//   - Historial "Mis Entradas" con acceso directo al pase QR
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import DisponibilidadPlaceholder from "./DisponibilidadPlaceholder";
import ModalReservaHold from "./ModalReservaHold";
import { getSession, type SessionProfile } from "@/modules/auth/api";
import {
  obtenerEventos,
  obtenerEventoPorId,
  crearReservaTemporal,
  emitirEntradaDirecta,
  evaluarPromocion,
  obtenerMisEntradas,
} from "../api";
import {
  EventoEntradas,
  ReservaTemporal,
  EntradaEmitida,
  PromocionAplicada,
} from "../types";
import styles from "../styles/entradas.module.css";
import { THEME } from "../styles/theme";

export default function EntradasPlaceholder() {
  const searchParams = useSearchParams();
  const eventoIdParam = searchParams.get("eventoId");
  const tabParam = searchParams.get("tab");

  const [vistaActiva, setVistaActiva] = useState<"adquirir" | "mis-entradas">(
    tabParam === "mis-entradas" ? "mis-entradas" : "adquirir"
  );

  const [eventos, setEventos] = useState<EventoEntradas[]>([]);
  const [eventoActivo, setEventoActivo] = useState<EventoEntradas | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [cantidad, setCantidad] = useState<number>(1);
  const [procesando, setProcesando] = useState(false);
  const [errorValidacion, setErrorValidacion] = useState<string | null>(null);

  const [codigoDescuento, setCodigoDescuento] = useState("");
  const [promocionActiva, setPromocionActiva] = useState<PromocionAplicada | null>(null);
  const [mensajePromo, setMensajePromo] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);
  const [validandoPromo, setValidandoPromo] = useState(false);

  const [reservaActiva, setReservaActiva] = useState<ReservaTemporal | null>(null);
  const [ultimoTicketEmitido, setUltimoTicketEmitido] = useState<EntradaEmitida | null>(null);
  const [usuarioSesion, setUsuarioSesion] = useState<SessionProfile["usuario"] | null>(null);

  const [misEntradas, setMisEntradas] = useState<EntradaEmitida[]>([]);
  const [cargandoHistorial, setCargandoHistorial] = useState(false);

  useEffect(() => {
    if (tabParam === "mis-entradas") {
      setVistaActiva("mis-entradas");
    }
  }, [tabParam]);

  useEffect(() => {
    async function inicializar() {
      setCargando(true);
      setErrorCarga(null);
      try {
        const [lista, sesion] = await Promise.all([
          obtenerEventos(),
          getSession().catch(() => null),
        ]);
        setEventos(lista);

        if (sesion?.valido && sesion.usuario) {
          setUsuarioSesion(sesion.usuario);
          setCargandoHistorial(true);
          obtenerMisEntradas()
            .then((historial) => setMisEntradas(historial))
            .catch(() => setMisEntradas([]))
            .finally(() => setCargandoHistorial(false));
        }

        const seleccionado = eventoIdParam
          ? lista.find((e) => e.id === eventoIdParam) || lista[0]
          : lista[0];

        if (seleccionado) {
          setEventoActivo(seleccionado);
          setCantidad(seleccionado.stockDisponible > 0 ? 1 : 0);
        }
      } catch (err) {
        setErrorCarga(
          err instanceof Error
            ? err.message
            : "No fue posible cargar los eventos disponibles en este momento."
        );
      } finally {
        setCargando(false);
      }
    }
    inicializar();
  }, [eventoIdParam]);

  const recargarEventoActivo = async (id: string) => {
    const actualizado = await obtenerEventoPorId(id);
    if (actualizado) {
      setEventoActivo(actualizado);
      setEventos((prev) => prev.map((e) => (e.id === id ? actualizado : e)));
    }
  };

  const recargarMisEntradas = async () => {
    if (!usuarioSesion) return;
    setCargandoHistorial(true);
    try {
      const historial = await obtenerMisEntradas();
      setMisEntradas(historial);
    } catch {
      // Mantener estado actual
    } finally {
      setCargandoHistorial(false);
    }
  };

  const handleCambiarEvento = async (nuevoId: string) => {
    const nuevo = await obtenerEventoPorId(nuevoId);
    if (nuevo) {
      setEventoActivo(nuevo);
      setCantidad(nuevo.stockDisponible > 0 ? 1 : 0);
      setErrorValidacion(null);
      setPromocionActiva(null);
      setMensajePromo(null);
      setCodigoDescuento("");
      setReservaActiva(null);
    }
  };

  const handleCambiarCantidad = (delta: number) => {
    if (!eventoActivo) return;

    const nueva = cantidad + delta;
    if (nueva < 1) return;

    if (nueva > eventoActivo.stockDisponible) {
      setErrorValidacion(`Solo quedan ${eventoActivo.stockDisponible} entrada(s) disponibles.`);
      return;
    }

    if (eventoActivo.tipoEntrada === "GRATUITA" && eventoActivo.limiteGratuitoUsuario) {
      if (nueva > eventoActivo.limiteGratuitoUsuario) {
        setErrorValidacion(
          `Puedes solicitar hasta ${eventoActivo.limiteGratuitoUsuario} entrada(s) gratuita(s) por persona.`
        );
        return;
      }
    }

    if (eventoActivo.tipoEntrada === "PAGADA" && nueva > eventoActivo.maxTickets) {
      setErrorValidacion(
        `El máximo permitido por compra es de ${eventoActivo.maxTickets} entradas.`
      );
      return;
    }

    setErrorValidacion(null);
    setCantidad(nueva);
  };

  const handleAplicarPromocion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventoActivo || !codigoDescuento.trim()) return;

    if (eventoActivo.tipoEntrada === "GRATUITA") {
      setMensajePromo({ tipo: "error", texto: "Las entradas gratuitas ya tienen valor $0." });
      return;
    }

    if (!usuarioSesion) {
      setMensajePromo({ tipo: "error", texto: "Inicia sesión para aplicar un código promocional." });
      return;
    }

    setValidandoPromo(true);
    try {
      const resultado = await evaluarPromocion({
        idEvento: eventoActivo.id,
        idUsuario: usuarioSesion.id_usuario,
        cantidadEntradas: cantidad,
        codigoPromocion: codigoDescuento,
      });

      if (resultado.promocion) {
        setPromocionActiva(resultado.promocion);
        setMensajePromo({ tipo: "exito", texto: resultado.promocion.descripcion });
        setErrorValidacion(null);
      } else {
        setPromocionActiva(null);
        setMensajePromo({
          tipo: "error",
          texto: resultado.mensaje || "Código de promoción no válido o expirado.",
        });
      }
    } finally {
      setValidandoPromo(false);
    }
  };

  const esEventoGratuito = eventoActivo?.tipoEntrada === "GRATUITA";
  const estadoEvento = eventoActivo?.estadoGestion || "PUBLICADO";
  const eventoNoDisponible = estadoEvento !== "PUBLICADO";
  const estaAgotado = (eventoActivo?.stockDisponible ?? 0) <= 0;
  const precioUnitario = eventoActivo?.precio ?? 0;

  const subtotal = precioUnitario * cantidad;
  const porcentajeDescuento = promocionActiva ? promocionActiva.porcentajeDescuento : 0;
  const montoDescuento = Math.round(subtotal * (porcentajeDescuento / 100));
  const totalFinal = Math.max(0, subtotal - montoDescuento);

  const handleContinuarAdquisicion = async () => {
    if (!eventoActivo) return;
    if (!usuarioSesion) {
      setErrorValidacion("Debes iniciar sesión para adquirir o reservar entradas.");
      return;
    }
    if (eventoNoDisponible) {
      setErrorValidacion("Este evento no se encuentra disponible para la venta.");
      return;
    }
    if (cantidad <= 0) {
      setErrorValidacion("Debes seleccionar al menos una entrada.");
      return;
    }

    setProcesando(true);
    setErrorValidacion(null);

    try {
      if (esEventoGratuito) {
        const emitida = await emitirEntradaDirecta({
          idEvento: eventoActivo.id,
          cantidadEntradas: cantidad,
        });

        await Promise.all([recargarEventoActivo(eventoActivo.id), recargarMisEntradas()]);
        setUltimoTicketEmitido(emitida);

        if (typeof window !== "undefined") {
          window.open(`/entradas/confirmacion?idEntrada=${encodeURIComponent(emitida.idEntrada)}`, "_blank");
        }
      } else {
        const reserva = await crearReservaTemporal({
          idEvento: eventoActivo.id,
          idUsuario: usuarioSesion.id_usuario,
          nombreUsuario: usuarioSesion.nombre_completo,
          correoUsuario: usuarioSesion.correo_electronico,
          cantidadEntradas: cantidad,
          subtotal,
          descuento: montoDescuento,
          total: totalFinal,
          nombreCodigo: promocionActiva?.codigo,
          idPromocion: promocionActiva?.idPromocion,
          porcentajeDescuento: promocionActiva?.porcentajeDescuento ?? 0,
        });

        await recargarEventoActivo(eventoActivo.id);
        setReservaActiva(reserva);
      }
    } catch (err: unknown) {
      setErrorValidacion(err instanceof Error ? err.message : "No fue posible procesar tu solicitud.");
    } finally {
      setProcesando(false);
    }
  };

  if (cargando) {
    return (
      <div className={styles.entradasModuleScope}>
        <div className={styles.container} style={{ textAlign: "center", padding: "48px 0" }}>
          <h2 className={styles.titleH2}>Cargando entradas disponibles...</h2>
          <p className={styles.textMuted}>Estamos obteniendo la disponibilidad actualizada de los eventos.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.entradasModuleScope} style={{ minHeight: "80vh", padding: "24px 0 48px 0" }}>
      <div className={styles.container}>
        {/* Encabezado y navegación de pestañas */}
        <div className={styles.bannerContext}>
          <div>
            <h1 className={styles.titleH1} style={{ margin: "0 0 4px 0" }}>
              Entradas
            </h1>
            <p className={styles.textMuted}>
              Selecciona tu evento para reservar entradas o revisa los pases QR ya adquiridos.
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => setVistaActiva("adquirir")}
              className={vistaActiva === "adquirir" ? styles.buttonPrimary : styles.buttonSecondary}
            >
              Adquirir entradas
            </button>
            <button
              type="button"
              onClick={() => {
                setVistaActiva("mis-entradas");
                void recargarMisEntradas();
              }}
              className={vistaActiva === "mis-entradas" ? styles.buttonPrimary : styles.buttonSecondary}
            >
              Mis entradas {usuarioSesion && misEntradas.length > 0 ? `(${misEntradas.length})` : ""}
            </button>
            <Link
              href={eventoActivo ? `/catalogo/${encodeURIComponent(eventoActivo.id)}` : "/catalogo"}
              className={styles.buttonSecondary}
            >
              Ver catálogo
            </Link>
          </div>
        </div>

        {/* Aviso claro si no hay sesión iniciada */}
        {!usuarioSesion && (
          <div
            className={`${styles.alert} ${styles.alertInfo}`}
            style={{ marginTop: 0, marginBottom: "20px", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}
          >
            <div>
              <strong>Inicia sesión para continuar:</strong> necesitas una cuenta activa en TicketU para adquirir entradas o consultar tus pases QR.
            </div>
            <Link href="/auth" className={styles.buttonPrimary} style={{ height: "36px", padding: "0 16px" }}>
              Iniciar sesión
            </Link>
          </div>
        )}

        {errorCarga && (
          <div className={`${styles.alert} ${styles.alertDanger}`} style={{ marginTop: 0, marginBottom: "20px" }}>
            <span>{errorCarga}</span>
          </div>
        )}

        {/* ==================== PESTAÑA: MIS ENTRADAS (HU-04 / HU-05) ==================== */}
        {vistaActiva === "mis-entradas" ? (
          <div className={styles.card}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "12px",
                marginBottom: "20px",
              }}
            >
              <div>
                <h2 className={styles.titleH2} style={{ margin: 0 }}>
                  Mis entradas adquiridas
                </h2>
                <p className={styles.textMuted} style={{ fontSize: "13px", marginTop: "4px" }}>
                  Accede al detalle y código QR de cada una de tus entradas confirmadas.
                </p>
              </div>
              {usuarioSesion && (
                <button
                  type="button"
                  onClick={() => void recargarMisEntradas()}
                  className={styles.buttonSecondary}
                  disabled={cargandoHistorial}
                >
                  {cargandoHistorial ? "Actualizando..." : "Actualizar lista"}
                </button>
              )}
            </div>

            {!usuarioSesion ? (
              <div style={{ textAlign: "center", padding: "32px 16px" }}>
                <p className={styles.textMuted} style={{ marginBottom: "16px" }}>
                  Debes iniciar sesión para consultar tu historial de entradas.
                </p>
                <Link href="/auth" className={styles.buttonPrimary}>
                  Ir a iniciar sesión
                </Link>
              </div>
            ) : cargandoHistorial ? (
              <p className={styles.textMuted}>Cargando tus entradas...</p>
            ) : misEntradas.length === 0 ? (
              <div style={{ textAlign: "center", padding: "32px 16px" }}>
                <p className={styles.textMuted} style={{ marginBottom: "16px" }}>
                  Aún no tienes entradas emitidas en tu cuenta.
                </p>
                <button
                  type="button"
                  onClick={() => setVistaActiva("adquirir")}
                  className={styles.buttonPrimary}
                >
                  Explorar eventos disponibles
                </button>
              </div>
            ) : (
              <div style={{ display: "grid", gap: "16px" }}>
                {misEntradas.map((ent) => (
                  <div
                    key={ent.idEntrada}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: "16px",
                      padding: "16px 20px",
                      borderRadius: THEME.radius.card,
                      border: `1px solid ${THEME.colors.border}`,
                      backgroundColor: THEME.colors.bgPanel,
                    }}
                  >
                    <div style={{ flex: "1 1 260px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                        <span
                          className={`${styles.badge} ${
                            ent.estadoEntrada === "ANULADA" ? styles.badgeDanger : styles.badgeSuccess
                          }`}
                        >
                          {ent.estadoEntrada === "ANULADA" ? "Anulada" : "Emitida"}
                        </span>
                        <span style={{ fontSize: "12px", color: THEME.colors.secondary }}>
                          Código: <strong>{ent.idEntrada}</strong>
                        </span>
                      </div>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: THEME.colors.primary }}>
                        {ent.nombreEvento}
                      </div>
                      <div style={{ fontSize: "13px", color: THEME.colors.secondary, marginTop: "4px" }}>
                        Fecha: {ent.fechaEvento} · Hora: {ent.horaEvento} · Lugar: {ent.lugarEvento}
                      </div>
                      <div style={{ fontSize: "13px", color: THEME.colors.secondary, marginTop: "2px" }}>
                        Acceso: {ent.tipoAcceso} · Valor:{" "}
                        <strong>
                          {ent.precioFinal === 0 ? "Gratis ($0)" : `$${ent.precioFinal.toLocaleString("es-CL")}`}
                        </strong>
                      </div>
                    </div>

                    <Link
                      href={`/entradas/confirmacion?idEntrada=${encodeURIComponent(ent.idEntrada)}`}
                      className={styles.buttonPrimary}
                    >
                      Ver pase QR
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : !eventoActivo ? (
          <div className={styles.card} style={{ textAlign: "center", padding: "40px 20px" }}>
            <h2 className={styles.titleH2}>No hay eventos publicados disponibles</h2>
            <p className={styles.textMuted} style={{ maxWidth: "520px", margin: "0 auto 20px auto" }}>
              En este momento no existen eventos publicados desde el Panel Organizador. Cuando se publique un evento aparecerá automáticamente aquí.
            </p>
            <Link href="/catalogo" className={styles.buttonPrimary}>
              Ir al catálogo
            </Link>
          </div>
        ) : (
          /* ==================== PESTAÑA: ADQUIRIR ENTRADAS ==================== */
          <>
            {/* Selector de evento */}
            {eventos.length > 0 && (
              <div
                className={styles.card}
                style={{
                  marginBottom: "20px",
                  padding: "16px 20px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", flex: "1 1 320px" }}>
                  <label htmlFor="select-evento" style={{ fontSize: "14px", fontWeight: 600, color: THEME.colors.primary }}>
                    Evento seleccionado:
                  </label>
                  <select
                    id="select-evento"
                    value={eventoActivo?.id || ""}
                    onChange={(e) => void handleCambiarEvento(e.target.value)}
                    style={{
                      height: "40px",
                      padding: "0 12px",
                      borderRadius: THEME.radius.input,
                      border: `1px solid ${THEME.colors.border}`,
                      backgroundColor: "#FFFFFF",
                      color: THEME.colors.primary,
                      fontFamily: THEME.fonts.body,
                      fontSize: "14px",
                      fontWeight: 600,
                      cursor: "pointer",
                      maxWidth: "100%",
                    }}
                  >
                    {eventos.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.titulo} ({ev.tipoEntrada === "GRATUITA" ? "Gratuita" : `$${ev.precio.toLocaleString("es-CL")}`})
                      </option>
                    ))}
                  </select>
                </div>

                {eventoActivo && (
                  <Link href={`/catalogo/${encodeURIComponent(eventoActivo.id)}`} className={styles.buttonSecondary}>
                    Ver detalle del evento
                  </Link>
                )}
              </div>
            )}

            {/* Confirmación tras emitir entradas gratuitas */}
            {ultimoTicketEmitido && (
              <div
                className={`${styles.alert} ${styles.alertSuccess}`}
                style={{ marginTop: 0, marginBottom: "20px", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}
              >
                <div>
                  <strong>¡Listo! Tus entradas fueron emitidas correctamente.</strong>
                  <div style={{ fontSize: "13px", marginTop: "4px" }}>
                    Ya puedes abrir tu pase QR y revisarlo en cualquier momento desde la pestaña Mis Entradas.
                  </div>
                </div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {(ultimoTicketEmitido.entradasEmitidas && ultimoTicketEmitido.entradasEmitidas.length > 0
                    ? ultimoTicketEmitido.entradasEmitidas
                    : [ultimoTicketEmitido.idEntrada]
                  ).map((idTk, index) => (
                    <Link
                      key={idTk}
                      href={`/entradas/confirmacion?idEntrada=${encodeURIComponent(idTk)}`}
                      target="_blank"
                      className={styles.buttonPrimary}
                      style={{ height: "36px", padding: "0 14px", fontSize: "13px" }}
                    >
                      Ver pase QR {ultimoTicketEmitido.cantidadEntradas > 1 ? `#${index + 1}` : ""}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Resumen de disponibilidad */}
            {eventoActivo && (
              <div style={{ marginBottom: "24px" }}>
                <DisponibilidadPlaceholder
                  key={`${eventoActivo.id}-${eventoActivo.stockDisponible}`}
                  eventoId={eventoActivo.id}
                  mostrarBotonAccion={false}
                />
              </div>
            )}

            {/* Tarjeta de información del evento */}
            {eventoActivo && (
              <div className={styles.card} style={{ marginBottom: "24px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
                  <div style={{ flex: "1 1 300px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                      <span
                        className={`${styles.badge} ${
                          eventoNoDisponible || estaAgotado
                            ? styles.badgeDanger
                            : esEventoGratuito
                            ? styles.badgeSuccess
                            : styles.badgeInfo
                        }`}
                      >
                        {estadoEvento === "CANCELADO"
                          ? "Cancelado"
                          : estadoEvento === "FINALIZADO"
                          ? "Finalizado"
                          : estaAgotado
                          ? "Agotado"
                          : esEventoGratuito
                          ? "Evento gratuito"
                          : "Evento pagado"}
                      </span>
                    </div>

                    <h2 className={styles.titleH2} style={{ margin: "0 0 8px 0" }}>
                      {eventoActivo.titulo}
                    </h2>
                    {eventoActivo.descripcion && (
                      <p className={styles.textMuted} style={{ marginBottom: "12px", fontSize: "14px" }}>
                        {eventoActivo.descripcion}
                      </p>
                    )}

                    <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", fontSize: "14px", color: THEME.colors.secondary }}>
                      <span>Fecha: {eventoActivo.fecha}</span>
                      <span>Hora: {eventoActivo.hora}</span>
                      <span>Lugar: {eventoActivo.lugar}</span>
                    </div>
                  </div>

                  <div
                    style={{
                      backgroundColor: THEME.colors.bgPanel,
                      padding: "16px 20px",
                      borderRadius: THEME.radius.card,
                      border: `1px solid ${THEME.colors.border}`,
                      textAlign: "right",
                      minWidth: "180px",
                    }}
                  >
                    <div style={{ fontSize: "12px", color: THEME.colors.secondary, fontWeight: 600 }}>
                      Entradas disponibles
                    </div>
                    <div
                      style={{
                        fontSize: "24px",
                        fontWeight: 700,
                        fontFamily: THEME.fonts.titles,
                        color: eventoNoDisponible || estaAgotado ? THEME.colors.danger.text : THEME.colors.primary,
                      }}
                    >
                      {eventoActivo.stockDisponible} / {eventoActivo.stockTotal}
                    </div>
                    <span style={{ fontSize: "12px", color: THEME.colors.secondary }}>cupos restantes</span>
                  </div>
                </div>
              </div>
            )}

            {errorValidacion && (
              <div className={`${styles.alert} ${styles.alertDanger}`} style={{ marginTop: 0, marginBottom: "20px" }}>
                <span>{errorValidacion}</span>
              </div>
            )}

            {eventoNoDisponible ? (
              <div className={styles.card} style={{ textAlign: "center", padding: "40px 20px" }}>
                <h2 className={styles.titleH2} style={{ color: THEME.colors.danger.text }}>
                  {estadoEvento === "CANCELADO"
                    ? "Este evento fue cancelado"
                    : estadoEvento === "FINALIZADO"
                    ? "Este evento ya finalizó"
                    : "Este evento aún no está disponible para la venta"}
                </h2>
                <p className={styles.textMuted} style={{ maxWidth: "520px", margin: "0 auto 20px auto" }}>
                  No es posible reservar ni emitir entradas para este evento. Puedes explorar otros eventos activos en el catálogo.
                </p>
                <Link href="/catalogo" className={styles.buttonPrimary}>
                  Explorar otros eventos
                </Link>
              </div>
            ) : estaAgotado ? (
              <div className={styles.card} style={{ textAlign: "center", padding: "40px 20px" }}>
                <h2 className={styles.titleH2} style={{ color: THEME.colors.danger.text }}>
                  Entradas agotadas
                </h2>
                <p className={styles.textMuted} style={{ maxWidth: "520px", margin: "0 auto 20px auto" }}>
                  Actualmente no quedan cupos disponibles para este evento. Si alguna reserva temporal vence sin completarse, el stock volverá a estar disponible aquí.
                </p>
                <Link href="/catalogo" className={styles.buttonPrimary}>
                  Explorar otros eventos
                </Link>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "24px" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                  <div className={styles.card}>
                    <h3 className={styles.titleH3}>1. Selección de entradas</h3>
                    <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "20px" }}>
                      {esEventoGratuito
                        ? "Evento de acceso gratuito: recibirás tu pase con código QR al confirmar."
                        : "Selecciona cuántas entradas deseas reservar para continuar al pago."}
                    </p>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "16px",
                        backgroundColor: THEME.colors.bgPanel,
                        borderRadius: THEME.radius.card,
                        border: `1px solid ${THEME.colors.border}`,
                        marginBottom: "16px",
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, color: THEME.colors.primary, fontSize: "16px" }}>
                          {esEventoGratuito ? "Entrada general gratuita" : "Entrada general"}
                        </div>
                        <div style={{ fontSize: "13px", color: THEME.colors.secondary, marginTop: "2px" }}>
                          {esEventoGratuito
                            ? `Máximo ${eventoActivo?.limiteGratuitoUsuario || 2} entrada(s) por persona`
                            : `Máximo ${eventoActivo?.maxTickets} entradas por compra`}
                        </div>
                      </div>

                      <div style={{ textAlign: "right" }}>
                        <div
                          style={{
                            fontSize: "20px",
                            fontWeight: 700,
                            fontFamily: THEME.fonts.titles,
                            color: THEME.colors.primary,
                          }}
                        >
                          {esEventoGratuito ? "Gratis" : `$${precioUnitario.toLocaleString("es-CL")}`}
                        </div>
                        <span style={{ fontSize: "12px", color: THEME.colors.secondary }}>c/u</span>
                      </div>
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "16px" }}>
                      <span style={{ fontWeight: 600, color: THEME.colors.primary }}>Cantidad de entradas:</span>

                      <div className={styles.stepperContainer}>
                        <button
                          type="button"
                          className={styles.stepperBtn}
                          disabled={cantidad <= 1 || procesando}
                          onClick={() => handleCambiarCantidad(-1)}
                          aria-label="Restar una entrada"
                        >
                          -
                        </button>
                        <span className={styles.stepperValue}>{cantidad}</span>
                        <button
                          type="button"
                          className={styles.stepperBtn}
                          disabled={
                            cantidad >= (eventoActivo?.stockDisponible ?? 0) ||
                            (esEventoGratuito && cantidad >= (eventoActivo?.limiteGratuitoUsuario ?? 2)) ||
                            (!esEventoGratuito && cantidad >= (eventoActivo?.maxTickets ?? 6)) ||
                            procesando
                          }
                          onClick={() => handleCambiarCantidad(1)}
                          aria-label="Sumar una entrada"
                        >
                          +
                        </button>
                      </div>
                    </div>
                  </div>

                  {!esEventoGratuito && (
                    <div className={styles.card}>
                      <h3 className={styles.titleH3}>¿Tienes un código de descuento?</h3>
                      <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "16px" }}>
                        Ingresa un código promocional vigente para este evento.
                      </p>

                      <form onSubmit={handleAplicarPromocion} style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                        <input
                          type="text"
                          placeholder="Código promocional"
                          value={codigoDescuento}
                          onChange={(e) => setCodigoDescuento(e.target.value.toUpperCase())}
                          style={{
                            height: "40px",
                            padding: "0 12px",
                            borderRadius: THEME.radius.input,
                            border: `1px solid ${THEME.colors.border}`,
                            fontFamily: THEME.fonts.body,
                            fontSize: "14px",
                            flex: "1 1 180px",
                            textTransform: "uppercase",
                          }}
                        />
                        <button
                          type="submit"
                          disabled={validandoPromo || !codigoDescuento.trim()}
                          className={styles.buttonSecondary}
                          style={{ height: "40px" }}
                        >
                          {validandoPromo ? "Validando..." : "Aplicar descuento"}
                        </button>
                      </form>

                      {mensajePromo && (
                        <div
                          className={`${styles.alert} ${
                            mensajePromo.tipo === "exito" ? styles.alertSuccess : styles.alertDanger
                          }`}
                          style={{ marginTop: "12px", padding: "10px 14px", fontSize: "13px" }}
                        >
                          <span>{mensajePromo.texto}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div>
                  <div className={styles.card} style={{ position: "sticky", top: "24px" }}>
                    <h3 className={styles.titleH3}>2. Resumen de solicitud</h3>
                    <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "16px" }}>
                      Revisa el detalle antes de continuar.
                    </p>

                    <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "16px" }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "14px",
                          paddingBottom: "8px",
                          borderBottom: `1px solid ${THEME.colors.border}`,
                        }}
                      >
                        <span>Evento:</span>
                        <strong>{eventoActivo?.titulo}</strong>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "14px",
                          paddingBottom: "8px",
                          borderBottom: `1px solid ${THEME.colors.border}`,
                        }}
                      >
                        <span>Cantidad:</span>
                        <strong>{cantidad} entrada(s)</strong>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "14px",
                          paddingBottom: "8px",
                          borderBottom: `1px solid ${THEME.colors.border}`,
                        }}
                      >
                        <span>Subtotal:</span>
                        <strong>{esEventoGratuito ? "Gratis ($0)" : `$${subtotal.toLocaleString("es-CL")}`}</strong>
                      </div>

                      {promocionActiva && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: "14px",
                            color: THEME.colors.success.text,
                            paddingBottom: "8px",
                            borderBottom: `1px solid ${THEME.colors.border}`,
                          }}
                        >
                          <span>Descuento ({promocionActiva.porcentajeDescuento}%):</span>
                          <strong>-${montoDescuento.toLocaleString("es-CL")}</strong>
                        </div>
                      )}
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: "18px",
                        fontWeight: 700,
                        color: THEME.colors.primary,
                        fontFamily: THEME.fonts.titles,
                        marginBottom: "16px",
                      }}
                    >
                      <span>Total final:</span>
                      <span style={{ fontSize: "22px" }}>
                        {totalFinal === 0 ? "$0 (Gratis)" : `$${totalFinal.toLocaleString("es-CL")}`}
                      </span>
                    </div>

                    <div
                      className={`${styles.alert} ${esEventoGratuito ? styles.alertSuccess : styles.alertInfo}`}
                      style={{ marginTop: 0, marginBottom: "20px", fontSize: "13px" }}
                    >
                      <div>
                        {esEventoGratuito ? (
                          <span>Emisión inmediata: al confirmar obtendrás tu pase de acceso con código QR.</span>
                        ) : (
                          <span>
                            Tus entradas quedarán reservadas temporalmente por 15 minutos mientras completas el pago.
                          </span>
                        )}
                      </div>
                    </div>

                    <button
                      type="button"
                      disabled={procesando || cantidad === 0 || !usuarioSesion}
                      onClick={() => void handleContinuarAdquisicion()}
                      className={styles.buttonPrimary}
                      style={{ width: "100%", height: "48px", fontSize: "15px" }}
                    >
                      {procesando
                        ? "Procesando..."
                        : !usuarioSesion
                        ? "Inicia sesión para continuar"
                        : esEventoGratuito
                        ? "Obtener entrada gratuita"
                        : `Reservar y continuar al pago ($${totalFinal.toLocaleString("es-CL")})`}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {reservaActiva && (
              <ModalReservaHold
                reserva={reservaActiva}
                nombreEvento={eventoActivo?.titulo}
                onClose={() => setReservaActiva(null)}
                onExpirada={async () => {
                  if (eventoActivo) await recargarEventoActivo(eventoActivo.id);
                  setReservaActiva(null);
                }}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
