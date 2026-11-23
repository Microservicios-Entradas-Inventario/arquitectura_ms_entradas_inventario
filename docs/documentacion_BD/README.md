# Documentación Oficial de Base de Datos — Microservicio de Entradas e Inventario (`ticketu_entradas_db`)

Paquete completo y replicable de documentación técnica, diagrama relacional, diccionario de datos, scripts de creación y evidencias de verificación para la evaluación de Base de Datos (**BD1, BD2, BD3 y BD4**) del microservicio **Entradas e Inventario (`entradas-service`)** de la plataforma **TicketU**.

---

## Estructura de Entregables

```text
documentacion BD/
├── INFORME_CENTRALIZADO_BD_ENTRADAS.pdf                 # Informe único centralizado en PDF (todo integrado)
├── README.md                                            # Este índice maestro y guía de replicación
├── diagrama_relacional/
│   ├── diagrama_relacional_entradas.svg                 # Diagrama relacional actualizado (vectorial SVG)
│   ├── diagrama_relacional_entradas.png                 # Diagrama relacional actualizado (PNG alta resolución 2x)
│   ├── schema_entradas_actualizado.dbml                 # Definición DBML generada desde MongoDB
│   └── schema_extraido_workstation.json                 # Metadatos $jsonSchema e índices extraídos en vivo
├── diccionario_datos/
│   ├── DICCIONARIO_DE_DATOS.md                          # Diccionario completo (3 colecciones, 54 atributos, 14 índices)
│   └── diccionario_datos_entradas.csv                   # Exportación tabular CSV del diccionario de datos
├── documentacion_funcionamiento/
│   ├── VERIFICACION_FUNCIONAMIENTO_E_INTEGRACION.md     # Guía replicable BD1–BD4, aislamiento BD2 y consultas
│   └── resultados_ejecucion_consultas.json              # Salida JSON real de todas las consultas MongoDB + API
├── evidencias/
│   ├── 01_aislamiento_bd_y_colecciones_BD2.png
│   ├── 02_validadores_indices_y_esquema_BD3_BD4.png
│   ├── 03_inventario_y_consistencia_stock_BD1_BD4.png
│   ├── 04_integridad_referencial_y_join_3_niveles_BD1_BD4.png
│   ├── 05_referencias_externas_y_rechazo_datos_ajenos_BD2.png
│   ├── 06_consultas_integraciones_pagos_promociones_checkin_BD1.png
│   ├── 07_respuestas_api_servicios_propios_e_integraciones_BD1.png
│   └── 08_auditoria_nomenclatura_y_grafo_aciclico_BD3_BD4.png
└── scripts/
    ├── init_db_creacion_bd.js                           # Script de creación de la BD MongoDB (referencia oficial)
    ├── generar_diagrama_bd.py                           # Script generador del diagrama (SVG, PNG y DBML) desde MongoDB
    ├── generar_diccionario_datos.py                     # Script generador del diccionario (MD y CSV) desde MongoDB
    ├── ejecutar_verificacion_bd.js                      # Batería replicable de 9 consultas mongosh (BD1–BD4)
    └── generar_evidencias_y_pdf.py                      # Script generador de capturas reales y PDF centralizado
```

---

## Acceso Directo a los Documentos Principales

1. **Informe Centralizado Único (PDF):** [`INFORME_CENTRALIZADO_BD_ENTRADAS.pdf`](INFORME_CENTRALIZADO_BD_ENTRADAS.pdf)
2. **Diagrama Relacional Vectorial (SVG):** [`diagrama_relacional/diagrama_relacional_entradas.svg`](diagrama_relacional/diagrama_relacional_entradas.svg)
3. **Diagrama Relacional (PNG):** [`diagrama_relacional/diagrama_relacional_entradas.png`](diagrama_relacional/diagrama_relacional_entradas.png)
4. **Diccionario de Datos:** [`diccionario_datos/DICCIONARIO_DE_DATOS.md`](diccionario_datos/DICCIONARIO_DE_DATOS.md)
5. **Documentación Replicable de Funcionamiento, BD2 e Integración:** [`documentacion_funcionamiento/VERIFICACION_FUNCIONAMIENTO_E_INTEGRACION.md`](documentacion_funcionamiento/VERIFICACION_FUNCIONAMIENTO_E_INTEGRACION.md)

---

## Replicación en Workstation (Comandos Exactos)

```powershell
# 1. Ejecutar las 9 consultas de verificación sobre MongoDB de workstation (solo lectura / sin mutar datos)
Get-Content "scripts\ejecutar_verificacion_bd.js" -Raw | docker exec -i ticketu_entradas_mongo mongosh ticketu_entradas_db --quiet

# 2. Regenerar diagrama relacional (SVG + PNG + DBML) desde MongoDB
python scripts\generar_diagrama_bd.py --uri "mongodb://127.0.0.1:27017" --db "ticketu_entradas_db"

# 3. Regenerar diccionario de datos (MD + CSV) desde MongoDB
python scripts\generar_diccionario_datos.py --uri "mongodb://127.0.0.1:27017" --db "ticketu_entradas_db"

# 4. Regenerar capturas de evidencias e informe centralizado PDF
python scripts\generar_evidencias_y_pdf.py --container "ticketu_entradas_mongo" --uri "mongodb://127.0.0.1:27017" --db "ticketu_entradas_db"
```
