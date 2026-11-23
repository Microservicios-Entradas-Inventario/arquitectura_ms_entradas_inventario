#!/usr/bin/env python3
"""
Script de creación del Diagrama Relacional (Vectorial SVG, PNG alta resolución y DBML)
para la base de datos MongoDB del microservicio de Entradas e Inventario (ticketu_entradas_db).

Características (BD1, BD2, BD3, BD4):
- Se conecta directamente a la instancia MongoDB de workstation (por defecto mongodb://127.0.0.1:27017)
  y extrae en tiempo real: colecciones, validadores $jsonSchema (tipos BSON, required, enums,
  rangos min/max, additionalProperties) e índices reales (PK únicas, FKs, compuestos).
- Genera:
  1. diagrama_relacional/diagrama_relacional_entradas.svg   (formato vectorial escalable)
  2. diagrama_relacional/diagrama_relacional_entradas.png   (formato PNG de alta resolución)
  3. diagrama_relacional/schema_entradas_actualizado.dbml   (código DBML actualizado)
  4. diagrama_relacional/schema_extraido_workstation.json   (metadatos crudos de introspección)

Uso replicable en workstation:
    python scripts/generar_diagrama_bd.py
    python scripts/generar_diagrama_bd.py --uri mongodb://127.0.0.1:27017 --db ticketu_entradas_db
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient

# Orden topológico esperado de las colecciones del dominio Entradas
COLLECTION_ORDER = ["inventario_evento", "reserva_entrada", "entrada"]

# Definición formal de llaves de negocio, llaves foráneas internas y referencias externas
PRIMARY_BUSINESS_KEYS = {
    "inventario_evento": "id_evento",
    "reserva_entrada": "id_reserva",
    "entrada": "id_entrada",
}

INTERNAL_FKS: List[Dict[str, str]] = [
    {
        "from_col": "reserva_entrada",
        "from_field": "id_evento",
        "to_col": "inventario_evento",
        "to_field": "id_evento",
        "cardinality": "1 : 0..N",
        "index": "fk_reserva_inventario_evento",
        "label": "1 : 0..N  (id_evento)",
    },
    {
        "from_col": "entrada",
        "from_field": "id_reserva",
        "to_col": "reserva_entrada",
        "to_field": "id_reserva",
        "cardinality": "1 : 0..N",
        "index": "fk_entrada_reserva",
        "label": "1 : 0..N  (id_reserva)",
    },
    {
        "from_col": "entrada",
        "from_field": "id_evento",
        "to_col": "inventario_evento",
        "to_field": "id_evento",
        "cardinality": "1 : 0..N",
        "index": "idx_entrada_evento",
        "label": "1 : 0..N  (id_evento · FK directa sin ciclos)",
    },
]

EXTERNAL_REFS: Dict[Tuple[str, str], str] = {
    ("inventario_evento", "id_evento"): "Panel / Catálogo",
    ("inventario_evento", "id_usuario"): "Auth (Organizador)",
    ("reserva_entrada", "id_usuario"): "Auth (Usuario)",
    ("reserva_entrada", "id_promocion"): "Promociones",
    ("reserva_entrada", "id_pago"): "Pagos",
    ("entrada", "id_usuario"): "Auth (Titular)",
    ("entrada", "id_entrada"): "Check-in (QR)",
}

COLLECTION_META = {
    "inventario_evento": {
        "title": "inventario_evento",
        "layer": "Nivel 0 · Raíz (DAG)",
        "color": "#1B365D",
        "accent": "#E8EEF6",
        "subtitle": "Control de cupos, tarifas y estado de venta",
    },
    "reserva_entrada": {
        "title": "reserva_entrada",
        "layer": "Nivel 1 · Intermedio (DAG)",
        "color": "#0D5C63",
        "accent": "#E6F4F5",
        "subtitle": "Hold temporal (HU-03), descuentos y vínculo a Pagos",
    },
    "entrada": {
        "title": "entrada",
        "layer": "Nivel 2 · Hoja (DAG)",
        "color": "#393E8F",
        "accent": "#ECEEFB",
        "subtitle": "Tickets inmutables emitidos y código QR (HU-04/05)",
    },
}


def verify_dag_acyclicity(collections: List[str], fks: List[Dict[str, str]]) -> Dict[str, Any]:
    """Verifica formalmente mediante ordenamiento topológico (Kahn) que no existen ciclos."""
    adj: Dict[str, List[str]] = {c: [] for c in collections}
    indeg: Dict[str, int] = {c: 0 for c in collections}
    for fk in fks:
        parent = fk["to_col"]
        child = fk["from_col"]
        if parent in adj and child in adj:
            adj[parent].append(child)
            indeg[child] += 1

    queue = deque([c for c in collections if indeg[c] == 0])
    topo_order: List[str] = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for nxt in adj[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    return {
        "es_dag_aciclico": len(topo_order) == len(collections),
        "orden_topologico": topo_order,
        "ciclos_detectados": 0 if len(topo_order) == len(collections) else len(collections) - len(topo_order),
        "aristas_dirigidas": [f"{fk['to_col']} -> {fk['from_col']} ({fk['from_field']})" for fk in fks],
    }


def parse_bson_type(prop_spec: Dict[str, Any]) -> Tuple[str, bool]:
    """Retorna (tipo_formateado, es_nullable_por_tipo) a partir de una propiedad $jsonSchema."""
    btype = prop_spec.get("bsonType", "any")
    nullable = False
    if isinstance(btype, list):
        nullable = "null" in btype
        non_null = [t for t in btype if t != "null"]
        base = "|".join(non_null) if non_null else "null"
    else:
        base = str(btype)

    constraints: List[str] = []
    if "minimum" in prop_spec and "maximum" in prop_spec:
        constraints.append(f"{prop_spec['minimum']}..{prop_spec['maximum']}")
    elif "minimum" in prop_spec:
        constraints.append(f">={prop_spec['minimum']}")
    elif "maximum" in prop_spec:
        constraints.append(f"<={prop_spec['maximum']}")

    if "enum" in prop_spec:
        constraints.append(f"enum[{len(prop_spec['enum'])}]")

    if base == "object" and "properties" in prop_spec:
        subkeys = ",".join(prop_spec["properties"].keys())
        base = f"object{{{subkeys}}}"

    if constraints:
        return f"{base} ({', '.join(constraints)})", nullable
    return base, nullable


def extract_live_schema(uri: str, db_name: str) -> Dict[str, Any]:
    """Extrae el esquema en vivo directamente desde MongoDB ($jsonSchema, índices y conteos)."""
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        server_info = client.server_info()
        db = client[db_name]
        raw_infos = list(db.list_collections())
        infos_by_name = {
            c["name"]: c for c in raw_infos if c.get("type") == "collection" and not c["name"].startswith("system.")
        }

        ordered_names = [c for c in COLLECTION_ORDER if c in infos_by_name] + [
            c for c in sorted(infos_by_name.keys()) if c not in COLLECTION_ORDER
        ]

        collections_data: Dict[str, Any] = {}
        for col_name in ordered_names:
            info = infos_by_name[col_name]
            validator = info.get("options", {}).get("validator", {})
            jschema = validator.get("$jsonSchema", {})
            required_fields = set(jschema.get("required", []))
            props = jschema.get("properties", {})
            indexes = list(db[col_name].list_indexes())
            doc_count = db[col_name].count_documents({})

            fields: List[Dict[str, Any]] = []
            for fname, fspec in props.items():
                type_str, type_allows_null = parse_bson_type(fspec)
                is_required = fname in required_fields or fname == "_id"
                is_nullable = (not is_required) or type_allows_null

                badges: List[str] = []
                if fname == "_id":
                    badges.append("ID")
                if PRIMARY_BUSINESS_KEYS.get(col_name) == fname:
                    badges.append("PK")
                if any(fk["from_col"] == col_name and fk["from_field"] == fname for fk in INTERNAL_FKS):
                    badges.append("FK")
                if (col_name, fname) in EXTERNAL_REFS:
                    badges.append("EXT")

                fields.append(
                    {
                        "name": fname,
                        "bson_type_raw": fspec.get("bsonType"),
                        "type_display": type_str,
                        "required": is_required,
                        "nullable": is_nullable,
                        "nullability_label": "NULLABLE" if is_nullable else "NOT NULL",
                        "enum": fspec.get("enum"),
                        "minimum": fspec.get("minimum"),
                        "maximum": fspec.get("maximum"),
                        "description": fspec.get("description", ""),
                        "subproperties": fspec.get("properties"),
                        "badges": badges,
                        "external_ref": EXTERNAL_REFS.get((col_name, fname)),
                    }
                )

            idx_list = []
            for idx in indexes:
                idx_list.append(
                    {
                        "name": idx.get("name"),
                        "key": dict(idx.get("key", {})),
                        "unique": bool(idx.get("unique", False)),
                        "expireAfterSeconds": idx.get("expireAfterSeconds"),
                    }
                )

            collections_data[col_name] = {
                "name": col_name,
                "doc_count": doc_count,
                "additional_properties": jschema.get("additionalProperties"),
                "required_count": len(required_fields),
                "fields": fields,
                "indexes": idx_list,
            }

        dag_check = verify_dag_acyclicity(ordered_names, INTERNAL_FKS)

        return {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "mongodb_version": server_info.get("version", "unknown"),
            "database_name": db_name,
            "collection_order": ordered_names,
            "collections": collections_data,
            "internal_fks": INTERNAL_FKS,
            "dag_verification": dag_check,
        }
    finally:
        client.close()


def generate_dbml(schema: Dict[str, Any]) -> str:
    """Genera el archivo DBML actualizado a partir del esquema extraído en vivo."""
    lines = [
        f"// Generado automáticamente desde MongoDB {schema['mongodb_version']} ({schema['database_name']})",
        f"// Fecha extracción: {schema['generated_at_utc']}",
        "",
        "Project TicketuEntradas {",
        "  database_type: 'MongoDB 7.0'",
        "  Note: 'Microservicio de Entradas e Inventario (ticketu_entradas_db) - Esquema oficial workstation'",
        "}",
        "",
    ]

    fk_lookup = {(fk["from_col"], fk["from_field"]): fk for fk in schema["internal_fks"]}

    for col_name in schema["collection_order"]:
        col = schema["collections"][col_name]
        lines.append(f"Table {col_name} {{")
        for f in col["fields"]:
            btype = f["bson_type_raw"]
            if isinstance(btype, list):
                base_t = next((t for t in btype if t != "null"), "string")
            else:
                base_t = str(btype or "string")

            attrs: List[str] = []
            if "PK" in f["badges"]:
                attrs.append("pk")
            if not f["nullable"]:
                attrs.append("not null")
            else:
                attrs.append("null")

            fk = fk_lookup.get((col_name, f["name"]))
            if fk:
                attrs.append(f"ref: > {fk['to_col']}.{fk['to_field']}")

            notes: List[str] = []
            if f["name"] == "_id":
                notes.append("Clave interna MongoDB")
            if "PK" in f["badges"]:
                notes.append("PK negocio (unique index)")
            if fk:
                notes.append(f"FK interna -> {fk['to_col']}.{fk['to_field']}")
            if f["external_ref"]:
                notes.append(f"Ref externa -> {f['external_ref']}")
            if f["enum"]:
                notes.append("ENUM: " + ", ".join(str(x) for x in f["enum"]))
            if f["minimum"] is not None:
                notes.append(f"min={f['minimum']}")
            if f["maximum"] is not None:
                notes.append(f"max={f['maximum']}")
            if notes:
                note_txt = "; ".join(notes).replace("'", "")
                attrs.append(f"note: '{note_txt}'")

            attr_block = f" [{', '.join(attrs)}]" if attrs else ""
            lines.append(f"  {f['name']} {base_t}{attr_block}")

        lines.append("")
        lines.append("  indexes {")
        for idx in col["indexes"]:
            if idx["name"] == "_id_":
                continue
            cols_str = ", ".join(idx["key"].keys())
            if len(idx["key"]) > 1:
                cols_str = f"({cols_str})"
            idx_attrs = [f"name: '{idx['name']}'"]
            if idx["unique"]:
                idx_attrs.append("unique")
            lines.append(f"    {cols_str} [{', '.join(idx_attrs)}]")
        lines.append("  }")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def build_svg(schema: Dict[str, Any]) -> str:
    """Construye un diagrama relacional vectorial SVG profesional con notación Crow's Foot."""
    W = 1960
    H = 1220

    # Geometría de tarjetas (3 columnas en orden topológico estricto Nivel 0 -> Nivel 1 -> Nivel 2)
    card_w = 560
    gap_x = 90
    margin_x = 50
    card_top = 178
    header_h = 74
    col_hdr_h = 28
    row_h = 28

    col_positions: Dict[str, Dict[str, Any]] = {}
    max_card_bottom = 0

    for i, col_name in enumerate(schema["collection_order"]):
        col = schema["collections"][col_name]
        x = margin_x + i * (card_w + gap_x)
        n_fields = len(col["fields"])
        n_indexes = len([ix for ix in col["indexes"] if ix["name"] != "_id_"])
        idx_block_h = 26 + n_indexes * 19 + 12
        total_h = header_h + col_hdr_h + n_fields * row_h + idx_block_h + 10
        row_y_map = {}
        for r_idx, fld in enumerate(col["fields"]):
            row_y_map[fld["name"]] = card_top + header_h + col_hdr_h + r_idx * row_h + row_h / 2.0

        col_positions[col_name] = {
            "x": x,
            "y": card_top,
            "w": card_w,
            "h": total_h,
            "row_y": row_y_map,
            "idx_y": card_top + header_h + col_hdr_h + n_fields * row_h + 6,
        }
        max_card_bottom = max(max_card_bottom, card_top + total_h)

    ext_strip_y = max_card_bottom + 54
    ext_strip_h = 122
    legend_y = ext_strip_y + ext_strip_h + 24
    legend_h = 114
    H = legend_y + legend_h + 28

    svg: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "  <defs>",
        '    <filter id="cardShadow" x="-4%" y="-4%" width="108%" height="110%">',
        '      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#0F172A" flood-opacity="0.10"/>',
        "    </filter>",
        '    <linearGradient id="bannerGrad" x1="0" y1="0" x2="1" y2="0">',
        '      <stop offset="0%" stop-color="#0F2942"/>',
        '      <stop offset="55%" stop-color="#1B365D"/>',
        '      <stop offset="100%" stop-color="#0D5C63"/>',
        "    </linearGradient>",
        "    <style>",
        "      .sans { font-family: 'Segoe UI', 'DejaVu Sans', Arial, sans-serif; }",
        "      .mono { font-family: 'Cascadia Code', 'Consolas', 'DejaVu Sans Mono', monospace; }",
        "    </style>",
        "  </defs>",
        "",
        f'  <rect x="0" y="0" width="{W}" height="{H}" fill="#F4F7FB"/>',
        # Grid sutil de fondo
        '  <g stroke="#E2E8F0" stroke-width="0.6" opacity="0.55">',
    ]
    for gx in range(40, W, 40):
        svg.append(f'    <line x1="{gx}" y1="0" x2="{gx}" y2="{H}"/>')
    for gy in range(40, H, 40):
        svg.append(f'    <line x1="0" y1="{gy}" x2="{W}" y2="{gy}"/>')
    svg.append("  </g>")

    # Banner superior
    svg.extend(
        [
            f'  <rect x="24" y="18" width="{W - 48}" height="92" rx="12" fill="url(#bannerGrad)" filter="url(#cardShadow)"/>',
            '  <text x="50" y="55" class="sans" font-size="25" font-weight="700" fill="#FFFFFF">Diagrama Relacional Actualizado — Microservicio de Entradas e Inventario</text>',
            f'  <text x="50" y="81" class="sans" font-size="13.5" fill="#CBD5E1">Base de datos: {html.escape(schema["database_name"])} (MongoDB {html.escape(schema["mongodb_version"])})  ·  Introspección directa de $jsonSchema e índices de workstation  ·  Extraído: {html.escape(schema["generated_at_utc"])}</text>',
        ]
    )

    # Pills de estado en el banner derecho
    dag = schema["dag_verification"]
    pills = [
        (f"Colecciones: {len(schema['collection_order'])}", "#10B981"),
        (f"Ciclos: {dag['ciclos_detectados']} (DAG Acíclico)", "#38BDF8"),
        ("additionalProperties: false", "#F59E0B"),
    ]
    px_cursor = W - 46
    for label, pcol in reversed(pills):
        pw = len(label) * 7.8 + 26
        px_cursor -= pw
        svg.append(f'  <rect x="{px_cursor:.1f}" y="44" width="{pw:.1f}" height="32" rx="16" fill="#FFFFFF" fill-opacity="0.14" stroke="{pcol}" stroke-width="1.3"/>')
        svg.append(f'  <text x="{px_cursor + pw / 2:.1f}" y="64.5" text-anchor="middle" class="sans" font-size="12" font-weight="600" fill="#FFFFFF">{html.escape(label)}</text>')
        px_cursor -= 12

    # ------------------------------------------------------------------
    # Relaciones internas (Crow's Foot) dibujadas antes/encima limpiamente
    # ------------------------------------------------------------------
    def draw_crows_foot_one(x: float, y: float, direction: str, color: str) -> List[str]:
        # direction: 'right' significa línea sale hacia la derecha desde (x,y)
        dx = 1 if direction == "right" else -1
        return [
            f'  <line x1="{x + dx * 7}" y1="{y - 8}" x2="{x + dx * 7}" y2="{y + 8}" stroke="{color}" stroke-width="2.2"/>',
            f'  <line x1="{x + dx * 13}" y1="{y - 8}" x2="{x + dx * 13}" y2="{y + 8}" stroke="{color}" stroke-width="2.2"/>',
        ]

    def draw_crows_foot_zero_many(x: float, y: float, direction: str, color: str) -> List[str]:
        # direction: 'left' significa línea llega desde la izquierda hacia (x,y)
        dx = -1 if direction == "left" else 1
        return [
            f'  <line x1="{x + dx * 16}" y1="{y}" x2="{x}" y2="{y - 9}" stroke="{color}" stroke-width="2.2"/>',
            f'  <line x1="{x + dx * 16}" y1="{y}" x2="{x}" y2="{y + 9}" stroke="{color}" stroke-width="2.2"/>',
            f'  <line x1="{x + dx * 16}" y1="{y}" x2="{x}" y2="{y}" stroke="{color}" stroke-width="2.2"/>',
            f'  <circle cx="{x + dx * 21}" cy="{y}" r="4.5" fill="#F4F7FB" stroke="{color}" stroke-width="2.1"/>',
        ]

    # 1) inventario_evento.id_evento (1) -> reserva_entrada.id_evento (0..N)
    p1 = col_positions["inventario_evento"]
    p2 = col_positions["reserva_entrada"]
    p3 = col_positions["entrada"]

    x1_out = p1["x"] + p1["w"]
    y1_out = p1["row_y"]["id_evento"]
    x2_in = p2["x"]
    y2_in = p2["row_y"]["id_evento"]
    mid12 = (x1_out + x2_in) / 2.0

    rel_color_1 = "#1B365D"
    svg.append(
        f'  <path d="M {x1_out} {y1_out} L {mid12} {y1_out} L {mid12} {y2_in} L {x2_in} {y2_in}" '
        f'fill="none" stroke="{rel_color_1}" stroke-width="2.4"/>'
    )
    svg.extend(draw_crows_foot_one(x1_out, y1_out, "right", rel_color_1))
    svg.extend(draw_crows_foot_zero_many(x2_in, y2_in, "left", rel_color_1))
    # Etiqueta 1:0..N
    svg.append(f'  <rect x="{mid12 - 38}" y="{min(y1_out, y2_in) - 34}" width="76" height="22" rx="6" fill="#FFFFFF" stroke="{rel_color_1}" stroke-width="1.2"/>')
    svg.append(f'  <text x="{mid12}" y="{min(y1_out, y2_in) - 19}" text-anchor="middle" class="mono" font-size="11" font-weight="700" fill="{rel_color_1}">1 : 0..N</text>')

    # 2) reserva_entrada.id_reserva (1) -> entrada.id_reserva (0..N)
    x2_out = p2["x"] + p2["w"]
    y2_out = p2["row_y"]["id_reserva"]
    x3_in = p3["x"]
    y3_in = p3["row_y"]["id_reserva"]
    mid23 = (x2_out + x3_in) / 2.0

    rel_color_2 = "#0D5C63"
    svg.append(
        f'  <path d="M {x2_out} {y2_out} L {mid23} {y2_out} L {mid23} {y3_in} L {x3_in} {y3_in}" '
        f'fill="none" stroke="{rel_color_2}" stroke-width="2.4"/>'
    )
    svg.extend(draw_crows_foot_one(x2_out, y2_out, "right", rel_color_2))
    svg.extend(draw_crows_foot_zero_many(x3_in, y3_in, "left", rel_color_2))
    svg.append(f'  <rect x="{mid23 - 38}" y="{min(y2_out, y3_in) - 34}" width="76" height="22" rx="6" fill="#FFFFFF" stroke="{rel_color_2}" stroke-width="1.2"/>')
    svg.append(f'  <text x="{mid23}" y="{min(y2_out, y3_in) - 19}" text-anchor="middle" class="mono" font-size="11" font-weight="700" fill="{rel_color_2}">1 : 0..N</text>')

    # 3) inventario_evento.id_evento (1) -> entrada.id_evento (0..N) por canal superior (sin cruces ni ciclos!)
    top_channel_y = 142
    x1_top = p1["x"] + p1["w"] * 0.72
    x3_top = p3["x"] + p3["w"] * 0.28
    rel_color_3 = "#393E8F"
    svg.append(
        f'  <path d="M {x1_top} {card_top} L {x1_top} {top_channel_y} L {x3_top} {top_channel_y} L {x3_top} {card_top}" '
        f'fill="none" stroke="{rel_color_3}" stroke-width="2.3" stroke-dasharray="7 4"/>'
    )
    # Crow's foot vertical en extremos superiores
    # 1 en inventario_evento (arriba del borde superior)
    svg.append(f'  <line x1="{x1_top - 8}" y1="{card_top - 7}" x2="{x1_top + 8}" y2="{card_top - 7}" stroke="{rel_color_3}" stroke-width="2.2"/>')
    svg.append(f'  <line x1="{x1_top - 8}" y1="{card_top - 13}" x2="{x1_top + 8}" y2="{card_top - 13}" stroke="{rel_color_3}" stroke-width="2.2"/>')
    # 0..N en entrada (arriba del borde superior)
    svg.append(f'  <line x1="{x3_top}" y1="{card_top - 15}" x2="{x3_top - 9}" y2="{card_top}" stroke="{rel_color_3}" stroke-width="2.2"/>')
    svg.append(f'  <line x1="{x3_top}" y1="{card_top - 15}" x2="{x3_top + 9}" y2="{card_top}" stroke="{rel_color_3}" stroke-width="2.2"/>')
    svg.append(f'  <circle cx="{x3_top}" cy="{card_top - 20}" r="4.5" fill="#F4F7FB" stroke="{rel_color_3}" stroke-width="2.1"/>')
    mid_top = (x1_top + x3_top) / 2.0
    svg.append(f'  <rect x="{mid_top - 255}" y="{top_channel_y - 13}" width="510" height="26" rx="13" fill="#FFFFFF" stroke="{rel_color_3}" stroke-width="1.3"/>')
    svg.append(f'  <text x="{mid_top}" y="{top_channel_y + 4}" text-anchor="middle" class="sans" font-size="11.5" font-weight="600" fill="{rel_color_3}">1 : 0..N  ·  entrada.id_evento → inventario_evento.id_evento (FK directa · DAG acíclico)</text>')

    # ------------------------------------------------------------------
    # Tarjetas de colecciones (Entidades)
    # ------------------------------------------------------------------
    badge_styles = {
        "ID": ("#475569", "#F1F5F9"),
        "PK": ("#FFFFFF", "#D97706"),
        "FK": ("#FFFFFF", "#0284C7"),
        "EXT": ("#6D28D9", "#EDE9FE"),
    }

    for col_name in schema["collection_order"]:
        col = schema["collections"][col_name]
        pos = col_positions[col_name]
        meta = COLLECTION_META.get(
            col_name,
            {"title": col_name, "layer": "Colección", "color": "#1E293B", "accent": "#F1F5F9", "subtitle": ""},
        )
        x, y, w, h = pos["x"], pos["y"], pos["w"], pos["h"]

        # Cuerpo tarjeta
        svg.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#FFFFFF" stroke="{meta["color"]}" stroke-width="1.8" filter="url(#cardShadow)"/>')
        # Header con esquinas redondeadas arriba
        svg.append(f'  <path d="M {x+10} {y} L {x+w-10} {y} Q {x+w} {y} {x+w} {y+10} L {x+w} {y+header_h} L {x} {y+header_h} L {x} {y+10} Q {x} {y} {x+10} {y} Z" fill="{meta["color"]}"/>')
        svg.append(f'  <text x="{x + 16}" y="{y + 29}" class="mono" font-size="18" font-weight="700" fill="#FFFFFF">{html.escape(meta["title"])}</text>')
        svg.append(f'  <text x="{x + 16}" y="{y + 50}" class="sans" font-size="11.5" fill="#E2E8F0">{html.escape(meta["subtitle"])}</text>')
        # Badge de nivel DAG + conteo docs
        layer_txt = f'{meta["layer"]}  ·  {col["doc_count"]} docs'
        lw = len(layer_txt) * 6.4 + 18
        svg.append(f'  <rect x="{x + w - lw - 12:.1f}" y="{y + 12}" width="{lw:.1f}" height="22" rx="11" fill="#FFFFFF" fill-opacity="0.18"/>')
        svg.append(f'  <text x="{x + w - lw / 2 - 12:.1f}" y="{y + 26.5}" text-anchor="middle" class="sans" font-size="10.5" font-weight="600" fill="#FFFFFF">{html.escape(layer_txt)}</text>')

        # Sub-cabecera de columnas
        ch_y = y + header_h
        svg.append(f'  <rect x="{x + 1}" y="{ch_y}" width="{w - 2}" height="{col_hdr_h}" fill="{meta["accent"]}"/>')
        svg.append(f'  <line x1="{x}" y1="{ch_y + col_hdr_h}" x2="{x + w}" y2="{ch_y + col_hdr_h}" stroke="#CBD5E1" stroke-width="1"/>')
        svg.append(f'  <text x="{x + 14}" y="{ch_y + 18}" class="sans" font-size="10.5" font-weight="700" fill="#334155">LLAVE</text>')
        svg.append(f'  <text x="{x + 86}" y="{ch_y + 18}" class="sans" font-size="10.5" font-weight="700" fill="#334155">ATRIBUTO</text>')
        svg.append(f'  <text x="{x + 305}" y="{ch_y + 18}" class="sans" font-size="10.5" font-weight="700" fill="#334155">TIPO BSON / RESTRICCIÓN</text>')
        svg.append(f'  <text x="{x + w - 14}" y="{ch_y + 18}" text-anchor="end" class="sans" font-size="10.5" font-weight="700" fill="#334155">NULABILIDAD</text>')

        # Filas de atributos
        for r_idx, fld in enumerate(col["fields"]):
            ry = ch_y + col_hdr_h + r_idx * row_h
            bg = "#FFFFFF" if r_idx % 2 == 0 else "#F8FAFC"
            svg.append(f'  <rect x="{x + 1}" y="{ry}" width="{w - 2}" height="{row_h}" fill="{bg}"/>')
            svg.append(f'  <line x1="{x + 1}" y1="{ry + row_h}" x2="{x + w - 1}" y2="{ry + row_h}" stroke="#EEF2F6" stroke-width="0.8"/>')

            # Badges de llave (PK / FK / EXT / ID)
            bx = x + 12
            for b in fld["badges"][:2]:
                fg, bbg = badge_styles.get(b, ("#334155", "#E2E8F0"))
                bw = 30 if len(b) == 2 else 34
                svg.append(f'  <rect x="{bx}" y="{ry + 5.5}" width="{bw}" height="17" rx="4" fill="{bbg}"/>')
                svg.append(f'  <text x="{bx + bw / 2}" y="{ry + 17.5}" text-anchor="middle" class="mono" font-size="9.5" font-weight="700" fill="{fg}">{b}</text>')
                bx += bw + 4

            # Nombre atributo
            fname_weight = "700" if ("PK" in fld["badges"] or "FK" in fld["badges"]) else "500"
            fname_color = "#0F172A" if not fld["nullable"] else "#475569"
            svg.append(f'  <text x="{x + 86}" y="{ry + 18.5}" class="mono" font-size="11.5" font-weight="{fname_weight}" fill="{fname_color}">{html.escape(fld["name"])}</text>')

            # Tipo BSON
            svg.append(f'  <text x="{x + 305}" y="{ry + 18.5}" class="mono" font-size="10.8" fill="#334155">{html.escape(fld["type_display"])}</text>')

            # Nulabilidad pill
            if fld["nullable"]:
                n_bg, n_fg, n_txt = "#F1F5F9", "#64748B", "NULLABLE"
            else:
                n_bg, n_fg, n_txt = "#FEE2E2", "#991B1B", "NOT NULL"
            nw = 66
            svg.append(f'  <rect x="{x + w - nw - 12}" y="{ry + 5.5}" width="{nw}" height="17" rx="4" fill="{n_bg}"/>')
            svg.append(f'  <text x="{x + w - nw / 2 - 12}" y="{ry + 17.5}" text-anchor="middle" class="mono" font-size="9.2" font-weight="700" fill="{n_fg}">{n_txt}</text>')

        # Bloque de índices reales en el pie de la tarjeta
        iy = pos["idx_y"]
        svg.append(f'  <line x1="{x + 1}" y1="{iy}" x2="{x + w - 1}" y2="{iy}" stroke="#CBD5E1" stroke-width="1.2"/>')
        svg.append(f'  <text x="{x + 14}" y="{iy + 17}" class="sans" font-size="10.5" font-weight="700" fill="{meta["color"]}">ÍNDICES VERIFICADOS EN MONGODB (sin TTL destructivo):</text>')
        idx_line_y = iy + 34
        for idx in col["indexes"]:
            if idx["name"] == "_id_":
                continue
            keys_str = ", ".join(f"{k}:{'ASC' if v == 1 else 'DESC'}" for k, v in idx["key"].items())
            uniq = " [UNIQUE]" if idx["unique"] else ""
            svg.append(
                f'  <text x="{x + 16}" y="{idx_line_y}" class="mono" font-size="10.2" fill="#334155">• {html.escape(idx["name"])} ({html.escape(keys_str)}){uniq}</text>'
            )
            idx_line_y += 19

    # ------------------------------------------------------------------
    # Franja de Referencias Externas a otros microservicios (BD2)
    # ------------------------------------------------------------------
    svg.append(f'  <rect x="50" y="{ext_strip_y}" width="{W - 100}" height="{ext_strip_h}" rx="10" fill="#FFFFFF" stroke="#7C3AED" stroke-width="1.5" stroke-dasharray="7 4" filter="url(#cardShadow)"/>')
    svg.append(f'  <text x="70" y="{ext_strip_y + 24}" class="sans" font-size="13" font-weight="700" fill="#5B21B6">REFERENCIAS EXTERNAS A OTROS MICROSERVICIOS (AISLAMIENTO DATABASE-PER-SERVICE · BD2 — SIN COLECCIONES REPLICADAS)</text>')

    ext_cards = [
        ("Panel Organizador & Catálogo", "Ref: id_evento", "Consume panel.evento.entradas.v1\nExpone /disponibilidad y /stock", "#1B365D"),
        ("Auth (auth-service)", "Ref: id_usuario", "Introspección HTTP /internal/validar-sesion\nNo persiste JWT ni credenciales", "#0F766E"),
        ("Promociones", "Ref: id_promocion", "Revalidación HTTP POST /api/promociones/evaluar\nSolo guarda ID y resultado aplicado", "#B45309"),
        ("Pasarela de Pagos", "Ref: id_pago / id_reserva", "HTTP INT-01 + RabbitMQ pago.*\nNo persiste client_secret ni tarjetas", "#BE123C"),
        ("Check-in & Notificaciones", "Ref: id_entrada / qr_data", "POST /api/checkin/tickets (JSON QR)\nRabbitMQ entradas.events (entradas_emitidas)", "#4338CA"),
    ]
    ec_w = (W - 100 - 40 - 4 * 16) / 5.0
    for idx_e, (etitle, eref, edesc, ecol) in enumerate(ext_cards):
        ex = 70 + idx_e * (ec_w + 16)
        ey = ext_strip_y + 36
        eh = 74
        svg.append(f'  <rect x="{ex:.1f}" y="{ey}" width="{ec_w:.1f}" height="{eh}" rx="8" fill="#FAF5FF" stroke="{ecol}" stroke-width="1.2"/>')
        svg.append(f'  <text x="{ex + 12:.1f}" y="{ey + 20}" class="sans" font-size="11.8" font-weight="700" fill="{ecol}">{html.escape(etitle)}</text>')
        svg.append(f'  <text x="{ex + 12:.1f}" y="{ey + 37}" class="mono" font-size="10.5" font-weight="700" fill="#1E293B">{html.escape(eref)}</text>')
        for li, line in enumerate(edesc.split("\n")):
            svg.append(f'  <text x="{ex + 12:.1f}" y="{ey + 53 + li * 14}" class="sans" font-size="9.8" fill="#475569">{html.escape(line)}</text>')

    # ------------------------------------------------------------------
    # Leyenda y Dominios ENUM (BD3 / BD4)
    # ------------------------------------------------------------------
    svg.append(f'  <rect x="50" y="{legend_y}" width="{W - 100}" height="{legend_h}" rx="10" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.3"/>')
    svg.append(f'  <text x="70" y="{legend_y + 24}" class="sans" font-size="12.5" font-weight="700" fill="#0F172A">LEYENDA DE NOTACIÓN Y DOMINIOS ENUM ($jsonSchema)</text>')

    legend_items = [
        ("PK", "#FFFFFF", "#D97706", "Llave primaria de negocio (índice unique)"),
        ("ID", "#475569", "#F1F5F9", "Identificador interno MongoDB (_id: ObjectId)"),
        ("FK", "#FFFFFF", "#0284C7", "Llave foránea interna verificada"),
        ("EXT", "#6D28D9", "#EDE9FE", "Identificador de referencia a otro squad"),
        ("NOT NULL", "#991B1B", "#FEE2E2", "Campo obligatorio (required y sin null)"),
        ("NULLABLE", "#64748B", "#F1F5F9", "Campo opcional o bsonType incluye null"),
    ]
    lx = 70
    ly = legend_y + 38
    for idx_l, (btxt, fg, bg, desc) in enumerate(legend_items):
        col_l = idx_l % 3
        row_l = idx_l // 3
        ix_l = lx + col_l * 335
        iy_l = ly + row_l * 30
        bw = 68 if len(btxt) > 3 else 38
        svg.append(f'  <rect x="{ix_l}" y="{iy_l}" width="{bw}" height="19" rx="4" fill="{bg}"/>')
        svg.append(f'  <text x="{ix_l + bw / 2}" y="{iy_l + 13}" text-anchor="middle" class="mono" font-size="9.5" font-weight="700" fill="{fg}">{btxt}</text>')
        svg.append(f'  <text x="{ix_l + bw + 8}" y="{iy_l + 13.5}" class="sans" font-size="11" fill="#334155">{html.escape(desc)}</text>')

    # Caja derecha con dominios enum reales
    enum_x = 1090
    svg.append(f'  <line x1="{enum_x - 20}" y1="{legend_y + 14}" x2="{enum_x - 20}" y2="{legend_y + legend_h - 14}" stroke="#E2E8F0" stroke-width="1.2"/>')
    enum_lines = [
        "tipo_entrada:    PAGADA | GRATUITA",
        "estado_gestion:  BORRADOR | PUBLICADO | FINALIZADO | CANCELADO",
        "estado_reserva:  RESERVADO | CONSOLIDADO | EXPIRADO | CANCELADO",
        "estado_entrada:  EMITIDA | ANULADA   ·   tipo_acceso: GENERAL",
    ]
    for ei, eline in enumerate(enum_lines):
        svg.append(f'  <text x="{enum_x}" y="{legend_y + 42 + ei * 18}" class="mono" font-size="10.8" fill="#1E293B">{html.escape(eline)}</text>')

    svg.append("</svg>")
    return "\n".join(svg)


