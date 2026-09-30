import { Suspense } from "react";
import ConfirmacionTicket from "@/modules/entradas/components/ConfirmacionTicket";

// Página de Confirmación y Código QR de Entrada — GRUPO 3
//
// Esta vista se abre en una pestaña independiente cuando se emite una
// entrada gratuita o se aprueba el pago de una compra. Muestra el código QR
// de acceso oficial para presentar en el Check-in.

export default function ConfirmacionEntradaPage() {
  return (
    <Suspense fallback={<div style={{ padding: "48px", textAlign: "center" }}>Cargando entrada oficial...</div>}>
      <ConfirmacionTicket />
    </Suspense>
  );
}
