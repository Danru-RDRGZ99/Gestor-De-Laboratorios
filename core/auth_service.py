from __future__ import annotations
import bcrypt
from sqlalchemy import or_

# --- SOLUCIÓN: Unificar las importaciones para usar siempre rutas relativas ---
from .db import SessionLocal, engine
from .models import Base, Usuario, Plantel, Laboratorio, Recurso, Reserva, Prestamo


# --------------------------------------------------------------------------------------
# Inicialización de BD
# --------------------------------------------------------------------------------------
def init_db(create_dev_admin: bool = False) -> None:
    """
    Crea tablas si no existen. Si `create_dev_admin=True`, crea un admin por defecto
    (user: admin, pass: admin123) solo si no existe.
    """
    Base.metadata.create_all(bind=engine)
    if create_dev_admin:
        _ensure_dev_admin()


def _ensure_dev_admin() -> None:
    db = SessionLocal()
    try:
        admin = db.query(Usuario).filter(Usuario.user == "admin").first()
        if not admin:
            print("INFO: Creando usuario admin por defecto (admin / admin123)") # Mensaje informativo
            u = Usuario(
                nombre="Administrador",
                correo="admin@example.com",
                user="admin",
                password_hash=hash_password("admin123"),
                rol="admin",
            )
            db.add(u)
            db.commit()
        else:
            print("INFO: Usuario admin ya existe.") # Mensaje informativo
    except Exception as e:
        print(f"ERROR: No se pudo verificar/crear el usuario admin: {e}") # Mensaje de error
        db.rollback()
    finally:
        db.close()


# --------------------------------------------------------------------------------------
# Password helpers
# --------------------------------------------------------------------------------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str | bytes) -> bool:
    h_bytes = h.encode("utf-8") if isinstance(h, str) else h
    return bcrypt.checkpw(p.encode("utf-8"), h_bytes)


# --------------------------------------------------------------------------------------
# Auth API
# --------------------------------------------------------------------------------------
def login(username_or_email: str, password: str):
    """
    Autentica por usuario O correo. Devuelve dict con campos que la UI espera
    o None si falla.
    """
    username_or_email = (username_or_email or "").strip()
    # --- MENSAJES DE DEPURACIÓN ---
    print(f"\nDEBUG: Intentando login para: '{username_or_email}'")
    # --- FIN MENSAJES DE DEPURACIÓN ---

    db = SessionLocal()
    try:
        u = (
            db.query(Usuario)
            .filter(
                or_(
                    Usuario.user == username_or_email,
                    Usuario.correo == username_or_email.lower(),
                )
            )
            .first()
        )

        # --- MENSAJES DE DEPURACIÓN ---
        print(f"DEBUG: Usuario encontrado: {u is not None}")
        if u:
            print(f"DEBUG: Usuario ID: {u.id}, User: {u.user}, Rol: {u.rol}")
        # --- FIN MENSAJES DE DEPURACIÓN ---

        if not u:
            return None # Usuario no encontrado

        # --- MENSAJES DE DEPURACIÓN ---
        is_password_correct = verify_password(password or "", u.password_hash)
        print(f"DEBUG: Verificación de contraseña: {is_password_correct}")
        # --- FIN MENSAJES DE DEPURACIÓN ---

        if not is_password_correct:
            return None # Contraseña incorrecta

        # Si todo está bien, devuelve los datos del usuario
        return {
            "id": u.id,
            "nombre": u.nombre,
            "user": u.user,
            "rol": u.rol,
            "correo": u.correo,
        }
    except Exception as e:
        print(f"ERROR: Excepción durante el login: {e}") # Error inesperado
        return None
    finally:
        db.close()


ALLOWED_ROLES = {"admin", "docente", "estudiante"}


def create_user(nombre: str, correo: str, user: str, password: str, rol: str):
    """
    Crea un usuario. Roles permitidos: admin, docente, estudiante.
    Retorna (ok: bool, payload: dict|str)
    """
    nombre = (nombre or "").strip()
    correo = (correo or "").strip().lower()
    # SOLUCIÓN: Usar consistentemente el parámetro 'user'
    user_param = (user or "").strip()
    rol_norm = (rol or "").strip().lower()

    if rol_norm not in ALLOWED_ROLES:
        return False, "Rol no permitido (usa: admin, docente o estudiante)"
    if not nombre or not correo or not user_param or not password:
        return False, "Campos incompletos"
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres"

    db = SessionLocal()
    try:
        # SOLUCIÓN: Usar consistentemente 'user_param' para la consulta
        if db.query(Usuario).filter(Usuario.user == user_param).first():
            return False, "El usuario ya existe"
        if db.query(Usuario).filter(Usuario.correo == correo).first():
            return False, "El correo ya está registrado"

        u = Usuario(
            nombre=nombre,
            correo=correo,
            # SOLUCIÓN: Usar consistentemente 'user_param' al crear el objeto
            user=user_param,
            password_hash=hash_password(password),
            rol=rol_norm,
        )
        db.add(u)
        db.commit()
        db.refresh(u)

        return True, {
            "id": u.id,
            "nombre": u.nombre,
            "user": u.user,
            "rol": u.rol,
            "correo": u.correo,
        }
    except Exception as e:
        db.rollback()
        print(f"ERROR: Excepción al crear usuario: {e}") # Mensaje de error
        return False, f"Error interno al crear usuario: {e}"
    finally:
        db.close()