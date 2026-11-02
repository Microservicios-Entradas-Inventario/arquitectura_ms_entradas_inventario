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
    cantidad: int = Field(gt=0, description="Cantidad de entradas a comprar (1 a 100 según contrato Pagos v2.3).")
    token_sesion: Optional[str] = Field(default=None, description="Opcional por retrocompatibilidad con Catálogo; en v2.3 se prioriza el header Cookie (jwt=<token>).")
    metodo: Optional[str] = Field(default="formulario", description="Método de cobro en Pagos v2.3: 'formulario' o 'checkout'.")

class ProcesarCompraResponse(BaseModel):
    nuevo_stock: int
    id_reserva: Optional[str] = None
    id_pago: Optional[str] = None
    estado_pago: Optional[str] = None
    url_checkout: Optional[str] = None
    metodo: Optional[str] = None
    fecha_creacion: Optional[str] = None
    fecha_expiracion: Optional[str] = None

# ==========================================
# HU-03: Reserva Temporal de Cupo (Hold)
# ==========================================
class CrearReservaHoldRequest(BaseModel):
    id_evento: str = Field(..., description="Identificador único del evento para reservar.")
    id_usuario: Optional[str] = Field(default=None, description="Identificador del usuario (si viene la cookie 'jwt', se obtiene automáticamente desde Auth).")
    cantidad: int = Field(default=1, gt=0, le=100, description="Cantidad de cupos a reservar temporalmente (1 a 100).")
    nombre_usuario: Optional[str] = Field(default=None, description="Nombre del cliente (obtenido automáticamente de Auth desde la cookie 'jwt').")
    rut_usuario: Optional[str] = Field(default=None, description="RUT del cliente (obtenido automáticamente de Auth desde la cookie 'jwt').")
    correo_usuario: Optional[str] = Field(default=None, description="Correo electrónico del comprador (obtenido automáticamente de Auth desde la cookie 'jwt').")
    token_sesion: Optional[str] = Field(default=None, description="Opcional; en v2.3 se usa el header Cookie (jwt=<token>).")
    tiempo_limite_minutos: int = Field(default=15, gt=0, le=60, description="Tiempo límite de vigencia de la reserva en minutos.")

class CrearReservaHoldResponse(BaseModel):
    hold_id: str = Field(..., description="Identificador único de la reserva temporal (holdId).")
    id_reserva: str = Field(..., description="ID de la reserva en el sistema de entradas.")
    id_evento: str
    id_usuario: str
    nombre_usuario: Optional[str] = None
    rut_usuario: Optional[str] = None
    correo_usuario: Optional[str] = None
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
    nombre_usuario: Optional[str] = None
    rut_usuario: Optional[str] = None
    correo_usuario: Optional[str] = None
    cantidad_entrada: int
    cantidad_entradas: int = Field(default=0, description="Alias compatible con Contrato Pagos v2.3 (INT-01).")
    monto_total: int
    total: int = Field(default=0, description="Alias compatible con Contrato Pagos v2.3 (INT-01).")
    id_pago: Optional[str] = None
    estado_reserva: str
    fecha_expiracion: Optional[datetime] = None
    tiempo_restante_segundos: int = 0
    expirada: bool = False

class IniciarPagoReservaRequest(BaseModel):
    metodo: Optional[str] = Field(default="formulario", description="'formulario' (por defecto) o 'checkout'.")
    token_sesion: Optional[str] = Field(default=None, description="Opcional; en Contrato Pagos v2.3 se reenvía el header Cookie (jwt=<token>) tal cual.")

class AnularPagoReservaRequest(BaseModel):
    motivo: str = Field(
        default="Hold de la reserva vencido: el usuario pagó fuera de plazo",
        min_length=3,
        max_length=255,
        description="Razón de la anulación o reembolso en Pagos (3 a 255 caracteres)."
    )
    token_sesion: Optional[str] = Field(default=None, description="Opcional; en Contrato Pagos v2.3 se reenvía el header Cookie (jwt=<token>).")

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
    rut_usuario: Optional[str] = None
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
