'use client';

import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Elements } from '@stripe/react-stripe-js';
import { AlertCircle, Loader2 } from 'lucide-react';
import BannerPasos from '@/modules/pagos/components/BannerPasos';
import CheckoutForm, { type EstadoPerfil, type PagoExistente } from '@/modules/pagos/components/CheckoutForm';
import OrderSummary from '@/modules/pagos/components/OrderSummary';
import Confirmacion from '@/modules/pagos/components/Confirmacion';
import { ErrorApi, obtenerDatosCheckout, obtenerPerfil, type Destinatario, type Pago } from '@/modules/pagos/api';
import { PEDIDO_DEMO } from '@/modules/pagos/lib/pedido';
import { stripePromise } from '@/modules/pagos/lib/stripe';
import '@/modules/pagos/pagos.css';

type Carga =
  | { estado: 'cargando' }
  | { estado: 'listo'; existente: PagoExistente | null; destinatario?: Destinatario | null }
  | { estado: 'error'; mensaje: string; urlStripe?: string | null };

/**
 * Flujo del módulo de Pagos:
 *   - Con ?id_pago=... (url_checkout que entrega el backend a Entradas): se cobra ese pago existente.
 *   - Sin id_pago: demo con el pedido de ejemplo (el front crea el pago).
 *   Paso 1 (Pago) → datos del comprador (Auth, vía Pagos), "¿Para quién es la entrada?" y formulario
 *   con Stripe Elements. Paso 2 (Confirmación) → resultado del microservicio.
 *   Todas las llamadas van al API Gateway: /api/pagos/**.
 *   El Header y el Footer los pone el layout común de TicketU (src/app/layout.tsx).
 */
export default function CheckoutPage() {
  const pedido = PEDIDO_DEMO;
  const idPago = useSearchParams().get('id_pago');
  const [pago, setPago] = useState<Pago | null>(null);
  const [carga, setCarga] = useState<Carga>(idPago ? { estado: 'cargando' } : { estado: 'listo', existente: null });
  const [perfil, setPerfil] = useState<EstadoPerfil>({ estado: 'cargando' });

  // Sesión y datos del comprador: Pagos los valida con Auth (contrato Auth ↔ Pagos v1.3).
  const pedirPerfil = useCallback(
    () =>
      obtenerPerfil()
        .then((datos) => setPerfil({ estado: 'listo', perfil: datos }))
        .catch((e: unknown) =>
          setPerfil({
            estado: 'error',
            mensaje: e instanceof Error ? e.message : 'Auth no disponible',
            status: e instanceof ErrorApi ? e.status : 0,
          }),
        ),
    [],
  );
  const reintentarPerfil = () => {
    setPerfil({ estado: 'cargando' });
    void pedirPerfil();
  };

  useEffect(() => {
    void pedirPerfil();
  }, [pedirPerfil]);

  useEffect(() => {
    if (!idPago) return;
    let cancelado = false;
    obtenerDatosCheckout(idPago)
      .then((datos) => {
        if (cancelado) return;
        if (datos.estado_pago !== 'PENDIENTE') {
          setPago(datos);
          setCarga({ estado: 'listo', existente: null });
        } else if (!datos.client_secret) {
          setCarga({
            estado: 'error',
            mensaje: 'Este pago se completa en la página de Stripe.',
            urlStripe: datos.url_checkout,
          });
        } else {
          setCarga({
            estado: 'listo',
            existente: {
              id_pago: datos.id_pago,
              id_reserva: datos.id_reserva,
              monto: datos.monto,
              client_secret: datos.client_secret,
            },
            destinatario: datos.destinatario ?? null,
          });
        }
      })
      .catch((e: unknown) => {
        if (!cancelado) setCarga({ estado: 'error', mensaje: e instanceof Error ? e.message : 'No se pudo cargar el pago.' });
      });
    return () => {
      cancelado = true;
    };
  }, [idPago]);

  const existente = carga.estado === 'listo' ? carga.existente : null;
  const destinatarioInicial = carga.estado === 'listo' ? (carga.destinatario ?? null) : null;

  let contenido: React.ReactNode;
  if (pago) {
    contenido = <Confirmacion pago={pago} />;
  } else if (carga.estado === 'cargando') {
    contenido = (
      <div className="flex items-center gap-2 text-ticket-secondary py-16 justify-center">
        <Loader2 className="w-5 h-5 animate-spin" /> Cargando el pago...
      </div>
    );
  } else if (carga.estado === 'error') {
    contenido = (
      <div role="alert" className="flex flex-col gap-3 rounded-xl border border-ticket-peligro bg-ticket-peligro-bg p-6 text-sm text-ticket-peligro">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{carga.mensaje}</span>
        </div>
        {carga.urlStripe && (
          <a href={carga.urlStripe} className="font-semibold underline">
            Ir a pagar en Stripe
          </a>
        )}
      </div>
    );
  } else {
    contenido = (
      <Elements stripe={stripePromise} options={{ locale: 'es' }}>
        <CheckoutForm
          pedido={pedido}
          existente={existente}
          perfil={perfil}
          onReintentarPerfil={reintentarPerfil}
          destinatarioInicial={destinatarioInicial}
          onFinalizado={setPago}
        />
      </Elements>
    );
  }

  return (
    <div className="modulo-pagos flex flex-col bg-ticket-bg">
      <BannerPasos paso={pago ? 2 : 1} />
      {/* Contenido: 1200px máx., grid de 12 columnas, gutters de 24px (fila 13) */}
      <section className="flex-grow w-full max-w-[1200px] mx-auto px-4 md:px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-7 xl:col-span-8">{contenido}</div>
          <div className="lg:col-span-5 xl:col-span-4 sticky top-24">
            <OrderSummary
              pedido={pedido}
              existente={existente ?? (pago ? { id_reserva: pago.id_reserva, monto: pago.monto } : null)}
              cargando={carga.estado === 'cargando' && !pago}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
