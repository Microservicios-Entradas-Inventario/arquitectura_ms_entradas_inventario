import os
import json
import uuid
import asyncio
from datetime import datetime
import aio_pika
from database import get_database

BROKER_URL = os.getenv("BROKER_URL", "amqp://ticketu:ticketu_dev@localhost:5672/ticketu")
EVENT_EXCHANGE = os.getenv("EVENT_EXCHANGE", "ticketu.events")
QUEUE_NAME = os.getenv("QUEUE_NAME", "entradas.pagos")
RECONNECT_INTERVAL_SECONDS = float(os.getenv("BROKER_RECONNECT_SECONDS", "5.0"))


class BrokerService:
    connection = None
    channel = None
    exchange = None
    entradas_exchange = None
    consumer_task = None
    reconnect_task = None
    _is_connected = False
    _closing = False

    @classmethod
    async def connect(cls):
        """Inicializa la conexión con RabbitMQ; si el broker no está listo, reintenta en segundo plano."""
        cls._closing = False
        conectado = await cls._try_connect()
        if not conectado and not cls._closing:
            cls.reconnect_task = asyncio.create_task(cls._reconnect_loop())

    @classmethod
    async def _try_connect(cls) -> bool:
        broker_url = os.getenv("BROKER_URL", BROKER_URL)
        exchange_name = os.getenv("EVENT_EXCHANGE", EVENT_EXCHANGE)
        queue_name = os.getenv("QUEUE_NAME", QUEUE_NAME)
        try:
            print(f"[RabbitMQ] Conectando al broker...")
            cls.connection = await aio_pika.connect_robust(broker_url, timeout=3.0)
            cls.channel = await cls.connection.channel()
            cls.exchange = await cls.channel.declare_exchange(
                exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            # Exchange requerido por el Contrato v3 de Notificaciones
            cls.entradas_exchange = await cls.channel.declare_exchange(
                "entradas.events",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            queue = await cls.channel.declare_queue(queue_name, durable=True)
            await queue.bind(cls.exchange, routing_key="pago.*")
            await queue.bind(cls.exchange, routing_key="evento.*")
            await queue.bind(cls.exchange, routing_key="panel.evento.entradas.v1")
            try:
                await queue.unbind(cls.exchange, routing_key="panel.#")
            except Exception:
                pass

            cls.consumer_task = asyncio.create_task(cls._consume(queue))
            cls._is_connected = True
            print(f"[RabbitMQ] Conectado exitosamente. Escuchando en cola '{queue_name}'.")
            return True
        except Exception as e:
            cls._is_connected = False
            print(
                f"[RabbitMQ] Advertencia: No se pudo conectar al broker ({e}). Se reintentará automáticamente."
            )
            return False

    @classmethod
    async def _reconnect_loop(cls):
        """Reintenta conectar periódicamente hasta que RabbitMQ esté disponible."""
        while not cls._closing and not cls._is_connected:
            try:
                await asyncio.sleep(RECONNECT_INTERVAL_SECONDS)
                if cls._closing:
                    break
                if await cls._try_connect():
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[RabbitMQ] Reintento fallido: {e}")

    @classmethod
    async def _consume(cls, queue: aio_pika.abc.AbstractQueue):
        """Bucle consumidor que procesa eventos entrantes y envía ACK."""
        try:
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process(requeue=False):
                        try:
                            body = json.loads(message.body.decode("utf-8"))
                            routing_key = message.routing_key or ""
                            print(f"[RabbitMQ] Evento recibido: '{routing_key}'")
                            await cls._handle_event(routing_key, body)
                        except Exception as err:
                            print(f"[RabbitMQ] Error procesando mensaje ({err})")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[RabbitMQ] Error en consumidor: {e}")

    @classmethod
    async def _handle_event(cls, routing_key: str, envelope: dict):
        """Maneja la lógica de negocio según el evento recibido."""
        if not isinstance(envelope, dict):
            return

        event_name = envelope.get("eventName") or envelope.get("tipo") or routing_key
        data = envelope.get("data") if isinstance(envelope.get("data"), dict) else envelope
        db = get_database()
        if db is None:
            print("[RabbitMQ] Base de datos no disponible para procesar evento.")
            return

        if event_name in ("pago.realizado", "pago_realizado"):
            id_reserva = data.get("id_reserva")
            id_pago = data.get("id_pago") or data.get("pagoId")
            destinatario = data.get("destinatario") if isinstance(data.get("destinatario"), dict) else None
            if not id_reserva:
                print("[RabbitMQ - pago.realizado] Mensaje sin id_reserva; descartado.")
                return

            reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
            if reserva and reserva.get("estado_reserva") == "RESERVADO":
                from routers.reservas import consolidar_y_emitir_entradas

                entradas = await consolidar_y_emitir_entradas(
                    db=db,
                    reserva=reserva,
                    id_pago=id_pago,
                    destinatario=destinatario,
                )
                print(
                    f"[RabbitMQ - pago.realizado] Reserva '{id_reserva}' consolidada; {len(entradas)} entrada(s) emitida(s)."
                )

        elif event_name in (
            "pago.rechazado",
            "pago_rechazado",
            "pago.anulado",
            "pago_anulado",
            "pago.reembolsado",
            "pago_reembolsado",
        ):
            id_reserva = data.get("id_reserva")
            if not id_reserva:
                return
            reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
            if reserva and reserva.get("estado_reserva") == "RESERVADO":
                from routers.reservas import liberar_reserva_y_anular_pago

                nuevo_estado = "EXPIRADO" if "rechazado" in event_name else "CANCELADO"
                await liberar_reserva_y_anular_pago(
                    db=db,
                    reserva=reserva,
                    nuevo_estado=nuevo_estado,
                    anular_en_pagos=False,
                )
                print(
                    f"[RabbitMQ - {event_name}] Reserva '{id_reserva}' liberada y stock restaurado."
                )

        elif routing_key == "panel.evento.entradas.v1" or (
            not routing_key.startswith("panel.")
            and event_name
            in (
                "evento_creado",
                "evento_publicado",
                "evento_actualizado",
                "evento_eliminado",
                "evento_cancelado",
                "evento.creado",
                "evento.publicado",
                "evento.actualizado",
                "evento.eliminado",
                "evento.cancelado",
            )
        ):
            # Evento originado desde Panel Organizador para Entradas (Outbox Pattern)
            payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else data
            env_meta = envelope.get("envelope") if isinstance(envelope.get("envelope"), dict) else {}
            sub_tipo = str(env_meta.get("tipo") or event_name).replace(".", "_")
            id_evt = payload.get("id_evento") or env_meta.get("id_evento")

            if not id_evt:
                return

            if sub_tipo == "evento_eliminado":
                await db.inventario_evento.delete_one({"id_evento": id_evt})
                print(f"[RabbitMQ - Panel Organizador] Evento '{id_evt}' eliminado del inventario.")
                return

            raw_cant = payload.get("cantidad_entradas")
            cant = max(0, int(raw_cant)) if raw_cant is not None else None

            estado_g = str(payload.get("estado_gestion") or "PUBLICADO").upper()
            if sub_tipo == "evento_cancelado":
                estado_g = "CANCELADO"
            if estado_g not in ("BORRADOR", "PUBLICADO", "FINALIZADO", "CANCELADO"):
                estado_g = "PUBLICADO"

            raw_tipo = payload.get("tipo_entrada")
            tipo_e = str(raw_tipo).upper() if raw_tipo is not None else None
            if tipo_e not in ("PAGADA", "GRATUITA"):
                tipo_e = None

            id_usr = payload.get("id_usuario")
            raw_precio = payload.get("precio")

            campos_meta = {}
            if payload.get("nombre_evento"):
                campos_meta["nombre_evento"] = str(payload["nombre_evento"])
            if payload.get("descripcion") is not None:
                campos_meta["descripcion"] = str(payload["descripcion"])
            if payload.get("fecha_evento"):
                campos_meta["fecha_evento"] = str(payload["fecha_evento"])
            if payload.get("hora_evento"):
                campos_meta["hora_evento"] = str(payload["hora_evento"])
            lugar = payload.get("direccion_evento") or payload.get("lugar_ingreso")
            if lugar:
                campos_meta["lugar_ingreso"] = str(lugar)

            evento_existente = await db.inventario_evento.find_one({"id_evento": id_evt})
            if evento_existente:
                set_fields = {
                    **campos_meta,
                    "estado_gestion": estado_g,
                    "fecha_actualizacion": datetime.utcnow(),
                }
                if cant is not None:
                    vendidas = int(evento_existente.get("cantidad_entrada_comprada", 0))
                    reservadas = int(evento_existente.get("cantidad_entrada_reservada", 0))
                    set_fields["stock_inicial"] = cant
                    set_fields["stock_actual"] = max(cant - vendidas - reservadas, 0)
                if tipo_e is not None:
                    set_fields["tipo_entrada"] = tipo_e
                    set_fields["precio_unitario"] = 0 if tipo_e == "GRATUITA" else max(0, int(raw_precio or 0))
                elif raw_precio is not None:
                    set_fields["precio_unitario"] = max(0, int(raw_precio))
                if id_usr:
                    set_fields["id_usuario"] = id_usr

                await db.inventario_evento.update_one(
                    {"id_evento": id_evt},
                    {"$set": set_fields},
                )
            else:
                stock_ini = cant if cant is not None else 100
                tipo_final = tipo_e or "PAGADA"
                precio_final = 0 if tipo_final == "GRATUITA" else max(0, int(raw_precio or 0))
                await db.inventario_evento.insert_one(
                    {
                        "id_evento": id_evt,
                        **campos_meta,
                        "id_usuario": id_usr or "org-panel",
                        "rol_usuario": "organizador",
                        "tipo_entrada": tipo_final,
                        "precio_unitario": precio_final,
                        "stock_inicial": stock_ini,
                        "stock_actual": stock_ini,
                        "cantidad_entrada_reservada": 0,
                        "cantidad_entrada_comprada": 0,
                        "maximo_ticket": 6,
                        "estado_gestion": estado_g,
                        "fecha_actualizacion": datetime.utcnow(),
                    }
                )
            print(
                f"[RabbitMQ - Panel Organizador] Evento '{sub_tipo}' procesado para '{id_evt}'. Stock inicial={cant}, estado={estado_g}."
            )

    @classmethod
    async def publish_event(cls, event_name: str, data: dict) -> bool:
        """Publica un evento con el sobre estándar acordado para TicketU."""
        if not cls._is_connected or not cls.exchange:
            print(f"[RabbitMQ Offline] Evento '{event_name}' no publicado (broker sin conexión): {data}")
            return False

        try:
            envelope = {
                "eventId": str(uuid.uuid4()),
                "eventName": event_name,
                "occurredAt": datetime.utcnow().isoformat(),
                "source": "entradas-service",
                "data": data,
            }
            message_body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            message = aio_pika.Message(
                body=message_body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                timestamp=datetime.utcnow(),
            )
            await cls.exchange.publish(message, routing_key=event_name)
            print(f"[RabbitMQ] Evento publicado: '{event_name}' (ID: {envelope['eventId']})")
            return True
        except Exception as e:
            print(f"[RabbitMQ] Error publicando evento '{event_name}': {e}")
            return False

    @classmethod
    async def publish_notificaciones(cls, payload: dict) -> bool:
        """Publica el evento plano 'entradas_emitidas' en el exchange 'entradas.events' (Contrato v3)."""
        if not cls._is_connected or not cls.entradas_exchange:
            print(f"[RabbitMQ Offline] Evento 'entradas_emitidas' no publicado (broker sin conexión).")
            return False

        try:
            message_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            message = aio_pika.Message(
                body=message_body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                timestamp=datetime.utcnow(),
            )
            await cls.entradas_exchange.publish(message, routing_key="entradas_emitidas")
            print(
                f"[RabbitMQ - entradas.events] Evento 'entradas_emitidas' publicado para {payload.get('correo_comprador')}"
            )
            return True
        except Exception as e:
            print(f"[RabbitMQ] Error publicando en 'entradas.events': {e}")
            return False

    @classmethod
    async def close(cls):
        """Cierra el consumidor, reintentos y la conexión con RabbitMQ."""
        cls._closing = True
        if cls.reconnect_task:
            cls.reconnect_task.cancel()
            cls.reconnect_task = None
        if cls.consumer_task:
            cls.consumer_task.cancel()
            cls.consumer_task = None
        if cls.connection and not cls.connection.is_closed:
            await cls.connection.close()
            print("[RabbitMQ] Conexión cerrada.")
        cls._is_connected = False
