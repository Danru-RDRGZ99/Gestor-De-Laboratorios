import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv

load_dotenv()

# ANTES:
# DATABASE_URL = os.getenv("DATABASE_URL")

# AHORA (Añadiendo +pg8000):
DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+pg8000://")


engine=create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
