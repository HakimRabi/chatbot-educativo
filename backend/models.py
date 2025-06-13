from sqlalchemy import create_engine, Column, Integer, String, text, JSON, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from passlib.context import CryptContext
from config import DATABASE_URL

# Configurar bcrypt para el hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Crear engine y sesión
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Modelos de Base de Datos
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    password = Column(String(100))
    created_at = Column(String(100))
    permisos = Column(String(10), nullable=False, default='usuario')

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    session_id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=False)
    history = Column(JSON, nullable=False)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    session_id = Column(String(255), nullable=False)
    pregunta = Column(String(1000), nullable=False)
    respuesta = Column(String(1000), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

# Modelos Pydantic
class Pregunta(BaseModel):
    texto: str
    userId: str = None
    chatToken: str = None
    history: list = None

class SessionIn(BaseModel):
    user_id: str
    session_id: str
    history: list

class FeedbackIn(BaseModel):
    user_id: str
    session_id: str
    pregunta: str
    respuesta: str
    rating: int
    comentario: str = None

class SolicitudSugerencias(BaseModel):
    userId: str = None
    chatToken: str = None
    history: list = None

class SugerenciasIn(BaseModel):
    history: list = None

# Crear las tablas si no existen
Base.metadata.create_all(bind=engine)

def check_db_connection():
    """Función para verificar conexión a la base de datos"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text('SELECT 1')).fetchone()
            return result is not None
    except Exception as e:
        print("Error de conexión a la base de datos:", e)
        return False
