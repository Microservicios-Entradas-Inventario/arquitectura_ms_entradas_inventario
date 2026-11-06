import { Suspense } from "react";
import CheckinPlaceholder from "@/modules/checkin/components/CheckinPlaceholder";

export default function CheckinPage() {
  return (
    <Suspense fallback={<div style={{ padding: "48px", textAlign: "center" }}>Cargando módulo de Check-in...</div>}>
      <CheckinPlaceholder />
    </Suspense>
  );
}
