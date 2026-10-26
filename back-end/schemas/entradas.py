from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class InventarioResponse(BaseModel):
    id_evento: str
    stock_actual: int
    tipo_entrada: str
    precio_unitario: int

class ProcesarCompraRequest(BaseModel):
    id_evento: str = Field(..., description="Identificador único del evento seleccionado.")
    tipo_entrada: str = Field(..., description="Tipo de entrada seleccionada (ej. General, VIP, Gratuita, Pagada).")
    cantidad: int = Field(gt=0, description="Cantidad de entradas a comprar.")
    token_sesion: str = Field(..., description="Token de autenticación enviado por Catálogo.")

class ProcesarCompraResponse(BaseModel):
    nuevo_stock: int

# ==========================================
# HU-03: Reserva Temporal de Cupo (Hold)
# ==========================================
class CrearReservaHoldRequest(BaseModel):
    id_evento: str = Field(..., description="Identificador único del evento para reservar.")
    id_usuario: str = Field(..., description="Identificador del usuario que solicita la reserva.")
    cantidad: int = Field(default=1, gt=0, description="Cantidad de cupos a reservar temporalmente.")
    nombre_usuario: Optional[str] = Field(default=None, description="Nombre del cliente o asistente.")
    correo_usuario: Optional[str] = Field(default=None, description="Correo electrónico del comprador.")
    tiempo_limite_minutos: int = Field(default=15, gt=0, le=60, description="Tiempo límite de vigencia de la reserva en minutos.")

class CrearReservaHoldResponse(BaseModel):
    hold_id: str = Field(..., description="Identificador único de la reserva temporal (holdId).")
    id_reserva: str = Field(..., description="ID de la reserva en el sistema de entradas.")
    id_evento: str
    id_usuario: str
    cantidad_entrada: int
    monto_total: int
    estado_reserva: str
    fecha_creacion: datetime
    fecha_expiracion: datetime
    tiempo_restante_segundos: int

class DetalleReservaResponse(BaseModel):
    id_reserva: str
    hold_id: str
    id_evento: str
    id_usuario: str
    cantidad_entrada: int
    monto_total: int
    estado_reserva: str
    fecha_expiracion: Optional[datetime] = None
    tiempo_restante_segundos: int = 0
    expirada: bool = False

# ==========================================
# HU-04: Visualización de Detalles de Entrada Adquirida
# ==========================================
class DetalleEntradaAdquirida(BaseModel):
    id_entrada: str = Field(..., description="Código alfanumérico único e inmutable de la entrada.")
    id_reserva: str
    id_evento: str
    nombre_evento: str = Field(..., description="Nombre comercial del evento.")
    id_usuario: str
    nombre_usuario: str = Field(..., description="Nombre del asistente acreditado.")
    correo_usuario: Optional[str] = None
    tipo_acceso: str = Field(default="GENERAL", description="Tipo de acceso físico general (sin asignación de mapa numérico).")
    lugar_ingreso: str = Field(default="Puerta Principal - Acceso General", description="Condición física de ingreso al recinto.")
    precio_final_pagado: int = Field(..., description="Precio final pagado inmutable en la base de datos.")
    estado_entrada: str = Field(default="EMITIDA", description="Estado de la entrada (EMITIDA, ANULADA).")
    nombre_archivo_qr: str
    qr_data: Any = Field(..., description="Objeto o URL de validación del código QR.")
    fecha_emision: datetime

# ==========================================
# HU-05: Recepción de Código QR de Acceso
# ==========================================
class CodigoQRAccesoResponse(BaseModel):
    id_entrada: str
    id_evento: str
    nombre_asistente: str
    nombre_evento: str
    lugar_ingreso: str
    tipo_acceso: str
    qr_data: Any = Field(..., description="Objeto o URL directa del código QR.")
    qr_payload: Dict[str, Any] = Field(..., description="Contenido estructurado del QR con id_evento e id_entrada.")
    habilitado_checkin: bool = Field(default=True, description="Indica si la entrada ya fue notificada y habilitada en el control de acceso.")

