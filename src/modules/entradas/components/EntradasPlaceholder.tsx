// ============================================================================
// modules/entradas/components/EntradasPlaceholder.tsx
// ----------------------------------------------------------------------------
// Entradas / Inventario — Grupo 3.
// Componente interactivo principal de la ruta /entradas.
//
// Nomenclatura 100% en camelCase.
// Soporta:
// - Integración con Promociones (Grupo 9) para cálculo de descuentos (HU-02).
// - Reserva temporal de cupos con Hold de 15 minutos (HU-03).
// - Emisión y apertura de ticket con código QR en nueva pestaña (HU-04, HU-05, HU-09).
// - Redirección a Pagos (Grupo 4).
// - Mitigación de acaparamiento en entradas gratuitas (HU-08).
// ============================================================================

"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  obtenerEventos,
  obtenerEventoPorId,
  crearReservaTemporal,
  emitirEntradaDirecta,
  evaluarPromocion,
  liberarReservaTemporal,
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

  // Estado general de eventos
  const [eventos, setEventos] = useState<EventoEntradas[]>([]);
  const [eventoActivo, setEventoActivo] = useState<EventoEntradas | null>(null);
  const [cargando, setCargando] = useState(true);

  // Cantidad de entradas seleccionadas
  const [cantidad, setCantidad] = useState<number>(1);
  const [procesando, setProcesando] = useState(false);
  const [errorValidacion, setErrorValidacion] = useState<string | null>(null);

  // Integración con Promociones (Grupo 9)
  const [codigoDescuento, setCodigoDescuento] = useState("");
  const [promocionActiva, setPromocionActiva] = useState<PromocionAplicada | null>(null);
  const [mensajePromo, setMensajePromo] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);

  // Estados de Reserva Temporal (HU-03) y Notificación Agotado (HU-07)
  const [reservaActiva, setReservaActiva] = useState<ReservaTemporal | null>(null);
  const [ultimoTicketEmitido, setUltimoTicketEmitido] = useState<EntradaEmitida | null>(null);
  const [correoNotificacion, setCorreoNotificacion] = useState("");
  const [notificacionEnviada, setNotificacionEnviada] = useState(false);

  // Temporizador para el Hold de 10 minutos (HU-03)
  const [segundosRestantes, setSegundosRestantes] = useState(10 * 60);

  // Cargar eventos al montar
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

  // Temporizador regresivo para la reserva temporal (liberación al llegar a 0)
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (reservaActiva && segundosRestantes > 0) {
      timer = setInterval(() => {
        setSegundosRestantes((prev) => {
          if (prev <= 1) {
            // Tiempo expirado: liberar stock reservado
            liberarReservaTemporal(reservaActiva.idEvento, reservaActiva.cantidadEntradas);
            if (eventoActivo && eventoActivo.id === reservaActiva.idEvento) {
              setEventoActivo({
                ...eventoActivo,
                stockDisponible: eventoActivo.stockDisponible + reservaActiva.cantidadEntradas,
              });
            }
            setReservaActiva(null);
            setErrorValidacion("El tiempo límite de 10 minutos ha expirado. Tu cupo reservado ha sido liberado automáticamente.");
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [reservaActiva, segundosRestantes, eventoActivo]);

  // Cambiar evento en el selector interactivo
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

  // Modificar cantidad con el Stepper (+/-)
  const handleCambiarCantidad = (delta: number) => {
    if (!eventoActivo) return;

    const nueva = cantidad + delta;
    if (nueva < 1) return;

    // Validación de stock disponible
    if (nueva > eventoActivo.stockDisponible) {
      setErrorValidacion(`No hay suficiente stock. Solo quedan ${eventoActivo.stockDisponible} entradas.`);
      return;
    }

    // Validación de entradas gratuitas (HU-08)
    if (eventoActivo.tipoEntrada === "GRATUITA" && eventoActivo.limiteGratuitoUsuario) {
      if (nueva > eventoActivo.limiteGratuitoUsuario) {
        setErrorValidacion(
          `Límite de entradas gratuitas excedido: según HU-08 solo puedes solicitar hasta ${eventoActivo.limiteGratuitoUsuario} entrada(s) por usuario (mitigación de acaparamiento).`
        );
        return;
      }
    }

    // Validación de límite por transacción para pagadas (HU-02)
    if (eventoActivo.tipoEntrada === "PAGADA" && nueva > eventoActivo.maxTickets) {
      setErrorValidacion(
        `Límite por compra excedido: máximo ${eventoActivo.maxTickets} entradas por transacción.`
      );
      return;
    }

    setErrorValidacion(null);
    setCantidad(nueva);
  };

  // Aplicar código de descuento de Promociones (Grupo 9)
  const handleAplicarPromocion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventoActivo || !codigoDescuento.trim()) return;

    if (eventoActivo.tipoEntrada === "GRATUITA") {
      setMensajePromo({ tipo: "error", texto: "Las entradas gratuitas ya tienen costo $0." });
      return;
    }

    const resultado = await evaluarPromocion({
      idEvento: eventoActivo.id,
      idUsuario: "usr-alumno-uv",
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

  // Cálculos financieros con descuento
  const subtotal = precioUnitario * cantidad;
  const porcentajeDescuento = promocionActiva ? promocionActiva.porcentajeDescuento : 0;
  const montoDescuento = Math.round(subtotal * (porcentajeDescuento / 100));
  const totalFinal = Math.max(0, subtotal - montoDescuento);

  // Acción principal: Crear Reserva (Pagado) o Emisión Directa (Gratis)
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
        // Flujo Gratuito (HU-05 y HU-08): Emisión directa inmediata
        const emitida = await emitirEntradaDirecta({
          idEvento: eventoActivo.id,
          idUsuario: "usr-alumno-uv",
          nombreComprador: "Patricio Carlos",
          correoComprador: "patricio.carlos@estudiantes.uv.cl",
          cantidadEntradas: cantidad,
          precioFinal: 0,
        });

        setEventoActivo({
          ...eventoActivo,
          stockDisponible: Math.max(0, eventoActivo.stockDisponible - cantidad),
        });

        setUltimoTicketEmitido(emitida);

        // Abrir ticket y QR en nueva pestaña (como solicitó el usuario)
        if (typeof window !== "undefined") {
          window.open(`/entradas/confirmacion?idEntrada=${emitida.idEntrada}`, "_blank");
        }
      } else {
        // Flujo Pagado (HU-03): Reserva temporal de cupos (Hold de 10 minutos)
        const reserva = await crearReservaTemporal({
          idEvento: eventoActivo.id,
          idUsuario: "usr-alumno-uv",
          cantidadEntradas: cantidad,
          subtotal: subtotal,
          descuento: montoDescuento,
          total: totalFinal,
        });

        // Restar temporalmente en el estado visual para que pase de 74 a 73
        setEventoActivo({
          ...eventoActivo,
          stockDisponible: Math.max(0, eventoActivo.stockDisponible - cantidad),
        });

        setReservaActiva(reserva);
        setSegundosRestantes(10 * 60);
      }
    } catch (err: unknown) {
      setErrorValidacion(err instanceof Error ? err.message : "Error al procesar la solicitud.");
    } finally {
      setProcesando(false);
    }
  };

  // Simular la confirmación bancaria (HU-09) y abrir ticket con QR en nueva pestaña
  const handleSimularPagoAprobado = async () => {
    if (!eventoActivo || !reservaActiva) return;
    setProcesando(true);
    try {
      const emitida = await emitirEntradaDirecta({
        idEvento: eventoActivo.id,
        idUsuario: reservaActiva.idUsuario,
        nombreComprador: "Patricio Carlos",
        correoComprador: "patricio.carlos@estudiantes.uv.cl",
        cantidadEntradas: reservaActiva.cantidadEntradas,
        precioFinal: reservaActiva.total,
      });

      setUltimoTicketEmitido(emitida);
      setReservaActiva(null);

      // Abrir en nueva pestaña
      if (typeof window !== "undefined") {
        window.open(`/entradas/confirmacion?idEntrada=${emitida.idEntrada}`, "_blank");
      }
    } finally {
      setProcesando(false);
    }
  };

  // Redirigir a Pagos (Grupo 4)
  const handleRedirigirAPagos = () => {
    if (!reservaActiva) return;
    router.push(`/pagos?idReserva=${reservaActiva.idReserva}&total=${reservaActiva.total}&cantidad=${reservaActiva.cantidadEntradas}`);
  };

  // Formato para el reloj de expiración (MM:SS)
  const formatoTiempo = (totalSegundos: number) => {
    const mins = Math.floor(totalSegundos / 60);
    const segs = totalSegundos % 60;
    return `${mins.toString().padStart(2, "0")}:${segs.toString().padStart(2, "0")}`;
  };

  if (cargando) {
    return (
      <div className={styles.entradasModuleScope}>
        <div className={styles.container} style={{ textAlign: "center", padding: "48px 0" }}>
          <div style={{ fontSize: "36px", marginBottom: "16px" }}>🎟️</div>
          <h2 className={styles.titleH2}>Cargando información del aforo...</h2>
          <p className={styles.textMuted}>Conectando con el microservicio de Entradas e Inventario</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.entradasModuleScope}>
      <div className={styles.container}>
        {/* Banner de Contexto Superior acordado en Design System */}
        <div className={styles.bannerContext}>
          <div>
            <span style={{ fontSize: "12px", fontWeight: 600, color: THEME.colors.secondary, textTransform: "uppercase" }}>
              Módulo de Entradas e Inventario · Grupo 3
            </span>
            <h1 className={styles.titleH1} style={{ margin: "4px 0 0 0" }}>
              Adquisición y Reserva de Entradas
            </h1>
          </div>

          {/* Selector de Evento para pruebas en vivo */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <label htmlFor="select-evento" style={{ fontSize: "14px", fontWeight: 600, color: THEME.colors.primary }}>
              Probar Evento:
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
                  {ev.titulo} ({ev.tipoEntrada})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Tarjeta de Información General del Evento Activo */}
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
                    Estado de Gestión: <strong>{eventoActivo.estadoGestion}</strong>
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

              {/* Indicador de Stock Restante */}
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
                <div style={{ fontSize: "12px", color: THEME.colors.secondary, fontWeight: 600 }}>Aforo Disponible:</div>
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

        {/* Mensaje de Error de Validación */}
        {errorValidacion && (
          <div className={`${styles.alert} ${styles.alertDanger}`} style={{ marginBottom: "20px" }}>
            <span>⚠️</span>
            <div>{errorValidacion}</div>
          </div>
        )}

        {/* Caso: Evento Agotado con Solicitud de Notificación (HU-07) */}
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
          /* Cuadrícula Principal: Selección a la izquierda, Resumen y Descuento a la derecha */
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "24px" }}>
            {/* Columna Izquierda: Selección de Entradas y Promociones */}
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <div className={styles.card}>
                <h3 className={styles.titleH3}>1. Selección de Entradas</h3>
                <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "20px" }}>
                  {esEventoGratuito
                    ? "Evento de acceso gratuito para la comunidad universitaria."
                    : "Selecciona cuántas entradas deseas adquirir para este evento."}
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
                        ? `Límite: Máx ${eventoActivo?.limiteGratuitoUsuario || 1} por persona (HU-08)`
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

                {/* Control Stepper de Cantidad */}
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
                        (esEventoGratuito && cantidad >= (eventoActivo?.limiteGratuitoUsuario ?? 1)) ||
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

              {/* Formulario de Código de Descuento (Integración Promociones Grupo 9) */}
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

            {/* Columna Derecha: Resumen de Compra / Adquisición */}
            <div>
              <div className={styles.card} style={{ position: "sticky", top: "24px" }}>
                <h3 className={styles.titleH3}>2. Resumen de Adquisición</h3>
                <p className={styles.textMuted} style={{ fontSize: "13px", marginBottom: "16px" }}>
                  Verifica el desglose antes de proceder.
                </p>

                {/* Desglose */}
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

                  {/* Fila de Descuento si está activo */}
                  {promocionActiva && (
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "14px", color: THEME.colors.success.text, paddingBottom: "8px", borderBottom: `1px solid ${THEME.colors.border}` }}>
                      <span>Descuento Promociones (-{promocionActiva.porcentajeDescuento}%):</span>
                      <strong>-${montoDescuento.toLocaleString("es-CL")}</strong>
                    </div>
                  )}
                </div>

                {/* Total Final */}
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

                {/* Alerta explicativa del tipo de flujo */}
                <div
                  className={`${styles.alert} ${esEventoGratuito ? styles.alertSuccess : styles.alertInfo}`}
                  style={{ marginTop: 0, marginBottom: "20px", fontSize: "13px" }}
                >
                  <span>{esEventoGratuito ? "🎁" : "⏱️"}</span>
                  <div>
                    {esEventoGratuito ? (
                      <strong>Flujo Gratuito: Tu entrada y código QR se abrirán en una nueva pestaña sin costo.</strong>
                    ) : (
                      <span>
                        <strong>Reserva Temporal (HU-03):</strong> Congelamos tus cupos por 10 minutos mientras se efectúa el pago.
                      </span>
                    )}
                  </div>
                </div>

                {/* Botón de Acción Principal */}
                <button
                  type="button"
                  disabled={procesando || cantidad === 0}
                  onClick={handleContinuarAdquisicion}
                  className={styles.buttonPrimary}
                  style={{ width: "100%", height: "48px", fontSize: "15px" }}
                >
                  {procesando
                    ? "Procesando solicitud..."
                    : esEventoGratuito
                    ? "Obtener Entrada Gratuita Directa (Abrir QR) ➔"
                    : `Continuar a Reserva ($${totalFinal.toLocaleString("es-CL")}) ➔`}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ====================================================================
            MODAL: RESERVA TEMPORAL GENERADA (HU-03 - Flujo Pagado)
            ==================================================================== */}
        {reservaActiva && (
          <div className={styles.modalOverlay}>
            <div className={styles.modalContent}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <span className={`${styles.badge} ${styles.badgeInfo}`}>Hold Activo · 10 Minutos</span>
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
                Hemos descontado temporalmente del inventario {reservaActiva.cantidadEntradas} entrada(s) para evitar que se agoten mientras completas el pago.
              </p>

              {/* Ficha de la Reserva */}
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
                  <strong>{reservaActiva.idReserva}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ color: THEME.colors.secondary }}>Evento:</span>
                  <strong>{eventoActivo?.titulo}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ color: THEME.colors.secondary }}>Cantidad:</span>
                  <strong>{reservaActiva.cantidadEntradas} entrada(s)</strong>
                </div>
                {reservaActiva.descuento > 0 && (
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", color: THEME.colors.success.text }}>
                    <span>Descuento aplicado:</span>
                    <strong>-${reservaActiva.descuento.toLocaleString("es-CL")}</strong>
                  </div>
                )}
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ color: THEME.colors.secondary }}>Monto a Cobrar:</span>
                  <strong style={{ fontSize: "16px", color: THEME.colors.primary }}>
                    ${reservaActiva.total.toLocaleString("es-CL")}
                  </strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: THEME.colors.secondary }}>Estado del Pago:</span>
                  <span className={`${styles.badge} ${styles.badgeMuted}`}>Pendiente de Cobro</span>
                </div>
              </div>

              {/* Acciones de la Reserva */}
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {/* Opción A: Simulación de Pago y Apertura en Pestaña Nueva */}
                <button
                  type="button"
                  disabled={procesando}
                  onClick={handleSimularPagoAprobado}
                  className={styles.buttonPrimary}
                  style={{ width: "100%", height: "46px" }}
                >
                  {procesando ? "Consolidando..." : "💳 Simular Pago Aprobado y Abrir Entrada con QR ➔"}
                </button>

                {/* Opción B: Redirigir a la URL oficial de Pagos */}
                <button
                  type="button"
                  onClick={handleRedirigirAPagos}
                  className={styles.buttonSecondary}
                  style={{ width: "100%", height: "40px" }}
                >
                  🔗 Ir a Pasarela de Pagos (Grupo 4)
                </button>

                <button
                  type="button"
                  onClick={async () => {
                    if (reservaActiva) {
                      await liberarReservaTemporal(reservaActiva.idEvento, reservaActiva.cantidadEntradas);
                      if (eventoActivo && eventoActivo.id === reservaActiva.idEvento) {
                        setEventoActivo({
                          ...eventoActivo,
                          stockDisponible: eventoActivo.stockDisponible + reservaActiva.cantidadEntradas,
                        });
                      }
                      setReservaActiva(null);
                    }
                  }}
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
                  Liberar cupo y modificar pedido
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
