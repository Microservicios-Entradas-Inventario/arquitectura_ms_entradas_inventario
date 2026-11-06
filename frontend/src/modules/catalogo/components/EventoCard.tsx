import Link from "next/link";
import type { Evento } from "../types";
import { formatearFecha, formatearPrecio, esPasado } from "../formato";
import ImagenEvento from "./ImagenEvento";
import styles from "../styles/catalogo.module.css";

interface EventoCardProps {
    evento: Evento;
}

export default function EventoCard({ evento }: EventoCardProps) {
    const eventoEsPasado = esPasado(evento);
    const esAgotado = evento.estado_evento === "agotado";
    const esCancelado = evento.estado_evento === "cancelado";
    const esAtenuada = esAgotado || esCancelado || eventoEsPasado;

    const estadoCardClass =
        esAgotado
            ? styles.cardAgotado
            : esCancelado
            ? styles.cardCancelado
            : eventoEsPasado
            ? styles.cardPasado
            : styles.cardDisponible;

    const precioTexto = formatearPrecio(evento.precio_final_evento);
    const esGratis = precioTexto === "Gratis";

    return (
        <Link
            href={`/catalogo/${evento.id_evento}`}
            className={`${styles.card} ${estadoCardClass}`}
        >
            <div className={styles.imagenContenedor}>
                <ImagenEvento
                    src={evento.imagen_evento}
                    alt={evento.nombre_evento}
                    alto={160}
                    radio={8}
                    apagada={esAtenuada}
                />

                {/* Badge de estado en esquina superior izquierda (solo si NO es disponible) */}
                {(esAgotado || esCancelado || eventoEsPasado) && (
                    <span
                        className={`${styles.badgeEstado} ${
                            esAgotado
                                ? styles.badgeAgotado
                                : esCancelado
                                ? styles.badgeCancelado
                                : styles.badgePasado
                        }`}
                    >
                        {esAgotado 
                            ? "Agotado" 
                            : esCancelado 
                            ? "Cancelado" 
                            : "Pasado"}
                    </span>
                )}

                {/* Calificación y total reseñas en esquina inferior derecha (solo si total_resenas > 0) */}
                {evento.total_resenas > 0 && (
                    <span className={styles.pillCalificacion}>
                        ★ {evento.promedio_calificacion.toFixed(1)} ({evento.total_resenas})
                    </span>
                )}
            </div>

            <div className={styles.tarjetaInfo}>
                <h3 className={styles.tarjetaTitulo}>{evento.nombre_evento}</h3>
                <p className={styles.tarjetaDetalle}>
                    {evento.lugar_evento} · {formatearFecha(evento.fecha_evento)}, {evento.hora_evento}
                </p>
                <span className={`${styles.tarjetaPrecio} ${esGratis ? styles.precioGratis : ""}`}>
                    {precioTexto}
                </span>
            </div>
        </Link>
    );
}
