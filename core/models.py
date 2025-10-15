from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    CheckConstraint,
    func,
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
    rol: Mapped[str] = mapped_column(String(20))

    # Relación cómoda (opcional)
    prestamos: Mapped[List["Prestamo"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"Usuario(id={self.id}, user={self.user!r})"


class Plantel(Base):
    __tablename__ = "planteles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    direccion: Mapped[str] = mapped_column(String(200))

    # Relación cómoda (opcional)
    laboratorios: Mapped[List["Laboratorio"]] = relationship(
        back_populates="plantel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"Plantel(id={self.id}, nombre={self.nombre!r})"


class Laboratorio(Base):
    __tablename__ = "laboratorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    ubicacion: Mapped[str] = mapped_column(String(160))
    capacidad: Mapped[int] = mapped_column(Integer)
    plantel_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("planteles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    plantel: Mapped[Optional[Plantel]] = relationship(back_populates="laboratorios")

    # Relación cómoda
    recursos: Mapped[List["Recurso"]] = relationship(
        back_populates="laboratorio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"Laboratorio(id={self.id}, nombre={self.nombre!r})"


class Recurso(Base):
    __tablename__ = "recursos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("laboratorios.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(80))            # UI lo hace obligatorio
    estado: Mapped[str] = mapped_column(String(40))          # "disponible", "prestado", "mantenimiento"
    specs: Mapped[str] = mapped_column(Text)

    laboratorio: Mapped[Laboratorio] = relationship(back_populates="recursos")

    # Relación cómoda
    prestamos: Mapped[List["Prestamo"]] = relationship(
        back_populates="recurso",
        cascade="all, delete-orphan",
        passive_deletes=True,
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
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime] = mapped_column(DateTime)
    estado: Mapped[str] = mapped_column(String(40), default="activa")

    def __repr__(self) -> str:
        return f"Reserva(id={self.id}, usuario_id={self.usuario_id}, laboratorio_id={self.laboratorio_id})"


class Prestamo(Base):
    """
    Usado por la UI como 'SolicitudModel'.
    Campos clave que la UI usa:
      - recurso_id (FK a recursos.id)
      - usuario_id (id de la sesión)
      - solicitante (string mostrado)
      - cantidad (int, default 1)
      - inicio, fin (datetimes)
      - estado (pendiente/aprobado/rechazado/entregado/devuelto)
      - comentario (texto opcional)
      - created_at (auto)
    """
    __tablename__ = "prestamos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    recurso_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recursos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    solicitante: Mapped[str] = mapped_column(String, nullable=False)

    cantidad: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    estado: Mapped[str] = mapped_column(String, nullable=False, default="pendiente")
    # estados: pendiente, aprobado, rechazado, entregado, devuelto

    comentario: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("cantidad >= 1", name="ck_prestamos_cantidad_pos"),
    )

    # Relaciones
    recurso: Mapped[Recurso] = relationship(back_populates="prestamos", lazy="joined")
    usuario: Mapped[Usuario] = relationship(back_populates="prestamos", lazy="joined")

    def __repr__(self) -> str:
        return f"Prestamo(id={self.id}, recurso_id={self.recurso_id}, usuario_id={self.usuario_id}, estado={self.estado!r})"
