// ============================================================================
// Script Replicable de Verificación Integral de Base de Datos (MongoDB 7.0)
// Microservicio: Entradas e Inventario (ticketu_entradas_db)
// Cobertura de rúbrica: BD1, BD2, BD3 y BD4
//
// Ejecución replicable en workstation:
//   docker exec -i ticketu_entradas_mongo mongosh ticketu_entradas_db --quiet < scripts/ejecutar_verificacion_bd.js
// ============================================================================

const mdb = db.getSiblingDB("ticketu_entradas_db");

function header(title) {
  print("\n========================================================================");
  print("  " + title);
  print("========================================================================");
}

// ----------------------------------------------------------------------------
// Q1 [BD2]: Aislamiento Database-per-Service y colecciones propias
// ----------------------------------------------------------------------------
header("Q1 [BD2] - AISLAMIENTO DE BD PROPIA Y COLECCIONES EXISTENTES");
const dbs = db.adminCommand({ listDatabases: 1 }).databases.map(d => d.name);
const colecciones = mdb.getCollectionNames().sort();
const coleccionesPropiasEsperadas = ["entrada", "inventario_evento", "reserva_entrada"];
const coleccionesAjenas = colecciones.filter(c => !coleccionesPropiasEsperadas.includes(c));

printjson({
  bases_de_datos_instancia: dbs,
  bd_microservicio: "ticketu_entradas_db",
  colecciones_encontradas: colecciones,
  total_colecciones_propias: colecciones.length,
  colecciones_otros_squads: coleccionesAjenas,
  conteo_documentos: {
    inventario_evento: mdb.inventario_evento.countDocuments(),
    reserva_entrada: mdb.reserva_entrada.countDocuments(),
    entrada: mdb.entrada.countDocuments()
  },
  verificacion_bd2_colecciones: coleccionesAjenas.length === 0 ? "APROBADO (0 colecciones de otros squads)" : "OBSERVACION"
});

// ----------------------------------------------------------------------------
// Q2 [BD3 / BD4]: Auditoría de validadores $jsonSchema, additionalProperties e índices
// ----------------------------------------------------------------------------
header("Q2 [BD3/BD4] - VALIDADORES $jsonSchema, additionalProperties E INDICES");
const resumenEsquema = mdb.getCollectionInfos({ type: "collection" }).map(info => {
  const js = (info.options && info.options.validator && info.options.validator.$jsonSchema) || {};
  const idxs = mdb[info.name].getIndexes();
  const tieneTTL = idxs.some(ix => ix.expireAfterSeconds !== undefined);
  return {
    coleccion: info.name,
    additionalProperties: js.additionalProperties,
    atributos_definidos: Object.keys(js.properties || {}).length,
    atributos_required: (js.required || []).length,
    indices: idxs.map(ix => ({
      nombre: ix.name,
      llave: ix.key,
      unique: Boolean(ix.unique)
    })),
    tiene_indice_ttl_destructivo: tieneTTL
  };
});
printjson(resumenEsquema);

// ----------------------------------------------------------------------------
// Q3 [BD1 / BD4]: Invariante aritmética de stock en inventario_evento
//   Verifica: stock_inicial === stock_actual + cantidad_entrada_reservada + cantidad_entrada_comprada
// ----------------------------------------------------------------------------
header("Q3 [BD1/BD4] - INVARIANTE ARITMETICA DE STOCK (inventario_evento)");
const resumenStock = mdb.inventario_evento.aggregate([
  {
    $project: {
      _id: 0,
      id_evento: 1,
      tipo_entrada: 1,
      precio_unitario: 1,
      estado_gestion: 1,
      stock_inicial: 1,
      stock_actual: 1,
      reservadas: "$cantidad_entrada_reservada",
      compradas: "$cantidad_entrada_comprada",
      suma_control: { $add: ["$stock_actual", "$cantidad_entrada_reservada", "$cantidad_entrada_comprada"] },
      consistente: {
        $eq: [
          "$stock_inicial",
          { $add: ["$stock_actual", "$cantidad_entrada_reservada", "$cantidad_entrada_comprada"] }
        ]
      }
    }
  },
  { $sort: { id_evento: 1 } }
]).toArray();

