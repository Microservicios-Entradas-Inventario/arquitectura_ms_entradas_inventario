const dbName = "ticketu_entradas_db";
const dbRef = db.getSiblingDB(dbName);

dbRef.inventario_evento.drop();
dbRef.reserva_entrada.drop();
dbRef.entrada.drop();

// 1. COLECCIÓN: inventario_evento
dbRef.createCollection("inventario_evento", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "id_evento",
        "id_usuario",
        "rol_usuario",
        "tipo_entrada",
        "precio_unitario",
        "stock_inicial",
        "stock_actual",
        "cantidad_entrada_reservada",
        "cantidad_entrada_comprada",
        "maximo_ticket",
        "estado_gestion",
        "fecha_actualizacion"
      ],
      additionalProperties: false,
      properties: {
        _id: { bsonType: "objectId" },
        id_evento: { bsonType: "string" },
        id_usuario: { bsonType: "string" },
        rol_usuario: { bsonType: "string", enum: ["ORGANIZADOR"] },
        tipo_entrada: { bsonType: "string", enum: ["PAGADA", "GRATUITA"] },
        precio_unitario: { bsonType: "int", minimum: 0 },
        stock_inicial: { bsonType: "int", minimum: 0 },
        stock_actual: { bsonType: "int", minimum: 0 },
        cantidad_entrada_reservada: { bsonType: "int", minimum: 0 },
        cantidad_entrada_comprada: { bsonType: "int", minimum: 0 },
        maximo_ticket: { bsonType: "int", minimum: 1 },
        estado_gestion: {
          bsonType: "string",
          enum: ["BORRADOR", "PUBLICADO", "FINALIZADO", "CANCELADO", "AGOTADO"]
        },
        fecha_actualizacion: { bsonType: "date" }
      }
    }
  }
});

dbRef.inventario_evento.createIndex({ id_evento: 1 }, { unique: true, name: "pk_inventario_id_evento" });
dbRef.inventario_evento.createIndex({ id_usuario: 1, rol_usuario: 1 }, { name: "idx_inventario_organizador" });

// 2. COLECCIÓN: reserva_entrada
dbRef.createCollection("reserva_entrada", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "id_reserva",
        "id_evento",
        "id_usuario",
        "rol_usuario",
        "cantidad_entrada",
        "id_promocion",
        "porcentaje_descuento",
        "monto_total",
        "id_pago",
        "estado_reserva",
        "fecha_creacion",
        "fecha_expiracion"
      ],
      additionalProperties: false,
      properties: {
        _id: { bsonType: "objectId" },
        id_reserva: { bsonType: "string" },
        id_evento: { bsonType: "string" },
        id_usuario: { bsonType: "string" },
        rol_usuario: { bsonType: "string", enum: ["CLIENTE"] },
        cantidad_entrada: { bsonType: "int", minimum: 1 },
        id_promocion: { bsonType: ["string", "null"] },
        porcentaje_descuento: { bsonType: "int", minimum: 0, maximum: 100 },
        monto_total: { bsonType: "int", minimum: 0 },
        id_pago: { bsonType: ["string", "null"] },
        estado_reserva: {
          bsonType: "string",
          enum: ["RESERVADO", "CONSOLIDADO", "EXPIRADO", "RECHAZADO"]
        },
        fecha_creacion: { bsonType: "date" },
        fecha_expiracion: { bsonType: ["date", "null"] }
      }
    }
  }
});

dbRef.reserva_entrada.createIndex({ id_reserva: 1 }, { unique: true, name: "pk_reserva_id_reserva" });
dbRef.reserva_entrada.createIndex({ id_evento: 1 }, { name: "fk_reserva_inventario_evento" });
dbRef.reserva_entrada.createIndex({ id_usuario: 1, id_evento: 1 }, { name: "idx_reserva_usuario_evento" });
dbRef.reserva_entrada.createIndex({ fecha_expiracion: 1 }, { expireAfterSeconds: 0, name: "ttl_reserva_expiracion" });

// 3. COLECCIÓN: entrada
dbRef.createCollection("entrada", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "id_entrada",
        "id_reserva",
        "id_usuario",
        "rol_usuario",
        "tipo_acceso",
        "precio_final_pagado",
        "estado_entrada",
        "nombre_archivo_qr",
        "qr_data",
        "fecha_emision"
      ],
      additionalProperties: false,
      properties: {
        _id: { bsonType: "objectId" },
        id_entrada: { bsonType: "string" },
        id_reserva: { bsonType: "string" },
        id_usuario: { bsonType: "string" },
        rol_usuario: { bsonType: "string", enum: ["CLIENTE"] },
        tipo_acceso: { bsonType: "string", enum: ["GENERAL"] },
        precio_final_pagado: { bsonType: "int", minimum: 0 },
        estado_entrada: { bsonType: "string", enum: ["EMITIDA", "ANULADA"] },
        nombre_archivo_qr: { bsonType: "string" },
        qr_data: { bsonType: "string" },
        fecha_emision: { bsonType: "date" }
      }
    }
  }
});

dbRef.entrada.createIndex({ id_entrada: 1 }, { unique: true, name: "pk_entrada_id_entrada" });
dbRef.entrada.createIndex({ id_reserva: 1 }, { name: "fk_entrada_reserva" });

// 4. DATOS SEMILLA
const ahora = new Date();
const expiraEn15Min = new Date(ahora.getTime() + 15 * 60 * 1000);

dbRef.inventario_evento.insertMany([
  {
    id_evento: "evt-77889",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(10000),
    stock_inicial: NumberInt(150),
    stock_actual: NumberInt(148),
    cantidad_entrada_reservada: NumberInt(1),
    cantidad_entrada_comprada: NumberInt(1),
    maximo_ticket: NumberInt(4),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-002",
    id_usuario: "usr-org-002",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "GRATUITA",
    precio_unitario: NumberInt(0),
    stock_inicial: NumberInt(100),
    stock_actual: NumberInt(99),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(1),
    maximo_ticket: NumberInt(2),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  }
]);

dbRef.reserva_entrada.insertMany([
  {
    id_reserva: "res-98765",
    id_evento: "evt-77889",
    id_usuario: "usr-12345",
    rol_usuario: "CLIENTE",
    cantidad_entrada: NumberInt(1),
    id_promocion: "promo-estudiante-2026",
    porcentaje_descuento: NumberInt(15),
    monto_total: NumberInt(8500),
    id_pago: "pay-112233",
    estado_reserva: "CONSOLIDADO",
    fecha_creacion: ahora,
    fecha_expiracion: null
  },
  {
    id_reserva: "res-98766",
    id_evento: "evt-77889",
    id_usuario: "usr-54321",
    rol_usuario: "CLIENTE",
    cantidad_entrada: NumberInt(1),
    id_promocion: null,
    porcentaje_descuento: NumberInt(0),
    monto_total: NumberInt(10000),
    id_pago: "pay-112234",
    estado_reserva: "RESERVADO",
    fecha_creacion: ahora,
    fecha_expiracion: expiraEn15Min
  }
]);

dbRef.entrada.insertOne({
  id_entrada: "tk-998877",
  id_reserva: "res-98765",
  id_usuario: "usr-12345",
  rol_usuario: "CLIENTE",
  tipo_acceso: "GENERAL",
  precio_final_pagado: NumberInt(8500),
  estado_entrada: "EMITIDA",
  nombre_archivo_qr: "tk-998877.png",
  qr_data: "[https://storage.midominio.com/qr/tk-998877.png](https://storage.midominio.com/qr/tk-998877.png)",
  fecha_emision: ahora
});
