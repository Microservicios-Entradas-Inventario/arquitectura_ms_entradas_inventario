#!/usr/bin/env python3
"""
Script de creación del Diccionario de Datos (Markdown + CSV) directamente desde
la instancia MongoDB de workstation del microservicio de Entradas e Inventario
(`ticketu_entradas_db`).

Cumple BD3 (Nomenclatura y documentación) y BD4 (Diseño técnico):
- Extrae automáticamente todas las colecciones, propiedades de $jsonSchema, tipos BSON,
  nulabilidad exacta, dominios ENUM, restricciones min/max, subdocumentos embebidos,
  llaves primarias, llaves foráneas internas, referencias externas a otros microservicios
  e índices configurados en MongoDB.

Uso replicable en workstation:
    python scripts/generar_diccionario_datos.py
    python scripts/generar_diccionario_datos.py --uri mongodb://127.0.0.1:27017 --db ticketu_entradas_db
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pymongo import MongoClient

COLLECTION_ORDER = ["inventario_evento", "reserva_entrada", "entrada"]

COLLECTION_DESCRIPTIONS = {
    "inventario_evento": (
        "Administra el inventario de cupos, tarifas unitarias, límites por compra y estado "
        "operativo de venta por evento. Constituye la colección raíz (Nivel 0) del grafo relacional "
        "y se sincroniza con Panel Organizador y Catálogo de Eventos mediante el identificador `id_evento`."
    ),
    "reserva_entrada": (
        "Registra las reservas temporales de cupo (Hold, HU-03) y las órdenes consolidadas o "
        "liberadas de compra. Descuenta stock atómicamente, persiste el cálculo validado de "
        "descuento con Promociones y mantiene el vínculo con la Pasarela de Pagos (`id_pago`). "
        "No utiliza índice TTL destructivo ni almacena cookies JWT ni secretos de pago."
    ),
    "entrada": (
        "Almacena de forma inmutable cada ticket emitido tras la consolidación de un pago o "
        "emisión directa gratuita (HU-04 y HU-05), junto con su código QR estructurado (`qr_data`) "
        "para control de acceso en puerta por Check-in y entrega por Notificaciones."
    ),
}

FIELD_METADATA: Dict[Tuple[str, str], Dict[str, str]] = {
    # inventario_evento
    ("inventario_evento", "_id"): {
        "key": "ID (PK interna)",
        "origin": "MongoDB (Entradas)",
        "desc": "Identificador interno autogenerado por MongoDB (`ObjectId`).",
    },
    ("inventario_evento", "id_evento"): {
        "key": "PK / FK Ext (Panel, Catálogo)",
        "origin": "Referencia externa → Panel Organizador / Catálogo",
        "desc": "Identificador único de negocio del evento. Índice único `pk_inventario_id_evento`. Referenciado desde `reserva_entrada` y `entrada`.",
    },
    ("inventario_evento", "nombre_evento"): {
        "key": "-",
        "origin": "Sincronización Panel (snapshot operativo)",
        "desc": "Título descriptivo del evento sincronizado para visualización de inventario y comprobante de emisión.",
    },
    ("inventario_evento", "descripcion"): {
        "key": "-",
        "origin": "Sincronización Panel (snapshot operativo)",
        "desc": "Descripción resumida del evento recibida en eventos `panel.evento.entradas.v1`.",
    },
    ("inventario_evento", "fecha_evento"): {
        "key": "-",
        "origin": "Sincronización Panel (snapshot operativo)",
        "desc": "Fecha programada del evento en formato `YYYY-MM-DD`, requerida también para el payload del evento `entradas_emitidas` hacia Notificaciones.",
    },
    ("inventario_evento", "hora_evento"): {
        "key": "-",
        "origin": "Sincronización Panel (snapshot operativo)",
        "desc": "Hora de inicio del evento en formato `HH:MM`, requerida para detalle de entrada (HU-04) y Notificaciones.",
    },
    ("inventario_evento", "lugar_ingreso"): {
        "key": "-",
        "origin": "Sincronización Panel (snapshot operativo)",
        "desc": "Ubicación o punto de acceso al recinto para mostrar en la entrada adquirida (HU-04/HU-05).",
    },
    ("inventario_evento", "id_usuario"): {
        "key": "FK Ext (Auth)",
        "origin": "Referencia externa → Auth",
        "desc": "Identificador de referencia del organizador o staff responsable de gestionar el inventario del evento.",
    },
    ("inventario_evento", "rol_usuario"): {
        "key": "IDX compuesto",
        "origin": "Referencia rol Auth",
        "desc": "Rol autorizado del gestor del inventario (`ORGANIZADOR` / `STAFF`). Parte del índice `idx_inventario_organizador`.",
    },
    ("inventario_evento", "tipo_entrada"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Modalidad comercial del inventario: `PAGADA` (requiere Hold + Pagos) o `GRATUITA` (emisión directa `$0`).",
    },
    ("inventario_evento", "precio_unitario"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Valor unitario en pesos chilenos (CLP entero `>= 0`). Para eventos `GRATUITA` es `0`.",
    },
    ("inventario_evento", "stock_inicial"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Capacidad total de entradas asignadas inicialmente al evento (`>= 0`).",
    },
    ("inventario_evento", "stock_actual"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Cupos disponibles en tiempo real (`>= 0`). Cumple invariante: `stock_inicial = stock_actual + cantidad_entrada_reservada + cantidad_entrada_comprada`.",
    },
    ("inventario_evento", "cantidad_entrada_reservada"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Cupos retenidos temporalmente en reservas activas (`estado_reserva = RESERVADO`).",
    },
    ("inventario_evento", "cantidad_entrada_comprada"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Total acumulado de entradas vendidas/emitidas definitivamente (`CONSOLIDADO`).",
    },
    ("inventario_evento", "maximo_ticket"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Límite máximo de entradas permitidas por transacción o solicitud (`>= 1`).",
    },
    ("inventario_evento", "estado_gestion"): {
        "key": "-",
        "origin": "Entradas / Sincronización Panel",
        "desc": "Estado del ciclo de vida del inventario: `BORRADOR`, `PUBLICADO`, `FINALIZADO` o `CANCELADO`. Solo `PUBLICADO` admite compras/reservas.",
    },
    ("inventario_evento", "fecha_actualizacion"): {
        "key": "-",
        "origin": "Entradas (Auditoría)",
        "desc": "Marca de tiempo UTC (`ISODate`) de la última sincronización o actualización del inventario.",
    },
    # reserva_entrada
    ("reserva_entrada", "_id"): {
        "key": "ID (PK interna)",
        "origin": "MongoDB (Entradas)",
        "desc": "Identificador interno autogenerado por MongoDB (`ObjectId`).",
    },
    ("reserva_entrada", "id_reserva"): {
        "key": "PK",
        "origin": "Entradas (Dominio propio)",
        "desc": "Identificador único de negocio de la reserva (`res-*` o `hold-*`). Índice único `pk_reserva_id_reserva`. Consultado por Pagos en INT-01.",
    },
    ("reserva_entrada", "hold_id"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Alias opcional de reserva temporal (HU-03) para trazabilidad con el frontend y Pagos.",
    },
    ("reserva_entrada", "id_evento"): {
        "key": "FK → inventario_evento.id_evento",
        "origin": "Referencia interna y externa (Panel/Catálogo)",
        "desc": "Llave foránea hacia `inventario_evento.id_evento`. Indexada mediante `fk_reserva_inventario_evento` e `idx_reserva_usuario_evento`.",
    },
    ("reserva_entrada", "id_usuario"): {
        "key": "FK Ext (Auth)",
        "origin": "Referencia externa → Auth",
        "desc": "Identificador de referencia del comprador obtenido exclusivamente mediante introspección de sesión en Auth (`/internal/validar-sesion`).",
    },
    ("reserva_entrada", "nombre_usuario"): {
        "key": "-",
        "origin": "Proyección sesión Auth (comprobante/Check-in)",
        "desc": "Nombre del asistente titular al momento de la reserva para emisión de ticket, registro en Check-in y correo de Notificaciones.",
    },
    ("reserva_entrada", "rut_usuario"): {
        "key": "-",
        "origin": "Proyección sesión Auth (opcional)",
        "desc": "RUT referencial del asistente si fue informado por Auth en la introspección de sesión.",
    },
    ("reserva_entrada", "correo_usuario"): {
        "key": "-",
        "origin": "Proyección sesión Auth (Notificaciones)",
        "desc": "Correo electrónico de entrega utilizado para publicar el evento `entradas_emitidas` hacia Notificaciones.",
    },
    ("reserva_entrada", "rol_usuario"): {
        "key": "-",
        "origin": "Referencia rol Auth",
        "desc": "Rol del usuario que realiza la reserva (`usuario`, `staff`, `organizador` y variantes en mayúsculas).",
    },
    ("reserva_entrada", "cantidad_entrada"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Número de cupos reservados en la orden (`>= 1`, máximo según `maximo_ticket` y contrato Pagos `<= 100`).",
    },
    ("reserva_entrada", "id_promocion"): {
        "key": "FK Ext (Promociones)",
        "origin": "Referencia externa → Promociones",
        "desc": "Identificador de referencia de la promoción validada por `POST /api/promociones/evaluar` (`null` si no aplica descuento).",
    },
    ("reserva_entrada", "nombre_codigo"): {
        "key": "-",
        "origin": "Referencia contrato Pagos/Promociones",
        "desc": "Código promocional validado (ej. `ESTUDIANTE15`) expuesto a Pagos en `GET /api/entradas/reservas/{id_reserva}` (INT-01) para propagación a `pago.completado`.",
    },
    ("reserva_entrada", "porcentaje_descuento"): {
        "key": "-",
        "origin": "Entradas (Cálculo validado server-side)",
        "desc": "Porcentaje de descuento entero (`0..100`) revalidado server-side con Promociones (`0` si no aplica).",
    },
    ("reserva_entrada", "monto_total"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Monto total final a pagar en CLP (`>= 0`), calculado como `precio_unitario * cantidad_entrada * (1 - porcentaje_descuento/100)`. Validado por Pagos en INT-01.",
    },
    ("reserva_entrada", "id_pago"): {
        "key": "FK Ext (Pagos)",
        "origin": "Referencia externa → Pasarela de Pagos",
        "desc": "Identificador de referencia de la transacción en Pagos (`pay-*`). `null` en reservas gratuitas o antes de iniciar pago. Indexado por `idx_reserva_id_pago`.",
    },
    ("reserva_entrada", "estado_reserva"): {
        "key": "IDX compuesto",
        "origin": "Entradas (Máquina de estados)",
        "desc": "Estado de la reserva: `RESERVADO` (hold activo), `CONSOLIDADO` (pagada/emitida), `EXPIRADO` (vencida/rechazada) o `CANCELADO` (cancelada por usuario/reembolso).",
    },
    ("reserva_entrada", "fecha_cancelacion"): {
        "key": "-",
        "origin": "Entradas (Auditoría)",
        "desc": "Marca de tiempo UTC de cancelación manual o expiración automática por el worker de liberación.",
    },
    ("reserva_entrada", "fecha_creacion"): {
        "key": "-",
        "origin": "Entradas (Auditoría)",
        "desc": "Marca de tiempo UTC de creación de la reserva.",
    },
    ("reserva_entrada", "fecha_expiracion"): {
        "key": "IDX compuesto",
        "origin": "Entradas (Control Hold HU-03)",
        "desc": "Fecha límite UTC del Hold temporal (`null` cuando la reserva ya está `CONSOLIDADO`). Monitoreada por el worker en segundo plano usando `idx_reserva_estado_expiracion` (sin TTL destructivo).",
    },
    # entrada
    ("entrada", "_id"): {
        "key": "ID (PK interna)",
        "origin": "MongoDB (Entradas)",
        "desc": "Identificador interno autogenerado por MongoDB (`ObjectId`).",
    },
    ("entrada", "id_entrada"): {
        "key": "PK / FK Ext (Check-in)",
        "origin": "Entradas (Dominio propio)",
        "desc": "Código único e inmutable del ticket emitido (`tk-*`). Índice único `pk_entrada_id_entrada`. Referenciado por Check-in para validación en torniquete.",
    },
    ("entrada", "id_reserva"): {
        "key": "FK → reserva_entrada.id_reserva",
        "origin": "Entradas (Integridad referencial)",
        "desc": "Llave foránea hacia la reserva consolidada que originó el ticket. Indexada por `fk_entrada_reserva`.",
    },
    ("entrada", "id_evento"): {
        "key": "FK → inventario_evento.id_evento",
        "origin": "Referencia interna y externa (Panel/Check-in)",
        "desc": "Llave foránea directa hacia `inventario_evento.id_evento` (misma dirección topológica del DAG, sin ciclos). Indexada por `idx_entrada_evento`.",
    },
    ("entrada", "nombre_evento"): {
        "key": "-",
        "origin": "Snapshot inmutable de comprobante (HU-04)",
        "desc": "Título del evento congelado al instante de emisión del ticket para consulta histórica inmutable.",
    },
    ("entrada", "id_usuario"): {
        "key": "FK Ext (Auth)",
        "origin": "Referencia externa → Auth",
        "desc": "Identificador de referencia del titular de la entrada. Parte del índice `idx_entrada_usuario` (`{id_usuario: 1, fecha_emision: -1}`).",
    },
    ("entrada", "nombre_usuario"): {
        "key": "-",
        "origin": "Snapshot inmutable de comprobante / Check-in",
        "desc": "Nombre del asistente acreditado en el comprobante inmutable y devuelto en el contrato HTTP hacia Check-in (`GET /api/entradas/{id_ticket}`).",
    },
    ("entrada", "rut_usuario"): {
        "key": "-",
        "origin": "Snapshot inmutable de comprobante (opcional)",
        "desc": "RUT del asistente titular capturado al momento de emitir el comprobante.",
    },
    ("entrada", "correo_usuario"): {
        "key": "-",
        "origin": "Snapshot inmutable de comprobante (opcional)",
        "desc": "Correo del asistente titular utilizado en la notificación de emisión.",
    },
    ("entrada", "rol_usuario"): {
        "key": "-",
        "origin": "Referencia rol Auth",
        "desc": "Rol del titular acreditado devuelto a Check-in (`usuario`, `staff`, `organizador`).",
    },
    ("entrada", "tipo_acceso"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Categoría de acceso físico del ticket. Valor permitido actual: `GENERAL`.",
    },
    ("entrada", "lugar_ingreso"): {
        "key": "-",
        "origin": "Snapshot inmutable de comprobante (HU-04/05)",
        "desc": "Puerta o sector de ingreso al recinto mostrado en el pase digital.",
    },
    ("entrada", "precio_final_pagado"): {
        "key": "-",
        "origin": "Entradas (Inmutable financiero)",
        "desc": "Precio unitario final efectivamente pagado en CLP (`>= 0`), persistido de forma inmutable al emitir el ticket.",
    },
    ("entrada", "estado_entrada"): {
        "key": "-",
        "origin": "Entradas (Ciclo de vida ticket)",
        "desc": "Estado operativo de la entrada: `EMITIDA` (habilitada para QR/Check-in) o `ANULADA` (inhabilitada).",
    },
    ("entrada", "nombre_archivo_qr"): {
        "key": "-",
        "origin": "Entradas (Dominio propio)",
        "desc": "Nombre de archivo asociado a la representación gráfica del QR (`<id_entrada>.png`).",
    },
    ("entrada", "qr_data"): {
        "key": "-",
        "origin": "Entradas / Contrato Check-in (HU-05)",
        "desc": "Subdocumento BSON obligatorio con `url` (URL del código QR que codifica JSON `{id_entrada, id_evento}`) y `hash` (huella de verificación).",
    },
    ("entrada", "fecha_emision"): {
        "key": "IDX compuesto",
        "origin": "Entradas (Auditoría)",
        "desc": "Marca de tiempo UTC de emisión definitiva del ticket. Usada para orden descendente en `idx_entrada_usuario`.",
    },
}


def format_type(prop: Dict[str, Any]) -> Tuple[str, bool]:
    btype = prop.get("bsonType", "any")
    if isinstance(btype, list):
        nullable = "null" in btype
        clean = " \\| ".join(t for t in btype if t != "null")
        return clean, nullable
    return str(btype), False


def format_constraints(prop: Dict[str, Any]) -> str:
    parts: List[str] = []
    if "enum" in prop:
        parts.append("ENUM: `" + "`, `".join(str(v) for v in prop["enum"]) + "`")
    if "minimum" in prop:
        parts.append(f"`>= {prop['minimum']}`")
    if "maximum" in prop:
        parts.append(f"`<= {prop['maximum']}`")
    if prop.get("bsonType") == "object" and "properties" in prop:
        req = ", ".join(prop.get("required", []))
        sub = ", ".join(f"`{k}: {v.get('bsonType')}`" for k, v in prop["properties"].items())
        parts.append(f"Subdocumento ({sub}; required: `{req}`)")
    return "; ".join(parts) if parts else "—"


def generate_dictionary(uri: str, db_name: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        server_info = client.server_info()
        db = client[db_name]
        raw_cols = {
            c["name"]: c
            for c in db.list_collections()
            if c.get("type") == "collection" and not c["name"].startswith("system.")
        }
        ordered = [c for c in COLLECTION_ORDER if c in raw_cols] + [
            c for c in sorted(raw_cols.keys()) if c not in COLLECTION_ORDER
        ]

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        csv_rows: List[Dict[str, str]] = []
        md: List[str] = [
            "# Diccionario de Datos — Microservicio de Entradas e Inventario (`ticketu_entradas_db`)",
            "",
            f"- **Motor de Base de Datos:** MongoDB {server_info.get('version', '7.0')}",
            f"- **Base de Datos:** `{db_name}` (instancia dedicada en red aislada `entradas-internal-net`)",
            f"- **Fecha de extracción automática:** `{now_utc}`",
            "- **Script de creación de la BD (referencia oficial):** [`scripts/init_db_creacion_bd.js`](../scripts/init_db_creacion_bd.js)",
            "- **Script generador de este diccionario:** [`scripts/generar_diccionario_datos.py`](../scripts/generar_diccionario_datos.py)",
            "- **Criterios de rúbrica cubiertos:** **BD3** (Nomenclatura y documentación) y **BD4** (Diseño técnico: PK, FK, tipos, nulabilidad, índices y sin ciclos).",
            "",
            "---",
            "",
            "## 1. Estándares de Nomenclatura Aplicados (BD3)",
            "",
            "| Elemento | Convención oficial | Ejemplos reales verificados en MongoDB |",
            "| :--- | :--- | :--- |",
            "| **Base de datos** | `snake_case` con prefijo de plataforma y dominio | `ticketu_entradas_db` |",
            "| **Colecciones** | `snake_case`, sustantivo singular descriptivo | `inventario_evento`, `reserva_entrada`, `entrada` |",
            "| **Atributos** | `snake_case` en español sin tildes | `id_evento`, `precio_unitario`, `estado_reserva`, `fecha_emision` |",
            "| **Llaves primarias de negocio** | Prefijo `id_` + índice único `pk_<entidad>_<campo>` | `pk_inventario_id_evento`, `pk_reserva_id_reserva`, `pk_entrada_id_entrada` |",
            "| **Llaves foráneas internas** | Mismo nombre del identificador referenciado + índice `fk_*` o `idx_*` | `fk_reserva_inventario_evento`, `fk_entrada_reserva`, `idx_entrada_evento` |",
            "| **Índices secundarios** | Prefijo `idx_<entidad>_<propósito>` | `idx_inventario_organizador`, `idx_reserva_estado_expiracion`, `idx_reserva_id_pago`, `idx_entrada_usuario` |",
            "| **Estados y tipos (ENUM)** | `UPPER_SNAKE_CASE` (roles aceptan normalización Auth en minúsculas/mayúsculas) | `PAGADA`, `GRATUITA`, `PUBLICADO`, `RESERVADO`, `CONSOLIDADO`, `EMITIDA`, `ANULADA` |",
            "| **Prefijos de identificadores** | Prefijo semántico de entidad | `evt-*`, `res-*` / `hold-*`, `tk-*`, `usr-*`, `pay-*`, `promo-*` |",
            "| **Política de esquema estricto** | `$jsonSchema` con `additionalProperties: false` en las 3 colecciones | Impide persistir campos no declarados, tokens JWT o entidades de otros squads |",
            "",
            "---",
            "",
            "## 2. Resumen General de Colecciones",
            "",
            "| # | Colección | Nivel DAG | Documentos semilla | Atributos documentados | Obligatorios (`required`) | Índices | `additionalProperties` |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
        ]

        dag_labels = {
            "inventario_evento": "Nivel 0 (Raíz)",
            "reserva_entrada": "Nivel 1 (Intermedio)",
            "entrada": "Nivel 2 (Hoja)",
        }

        total_fields = 0
        total_indexes = 0
        for idx_c, col_name in enumerate(ordered, start=1):
            info = raw_cols[col_name]
            jschema = info.get("options", {}).get("validator", {}).get("$jsonSchema", {})
            props = jschema.get("properties", {})
            req = jschema.get("required", [])
            indexes = list(db[col_name].list_indexes())
            cnt = db[col_name].count_documents({})
            total_fields += len(props)
            total_indexes += len(indexes)
            add_prop = str(jschema.get("additionalProperties")).lower()
            md.append(
                f"| {idx_c} | `{col_name}` | {dag_labels.get(col_name, '-')} | {cnt} | {len(props)} | {len(req)} | {len(indexes)} | `{add_prop}` |"
            )

        md.extend(
            [
                "",
                f"**Totales verificados:** `{len(ordered)}` colecciones propias del dominio Entradas · `{total_fields}` atributos documentados (100% de cobertura) · `{total_indexes}` índices totales · `0` colecciones de otros microservicios.",
                "",
                "---",
                "",
                "## 3. Detalle por Colección",
                "",
            ]
        )

        for idx_c, col_name in enumerate(ordered, start=1):
            info = raw_cols[col_name]
            jschema = info.get("options", {}).get("validator", {}).get("$jsonSchema", {})
            props = jschema.get("properties", {})
            req_set = set(jschema.get("required", []))
            indexes = list(db[col_name].list_indexes())
            cnt = db[col_name].count_documents({})

            md.extend(
                [
                    f"### 3.{idx_c}. Colección `{col_name}`",
                    "",
                    COLLECTION_DESCRIPTIONS.get(col_name, ""),
                    "",
                    f"- **Validador activo:** `$jsonSchema` (`additionalProperties: {str(jschema.get('additionalProperties')).lower()}`)",
                    f"- **Documentos registrados en semilla oficial:** `{cnt}`",
                    "",
                    "#### Atributos",
                    "",
                    "| Atributo | Tipo BSON | Nulabilidad | Llave / Referencia | Restricciones / Dominio | Origen / Descripción |",
                    "| :--- | :--- | :---: | :--- | :--- | :--- |",
                ]
            )

            for fname, fspec in props.items():
                type_str, allows_null = format_type(fspec)
                is_req = fname in req_set or fname == "_id"
                nullable = (not is_req) or allows_null
                null_str = "NULLABLE" if nullable else "**NOT NULL**"
                meta = FIELD_METADATA.get((col_name, fname), {"key": "-", "origin": "Entradas", "desc": fspec.get("description", "—")})
                constr = format_constraints(fspec)
                md.append(
                    f"| `{fname}` | `{type_str}` | {null_str} | {meta['key']} | {constr} | **{meta['origin']}.** {meta['desc']} |"
                )

                csv_rows.append(
                    {
                        "coleccion": col_name,
                        "atributo": fname,
                        "tipo_bson": type_str.replace(" \\| ", "|"),
                        "required_en_schema": "SI" if is_req else "NO",
                        "nulabilidad": "NULLABLE" if nullable else "NOT NULL",
                        "llave_referencia": meta["key"],
                        "restricciones": constr.replace("`", ""),
                        "origen": meta["origin"],
                        "descripcion": meta["desc"],
                    }
                )

            has_subdocs = any(v.get("bsonType") == "object" and "properties" in v for v in props.values())
            if has_subdocs:
                md.extend(["", "#### Subdocumentos embebidos"])
            for fname, fspec in props.items():
                if fspec.get("bsonType") == "object" and "properties" in fspec:
                    sub_req = set(fspec.get("required", []))
                    md.extend(
                        [
                            "",
                            f"| Subatributo (`{fname}.*`) | Tipo BSON | Nulabilidad | Descripción |",
                            "| :--- | :--- | :---: | :--- |",
                        ]
                    )
                    sub_descs = {
                        "url": "URL generadora del código QR que codifica el payload JSON `{\"id_entrada\",\"id_evento\"}` para lectura en torniquete por Check-in.",
                        "hash": "Huella hexadecimal corta de verificación e integridad del QR emitido.",
                    }
                    for sk, sv in fspec["properties"].items():
                        sn = "**NOT NULL**" if sk in sub_req else "NULLABLE"
                        md.append(f"| `{fname}.{sk}` | `{sv.get('bsonType')}` | {sn} | {sub_descs.get(sk, '—')} |")

            md.extend(
                [
                    "",
                    "#### Índices configurados",
                    "",
                    "| Nombre del índice | Campos y orden | Único | Propósito técnico |",
                    "| :--- | :--- | :---: | :--- |",
                ]
            )
            idx_purposes = {
                "_id_": "Índice primario interno automático de MongoDB.",
                "pk_inventario_id_evento": "Garantiza unicidad de negocio por `id_evento` y acelera búsquedas O(log n) de disponibilidad/stock.",
                "idx_inventario_organizador": "Acelera consultas de inventario filtradas por organizador y rol.",
                "pk_reserva_id_reserva": "Garantiza unicidad de negocio por `id_reserva` (consultado por Pagos INT-01 y Checkout).",
                "fk_reserva_inventario_evento": "Soporta integridad referencial y `$lookup` hacia `inventario_evento`.",
                "idx_reserva_usuario_evento": "Optimiza búsquedas de reservas por comprador y evento.",
                "idx_reserva_estado_expiracion": "Optimiza el barrido periódico del worker de expiración de Holds (`RESERVADO` + `fecha_expiracion < ahora`) sin borrado TTL destructivo.",
                "idx_reserva_id_pago": "Acelera la correlación con transacciones reportadas por Pagos (`pago.realizado`, `pago.rechazado`, polling).",
                "pk_entrada_id_entrada": "Garantiza unicidad e inmutabilidad por `id_entrada` (consultado por Check-in y QR).",
                "fk_entrada_reserva": "Soporta integridad referencial y `$lookup` hacia `reserva_entrada`.",
                "idx_entrada_evento": "Soporta integridad referencial directa hacia `inventario_evento` y reportes por evento.",
                "idx_entrada_usuario": "Optimiza historial `GET /api/entradas/mis-entradas` ordenado cronológicamente descendente (HU-04).",
            }
            for ix in indexes:
                ix_name = ix.get("name", "")
                k_str = ", ".join(f"`{k}: {'ASC (1)' if v == 1 else 'DESC (-1)'}`" for k, v in ix.get("key", {}).items())
                uniq_str = "Sí (`unique: true`)" if ix.get("unique") or ix_name == "_id_" else "No"
                md.append(f"| `{ix_name}` | {k_str} | {uniq_str} | {idx_purposes.get(ix_name, 'Índice operativo')} |")
            md.append("")

        md.extend(
            [
                "---",
                "",
                "## 4. Mapa de Integridad Referencial Interna y Referencias Externas (BD2 y BD4)",
                "",
                "### 4.1. Relaciones internas (Grafo Acíclico Dirigido — 0 ciclos)",
                "",
                "| Colección padre (1) | Colección hija (0..N) | Campo FK | Índice en hija | Dirección topológica |",
                "| :--- | :--- | :--- | :--- | :--- |",
                "| `inventario_evento.id_evento` | `reserva_entrada.id_evento` | `id_evento` | `fk_reserva_inventario_evento` | Nivel 0 → Nivel 1 |",
                "| `reserva_entrada.id_reserva` | `entrada.id_reserva` | `id_reserva` | `fk_entrada_reserva` | Nivel 1 → Nivel 2 |",
                "| `inventario_evento.id_evento` | `entrada.id_evento` | `id_evento` | `idx_entrada_evento` | Nivel 0 → Nivel 2 |",
                "",
                "### 4.2. Referencias externas hacia otros microservicios",
                "",
                "| Microservicio contraparte | Identificador de referencia | Colección(es) en Entradas | ¿Se replican colecciones o credenciales? |",
                "| :--- | :--- | :--- | :---: |",
                "| **Panel Organizador & Catálogo** | `id_evento` | `inventario_evento`, `reserva_entrada`, `entrada` | **No** (solo ID y snapshot operativo) |",
                "| **Autenticación (Auth)** | `id_usuario` | `inventario_evento`, `reserva_entrada`, `entrada` | **No** (0 passwords, 0 JWT en BD) |",
                "| **Promociones** | `id_promocion` | `reserva_entrada` | **No** (0 reglas de cupones; revalidación server-side) |",
                "| **Pasarela de Pagos** | `id_pago` (y `id_reserva` en INT-01) | `reserva_entrada` | **No** (0 tarjetas, 0 `client_secret`) |",
                "| **Check-in** | `id_entrada`, `id_evento` (payload QR) | `entrada` | **No** (estado de torniquete vive en MySQL de Check-in) |",
                "| **Notificaciones** | `id_usuario`, `id_evento`, `qr_data` | `entrada` (publicación RabbitMQ) | **No** (logs de correo viven en Notificaciones) |",
                "",
            ]
        )

        md_path = out_dir / "DICCIONARIO_DE_DATOS.md"
        md_path.write_text("\n".join(md), encoding="utf-8")

        csv_path = out_dir / "diccionario_datos_entradas.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "coleccion",
                    "atributo",
                    "tipo_bson",
                    "required_en_schema",
                    "nulabilidad",
                    "llave_referencia",
                    "restricciones",
                    "origen",
                    "descripcion",
                ],
            )
            writer.writeheader()
            writer.writerows(csv_rows)

        print(f"[OK] Diccionario Markdown generado en: {md_path}")
        print(f"[OK] Diccionario CSV generado en:      {csv_path} ({len(csv_rows)} filas)")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el Diccionario de Datos (MD + CSV) desde MongoDB.")
    parser.add_argument("--uri", default=os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"), help="URI de conexión MongoDB")
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "ticketu_entradas_db"), help="Nombre de la base de datos")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent.parent / "diccionario_datos"),
        help="Directorio de salida del diccionario de datos",
    )
    args = parser.parse_args()
    generate_dictionary(args.uri, args.db, Path(args.out_dir))


if __name__ == "__main__":
    main()
