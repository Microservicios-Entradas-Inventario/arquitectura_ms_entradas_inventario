// ============================================================================
// modules/entradas/components/EntradasPlaceholder.tsx
// ----------------------------------------------------------------------------
// Entradas / Inventario — Grupo 3.
// Componente interactivo principal de la ruta /entradas conectado a través del
// API Gateway (http://localhost:8080) con:
//   1. Microservicio Entradas e Inventario (MongoDB)
//   2. Microservicio Check-in (MySQL)
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import DisponibilidadPlaceholder from "./DisponibilidadPlaceholder";
import ModalReservaHold from "./ModalReservaHold";
import {
  obtenerEventos,
  obtenerEventoPorId,
  crearReservaTemporal,
  emitirEntradaDirecta,
  evaluarPromocion,
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const eventoIdParam = searchParams.get("eventoId");

  const [eventos, setEventos] = useState<EventoEntradas[]>([]);
  const [eventoActivo, setEventoActivo] = useState<EventoEntradas | null>(null);
  const [cargando, setCargando] = useState(true);

  const [cantidad, setCantidad] = useState<number>(1);
  const [procesando, setProcesando] = useState(false);
  const [errorValidacion, setErrorValidacion] = useState<string | null>(null);

  const [codigoDescuento, setCodigoDescuento] = useState("");
  const [promocionActiva, setPromocionActiva] = useState<PromocionAplicada | null>(null);
  const [mensajePromo, setMensajePromo] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);

  const [reservaActiva, setReservaActiva] = useState<ReservaTemporal | null>(null);
  const [ultimoTicketEmitido, setUltimoTicketEmitido] = useState<EntradaEmitida | null>(null);
  const [correoNotificacion, setCorreoNotificacion] = useState("");
  const [notificacionEnviada, setNotificacionEnviada] = useState(false);

  useEffect(() => {
    async function inicializar() {
      setCargando(true);
      try {
        const lista = await obtenerEventos();
        setEventos(lista);

        const seleccionado = eventoIdParam
          ? lista.find((e) => e.id === eventoIdParam) || lista[0]
          : lista[0];

        if (seleccionado) {
          setEventoActivo(seleccionado);
          setCantidad(seleccionado.stockDisponible > 0 ? 1 : 0);
        }
      } catch (err) {
        console.error("Error al cargar eventos:", err);
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

  const handleCambiarEvento = async (nuevoId: string) => {
    const nuevo = await obtenerEventoPorId(nuevoId);
    if (nuevo) {
      setEventoActivo(nuevo);
      setCantidad(nuevo.stockDisponible > 0 ? 1 : 0);
      setErrorValidacion(null);
      setPromocionActiva(null);
      setMensajePromo(null);
      setNotificacionEnviada(false);
      setReservaActiva(null);
    }
  };

  const handleCambiarCantidad = (delta: number) => {
    if (!eventoActivo) return;

    const nueva = cantidad + delta;
    if (nueva < 1) return;

    if (nueva > eventoActivo.stockDisponible) {
      setErrorValidacion(`No hay suficiente stock. Solo quedan ${eventoActivo.stockDisponible} entradas.`);
      return;
    }

    if (eventoActivo.tipoEntrada === "GRATUITA" && eventoActivo.limiteGratuitoUsuario) {
      if (nueva > eventoActivo.limiteGratuitoUsuario) {
        setErrorValidacion(
          `Límite de entradas gratuitas excedido: según HU-08 solo puedes solicitar hasta ${eventoActivo.limiteGratuitoUsuario} entrada(s) por usuario.`
        );
        return;
      }
    }

    if (eventoActivo.tipoEntrada === "PAGADA" && nueva > eventoActivo.maxTickets) {
      setErrorValidacion(
        `Límite por compra excedido: máximo ${eventoActivo.maxTickets} entradas por transacción.`
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
      setMensajePromo({ tipo: "error", texto: "Las entradas gratuitas ya tienen costo $0." });
      return;
    }

    const resultado = await evaluarPromocion({
      idEvento: eventoActivo.id,
      idUsuario: "usr-12345",
      cantidadEntradas: cantidad,
      codigoPromocion: codigoDescuento,
    });

    if (resultado) {
      setPromocionActiva(resultado);
      setMensajePromo({ tipo: "exito", texto: `¡${resultado.descripcion}!` });
      setErrorValidacion(null);
    } else {
      setPromocionActiva(null);
      setMensajePromo({ tipo: "error", texto: "Código de promoción no válido o expirado." });
    }
  };

  const esEventoGratuito = eventoActivo?.tipoEntrada === "GRATUITA";
  const estaAgotado = (eventoActivo?.stockDisponible ?? 0) <= 0;
  const precioUnitario = eventoActivo?.precio ?? 0;

  const subtotal = precioUnitario * cantidad;
  const porcentajeDescuento = promocionActiva ? promocionActiva.porcentajeDescuento : 0;
  const montoDescuento = Math.round(subtotal * (porcentajeDescuento / 100));
  const totalFinal = Math.max(0, subtotal - montoDescuento);

  const handleContinuarAdquisicion = async () => {
    if (!eventoActivo) return;
    if (cantidad === 0) {
      setErrorValidacion("Debes seleccionar al menos una entrada.");
      return;
    }

    setProcesando(true);
    setErrorValidacion(null);

    try {
      if (esEventoGratuito) {
        const emitida = await emitirEntradaDirecta({
          idEvento: eventoActivo.id,
          idUsuario: "usr-12345",
          nombreComprador: "Sebastian Fuentes",
          correoComprador: "sebastian.fuentes@ticketu.cl",
          cantidadEntradas: cantidad,
          precioFinal: 0,
        });

        await recargarEventoActivo(eventoActivo.id);
        setUltimoTicketEmitido(emitida);

        if (typeof window !== "undefined") {
          window.open(`/entradas/confirmacion?idEntrada=${emitida.idEntrada}`, "_blank");
        }
      } else {
        const reserva = await crearReservaTemporal({
          idEvento: eventoActivo.id,
          idUsuario: "usr-12345",
          cantidadEntradas: cantidad,
          subtotal: subtotal,
          descuento: montoDescuento,
          total: totalFinal,
        });

        await recargarEventoActivo(eventoActivo.id);
        setReservaActiva(reserva);
      }
    } catch (err: unknown) {
      setErrorValidacion(err instanceof Error ? err.message : "Error al procesar la solicitud.");
    } finally {
      setProcesando(false);
    }
  };

  if (cargando) {
    return (
      <div className={styles.entradasModuleScope}>
        <div className={styles.container} style={{ textAlign: "center", padding: "48px 0" }}>
          <div style={{ fontSize: "36px", marginBottom: "16px" }}>🎟️</div>
          <h2 className={styles.titleH2}>Cargando inventario desde MongoDB (`entradas-service`)...</h2>
          <p className={styles.textMuted}>Conectando a través del API Gateway (`http://localhost:8080/api/entradas/eventos`)</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.entradasModuleScope} style={{ minHeight: "80vh", padding: "24px 0 48px 0" }}>
      <div className={styles.container}>
        {/* Banner de Contexto Superior */}
        <div className={styles.bannerContext}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span className={`${styles.badge} ${styles.badgeInfo}`}>Grupo 3 · Entradas</span>
              <span className={`${styles.badge} ${styles.badgeSuccess}`}>
                ✓ Conectado con API Gateway (:8080) · Catálogo (:4000) · MongoDB Entradas · MySQL Check-in (:3005)
              </span>
            </div>
            <h1 className={styles.titleH1} style={{ margin: "4px 0 0 0" }}>
              Adquisición, Sincronización con Catálogo y Emisión hacia Check-in
            </h1>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <label htmlFor="select-evento" style={{ fontSize: "14px", fontWeight: 600, color: THEME.colors.primary }}>
              Evento en BD:
            </label>
            <select
              id="select-evento"
              value={eventoActivo?.id || ""}
              onChange={(e) => handleCambiarEvento(e.target.value)}
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
              }}
            >
              {eventos.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  [{ev.id}] {ev.titulo} ({ev.tipoEntrada})
                </option>
              ))}
            </select>
            <Link
              href={eventoActivo ? `/catalogo/${eventoActivo.id}` : "/catalogo"}
              className={styles.buttonSecondary}
              style={{ height: "40px", padding: "0 14px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
            >
              🔎 Ver en Catálogo
            </Link>
            <Link
              href="/checkin"
              className={styles.buttonSecondary}
              style={{ height: "40px", padding: "0 14px", textDecoration: "none", display: "inline-flex", alignItems: "center" }}
            >
              🚪 Ir a Check-in ➔
            </Link>
          </div>
        </div>

        {/* Banner si se acaba de emitir un ticket */}
        {ultimoTicketEmitido && (
          <div className={`${styles.alert} ${styles.alertSuccess}`} style={{ marginBottom: "20px", justifyContent: "space-between", flexWrap: "wrap" }}>
            <div>
              <strong>✅ ¡Entrada {ultimoTicketEmitido.idEntrada} emitida en MongoDB y registrada en MySQL de Check-in!</strong>
              <div style={{ fontSize: "13px", marginTop: "4px" }}>
                Puedes ver su código QR o validarla inmediatamente en el módulo de Check-in.
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", marginTop: "6px" }}>
              <Link
                href={`/entradas/confirmacion?idEntrada=${ultimoTicketEmitido.idEntrada}`}
                target="_blank"
                className={styles.buttonPrimary}
                style={{ height: "36px", padding: "0 14px", fontSize: "13px", textDecoration: "none" }}
              >
                🎟️ Ver Pase QR ({ultimoTicketEmitido.idEntrada})
              </Link>
              <button
                type="button"
                onClick={() => router.push(`/checkin?idEntrada=${ultimoTicketEmitido.idEntrada}&idEvento=${ultimoTicketEmitido.idEvento}`)}
                className={styles.buttonSecondary}
                style={{ height: "36px", padding: "0 14px", fontSize: "13px" }}
              >
                🔍 Validar en Check-in
              </button>
            </div>
          </div>
        )}

        {/* Widget HU-01 para Catálogo (sin botón redundante dentro de /entradas) */}
        {eventoActivo && (
          <div style={{ marginBottom: "24px" }}>
            <DisponibilidadPlaceholder
              key={`${eventoActivo.id}-${eventoActivo.stockDisponible}`}
              eventoId={eventoActivo.id}
              mostrarBotonAccion={false}
            />
          </div>
        )}

        {/* Tarjeta de Información del Evento Activo */}
        {eventoActivo && (
          <div className={styles.card} style={{ marginBottom: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
              <div style={{ flex: "1 1 300px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                  <span
                    className={`${styles.badge} ${
                      estaAgotado ? styles.badgeDanger : esEventoGratuito ? styles.badgeSuccess : styles.badgeInfo
                    }`}
                  >
                    {estaAgotado ? "Agotado" : esEventoGratuito ? "Evento Gratuito" : "Evento Pagado"}
                  </span>
                  <span style={{ fontSize: "13px", color: THEME.colors.secondary, fontWeight: 500 }}>
                    ID MongoDB: <code>{eventoActivo.id}</code> · Estado: <strong>{eventoActivo.estadoGestion}</strong>
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
                  <span>📅 {eventoActivo.fecha}</span>
                  <span>⏰ {eventoActivo.hora}</span>
                  <span>📍 {eventoActivo.lugar}</span>
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
                <div style={{ fontSize: "12px", color: THEME.colors.secondary, fontWeight: 600 }}>Aforo Disponible (MongoDB):</div>
                <div
                  style={{
                    fontSize: "24px",
                    fontWeight: 700,
                    fontFamily: THEME.fonts.titles,
                    color: estaAgotado ? THEME.colors.danger.text : THEME.colors.primary,
                  }}
                >
                  {eventoActivo.stockDisponible} / {eventoActivo.stockTotal}
                </div>
                <span style={{ fontSize: "12px", color: THEME.colors.secondary }}>entradas restantes</span>
              </div>
            </div>
          </div>
        )}

        {errorValidacion && (
          <div className={`${styles.alert} ${styles.alertDanger}`} style={{ marginBottom: "20px" }}>
            <span>⚠️</span>
            <div>{errorValidacion}</div>
          </div>
        )}

        {estaAgotado ? (
          <div className={styles.card} style={{ textAlign: "center", padding: "40px 20px" }}>
            <div style={{ fontSize: "48px", marginBottom: "16px" }}>🚫</div>
            <h2 className={styles.titleH2} style={{ color: THEME.colors.danger.text }}>
              Entradas Agotadas para este Evento
            </h2>
            <p className={styles.textMuted} style={{ maxWidth: "560px", margin: "0 auto 24px auto" }}>
              El aforo llegó a cero (HU-07). Si algún cupo se libera por expiración de reserva o cancelación,
              podemos notificarte inmediatamente al correo.
            </p>

            {notificacionEnviada ? (
              <div className={`${styles.alert} ${styles.alertSuccess}`} style={{ maxWidth: "480px", margin: "0 auto" }}>
                <span>✅</span>
                <span>¡Suscripción registrada! Te avisaremos al correo si se libera stock.</span>
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (correoNotificacion) setNotificacionEnviada(true);
                }}
                style={{ display: "flex", justifyContent: "center", gap: "8px", maxWidth: "420px", margin: "0 auto", flexWrap: "wrap" }}
              >
                <input
                  type="email"
                  required
                  placeholder="tu.correo@alumnos.uv.cl"
                  value={correoNotificacion}
                  onChange={(e) => setCorreoNotificacion(e.target.value)}
                  style={{
                    height: "40px",
                    padding: "0 12px",
                    borderRadius: THEME.radius.input,
                    border: `1px solid ${THEME.colors.border}`,
                    fontFamily: THEME.fonts.body,
                    fontSize: "14px",
                    flex: "1 1 200px",
                  }}
                />
                <button type="submit" className={styles.buttonPrimary}>
                  Avisarme si hay cupos
                </button>
              </form>
            )}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "24px" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <div className={styles.card}>
                <h3 className={styles.titleH3}>1. Selección de Entradas</h3>
                <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "20px" }}>
                  {esEventoGratuito
                    ? "Evento de acceso gratuito: emite tu entrada en MongoDB y la registra en Check-in."
                    : "Selecciona cuántas entradas deseas reservar temporalmente en MongoDB."}
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
                      {esEventoGratuito ? "Pase Gratuito Oficial" : "Entrada General Oficial"}
                    </div>
                    <div style={{ fontSize: "13px", color: THEME.colors.secondary, marginTop: "2px" }}>
                      {esEventoGratuito
                        ? `Límite: Máx ${eventoActivo?.limiteGratuitoUsuario || 2} por persona (HU-08)`
                        : `Límite: Máx ${eventoActivo?.maxTickets} por transacción (HU-02)`}
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "20px", fontWeight: 700, fontFamily: THEME.fonts.titles, color: THEME.colors.primary }}>
                      {esEventoGratuito ? "Gratis" : `$${precioUnitario.toLocaleString("es-CL")}`}
                    </div>
                    <span style={{ fontSize: "12px", color: THEME.colors.secondary }}>c/u</span>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "16px" }}>
                  <span style={{ fontWeight: 600, color: THEME.colors.primary }}>Cantidad de Entradas:</span>

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
                  <h3 className={styles.titleH3}>¿Tienes un Código de Promoción?</h3>
                  <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "16px" }}>
                    Prueba con <strong>INFO2026</strong> (-15%) o <strong>TITEC20</strong> (-20%).
                  </p>

                  <form onSubmit={handleAplicarPromocion} style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <input
                      type="text"
                      placeholder="Código de descuento"
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
                    <button type="submit" className={styles.buttonSecondary} style={{ height: "40px" }}>
                      Aplicar Descuento
                    </button>
                  </form>

                  {mensajePromo && (
                    <div
                      className={`${styles.alert} ${mensajePromo.tipo === "exito" ? styles.alertSuccess : styles.alertDanger}`}
                      style={{ marginTop: "12px", padding: "10px 14px", fontSize: "13px" }}
                    >
                      <span>{mensajePromo.tipo === "exito" ? "🎉" : "⚠️"}</span>
                      <span>{mensajePromo.texto}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div>
              <div className={styles.card} style={{ position: "sticky", top: "24px" }}>
                <h3 className={styles.titleH3}>2. Resumen de Adquisición</h3>
                <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "16px" }}>
                  Verifica el desglose antes de proceder.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "14px", paddingBottom: "8px", borderBottom: `1px solid ${THEME.colors.border}` }}>
                    <span>Evento:</span>
                    <strong>{eventoActivo?.titulo}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "14px", paddingBottom: "8px", borderBottom: `1px solid ${THEME.colors.border}` }}>
                    <span>Cantidad:</span>
                    <strong>{cantidad} entrada(s)</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "14px", paddingBottom: "8px", borderBottom: `1px solid ${THEME.colors.border}` }}>
                    <span>Subtotal:</span>
                    <strong>{esEventoGratuito ? "Gratis ($0)" : `$${subtotal.toLocaleString("es-CL")}`}</strong>
                  </div>

                  {promocionActiva && (
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "14px", color: THEME.colors.success.text, paddingBottom: "8px", borderBottom: `1px solid ${THEME.colors.border}` }}>
                      <span>Descuento (-{promocionActiva.porcentajeDescuento}%):</span>
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
                  <span>Total Final:</span>
                  <span style={{ fontSize: "22px" }}>
                    {totalFinal === 0 ? "$0 (Gratis)" : `$${totalFinal.toLocaleString("es-CL")}`}
                  </span>
                </div>

                <div
                  className={`${styles.alert} ${esEventoGratuito ? styles.alertSuccess : styles.alertInfo}`}
                  style={{ marginTop: 0, marginBottom: "20px", fontSize: "13px" }}
                >
                  <span>{esEventoGratuito ? "🎁" : "⏱️"}</span>
                  <div>
                    {esEventoGratuito ? (
                      <strong>Emisión Directa: Crea el ticket en MongoDB, lo sincroniza en MySQL de Check-in y abre el QR.</strong>
                    ) : (
                      <span>
                        <strong>Reserva Temporal (HU-03):</strong> Descuenta el cupo en MongoDB y al confirmar emite el ticket hacia Check-in.
                      </span>
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  disabled={procesando || cantidad === 0}
                  onClick={handleContinuarAdquisicion}
                  className={styles.buttonPrimary}
                  style={{ width: "100%", height: "48px", fontSize: "15px" }}
                >
                  {procesando
                    ? "Procesando en Backend..."
                    : esEventoGratuito
                    ? "Emitir Entrada Gratuita + Registrar en Check-in ➔"
                    : `Reservar Cupo (Hold) en MongoDB ($${totalFinal.toLocaleString("es-CL")}) ➔`}
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
            onPagoCompletado={async (idEntrada) => {
              if (eventoActivo) {
                await recargarEventoActivo(eventoActivo.id);
                setUltimoTicketEmitido({
                  idEntrada,
                  idEvento: eventoActivo.id,
                  nombreEvento: eventoActivo.titulo,
                  nombreComprador: "Sebastian Fuentes",
                  correoComprador: "sebastian.fuentes@ticketu.cl",
                  tipoAcceso: "Entrada General Oficial",
                  precioFinal: reservaActiva.total,
                  cantidadEntradas: reservaActiva.cantidadEntradas,
                  qrData: `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${idEntrada}`,
                  fechaEvento: eventoActivo.fecha,
                  horaEvento: eventoActivo.hora,
                  lugarEvento: eventoActivo.lugar,
                  fechaEmision: new Date().toLocaleDateString("es-CL"),
                });
              }
            }}
          />
        )}
      </div>
    </div>
  );
}
