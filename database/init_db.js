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
        nombre_evento: { bsonType: ["string", "null"] },
        fecha_evento: { bsonType: ["string", "null"] },
        hora_evento: { bsonType: ["string", "null"] },
        lugar_ingreso: { bsonType: ["string", "null"] },
        id_usuario: { bsonType: "string" },
        rol_usuario: {
          bsonType: "string",
          enum: ["ORGANIZADOR", "organizador", "STAFF", "staff"]
        },
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
        "nombre_usuario",
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
        hold_id: { bsonType: ["string", "null"] },
        id_evento: { bsonType: "string" },
        id_usuario: { bsonType: "string" },
        nombre_usuario: { bsonType: "string" },
        rut_usuario: { bsonType: ["string", "null"] },
        correo_usuario: { bsonType: ["string", "null"] },
        rol_usuario: {
          bsonType: "string",
          enum: ["CLIENTE", "USUARIO", "STAFF", "ORGANIZADOR", "cliente", "usuario", "staff", "organizador"]
        },
        cantidad_entrada: { bsonType: "int", minimum: 1 },
        id_promocion: { bsonType: ["string", "null"] },
        porcentaje_descuento: { bsonType: "int", minimum: 0, maximum: 100 },
        monto_total: { bsonType: "int", minimum: 0 },
        id_pago: { bsonType: ["string", "null"] },
        cookie_header: { bsonType: ["string", "null"] },
        token_sesion: { bsonType: ["string", "null"] },
        estado_reserva: {
          bsonType: "string",
          enum: ["RESERVADO", "CONSOLIDADO", "EXPIRADO", "RECHAZADO", "CANCELADO"]
        },
        fecha_cancelacion: {
          bsonType: ["date", "null"],
          description: "Fecha de cancelación manual de la reserva"
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
        "nombre_usuario",
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
        id_evento: { bsonType: ["string", "null"] },
        nombre_evento: { bsonType: ["string", "null"] },
        id_usuario: { bsonType: "string" },
        nombre_usuario: { bsonType: "string" },
        rut_usuario: { bsonType: ["string", "null"] },
        correo_usuario: { bsonType: ["string", "null"] },
        rol_usuario: {
          bsonType: "string",
          enum: ["CLIENTE", "USUARIO", "STAFF", "ORGANIZADOR", "cliente", "usuario", "staff", "organizador"]
        },
        tipo_acceso: { bsonType: "string", enum: ["GENERAL"] },
        lugar_ingreso: { bsonType: ["string", "null"] },
        precio_final_pagado: { bsonType: "int", minimum: 0 },
        estado_entrada: { bsonType: "string", enum: ["EMITIDA", "ANULADA"] },
        nombre_archivo_qr: { bsonType: "string" },
        qr_data: { bsonType: ["object", "string"] },
        fecha_emision: { bsonType: "date" }
      }
    }
  }
});

dbRef.entrada.createIndex({ id_entrada: 1 }, { unique: true, name: "pk_entrada_id_entrada" });
dbRef.entrada.createIndex({ id_reserva: 1 }, { name: "fk_entrada_reserva" });

// 4. DATOS SEMILLA PARA DEMOSTRACIÓN E INTEGRACIÓN E2E
const ahora = new Date();
// Vigencia de 7 días para las reservas semilla para evitar que el índice TTL de MongoDB las elimine antes de las pruebas
const expiraEn7Dias = new Date(ahora.getTime() + 7 * 24 * 60 * 60 * 1000);

