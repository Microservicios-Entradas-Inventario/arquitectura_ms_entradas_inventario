from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["UP"])
    service: str = Field(..., examples=["entradas-service"])
    timestamp: str


class InventarioResponse(BaseModel):
    id_evento: str
    stock_actual: int
    tipo_entrada: str
    precio_unitario: int


class EventoFrontendResponse(BaseModel):
    id: str
    titulo: str
    fecha: str
    hora: str
    lugar: str
    descripcion: str
    tipoEntrada: str
    precio: int
    stockTotal: int
    stockDisponible: int
    maxTickets: int
    limiteGratuitoUsuario: Optional[int] = None
    estadoGestion: str


class DisponibilidadFrontendResponse(BaseModel):
    idEvento: str
    stockDisponible: int
    stockTotal: int
    tipoEntrada: str
    precio: int
    estadoGestion: str = "PUBLICADO"


class StockPanelResponse(BaseModel):
    id_evento: str
    stock: int


class UsuarioTicketCheckin(BaseModel):
    id_usuario: str
    rol_usuario: str


class ConsultaEntradaCheckinResponse(BaseModel):
    id_ticket: str
    id_entrada: str
    id_evento: str
    estado_entrada: str
    nombre_usuario: str
    usuario: UsuarioTicketCheckin


class ProcesarCompraRequest(BaseModel):
    id_evento: str = Field(..., description="Identificador único del evento seleccionado.")
    tipo_entrada: str = Field(..., description="Tipo de entrada seleccionada (GRATUITA o PAGADA).")
    cantidad: int = Field(gt=0, le=100, description="Cantidad de entradas a comprar (1 a 100 según contrato Pagos v2.3).")
    token_sesion: Optional[str] = Field(default=None, description="Opcional por retrocompatibilidad con Catálogo; se prioriza el header Cookie (jwt=<token>).")
    metodo: Optional[str] = Field(default="formulario", description="Método de cobro en Pagos: 'formulario' o 'checkout'.")
    nombre_codigo: Optional[str] = Field(default=None, description="Código promocional aplicado para revalidar con Promociones y transmitir a Pagos.")
    id_promocion: Optional[str] = Field(default=None, description="Identificador de la promoción aplicada.")
    porcentaje_descuento: int = Field(default=0, ge=0, le=100, description="Porcentaje de descuento referencial (siempre revalidado con Promociones).")


class ProcesarCompraResponse(BaseModel):
    nuevo_stock: int
    id_reserva: Optional[str] = None
    id_pago: Optional[str] = None
    estado_pago: Optional[str] = None
    url_checkout: Optional[str] = None
    metodo: Optional[str] = None
    fecha_creacion: Optional[str] = None
    fecha_expiracion: Optional[str] = None
    entradas_emitidas: Optional[List[str]] = None


# ==========================================
# HU-03: Reserva Temporal de Cupo (Hold)
# ==========================================
class CrearReservaHoldRequest(BaseModel):
    id_evento: str = Field(..., description="Identificador único del evento para reservar.")
    id_usuario: Optional[str] = Field(default=None, description="Obtenido automáticamente desde Auth mediante la cookie 'jwt'.")
    cantidad: int = Field(default=1, gt=0, le=100, description="Cantidad de cupos a reservar temporalmente (1 a 100).")
    nombre_usuario: Optional[str] = Field(default=None, description="Obtenido automáticamente desde Auth mediante la cookie 'jwt'.")
    rut_usuario: Optional[str] = Field(default=None, description="Obtenido automáticamente desde Auth mediante la cookie 'jwt'.")
    correo_usuario: Optional[str] = Field(default=None, description="Obtenido automáticamente desde Auth mediante la cookie 'jwt'.")
    token_sesion: Optional[str] = Field(default=None, description="Opcional por compatibilidad; se prioriza el header Cookie (jwt=<token>).")
    tiempo_limite_minutos: int = Field(default=15, gt=0, le=60, description="Tiempo límite de vigencia de la reserva en minutos.")
    nombre_codigo: Optional[str] = Field(default=None, description="Código promocional aplicado para revalidar con Promociones y transmitir a Pagos.")
    id_promocion: Optional[str] = Field(default=None, description="Identificador de la promoción aplicada.")
    porcentaje_descuento: int = Field(default=0, ge=0, le=100, description="Porcentaje de descuento referencial (siempre revalidado con Promociones).")


