import sys
import bcrypt
from sqlalchemy.orm import Session
from core.db import SessionLocal, engine
from core.models import Base, Usuario # Asegúrate que Usuario esté importado

# --- Password helpers (copiados de auth_service.py para autosuficiencia) ---
def hash_password(p: str) -> str:
    """Genera un hash bcrypt para la contraseña."""
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_admin(db: Session, nombre: str, correo: str, username: str, password: str):
    """
    Crea un nuevo usuario con rol 'admin'.
    Verifica si el usuario o correo ya existen.
    """
    # Validaciones básicas
    if not all([nombre, correo, username, password]):
        print("Error: Todos los campos son requeridos.")
        return
    if len(password) < 6:
        print("Error: La contraseña debe tener al menos 6 caracteres.")
        return

    # Verificar si ya existe
    existing_user = db.query(Usuario).filter(
        (Usuario.user == username) | (Usuario.correo == correo.lower())
    ).first()

    if existing_user:
        print(f"Error: El usuario '{username}' o el correo '{correo}' ya existen.")
        return

    # Crear el nuevo administrador
    try:
        hashed_password = hash_password(password)
        admin_user = Usuario(
            nombre=nombre.strip(),
            correo=correo.strip().lower(),
            user=username.strip(),
            password_hash=hashed_password,
            rol="admin" # Rol fijo como admin
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"¡Administrador '{admin_user.user}' creado exitosamente con ID {admin_user.id}!")
    except Exception as e:
        db.rollback()
        print(f"Error al crear el administrador: {e}")

if __name__ == "__main__":
    # Verifica si se pasaron los argumentos correctos
    if len(sys.argv) != 5:
        print("Uso: python create_admin.py \"<Nombre Completo>\" <correo> <username> <password>")
        sys.exit(1)

    # Lee los argumentos de la línea de comandos
    nombre_arg = sys.argv[1]
    correo_arg = sys.argv[2]
    username_arg = sys.argv[3]
    password_arg = sys.argv[4]

    # Crea las tablas si no existen (importante para la primera ejecución)
    Base.metadata.create_all(bind=engine)

    # Obtiene una sesión de base de datos
    db_session = SessionLocal()
    try:
        # Intenta crear el administrador
        create_admin(db_session, nombre_arg, correo_arg, username_arg, password_arg)
    finally:
        # Cierra la sesión
        db_session.close()
