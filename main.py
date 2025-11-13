# --- Standard FastAPI and SQLAlchemy Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, Path
from sqlalchemy.orm import Session, joinedload
from typing import List, Annotated, Optional, Dict, Tuple
from datetime import datetime, timedelta, timezone, date, time
import traceback
import os
import base64

# --- Security and Authentication Imports ---
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

# --- Google Auth Imports (para /auth/google-token) ---
from google.oauth2 import id_token
from google.auth.exceptions import GoogleAuthError

# --- CAPTCHA Imports ---
from starlette.middleware.sessions import SessionMiddleware
from captcha.image import ImageCaptcha
from io import BytesIO
import random
import string

# --- Configuración y Otros ---
from starlette.config import Config
from starlette.responses import HTMLResponse, RedirectResponse, JSONResponse
import secrets

# --- Project-specific Core Imports ---
from core import auth_service, models, security, calendar_service, google_auth # Ensure calendar_service is imported
from core.db import SessionLocal
import pydantic_models as schemas

# --- Helper for Random Password ---
def generate_random_password(length=16):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))
# --- End Helper ---

# --- Load Configuration from environment variables (Railway) ---
# Railway proporciona las variables de entorno directamente
# --- End Configuration ---

# --- Database Initialization ---
# Se ejecutará automáticamente al iniciar la aplicación
# --- End Database Initialization ---

# --- FastAPI App Initialization ---
app = FastAPI(
    title="API del Gestor de Laboratorios",
    description="Backend para gestionar recursos, reservas y usuarios de laboratorios.",
    version="1.0.0"
)
# --- End App Initialization ---

# --- Middleware ---
# Usar variable de entorno para secret key en producción
SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "a-very-secret-key-please-change-in-production")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session_id",
    max_age=3600,
    same_site="lax",
    https_only=False
)
# --- End Middleware ---

# --- Pydantic Schemas for Request Bodies ---
class UsuarioAdminUpdate(BaseModel):
    nombre: Optional[str] = None
    user: Optional[str] = None
    correo: Optional[EmailStr] = None
    rol: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str
    captcha: str

class GoogleToken(BaseModel):
    id_token: str = Field(..., alias="idToken")
# --- End Schemas ---

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
DbSession = Annotated[Session, Depends(get_db)]
# --- End Database Dependency ---

# --- Security Dependencies ---
CurrentUser = Annotated[dict, Depends(security.get_current_user)]
AdminUser = Annotated[dict, Depends(security.get_current_admin_user)]
# --- End Security Dependencies ---

# --- MAPA DE LABORATORIOS (para obtener nombre y ubicación) ---
labs_cache_main = {}
def load_labs_cache():
    global labs_cache_main
    db = SessionLocal()
    try:
        labs = db.query(models.Laboratorio).all()
        labs_cache_main = {lab.id: lab for lab in labs}
        print("INFO: Cache de laboratorios cargada.")
    except Exception as e:
        print(f"ERROR: No se pudo cargar la caché de laboratorios: {e}")
    finally:
        db.close()

# Carga la caché al iniciar la aplicación
@app.on_event("startup")
async def startup_event():
    # Inicializar base de datos
    auth_service.init_db(create_dev_admin=True)
    # Cargar cache de laboratorios
    load_labs_cache()

# ==============================================================================
# --- AUTHENTICATION ENDPOINTS ---
# ==============================================================================

@app.get("/captcha", tags=["Auth"])
async def get_captcha(request: Request):
    image_captcha = ImageCaptcha()
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    request.session["captcha_text"] = captcha_text
    image_stream = image_captcha.generate(captcha_text)
    image_bytes = image_stream.getvalue()
    
    # --- INICIO DE LA CORRECCIÓN ---
    # 1. Codifica los bytes de la imagen a base64
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # 2. Devuelve SÓLO el string base64 puro
    return {"image_data": image_b64}
    # --- FIN DE LA CORRECCIÓN ---
# --- Standard Login Endpoint (Username/Password + CAPTCHA) ---
@app.post("/token", response_model=schemas.Token, tags=["Auth"])
async def login_for_access_token(request: Request, login_data: LoginRequest, db: DbSession):
    captcha_esperado = request.session.get("captcha_text")
    if "captcha_text" in request.session: del request.session["captcha_text"]
    if not captcha_esperado or login_data.captcha.upper() != captcha_esperado.upper():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El texto del CAPTCHA es incorrecto.")
    user_dict = auth_service.login(username_or_email=login_data.username, password=login_data.password)
    if not user_dict:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": user_dict["user"], "rol": user_dict["rol"], "id": user_dict["id"]}
    access_token = security.create_access_token(data=token_data, expires_delta=expires)
    user_obj = db.get(models.Usuario, user_dict["id"])
    if not user_obj: raise HTTPException(status_code=404, detail="Usuario no encontrado post-login.")
    return {"access_token": access_token, "token_type": "bearer", "user": user_obj}

# --- ¡ENDPOINT DE LOGIN CON GOOGLE MEJORADO! ---
@app.post("/auth/google-token", response_model=schemas.Token, tags=["Auth"])
async def login_with_google_token(token_data: GoogleToken, db: DbSession):
    """
    Google OAuth2 authentication endpoint.
    
    Expects: {"idToken": "<google_id_token_string>"}
    Returns: {"access_token": "...", "token_type": "bearer", "user": {...}}
    """
    try:
        # Use the improved Google auth service
        success, result, message = google_auth.authenticate_with_google(token_data.id_token)
        
        if not success:
            print(f"ERROR: Google authentication failed: {message}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Google authentication failed: {message}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        print(f"SUCCESS: User {result['user']['user']} authenticated via Google")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: Unexpected error in Google auth endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


# --- User Registration Endpoint ---
@app.post("/register", response_model=schemas.Usuario, tags=["Auth"], status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UsuarioCreate, db: DbSession):
    ok, result = auth_service.create_user(**user.model_dump())
    if not ok: 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(result))
    user_db = db.get(models.Usuario, result["id"])
    if not user_db: 
        raise HTTPException(status_code=404, detail="Usuario creado pero no recuperado.")
    return user_db

