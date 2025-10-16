from sqlalchemy.orm import Session
# ANTES: from .models import User
from . import models  # AHORA: Importa el módulo completo
from .schemas import UserCreate, UserLogin
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def register_user(db: Session, user: UserCreate):
    hashed_password = pwd_context.hash(user.password)
    # ANTES: db_user = User(...)
    db_user = models.User(username=user.username, hashed_password=hashed_password) # AHORA: Usa models.User
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def login(db: Session, user: UserLogin):
    # ANTES: db_user = db.query(User)...
    db_user = db.query(models.User).filter(models.User.username == user.username).first() # AHORA: Usa models.User
    if db_user and pwd_context.verify(user.password, db_user.hashed_password):
        access_token = create_access_token(data={"sub": db_user.username})
        return {"access_token": access_token, "token_type": "bearer"}
    return None