class CrearReservaHoldResponse(BaseModel):
    hold_id: str = Field(..., description="Identificador único de la reserva temporal (holdId).")
    id_reserva: str = Field(..., description="ID de la reserva en el sistema de entradas.")
    id_evento: str
    id_usuario: str
    nombre_usuario: Optional[str] = None
    rut_usuario: Optional[str] = None
    correo_usuario: Optional[str] = None
    cantidad_entrada: int
    id_promocion: Optional[str] = None
    nombre_codigo: Optional[str] = None
    porcentaje_descuento: float = 0
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
    cantidad_entradas: int = Field(default=0, description="Alias compatible con Contrato Pagos (INT-01).")
    monto_total: int
    total: int = Field(default=0, description="Alias compatible con Contrato Pagos (INT-01).")
    nombre_codigo: Optional[str] = Field(default=None, description="Código promocional validado asociado a la reserva.")
    id_promocion: Optional[str] = None
    porcentaje_descuento: int = 0
    id_pago: Optional[str] = None
    estado_reserva: str
    estado: str = Field(default="", description="Alias compatible con Contrato Pagos (INT-01).")
    fecha_expiracion: Optional[datetime] = None
    tiempo_restante_segundos: int = 0
    expirada: bool = False


class IniciarPagoReservaRequest(BaseModel):
    metodo: Optional[str] = Field(default="formulario", description="'formulario' (por defecto) o 'checkout'.")
    token_sesion: Optional[str] = Field(default=None, description="Opcional; se prioriza el header Cookie (jwt=<token>).")


class AnularPagoReservaRequest(BaseModel):
    motivo: str = Field(
        default="Hold de la reserva vencido: el usuario pagó fuera de plazo",
        min_length=3,
        max_length=255,
        description="Razón de la anulación o reembolso en Pagos (3 a 255 caracteres).",
    )
    token_sesion: Optional[str] = Field(default=None, description="Opcional; se prioriza el header Cookie (jwt=<token>).")


class CancelarReservaResponse(BaseModel):
    mensaje: str
    id_reserva: str
    cupos_liberados: int
    id_pago: Optional[str] = None
    resultado_reembolso_pagos: Optional[Dict[str, Any]] = None


class EstadoPagoReservaResponse(BaseModel):
    id_reserva: str
    id_pago: str
    estado_pago: str
    estado_reserva: str
    entradas_emitidas: List[str]
    detalle_pago: Dict[str, Any]


class EmisionDirectaRequest(BaseModel):
    id_evento: str = Field(..., description="ID del evento gratuito.")
    id_usuario: Optional[str] = Field(default=None, description="Ignorado si hay sesión Auth; se toma siempre desde Auth.")
    nombre_comprador: Optional[str] = Field(default=None, description="Obtenido automáticamente desde Auth.")
    correo_comprador: Optional[str] = Field(default=None, description="Obtenido automáticamente desde Auth.")
    cantidad_entradas: int = Field(default=1, gt=0, le=100, description="Cantidad de entradas gratuitas a emitir.")
    precio_final: int = Field(default=0, ge=0, description="Solo se permiten eventos gratuitos ($0) por emisión directa.")
    id_reserva: Optional[str] = Field(default=None, description="Reservado para compatibilidad interna.")


class EmisionDirectaResponse(BaseModel):
    idEntrada: str
    entradasEmitidas: List[str]
    idEvento: str
    nombreEvento: str
    nombreComprador: str
    correoComprador: str
    tipoAcceso: str
    precioFinal: int
    cantidadEntradas: int
    qrData: str
    fechaEvento: str
    horaEvento: str
    lugarEvento: str
    fechaEmision: str
    registradoEnCheckin: bool


# ==========================================
# HU-04: Visualización de Detalles de Entrada Adquirida
# ==========================================
class DetalleEntradaAdquirida(BaseModel):
    id_entrada: str = Field(..., description="Código alfanumérico único e inmutable de la entrada.")
    id_reserva: str
    id_evento: str
    nombre_evento: str = Field(..., description="Nombre comercial del evento.")
    fecha_evento: Optional[str] = Field(default=None, description="Fecha programada del evento.")
    hora_evento: Optional[str] = Field(default=None, description="Hora programada del evento.")
    id_usuario: str
    nombre_usuario: str = Field(..., description="Nombre del asistente acreditado.")
    rut_usuario: Optional[str] = None
    correo_usuario: Optional[str] = None
    tipo_acceso: str = Field(default="GENERAL", description="Tipo de acceso físico general.")
    lugar_ingreso: str = Field(default="Puerta Principal - Acceso General", description="Lugar de ingreso al recinto.")
    precio_final_pagado: int = Field(..., description="Precio final pagado inmutable en la base de datos.")
    estado_entrada: str = Field(default="EMITIDA", description="Estado de la entrada (EMITIDA, ANULADA).")
    nombre_archivo_qr: str
    qr_data: Any = Field(..., description="URL directa del código QR de acceso.")
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
    qr_data: Any = Field(..., description="URL directa del código QR.")
    qr_payload: Dict[str, Any] = Field(..., description="Contenido estructurado del QR con id_evento e id_entrada.")
    habilitado_checkin: bool = Field(default=True, description="Indica si la entrada está habilitada en el control de acceso.")
