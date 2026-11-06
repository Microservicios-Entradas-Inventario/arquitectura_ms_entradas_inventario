import { Suspense } from "react";
import EntradasPlaceholder from "@/modules/entradas/components/EntradasPlaceholder";

export default function EntradasPage() {
  return (
    <Suspense fallback={<div style={{ padding: "48px", textAlign: "center" }}>Cargando módulo de Entradas...</div>}>
      <EntradasPlaceholder />
    </Suspense>
  );
}
