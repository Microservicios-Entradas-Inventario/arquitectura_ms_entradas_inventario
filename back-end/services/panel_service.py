import os
import httpx
from datetime import datetime
from typing import Optional, Dict, List


class PanelService:
    BASE_URL = os.getenv("PANEL_SERVICE_URL", "http://ticketu-api-gateway:8080")
    TIMEOUT_SECONDS = float(os.getenv("PANEL_TIMEOUT_SECONDS", "2.5"))

    @classmethod
    async def obtener_eventos_proximos(cls, limite: int = 50) -> List[Dict]:
        """Obtiene los eventos públicos publicados desde Panel vía API Gateway."""
        base_url = os.getenv("PANEL_SERVICE_URL", cls.BASE_URL)
        url = f"{base_url}/api/organizador/v1/organizador/eventos/proximos?limite={limite}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=cls.TIMEOUT_SECONDS)
                if response.status_code == 200:
                    data = response.json()
                    return data if isinstance(data, list) else []
                print(f"[Panel Sync] HTTP {response.status_code} al consultar eventos próximos en Panel.")
            except httpx.RequestError as exc:
                print(f"[Panel Sync] Error consultando eventos próximos de Panel: {exc}")
        return []

    @classmethod
    async def sincronizar_eventos_panel(cls, db) -> int:
        """
        Sincroniza en MongoDB (inventario_evento) los eventos publicados de Panel.
        Si el evento es nuevo lo inserta; si ya existe actualiza sus metadatos/estado sin sobrescribir
        las ventas ni reservas en curso.
        """
        if db is None:
            return 0
        eventos = await cls.obtener_eventos_proximos(limite=50)
        sincronizados = 0
        for ev in eventos:
            id_evt = ev.get("id_evento")
            if not id_evt:
                continue
            tipo = str(ev.get("tipo_entrada") or "GRATUITA").upper()
            tipo_norm = "PAGADA" if tipo == "PAGADA" else "GRATUITA"
            precio = int(ev.get("precio") or 0) if tipo_norm == "PAGADA" else 0
            raw_stock = ev.get("cantidad_entradas")
            stock = int(raw_stock) if raw_stock is not None else 100
            estado_raw = str(ev.get("estado_gestion") or "PUBLICADO").upper()
            estado_norm = (
                estado_raw
                if estado_raw in ("BORRADOR", "PUBLICADO", "FINALIZADO", "CANCELADO")
                else "PUBLICADO"
            )

            set_fields = {
                "nombre_evento": ev.get("nombre_evento") or f"Evento {id_evt}",
                "descripcion": ev.get("descripcion") or "",
                "fecha_evento": ev.get("fecha_evento") or "",
                "hora_evento": ev.get("hora_evento") or "",
                "lugar_ingreso": ev.get("direccion_evento") or "Por confirmar",
                "tipo_entrada": tipo_norm,
                "precio_unitario": precio,
                "estado_gestion": estado_norm,
                "fecha_actualizacion": datetime.utcnow(),
            }
            insert_only = {
                "id_evento": id_evt,
                "id_usuario": ev.get("id_usuario") or "usr-org-panel",
                "rol_usuario": "organizador",
                "stock_inicial": stock,
                "stock_actual": stock,
                "cantidad_entrada_reservada": 0,
                "cantidad_entrada_comprada": 0,
                "maximo_ticket": 6,
            }
            res = await db.inventario_evento.update_one(
                {"id_evento": id_evt},
                {"$set": set_fields, "$setOnInsert": insert_only},
                upsert=True,
            )
            if res.upserted_id is not None:
                sincronizados += 1
        if sincronizados:
            print(f"[Panel Sync] {sincronizados} evento(s) nuevo(s) sincronizado(s) desde Panel.")
        return sincronizados

    @classmethod
    async def obtener_info_evento(cls, id_evento: str, cookie_header: Optional[str] = None) -> Optional[Dict]:
        """
        Contrato: Panel Organizador <-> Entradas / Inventario v3.0
        Consumidor: Entradas / Inventario
        Propósito: Fallback para rehidratar BD o consultar estado ('CANCELADO') antes de operar.
        """
        base_url = os.getenv("PANEL_SERVICE_URL", cls.BASE_URL)
        url = f"{base_url}/api/organizador/v1/panel/eventos/{id_evento}"
        headers = {}
        if cookie_header:
            headers["Cookie"] = cookie_header if "jwt=" in cookie_header else f"jwt={cookie_header}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=cls.TIMEOUT_SECONDS)
                if response.status_code == 200:
                    return response.json()
                print(f"[Panel] HTTP {response.status_code} al consultar evento '{id_evento}' en Panel.")
                return None
            except httpx.RequestError as exc:
                print(f"[Panel] Error comunicando con Panel Organizador: {exc}")
                return None