# ==============================================================================
# --- USER MANAGEMENT ENDPOINTS ---
# ==============================================================================
@app.get("/usuarios", response_model=List[schemas.Usuario], tags=["Usuarios (Admin)"])
def get_all_users(user: AdminUser, db: DbSession, q: Optional[str] = "", rol: Optional[str] = ""):
    query = db.query(models.Usuario)
    if rol: 
        query = query.filter(models.Usuario.rol == rol)
    if q:
        search = f"%{q.lower()}%"
        query = query.filter((models.Usuario.nombre.ilike(search)) | (models.Usuario.user.ilike(search)) | (models.Usuario.correo.ilike(search)))
    return query.order_by(models.Usuario.nombre.asc()).all()

@app.put("/usuarios/{user_id}", response_model=schemas.Usuario, tags=["Usuarios (Admin)"])
def update_user_by_admin(user_id: int, user_update: UsuarioAdminUpdate, user: AdminUser, db: DbSession):
    user_to_update = db.get(models.Usuario, user_id)
    if not user_to_update: 
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user_id == user["id"] and user_update.rol and user_update.rol != "admin": 
        raise HTTPException(status_code=403, detail="No puedes revocar tu propio rol.")
    update_data = user_update.model_dump(exclude_unset=True)
    if not update_data: 
        raise HTTPException(status_code=400, detail="No se proporcionaron datos.")
    if 'user' in update_data and update_data['user'] != user_to_update.user:
        if db.query(models.Usuario).filter(models.Usuario.user == update_data['user'], models.Usuario.id != user_id).first(): 
            raise HTTPException(status_code=400, detail="Usuario ya en uso.")
    if 'correo' in update_data and update_data['correo'] != user_to_update.correo:
        if db.query(models.Usuario).filter(models.Usuario.correo == update_data['correo'], models.Usuario.id != user_id).first(): 
            raise HTTPException(status_code=400, detail="Correo ya registrado.")
    allowed_roles = {'admin', 'docente', 'estudiante'}
    if 'rol' in update_data and update_data['rol'] not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"Rol '{update_data['rol']}' inválido. Permitidos: {', '.join(allowed_roles)}")
    for key, value in update_data.items(): 
        setattr(user_to_update, key, value)
    try: 
        db.commit(); db.refresh(user_to_update); return user_to_update
    except Exception as e: 
        db.rollback(); print(f"ERROR updating user {user_id}: {e}"); 
        raise HTTPException(status_code=500, detail="Error interno.")

@app.delete("/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Usuarios (Admin)"])
def delete_user(user_id: int, user: AdminUser, db: DbSession):
    if user_id == user["id"]: 
        raise HTTPException(status_code=403, detail="No puedes eliminar tu propia cuenta.")
    user_to_delete = db.get(models.Usuario, user_id)
    if not user_to_delete: 
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    active_prestamos = db.query(models.Prestamo).filter(models.Prestamo.usuario_id == user_id, models.Prestamo.estado.notin_(['devuelto', 'rechazado'])).count()
    if active_prestamos > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: usuario tiene {active_prestamos} préstamo(s) activo(s).")
    try:
        db.delete(user_to_delete); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback(); print(f"ERROR deleting user {user_id}: {e}")
        if "violates foreign key constraint" in str(e).lower() and "reservas" in str(e).lower(): 
            raise HTTPException(status_code=409, detail="No se puede eliminar: el usuario tiene reservas asociadas.")
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar usuario: {e}")

@app.put("/usuarios/me/profile", response_model=schemas.Usuario, tags=["Usuarios"])
def update_my_profile(profile_data: schemas.ProfileUpdate, user: CurrentUser, db: DbSession):
    user_to_update = db.get(models.Usuario, user["id"])
    if not user_to_update: 
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    update_data = profile_data.model_dump(exclude_unset=True)
    if not update_data: 
        raise HTTPException(status_code=400, detail="No se proporcionaron datos.")
    if 'user' in update_data and update_data['user'] != user_to_update.user:
        if db.query(models.Usuario).filter(models.Usuario.user == update_data['user'], models.Usuario.id != user["id"]).first(): 
            raise HTTPException(status_code=400, detail="Nombre de usuario ya en uso.")
    if 'correo' in update_data and update_data['correo'] != user_to_update.correo:
        if db.query(models.Usuario).filter(models.Usuario.correo == update_data['correo'], models.Usuario.id != user["id"]).first(): 
            raise HTTPException(status_code=400, detail="Correo ya registrado.")
    for key, value in update_data.items(): 
        setattr(user_to_update, key, value)
    try: 
        db.commit(); db.refresh(user_to_update); return user_to_update
    except Exception as e: 
        db.rollback(); print(f"ERROR updating profile: {e}"); 
        raise HTTPException(status_code=500, detail="Error interno.")

@app.put("/usuarios/me/password", tags=["Usuarios"])
def change_my_password(pass_data: schemas.PasswordUpdate, user: CurrentUser, db: DbSession):
    user_in_db = db.get(models.Usuario, user["id"])
    if not user_in_db: 
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if not auth_service.verify_password(pass_data.old_password, user_in_db.password_hash): 
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta.")
    if len(pass_data.new_password) < 6: 
        raise HTTPException(status_code=400, detail="Contraseña debe tener >= 6 caracteres.")
    user_in_db.password_hash = auth_service.hash_password(pass_data.new_password)
    try: 
        db.commit(); return {"message": "Contraseña actualizada."}
    except Exception as e: 
        db.rollback(); print(f"ERROR updating password: {e}"); 
        raise HTTPException(status_code=500, detail="Error interno.")

# ==============================================================================
# --- OTHER RESOURCE ENDPOINTS ---
# ==============================================================================
# --- Planteles ---
@app.get("/planteles", response_model=List[schemas.Plantel], tags=["Admin: Gestión"])
def get_all_planteles(user: CurrentUser, db: DbSession):
    return db.query(models.Plantel).order_by(models.Plantel.nombre.asc()).all()

