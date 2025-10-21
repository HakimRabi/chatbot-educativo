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

# Configuración de Base de Datos
# Lee desde variables de entorno con valores por defecto
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "rootchatbot")
# Usar host.docker.internal para acceder a MySQL desde contenedores Docker
# En entorno local (no Docker), usar 127.0.0.1
DB_HOST = os.getenv("DB_HOST", "host.docker.internal")  # Por defecto para Docker
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "bd_chatbot")

# Usar mysqldb (mysqlclient) en lugar de mysqlconnector
DATABASE_URL = f"mysql+mysqldb://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# Configuración de Ollama
# En Docker usar host.docker.internal, en local usar localhost
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")

# Configuración de archivos
# Cambiar estas líneas:
PDFS_DIR = os.path.join(os.path.dirname(__file__), "data", "pdfs")  
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")  
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "data", "chroma_db")  
FAISS_PATH = os.path.join(os.path.dirname(__file__), "data", "faiss_index") 

# Configuración del modelo
MODEL_NAME = "llama3"
MODEL_TEMPERATURE = 0.3
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Configuración de modelos disponibles
AVAILABLE_MODELS = {
    "llama3": {
        "name": "llama3",
        "display_name": "Llama3",
        "description": "Modelo general",
        "temperature": 0.3
    },
    "gpt-oss:20b": {
        "name": "gpt-oss:20b", 
        "display_name": "GPT-OSS 20B",
        "description": "Razonamiento",
        "temperature": 0.2
    }
}

# Modelo por defecto
DEFAULT_MODEL = "llama3"
