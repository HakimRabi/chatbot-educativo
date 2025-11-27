# CHATBOT EDUCATIVO UNAB - DOCUMENTACION TECNICA COMPLETA

**Version:** 2.1  
**Rama Git:** feature/phase2-vllm-integration  
**Repositorio:** github.com/HakimRabi/chatbot-educativo  
**Ultima Actualizacion:** Noviembre 2025

---

# TABLA DE CONTENIDOS

1. [Descripcion General](#1-descripcion-general)
2. [Stack Tecnologico](#2-stack-tecnologico)
3. [Arquitectura del Sistema](#3-arquitectura-del-sistema)
4. [Estructura del Proyecto](#4-estructura-del-proyecto)
5. [Codigo Fuente - Backend](#5-codigo-fuente---backend)
6. [Codigo Fuente - Frontend](#6-codigo-fuente---frontend)
7. [API REST - Endpoints Completos](#7-api-rest---endpoints-completos)
8. [Base de Datos](#8-base-de-datos)
9. [Sistema RAG](#9-sistema-rag)
10. [Sistema de Diagnosticos](#10-sistema-de-diagnosticos)
11. [Docker y Despliegue](#11-docker-y-despliegue)
12. [Variables de Entorno](#12-variables-de-entorno)
13. [Seguridad](#13-seguridad)

---

# 1. DESCRIPCION GENERAL

## 1.1 Proposito

Chatbot Educativo es un asistente academico inteligente para estudiantes del curso "Fundamentos de Inteligencia Artificial" (CINF103) de la Universidad Andres Bello.

## 1.2 Caracteristicas Principales

- Chat con IA usando modelos de lenguaje locales (Ollama)
- RAG (Retrieval-Augmented Generation) para respuestas contextualizadas con material del curso
- Streaming de respuestas en tiempo real via SSE (Server-Sent Events)
- Dashboard de administracion con analisis de feedback
- Sistema de diagnosticos y stress testing
- Procesamiento asincrono con Celery + Redis
- Soporte multi-modelo (Llama 3, Phi 4)
- Autenticacion con Cloudflare Turnstile
- Exportacion de reportes a CSV, TXT, JSON, XLSX

## 1.3 Usuarios

- **Estudiantes**: Chat con el asistente para consultas academicas
- **Administradores**: Dashboard completo, gestion de usuarios, analisis, diagnosticos

---

# 2. STACK TECNOLOGICO

## 2.1 Backend

| Tecnologia | Version | Proposito |
|------------|---------|-----------|
| Python | 3.11+ | Lenguaje principal |
| FastAPI | 0.115.4 | Framework API REST |
| LangChain | 0.3.7 | Orquestacion LLM y RAG |
| Ollama | 0.3.3 | Interface modelos locales |
| ChromaDB | 0.5.18 | Base de datos vectorial |
| FAISS | 1.9.0 | Busqueda vectores (fallback) |
| SQLAlchemy | 2.0.35 | ORM para MySQL |
| PyMySQL | 1.1.1 | Driver MySQL |
| Celery | 5.4.0 | Procesamiento asincrono |
| Redis | 5.2.0 | Broker mensajes/cache |
| Uvicorn | 0.32.0 | Servidor ASGI |
| aiohttp | 3.9.0+ | Cliente HTTP asincrono |
| openpyxl | 3.1.0+ | Generacion Excel |
| psutil | 6.0+ | Metricas sistema |
| GPUtil | - | Metricas GPU (opcional) |
| bcrypt/passlib | - | Hash de passwords |
| httpx | - | Cliente HTTP para Turnstile |

## 2.2 Frontend

| Tecnologia | Proposito |
|------------|-----------|
| HTML5/CSS3 | Estructura y estilos |
| JavaScript ES6+ | Logica del cliente |
| Marked.js | Renderizado Markdown |
| KaTeX | Ecuaciones matematicas |
| Prism.js | Syntax highlighting |
| SweetAlert2 | Modales y notificaciones |
| Chart.js | Graficos dashboard |
| Font Awesome 6 | Iconografia |

## 2.3 Bases de Datos

| Base de Datos | Uso |
|---------------|-----|
| MySQL 8.0 | Usuarios, sesiones, feedback, tareas |
| ChromaDB | Embeddings y busqueda semantica |
| Redis 7.2 | Cola de tareas y cache |

## 2.4 Infraestructura

| Componente | Proposito |
|------------|-----------|
| Docker | Containerizacion |
| Docker Compose | Orquestacion local |
| Nginx | Proxy reverso |
| AWS ECR | Registro imagenes |
| Flower | Monitoreo Celery |

---

# 3. ARQUITECTURA DEL SISTEMA

```
+------------------------------------------------------------------+
|                      CLIENTE (Navegador)                          |
|  +---------------+  +---------------+  +---------------+          |
|  |  index.html   |  |  dashboard    |  |    login      |          |
|  |    (Chat)     |  |    .html      |  |    .html      |          |
|  +-------+-------+  +-------+-------+  +-------+-------+          |
+----------|--------------------|-----------------|------------------+
           |                    |                 |
           +--------------------+-----------------+
                               |
                          HTTP/SSE
                               |
+------------------------------v-----------------------------------+
|                      NGINX (Proxy :80)                           |
|    /api/* -> backend:8000    /* -> frontend estatico             |
+------------------------------+-----------------------------------+
                               |
+------------------------------v-----------------------------------+
|                    BACKEND (FastAPI:8000)                        |
|                                                                   |
|  +-------------+  +-------------+  +-------------+  +-----------+ |
|  |   app.py    |  |  auth.py    |  | dashboard.py|  |  chat.py  | |
|  | (API Core)  |  | (JWT/Auth)  |  | (Admin API) |  | (Feedback)| |
|  +------+------+  +-------------+  +------+------+  +-----------+ |
|         |                                 |                       |
|  +------v------+                  +-------v-------+               |
|  | ai_system.py|                  |  diagnostics/ |               |
|  | (RAG + LLM) |                  | (Stress Test) |               |
|  +------+------+                  +---------------+               |
+---------|---------------------------------------------------------+
          |
    +-----+-----+
    |           |
+---v---+  +----v----+     +-------------+     +------------------+
|ChromaDB|  | Ollama  |<----|   Celery    |---->|     Flower       |
|(Vector)|  |  (LLM)  |     |   Worker    |     |   (:5555)        |
+--------+  +---------+     +------+------+     +------------------+
                                   |
+--------+  +---------+     +------v------+
| MySQL  |  |  Redis  |<----|   Broker    |
| (:3306)|  | (:6379) |     +-------------+
+--------+  +---------+
```

## 3.1 Flujo de una Consulta

1. Usuario envia pregunta desde frontend
2. Request llega a `/preguntar` en FastAPI
3. `ai_system.py` analiza tipo de pregunta
4. Busca contexto relevante en ChromaDB (RAG)
5. Construye prompt con contexto
6. Envia a Ollama (LLM local)
7. Respuesta se streamea via SSE
8. Historial se guarda en MySQL
9. Feedback opcional se almacena

---

# 4. ESTRUCTURA DEL PROYECTO

```
chatbot-educativo/
|
+-- backend/
|   +-- app.py                    # FastAPI - aplicacion principal (1819 lineas)
|   +-- ai_system.py              # Sistema RAG + LLM (1088 lineas)
|   +-- auth.py                   # Autenticacion Turnstile (203 lineas)
|   +-- chat.py                   # Endpoints feedback
|   +-- dashboard.py              # API dashboard admin (2439 lineas)
|   +-- config.py                 # Configuracion centralizada
|   +-- database.py               # Conexion SQLAlchemy
|   +-- models.py                 # Modelos SQLAlchemy + Pydantic (201 lineas)
|   +-- celery_worker.py          # Worker tareas asincronas
|   +-- metrics.py                # Sistema metricas
|   +-- templates.py              # Plantillas prompts (273 lineas)
|   +-- utils.py                  # Funciones utilitarias
|   +-- Dockerfile                # Imagen Docker backend
|   +-- Dockerfile.worker         # Imagen worker Celery
|   +-- requirements-prod.txt     # Dependencias produccion
|   |
|   +-- diagnostics/              # Modulo diagnosticos
|   |   +-- __init__.py
|   |   +-- metrics_collector.py  # Recolector metricas HW (185 lineas)
|   |   +-- stress_runner.py      # Ejecutor stress tests (484 lineas)
|   |   +-- report_generator.py   # Generador reportes (612 lineas)
|   |
|   +-- data/
|       +-- pdfs/                 # Documentos del curso
|       +-- chroma_db/            # Base vectorial
|       +-- faiss_index/          # Indice FAISS
|       +-- cache/                # Cache embeddings
|
+-- frontend/
|   +-- index.html                # Chat principal
|   +-- Dockerfile                # Imagen Nginx
|   +-- nginx.conf                # Config proxy (106 lineas)
|   |
|   +-- pages/
|   |   +-- login.html            # Login/registro
|   |   +-- dashboard.html        # Panel admin
|   |
|   +-- assets/
|       +-- css/
|       |   +-- index.css         # Estilos chat
|       |   +-- login.css         # Estilos login
|       |   +-- dashboard.css     # Estilos dashboard
|       |
|       +-- js/
|       |   +-- chat.js           # Logica chat
|       |   +-- login.js          # Logica auth
|       |   +-- dashboard.js      # Logica dashboard
|       |   +-- notifications.js  # Notificaciones
|       |
|       +-- figures/              # Imagenes curso
|
+-- pushAWS/                      # Scripts despliegue AWS
|   +-- build.sh
|   +-- push.sh
|   +-- login.sh
|
+-- docker-compose.yml            # Orquestacion servicios
+-- init-db.sql                   # Schema MySQL (187 lineas)
+-- requirements.txt              # Deps desarrollo
```

---

# 5. CODIGO FUENTE - BACKEND

## 5.1 config.py - Configuracion Central

```python
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configuracion de Base de Datos
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "rootchatbot")
DB_HOST = os.getenv("DB_HOST", "host.docker.internal")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "bd_chatbot")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# Configuracion de Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.31.88.219:11434")

# Configuracion de archivos
PDFS_DIR = os.path.join(os.path.dirname(__file__), "data", "pdfs")  
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")  
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "data", "chroma_db")  
FAISS_PATH = os.path.join(os.path.dirname(__file__), "data", "faiss_index") 

# Configuracion del modelo
MODEL_NAME = "llama3"
MODEL_TEMPERATURE = 0.3
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Configuracion de modelos disponibles
AVAILABLE_MODELS = {
    "llama3": {
        "name": "llama3",
        "display_name": "Llama 3",
        "description": "Modelo rapido y general",
        "temperature": 0.3
    },
    "phi4": {
        "name": "phi4", 
        "display_name": "Phi 4",
        "description": "Modelo avanzado de razonamiento",
        "temperature": 0.2
    }
}

DEFAULT_MODEL = "llama3"

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
```

## 5.2 models.py - Modelos de Datos

```python
from sqlalchemy import create_engine, Column, Integer, String, Text, text, JSON, TIMESTAMP, Float, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime
from config import DATABASE_URL
import enum

# Configurar bcrypt para hash de passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Crear engine y sesion
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_db_connection():
    """Verifica conexion a la base de datos"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        print(f"Error verificando conexion DB: {e}")
        return False

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

class TaskStatusEnum(str, enum.Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'

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
    query = Column(Text, nullable=False)
    query_length = Column(Integer)
    response = Column(Text)
    response_length = Column(Integer)
    model = Column(String(50), server_default=text("'llama3'"))
    worker_name = Column(String(100))
    status = Column(Enum(TaskStatusEnum), server_default=text("'PENDING'"), index=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    processing_time = Column(Float)
    vector_db_used = Column(Boolean, server_default=text("FALSE"))
    documents_count = Column(Integer, server_default=text("0"))
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'), index=True)

class StressTest(Base):
    __tablename__ = "stress_tests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    config = Column(JSON, nullable=False)
    status = Column(Enum(StressTestStatusEnum), server_default=text("'PENDING'"), index=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    hardware_info = Column(JSON, nullable=True)
    metrics_snapshots = Column(JSON, nullable=True)
    summary = Column(JSON, nullable=True)
    log_entries = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'), index=True)

# Pydantic Models para Request/Response
class SolicitudChat(BaseModel):
    texto: str
    userId: str
    chatToken: str
    history: list = []
    modelo: str = "llama3"

class StressTestConfig(BaseModel):
    test_type: str = "concurrent_users"
    concurrent_users: int = 5
    queries_per_user: int = 5
    duration_seconds: int = 120
    ramp_up_seconds: int = 0
    query_complexity: str = "medium"
    model_target: str = "phi4"
    use_rag: bool = True
    snapshot_interval_seconds: int = 5
    custom_queries: list = None

class StartStressTestRequest(BaseModel):
    name: str
    config: StressTestConfig
```

## 5.3 app.py - Aplicacion Principal (Fragmento Clave)

```python
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Imports internos
from config import *
from models import *
from ai_system import AISystem

logger = logging.getLogger("chatbot_app")
app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variable global sistema IA
ai_system_instance = None
ai_system_ready = False
executor = ThreadPoolExecutor(max_workers=4)

@app.on_event("startup")
async def startup_event():
    """Inicializa el sistema al arrancar"""
    global ai_system_instance, ai_system_ready
    
    logger.info("=" * 60)
    logger.info("INICIANDO CHATBOT EDUCATIVO")
    logger.info("=" * 60)
    
    # Inicializar sistema IA
    ai_system_instance = AISystem()
    ai_system_instance.initialize()
    ai_system_ready = True
    
    logger.info("Sistema IA listo")

@app.post("/preguntar")
async def preguntar(request: Request):
    """Endpoint principal para procesar preguntas"""
    global ai_system_instance, ai_system_ready
    
    if not ai_system_ready:
        return {"respuesta": "Sistema no disponible", "status": "error"}
    
    data = await request.json()
    texto = data.get("texto", "")
    user_id = data.get("userId", "")
    session_id = data.get("chatToken", "")
    history = data.get("history", [])
    modelo = data.get("modelo", "llama3")
    
    # Procesar pregunta
    loop = asyncio.get_event_loop()
    respuesta = await loop.run_in_executor(
        executor,
        lambda: ai_system_instance.process_question(
            texto, history, modelo
        )
    )
    
    return {"respuesta": respuesta, "status": "success"}

@app.get("/modelos")
async def obtener_modelos():
    """Lista modelos disponibles"""
    return {
        "modelos": AVAILABLE_MODELS,
        "actual": ai_system_instance.get_current_model() if ai_system_instance else DEFAULT_MODEL
    }

@app.post("/cambiar_modelo")
async def cambiar_modelo(request: Request):
    """Cambia el modelo activo"""
    data = await request.json()
    modelo = data.get("modelo", DEFAULT_MODEL)
    
    if ai_system_instance:
        success = ai_system_instance.switch_model(modelo)
        return {"success": success, "modelo": modelo}
    
    return {"success": False, "error": "Sistema no disponible"}
```

## 5.4 ai_system.py - Sistema RAG + LLM (Fragmento Clave)

```python
import os
import logging
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.document_loaders import PyPDFLoader

from config import *
from templates import *

logger = logging.getLogger("ai_system")

class AISystem:
    def __init__(self):
        self.fragmentos = []
        self.documentos = []
        self.using_vector_db = False
        self.using_chroma = False
        self.cadena = None
        self.llm = None
        self.llm_cache = {}
        self.current_model = None
        self.memory = None
        self.vector_store = None
        self.is_initialized = False
    
    def get_or_create_llm(self, model_name=None):
        """Obtiene o crea instancia LLM para el modelo"""
        if model_name is None:
            model_name = DEFAULT_MODEL
            
        if model_name not in AVAILABLE_MODELS:
            model_name = DEFAULT_MODEL
            
        if model_name in self.llm_cache:
            return self.llm_cache[model_name]
            
        model_config = AVAILABLE_MODELS[model_name]
        
        llm_instance = OllamaLLM(
            model=model_config["name"],
            temperature=model_config["temperature"],
            base_url=OLLAMA_URL
        )
        
        self.llm_cache[model_name] = llm_instance
        return llm_instance
    
    def switch_model(self, model_name):
        """Cambia modelo preservando contexto"""
        new_llm = self.get_or_create_llm(model_name)
        self.llm = new_llm
        self.current_model = model_name
        
        # Recrear cadena RAG con nuevo modelo
        if self.vector_store is not None:
            retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            self.cadena = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": PROMPT_QA_SIMPLE}
            )
        
        return True
    
    def initialize(self):
        """Inicializa el sistema completo"""
        # 1. Crear LLM
        self.llm = self.get_or_create_llm(DEFAULT_MODEL)
        self.current_model = DEFAULT_MODEL
        
        # 2. Cargar documentos
        self._load_documents()
        
        # 3. Crear vector store
        self._setup_vector_store()
        
        # 4. Crear cadena RAG
        self._setup_chain()
        
        self.is_initialized = True
    
    def _load_documents(self):
        """Carga PDFs del directorio"""
        pdf_files = glob(os.path.join(PDFS_DIR, "*.pdf"))
        
        for pdf_path in pdf_files:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            self.documentos.extend(docs)
        
        # Dividir en fragmentos
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        self.fragmentos = splitter.split_documents(self.documentos)
    
    def _setup_vector_store(self):
        """Configura ChromaDB o FAISS"""
        try:
            embeddings = OllamaEmbeddings(
                model="llama3",
                base_url=OLLAMA_URL
            )
            
            # Intentar ChromaDB primero
            self.vector_store = Chroma.from_documents(
                self.fragmentos,
                embeddings,
                persist_directory=CHROMA_PATH
            )
            self.using_chroma = True
            self.using_vector_db = True
            
        except Exception as e:
            # Fallback a FAISS
            self.vector_store = FAISS.from_documents(
                self.fragmentos,
                embeddings
            )
            self.using_vector_db = True
    
    def _setup_chain(self):
        """Configura cadena RetrievalQA"""
        if self.vector_store:
            retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            self.cadena = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": PROMPT_QA_SIMPLE}
            )
    
    def process_question(self, pregunta, history=None, modelo=None):
        """Procesa una pregunta y genera respuesta"""
        if modelo and modelo != self.current_model:
            self.switch_model(modelo)
        
        # Usar cadena RAG si disponible
        if self.cadena:
            result = self.cadena.invoke({"query": pregunta})
            return result["result"]
        
        # Fallback sin RAG
        return self.llm.invoke(pregunta)
    
    def get_context_status(self):
        """Estado actual del sistema"""
        return {
            "current_model": self.current_model,
            "documents_loaded": len(self.documentos),
            "fragments_available": len(self.fragmentos),
            "vector_store_type": "ChromaDB" if self.using_chroma else "FAISS",
            "vector_store_active": self.vector_store is not None,
            "rag_chain_active": self.cadena is not None
        }
```

## 5.5 auth.py - Autenticacion con Turnstile

```python
import logging
import os
import httpx
from datetime import datetime
from fastapi import APIRouter, Request
from models import User, SessionLocal, pwd_context

logger = logging.getLogger("auth")
router = APIRouter()

TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

async def verify_turnstile(token: str, ip: str = None) -> bool:
    """Verificar token Cloudflare Turnstile"""
    if not TURNSTILE_SECRET_KEY:
        return True  # Desarrollo sin Turnstile
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": TURNSTILE_SECRET_KEY,
                    "response": token,
                    "remoteip": ip
                }
            )
            result = response.json()
            return result.get("success", False)
    except Exception as e:
        logger.error(f"Error verificando Turnstile: {e}")
        return False

@router.post("/register")
async def register_user(request: Request):
    data = await request.json()
    
    nombre = data.get("nombre")
    email = data.get("email")
    password = data.get("password")
    turnstile_token = data.get("turnstile_token")
    
    if not all([nombre, email, password]):
        return {"success": False, "message": "Campos requeridos"}
    
    # Verificar Turnstile
    client_ip = request.client.host if request.client else None
    if not await verify_turnstile(turnstile_token, client_ip):
        return {"success": False, "message": "Verificacion fallida"}
    
    # Truncar password a 72 bytes (limite bcrypt)
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        password = password_bytes.decode('utf-8', errors='ignore')
    
    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {"success": False, "message": "Email ya registrado"}
        
        hashed_password = pwd_context.hash(password)
        new_user = User(
            nombre=nombre,
            email=email,
            password=hashed_password,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "success": True,
            "user": {"id": new_user.id, "nombre": new_user.nombre, "email": new_user.email}
        }

@router.post("/login")
async def login_user(request: Request):
    data = await request.json()
    
    email = data.get("email")
    password = data.get("password")
    turnstile_token = data.get("turnstile_token")
    
    # Verificar Turnstile
    client_ip = request.client.host if request.client else None
    if not await verify_turnstile(turnstile_token, client_ip):
        return {"success": False, "message": "Verificacion fallida"}
    
    # Truncar password
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        password = password_bytes.decode('utf-8', errors='ignore')
    
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            return {"success": False, "message": "Credenciales incorrectas"}
        
        if not pwd_context.verify(password, user.password):
            return {"success": False, "message": "Credenciales incorrectas"}
        
        permisos = user.permisos or 'usuario'
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "nombre": user.nombre,
                "email": user.email,
                "permisos": permisos
            }
        }

@router.post("/verify-role")
async def verify_role(request: Request):
    """Verificar rol de usuario desde servidor"""
    data = await request.json()
    user_id = data.get("user_id")
    
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return {"success": False, "is_admin": False}
        
        is_admin = user.permisos == 'admin'
        
        return {
            "success": True,
            "is_admin": is_admin,
            "user_id": user.id,
            "permisos": user.permisos
        }
```

## 5.6 templates.py - Plantillas de Prompts

```python
from langchain.prompts import PromptTemplate

contexto_base = (
    "Eres un asistente virtual especializado en Fundamentos de Inteligencia Artificial, "
    "orientado a estudiantes universitarios. Tu funcion es apoyar el aprendizaje, "
    "responder preguntas, aclarar conceptos sobre IA, machine learning, algoritmos, "
    "etica, redes neuronales, agentes inteligentes. "
    "Adapta respuestas al nivel universitario, siendo claro y didactico. "
    "Siempre responde en espanol."
)

plantilla_qa_simple_str = (
    "Contexto: Eres un asistente educativo de Fundamentos de IA.\n\n"
    "Instrucciones:\n"
    "- Usa informacion de los documentos recuperados\n"
    "- Organiza respuesta en parrafos claros\n"
    "- Incluye ejemplos cuando sea relevante\n"
    "- Si la info no esta en documentos, indicalo\n\n"
    "Documentos relevantes:\n{context}\n\n"
    "Pregunta: {question}\n\n"
    "Respuesta educativa en espanol:"
)

PROMPT_QA_SIMPLE = PromptTemplate(
    template=plantilla_qa_simple_str,
    input_variables=["context", "question"]
)

plantilla_detallada = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Proporciona explicacion completa y detallada:\n"
        "1. Definicion o concepto principal\n"
        "2. Explicacion detallada\n"
        "3. Ejemplos concretos\n"
        "4. Relacion con otros conceptos IA\n\n"
        "Conversacion previa:\n{conversacion}\n\n"
        "Pregunta: {pregunta}\n\n"
        "Respuesta detallada:"
    )
)

plantilla_concisa = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Respuesta clara y directa en 3-5 oraciones.\n\n"
        "Conversacion previa:\n{conversacion}\n\n"
        "Pregunta: {pregunta}\n\n"
        "Respuesta concisa:"
    )
)
```

---

# 6. CODIGO FUENTE - FRONTEND

## 6.1 Estructura HTML Principal (index.html)

El chat principal incluye:
- Sidebar con historial de sesiones
- Area de mensajes con scroll
- Input de texto con sugerencias
- Selector de modelo
- Modo oscuro/claro

## 6.2 JavaScript del Chat (chat.js - Fragmento)

```javascript
// Configuracion API
const API_BASE = window.location.origin;

// Estado global
let currentSession = null;
let currentModel = 'llama3';
let chatHistory = [];

// Enviar mensaje
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Agregar mensaje usuario
    addMessage('user', message);
    input.value = '';
    
    // Mostrar typing indicator
    showTypingIndicator();
    
    try {
        const response = await fetch(`${API_BASE}/preguntar`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                texto: message,
                userId: getUserId(),
                chatToken: currentSession,
                history: chatHistory,
                modelo: currentModel
            })
        });
        
        const data = await response.json();
        
        hideTypingIndicator();
        
        if (data.status === 'success') {
            addMessage('bot', data.respuesta);
            chatHistory.push({role: 'user', content: message});
            chatHistory.push({role: 'assistant', content: data.respuesta});
        }
    } catch (error) {
        hideTypingIndicator();
        addMessage('bot', 'Error al procesar mensaje');
    }
}

// Agregar mensaje al chat
function addMessage(role, content) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message ${role}-message`;
    
    // Renderizar markdown
    div.innerHTML = marked.parse(content);
    
    // Syntax highlighting
    div.querySelectorAll('pre code').forEach(block => {
        Prism.highlightElement(block);
    });
    
    // Renderizar LaTeX
    renderMathInElement(div, {
        delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false}
        ]
    });
    
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// Cambiar modelo
async function changeModel(model) {
    try {
        const response = await fetch(`${API_BASE}/cambiar_modelo`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({modelo: model})
        });
        
        const data = await response.json();
        if (data.success) {
            currentModel = model;
            updateModelSelector();
        }
    } catch (error) {
        console.error('Error cambiando modelo:', error);
    }
}
```

---

# 7. API REST - ENDPOINTS COMPLETOS

## 7.1 Autenticacion (/auth)

| Metodo | Endpoint | Descripcion | Body |
|--------|----------|-------------|------|
| POST | /auth/register | Registro usuario | {nombre, email, password, turnstile_token} |
| POST | /auth/login | Login | {email, password, turnstile_token} |
| POST | /auth/verify-role | Verificar rol | {user_id} |

## 7.2 Chat (raiz)

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| POST | /preguntar | Enviar pregunta al chatbot |
| GET | /historial/{session_id} | Obtener historial |
| POST | /guardar_historial | Guardar historial |
| GET | /sesiones/{user_id} | Listar sesiones |
| DELETE | /sesiones/{session_id} | Eliminar sesion |
| POST | /feedback | Guardar feedback |
| GET | /ratings/{session_id} | Obtener ratings |
| POST | /generar_sugerencias | Generar sugerencias |

## 7.3 Modelos

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | /modelos | Listar modelos |
| POST | /cambiar_modelo | Cambiar modelo activo |
| GET | /ai_status | Estado del sistema |

## 7.4 Dashboard (/dashboard)

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | /dashboard/check-access | Verificar acceso admin |
| GET | /dashboard/stats | Estadisticas generales |
| GET | /dashboard/users | Listar usuarios |
| GET | /dashboard/users/paginated | Usuarios paginados |
| PUT | /dashboard/users/{id} | Actualizar usuario |
| DELETE | /dashboard/users/{id} | Eliminar usuario |
| GET | /dashboard/feedback/paginated | Feedback paginado |
| GET | /dashboard/feedback-analysis | Analisis con IA |
| GET | /dashboard/system-health | Salud del sistema |
| GET | /dashboard/resource-usage | CPU/RAM/GPU |
| POST | /dashboard/upload-pdf | Subir PDF |

## 7.5 Diagnosticos (/dashboard/diagnostics)

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | /dashboard/diagnostics/hardware | Info hardware |
| GET | /dashboard/diagnostics/tests | Listar tests |
| GET | /dashboard/diagnostics/tests/{id} | Detalle test |
| GET | /dashboard/diagnostics/tests/{id}/status | Estado tiempo real |
| POST | /dashboard/diagnostics/tests/start | Iniciar test |
| POST | /dashboard/diagnostics/tests/{id}/stop | Detener test |
| GET | /dashboard/diagnostics/tests/{id}/export | Exportar reporte |
| DELETE | /dashboard/diagnostics/tests/{id} | Eliminar test |

---

# 8. BASE DE DATOS

## 8.1 Schema MySQL (init-db.sql)

```sql
CREATE DATABASE IF NOT EXISTS `bd_chatbot` 
DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE `bd_chatbot`;

-- Usuarios
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) DEFAULT NULL,
  `email` varchar(100) DEFAULT NULL,
  `password` varchar(100) DEFAULT NULL,
  `created_at` varchar(100) DEFAULT NULL,
  `permisos` enum('usuario','admin') NOT NULL DEFAULT 'usuario',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_email` (`email`)
);

-- Sesiones de chat
CREATE TABLE `chat_sessions` (
  `session_id` varchar(255) NOT NULL,
  `user_id` int NOT NULL,
  `history` json NOT NULL,
  `updated_at` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `session_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
);

-- Feedback
CREATE TABLE `feedback` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `session_id` varchar(255) NOT NULL,
  `pregunta` text NOT NULL,
  `respuesta` text NOT NULL,
  `rating` int DEFAULT NULL,
  `comentario` text,
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CHECK (`rating` between 1 and 5),
  FOREIGN KEY (`user_id`, `session_id`) REFERENCES `chat_sessions` (`user_id`, `session_id`) ON DELETE CASCADE
);

-- Tareas asincronas
CREATE TABLE `chat_tasks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `task_id` VARCHAR(255) UNIQUE NOT NULL,
    `user_id` INT NOT NULL,
    `session_id` VARCHAR(255),
    `query` TEXT NOT NULL,
    `response` TEXT,
    `model` VARCHAR(50) DEFAULT 'llama3',
    `status` ENUM('PENDING','PROCESSING','COMPLETED','FAILED') DEFAULT 'PENDING',
    `processing_time` FLOAT,
    `vector_db_used` BOOLEAN DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
);

-- Tests de estres
CREATE TABLE `stress_tests` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `test_id` VARCHAR(36) UNIQUE NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    `config` JSON NOT NULL,
    `status` ENUM('PENDING','PROCESSING','COMPLETED','FAILED') DEFAULT 'PENDING',
    `hardware_info` JSON,
    `metrics_snapshots` JSON,
    `summary` JSON,
    `duration_seconds` FLOAT,
    `started_at` TIMESTAMP NULL,
    `completed_at` TIMESTAMP NULL,
    `created_by` INT NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE CASCADE
);
```

---

# 9. SISTEMA RAG

## 9.1 Componentes

1. **Carga Documentos**: PyPDFLoader procesa PDFs
2. **Chunking**: RecursiveCharacterTextSplitter (1000 chars, 200 overlap)
3. **Embeddings**: OllamaEmbeddings (llama3)
4. **Vector Store**: ChromaDB (primario) / FAISS (fallback)
5. **Retrieval**: Top-k=3 documentos relevantes
6. **Chain**: RetrievalQA con prompts personalizados

## 9.2 Flujo RAG

```
Pregunta Usuario
       |
       v
[Analisis Pregunta] --> Determina tipo/complejidad
       |
       v
[Busqueda Vectorial] --> ChromaDB similarity_search(k=3)
       |
       v
[Contexto Recuperado] --> Fragmentos relevantes
       |
       v
[Construccion Prompt] --> Template + Contexto + Pregunta
       |
       v
[Generacion LLM] --> Ollama (llama3/phi4)
       |
       v
Respuesta
```

---

# 10. SISTEMA DE DIAGNOSTICOS

## 10.1 metrics_collector.py

```python
import psutil
import platform

class MetricsCollector:
    def get_hardware_info(self) -> Dict:
        return {
            "cpu_model": self._get_cpu_model(),
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "gpu_model": self._get_gpu_info().get("name", "No detectada"),
            "gpu_vram_gb": self._get_gpu_info().get("vram_total_gb", 0),
            "os": f"{platform.system()} {platform.release()}"
        }
    
    def collect_snapshot(self) -> Dict:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "ram_percent": psutil.virtual_memory().percent,
                "ram_used_mb": psutil.virtual_memory().used / (1024**2)
            },
            "gpu": self._get_gpu_metrics()
        }
```

## 10.2 stress_runner.py

```python
class StressTestRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.metrics_collector = MetricsCollector()
    
    async def run_test(self, config: Dict) -> Dict:
        concurrent_users = config.get("concurrent_users", 5)
        queries_per_user = config.get("queries_per_user", 5)
        duration_seconds = config.get("duration_seconds", 120)
        
        # Timeout por query = duracion maxima
        self.query_timeout_seconds = duration_seconds
        
        # Ejecutar queries concurrentes
        await self._run_concurrent(queries, concurrent_users, model, use_rag)
        
        # Calcular resumen
        return {
            "hardware_info": hardware_info,
            "snapshots": snapshots,
            "summary": self._calculate_summary(duration, snapshots)
        }
    
    async def _send_query(self, query: str, model: str) -> Dict:
        timeout = aiohttp.ClientTimeout(total=self.query_timeout_seconds)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "texto": query,
                "userId": "stress-test-user",
                "chatToken": "stress-test-session",
                "history": [],
                "modelo": model
            }
            
            async with session.post(f"{self.base_url}/preguntar", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        return {"success": True, "response": data}
                
                return {"success": False, "error": f"HTTP {response.status}"}
```

## 10.3 report_generator.py

Genera reportes en multiples formatos:
- **CSV**: Datos tabulares
- **TXT**: Legible por humanos
- **JSON**: Datos completos
- **XLSX**: Excel con tablas formateadas

---

# 11. DOCKER Y DESPLIEGUE

## 11.1 docker-compose.yml

```yaml
version: '3.8'

services:
  redis:
    image: redis:7.2-alpine
    container_name: chatbot_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 512mb
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

  backend:
    image: chatbot-educativo/backend:v2.1
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - DATABASE_URL=mysql+pymysql://root:${MYSQL_PASSWORD}@host.docker.internal:3306/bd_chatbot
      - OLLAMA_URL=http://host.docker.internal:11434
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - ./backend/data:/app/data
    depends_on:
      redis:
        condition: service_healthy

  worker:
    image: chatbot-educativo/worker:v2.1
    build:
      context: .
      dockerfile: backend/Dockerfile.worker
    environment:
      - REDIS_HOST=redis
      - DATABASE_URL=mysql+pymysql://root:${MYSQL_PASSWORD}@host.docker.internal:3306/bd_chatbot
      - OLLAMA_URL=http://host.docker.internal:11434
    depends_on:
      - redis
      - backend

  frontend:
    image: chatbot-educativo/frontend:v2.1
    build:
      context: .
      dockerfile: frontend/Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend

  flower:
    image: mher/flower
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  redis_data:

networks:
  default:
    name: chatbot_network
```

## 11.2 Backend Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ curl default-libmysqlclient-dev pkg-config build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-prod.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN mkdir -p data/cache data/chroma_db data/faiss_index data/pdfs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/check_connection || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 11.3 Nginx Config

```nginx
server {
    listen 80;
    server_name localhost;
    
    root /usr/share/nginx/html;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api/ {
        proxy_pass http://backend-service/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
        proxy_http_version 1.1;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    location /auth/ {
        proxy_pass http://backend-service/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /dashboard/ {
        proxy_pass http://backend-service/dashboard/;
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

## 11.4 Despliegue AWS ECR

```bash
# pushAWS/login.sh
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 913808666659.dkr.ecr.us-east-1.amazonaws.com

# pushAWS/build.sh
docker build -t chatbot-educativo/backend:v2.1 -f backend/Dockerfile .
docker build -t chatbot-educativo/frontend:v2.1 -f frontend/Dockerfile .

# pushAWS/push.sh
docker tag chatbot-educativo/backend:v2.1 913808666659.dkr.ecr.us-east-1.amazonaws.com/icfunab:backend-v2.1
docker push 913808666659.dkr.ecr.us-east-1.amazonaws.com/icfunab:backend-v2.1
```

---

# 12. VARIABLES DE ENTORNO

## 12.1 Backend (.env)

```env
# Base de Datos
DB_USER=root
DB_PASSWORD=tu_password
DB_HOST=host.docker.internal
DB_PORT=3306
DB_NAME=bd_chatbot
DATABASE_URL=mysql+pymysql://root:password@host:3306/bd_chatbot

# Ollama
OLLAMA_URL=http://host.docker.internal:11434

# Redis
REDIS_HOST=redis
REDIS_URL=redis://redis:6379/0

# Seguridad
SECRET_KEY=clave-secreta-muy-larga
TURNSTILE_SECRET_KEY=clave-cloudflare

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_TIMEZONE=America/Santiago

# Aplicacion
ENVIRONMENT=development
DEBUG=true
MAX_WORKERS=4
LOG_LEVEL=info
```

---

# 13. SEGURIDAD

## 13.1 Autenticacion

- **Hash passwords**: bcrypt con salt
- **Limite bcrypt**: 72 bytes (truncado automatico)
- **Cloudflare Turnstile**: Captcha invisible
- **Verificacion roles**: Server-side obligatorio

## 13.2 Validacion Email

Solo dominios institucionales:
- @unab.cl
- @uandresbello.edu

## 13.3 CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restringir en produccion
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 13.4 Roles

- `usuario`: Solo acceso al chat
- `admin`: Dashboard completo, gestion usuarios, diagnosticos

---

# ANEXOS

## A. Modelos IA Disponibles

| Modelo | Temperatura | Uso |
|--------|-------------|-----|
| llama3 | 0.3 | Rapido, general |
| phi4 | 0.2 | Razonamiento avanzado |

## B. Puertos del Sistema

| Servicio | Puerto |
|----------|--------|
| Frontend (Nginx) | 80 |
| Backend (FastAPI) | 8000 |
| Redis | 6379 |
| Flower | 5555 |
| MySQL | 3306 |
| Ollama | 11434 |

## C. Comandos Utiles

```bash
# Construir y levantar
docker-compose up -d --build

# Ver logs
docker-compose logs -f backend

# Reiniciar servicio
docker-compose restart backend

# Backup MySQL
mysqldump -u root -p bd_chatbot > backup.sql

# Limpiar ChromaDB
rm -rf backend/data/chroma_db/*
docker-compose restart backend
```

---

*Documentacion generada - Noviembre 2025*
*Chatbot Educativo UNAB v2.1*
