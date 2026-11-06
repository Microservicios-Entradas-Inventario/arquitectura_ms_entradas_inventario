// ============================================================================
// modules/catalogo/api.ts
// Recordatorio de alcance: el catálogo SOLO busca/lista/consulta eventos.
// ============================================================================

import { GATEWAY_URL } from "@/lib/env";
import type { Evento, FiltrosEventos, RespuestaLista, RespuestaDetalle, ResumenResenas, RespuestaResenas } from "./types";
import { eventosPrueba } from "./datosPrueba";
import resenasPrueba from "./resenasPrueba.json";

// Cambiar a false cuando el backend esté funcionando.
const USAR_DATOS_PRUEBA = false;

// Simulación de la integración con Reseñas (Grupo 6).
const USAR_DATOS_PRUEBA_RESENAS = false;

// TODO: el repo común usa "/api/catalogo/eventos" vía Gateway. Confirmar path final.
const BASE_PATH = "/api/catalogo/eventos";

const esperar = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function buscarEventos(filtros: FiltrosEventos = {}): Promise<Evento[]> {
    if (USAR_DATOS_PRUEBA) {
        await esperar(500);
        return eventosPrueba.filter((e) => {
            if (filtros.search && !e.nombre_evento.toLowerCase().includes(filtros.search.toLowerCase())) return false;
            if (filtros.category && e.categoria_evento !== filtros.category) return false;
            if (filtros.isFree !== undefined && (e.tipo_evento === "gratuito") !== filtros.isFree) return false;
            return true;
        });
    }

    const params = new URLSearchParams();
    if (filtros.search) params.set("search", filtros.search);
    if (filtros.category) params.set("category", filtros.category);
    if (filtros.isFree !== undefined) params.set("isFree", String(filtros.isFree));
    // TODO: temporal. El front pagina en el navegador, así que pide todos los eventos de una vez.
    // Quitar cuando el front use la paginación del backend (pagina/limite).
    params.set("limite", "100");
    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}?${params}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Error al conectar con el módulo de catálogo");
    const json: RespuestaLista = await res.json();
    return json.data;
}

export async function obtenerEventoPorId(eventoId: string): Promise<Evento> {
    if (USAR_DATOS_PRUEBA) {
        await esperar(500);
        const evento = eventosPrueba.find((e) => e.id_evento === eventoId);
        if (!evento) throw new Error("Error al obtener el evento del catálogo");
        return evento;
    }

    const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/${encodeURIComponent(eventoId)}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Error al obtener el evento del catálogo");
    const json: RespuestaDetalle = await res.json();
    return json.data;
}

export async function obtenerResenasEvento(eventoId: string, limite = 3): Promise<ResumenResenas> {
    try {
        if (USAR_DATOS_PRUEBA_RESENAS) {
            await esperar(300);
            const data = (resenasPrueba as Record<string, ResumenResenas>)[eventoId];
            if (!data) {
                return { id_evento: eventoId, promedio: null, total_resenas: 0, resenas: [] };
            }
            return {
                ...data,
                resenas: data.resenas.slice(0, limite)
            };
        }

        // TODO: endpoint propuesto del backend de Catálogo, que por dentro invoca a Reseñas.
        const res = await fetch(`${GATEWAY_URL}${BASE_PATH}/${encodeURIComponent(eventoId)}/resenas?limite=${limite}`, { cache: "no-store" });
        if (!res.ok) throw new Error("Error al obtener reseñas del evento");
        const json: RespuestaResenas = await res.json();
        return json.data;
    } catch (error) {
        console.error("Error al obtener reseñas:", error);
        return { id_evento: eventoId, promedio: null, total_resenas: 0, resenas: [] };
    }
}