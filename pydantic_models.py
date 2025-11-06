from pydantic import BaseModel, EmailStr, ConfigDict # Import ConfigDict for Pydantic v2
from typing import Optional, List, Dict
from datetime import datetime, time, date # Añadido time, date, Dict

# --- Base Schemas (for creation) ---

class PlantelBase(BaseModel):
    nombre: str
    direccion: str

class LaboratorioBase(BaseModel):
    nombre: str
    ubicacion: Optional[str] = ""
    capacidad: Optional[int] = 0
    plantel_id: int

class RecursoBase(BaseModel):
    laboratorio_id: int
    tipo: str
    estado: str
    specs: Optional[str] = ""

class ReservaBase(BaseModel):
    usuario_id: int
    laboratorio_id: int
    inicio: datetime
    fin: datetime

class PrestamoBase(BaseModel):
    recurso_id: int
    usuario_id: int
    # El campo 'solicitante' se añade en el schema de lectura
    cantidad: int = 1
    inicio: datetime
    fin: datetime
    comentario: Optional[str] = None

class UsuarioBase(BaseModel):
    nombre: str
    correo: EmailStr
    user: str
    rol: str

# --- Create Schemas (with required fields for POST/PUT) ---

class PlantelCreate(PlantelBase): pass
class LaboratorioCreate(LaboratorioBase): pass
class RecursoCreate(RecursoBase): pass
class ReservaCreate(ReservaBase): pass
class PrestamoCreate(PrestamoBase): pass
class UsuarioCreate(UsuarioBase):
    password: str

# --- Read Schemas (for GET, includes ID and nested data) ---

class Plantel(PlantelBase):
    id: int
    model_config = ConfigDict(from_attributes=True) # Use ConfigDict for Pydantic v2


class Laboratorio(LaboratorioBase):
    id: int
    plantel: Optional[Plantel] = None
    model_config = ConfigDict(from_attributes=True)

class Recurso(RecursoBase):
    id: int
    laboratorio: Optional[Laboratorio] = None
    model_config = ConfigDict(from_attributes=True)

# --- Define User Schema needed for nested Reserva ---
# (You might already have this or a similar one like 'Usuario')
class UsuarioSimple(BaseModel):
    id: int
    nombre: str
    user: str
    correo: str
    rol: str
    model_config = ConfigDict(from_attributes=True)

# =========================================================================
# --- INICIO DE LA CORRECCIÓN (Añadir usuario a Reserva) ---
# =========================================================================
class Reserva(ReservaBase):
    id: int
    estado: str
    google_event_id: Optional[str] = None

    # --- ADDED THIS FIELD ---
    usuario: UsuarioSimple # Include the related user object

    model_config = ConfigDict(from_attributes=True)
# =========================================================================
# --- FIN DE LA CORRECCIÓN ---
# =========================================================================

class Usuario(UsuarioBase): # This is likely your main User schema
    id: int
    model_config = ConfigDict(from_attributes=True)


class Prestamo(PrestamoBase):
    id: int
    estado: str
    created_at: datetime
    solicitante: str # Added solicitante here for read schema
    recurso: Recurso # Nested schema for related resource
    usuario: Usuario # Nested schema for related user
    model_config = ConfigDict(from_attributes=True)


# This schema might be redundant now if Reserva includes the full UsuarioSimple
# class ReservaConUsuario(BaseModel):
#     id: int
#     inicio: datetime
#     fin: datetime
#     usuario_id: int
#     usuario_nombre: str
#     # google_event_id: Optional[str] = None
#     model_config = ConfigDict(from_attributes=True)


# ============================
#     SCHEMAS HORARIO       #
# ============================
# ... (Schedule Schemas remain the same) ...
class ReglaHorarioBase(BaseModel):
    laboratorio_id: Optional[int] = None
    dia_semana: int # 0=Lunes, 6=Domingo
    hora_inicio: time
    hora_fin: time
    es_habilitado: bool = True
    tipo_intervalo: Optional[str] = 'disponible'

class ReglaHorarioCreate(ReglaHorarioBase):
    pass

class ReglaHorarioUpdate(BaseModel):
    laboratorio_id: Optional[int] = None
    dia_semana: Optional[int] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    es_habilitado: Optional[bool] = None
    tipo_intervalo: Optional[str] = None

class ReglaHorario(ReglaHorarioBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ExcepcionHorarioBase(BaseModel):
    laboratorio_id: Optional[int] = None
    fecha: date
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    es_habilitado: bool = False # Default a no habilitado (cerrado)
    descripcion: Optional[str] = None

class ExcepcionHorarioCreate(ExcepcionHorarioBase):
    pass

class ExcepcionHorarioUpdate(BaseModel):
    laboratorio_id: Optional[int] = None
    fecha: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    es_habilitado: Optional[bool] = None
    descripcion: Optional[str] = None

class ExcepcionHorario(ExcepcionHorarioBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class SlotHorario(BaseModel):
    inicio: datetime
    fin: datetime
    tipo: str

class HorarioCalculado(BaseModel):
    fecha: date
    slots: List[SlotHorario]


# --- Auth Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Usuario # Includes full user details on login

# --- Update Schemas ---

class ProfileUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[EmailStr] = None
    user: Optional[str] = None

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str


# --- Schemas with Counts ---
class UsuarioConteo(Usuario):
    reservas_count: int = 0
    prestamos_count: int = 0
    model_config = ConfigDict(from_attributes=True)