dbRef.inventario_evento.insertMany([
  {
    id_evento: "evt-77889",
    nombre_evento: "Concierto Sinfonico TicketU",
    fecha_evento: "2026-11-20",
    hora_evento: "20:00",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(10000),
    stock_inicial: NumberInt(150),
    stock_actual: NumberInt(144),
    cantidad_entrada_reservada: NumberInt(5),
    cantidad_entrada_comprada: NumberInt(1),
    maximo_ticket: NumberInt(4),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-002",
    nombre_evento: "Charla Abierta de Innovacion",
    fecha_evento: "2026-11-25",
    hora_evento: "18:30",
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
  },
  {
    id_evento: "evt-101",
    nombre_evento: "Festival Universitario TITEC",
    fecha_evento: "2026-12-05",
    hora_evento: "19:00",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(15000),
    stock_inicial: NumberInt(200),
    stock_actual: NumberInt(200),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(0),
    maximo_ticket: NumberInt(4),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "66f1a0000000000000000002",
    nombre_evento: "Feria de Innovacion TITEC",
    fecha_evento: "2026-12-10",
    hora_evento: "10:00",
    id_usuario: "usr-org-panel",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(10000),
    stock_inicial: NumberInt(300),
    stock_actual: NumberInt(300),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(0),
    maximo_ticket: NumberInt(10),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  }
]);

dbRef.reserva_entrada.insertMany([
  {
    id_reserva: "res-98765",
    id_evento: "evt-77889",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
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
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    cantidad_entrada: NumberInt(1),
    id_promocion: null,
    porcentaje_descuento: NumberInt(0),
    monto_total: NumberInt(10000),
    id_pago: "pay-112234",
    estado_reserva: "RESERVADO",
    fecha_creacion: ahora,
    fecha_expiracion: expiraEn7Dias
  },
  {
    id_reserva: "res-demo-checkin",
    id_evento: "evt-77889",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    cantidad_entrada: NumberInt(1),
    id_promocion: null,
    porcentaje_descuento: NumberInt(0),
    monto_total: NumberInt(10000),
    id_pago: "pay-demo-checkin",
    estado_reserva: "RESERVADO",
    fecha_creacion: ahora,
    fecha_expiracion: expiraEn7Dias
  },
  {
    id_reserva: "res-demo-pagos",
    id_evento: "evt-77889",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    cantidad_entrada: NumberInt(2),
    id_promocion: null,
    porcentaje_descuento: NumberInt(0),
    monto_total: NumberInt(20000),
    id_pago: null,
    estado_reserva: "RESERVADO",
    fecha_creacion: ahora,
    fecha_expiracion: expiraEn7Dias
  },
  {
    id_reserva: "res-demo-cancelar",
    id_evento: "evt-77889",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    cantidad_entrada: NumberInt(1),
    id_promocion: null,
    porcentaje_descuento: NumberInt(0),
    monto_total: NumberInt(10000),
    id_pago: "pay-demo-cancel",
    estado_reserva: "RESERVADO",
    fecha_creacion: ahora,
    fecha_expiracion: expiraEn7Dias
  }
]);

dbRef.entrada.insertMany([
  {
    id_entrada: "tk-998877",
    id_reserva: "res-98765",
    id_evento: "evt-77889",
    nombre_evento: "Concierto Sinfonico TicketU",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    tipo_acceso: "GENERAL",
    lugar_ingreso: "Puerta Principal - Acceso General",
    precio_final_pagado: NumberInt(8500),
    estado_entrada: "EMITIDA",
    nombre_archivo_qr: "tk-998877.png",
    qr_data: {
      url: "https://storage.midominio.com/qr/tk-998877.png",
      hash: "abc1234"
    },
    fecha_emision: ahora
  },
  {
    id_entrada: "tk-demo-001",
    id_reserva: "res-98765",
    id_evento: "evt-002",
    nombre_evento: "Charla Abierta de Innovacion",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    tipo_acceso: "GENERAL",
    lugar_ingreso: "Auditorio Central - Puerta A",
    precio_final_pagado: NumberInt(0),
    estado_entrada: "EMITIDA",
    nombre_archivo_qr: "tk-demo-001.png",
    qr_data: {
      url: "https://storage.midominio.com/qr/tk-demo-001.png",
      hash: "def5678"
    },
    fecha_emision: ahora
  }
]);