def find_headless_browser() -> Optional[str]:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("msedge"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def render_svg_to_png(svg_path: Path, png_path: Path, width: int, height: int) -> bool:
    """Renderiza el SVG a un PNG nítido de alta resolución (2x DPI) usando Chrome/Edge headless."""
    browser = find_headless_browser()
    if not browser:
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        html_file = Path(tmpdir) / "render.html"
        svg_text = svg_path.read_text(encoding="utf-8")
        html_file.write_text(
            f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  html, body {{ margin: 0; padding: 0; width: {width}px; height: {height}px; overflow: hidden; background: #F4F7FB; }}
  svg {{ display: block; width: {width}px; height: {height}px; }}
</style>
</head>
<body>{svg_text}</body>
</html>""",
            encoding="utf-8",
        )
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            f"--window-size={width},{height}",
            f"--screenshot={str(png_path)}",
            html_file.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return res.returncode == 0 and png_path.exists() and png_path.stat().st_size > 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el diagrama relacional SVG, PNG y DBML desde MongoDB.")
    parser.add_argument("--uri", default=os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"), help="URI de conexión MongoDB")
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "ticketu_entradas_db"), help="Nombre de la base de datos")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent.parent / "diagrama_relacional"),
        help="Directorio de salida para SVG, PNG, DBML y JSON",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Extrayendo esquema en vivo desde {args.uri} / {args.db}...")
    schema = extract_live_schema(args.uri, args.db)

    json_path = out_dir / "schema_extraido_workstation.json"
    json_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"      -> Metadatos guardados en {json_path}")

    print("[2/4] Generando DBML actualizado...")
    dbml_path = out_dir / "schema_entradas_actualizado.dbml"
    dbml_path.write_text(generate_dbml(schema), encoding="utf-8")
    print(f"      -> DBML guardado en {dbml_path}")

    print("[3/4] Generando diagrama vectorial SVG...")
    svg_content = build_svg(schema)
    svg_path = out_dir / "diagrama_relacional_entradas.svg"
    svg_path.write_text(svg_content, encoding="utf-8")
    print(f"      -> SVG vectorial guardado en {svg_path}")

    # Extraer dimensiones exactas del SVG para renderizar PNG sin recorte
    import re
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg_content)
    svg_w, svg_h = (int(m.group(1)), int(m.group(2))) if m else (1960, 1220)

    print(f"[4/4] Renderizando PNG de alta resolución ({svg_w*2}x{svg_h*2} px)...")
    png_path = out_dir / "diagrama_relacional_entradas.png"
    ok = render_svg_to_png(svg_path, png_path, svg_w, svg_h)
    if ok:
        print(f"      -> PNG generado correctamente en {png_path} ({png_path.stat().st_size:,} bytes)")
    else:
        raise RuntimeError("No se encontró navegador Chromium/Edge para rasterizar el SVG a PNG.")


if __name__ == "__main__":
    main()
