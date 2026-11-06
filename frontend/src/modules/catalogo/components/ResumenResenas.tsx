"use client";

import { useState } from "react";
import Link from "next/link";
import styles from "../styles/catalogo.module.css";
import type { ResumenResenas as TResumenResenas } from "../types";
import { obtenerIniciales, formatearFechaRelativa, formatearNumero } from "../formato";
import Estrellas from "./Estrellas";
import ImagenEvento from "./ImagenEvento";

interface Props {
    resumen: TResumenResenas;
    eventoId: string;
    imagenEvento: string;
    tituloEvento: string;
}

export default function ResumenResenas({ resumen, eventoId, imagenEvento, tituloEvento }: Props) {
    const [expandido, setExpandido] = useState(false);

    return (
        <div className={styles.resumenResenasContainer}>
            <div className={styles.resumenResenasBarra}>
                <div className={styles.resumenResenasLinea}></div>
                <button
                    type="button"
                    className={styles.resumenResenasBotonToggle}
                    aria-expanded={expandido}
                    aria-controls="region-resumen-resenas"
                    onClick={() => setExpandido(!expandido)}
                >
                    {expandido ? (
                        <>OCULTAR RESEÑAS <span aria-hidden="true">▲</span></>
                    ) : (
                        <>VER RESEÑAS <span aria-hidden="true">▼</span></>
                    )}
                </button>
                <div className={styles.resumenResenasLinea}></div>
            </div>

            {expandido && (
                <div id="region-resumen-resenas" role="region" aria-label="Reseñas del evento" className={styles.resumenResenasContenido}>
                    {resumen.total_resenas > 0 && resumen.promedio !== null ? (
                        <>
                            <div className={styles.resumenResenasCabecera}>
                                <div className={styles.resumenResenasTitulos}>
                                    <h2 className={styles.resumenResenasH2}>RESEÑAS DEL EVENTO</h2>
                                    <p className={styles.resumenResenasDescripcion}>
                                        Opiniones de quienes asistieron a este evento o a sus ediciones anteriores.
                                    </p>
                                </div>
                                <div className={styles.resumenResenasTarjeta}>
                                    <div className={styles.resumenResenasTarjetaImagen}>
                                        <ImagenEvento src={imagenEvento} alt={tituloEvento} alto={110} />
                                    </div>
                                    <div
                                        className={styles.resumenResenasTarjetaDatos}
                                        role="img"
                                        aria-label={`Calificación promedio ${resumen.promedio.toFixed(1)} de 5, basada en ${resumen.total_resenas} ${resumen.total_resenas === 1 ? "reseña" : "reseñas"}`}
                                    >
                                        <div className={styles.resumenResenasPromedioFila}>
                                            <span className={styles.resumenResenasPromedioNum}>{resumen.promedio.toFixed(1)}</span>
                                            <span className={styles.resumenResenasPromedioTotal}>/ 5.0</span>
                                        </div>
                                        <Estrellas valor={resumen.promedio} tamano={24} />
                                        <div className={styles.resumenResenasBasadoEn}>
                                            Basado en {formatearNumero(resumen.total_resenas)} {resumen.total_resenas === 1 ? "reseña" : "reseñas"}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className={styles.resumenResenasLista}>
                                {resumen.resenas.map((resena, idx) => (
                                    <div key={idx} className={styles.resumenResenasItem}>
                                        <div className={styles.resumenResenasItemCabecera}>
                                            <div className={styles.resumenResenasItemAvatarFila}>
                                                <div className={styles.resumenResenasAvatar} aria-hidden="true">
                                                    {obtenerIniciales(resena.nombre_usuario)}
                                                </div>
                                                <div className={styles.resumenResenasItemDatosUser}>
                                                    <div className={styles.resumenResenasNombre}>{resena.nombre_usuario}</div>
                                                    <time dateTime={resena.fecha} className={styles.resumenResenasFecha}>
                                                        {formatearFechaRelativa(resena.fecha)}
                                                    </time>
                                                </div>
                                            </div>
                                            <div className={styles.resumenResenasEstrellasContainer}>
                                                <Estrellas valor={resena.calificacion} />
                                                <span className={styles.srOnly}>{resena.calificacion} de 5 estrellas</span>
                                            </div>
                                        </div>
                                        {resena.comentario && (
                                            <p className={styles.resumenResenasComentario}>{resena.comentario}</p>
                                        )}
                                    </div>
                                ))}
                            </div>

                            <div className={styles.resumenResenasBotonCtaContainer}>
                                <Link
                                    href={`/catalogo/${encodeURIComponent(eventoId)}/resenas`}
                                    className={styles.botonPrincipal}
                                >
                                    VER TODAS LAS RESEÑAS
                                </Link>
                            </div>
                        </>
                    ) : (
                        <div className={styles.resumenResenasVacio}>
                            <h2 className={styles.resumenResenasVacioTitulo}>Sin calificaciones aún</h2>
                            <p className={styles.resumenResenasVacioDesc}>Sé la primera persona en compartir tu experiencia.</p>
                            <Link
                                href={`/catalogo/${encodeURIComponent(eventoId)}/resenas`}
                                className={styles.botonPrincipal}
                            >
                                ESCRIBE UNA RESEÑA
                            </Link>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