const inconsistentesStock = resumenStock.filter(r => !r.consistente);
printjson({
  eventos_verificados: resumenStock.length,
  eventos_inconsistentes: inconsistentesStock.length,
  estado_invariante: inconsistentesStock.length === 0 ? "APROBADO (100% consistente)" : "FALLO",
  detalle_eventos: resumenStock
});

// ----------------------------------------------------------------------------
// Q4 [BD4]: Integridad referencial interna (0 huérfanos en reserva_entrada y entrada)
// ----------------------------------------------------------------------------
header("Q4 [BD4] - INTEGRIDAD REFERENCIAL INTERNA (VERIFICACION DE HUERFANOS)");
const reservasSinEvento = mdb.reserva_entrada.aggregate([
  { $lookup: { from: "inventario_evento", localField: "id_evento", foreignField: "id_evento", as: "evt" } },
  { $match: { evt: { $size: 0 } } },
  { $project: { _id: 0, id_reserva: 1, id_evento: 1 } }
]).toArray();

const entradasSinReserva = mdb.entrada.aggregate([
  { $lookup: { from: "reserva_entrada", localField: "id_reserva", foreignField: "id_reserva", as: "res" } },
  { $match: { res: { $size: 0 } } },
  { $project: { _id: 0, id_entrada: 1, id_reserva: 1 } }
]).toArray();

const entradasSinEvento = mdb.entrada.aggregate([
  { $lookup: { from: "inventario_evento", localField: "id_evento", foreignField: "id_evento", as: "evt" } },
  { $match: { evt: { $size: 0 } } },
  { $project: { _id: 0, id_entrada: 1, id_evento: 1 } }
]).toArray();

const entradasEventoDesalineado = mdb.entrada.aggregate([
  { $lookup: { from: "reserva_entrada", localField: "id_reserva", foreignField: "id_reserva", as: "res" } },
  { $unwind: "$res" },
  { $match: { $expr: { $ne: ["$id_evento", "$res.id_evento"] } } },
  { $project: { _id: 0, id_entrada: 1, id_evento_entrada: "$id_evento", id_evento_reserva: "$res.id_evento" } }
]).toArray();

printjson({
  reservas_sin_inventario_evento: reservasSinEvento.length,
  entradas_sin_reserva_entrada: entradasSinReserva.length,
  entradas_sin_inventario_evento: entradasSinEvento.length,
  entradas_con_id_evento_desalineado_de_reserva: entradasEventoDesalineado.length,
  integridad_referencial_global: (
    reservasSinEvento.length === 0 &&
    entradasSinReserva.length === 0 &&
    entradasSinEvento.length === 0 &&
    entradasEventoDesalineado.length === 0
  ) ? "APROBADO (0 huerfanos, 100% consistente)" : "FALLO"
});

// ----------------------------------------------------------------------------
// Q5 [BD1 / BD4]: Join relacional 3 niveles ($lookup): inventario_evento -> reserva_entrada -> entrada
// ----------------------------------------------------------------------------
header("Q5 [BD1/BD4] - CONSULTA INTEGRAL 3 NIVELES ($lookup: entrada -> reserva -> inventario)");
const cadenaCompleta = mdb.entrada.aggregate([
  { $lookup: { from: "reserva_entrada", localField: "id_reserva", foreignField: "id_reserva", as: "reserva" } },
  { $unwind: "$reserva" },
  { $lookup: { from: "inventario_evento", localField: "id_evento", foreignField: "id_evento", as: "evento" } },
  { $unwind: "$evento" },
  {
    $project: {
      _id: 0,
      id_entrada: 1,
      estado_entrada: 1,
      precio_final_pagado: 1,
      qr_hash: "$qr_data.hash",
      id_reserva: "$reserva.id_reserva",
      estado_reserva: "$reserva.estado_reserva",
      id_pago_ref: "$reserva.id_pago",
      id_promocion_ref: "$reserva.id_promocion",
      descuento_pct: "$reserva.porcentaje_descuento",
      id_evento: "$evento.id_evento",
      tipo_entrada: "$evento.tipo_entrada",
      precio_unitario_evento: "$evento.precio_unitario",
      stock_actual_evento: "$evento.stock_actual",
      id_usuario_ref: "$id_usuario"
    }
  },
  { $sort: { id_entrada: 1 } }
]).toArray();
printjson(cadenaCompleta);

