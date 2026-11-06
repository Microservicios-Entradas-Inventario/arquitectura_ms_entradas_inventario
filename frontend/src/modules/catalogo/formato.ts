export function formatearPrecio(n: number): string {
    if (n === 0) {
        return "Gratis";
    }
    return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
    }).format(n);
}

export function formatearFecha(iso: string): string {
    const fecha = new Date(iso);
    const formateador = new Intl.DateTimeFormat("es-CL", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
    });
    return formateador.format(fecha).replace(".", "");
}

export function formatearFechaLarga(iso: string): string {
    const fecha = new Date(iso);
    const texto = new Intl.DateTimeFormat("es-CL", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    }).format(fecha);

    return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function obtenerIniciales(nombre: string): string {
    const palabras = nombre.trim().split(/\s+/);
    if (palabras.length === 0 || palabras[0] === "") return "";
    if (palabras.length === 1) return palabras[0][0].toUpperCase();
    return (palabras[0][0] + palabras[1][0]).toUpperCase();
}

export function formatearFechaRelativa(iso: string): string {
    const fecha = new Date(iso);
    const ahora = new Date();
    const diffMs = fecha.getTime() - ahora.getTime();
    const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

    const diffSegundos = Math.round(diffMs / 1000);
    const diffMinutos = Math.round(diffSegundos / 60);
    const diffHoras = Math.round(diffMinutos / 60);
    const diffDias = Math.round(diffHoras / 24);

    let texto = "";
    if (Math.abs(diffMinutos) < 60) {
        texto = rtf.format(diffMinutos, "minute");
    } else if (Math.abs(diffHoras) < 24) {
        texto = rtf.format(diffHoras, "hour");
    } else if (Math.abs(diffDias) < 7) {
        texto = rtf.format(diffDias, "day");
    } else if (Math.abs(diffDias) < 30) {
        const semanas = Math.round(diffDias / 7);
        texto = rtf.format(semanas, "week");
    } else if (Math.abs(diffDias) < 365) {
        const meses = Math.round(diffDias / 30);
        texto = rtf.format(meses, "month");
    } else {
        const anos = Math.round(diffDias / 365);
        texto = rtf.format(anos, "year");
    }

    return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function formatearNumero(n: number): string {
    return new Intl.NumberFormat("es-CL").format(n);
}

// El backend decide si un evento es pasado (es_pasado);
// el respaldo por estado_evento es solo para los datos de prueba.
export function esPasado(evento: { es_pasado?: boolean; estado_evento: string }): boolean {
    if (typeof evento.es_pasado === "boolean") {
        return evento.es_pasado;
    }
    return evento.estado_evento === "pasado";
}
