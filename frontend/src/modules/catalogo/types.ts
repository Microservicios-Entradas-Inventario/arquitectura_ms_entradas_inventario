// Estructura real de la tabla `eventos` (schema_db.sql)
export type TipoEvento = "gratuito" | "pagado";
export type EstadoEvento = "disponible" | "agotado" | "pasado" | "cancelado";

export interface Evento {
    id_evento: string;
    nombre_evento: string;
    descripcion_evento: string;
    lugar_evento: string;
    fecha_evento: string;          
    hora_evento: string;          
    imagen_evento: string;         // URL
    precio_final_evento: number;   // 0 = gratuito
    tipo_evento: TipoEvento;
    categoria_evento: string | null;
    estado_evento: EstadoEvento;
    stock_actual: number;
    promedio_calificacion: number; // 0 si no hay reseñas
    total_resenas: number;
    metrica_clics?: number;
    created_at?: string;
    es_pasado?: boolean; // calculado por el backend
}

export interface FiltrosEventos {
    search?: string;
    category?: string;
    isFree?: boolean;
}

// Formato en que responde el backend
export interface RespuestaLista {
    success: boolean;
    count: number;
    data: Evento[];
}

export interface RespuestaDetalle {
    success: boolean;
    data: Evento;
}

export interface Resena {
  usuario_id: string;
  nombre_usuario: string;   
  calificacion: number;     // entero 1 a 5
  comentario?: string;
  fecha: string;            
}
export interface ResumenResenas {
  id_evento: string;
  promedio: number | null;
  total_resenas: number;
  resenas: Resena[];        // las más recientes primero
}
export interface RespuestaResenas { success: boolean; data: ResumenResenas; }