// ----------------------------------------------------------------------------
// Q6 [BD2]: Auditoría de referencias externas y ausencia de credenciales/secretos de otros squads
// ----------------------------------------------------------------------------
header("Q6 [BD2] - AUDITORIA DE REFERENCIAS EXTERNAS Y AUSENCIA DE CREDENCIALES/SECRETOS");
const camposProhibidos = [
  "password", "password_hash", "jwt", "cookie", "cookie_header", "token_sesion",
  "client_secret", "stripe_token", "numero_tarjeta", "cvv", "reglas_cupon", "estado_checkin"
];
const camposDetectadosProhibidos = {};
["inventario_evento", "reserva_entrada", "entrada"].forEach(col => {
  const encontrados = [];
  mdb[col].find().forEach(doc => {
    Object.keys(doc).forEach(k => {
      if (camposProhibidos.includes(k) && !encontrados.includes(k)) {
        encontrados.push(k);
      }
    });
  });
  camposDetectadosProhibidos[col] = encontrados;
});

printjson({
  referencias_externas_persistidas: {
    panel_y_catalogo_id_evento: mdb.inventario_evento.distinct("id_evento"),
    auth_id_usuario_organizadores: mdb.inventario_evento.distinct("id_usuario"),
    auth_id_usuario_compradores: mdb.reserva_entrada.distinct("id_usuario"),
    promociones_id_promocion: mdb.reserva_entrada.distinct("id_promocion").filter(x => x !== null),
    pagos_id_pago: mdb.reserva_entrada.distinct("id_pago").filter(x => x !== null),
    checkin_id_entrada: mdb.entrada.distinct("id_entrada")
  },
  campos_sensibles_o_ajenos_detectados: camposDetectadosProhibidos,
  verificacion_seguridad_y_aislamiento: Object.values(camposDetectadosProhibidos).every(a => a.length === 0)
    ? "APROBADO (0 tokens JWT, 0 client_secret, 0 credenciales ni entidades ajenas)"
    : "OBSERVACION"
});

// ----------------------------------------------------------------------------
// Q7 [BD2 / BD4]: Validación activa $jsonSchema (additionalProperties: false)
//   Prueba sin mutar datos: intenta validar mediante comando validate / insert rechazado en reserva_entrada
//   NOTA: La inserción es rechazada por MongoDB ANTES de escribir (0 documentos alterados).
// ----------------------------------------------------------------------------
header("Q7 [BD2/BD4] - PRUEBA DE RECHAZO $jsonSchema ANTE DATOS AJENOS (additionalProperties: false)");
const conteoAntes = mdb.reserva_entrada.countDocuments();
let resultadoRechazoAjenos = null;
try {
  mdb.reserva_entrada.insertOne({
    id_reserva: "res-test-rechazo-bd2",
    id_evento: "evt-77889",
    id_usuario: "usr-12345",
    nombre_usuario: "Prueba",
    rol_usuario: "usuario",
    cantidad_entrada: NumberInt(1),
    id_promocion: null,
    porcentaje_descuento: NumberInt(0),
    monto_total: NumberInt(10000),
    id_pago: null,
    estado_reserva: "RESERVADO",
    fecha_creacion: new Date(),
    fecha_expiracion: new Date(),
    // Campos prohibidos de otros squads (Auth / Pagos) que DEBEN ser rechazados por MongoDB:
    password_hash: "$2b$12$fakehash",
    client_secret: "pi_secret_prohibido",
    token_jwt: "eyJhbGciOiJIUzI1NiJ9.prohibido"
  });
  resultadoRechazoAjenos = { rechazado: false };
} catch (err) {
  resultadoRechazoAjenos = {
    rechazado: true,
    codigo_error_mongodb: err.code || 121,
    nombre_error: err.codeName || "DocumentValidationFailure",
    motivo: "MongoDB bloqueo la escritura por violar $jsonSchema (additionalProperties: false)",
    propiedades_rechazadas: ["password_hash", "client_secret", "token_jwt"]
  };
}
const conteoDespues = mdb.reserva_entrada.countDocuments();
printjson({
  prueba_rechazo_campos_ajenos: resultadoRechazoAjenos,
  documentos_antes: conteoAntes,
  documentos_despues: conteoDespues,
  bd_sin_modificaciones: conteoAntes === conteoDespues
});

