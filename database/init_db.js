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
        descripcion: { bsonType: ["string", "null"] },
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

// 4. DATOS SEMILLA PARA DEMOSTRACIÓN E INTEGRACIÓN E2E (FRONTEND + ENTRADAS + CHECKIN)
const ahora = new Date();
const expiraEn7Dias = new Date(ahora.getTime() + 7 * 24 * 60 * 60 * 1000);

dbRef.inventario_evento.insertMany([
  {
    id_evento: "evt-001",
    nombre_evento: "Gala Aniversario Civil Informatica UV 2026",
    descripcion: "Cena de camaraderia, balance del ano y fiesta de clausura para la comunidad de informatica.",
    fecha_evento: "18 de Noviembre, 2026",
    hora_evento: "20:00 hrs",
    lugar_ingreso: "Salon de Honor, Sede Central UV",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(6000),
    stock_inicial: NumberInt(200),
    stock_actual: NumberInt(74),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(126),
    maximo_ticket: NumberInt(6),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-002",
    nombre_evento: "Torneo eSports Inter-Carreras UV 2026",
    descripcion: "Competencia oficial de videojuegos universitarios. Acceso gratuito para toda la comunidad.",
    fecha_evento: "25 de Noviembre, 2026",
    hora_evento: "14:00 hrs",
    lugar_ingreso: "Laboratorio Central de Computacion, Facultad de Ingenieria",
    id_usuario: "usr-org-002",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "GRATUITA",
    precio_unitario: NumberInt(0),
    stock_inicial: NumberInt(100),
    stock_actual: NumberInt(25),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(75),
    maximo_ticket: NumberInt(2),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-003",
    nombre_evento: "Workshop: Inteligencia Artificial en Microservicios",
    descripcion: "Taller practico intensivo con despliegue de modelos en contenedores Docker.",
    fecha_evento: "05 de Diciembre, 2026",
    hora_evento: "10:30 hrs",
    lugar_ingreso: "Auditorio de Postgrado, Campus Playa Ancha",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "GRATUITA",
    precio_unitario: NumberInt(0),
    stock_inicial: NumberInt(50),
    stock_actual: NumberInt(0),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(50),
    maximo_ticket: NumberInt(1),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-004",
    nombre_evento: "Fiesta Mechona Info 2026",
    descripcion: "Bienvenida oficial a la nueva generacion de estudiantes de ingenieria.",
    fecha_evento: "20 de Noviembre, 2026",
    hora_evento: "22:00 hrs",
    lugar_ingreso: "Centro de Eventos El Canelo",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(4500),
    stock_inicial: NumberInt(300),
    stock_actual: NumberInt(148),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(152),
    maximo_ticket: NumberInt(6),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-77889",
    nombre_evento: "Concierto Sinfonico TicketU",
    descripcion: "Presentacion sinfonica anual en el Teatro Municipal.",
    fecha_evento: "20 de Noviembre, 2026",
    hora_evento: "20:00 hrs",
    lugar_ingreso: "Puerta Principal - Acceso General",
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
    id_evento: "evt-101",
    nombre_evento: "Feria de Innovacion TITEC",
    descripcion: "Muestra anual de proyectos de ingenieria y tecnologia.",
    fecha_evento: "15 de Diciembre, 2026",
    hora_evento: "10:00 hrs",
    lugar_ingreso: "Auditorio Principal UV",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "GRATUITA",
    precio_unitario: NumberInt(0),
    stock_inicial: NumberInt(150),
    stock_actual: NumberInt(150),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(0),
    maximo_ticket: NumberInt(2),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-102",
    nombre_evento: "Fiesta de Generacion Informatica",
    descripcion: "Fiesta de fin de semestre para estudiantes y egresados.",
    fecha_evento: "18 de Diciembre, 2026",
    hora_evento: "22:00 hrs",
    lugar_ingreso: "Centro de Eventos El Huevo",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(5000),
    stock_inicial: NumberInt(300),
    stock_actual: NumberInt(300),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(0),
    maximo_ticket: NumberInt(6),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-103",
    nombre_evento: "Torneo Interescuelas Valorant",
    descripcion: "Campeonato oficial universitario de deportes electronicos.",
    fecha_evento: "22 de Diciembre, 2026",
    hora_evento: "15:00 hrs",
    lugar_ingreso: "Laboratorios de Computacion UV",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(2000),
    stock_inicial: NumberInt(100),
    stock_actual: NumberInt(0),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(100),
    maximo_ticket: NumberInt(4),
    estado_gestion: "AGOTADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-104",
    nombre_evento: "Charla: IA y Etica",
    descripcion: "Conversatorio con academicos invitados sobre IA responsable.",
    fecha_evento: "12 de Diciembre, 2026",
    hora_evento: "17:30 hrs",
    lugar_ingreso: "Sala 204, Edificio de Ingenieria",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "GRATUITA",
    precio_unitario: NumberInt(0),
    stock_inicial: NumberInt(8),
    stock_actual: NumberInt(8),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(0),
    maximo_ticket: NumberInt(2),
    estado_gestion: "PUBLICADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-105",
    nombre_evento: "Congreso de Ciencias Sociales",
    descripcion: "Ponencias y mesas de trabajo sobre investigacion social.",
    fecha_evento: "10 de Septiembre, 2026",
    hora_evento: "09:00 hrs",
    lugar_ingreso: "Aula Magna UV",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(3000),
    stock_inicial: NumberInt(100),
    stock_actual: NumberInt(40),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(60),
    maximo_ticket: NumberInt(4),
    estado_gestion: "FINALIZADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "evt-109",
    nombre_evento: "Charla de Innovacion",
    descripcion: "Innovacion en startups.",
    fecha_evento: "19 de Diciembre, 2026",
    hora_evento: "10:00 hrs",
    lugar_ingreso: "Auditorio C",
    id_usuario: "usr-org-001",
    rol_usuario: "ORGANIZADOR",
    tipo_entrada: "PAGADA",
    precio_unitario: NumberInt(2000),
    stock_inicial: NumberInt(60),
    stock_actual: NumberInt(60),
    cantidad_entrada_reservada: NumberInt(0),
    cantidad_entrada_comprada: NumberInt(0),
    maximo_ticket: NumberInt(4),
    estado_gestion: "CANCELADO",
    fecha_actualizacion: ahora
  },
  {
    id_evento: "66f1a0000000000000000002",
    nombre_evento: "Feria de Innovacion TITEC",
    descripcion: "Exposicion de proyectos de ingenieria de software y arquitectura de microservicios.",
    fecha_evento: "10 de Diciembre, 2026",
    hora_evento: "10:00 hrs",
    lugar_ingreso: "Hall Central Facultad de Ingenieria",
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
      url: "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=tk-998877",
      hash: "abc1234"
    },
    fecha_emision: ahora
  },
  {
    id_entrada: "tk-demo-001",
    id_reserva: "res-98765",
    id_evento: "evt-002",
    nombre_evento: "Torneo eSports Inter-Carreras UV 2026",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    tipo_acceso: "GENERAL",
    lugar_ingreso: "Laboratorio Central de Computacion, Facultad de Ingenieria",
    precio_final_pagado: NumberInt(0),
    estado_entrada: "EMITIDA",
    nombre_archivo_qr: "tk-demo-001.png",
    qr_data: {
      url: "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=tk-demo-001",
      hash: "def5678"
    },
    fecha_emision: ahora
  },
  {
    id_entrada: "tk-DEMO-2026",
    id_reserva: "res-98765",
    id_evento: "evt-001",
    nombre_evento: "Gala Aniversario Civil Informatica UV 2026",
    id_usuario: "usr-12345",
    nombre_usuario: "Sebastian Fuentes",
    rut_usuario: "20.123.456-7",
    correo_usuario: "sebastian.fuentes@ticketu.cl",
    rol_usuario: "CLIENTE",
    tipo_acceso: "GENERAL",
    lugar_ingreso: "Salon de Honor, Sede Central UV",
    precio_final_pagado: NumberInt(6000),
    estado_entrada: "EMITIDA",
    nombre_archivo_qr: "tk-DEMO-2026.png",
    qr_data: {
      url: "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=tk-DEMO-2026",
      hash: "ghi9012"
    },
    fecha_emision: ahora
  }
]);