@app.post("/planteles", response_model=schemas.Plantel, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_plantel(plantel: schemas.PlantelCreate, user: AdminUser, db: DbSession):
    if not plantel.nombre.strip() or not plantel.direccion.strip(): 
        raise HTTPException(status_code=400, detail="Nombre y dirección obligatorios.")
    new_plantel = models.Plantel(**plantel.model_dump()); db.add(new_plantel)
    try: 
        db.commit(); db.refresh(new_plantel); return new_plantel
    except Exception as e: 
        db.rollback(); print(f"ERROR creating plantel: {e}"); 
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.put("/planteles/{plantel_id}", response_model=schemas.Plantel, tags=["Admin: Gestión"])
def update_plantel(plantel_id: int, plantel_update: schemas.PlantelCreate, user: AdminUser, db: DbSession):
    db_plantel = db.get(models.Plantel, plantel_id);
    if not db_plantel: 
        raise HTTPException(status_code=404, detail="Plantel no encontrado")
    update_data = plantel_update.model_dump(exclude_unset=True)
    if 'nombre' in update_data and not update_data['nombre'].strip(): 
        raise HTTPException(status_code=400, detail="Nombre no puede estar vacío.")
    if 'direccion' in update_data and not update_data['direccion'].strip(): 
        raise HTTPException(status_code=400, detail="Dirección no puede estar vacía.")
    for key, value in update_data.items(): 
        setattr(db_plantel, key, value)
    try: 
        db.commit(); db.refresh(db_plantel); return db_plantel
    except Exception as e: 
        db.rollback(); print(f"ERROR updating plantel {plantel_id}: {e}"); 
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.delete("/planteles/{plantel_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
def delete_plantel(plantel_id: int, user: AdminUser, db: DbSession):
    db_plantel = db.get(models.Plantel, plantel_id)
    if not db_plantel: 
        raise HTTPException(status_code=404, detail="Plantel no encontrado")
    labs_count = db.query(models.Laboratorio).filter(models.Laboratorio.plantel_id == plantel_id).count()
    if labs_count > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {labs_count} lab(s) asociados.")
    try: 
        db.delete(db_plantel); db.commit(); 
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e: 
        db.rollback(); print(f"ERROR deleting plantel {plantel_id}: {e}"); 
        raise HTTPException(status_code=500, detail=f"Error: {e}")

# --- Laboratorios ---
@app.get("/laboratorios", response_model=List[schemas.Laboratorio], tags=["Admin: Gestión"])
def get_all_laboratorios(user: CurrentUser, db: DbSession):
    if not labs_cache_main: 
        load_labs_cache()
    return db.query(models.Laboratorio).options(joinedload(models.Laboratorio.plantel)).order_by(models.Laboratorio.id.desc()).all()

@app.post("/laboratorios", response_model=schemas.Laboratorio, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_laboratorio(lab: schemas.LaboratorioCreate, user: AdminUser, db: DbSession):
    if not lab.nombre.strip(): 
        raise HTTPException(status_code=400, detail="Nombre obligatorio.")
    plantel = db.get(models.Plantel, lab.plantel_id);
    if not plantel: 
        raise HTTPException(status_code=404, detail=f"Plantel id {lab.plantel_id} no encontrado.")
    new_lab = models.Laboratorio(**lab.model_dump()); db.add(new_lab)
    try:
        db.commit(); db.refresh(new_lab)
        labs_cache_main[new_lab.id] = new_lab
        db.refresh(new_lab.plantel)
        return new_lab
    except Exception as e: 
        db.rollback(); print(f"ERROR creating lab: {e}"); 
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.put("/laboratorios/{lab_id}", response_model=schemas.Laboratorio, tags=["Admin: Gestión"])
def update_laboratorio(lab_id: int, lab_update: schemas.LaboratorioCreate, user: AdminUser, db: DbSession):
    db_lab = db.get(models.Laboratorio, lab_id)
    if not db_lab: 
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    update_data = lab_update.model_dump(exclude_unset=True)
    if 'nombre' in update_data and not update_data['nombre'].strip(): 
        raise HTTPException(status_code=400, detail="Nombre no puede estar vacío.")
    if 'plantel_id' in update_data and update_data['plantel_id'] != db_lab.plantel_id:
        plantel = db.get(models.Plantel, update_data['plantel_id'])
        if not plantel: 
            raise HTTPException(status_code=404, detail=f"Plantel id {update_data['plantel_id']} no encontrado.")
    for key, value in update_data.items(): 
        setattr(db_lab, key, value)
    try:
        db.commit(); db.refresh(db_lab)
        labs_cache_main[db_lab.id] = db_lab
        db.refresh(db_lab.plantel)
        return db_lab
    except Exception as e: 
        db.rollback(); print(f"ERROR updating lab {lab_id}: {e}"); 
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.delete("/laboratorios/{lab_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
def delete_laboratorio(lab_id: int, user: AdminUser, db: DbSession):
    db_lab = db.get(models.Laboratorio, lab_id);
    if not db_lab: 
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    recursos_count = db.query(models.Recurso).filter(models.Recurso.laboratorio_id == lab_id).count()
    if recursos_count > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {recursos_count} recurso(s) asociados.")
    reservas_count = db.query(models.Reserva).filter(models.Reserva.laboratorio_id == lab_id).count()
    if reservas_count > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {reservas_count} reserva(s) asociada(s).")
    try:
        db.delete(db_lab); db.commit()
        labs_cache_main.pop(lab_id, None)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e: 
        db.rollback(); print(f"ERROR deleting lab {lab_id}: {e}"); 
        raise HTTPException(status_code=500, detail=f"Error: {e}")

# --- RECURSOS ENDPOINTS ---
@app.get("/recursos", response_model=List[schemas.Recurso], tags=["Recursos"])
def get_recursos_filtrados(
    user: CurrentUser, db: DbSession, plantel_id: Optional[int] = None, lab_id: Optional[int] = None, estado: Optional[str] = None, tipo: Optional[str] = None
):
    q = db.query(models.Recurso)
    if lab_id: 
        q = q.filter(models.Recurso.laboratorio_id == lab_id)
    elif plantel_id:
        lab_ids_subquery = db.query(models.Laboratorio.id).filter(models.Laboratorio.plantel_id == plantel_id).subquery()
        q = q.filter(models.Recurso.laboratorio_id.in_(lab_ids_subquery))
    if estado: 
        q = q.filter(models.Recurso.estado == estado)
    if tipo: 
        q = q.filter(models.Recurso.tipo == tipo)
    q = q.options(joinedload(models.Recurso.laboratorio).joinedload(models.Laboratorio.plantel))
    return q.order_by(models.Recurso.id.desc()).all()


@app.get("/recursos/tipos", response_model=List[str], tags=["Recursos"])
def get_recurso_tipos(user: CurrentUser, db: DbSession):
    tipos = db.query(models.Recurso.tipo).distinct().order_by(models.Recurso.tipo).all()
    return [tipo[0] for tipo in tipos if tipo and tipo[0] and tipo[0].strip()]


@app.post("/recursos", response_model=schemas.Recurso, status_code=status.HTTP_201_CREATED, tags=["Admin: Gestión"])
def create_recurso(recurso: schemas.RecursoCreate, user: AdminUser, db: DbSession):
    if not recurso.tipo.strip() or not recurso.estado.strip(): 
        raise HTTPException(status_code=400, detail="Tipo y estado obligatorios.")
    if recurso.estado not in ["disponible", "prestado", "mantenimiento"]: 
        raise HTTPException(status_code=400, detail="Estado inválido.")
    lab = db.get(models.Laboratorio, recurso.laboratorio_id)
    if not lab: 
        raise HTTPException(status_code=404, detail="Laboratorio id no encontrado.")
    new_recurso = models.Recurso(**recurso.model_dump()); db.add(new_recurso)
    try:
        db.commit(); db.refresh(new_recurso); db.refresh(new_recurso.laboratorio)
        return new_recurso
    except Exception as e: 
        db.rollback(); print(f"ERROR creating resource: {e}"); traceback.print_exc(); 
        raise HTTPException(status_code=400, detail=f"Error al crear recurso: {e}")


@app.put("/recursos/{recurso_id}", response_model=schemas.Recurso, tags=["Admin: Gestión"])
def update_recurso(recurso_id: int, recurso_update: schemas.RecursoCreate, user: AdminUser, db: DbSession):
    db_recurso = db.get(models.Recurso, recurso_id)
    if not db_recurso: 
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    update_data = recurso_update.model_dump(exclude_unset=True)
    if 'tipo' in update_data and not update_data['tipo'].strip(): 
        raise HTTPException(status_code=400, detail="Tipo no puede estar vacío.")
    if 'estado' in update_data:
        if not update_data['estado'].strip(): 
            raise HTTPException(status_code=400, detail="Estado no puede estar vacío.")
        if update_data['estado'] not in ["disponible", "prestado", "mantenimiento"]: 
            raise HTTPException(status_code=400, detail="Estado inválido.")
    if 'laboratorio_id' in update_data and update_data['laboratorio_id'] != db_recurso.laboratorio_id:
        lab = db.get(models.Laboratorio, update_data['laboratorio_id'])
        if not lab: 
            raise HTTPException(status_code=404, detail="Laboratorio id no encontrado.")
    for key, value in update_data.items(): 
        setattr(db_recurso, key, value)
    try:
        db.commit(); db.refresh(db_recurso); db.refresh(db_recurso.laboratorio)
        return db_recurso
    except Exception as e: 
        db.rollback(); print(f"ERROR updating resource {recurso_id}: {e}"); traceback.print_exc(); 
        raise HTTPException(status_code=400, detail=f"Error al actualizar recurso: {e}")


@app.delete("/recursos/{recurso_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Gestión"])
def delete_recurso(recurso_id: int, user: AdminUser, db: DbSession):
    db_recurso = db.get(models.Recurso, recurso_id)
    if not db_recurso: 
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    prestamos_count = db.query(models.Prestamo).filter(models.Prestamo.recurso_id == recurso_id).count()
    if prestamos_count > 0: 
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: hay {prestamos_count} préstamo(s) asociado(s).")
    try:
        db.delete(db_recurso); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e: 
        db.rollback(); print(f"ERROR deleting resource {recurso_id}: {e}"); traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error interno al eliminar recurso: {e}")

# ==============================================================================
# --- ENDPOINTS DE GESTIÓN DE HORARIOS (ADMIN) ---
# ==============================================================================
@app.post("/admin/horarios/reglas", response_model=schemas.ReglaHorario, status_code=status.HTTP_201_CREATED, tags=["Admin: Horarios"])
def create_regla_horario(regla: schemas.ReglaHorarioCreate, user: AdminUser, db: DbSession):
    if not (0 <= regla.dia_semana <= 6): 
        raise HTTPException(status_code=400, detail="dia_semana debe estar entre 0 (Lunes) y 6 (Domingo).")
    if regla.hora_inicio >= regla.hora_fin: 
        raise HTTPException(status_code=400, detail="hora_inicio debe ser anterior a hora_fin.")
    db_regla = models.ReglaHorario(**regla.model_dump())
    try:
        db.add(db_regla); db.commit(); db.refresh(db_regla)
        return db_regla
    except Exception as e: 
        db.rollback(); traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error al crear regla: {e}")

@app.get("/admin/horarios/reglas", response_model=List[schemas.ReglaHorario], tags=["Admin: Horarios"])
def get_reglas_horario(user: AdminUser, db: DbSession, laboratorio_id: Optional[int] = None):
    query = db.query(models.ReglaHorario)
    if laboratorio_id is not None: 
        query = query.filter(models.ReglaHorario.laboratorio_id == laboratorio_id)
    return query.order_by(models.ReglaHorario.laboratorio_id, models.ReglaHorario.dia_semana, models.ReglaHorario.hora_inicio).all()

@app.put("/admin/horarios/reglas/{regla_id}", response_model=schemas.ReglaHorario, tags=["Admin: Horarios"])
def update_regla_horario(regla_id: int, regla_update: schemas.ReglaHorarioUpdate, user: AdminUser, db: DbSession):
    db_regla = db.get(models.ReglaHorario, regla_id)
    if not db_regla: 
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    update_data = regla_update.model_dump(exclude_unset=True)
    if not update_data: 
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    if 'dia_semana' in update_data and not (0 <= update_data['dia_semana'] <= 6): 
        raise HTTPException(status_code=400, detail="dia_semana debe estar entre 0 y 6.")
    for key, value in update_data.items(): 
        setattr(db_regla, key, value)
    try: 
        db.commit(); db.refresh(db_regla)
    except Exception as e: 
        db.rollback(); traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error al actualizar regla: {e}")
    return db_regla

@app.delete("/admin/horarios/reglas/{regla_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Horarios"])
def delete_regla_horario(regla_id: int, user: AdminUser, db: DbSession):
    db_regla = db.get(models.ReglaHorario, regla_id)
    if not db_regla: 
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    try:
        db.delete(db_regla); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e: 
        db.rollback(); traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error al eliminar regla: {e}")

@app.post("/admin/horarios/excepciones", response_model=schemas.ExcepcionHorario, status_code=status.HTTP_201_CREATED, tags=["Admin: Horarios"])
def create_excepcion_horario(excepcion: schemas.ExcepcionHorarioCreate, user: AdminUser, db: DbSession):
    if (excepcion.hora_inicio and not excepcion.hora_fin) or (not excepcion.hora_inicio and excepcion.hora_fin):
        raise HTTPException(status_code=400, detail="Debe especificar ambas horas (inicio y fin) o ninguna (para todo el día).")
    if excepcion.hora_inicio and excepcion.hora_fin and excepcion.hora_inicio >= excepcion.hora_fin:
        raise HTTPException(status_code=400, detail="hora_inicio debe ser anterior a hora_fin.")
    db_excepcion = models.ExcepcionHorario(**excepcion.model_dump())
    try:
        db.add(db_excepcion); db.commit(); db.refresh(db_excepcion)
        return db_excepcion
    except Exception as e: 
        db.rollback(); traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error al crear excepción: {e}")

@app.get("/admin/horarios/excepciones", response_model=List[schemas.ExcepcionHorario], tags=["Admin: Horarios"])
def get_excepciones_horario(user: AdminUser, db: DbSession, laboratorio_id: Optional[int] = None, fecha_desde: Optional[date] = None):
    query = db.query(models.ExcepcionHorario)
    if laboratorio_id is not None: 
        query = query.filter(models.ExcepcionHorario.laboratorio_id == laboratorio_id)
    if fecha_desde: 
        query = query.filter(models.ExcepcionHorario.fecha >= fecha_desde)
    return query.order_by(models.ExcepcionHorario.fecha, models.ExcepcionHorario.hora_inicio).all()

@app.put("/admin/horarios/excepciones/{excepcion_id}", response_model=schemas.ExcepcionHorario, tags=["Admin: Horarios"])
def update_excepcion_horario(excepcion_id: int, excepcion_update: schemas.ExcepcionHorarioUpdate, user: AdminUser, db: DbSession):
    db_excepcion = db.get(models.ExcepcionHorario, excepcion_id)
    if not db_excepcion: 
        raise HTTPException(status_code=404, detail="Excepción no encontrada")
    update_data = excepcion_update.model_dump(exclude_unset=True)
    if not update_data: 
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    for key, value in update_data.items(): 
        setattr(db_excepcion, key, value)
    try: 
        db.commit(); db.refresh(db_excepcion)
    except Exception as e: 
        db.rollback(); traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error al actualizar excepción: {e}")
    return db_excepcion

@app.delete("/admin/horarios/excepciones/{excepcion_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin: Horarios"])
def delete_excepcion_horario(excepcion_id: int, user: AdminUser, db: DbSession):
    db_excepcion = db.get(models.ExcepcionHorario, excepcion_id)
    if not db_excepcion: 
        raise HTTPException(status_code=404, detail="Excepción no encontrada")
    try:
        db.delete(db_excepcion); db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e: 
        db.rollback(); traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error al eliminar excepción: {e}")


# ==============================================================================
# --- ENDPOINT PARA OBTENER RESERVAS PROPIAS (¡NUEVO!) ---
# ==============================================================================

# ¡IMPORTANTE! Este endpoint debe definirse ANTES de "/reservas/{lab_id}"
# para evitar conflictos de rutas (donde "mis-solicitudes" se confunde con un lab_id).

@app.get("/reservas/mis-solicitudes", response_model=List[schemas.Reserva], tags=["Reservas"])
def get_mis_reservas(user: CurrentUser, db: DbSession):
    """
    Obtiene todas las reservas (no canceladas) del usuario autenticado.
    """
    reservas = db.query(models.Reserva).options(
        joinedload(models.Reserva.usuario),
        joinedload(models.Reserva.laboratorio).joinedload(models.Laboratorio.plantel) # Cargar también el lab y plantel
    ).filter(
        models.Reserva.usuario_id == user["id"],
        models.Reserva.estado != "cancelada"
    ).order_by(models.Reserva.inicio.desc()).all()
    
    # Asegurar que las fechas de respuesta estén en UTC
    for r in reservas:
        if r.inicio: r.inicio = r.inicio.astimezone(timezone.utc)
        if r.fin: r.fin = r.fin.astimezone(timezone.utc)
        
    return reservas

# ==============================================================================
# --- ENDPOINT PARA OBTENER RESERVAS POR LABORATORIO ---
# ==============================================================================
@app.get("/reservas/{lab_id}", response_model=List[schemas.Reserva], tags=["Reservas"])
def get_reservas_por_lab_y_fecha(
    lab_id: int,
    start_dt: date,
    end_dt: date, # El cliente debe enviar la fecha final *exclusiva*
    user: CurrentUser,
    db: DbSession
):
    """
    Obtiene todas las reservas activas para un laboratorio específico dentro de un rango de fechas.
    """
    lab = labs_cache_main.get(lab_id) or db.get(models.Laboratorio, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")

    # Convertir fechas (naive) a datetimes (aware, UTC)
    try:
        start_dt_utc = datetime.combine(start_dt, time.min, tzinfo=timezone.utc)
        end_dt_utc = datetime.combine(end_dt, time.min, tzinfo=timezone.utc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fechas inválidas: {e}")

    reservas_db = db.query(models.Reserva).options(
        joinedload(models.Reserva.usuario)
    ).filter(
        models.Reserva.laboratorio_id == lab_id,
        models.Reserva.estado != "cancelada",
        models.Reserva.inicio < end_dt_utc,
        models.Reserva.fin > start_dt_utc
    ).order_by(models.Reserva.inicio.asc()).all()

    for r in reservas_db:
            r.inicio = r.inicio.astimezone(timezone.utc)
            r.fin = r.fin.astimezone(timezone.utc)

    return reservas_db

# ==============================================================================
# --- ENDPOINT PARA CALCULAR HORARIO DISPONIBLE ---
# ==============================================================================
@app.get("/laboratorios/{lab_id}/horario", response_model=Dict[date, List[schemas.SlotHorario]], tags=["Reservas"])
def get_horario_laboratorio(
    lab_id: int, fecha_inicio: date, fecha_fin: date, user: CurrentUser, db: DbSession
):
    lab = db.get(models.Laboratorio, lab_id)
    if not lab: 
        raise HTTPException(status_code=404, detail="Laboratorio no encontrado")
    reglas_generales = db.query(models.ReglaHorario).filter(models.ReglaHorario.laboratorio_id == None).all()
    reglas_especificas = db.query(models.ReglaHorario).filter(models.ReglaHorario.laboratorio_id == lab_id).all()

    reglas_por_dia: Dict[int, List[models.ReglaHorario]] = {}

    for regla in reglas_generales:
        if regla.dia_semana not in reglas_por_dia:
                reglas_por_dia[regla.dia_semana] = []
        reglas_por_dia[regla.dia_semana].append(regla)

    dias_con_reglas_especificas = {r.dia_semana for r in reglas_especificas}
    dias_especificos_ya_procesados = set()

    for regla in reglas_especificas:
        if regla.dia_semana not in dias_especificos_ya_procesados:
            reglas_por_dia[regla.dia_semana] = []
            dias_especificos_ya_procesados.add(regla.dia_semana)
        reglas_por_dia[regla.dia_semana].append(regla)

    for dia in reglas_por_dia:
        reglas_por_dia[dia].sort(key=lambda r: r.hora_inicio)

    excepciones = db.query(models.ExcepcionHorario).filter(models.ExcepcionHorario.laboratorio_id.in_([lab_id, None]), models.ExcepcionHorario.fecha >= fecha_inicio, models.ExcepcionHorario.fecha <= fecha_fin).order_by(models.ExcepcionHorario.fecha, models.ExcepcionHorario.hora_inicio).all()
    excepciones_por_fecha: Dict[date, List[models.ExcepcionHorario]] = {}
    for ex in excepciones:
        if ex.fecha not in excepciones_por_fecha: 
            excepciones_por_fecha[ex.fecha] = []
        excepciones_por_fecha[ex.fecha].append(ex)

    reservas_existentes = db.query(models.Reserva).filter(models.Reserva.laboratorio_id == lab_id, models.Reserva.estado != 'cancelada', models.Reserva.inicio < datetime.combine(fecha_fin + timedelta(days=1), time.min).replace(tzinfo=timezone.utc), models.Reserva.fin > datetime.combine(fecha_inicio, time.min).replace(tzinfo=timezone.utc)).all()

    reservas_map: Dict[Tuple[date, time], models.Reserva] = {}
    for r in reservas_existentes:
        try:
            inicio_dt = r.inicio
            if isinstance(inicio_dt, datetime):
                naive_inicio = inicio_dt.replace(tzinfo=None)
                reservas_map[(naive_inicio.date(), naive_inicio.time())] = r
            else:
                print(f"WARN: Reserva ID {r.id} has invalid inicio type: {type(inicio_dt)}")
        except Exception as date_parse_err:
            print(f"ERROR parsing reserva inicio date for ID {r.id}: {date_parse_err}")

    horario_final: Dict[date, List[schemas.SlotHorario]] = {}
    current_date = fecha_inicio

    while current_date <= fecha_fin:
        dia_semana = current_date.weekday()
        slots_del_dia: List[schemas.SlotHorario] = []

        excepciones_hoy = excepciones_por_fecha.get(current_date, [])
        excepcion_dia_completo = next((ex for ex in excepciones_hoy if ex.laboratorio_id == lab_id and ex.hora_inicio is None), None)
        excepcion_dia_completo_general = next((ex for ex in excepciones_hoy if ex.laboratorio_id is None and ex.hora_inicio is None), None)
        ex_completa_aplicable = excepcion_dia_completo or excepcion_dia_completo_general

        if ex_completa_aplicable and not ex_completa_aplicable.es_habilitado:
                horario_final[current_date] = []; current_date += timedelta(days=1); continue

        reglas_a_usar = reglas_por_dia.get(dia_semana, [])

        if not reglas_a_usar:
                horario_final[current_date] = []
        else:
            for regla in reglas_a_usar:
                s_time = regla.hora_inicio
                f_time = regla.hora_fin

                if not isinstance(s_time, time) or not isinstance(f_time, time):
                    print(f"WARN: Invalid time objects in rule ID {regla.id} for date {current_date}. Skipping.")
                    continue

                slot_inicio_dt_naive = datetime.combine(current_date, s_time)
                slot_fin_dt_naive = datetime.combine(current_date, f_time)

                if not regla.es_habilitado:
                    slot_tipo = regla.tipo_intervalo or "no_habilitado"
                else:
                    slot_tipo = regla.tipo_intervalo or 'disponible'

                if slot_tipo == 'disponible':
                    if (current_date, s_time) in reservas_map:
                            slot_tipo = "reservado"
                    if slot_tipo == 'disponible':
                        for ex in excepciones_hoy:
                            if ex.hora_inicio and ex.hora_fin:
                                if not isinstance(ex.hora_inicio, time) or not isinstance(ex.hora_fin, time):
                                    print(f"WARN: Invalid time objects in exception ID {ex.id} for date {current_date}. Skipping check.")
                                    continue
                                ex_inicio_naive = datetime.combine(current_date, ex.hora_inicio)
                                ex_fin_naive = datetime.combine(current_date, ex.hora_fin)
                                if slot_inicio_dt_naive >= ex_inicio_naive and slot_fin_dt_naive <= ex_fin_naive:
                                    if not ex.es_habilitado:
                                        slot_tipo = ex.tipo or "mantenimiento"
                                        break

                try:
                    slot_inicio_dt_utc = slot_inicio_dt_naive.replace(tzinfo=timezone.utc)
                    slot_fin_dt_utc = slot_fin_dt_naive.replace(tzinfo=timezone.utc)
                    slots_del_dia.append(schemas.SlotHorario(inicio=slot_inicio_dt_utc, fin=slot_fin_dt_utc, tipo=slot_tipo))
                except Exception as dt_err:
                    print(f"ERROR converting datetimes for rule ID {regla.id} on {current_date}: {dt_err}")

            slots_del_dia.sort(key=lambda x: x.inicio)
            horario_final[current_date] = slots_del_dia

        current_date += timedelta(days=1)

    return horario_final

# ==============================================================================
# --- MODIFIED RESERVATION ENDPOINTS ---
# ==============================================================================

# --- MODIFIED: create_reserva ---
@app.post("/reservas", response_model=schemas.Reserva, status_code=status.HTTP_201_CREATED, tags=["Reservas"])
def create_reserva(reserva: schemas.ReservaCreate, user: CurrentUser, db: DbSession):
    # --- Validaciones ---
    if user.get("rol") not in ["admin", "docente"]: 
        raise HTTPException(status_code=403, detail="Solo admins/docentes pueden crear reservas.")
    lab = labs_cache_main.get(reserva.laboratorio_id) or db.get(models.Laboratorio, reserva.laboratorio_id)
    if not lab: 
        raise HTTPException(status_code=404, detail=f"Laboratorio id {reserva.laboratorio_id} no encontrado.")
    res_user = db.get(models.Usuario, reserva.usuario_id) # Get the user for whom the reservation is being made
    if not res_user: 
        raise HTTPException(status_code=404, detail=f"Usuario id {reserva.usuario_id} no encontrado.")

    # Ensure datetimes from request are timezone-aware (UTC)
    inicio = reserva.inicio
    if inicio.tzinfo is None: 
        inicio = inicio.replace(tzinfo=timezone.utc)
    else: 
        inicio = inicio.astimezone(timezone.utc)
    fin = reserva.fin
    if fin.tzinfo is None: 
        fin = fin.replace(tzinfo=timezone.utc)
    else: 
        fin = fin.astimezone(timezone.utc)
    if inicio >= fin: 
        raise HTTPException(status_code=400, detail="Inicio debe ser anterior a fin.")

    # --- Validación de Horario ---
    try:
        horario_dia = get_horario_laboratorio(lab_id=reserva.laboratorio_id, fecha_inicio=inicio.date(), fecha_fin=inicio.date(), user=user, db=db)
        slots_disponibles_hoy = horario_dia.get(inicio.date(), [])
        slot_valido_encontrado = False
        for slot in slots_disponibles_hoy:
            slot_inicio_utc = slot.inicio.astimezone(timezone.utc)
            slot_fin_utc = slot.fin.astimezone(timezone.utc)
            if slot_inicio_utc == inicio and slot_fin_utc == fin and slot.tipo == 'disponible':
                slot_valido_encontrado = True; break
        if not slot_valido_encontrado:
                raise HTTPException(status_code=409, detail="El horario solicitado no está disponible o no coincide con un slot válido y libre.")
    except HTTPException as http_ex: 
        raise http_ex
    except Exception as val_ex: 
        traceback.print_exc(); 
        raise HTTPException(status_code=500, detail=f"Error al validar disponibilidad: {val_ex}")

    # --- Verificar solapamiento ---
    overlapping = db.query(models.Reserva)\
                    .filter(models.Reserva.laboratorio_id == reserva.laboratorio_id,
                            models.Reserva.estado != "cancelada",
                            models.Reserva.inicio < fin,
                            models.Reserva.fin > inicio).first()
    if overlapping: 
        raise HTTPException(status_code=409, detail=f"Conflicto de horario detectado (ID existente: {overlapping.id}).")

    # --- Crear Reserva y Evento Calendar ---
    new_reserva = models.Reserva(usuario_id=reserva.usuario_id, laboratorio_id=reserva.laboratorio_id, inicio=inicio, fin=fin, estado="activa", google_event_id=None)
    google_event_id = None
    try:
        db.add(new_reserva); db.commit(); db.refresh(new_reserva)
        print(f"INFO: Reserva local creada con ID: {new_reserva.id}")
        try:
            lab_name = lab.nombre
            lab_location = getattr(lab, 'ubicacion', '')
            user_name = res_user.nombre
            # --- Get user's email to add as attendee ---
            user_email = res_user.correo # Get email from the user object

            summary = f"Reserva Lab: {lab_name} - {user_name}"
            description = f"Reserva ID Local: {new_reserva.id}\nUsuario: {user_name} (ID: {new_reserva.usuario_id})"

            # Call Google Calendar Service with attendee
            google_event_id = calendar_service.create_calendar_event(
                summary=summary,
                start_time=new_reserva.inicio,
                end_time=new_reserva.fin,
                description=description,
                location=lab_location,
                # --- ADD ATTENDEE ---
                attendees=[user_email] if user_email else [] # Pass user email in a list
            )

            if google_event_id and hasattr(new_reserva, 'google_event_id'):
                new_reserva.google_event_id = google_event_id; db.commit(); db.refresh(new_reserva)
                print(f"INFO: ID de evento de Google ({google_event_id}) asociado a reserva {new_reserva.id}")
            else: 
                print(f"WARN: No se pudo obtener/guardar el ID de evento de Google para reserva {new_reserva.id}")
        except Exception as calendar_e: 
            print(f"ERROR: Falló la creación/actualización del evento en Google Calendar para reserva {new_reserva.id}: {calendar_e}")

        # Ensure returned datetimes are UTC aware
        new_reserva.inicio = new_reserva.inicio.astimezone(timezone.utc)
        new_reserva.fin = new_reserva.fin.astimezone(timezone.utc)
        return new_reserva
    except Exception as e:
        db.rollback(); print(f"ERROR creating reservation: {e}"); traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error al crear reserva local: {e}")

# --- MODIFIED: cancel_reserva ---
@app.put("/reservas/{reserva_id}/cancelar", response_model=schemas.Reserva, tags=["Reservas"])
def cancel_reserva(reserva_id: int, user: CurrentUser, db: DbSession):
    reserva = db.get(models.Reserva, reserva_id)
    if not reserva: 
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    if user["rol"] != 'admin' and reserva.usuario_id != user["id"]: 
        raise HTTPException(status_code=403, detail="No autorizado")
    if reserva.estado == "cancelada": 
        raise HTTPException(status_code=400, detail="Reserva ya cancelada.")
    google_event_id_to_delete = getattr(reserva, 'google_event_id', None)
    reserva.estado = "cancelada"
    try:
        db.commit(); db.refresh(reserva)
        print(f"INFO: Reserva local {reserva_id} cancelada.")
        if google_event_id_to_delete:
            try:
                print(f"INFO: Intentando eliminar evento de Google {google_event_id_to_delete} para reserva {reserva_id}.")
                # Assuming delete_calendar_event takes the event ID
                deleted = calendar_service.delete_calendar_event(google_event_id_to_delete)
                if deleted and hasattr(reserva, 'google_event_id'):
                    reserva.google_event_id = None; db.commit(); db.refresh(reserva) # Clear the ID from DB
                    print(f"INFO: ID de evento de Google limpiado para reserva {reserva_id}.")
                elif not deleted: 
                    print(f"WARN: No se pudo eliminar el evento de Google {google_event_id_to_delete} (ID podría ser inválido o ya eliminado).")
            except Exception as calendar_e: 
                print(f"ERROR: Falló la eliminación del evento en Google Calendar para reserva {reserva_id}: {calendar_e}")
        else: 
            print(f"INFO: No hay ID de evento de Google asociado a reserva {reserva_id} para eliminar.")

        # Ensure returned datetimes are UTC aware
        reserva.inicio = reserva.inicio.astimezone(timezone.utc)
        reserva.fin = reserva.fin.astimezone(timezone.utc)
        return reserva
    except Exception as e:
        db.rollback(); print(f"ERROR canceling reservation {reserva_id}: {e}"); traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al cancelar reserva local: {e}")


# --- Préstamos ---
@app.get("/prestamos/mis-solicitudes", response_model=List[schemas.Prestamo], tags=["Préstamos"])
def get_mis_prestamos(user: CurrentUser, db: DbSession):
    prestamos = db.query(models.Prestamo).options(joinedload(models.Prestamo.recurso).joinedload(models.Recurso.laboratorio), joinedload(models.Prestamo.usuario)).filter(models.Prestamo.usuario_id == user["id"]).order_by(models.Prestamo.id.desc()).all()
    for p in prestamos:
        # Ensure UTC aware datetimes
        p.inicio = p.inicio.astimezone(timezone.utc)
        p.fin = p.fin.astimezone(timezone.utc)
        p.created_at = p.created_at.astimezone(timezone.utc)
    return prestamos

@app.post("/prestamos", response_model=schemas.Prestamo, status_code=status.HTTP_201_CREATED, tags=["Préstamos"])
def create_prestamo(prestamo: schemas.PrestamoCreate, user: CurrentUser, db: DbSession):
    recurso = db.get(models.Recurso, prestamo.recurso_id)
    if not recurso: 
        raise HTTPException(status_code=404, detail=f"Recurso id {prestamo.recurso_id} no encontrado.")
    if prestamo.usuario_id != user["id"] and user["rol"] != "admin": 
        raise HTTPException(status_code=403, detail="No autorizado para crear préstamo para otro usuario.")
    sol_user = db.get(models.Usuario, prestamo.usuario_id)
    if not sol_user: 
        raise HTTPException(status_code=404, detail="Usuario id no encontrado.")

    # Ensure UTC aware datetimes
    inicio = prestamo.inicio.astimezone(timezone.utc)
    fin = prestamo.fin.astimezone(timezone.utc)

    if inicio >= fin: 
        raise HTTPException(status_code=400, detail="Inicio debe ser anterior a fin.")
    if prestamo.cantidad < 1: 
        raise HTTPException(status_code=400, detail="Cantidad debe ser >= 1.")
    new_prestamo = models.Prestamo(
        recurso_id=prestamo.recurso_id, usuario_id=prestamo.usuario_id, solicitante=sol_user.nombre,
        cantidad=prestamo.cantidad, inicio=inicio, fin=fin, comentario=prestamo.comentario, estado="pendiente"
    )
    db.add(new_prestamo)
    try:
        db.commit(); db.refresh(new_prestamo); db.refresh(new_prestamo.recurso); db.refresh(new_prestamo.usuario)
        # Ensure UTC aware datetimes for response
        new_prestamo.inicio = new_prestamo.inicio.astimezone(timezone.utc)
        new_prestamo.fin = new_prestamo.fin.astimezone(timezone.utc)
        new_prestamo.created_at = new_prestamo.created_at.astimezone(timezone.utc)
        return new_prestamo
    except Exception as e:
        db.rollback(); print(f"ERROR creating loan: {e}"); traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error al crear préstamo: {e}")

@app.get("/admin/prestamos", response_model=List[schemas.Prestamo], tags=["Préstamos (Admin)"])
def get_todos_los_prestamos(user: AdminUser, db: DbSession):
    prestamos = db.query(models.Prestamo).options(joinedload(models.Prestamo.recurso), joinedload(models.Prestamo.usuario)).order_by(models.Prestamo.id.desc()).all()
    for p in prestamos:
        # Ensure UTC aware datetimes
        p.inicio = p.inicio.astimezone(timezone.utc)
        p.fin = p.fin.astimezone(timezone.utc)
        p.created_at = p.created_at.astimezone(timezone.utc)
    return prestamos

@app.put("/admin/prestamos/{prestamo_id}/estado", response_model=schemas.Prestamo, tags=["Préstamos (Admin)"])
def update_prestamo_estado(prestamo_id: int, nuevo_estado: str, user: AdminUser, db: DbSession):
    prestamo = db.query(models.Prestamo).options(joinedload(models.Prestamo.recurso)).filter(models.Prestamo.id == prestamo_id).first()
    if not prestamo: 
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    allowed_states = ["pendiente", "aprobado", "rechazado", "entregado", "devuelto"]
    if nuevo_estado not in allowed_states: 
        raise HTTPException(status_code=400, detail="Estado no válido.")
    old_status = prestamo.estado
    prestamo.estado = nuevo_estado
    recurso_updated = False
    if prestamo.recurso:
        if old_status != 'devuelto' and nuevo_estado == "devuelto": 
            prestamo.recurso.estado = "disponible"; recurso_updated = True
        elif old_status != 'entregado' and nuevo_estado == "entregado": 
            prestamo.recurso.estado = "prestado"; recurso_updated = True
    try:
        db.commit(); db.refresh(prestamo); db.refresh(prestamo.recurso); db.refresh(prestamo.usuario)
        print(f"INFO: Préstamo {prestamo_id} actualizado a '{nuevo_estado}'. Estado recurso: '{prestamo.recurso.estado if prestamo.recurso else 'N/A'}'")
        # Ensure UTC aware datetimes for response
        prestamo.inicio = prestamo.inicio.astimezone(timezone.utc)
        prestamo.fin = prestamo.fin.astimezone(timezone.utc)
        prestamo.created_at = prestamo.created_at.astimezone(timezone.utc)
        return prestamo
    except Exception as e:
        db.rollback(); print(f"ERROR updating loan state {prestamo_id}: {e}"); traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al actualizar estado del préstamo: {e}")

# Health check endpoint for Railway
@app.get("/")
async def root():
    return {"message": "API del Gestor de Laboratorios funcionando correctamente", "status": "online"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}