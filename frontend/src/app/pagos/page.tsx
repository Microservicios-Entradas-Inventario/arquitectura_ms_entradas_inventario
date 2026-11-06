import { Suspense } from "react";
import CheckoutPage from "@/modules/pagos/components/CheckoutPage";

// Página de "Pagos" — GRUPO 4
//
// Checkout del módulo de Pagos. Entradas redirige aquí con la url_checkout que entrega
// el backend de Pagos: /pagos?id_pago=<id>. Toda la lógica vive en src/modules/pagos/.
//
// useSearchParams (lectura de ?id_pago=) necesita un límite de Suspense en Next.js.

export default function PagosPage() {
  return (
    <Suspense>
      <CheckoutPage />
    </Suspense>
  );
}
