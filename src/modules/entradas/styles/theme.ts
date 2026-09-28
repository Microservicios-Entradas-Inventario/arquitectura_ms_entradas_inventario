// ============================================================================
// modules/entradas/styles/theme.ts
// ----------------------------------------------------------------------------
// Constantes y tokens del Design System oficial de Ticket-U
// Extraídos del documento: Documentacion Front_End.docx (Checklist Visual)
// ============================================================================

export const THEME = {
  colors: {
    primary: "#2F4374",          // Azul TicketAzul principal
    primaryHover: "#24355D",     // Hover 10% más oscuro
    secondary: "#6B7A9A",        // Texto secundario / Muted
    bgMain: "#FFFFFF",           // Fondo de página principal
    bgPanel: "#F8F9FA",          // Fondo de paneles y contenedores
    surface: "#FFFFFF",          // Fondo de tarjetas y elementos interactivos
    border: "#D8DFF0",           // Bordes de tarjetas e inputs (1px sólido)
    banner: "#EEF1F8",           // Banner de contexto superior

    // Colores semánticos de estado
    success: {
      text: "#1A6640",
      bg: "#E2F4EA",
      border: "rgba(26, 102, 64, 0.2)"
    },
    danger: {
      text: "#B3261E",
      bg: "#FDF0F2",
      border: "rgba(179, 38, 30, 0.2)"
    },
    info: {
      text: "#2F4374",
      bg: "#EEF1F8",
      border: "#D8DFF0"
    },
    muted: {
      text: "#6B7A9A",
      bg: "#F0F0F5",
      border: "#D8DFF0"
    }
  },

  fonts: {
    titles: "'Poppins', -apple-system, BlinkMacSystemFont, sans-serif",
    body: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
  },

  radius: {
    button: "8px",
    input: "8px",
    card: "12px",
    pill: "999px"
  },

  shadows: {
    card: "0 2px 10px rgba(47, 67, 116, 0.08)",
    cardHover: "0 6px 16px rgba(47, 67, 116, 0.12)",
    modal: "0 10px 30px rgba(0, 0, 0, 0.2)"
  }
} as const;
