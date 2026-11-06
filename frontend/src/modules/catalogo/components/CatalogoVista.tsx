"use client";

import { useState, useMemo } from "react";
import type { Evento } from "../types";
import EventoCard from "./EventoCard";
import FiltrosMenu, {
    FILTROS_MENU_INICIALES,
    type FiltrosMenuState,
} from "./FiltrosMenu";
import { poppins, inter } from "../styles/fonts";
import { esPasado } from "../formato";
import styles from "../styles/catalogo.module.css";

interface CatalogoVistaProps {
    eventos: Evento[];
}

const EVENTOS_POR_PAGINA = 6;

function normalizarTexto(texto: string): string {
    return texto
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
}

export default function CatalogoVista({ eventos }: CatalogoVistaProps) {
    const [busqueda, setBusqueda] = useState("");
    const [filtros, setFiltros] = useState<FiltrosMenuState>(FILTROS_MENU_INICIALES);
    const [pagina, setPagina] = useState(1);

    const handleBusquedaChange = (nuevoTexto: string) => {
        setBusqueda(nuevoTexto);
        setPagina(1);
    };

    const handleFiltrosChange = (nuevosFiltros: FiltrosMenuState) => {
        setFiltros(nuevosFiltros);
        setPagina(1);
    };

    const handleLimpiarTodo = () => {
        setBusqueda("");
        setFiltros(FILTROS_MENU_INICIALES);
        setPagina(1);
    };

    // Orden de aplicación: búsqueda → filtros → orden "mejor valorados"
    const eventosFiltrados = useMemo(() => {
        const termino = normalizarTexto(busqueda.trim());

        let resultado = eventos.filter((evento) => {
            // 1. Filtro por búsqueda
            if (termino) {
                const titulo = normalizarTexto(evento.nombre_evento);
                if (!titulo.includes(termino)) {
                    return false;
                }
            }

            // 2. Filtros de menú
            // a / b: Estado temporal
            if (filtros.estadoTemporal === "proximos" && esPasado(evento)) {
                return false;
            }
            if (filtros.estadoTemporal === "pasados" && !esPasado(evento)) {
                return false;
            }

            // c: Gratuitos
            if (filtros.gratuitos && evento.tipo_evento !== "gratuito") {
                return false;
            }

            // d: Rango de precio
            if (filtros.rangoPrecioActivo) {
                const min = filtros.precioMin.trim();
                const max = filtros.precioMax.trim();
                if (min !== "" && evento.precio_final_evento < Number(min)) {
                    return false;
                }
                if (max !== "" && evento.precio_final_evento > Number(max)) {
                    return false;
                }
            }

            return true;
        });

        // 3. Orden temporal / mejor valorados
        if (filtros.mejorValorados) {
            resultado = [...resultado].sort((a, b) => {
                const aSinResenas = a.total_resenas === 0;
                const bSinResenas = b.total_resenas === 0;
                if (aSinResenas && !bSinResenas) return 1;
                if (!aSinResenas && bSinResenas) return -1;
                if (aSinResenas && bSinResenas) return 0;
                return b.promedio_calificacion - a.promedio_calificacion;
            });
        } else {
            resultado = [...resultado].sort((a, b) => {
                const fechaA = new Date(a.fecha_evento).getTime();
                const fechaB = new Date(b.fecha_evento).getTime();
                if (filtros.estadoTemporal === "pasados") {
                    return fechaB - fechaA; // Descendente (más reciente primero)
                }
                return fechaA - fechaB; // Ascendente (más próximo primero)
            });
        }

        return resultado;
    }, [eventos, busqueda, filtros]);

    // 4. Paginación
    const totalPaginas = Math.ceil(eventosFiltrados.length / EVENTOS_POR_PAGINA);
    const eventosPaginados = useMemo(() => {
        const inicio = (pagina - 1) * EVENTOS_POR_PAGINA;
        return eventosFiltrados.slice(inicio, inicio + EVENTOS_POR_PAGINA);
    }, [eventosFiltrados, pagina]);

    const textoContador =
        eventosFiltrados.length === 1 ? "1 evento" : `${eventosFiltrados.length} eventos`;

    let textoSinResultados = "No encontramos eventos con esos filtros.";
    if (!busqueda && !filtros.gratuitos && !filtros.rangoPrecioActivo && !filtros.mejorValorados) {
        if (filtros.estadoTemporal === "proximos") {
            textoSinResultados = "No hay eventos próximos disponibles.";
        } else if (filtros.estadoTemporal === "pasados") {
            textoSinResultados = "No hay registro de eventos pasados.";
        }
    }

    return (
        <div className={`${styles.catalogo} ${poppins.variable} ${inter.variable}`}>
            <h1 className={styles.titulo}>Catálogo de eventos</h1>

            {/* Barra superior con FiltrosMenu y Buscador */}
            <div className={styles.barraSuperior}>
                <FiltrosMenu filtros={filtros} onChange={handleFiltrosChange} />

                <div className={styles.buscadorContenedor}>
                    <span className={styles.buscadorIcono}>
                        <svg
                            width="20"
                            height="20"
                            viewBox="0 0 20 20"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                        >
                            <circle cx="8.5" cy="8.5" r="5.5" />
                            <line x1="12.5" y1="12.5" x2="17" y2="17" />
                        </svg>
                    </span>
                    <input
                        type="search"
                        value={busqueda}
                        onChange={(e) => handleBusquedaChange(e.target.value)}
                        placeholder="Buscar eventos por nombre…"
                        aria-label="Buscar eventos"
                        className={styles.buscadorInput}
                    />
                </div>
            </div>

            {/* Contador de eventos */}
            <p className={styles.contadorEventos}>{textoContador}</p>

            {/* Grilla de eventos o Bloque sin resultados */}
            {eventosFiltrados.length === 0 ? (
                <div className={styles.sinResultados}>
                    <p className={styles.textoSinResultados}>
                        {textoSinResultados}
                    </p>
                    {textoSinResultados === "No encontramos eventos con esos filtros." && (
                        <button
                            type="button"
                            onClick={handleLimpiarTodo}
                            className={styles.botonReset}
                        >
                            Limpiar filtros
                        </button>
                    )}
                </div>
            ) : (
                <>
                    <div className={styles.grilla}>
                        {eventosPaginados.map((evento) => (
                            <EventoCard key={evento.id_evento} evento={evento} />
                        ))}
                    </div>

                    {/* Paginación (oculta si hay 1 sola página o menos) */}
                    {totalPaginas > 1 && (
                        <div className={styles.paginacion}>
                            <button
                                type="button"
                                onClick={() => setPagina((p) => Math.max(1, p - 1))}
                                disabled={pagina <= 1}
                                aria-label="Página anterior"
                                className={styles.botonPaginacion}
                            >
                                ←
                            </button>
                            <span className={styles.textoPaginacion}>
                                Página {pagina} de {totalPaginas}
                            </span>
                            <button
                                type="button"
                                onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
                                disabled={pagina >= totalPaginas}
                                aria-label="Página siguiente"
                                className={styles.botonPaginacion}
                            >
                                →
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
