export default function Estrellas({ valor, tamano = 16 }: { valor: number; tamano?: number }) {
    return (
        <span style={{ display: "inline-flex", gap: "2px", alignItems: "center" }}>
            {[1, 2, 3, 4, 5].map((i) => {
                const rellena = i <= Math.round(valor);
                return (
                    <svg
                        key={i}
                        width={tamano}
                        height={tamano}
                        viewBox="0 0 24 24"
                        fill={rellena ? "var(--color-primario)" : "none"}
                        stroke="var(--color-primario)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                    >
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                    </svg>
                );
            })}
        </span>
    );
}
