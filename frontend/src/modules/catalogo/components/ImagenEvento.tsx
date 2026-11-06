"use client";

import { useState } from "react";
import styles from "../styles/catalogo.module.css";

interface ImagenEventoProps {
    src: string;
    alt: string;
    alto: number;
    apagada?: boolean;
    radio?: number;
    className?: string;
}

export default function ImagenEvento({
    src,
    alt,
    alto,
    apagada = false,
    radio = 12,
    className = "",
}: ImagenEventoProps) {
    const [errorImagen, setErrorImagen] = useState(false);
    const sinImagen = !src || errorImagen;

    const estilo = {
        height: `${alto}px`,
        borderRadius: `${radio}px`,
    };

    if (sinImagen) {
        return (
            <div
                className={`${styles.imagenFallback} ${className}`}
                style={estilo}
            >
                Imagen no disponible
            </div>
        );
    }

    return (
        <img
            src={src}
            alt={alt}
            className={`${styles.imagen} ${apagada ? styles.imagenAtenuada : ""} ${className}`}
            style={estilo}
            onError={() => setErrorImagen(true)}
        />
    );
}
