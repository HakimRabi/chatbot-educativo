from sqlalchemy import create_engine, Column, Integer, String, Text, text, JSON, TIMESTAMP, Float, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime
from config import DATABASE_URL
import enum

# Configurar bcrypt para el hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Crear engine y sesión
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Función para verificar conexión a la base de datos
def check_db_connection():
    """Verifica si la conexión a la base de datos está funcionando"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        print(f"Error verificando conexión DB: {e}")
        return False

# Modelos de Base de Datos
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))
    email = Column(String(100), unique=True)
    password = Column(String(100))
    created_at = Column(String(100))
    permisos = Column(String(10), nullable=False, server_default=text("'usuario'"))

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    session_id = Column(String(255), primary_key=True)
    user_id = Column(String(255), primary_key=True)
    history = Column(JSON, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    session_id = Column(String(255), nullable=False)
    pregunta = Column(Text, nullable=False)
    respuesta = Column(Text, nullable=False)
    rating = Column(Integer)
    comentario = Column(Text)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

class SessionPdfs(Base):
    __tablename__ = "session_pdfs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    session_id = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    page_count = Column(Integer)
    upload_time = Column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

# Enum para estados de tareas
class TaskStatusEnum(str, enum.Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


# Enum para estados de tests de estres (reutiliza los mismos valores)
class StressTestStatusEnum(str, enum.Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class ChatTask(Base):
    __tablename__ = "chat_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255))
    
    # Información de la consulta
    query = Column(Text, nullable=False)
    query_length = Column(Integer)
    response = Column(Text)
    response_length = Column(Integer)
    
    # Modelo y configuración
    model = Column(String(50), server_default=text("'llama3'"))
    worker_name = Column(String(100))
    
    # Estados y tiempos
    status = Column(Enum(TaskStatusEnum), server_default=text("'PENDING'"), index=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    processing_time = Column(Float)
    
    # Metadata adicional
    vector_db_used = Column(Boolean, server_default=text("FALSE"))
    documents_count = Column(Integer, server_default=text("0"))
    error_message = Column(Text, nullable=True)
    
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'), index=True)


class StressTest(Base):
    """Modelo para tests de estres del sistema"""
    __tablename__ = "stress_tests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    
    # Configuracion del test
    config = Column(JSON, nullable=False)
    
    # Estado
    status = Column(Enum(StressTestStatusEnum), server_default=text("'PENDING'"), index=True)
    
    # Tiempos
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Hardware donde se ejecuto
    hardware_info = Column(JSON, nullable=True)
    
    # Resultados
    metrics_snapshots = Column(JSON, nullable=True)
    summary = Column(JSON, nullable=True)
    log_entries = Column(JSON, nullable=True)
    
    # Metadata
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'), index=True)


# Solicitudes (Pydantic models)
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
    nombre_completo: Optional[str] = None

class SolicitudChat(BaseModel):
    texto: str
    userId: str
    chatToken: str
    history: Optional[List[Dict[str, Any]]] = []
    modelo: Optional[str] = "llama3"

class SolicitudSugerencias(BaseModel):
    history: Optional[List[Dict[str, Any]]] = []

class AsyncChatRequest(BaseModel):
    texto: str
    userId: str
    chatToken: str
    history: Optional[List[Dict[str, Any]]] = []
    modelo: Optional[str] = "llama3"


# Modelos para Diagnosticos de Estres
class StressTestConfig(BaseModel):
    """Configuracion para un test de estres"""
    test_type: str = "concurrent_users"
    concurrent_users: int = 5
    queries_per_user: int = 5
    duration_seconds: int = 120
    ramp_up_seconds: int = 0
    query_complexity: str = "medium"
    model_target: str = "phi4"
    use_rag: bool = True
    snapshot_interval_seconds: int = 5
    custom_queries: Optional[List[str]] = None


class StartStressTestRequest(BaseModel):
    """Request para iniciar un test de estres"""
    name: str
    config: StressTestConfig
