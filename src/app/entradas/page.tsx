import { Suspense } from "react";
import EntradasPlaceholder from "@/modules/entradas/components/EntradasPlaceholder";

// Página de "Entradas / Inventario" — GRUPO 3
//
// Este archivo debería ser corto: solo importa y compone componentes
// desde src/modules/entradas/. Toda la lógica (llamadas a la API,
// estado, formularios, etc.) vive en esa carpeta, NO acá.

export default function EntradasPage() {
  return (
    <Suspense fallback={<div style={{ padding: "32px", textAlign: "center" }}>Cargando módulo de entradas...</div>}>
      <EntradasPlaceholder />
    </Suspense>
  );
}
