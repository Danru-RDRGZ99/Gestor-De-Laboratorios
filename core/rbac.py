from core.db import SessionLocal, engine
from core.models import Base, Usuario, Plantel, Laboratorio, Recurso, Reserva, Prestamo

ALLOWED={
    "admin":["dashboard","planteles","laboratorios","recursos","reservas","usuarios"],
    "docente":["dashboard","recursos","reservas","ajustes"],
    "estudiante":["dashboard","recursos","ajustes"],
}
def allowed_routes(role:str):
    return ALLOWED.get(role,["dashboard"])
