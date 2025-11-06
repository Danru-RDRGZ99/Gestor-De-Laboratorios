from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import secrets
import string

# --- Configuration ---
# IMPORTANT: Change this key to a long, random string in a real application.
SECRET_KEY = "PPHAPxHz2PnKhGzwK2nqV02Ws2kKLSedkfHfcmC62mI" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # Token lasts for 8 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def generate_random_password(length=16):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Asegúrate de que la contraseña cumpla con cualquier requisito mínimo si lo tienes
    # Esta versión es simple, podrías querer forzar ciertos tipos de caracteres.
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# --- Token Creation ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Token Verification and User Retrieval (Dependency) ---
def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """Decodes the token and returns the user payload if valid."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        rol: str = payload.get("rol")
        if username is None or user_id is None or rol is None:
            raise credentials_exception
        return {"id": user_id, "user": username, "rol": rol}
    except JWTError:
        raise credentials_exception

def get_current_admin_user(current_user: Annotated[dict, Depends(get_current_user)]):
    """Dependency to ensure the current user has the 'admin' role."""
    if current_user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    return current_user
