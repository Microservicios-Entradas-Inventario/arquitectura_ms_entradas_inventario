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

class BrokerService:
    connection = None
    channel = None
    exchange = None
    consumer_task = None
    _is_connected = False

    @classmethod
    async def connect(cls):
        """Inicializa la conexión con RabbitMQ, declara el exchange y la cola propia."""
        try:
            print(f"[RabbitMQ] Conectando a {BROKER_URL}...")
            cls.connection = await aio_pika.connect_robust(
                BROKER_URL,
                timeout=3.0
            )
            cls.channel = await cls.connection.channel()
            # Declarar exchange de tipo topic durable según especificación TicketU
            cls.exchange = await cls.channel.declare_exchange(
                EVENT_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            # Declarar cola durable propia para entradas
            queue = await cls.channel.declare_queue(QUEUE_NAME, durable=True)
            # Enlazar cola a eventos de interés (pago.*, evento.* y eventos de Panel Organizador)
            await queue.bind(cls.exchange, routing_key="pago.*")
            await queue.bind(cls.exchange, routing_key="evento.*")
            await queue.bind(cls.exchange, routing_key="panel.#")
            await queue.bind(cls.exchange, routing_key="panel.evento.entradas.v1")
            
            # Iniciar consumidor en background
            cls.consumer_task = asyncio.create_task(cls._consume(queue))
            cls._is_connected = True
            print(f"[RabbitMQ] Conectado exitosamente. Escuchando en cola '{QUEUE_NAME}'.")
        except Exception as e:
            cls._is_connected = False
            print(f"[RabbitMQ] Advertencia: No se pudo conectar al broker ({e}). La app continuará en modo degradado/HTTP.")

    @classmethod
    async def _consume(cls, queue: aio_pika.abc.AbstractQueue):
        """Bucle consumidor que procesa eventos entrantes y envía ACK."""
        try:
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process(requeue=False):
                        try:
                            body = json.loads(message.body.decode("utf-8"))
                            routing_key = message.routing_key
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
        event_name = envelope.get("eventName") or routing_key
        data = envelope.get("data", {})
        db = get_database()
        if db is None:
            print("[RabbitMQ] Base de datos no disponible para procesar evento.")
            return

        if event_name == "pago.realizado":
            # Consolidar reserva y emitir entrada automáticamente
            id_reserva = data.get("id_reserva") or data.get("pagoId")
            id_pago = data.get("id_pago") or data.get("pagoId", "pay-broker")
            if not id_reserva:
                return

            reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
            if reserva and reserva.get("estado_reserva") == "RESERVADO":
                await db.reserva_entrada.update_one(
                    {"id_reserva": id_reserva},
                    {"$set": {"estado_reserva": "CONSOLIDADO", "id_pago": id_pago}}
                )
                id_evento = reserva["id_evento"]
                cant = reserva.get("cantidad_entrada", 1)
                await db.inventario_evento.update_one(
                    {"id_evento": id_evento},
                    {"$inc": {"cantidad_entrada_reservada": -cant, "cantidad_entrada_comprada": cant}}
                )
                
                # Emitir ticket
                id_entrada = f"tk-{uuid.uuid4().hex[:8]}"
                qr_obj = {
                    "url": f"https://storage.midominio.com/qr/{id_entrada}.png",
                    "hash": uuid.uuid4().hex[:7]
                }
                doc_entrada = {
                    "id_entrada": id_entrada,
                    "id_reserva": id_reserva,
                    "id_usuario": reserva.get("id_usuario", ""),
                    "nombre_usuario": reserva.get("nombre_usuario", "Cliente"),
                    "rol_usuario": "CLIENTE",
                    "tipo_acceso": "GENERAL",
                    "precio_final_pagado": reserva.get("monto_total", 0) // cant,
                    "estado_entrada": "EMITIDA",
                    "nombre_archivo_qr": f"{id_entrada}.png",
                    "qr_data": qr_obj,
                    "fecha_emision": datetime.utcnow()
                }
                await db.entrada.insert_one(doc_entrada)
                print(f"[RabbitMQ - pago.realizado] Entrada '{id_entrada}' emitida exitosamente para reserva '{id_reserva}'.")
                
                # Publicar evento entrada.emitida
                await cls.publish_event("entrada.emitida", {
                    "id_entrada": id_entrada,
                    "id_reserva": id_reserva,
                    "id_evento": id_evento,
                    "id_usuario": reserva.get("id_usuario"),
                    "nombre_usuario": reserva.get("nombre_usuario"),
                    "qr_data": qr_obj
                })

        elif event_name == "pago.rechazado":
            id_reserva = data.get("id_reserva")
            if not id_reserva:
                return
            reserva = await db.reserva_entrada.find_one({"id_reserva": id_reserva})
            if reserva and reserva.get("estado_reserva") == "RESERVADO":
                cant = reserva.get("cantidad_entrada", 1)
                id_evento = reserva["id_evento"]
                await db.reserva_entrada.update_one(
                    {"id_reserva": id_reserva},
                    {"$set": {"estado_reserva": "EXPIRADO"}}
                )
                await db.inventario_evento.update_one(
                    {"id_evento": id_evento},
                    {"$inc": {"stock_actual": cant, "cantidad_entrada_reservada": -cant}}
                )
                print(f"[RabbitMQ - pago.rechazado] Reserva '{id_reserva}' liberada. Se devolvieron {cant} cupos.")

        elif routing_key.startswith("panel.") or event_name in ["evento_creado", "evento_publicado", "evento_actualizado"]:
            # Evento originado desde Panel Organizador (Outbox Pattern)
            payload = envelope.get("payload", data)
            sub_tipo = envelope.get("envelope", {}).get("tipo", event_name)
            id_evt = payload.get("id_evento") or envelope.get("envelope", {}).get("id_evento")

            if id_evt:
                cant = int(payload.get("cantidad_entradas") or 100)
                estado_g = payload.get("estado_gestion", "PUBLICADO").upper()
                if estado_g not in ["BORRADOR", "PUBLICADO", "FINALIZADO", "CANCELADO", "AGOTADO"]:
                    estado_g = "PUBLICADO"
                tipo_e = payload.get("tipo_entrada", "PAGADA").upper()
                if tipo_e not in ["PAGADA", "GRATUITA"]:
                    tipo_e = "PAGADA"
                id_usr = payload.get("id_usuario") or "org-panel"
                precio_u = int(payload.get("precio") or 10000)
                
                evento_existente = await db.inventario_evento.find_one({"id_evento": id_evt})
                if evento_existente:
                    await db.inventario_evento.update_one(
                        {"id_evento": id_evt},
                        {
                            "$set": {
                                "stock_actual": cant,
                                "stock_inicial": cant,
                                "tipo_entrada": tipo_e,
                                "estado_gestion": estado_g,
                                "fecha_actualizacion": datetime.utcnow()
                            }
                        }
                    )
                else:
                    await db.inventario_evento.insert_one({
                        "id_evento": id_evt,
                        "id_usuario": id_usr,
                        "rol_usuario": "ORGANIZADOR",
                        "tipo_entrada": tipo_e,
                        "precio_unitario": precio_u,
                        "stock_inicial": cant,
                        "stock_actual": cant,
                        "cantidad_entrada_reservada": 0,
                        "cantidad_entrada_comprada": 0,
                        "maximo_ticket": 10,
                        "estado_gestion": estado_g,
                        "fecha_actualizacion": datetime.utcnow()
                    })
                print(f"[RabbitMQ - Panel Organizador] Evento '{sub_tipo}' procesado para evento '{id_evt}'. Stock sincronizado a {cant}.")

    @classmethod
    async def publish_event(cls, event_name: str, data: dict):
        """Publica un evento con el sobre estándar acordado para TicketU."""
        if not cls._is_connected or not cls.exchange:
            print(f"[RabbitMQ Mock/Offline] Evento '{event_name}' generado: {data}")
            return

        try:
            envelope = {
                "eventId": str(uuid.uuid4()),
                "eventName": event_name,
                "occurredAt": datetime.utcnow().isoformat(),
                "source": "entradas-service",
                "data": data
            }
            message_body = json.dumps(envelope).encode("utf-8")
            message = aio_pika.Message(
                body=message_body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                timestamp=datetime.utcnow()
            )
            await cls.exchange.publish(message, routing_key=event_name)
            print(f"[RabbitMQ] Evento publicado: '{event_name}' (ID: {envelope['eventId']})")
        except Exception as e:
            print(f"[RabbitMQ] Error publicando evento '{event_name}': {e}")

    @classmethod
    async def close(cls):
        """Cierra el consumidor y la conexión con RabbitMQ."""
        if cls.consumer_task:
            cls.consumer_task.cancel()
        if cls.connection and not cls.connection.is_closed:
            await cls.connection.close()
            print("[RabbitMQ] Conexión cerrada.")
