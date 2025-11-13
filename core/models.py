from __future__ import annotations

from datetime import datetime, time, date # Added time, date
from typing import List, Optional
# Ensure db is imported if you run create_all from here
# from core.db import engine 

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
    func,
    Time,  # <-- Added Time
    Date,  # <-- Added Date
    Boolean # <-- Added Boolean
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ============================
#           MODELOS
# ============================

class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    user: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str] = mapped_column(String(20)) # e.g., 'admin', 'docente', 'estudiante'

    # Relationships
    prestamos: Mapped[List["Prestamo"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reservas: Mapped[List["Reserva"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan", # Because Reserva FK has ondelete="CASCADE"
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"Usuario(id={self.id}, user={self.user!r}, rol={self.rol!r})"


class Plantel(Base):
    __tablename__ = "planteles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    direccion: Mapped[str] = mapped_column(String(200))

    # Relationships
    laboratorios: Mapped[List["Laboratorio"]] = relationship(
        back_populates="plantel",
        cascade="all, delete-orphan", # If plantel deleted, its labs are deleted
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"Plantel(id={self.id}, nombre={self.nombre!r})"


class Laboratorio(Base):
    __tablename__ = "laboratorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    ubicacion: Mapped[Optional[str]] = mapped_column(String(160), nullable=True) # Explicitly nullable
    capacidad: Mapped[int] = mapped_column(Integer, default=0)
    plantel_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("planteles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    plantel: Mapped[Optional[Plantel]] = relationship(back_populates="laboratorios")
    recursos: Mapped[List["Recurso"]] = relationship(
        back_populates="laboratorio",
        cascade="all, delete-orphan", # If lab deleted, its resources are deleted
        passive_deletes=True,
    )
    reservas: Mapped[List["Reserva"]] = relationship(
        back_populates="laboratorio",
        # No cascade here, RESTRICT on FK prevents deletion
    )
    # --- Relationships for Schedule ---
    reglas_horario: Mapped[List["ReglaHorario"]] = relationship(
        back_populates="laboratorio",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    excepciones_horario: Mapped[List["ExcepcionHorario"]] = relationship(
        back_populates="laboratorio",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    # --- End Schedule Relationships ---

    def __repr__(self) -> str:
        return f"Laboratorio(id={self.id}, nombre={self.nombre!r})"


class Recurso(Base):
    __tablename__ = "recursos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("laboratorios.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(80))
    estado: Mapped[str] = mapped_column(String(40))
    specs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    laboratorio: Mapped[Laboratorio] = relationship(back_populates="recursos")
    prestamos: Mapped[List["Prestamo"]] = relationship(
        back_populates="recurso",
        # No cascade here, RESTRICT on FK prevents deletion
    )

    def __repr__(self) -> str:
        return f"Recurso(id={self.id}, tipo={self.tipo!r}, estado={self.estado!r})"


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    laboratorio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("laboratorios.id", ondelete="RESTRICT"), index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(40), default="activa")

    google_event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    usuario: Mapped[Usuario] = relationship(back_populates="reservas")
    laboratorio: Mapped[Laboratorio] = relationship(back_populates="reservas")

    def __repr__(self) -> str:
        return f"Reserva(id={self.id}, lab={self.laboratorio_id}, user={self.usuario_id}, estado={self.estado!r})"


class Prestamo(Base):
    __tablename__ = "prestamos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recurso_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recursos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    solicitante: Mapped[str] = mapped_column(String(120), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False, default="pendiente", index=True)
    comentario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("cantidad >= 1", name="ck_prestamos_cantidad_pos"),
    )

    # Relationships
    recurso: Mapped[Recurso] = relationship(back_populates="prestamos", lazy="joined")
    usuario: Mapped[Usuario] = relationship(back_populates="prestamos", lazy="joined")

    def __repr__(self) -> str:
        return f"Prestamo(id={self.id}, recurso_id={self.recurso_id}, user={self.usuario_id}, estado={self.estado!r})"


# ============================
#       MODELOS HORARIO      # <<-- NUEVOS MODELOS AÑADIDOS
# ============================

class ReglaHorario(Base):
    __tablename__ = "reglas_horario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("laboratorios.id", ondelete="CASCADE"), nullable=True, index=True)
    dia_semana: Mapped[int] = mapped_column(Integer, index=True, comment="0=Lunes, 1=Martes, ..., 6=Domingo")
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    es_habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    tipo_intervalo: Mapped[Optional[str]] = mapped_column(String(50), default='disponible', nullable=True) # ej: disponible, descanso

    # Relación inversa
    laboratorio: Mapped[Optional["Laboratorio"]] = relationship(back_populates="reglas_horario")

    def __repr__(self) -> str:
        return f"<ReglaHorario id={self.id} lab={self.laboratorio_id} dia={self.dia_semana} {self.hora_inicio}-{self.hora_fin} enabled={self.es_habilitado}>"


class ExcepcionHorario(Base):
    __tablename__ = "excepciones_horario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("laboratorios.id", ondelete="CASCADE"), nullable=True, index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    hora_inicio: Mapped[Optional[time]] = mapped_column(Time, nullable=True) # Null = todo el día
    hora_fin: Mapped[Optional[time]] = mapped_column(Time, nullable=True)   # Null = todo el día
    es_habilitado: Mapped[bool] = mapped_column(Boolean, default=False) # Default a cerrar (ej. festivo)
    descripcion: Mapped[Optional[str]] = mapped_column(String(200), nullable=True) # Motivo

    # Relación inversa
    laboratorio: Mapped[Optional["Laboratorio"]] = relationship(back_populates="excepciones_horario")

    def __repr__(self) -> str:
        return f"<ExcepcionHorario id={self.id} lab={self.laboratorio_id} fecha={self.fecha} enabled={self.es_habilitado} desc={self.descripcion}>"


# --- Opcional: Para crear tablas si no existen ---
# Descomenta y ejecuta este archivo una vez si no usas Alembic
# if __name__ == "__main__":
#     from core.db import engine # Asegúrate que engine esté importado correctamente
#     print("Creando tablas (incluyendo reglas y excepciones de horario)...")
#     Base.metadata.create_all(bind=engine)
#     print("Tablas creadas (si no existían).")