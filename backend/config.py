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
DB_USER = "root"
DB_PASSWORD = "rootchatbot"
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_NAME = "bd_chatbot"

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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