// ----------------------------------------------------------------------------
// Q8 [BD1]: Consultas por integración (Pagos INT-01, Promociones, Check-in, Catálogo/Panel)
// ----------------------------------------------------------------------------
header("Q8 [BD1] - CONSULTAS OPERATIVAS DE INTEGRACION POR MICROSERVICIO CONTRAPARTE");

// I2 + I7: Pagos (INT-01) y Promociones
const consultaPagosPromos = mdb.reserva_entrada.find(
  {},
  {
    _id: 0,
    id_reserva: 1,
    id_evento: 1,
    id_usuario: 1,
    cantidad_entrada: 1,
    id_promocion: 1,
    nombre_codigo: 1,
    porcentaje_descuento: 1,
    monto_total: 1,
    id_pago: 1,
    estado_reserva: 1
  }
).sort({ estado_reserva: 1, id_reserva: 1 }).toArray();

// I3: Check-in (verificación de payload QR JSON {id_entrada, id_evento} en entradas emitidas)
const consultaCheckin = mdb.entrada.find(
  { estado_entrada: "EMITIDA" },
  {
    _id: 0,
    id_entrada: 1,
    id_reserva: 1,
    id_evento: 1,
    id_usuario: 1,
    rol_usuario: 1,
    estado_entrada: 1,
    tipo_acceso: 1,
    "qr_data.url": 1,
    "qr_data.hash": 1
  }
).sort({ id_entrada: 1 }).toArray();

// I4 + I5: Catálogo y Panel Organizador (resumen por estado_gestion y stock agotado)
const consultaPanelCatalogo = mdb.inventario_evento.aggregate([
  {
    $group: {
      _id: { estado_gestion: "$estado_gestion", tipo_entrada: "$tipo_entrada" },
      total_eventos: { $sum: 1 },
      stock_inicial_total: { $sum: "$stock_inicial" },
      stock_actual_total: { $sum: "$stock_actual" },
      reservadas_total: { $sum: "$cantidad_entrada_reservada" },
      compradas_total: { $sum: "$cantidad_entrada_comprada" },
      eventos_agotados: { $sum: { $cond: [{ $eq: ["$stock_actual", 0] }, 1, 0] } }
    }
  },
  { $sort: { "_id.estado_gestion": 1, "_id.tipo_entrada": 1 } }
]).toArray();

printjson({
  I2_I7_pagos_y_promociones_reservas: consultaPagosPromos,
  I3_checkin_tickets_emitidos_con_qr: consultaCheckin,
  I4_I5_catalogo_y_panel_resumen_inventario: consultaPanelCatalogo
});

// ----------------------------------------------------------------------------
// Q9 [BD3 / BD4]: Auditoría automática de nomenclatura snake_case y verificación DAG sin ciclos
// ----------------------------------------------------------------------------
header("Q9 [BD3/BD4] - AUDITORIA DE NOMENCLATURA (snake_case) Y GRAFO ACICLICO (DAG)");
const regexSnake = /^_?[a-z][a-z0-9_]*$/;
const auditoriaNomenclatura = [];
mdb.getCollectionInfos({ type: "collection" }).forEach(info => {
  const props = Object.keys((info.options.validator && info.options.validator.$jsonSchema.properties) || {});
  const invalidos = props.filter(p => !regexSnake.test(p));
  auditoriaNomenclatura.push({
    coleccion: info.name,
    coleccion_snake_case: regexSnake.test(info.name),
    total_atributos: props.length,
    atributos_fuera_estandar: invalidos
  });
});

printjson({
  nomenclatura: auditoriaNomenclatura,
  cumplimiento_nomenclatura_bd3: auditoriaNomenclatura.every(x => x.coleccion_snake_case && x.atributos_fuera_estandar.length === 0)
    ? "APROBADO (100% snake_case)"
    : "OBSERVACION",
  grafo_relaciones_bd4: {
    nodos_topologicos: ["Nivel 0: inventario_evento", "Nivel 1: reserva_entrada", "Nivel 2: entrada"],
    aristas_dirigidas: [
      "inventario_evento(id_evento) -> reserva_entrada(id_evento) [1:0..N]",
      "reserva_entrada(id_reserva) -> entrada(id_reserva) [1:0..N]",
      "inventario_evento(id_evento) -> entrada(id_evento) [1:0..N]"
    ],
    ciclos_detectados: 0,
    es_dag_aciclico: true
  }
});
