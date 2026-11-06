"use client";

import { useState, useRef, useEffect } from "react";
import styles from "../styles/catalogo.module.css";

export interface FiltrosMenuState {
    estadoTemporal: "proximos" | "pasados" | null;
    gratuitos: boolean;
    rangoPrecioActivo: boolean;
    precioMin: string;
    precioMax: string;
    mejorValorados: boolean;
}

export const FILTROS_MENU_INICIALES: FiltrosMenuState = {
    estadoTemporal: "proximos",
    gratuitos: false,
    rangoPrecioActivo: false,
    precioMin: "",
    precioMax: "",
    mejorValorados: false,
};

interface FiltrosMenuProps {
    filtros: FiltrosMenuState;
    onChange: (nuevosFiltros: FiltrosMenuState) => void;
}

export default function FiltrosMenu({ filtros, onChange }: FiltrosMenuProps) {
    const [abierto, setAbierto] = useState(false);
    const contenedorRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!abierto) return;

        function handleClickFuera(event: MouseEvent) {
            if (contenedorRef.current && !contenedorRef.current.contains(event.target as Node)) {
                setAbierto(false);
            }
        }

        function handleKeyDown(event: KeyboardEvent) {
            if (event.key === "Escape") {
                setAbierto(false);
            }
        }

        document.addEventListener("mousedown", handleClickFuera);
        document.addEventListener("keydown", handleKeyDown);
        return () => {
            document.removeEventListener("mousedown", handleClickFuera);
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, [abierto]);

    const handleProximosChange = () => {
        onChange({
            ...filtros,
            estadoTemporal: filtros.estadoTemporal === "proximos" ? null : "proximos",
        });
    };

    const handlePasadosChange = () => {
        onChange({
            ...filtros,
            estadoTemporal: filtros.estadoTemporal === "pasados" ? null : "pasados",
        });
    };

    const handleGratuitosChange = () => {
        onChange({
            ...filtros,
            gratuitos: !filtros.gratuitos,
        });
    };

    const handleRangoPrecioToggle = () => {
        onChange({
            ...filtros,
            rangoPrecioActivo: !filtros.rangoPrecioActivo,
        });
    };

    const handleMejorValoradosChange = () => {
        onChange({
            ...filtros,
            mejorValorados: !filtros.mejorValorados,
        });
    };

    return (
        <div className={styles.filtrosContenedor} ref={contenedorRef}>
            <button
                type="button"
                id="boton-filtros"
                aria-haspopup="true"
                aria-expanded={abierto}
                aria-controls="menu-desplegable-filtros"
                className={styles.botonFiltros}
                onClick={() => setAbierto((prev) => !prev)}
            >
                <svg
                    width="20"
                    height="20"
                    viewBox="0 0 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    aria-hidden="true"
                >
                    <line x1="3" y1="5" x2="17" y2="5" />
                    <line x1="3" y1="10" x2="17" y2="10" />
                    <line x1="3" y1="15" x2="17" y2="15" />
                </svg>
                <span>Filtros</span>
            </button>

            {abierto && (
                <div
                    id="menu-desplegable-filtros"
                    role="region"
                    aria-label="Filtros de eventos"
                    className={styles.menuDesplegable}
                >
                    {/* a. Eventos próximos */}
                    <label className={styles.opcionFiltro}>
                        <input
                            type="checkbox"
                            className={styles.checkbox}
                            checked={filtros.estadoTemporal === "proximos"}
                            onChange={handleProximosChange}
                        />
                        <span>Eventos próximos</span>
                    </label>

                    {/* b. Eventos pasados */}
                    <label className={styles.opcionFiltro}>
                        <input
                            type="checkbox"
                            className={styles.checkbox}
                            checked={filtros.estadoTemporal === "pasados"}
                            onChange={handlePasadosChange}
                        />
                        <span>Eventos pasados</span>
                    </label>

                    {/* c. Gratuitos */}
                    <label className={styles.opcionFiltro}>
                        <input
                            type="checkbox"
                            className={styles.checkbox}
                            checked={filtros.gratuitos}
                            onChange={handleGratuitosChange}
                        />
                        <span>Gratuitos</span>
                    </label>

                    {/* d. Rango de precio */}
                    <label className={styles.opcionFiltro}>
                        <input
                            type="checkbox"
                            className={styles.checkbox}
                            checked={filtros.rangoPrecioActivo}
                            onChange={handleRangoPrecioToggle}
                        />
                        <span>Rango de precio</span>
                    </label>
                    {filtros.rangoPrecioActivo && (
                        <div className={styles.rangoPrecioInputs}>
                            <input
                                type="number"
                                min="0"
                                placeholder="Mín"
                                value={filtros.precioMin}
                                onChange={(e) =>
                                    onChange({ ...filtros, precioMin: e.target.value })
                                }
                                className={styles.inputPrecio}
                                aria-label="Precio mínimo en pesos"
                            />
                            <span className={styles.separadorPrecio}>—</span>
                            <input
                                type="number"
                                min="0"
                                placeholder="Máx"
                                value={filtros.precioMax}
                                onChange={(e) =>
                                    onChange({ ...filtros, precioMax: e.target.value })
                                }
                                className={styles.inputPrecio}
                                aria-label="Precio máximo en pesos"
                            />
                        </div>
                    )}

                    {/* e. Mejor valorados */}
                    <label className={styles.opcionFiltro}>
                        <input
                            type="checkbox"
                            className={styles.checkbox}
                            checked={filtros.mejorValorados}
                            onChange={handleMejorValoradosChange}
                        />
                        <span>Mejor valorados</span>
                    </label>


                    {/* Botón Limpiar filtros */}
                    <button
                        type="button"
                        onClick={() => onChange(FILTROS_MENU_INICIALES)}
                        className={styles.botonLimpiarFiltros}
                    >
                        Limpiar filtros
                    </button>
                </div>
            )}
        </div>
    );
}
