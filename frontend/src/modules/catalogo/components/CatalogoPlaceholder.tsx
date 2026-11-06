// ============================================================================
// modules/catalogo/components/CatalogoPlaceholder.tsx
// ----------------------------------------------------------------------------
// Grupo 2 — Catálogo de eventos.
// Buscador avanzado de eventos futuros y pasados (promociones, reseñas
// resumidas, entradas disponibles). NO crea/modifica/elimina eventos.
// ============================================================================

import { buscarEventos } from "../api";
import CatalogoVista from "./CatalogoVista";
import { poppins, inter } from "../styles/fonts";
import styles from "../styles/catalogo.module.css";

export default async function CatalogoPlaceholder() {
    try {
        const eventos = await buscarEventos();
        return <CatalogoVista eventos={eventos} />;
    } catch {
        return (
            <div className={`${styles.catalogo} ${poppins.variable} ${inter.variable}`}>
                <div className={styles.errorCarga}>
                    No pudimos cargar los eventos. Intenta nuevamente en unos minutos.
                </div>
            </div>
        );
    }
}