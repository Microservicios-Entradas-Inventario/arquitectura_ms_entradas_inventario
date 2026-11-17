import os
import httpx
from datetime import datetime
from typing import Optional, Dict, List

class PanelService:
    BASE_URL = os.getenv("PANEL_SERVICE_URL", "http://ticketu-api-gateway:8080")

    @classmethod
    async def obtener_eventos_proximos(cls, limite: int = 50) -> List[Dict]:
        """Obtiene los eventos públicos publicados desde Panel vía API Gateway."""
        url = f"{cls.BASE_URL}/api/organizador/v1/organizador/eventos/proximos?limite={limite}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=3.0)
                if response.status_code == 200:
                    data = response.json()
                    return data if isinstance(data, list) else []
            except httpx.RequestError as exc:
                print(f"[Panel Sync] Error consultando eventos próximos de Panel: {exc}")
        return []

    @classmethod
    async def sincronizar_eventos_panel(cls, db) -> int:
        """Sincroniza en MongoDB (inventario_evento) los eventos publicados de Panel sin sobreescribir los existentes."""
        if db is None:
            return 0
        eventos = await cls.obtener_eventos_proximos(limite=50)
        sincronizados = 0
        for ev in eventos:
            id_evt = ev.get("id_evento")
            if not id_evt:
                continue
            tipo = str(ev.get("tipo_entrada") or "GRATUITA").upper()
            precio = int(ev.get("precio") or 0) if tipo == "PAGADA" else 0
            stock = int(ev.get("cantidad_entradas") or 100)
            doc = {
                "id_evento": id_evt,
                "nombre_evento": ev.get("nombre_evento") or f"Evento {id_evt}",
                "descripcion": ev.get("descripcion") or "",
                "fecha_evento": ev.get("fecha_evento") or "",
                "hora_evento": ev.get("hora_evento") or "",
                "lugar_ingreso": ev.get("direccion_evento") or "Por confirmar",
                "id_usuario": "usr-org-panel",
                "rol_usuario": "ORGANIZADOR",
                "tipo_entrada": "PAGADA" if tipo == "PAGADA" else "GRATUITA",
                "precio_unitario": precio,
                "stock_inicial": stock,
                "stock_actual": stock,
                "cantidad_entrada_reservada": 0,
                "cantidad_entrada_comprada": 0,
                "maximo_ticket": 6,
                "estado_gestion": str(ev.get("estado_gestion") or "PUBLICADO").upper(),
                "fecha_actualizacion": datetime.utcnow(),
            }
            res = await db.inventario_evento.update_one(
                {"id_evento": id_evt},
                {"$setOnInsert": doc},
                upsert=True,
            )
            if res.upserted_id is not None:
                sincronizados += 1
        if sincronizados:
            print(f"[Panel Sync] {sincronizados} evento(s) nuevo(s) sincronizado(s) desde Panel.")
        return sincronizados

    @classmethod
    async def obtener_info_evento(cls, id_evento: str, token_sesion: Optional[str] = None) -> Optional[Dict]:
        """
        Contrato: Panel Organizador <-> Entradas / Inventario v3.0
        Consumidor: Entradas / Inventario
        Propósito: Fallback para rehidratar BD, o consultar estado ("CANCELADO") antes de operar.
        """
        url = f"{cls.BASE_URL}/api/organizador/v1/panel/eventos/{id_evento}"
        headers = {}
        if token_sesion:
            headers["Cookie"] = f"jwt={token_sesion}"
        
        async with httpx.AsyncClient() as client:
            try:
                # SLA < 300ms según contrato
                response = await client.get(url, headers=headers, timeout=0.3)
                if response.status_code == 200:
                    return response.json()
                return None
            except httpx.RequestError as exc:
                print(f"Error comunicando con Panel Organizador: {exc}")
                return None
