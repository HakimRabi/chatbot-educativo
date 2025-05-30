from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.llms import Ollama
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.callbacks.manager import get_openai_callback
from langchain.memory import ConversationBufferMemory
import os
from fastapi import HTTPException
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, text, JSON, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import logging
import re
from glob import glob
from pymilvus import MilvusClient
from langchain_community.embeddings import OllamaEmbeddings
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("chatbot_app")

# Crear la aplicación FastAPI
app = FastAPI()

# Cargar variables de entorno
load_dotenv()

# --- Inicializar mysql ---
DB_USER = "root"
DB_PASSWORD = "rootchatbot"
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_NAME = "bd_chatbot"

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Crear engine y sesión
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Configurar bcrypt para el hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Definir el modelo de la tabla de usuarios
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    password = Column(String(100))
    created_at = Column(String(100))

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

# Crear las tablas si no existen
Base.metadata.create_all(bind=engine)

# Función para verificar conexión a la base de datos
def check_db_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(text('SELECT 1')).fetchone()
            return result is not None
    except Exception as e:
        print("Error de conexión a la base de datos:", e)
        return False

# --- Habilitar CORS para permitir peticiones desde el frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar la carpeta actual como archivos estáticos
app.mount("/static", StaticFiles(directory="."), name="static")

# Ruta raíz para servir index.html
@app.get("/")
def serve_index():
    return FileResponse("index.html")

# --- Endpoint para verificar conexión ---
@app.get("/check_connection")
async def check_connection():
    try:
        # Verificar conexión con la base de datos
        if check_db_connection():
            return {"connected": True}
        else:
            return {"connected": False}
    except Exception as e:
        return {"connected": False, "error": str(e)}

# --- Funciones para el procesamiento del lenguaje natural ---
def analyze_question_complexity(question):
    """Analiza la complejidad de la pregunta para determinar el tipo de respuesta necesaria."""
    # Preguntas específicas que requieren respuestas detalladas
    detailed_patterns = [
        # Patrones de explicación
        r"explica|explicar|detalla|detallar|describe|describir|expón|exponer|desarrolla|desarrollar",
        r"(¿cómo|como)(\s+se)?(\s+hace|\s+funciona|\s+realiza|\s+desarrolla|\s+implementa|\s+ejecuta|\s+lleva a cabo|\s+logra|\s+consigue)",
        r"cuál es la (diferencia|distinción|discrepancia|divergencia)|diferencias entre|distingue entre|contrasta",
        r"qué (significa|implica|conlleva|supone|involucra|representa|denota|comprende|abarca)",
        r"profundiza|ahonda|elabora|amplía|ampliar|extiende|extender|expande|expandir",
        r"analiza|analizar|análisis|examina|examinar|estudia|estudiar|investiga|investigar",
        r"comparación|comparar|compara|coteja|cotejar|contrasta|contrastar|equipara|equiparar",
        
        # Patrones de razonamiento
        r"por qué|razón|motivo|causa|justifica|justificar|fundamenta|fundamentar",
        r"argumenta|argumentar|razona|razonar|demuestra|demostrar|prueba|probar",
        r"(cuáles|cuales) son (las|los) (razones|motivos|causas|factores|elementos|componentes|aspectos)",
        
        # Patrones de proceso
        r"proceso de|procedimiento para|metodología de|método para|técnica de|pasos para",
        r"etapas de|fases de|ciclo de|secuencia de|orden de|progresión de",
        r"(¿cómo|como) (se desarrolla|se lleva a cabo|se realiza|se ejecuta|se implementa) el proceso",
        
        # Patrones de relación
        r"relación entre|conexión entre|vínculo entre|asociación entre|correlación entre",
        r"cómo se relaciona|cómo se conecta|cómo se vincula|cómo se asocia|cómo interactúa",
        r"impacto de|efecto de|influencia de|consecuencia de|resultado de",
        
        # Patrones de evaluación
        r"evalúa|evaluar|valora|valorar|juzga|juzgar|critica|criticar|aprecia|apreciar",
        r"ventajas y desventajas|pros y contras|beneficios y perjuicios|fortalezas y debilidades",
        r"(¿qué|que) tan (efectivo|eficaz|eficiente|útil|valioso|importante|relevante|significativo)",
        
        # Patrones de aplicación
        r"aplica|aplicar|implementa|implementar|utiliza|utilizar|usa|usar|emplea|emplear",
        r"(¿cómo|como) se (aplica|implementa|utiliza|usa|emplea) (en|para|cuando)",
        r"ejemplo (práctico|real|concreto|específico) de|caso (práctico|real|concreto|específico) de",
        
        # Patrones de síntesis
        r"sintetiza|sintetizar|resume|resumir|condensa|condensar|compendia|compendiar",
        r"(principales|esenciales|fundamentales|básicos|clave) (aspectos|elementos|componentes|características|rasgos)",
        r"(¿cuáles|cuales) son los (puntos|aspectos|elementos) (principales|esenciales|fundamentales|clave)",
        
        # Patrones de historia y evolución
        r"historia de|evolución de|desarrollo histórico de|origen de|génesis de",
        r"(¿cómo|como) ha (evolucionado|cambiado|progresado|avanzado|desarrollado) (a lo largo del tiempo|históricamente)",
        r"(¿cuáles|cuales) han sido los (hitos|momentos clave|avances significativos|desarrollos importantes)",
        
        # Patrones de teoría y conceptos
        r"teoría de|concepto de|principio de|fundamento de|postulado de|axioma de",
        r"(¿cuáles|cuales) son los (conceptos|principios|fundamentos|postulados|axiomas) (básicos|fundamentales|esenciales)",
        r"marco (teórico|conceptual|referencial) de|base (teórica|conceptual) de",
        
        # Patrones de problemas y soluciones
        r"problema de|dificultad de|obstáculo de|desafío de|reto de",
        r"solución para|resolución de|abordaje de|enfoque para|estrategia para",
        r"(¿cómo|como) (resolver|solucionar|abordar|enfrentar|superar) (el problema|la dificultad|el obstáculo|el desafío|el reto)",
        
        # Patrones de ética y filosofía
        r"implicaciones éticas de|consideraciones éticas sobre|dilemas éticos en|cuestiones éticas relacionadas",
        r"filosofía (detrás de|subyacente a|que fundamenta)|perspectiva filosófica sobre",
        r"(¿cuáles|cuales) son las (implicaciones|consideraciones|cuestiones|dimensiones) éticas",
        
        # Patrones de futuro y tendencias
        r"futuro de|porvenir de|prospectiva de|proyección de|tendencia de",
        r"(¿cómo|como) (evolucionará|cambiará|se desarrollará|progresará|avanzará) en el futuro",
        r"tendencias (emergentes|futuras|próximas|venideras|inminentes) en|dirección futura de"
    ]
    
    # Preguntas que normalmente requieren respuestas concisas
    concise_patterns = [
        # Preguntas básicas de información
        r"^(¿)?(cuándo|cuando|donde|dónde|quién|quien|qué|que|cuál|cual)(\s+es|\s+son|\s+será|\s+fue|\s+fueron|\s+ha sido|\s+han sido)?\??$",
        r"^(¿)?(cuándo|cuando) (ocurrió|sucedió|pasó|tuvo lugar|se realizó|se llevó a cabo|comenzó|terminó)?\??$",
        r"^(¿)?(dónde|donde) (está|se encuentra|se ubica|se localiza|se sitúa|reside|yace)?\??$",
        r"^(¿)?(quién|quien) (inventó|creó|desarrolló|descubrió|fundó|estableció|inició)?\??$",
        
        # Patrones de enumeración
        r"menciona|lista|enumera|nombra|cita|indica|señala|especifica",
        r"(¿cuáles|cuales) son (los|las) (tipos|clases|categorías|variedades|modalidades|formas|ejemplos)",
        r"(dame|proporciona|facilita|provee) (una lista|un listado|una enumeración|un catálogo) de",
        
        # Patrones de cantidad y medida
        r"(¿)?(cuánto|cuanto|cuánta|cuanta|cuántos|cuantos|cuántas|cuantas)(\s+tiempo|\s+dinero|\s+cuesta|\s+vale|\s+mide|\s+pesa|\s+dura)?\??$",
        r"(¿)?(cuál|cual) es (el precio|el costo|el valor|la cantidad|el número|el monto|la cifra|la medida)?\??$",
        r"(¿)?(cuánto|cuanto) (cuesta|vale|tarda|demora|dura|se tarda|se demora|se requiere)?\??$",
        
        # Patrones de existencia
        r"(¿)?hay\s+|existe\s+|se encuentra\s+|está disponible\s+|se dispone de\s+",
        r"(¿)?(existe|hay) (algún|alguna|algunos|algunas|un|una)?\??$",
        r"(¿)?(es posible|se puede|se podría|cabría la posibilidad de)?\??$",
        
        # Patrones de verificación
        r"(¿)?(es|son|está|están|fue|fueron|será|serán) (cierto|verdad|correcto|exacto|preciso|válido)?\??$",
        r"(¿)?(es|son|está|están|fue|fueron|será|serán) (falso|mentira|incorrecto|inexacto|impreciso|inválido)?\??$",
        r"(¿)?(se considera|se clasifica como|se categoriza como|se define como)?\??$",
        
        # Patrones de frecuencia
        r"(¿)?(con qué frecuencia|cada cuánto|cada cuanto|qué tan seguido|que tan seguido)?\??$",
        r"(¿)?(cuántas veces|cuantas veces|qué tan frecuente|que tan frecuente)?\??$",
        r"(¿)?(es común|es frecuente|es habitual|es usual|es normal)?\??$",
        
        # Patrones de posibilidad
        r"(¿)?(es posible|se puede|se podría|cabe la posibilidad|existe la posibilidad)?\??$",
        r"(¿)?(qué probabilidad|que probabilidad|qué posibilidad|que posibilidad|qué tan probable|que tan probable)?\??$",
        r"(¿)?(podría|puede|cabría|sería factible|sería viable)?\??$",
        
        # Patrones de preferencia
        r"(¿)?(cuál|cual) es (mejor|peor|más recomendable|más adecuado|más apropiado|más conveniente)?\??$",
        r"(¿)?(qué|que) (prefieres|recomiendas|sugieres|aconsejas|propones)?\??$",
        r"(¿)?(es recomendable|es aconsejable|es preferible|es mejor|es conveniente)?\??$",
        
        # Patrones de definición breve
        r"^(¿)?(qué|que) (es|son) (un|una|el|la|los|las)?\??$",
        r"^(¿)?(qué|que) (significa|quiere decir|denota|representa)?\??$",
        r"^(¿)?(cuál|cual) es (el significado|la definición|el concepto) de?\??$",
        
        # Patrones de sí/no
        r"^(¿)?(se|es|está|son|están|puede|pueden|ha|han|había|habían)?\??$"
    ]
    
    # Contar palabras en la pregunta (más palabras suele indicar mayor complejidad)
    word_count = len(question.split())
    
    # Verificar patrones detallados
    for pattern in detailed_patterns:
        if re.search(pattern, question.lower()):
            return "detailed"
    
    # Verificar patrones concisos
    for pattern in concise_patterns:
        if re.search(pattern, question.lower()):
            return "concise"
    
    # Basado en la longitud de la pregunta
    if word_count <= 10:
        return "concise"
    else:
        return "mixed"

def extract_keywords(text):
    """Extrae palabras clave relevantes del texto de la pregunta."""
    # Lista ampliada de palabras vacías en español
    stopwords = [
        # Artículos
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        
        # Preposiciones
        "a", "ante", "bajo", "cabe", "con", "contra", "de", "desde", "durante", 
        "en", "entre", "hacia", "hasta", "mediante", "para", "por", "según", 
        "sin", "so", "sobre", "tras", "versus", "vía",
        
        # Conjunciones
        "y", "e", "ni", "o", "u", "bien", "sea", "ya", "pero", "mas", "aunque", 
        "sino", "siquiera", "que", "si", "como", "cuando", "mientras", "donde", 
        "porque", "pues", "luego", "conque", "así", "ergo",
        
        # Pronombres
        "yo", "me", "mí", "conmigo", "tú", "te", "ti", "contigo", "él", "ella", 
        "lo", "le", "se", "sí", "consigo", "nosotros", "nosotras", "nos", 
        "vosotros", "vosotras", "os", "ellos", "ellas", "los", "las", "les", 
        "se", "sí", "consigo", "mío", "mía", "míos", "mías", "tuyo", "tuya", 
        "tuyos", "tuyas", "suyo", "suya", "suyos", "suyas", "nuestro", "nuestra", 
        "nuestros", "nuestras", "vuestro", "vuestra", "vuestros", "vuestras", 
        "suyo", "suya", "suyos", "suyas", "este", "esta", "estos", "estas", 
        "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas", 
        "quien", "quienes", "cual", "cuales", "cuanto", "cuanta", "cuantos", 
        "cuantas", "alguien", "nadie", "algo", "nada", "uno", "alguno", "ninguno", 
        "poco", "mucho", "bastante", "demasiado", "todo", "otro", "mismo", "tan", 
        "tanto", "algún", "ningún",
        
        # Adverbios comunes
        "no", "sí", "también", "tampoco", "siempre", "nunca", "jamás", "aquí", 
        "ahí", "allí", "acá", "allá", "cerca", "lejos", "arriba", "abajo", 
        "delante", "detrás", "encima", "debajo", "antes", "después", "pronto", 
        "tarde", "temprano", "todavía", "aún", "ya", "ayer", "hoy", "mañana", 
        "ahora", "luego", "antes", "después", "bien", "mal", "regular", "despacio", 
        "deprisa", "así", "tal", "como", "muy", "poco", "mucho", "bastante", 
        "demasiado", "más", "menos", "tan", "tanto", "casi", "medio", "apenas", 
        "justo", "aproximadamente", "exactamente", "solamente", "únicamente",
        
        # Verbos auxiliares y comunes
        "es", "son", "está", "están", "fue", "fueron", "será", "serán", "ha", 
        "han", "había", "habían", "habrá", "habrán", "puede", "pueden", "podía", 
        "podían", "podrá", "podrán", "debe", "deben", "debía", "debían", "deberá", 
        "deberán", "tiene", "tienen", "tenía", "tenían", "tendrá", "tendrán", 
        "hacer", "hace", "hacen", "hizo", "hicieron", "hará", "harán", "ir", 
        "va", "van", "fue", "fueron", "irá", "irán", "dar", "da", "dan", "dio", 
        "dieron", "dará", "darán", "ver", "ve", "ven", "vio", "vieron", "verá", 
        "verán", "decir", "dice", "dicen", "dijo", "dijeron", "dirá", "dirán",
        
        # Palabras interrogativas (cuando no son el foco de la pregunta)
        "qué", "quién", "quiénes", "cuál", "cuáles", "cómo", "dónde", "cuándo", 
        "cuánto", "cuánta", "cuántos", "cuántas", "por qué", "para qué"
    ]
    
    # Limpiar y normalizar el texto
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # Eliminar puntuación
    text = re.sub(r'\d+', '', text)       # Eliminar números
    
    # Dividir en palabras y filtrar palabras vacías
    words = text.split()
    
    # Filtrar palabras vacías y palabras muy cortas (excepto siglas comunes de IA)
    keywords = []
    for word in words:
        if word not in stopwords and (len(word) > 2 or word.upper() in ["IA", "ML", "DL", "NLP", "CV"]):
            keywords.append(word)
    
    # Detectar y mantener términos compuestos comunes en IA
    compound_terms = [
        "inteligencia artificial", "aprendizaje automático", "aprendizaje profundo", 
        "redes neuronales", "procesamiento lenguaje natural", "visión computacional", 
        "sistemas expertos", "lógica difusa", "algoritmos genéticos", "minería datos", 
        "big data", "internet cosas", "reconocimiento patrones", "machine learning", 
        "deep learning", "neural networks", "natural language processing", "computer vision", 
        "expert systems", "fuzzy logic", "genetic algorithms", "data mining", 
        "internet of things", "pattern recognition", "agentes inteligentes", "intelligent agents", 
        "búsqueda heurística", "heuristic search", "razonamiento probabilístico", 
        "probabilistic reasoning", "representación conocimiento", "knowledge representation", 
        "planificación automática", "automated planning", "robótica inteligente", 
        "intelligent robotics", "sistemas multiagente", "multiagent systems", 
        "computación evolutiva", "evolutionary computation", "computación cognitiva", 
        "cognitive computing", "ética ia", "ai ethics", "explicabilidad ia", "ai explainability"
    ]
    
    original_text = text.lower()
    for term in compound_terms:
        if term in original_text:
            # Añadir el término compuesto como una sola palabra clave
            term_without_spaces = term.replace(" ", "_")
            if term_without_spaces not in keywords:
                keywords.append(term_without_spaces)
    
    # Aplicar stemming básico para palabras en español (simplificado)
    stemmed_keywords = []
    for word in keywords:
        # Reglas básicas de stemming para español
        if word.endswith("mente"):
            word = word[:-5]  # Quitar sufijo "mente"
        elif word.endswith("ción") or word.endswith("cion"):
            word = word[:-4] + "r"  # Convertir "ción/cion" a raíz verbal
        elif word.endswith("ando") or word.endswith("endo"):
            word = word[:-4]  # Quitar gerundios
        elif word.endswith("ado") or word.endswith("ido"):
            word = word[:-3]  # Quitar participios
        elif len(word) > 4 and word.endswith("s") and not word.endswith("es"):
            word = word[:-1]  # Quitar plural simple
        
        if word not in stemmed_keywords and len(word) > 2:
            stemmed_keywords.append(word)
    
    # Eliminar duplicados y ordenar por longitud (priorizando palabras más largas que suelen ser más específicas)
    unique_keywords = list(set(stemmed_keywords))
    unique_keywords.sort(key=len, reverse=True)
    
    # Limitar a un máximo de 10 palabras clave más relevantes
    return unique_keywords[:10] if len(unique_keywords) > 10 else unique_keywords

# --- Cargar TODOS los PDF de la carpeta y preparar el modelo ---
# Inicializar variables globales para evitar errores de referencia
fragmentos = []
documentos = []
using_vector_db = False
cadena = None
llm = None
memory = None

try:
    # Cargar PDFs
    pdfs_dir = os.path.join(os.path.dirname(__file__), "pdfs")
    pdf_files = glob(os.path.join(pdfs_dir, "*.pdf"))
    logger.info(f"Encontrados {len(pdf_files)} archivos PDF")
    
    if not pdf_files:
        logger.warning("No se encontraron archivos PDF en la carpeta pdfs")
        raise Exception("No hay archivos PDF disponibles")
    
    documentos = []
    for pdf_path in pdf_files:
        try:
            loader = PyPDFLoader(pdf_path)
            documentos.extend(loader.load())
            logger.info(f"Cargado PDF: {pdf_path}")
        except Exception as pdf_error:
            logger.error(f"Error al cargar {pdf_path}: {pdf_error}")
    
    if not documentos:
        logger.warning("No se pudieron cargar documentos de los PDFs")
        raise Exception("No se pudieron extraer documentos de los PDFs")
    
    # Dividir documentos en fragmentos
    splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=150)
    fragmentos = splitter.split_documents(documentos)
    logger.info(f"Documentos divididos en {len(fragmentos)} fragmentos")
    
    # Inicializar embeddings
    embeddings = OllamaEmbeddings(model="llama3")
    
    # Configurar FAISS
    faiss_path = os.path.join(os.path.dirname(__file__), "faiss_index")
    os.makedirs(faiss_path, exist_ok=True)  # Asegurar que el directorio existe
    
    # Crear la base de datos vectorial con FAISS
    logger.info(f"Inicializando FAISS en {faiss_path}")
    vector_store = FAISS.from_documents(documents=fragmentos, embedding=embeddings)
    
    # Guardar el índice en disco
    vector_store.save_local(faiss_path)
    logger.info(f"Índice FAISS guardado en {faiss_path}")
    
    # Inicializar el modelo LLM
    llm = Ollama(model="llama3", temperature=0.3)
    
    # Crear cadena de recuperación
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    cadena = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )
    
    # Crear memoria para conversación
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    # Marcar que estamos usando base de datos vectorial
    using_vector_db = True
    logger.info("FAISS inicializado correctamente")

except Exception as e:
    logger.error(f"Error al configurar FAISS: {e}")
    logger.info("Iniciando fallback a procesamiento en memoria...")
    
    # Asegurar que las variables estén inicializadas
    if not 'fragmentos' in locals() or not fragmentos:
        fragmentos = []
    if not 'documentos' in locals() or not documentos:
        documentos = []
    
    # Intentar cargar PDFs nuevamente si no se cargaron antes
    if not documentos:
        try:
            pdfs_dir = os.path.join(os.path.dirname(__file__), "pdfs")
            pdf_files = glob(os.path.join(pdfs_dir, "*.pdf"))
            
            for pdf_path in pdf_files:
                try:
                    loader = PyPDFLoader(pdf_path)
                    documentos.extend(loader.load())
                except Exception as pdf_error:
                    logger.error(f"Fallback: Error al cargar {pdf_path}: {pdf_error}")
            
            # Dividir documentos si hay alguno
            if documentos:
                splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
                fragmentos = splitter.split_documents(documentos)
                logger.info(f"Fallback: Documentos divididos en {len(fragmentos)} fragmentos")
        except Exception as fallback_error:
            logger.error(f"Error en fallback de carga de PDFs: {fallback_error}")
    
    # Configurar LLM y cadena de QA básica
    try:
        llm = Ollama(model="llama3", temperature=0.3)
        # Usar load_qa_chain como fallback (ignorar advertencia de deprecación)
        cadena = load_qa_chain(llm, chain_type="stuff")
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        using_vector_db = False  # Marcar que NO estamos usando base de datos vectorial
        logger.info("Fallback configurado correctamente")
    except Exception as llm_error:
        logger.error(f"Error crítico al configurar fallback: {llm_error}")
        cadena = None
        memory = None
# --- Contexto y plantillas de prompt ---
# Contexto base que se usará en todas las interacciones
contexto_base = (
    "Eres un asistente virtual especializado en el área de Fundamentos de Inteligencia Artificial, orientado a estudiantes universitarios. "
    "Tu función principal es apoyar el aprendizaje, responder preguntas, aclarar conceptos y proporcionar información relevante sobre temas relacionados con la inteligencia artificial, "
    "incluyendo historia, aplicaciones, algoritmos, ética, fundamentos matemáticos, aprendizaje automático, lógica, razonamiento, agentes inteligentes, y más. "
    "Puedes utilizar información de materiales de clase, syllabus, libros, artículos, manuales y cualquier recurso académico proporcionado. "
    "Adapta tus respuestas al nivel universitario, siendo claro, didáctico y preciso. "
    "Siempre responde en español y fomenta la curiosidad y el pensamiento crítico en los estudiantes. "
    "Si una pregunta está fuera del ámbito de la inteligencia artificial o no tienes suficiente información, indícalo amablemente y sugiere recursos o enfoques para investigar más. "
    
    "Cuando respondas preguntas, sigue estas pautas adicionales: "
    "- Mantén un tono natural, cálido y empático, especialmente en conversaciones casuales. "
    "- Responde en oraciones o párrafos completos, evitando respuestas demasiado cortas. "
    "- Cuando uses viñetas para resumir información, asegúrate de que cada punto tenga al menos 1-2 oraciones completas. "
    "- Si el estudiante proporciona contenido extenso como artículos científicos, responde en prosa y párrafos estructurados. "
    "- Cuando respondas sobre temas factuales, separa claramente los hechos conocidos de las especulaciones, y formula las suposiciones como tales. "
    "- Si el mensaje del estudiante parece asumir una afirmación falsa, no la aceptes completamente ni completes la tarea basada en esa premisa incorrecta. "
    "- Sé honesto y transparente cuando no puedas o no estés dispuesto a ayudar con parte o toda la solicitud. "
    "- Adapta el formato de tus respuestas al tema de la conversación, usando un estilo más formal para temas académicos. "
    "- Cuando el estudiante solicite respuestas estructuradas, puedes ofrecer esquemas, razonamiento paso a paso o formatos específicos. "
    "- Intenta proporcionar ejemplos concretos siempre que sea posible para facilitar la comprensión. "
    "- Si el estudiante califica negativamente tu respuesta o señala un error, agradece la retroalimentación y corrige la información. "
    "- Evita proporcionar información que pueda usarse con fines maliciosos o dañinos. "
    "- Puedes mostrar un poco de humor en conversaciones casuales cuando sea apropiado. "
    "- Cuando no puedas ayudar con algo, ofrece alternativas útiles si es posible, manteniendo tu respuesta breve y sin sonar sermoneador. "
    "- Responde a metáforas y solicitudes creativas usando ejemplos, pequeños experimentos o metáforas relacionadas con la IA. "
    "- En conversaciones largas, haz preguntas cuando creas que pueden ayudar a aclarar dudas, pero evita abrumar al estudiante. "
)


# Coloca esto después de definir 'contexto_base' y antes de la inicialización del modelo/FAISS

# Plantilla base para RetrievalQA (cuando FAISS está activo)
# Esta plantilla guía al LLM sobre cómo usar el contexto_base, los documentos recuperados,
# el historial de chat y la pregunta del usuario.
plantilla_qa_con_documentos_str = (
    contexto_base + "\n\n"  # Tu contexto general del bot
    "Instrucciones Adicionales: Eres un asistente especializado. "
    "Utiliza la siguiente información recuperada de documentos relevantes y el historial de conversación para responder la pregunta del usuario de manera precisa y útil. "
    "Si la información necesaria no se encuentra en los documentos recuperados, indícalo claramente. "
    "Adapta tu respuesta al nivel universitario, siendo claro y didáctico.\n\n"
    "Información recuperada de documentos (Contexto FAISS):\n{context}\n\n"
    "Historial de conversación previa:\n{chat_history}\n\n"
    "Pregunta del usuario: {question}\n\n"
    "Respuesta detallada y útil en español:"
)
PROMPT_QA_FAISS = PromptTemplate(
    template=plantilla_qa_con_documentos_str,
    input_variables=["context", "chat_history", "question"] # 'context' es donde RetrievalQA pone los docs
)

# Plantilla base para load_qa_chain (Fallback, si FAISS falla)
# Similar a la anterior, pero para el caso de fallback.
plantilla_fallback_str = (
    contexto_base + "\n\n"
    "Instrucciones Adicionales: Eres un asistente especializado (operando en modo fallback). "
    "Utiliza la siguiente información de documentos (si se proporcionan) y el historial de conversación para responder la pregunta del usuario. "
    "Si la información es limitada, haz tu mejor esfuerzo para ser útil o indica que no tienes suficiente información específica de los documentos.\n\n"
    "Información de documentos (Contexto directo de fragmentos):\n{context}\n\n" # 'context' es donde load_qa_chain pone los docs
    "Historial de conversación previa:\n{chat_history}\n\n"
    "Pregunta del usuario: {question}\n\n"
    "Respuesta útil en español:"
)
PROMPT_FALLBACK = PromptTemplate(
    template=plantilla_fallback_str,
    input_variables=["context", "chat_history", "question"]
)










plantilla_especifica = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: Busca información EXACTA en el syllabus o documentos proporcionados. "
        "SOLO responde con información que esté explícitamente en los documentos. "
        "Si la información específica no está en los documentos, indícalo claramente. "
        "Cita textualmente la parte relevante del documento y especifica la sección o página. "
        "NO elabores ni añadas información que no esté en los documentos.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta específica: {pregunta}\n\n"
        "Respuesta basada ÚNICAMENTE en documentos:"
    )
)

# Plantilla para respuestas detalladas
plantilla_detallada = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: Proporciona una explicación completa y detallada. Organiza tu respuesta en párrafos estructurados. "
        "Incluye ejemplos si son relevantes. Asegúrate de cubrir todos los aspectos importantes relacionados con la pregunta.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta: {pregunta}\n\n"
        "Respuesta detallada:"
    )
)

# Plantilla para respuestas concisas
plantilla_concisa = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: Proporciona una respuesta corta, directa y precisa. Usa máximo 2-3 oraciones. "
        "Ve directo al punto sin rodeos ni información adicional. Sé claro y específico.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta: {pregunta}\n\n"
        "Respuesta concisa:"
    )
)

# Plantilla para respuestas mixtas (equilibrio entre concisión y detalle)
plantilla_mixta = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: Proporciona una respuesta equilibrada. Comienza con la información esencial "
        "de forma directa y añade solo los detalles relevantes. Organiza la información de manera clara y concisa.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta: {pregunta}\n\n"
        "Respuesta:"
    )
)

# Plantilla para respuestas de seguimiento (aclaraciones o ejemplos adicionales)
plantilla_seguimiento = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: El usuario ha solicitado una aclaración, ejemplo adicional o desea profundizar en la respuesta anterior. "
        "Responde ampliando la información, proporcionando ejemplos concretos, analogías o explicaciones adicionales según corresponda. "
        "Mantén un tono didáctico y asegúrate de que la explicación sea fácil de entender.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta de seguimiento: {pregunta}\n\n"
        "Respuesta de seguimiento:"
    )
)


# Plantilla para aclaraciones
plantilla_aclaracion = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: El usuario ha solicitado que expliques la respuesta anterior de otra manera o con mayor claridad. "
        "Reformula la explicación usando diferentes palabras, analogías o simplificaciones.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta de aclaración: {pregunta}\n\n"
        "Respuesta aclaratoria:"
    )
)

# Plantilla para ejemplos
plantilla_ejemplo = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: El usuario ha solicitado ejemplos concretos relacionados con la pregunta. "
        "Proporciona uno o más ejemplos claros y relevantes.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta de ejemplo: {pregunta}\n\n"
        "Ejemplo(s):"
    )
)

# Plantilla para resumen
plantilla_resumen = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: El usuario ha solicitado un resumen. "
        "Resume la información clave de manera breve y clara.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta de resumen: {pregunta}\n\n"
        "Resumen:"
    )
)

# Plantilla para comparación
plantilla_comparacion = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: El usuario ha solicitado una comparación entre conceptos. "
        "Presenta las similitudes y diferencias de manera clara y estructurada.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta de comparación: {pregunta}\n\n"
        "Comparación:"
    )
)

# Plantilla para definición
plantilla_definicion = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: El usuario ha solicitado la definición de un término. "
        "Proporciona una definición clara, precisa y adecuada al nivel universitario.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta de definición: {pregunta}\n\n"
        "Definición:"
    )
)

# Plantilla para fuera de contexto
plantilla_fuera_contexto = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: La pregunta del usuario no está relacionada con inteligencia artificial o el ámbito académico. "
        "Indícalo amablemente y sugiere recursos o temas relacionados con IA.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta fuera de contexto: {pregunta}\n\n"
        "Respuesta:"
    )
)

# Plantilla para error o sin información
plantilla_sin_info = PromptTemplate(
    input_variables=["contexto", "conversacion", "pregunta"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: No se encontró información relevante para responder la pregunta. "
        "Indícalo de manera amable y sugiere cómo el usuario podría investigar más.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Pregunta: {pregunta}\n\n"
        "Respuesta:"
    )
)

# Plantilla para saludo/inicio
plantilla_saludo = PromptTemplate(
    input_variables=["contexto"],
    template=(
        "{contexto}\n\n"
        "¡Hola! Soy tu asistente virtual de Fundamentos de Inteligencia Artificial. ¿En qué puedo ayudarte hoy?"
    )
)

# Plantilla para despedida
plantilla_despedida = PromptTemplate(
    input_variables=["contexto"],
    template=(
        "{contexto}\n\n"
        "¡Ha sido un gusto ayudarte! Si tienes más preguntas sobre inteligencia artificial, no dudes en volver."
    )
)


# --- Modelos de solicitud ---
class Pregunta(BaseModel):
    texto: str
    userId: str = None
    chatToken: str = None
    history: list = None  # [{sender, text, timestamp}]

class SessionIn(BaseModel):
    user_id: str
    session_id: str
    history: list  # lista de mensajes [{sender, text, timestamp}]

class FeedbackIn(BaseModel):
    user_id: str
    session_id: str
    pregunta: str
    respuesta: str
    rating: int
    comentario: str = None  # Campo opcional para comentarios

# --- Endpoint principal mejorado ---
@app.post("/preguntar")
def preguntar(pregunta: Pregunta):
    # Construir conversación previa formateada
    conversacion = ""
    if pregunta.history and isinstance(pregunta.history, list):
        # Limitar el historial a las últimas 5 interacciones para mantener el contexto relevante
        history_limit = min(10, len(pregunta.history))
        recent_history = pregunta.history[-history_limit:]
        
        for msg in recent_history:
            if msg.get('sender') == 'user':
                conversacion += f"Usuario: {msg.get('text','')}\n"
            elif msg.get('sender') == 'bot':
                conversacion += f"Bot: {msg.get('text','')}\n"
    
    # Analizar la complejidad de la pregunta
    tipo_respuesta = analyze_question_complexity(pregunta.texto)
    
    # Obtener palabras clave de la pregunta
    keywords = extract_keywords(pregunta.texto)
    logger.info(f"Palabras clave extraídas: {keywords}")
    
    # Detectar la intención o tipo específico de pregunta
    # Patrones para diferentes tipos de preguntas
    patrones_tipo_pregunta = {
        "saludo": [r"^(hola|buenos días|buenas tardes|buenas noches|saludos|hey|qué tal|cómo estás|cómo va|buen día|hi|hello)"],
        
        "despedida": [r"^(adiós|chao|hasta luego|nos vemos|gracias por tu ayuda|gracias|hasta pronto|me voy|bye|hasta mañana|que tengas buen día|hasta la próxima)$"],
        
        "definicion": [r"(qué|que) (es|son|significa|significan) (un|una|el|la|los|las)?", 
                      r"define|definir|definición|significado de", 
                      r"concepto de", 
                      r"explica (el|la) (concepto|término|idea) de", 
                      r"(me puedes|podrías) (decir|explicar) (qué|que) (es|son)"],
        
        "ejemplo": [r"(dame|da|muestra|pon|proporciona) (un|unos|algunos)? ejemplos?", 
                   r"ejemplos? de", 
                   r"(ilustra|ilustración) con (un|unos) ejemplos?", 
                   r"caso práctico de", 
                   r"(cómo|como) se (aplica|implementa|usa) en la práctica", 
                   r"(me puedes|podrías) dar (un|unos) ejemplos?"],
        
        "comparacion": [r"(compara|comparación|diferencias?|similitudes?) (entre|de)", 
                       r"(qué|que|cuál|cual) es (mejor|peor|más efectivo|más eficiente)", 
                       r"(ventajas|desventajas) (de|entre)", 
                       r"(contrasta|contraste) (entre|de)", 
                       r"(en qué|que) se (diferencia|diferencian|distingue|distinguen)", 
                       r"(qué|que) tienen en común"],
        
        "resumen": [r"(resume|resumen|síntesis|sintetiza)", 
                   r"(en pocas palabras|brevemente|concisamente)", 
                   r"(puedes|podrías) (resumir|sintetizar)", 
                   r"(dime|explica) lo más importante de", 
                   r"(puntos|aspectos) (principales|clave|fundamentales) de", 
                   r"(resumen|síntesis) (breve|conciso|corto) de"],
        
        "aclaracion": [r"(puedes|podrías) (explicar|aclarar|clarificar) (mejor|de nuevo|otra vez|de otra manera)", 
                      r"no (entiendo|comprendo|me queda claro)", 
                      r"(me puedes|podrías) (explicar|aclarar) (con otras palabras|de forma más sencilla)", 
                      r"(no me quedó|no quedó) claro", 
                      r"(puedes|podrías) (simplificar|simplificarlo)", 
                      r"(estoy confundido|tengo dudas) (sobre|acerca de)"],
        
        "seguimiento": [r"(y|pero) (qué|que|cómo|como) (sobre|acerca de)", 
                       r"(puedes|podrías) (ampliar|expandir|profundizar)", 
                       r"(háblame|cuéntame) más (sobre|acerca de)", 
                       r"(quiero|me gustaría) saber más (sobre|acerca de)", 
                       r"(puedes|podrías) (elaborar|desarrollar) más (sobre|acerca de)", 
                       r"(y|pero) (respecto a|en cuanto a)"],
        
        "fuera_contexto": [r"(clima|tiempo|deportes|política|receta|cocina|salud personal|finanzas personales)"],
        
        "aplicacion": [r"(cómo|como) (se aplica|se implementa|se utiliza)", 
                      r"(aplicaciones|usos) (de|para)", 
                      r"(dónde|donde) se (usa|utiliza|aplica)", 
                      r"(para qué|para que) (sirve|se usa)", 
                      r"(beneficios|ventajas) de (usar|utilizar|implementar)", 
                      r"(casos|escenarios) de uso"],
        
        "historia": [r"(historia|origen|evolución) (de|del|de la)", 
                    r"(cuándo|cuando) (surgió|comenzó|se creó|se desarrolló)", 
                    r"(quién|quien) (inventó|creó|desarrolló)", 
                    r"(cómo|como) (ha evolucionado|ha cambiado|se ha desarrollado)", 
                    r"(línea de tiempo|cronología) (de|del|de la)"],
        
        "proceso": [r"(cómo|como) (funciona|opera|trabaja)", 
                   r"(pasos|etapas|fases) (para|de|del|de la)", 
                   r"(proceso|procedimiento|metodología) (de|para)", 
                   r"(explica|describe) (el proceso|los pasos|la metodología) (de|para)", 
                   r"(cómo|como) (implementar|desarrollar|crear)"],
        
        "problema": [r"(cómo|como) (resolver|solucionar|abordar)", 
                    r"(problema|dificultad|desafío) (con|de|en)", 
                    r"(error|fallo|bug) (en|con|de)", 
                    r"(no (funciona|sirve|trabaja))", 
                    r"(tengo problemas|tengo dificultades) (con|para)"],
        
        "opinion": [r"(qué|que) (opinas|piensas|crees) (sobre|acerca de)", 
                   r"(cuál|cual) es tu (opinión|punto de vista) (sobre|acerca de)", 
                   r"(estás|estas) de acuerdo (con|en que)", 
                   r"(crees|piensas) que (es|sea|sería) (mejor|peor|adecuado)", 
                   r"(recomendarías|recomiendas)"],
        
        "etica": [r"(ética|etica|moral|implicaciones éticas) (de|en|sobre)", 
                 r"(problemas|cuestiones|dilemas) (éticos|eticos|morales) (de|en|sobre)", 
                 r"(consecuencias|impacto) (social|ético|etico) (de|del|de la)", 
                 r"(responsabilidad|responsabilidades) (ética|etica|moral) (en|de)", 
                 r"(está bien|es correcto|es ético|es etico) (usar|utilizar|implementar)"],
        
        "futuro": [r"(futuro|porvenir) (de|del|de la)", 
                  r"(cómo|como) (evolucionará|cambiará|se desarrollará) (en el futuro)", 
                  r"(tendencias|direcciones) (futuras|emergentes) (en|de)", 
                  r"(qué|que) (podemos esperar|veremos) (en el futuro|próximamente)", 
                  r"(predicciones|pronósticos) (sobre|acerca de)"],
        
        "matematicas": [r"(fórmula|formula|ecuación|ecuacion) (de|para)", 
                       r"(cómo|como) (calcular|computar|resolver)", 
                       r"(demostración|demostracion|prueba) (de|del|de la)", 
                       r"(teorema|lema|corolario) (de|sobre)", 
                       r"(matemáticas|matematicas|cálculo|calculo|álgebra|algebra) (de|en|para)"],
        
        "algoritmo": [r"(algoritmo|método|metodo) (de|para)", 
                     r"(cómo|como) (implementar|programar) (el algoritmo|la técnica)", 
                     r"(complejidad|eficiencia) (del algoritmo|de la técnica)", 
                     r"(pseudocódigo|pseudocodigo|código|codigo) (de|para|del)", 
                     r"(optimización|optimizacion) (de|del) (algoritmo|método|metodo)"],
        
        "evaluacion": [r"(cómo|como) (evaluar|medir|valorar)", 
                      r"(métricas|metricas|indicadores) (de|para)", 
                      r"(evaluación|evaluacion|medición|medicion) (de|del|de la)", 
                      r"(criterios|parámetros|parametros) (para|de) (evaluar|medir)", 
                      r"(qué|que) tan (bueno|efectivo|eficiente) es"],
        
        "herramientas": [r"(herramientas|instrumentos|software) (para|de)", 
                        r"(qué|que) (herramientas|software|programas) (usar|utilizar|se recomiendan)", 
                        r"(cómo|como) (usar|utilizar) (la herramienta|el software)", 
                        r"(alternativas|opciones) (a|de|para)", 
                        r"(mejor|mejores) (herramienta|herramientas|software) (para|de)"],
        
        "implementacion": [r"(cómo|como) (implementar|programar|codificar)", 
                          r"(implementación|implementacion|desarrollo) (de|del|de la)", 
                          r"(código|codigo|programa) (para|de)", 
                          r"(lenguaje|framework|biblioteca) (para|de)", 
                          r"(arquitectura|diseño|diseno) (de|del|de la) (sistema|aplicación|aplicacion|programa)"],
                          
        "syllabus": [r"(syllabus|programa|temario|contenido|plan) (del|de la|de|del) (curso|materia|asignatura|clase)", 
                   r"(coordinador|profesor|docente|instructor) (del|de la|de|del) (curso|materia|asignatura|clase)",
                   r"(quién|quien) (es el|es la|es) (coordinador|profesor|docente|instructor)",
                   r"(cómo|como) (se|me) (evalúa|califica|puntúa) (en el|en la|en este|en) (curso|materia|asignatura|clase)",
                   r"(cuáles|cuales) son (los|las) (temas|contenidos|unidades|módulos) (del|de la|de|del) (curso|materia|asignatura|clase)",
                   r"(fecha|día|hora|horario|calendario) (de|del|de la|para) (entrega|examen|evaluación|clase|curso)",
                   r"(bibliografía|lecturas|textos|libros) (recomendados|obligatorios|del curso|de la materia)",
                   r"(política|reglas|normas) (de|para) (asistencia|participación|entregas|evaluación)"],
    }
    
    tipo_pregunta = None
    for tipo, patrones in patrones_tipo_pregunta.items():
        for patron in patrones:
            if re.search(patron, pregunta.texto.lower()):
                tipo_pregunta = tipo
                break
        if tipo_pregunta:
            break
    
    logger.info(f"Tipo de pregunta detectado: {tipo_pregunta if tipo_pregunta else 'general'}")
    
    # Seleccionar la plantilla adecuada según el tipo de pregunta y la complejidad
    if tipo_pregunta == "saludo":
        plantilla = plantilla_saludo
        logger.info("Usando plantilla de saludo")
    elif tipo_pregunta == "despedida":
        plantilla = plantilla_despedida
        logger.info("Usando plantilla de despedida")
    elif tipo_pregunta == "definicion":
        plantilla = plantilla_definicion
        logger.info("Usando plantilla de definición")
    elif tipo_pregunta == "ejemplo":
        plantilla = plantilla_ejemplo
        logger.info("Usando plantilla de ejemplo")
    elif tipo_pregunta == "comparacion":
        plantilla = plantilla_comparacion
        logger.info("Usando plantilla de comparación")
    elif tipo_pregunta == "resumen":
        plantilla = plantilla_resumen
        logger.info("Usando plantilla de resumen")
    elif tipo_pregunta == "aclaracion":
        plantilla = plantilla_aclaracion
        logger.info("Usando plantilla de aclaración")
    elif tipo_pregunta == "seguimiento":
        plantilla = plantilla_seguimiento
        logger.info("Usando plantilla de seguimiento")
    elif tipo_pregunta == "fuera_contexto":
        plantilla = plantilla_fuera_contexto
        logger.info("Usando plantilla fuera de contexto")
    elif tipo_pregunta == "syllabus":
        plantilla = plantilla_especifica
        logger.info("Usando plantilla específica para syllabus")
    elif tipo_pregunta == "plantilla_especifica":
        plantilla = plantilla_especifica
        logger.info("Usando plantilla plantilla_especifica")
    else:
        # Si no se detecta un tipo específico, usar la plantilla según la complejidad
        if tipo_respuesta == "detailed":
            plantilla = plantilla_detallada
            logger.info("Usando plantilla detallada")
        elif tipo_respuesta == "concise":
            plantilla = plantilla_concisa
            logger.info("Usando plantilla concisa")
        else:
            plantilla = plantilla_mixta
            logger.info("Usando plantilla mixta")


    # Formatear el prompt según la plantilla seleccionada
    prompt_formateado = plantilla.format(
        contexto=contexto_base,
        conversacion=conversacion,
        pregunta=pregunta.texto
    )
    
    logger.info(f"Tipo de respuesta detectado: {tipo_respuesta}")
    
    try:
        if cadena:
            # Usar la cadena de QA con recuperación
            if using_vector_db:  # Si estamos usando FAISS/RetrievalQA
                try:
                    result = cadena({"query": prompt_formateado})
                    respuesta = result["result"]
                    
                    # Extraer y mostrar las fuentes utilizadas
                    if "source_documents" in result:
                        fuentes = [doc.metadata.get("source", "Desconocido") for doc in result["source_documents"]]
                        logger.info(f"Fuentes utilizadas: {fuentes}")
                except Exception as retrieval_error:
                    logger.error(f"Error en recuperación con FAISS: {retrieval_error}")
                    # Fallback inmediato a procesamiento en memoria
                    if fragmentos:
                        result = cadena({"input_documents": fragmentos, "question": prompt_formateado})
                        respuesta = result["output_text"]
                    else:
                        respuesta = "Lo siento, no puedo acceder a la información en este momento."
            else:  # Si estamos usando el fallback con load_qa_chain
                # Para load_qa_chain necesitamos pasar los documentos explícitamente
                if fragmentos:
                    result = cadena({"input_documents": fragmentos, "question": prompt_formateado})
                    respuesta = result["output_text"]
                else:
                    respuesta = "No tengo información suficiente para responder a esa pregunta."
            
            # Postprocesamiento para mejorar la presentación
            respuesta = respuesta.strip()
            # Eliminar frases repetitivas como "como asistente educativo"
            respuesta = re.sub(r'Como (un )?asistente educativo( conversacional)?,?', '', respuesta)
            respuesta = re.sub(r'Basado en el syllabus( del curso)?,?', '', respuesta)
            
            # Simplificar expresiones comunes
            respuesta = re.sub(r'Es importante (mencionar|destacar|señalar) que', '', respuesta)
            
            # Limpiar espacios en blanco múltiples y saltos de línea excesivos
            respuesta = re.sub(r'\n{3,}', '\n\n', respuesta)
            respuesta = re.sub(r' {2,}', ' ', respuesta)
            respuesta = respuesta.strip()
            
            # Aplicar reglas según el tipo de respuesta
            if tipo_respuesta == "concise" and len(respuesta.split()) > 50:
                # Si la respuesta concisa es muy larga, intentar recortarla
                sentences = re.split(r'[.!?]\s+', respuesta)
                if len(sentences) > 3:
                    respuesta = '. '.join(sentences[:3]) + '.'
        else:
            # Respuesta predeterminada si no se pudo cargar el PDF
            respuesta = "Lo siento, no puedo acceder a la información del syllabus en este momento. ¿Hay algo más en lo que pueda ayudarte?"
        
        # Si el usuario proporcionó ID y token de sesión, guardar la interacción en el historial
        if pregunta.userId and pregunta.chatToken:
            try:
                # Recuperar historial actual
                db = SessionLocal()
                session = db.query(ChatSession).filter(
                    ChatSession.user_id == pregunta.userId,
                    ChatSession.session_id == pregunta.chatToken
                ).first()
                
                history = []
                if session:
                    # Si existe la sesión, cargar el historial
                    import json
                    if isinstance(session.history, str):
                        history = json.loads(session.history)
                    else:
                        history = session.history
                
                # Añadir la nueva interacción
                history.append({"sender": "user", "text": pregunta.texto, "timestamp": datetime.now().isoformat()})
                history.append({"sender": "bot", "text": respuesta, "timestamp": datetime.now().isoformat()})
                
                # Guardar o actualizar
                if session:
                    session.history = json.dumps(history)
                else:
                    new_session = ChatSession(
                        session_id=pregunta.chatToken,
                        user_id=pregunta.userId,
                        history=json.dumps(history)
                    )
                    db.add(new_session)
                
                db.commit()
                db.close()
            except Exception as e:
                print(f"Error al guardar historial: {e}")
        
        return {"respuesta": respuesta}
    except Exception as e:
        print(f"Error en la generación de respuesta: {e}")
        return {"error": str(e)}

# --- Endpoints de autenticación ---
@app.post("/auth/register")
async def register_user(request: Request):
    try:
        data = await request.json()
        logger.info(f"Datos de registro recibidos: {data}")
        
        nombre = data.get("nombre")
        email = data.get("email")
        password = data.get("password")
        
        if not all([nombre, email, password]):
            logger.error(f"Campos faltantes en registro: {data}")
            return {"success": False, "message": "Todos los campos son requeridos"}
        
        # Verificar si el email ya existe
        with SessionLocal() as db:
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                logger.warning(f"Email ya registrado: {email}")
                return {"success": False, "message": "El email ya está registrado"}
            
            # Crear nuevo usuario
            try:
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
                
                logger.info(f"Usuario registrado exitosamente: {email}")
                return {
                    "success": True, 
                    "message": "Usuario registrado exitosamente",
                    "user": {
                        "id": new_user.id,
                        "nombre": new_user.nombre,
                        "email": new_user.email
                    }
                }
            except Exception as e:
                db.rollback()
                logger.error(f"Error al crear usuario: {str(e)}")
                return {"success": False, "message": f"Error al crear usuario: {str(e)}"}
    except Exception as e:
        logger.error(f"Error general en registro: {str(e)}")
        return {"success": False, "message": f"Error general: {str(e)}"}






# Modelo para solicitar sugerencias
class SolicitudSugerencias(BaseModel):
    userId: str = None
    chatToken: str = None
    history: list = None  # [{sender, text, timestamp}]

# Plantilla para generar sugerencias de preguntas
plantilla_sugerencias = PromptTemplate(
    input_variables=["contexto", "conversacion"],
    template=(
        "{contexto}\n\n"
        "Instrucciones específicas: Basándote en la conversación previa, genera 3 posibles preguntas de seguimiento "
        "que el usuario podría querer hacer. Las preguntas deben ser cortas (máximo 8 palabras), relevantes al tema "
        "de la conversación, y variadas en su enfoque (por ejemplo: una para profundizar, otra para un ejemplo, "
        "y otra para un tema relacionado). Devuelve solo las 3 preguntas separadas por '|'.\n\n"
        "Conversación previa:\n{conversacion}\n\n"
        "Tres sugerencias de preguntas:"
    )
)

# Modelo para las sugerencias
class SugerenciasIn(BaseModel):
    history: list = None  # [{sender, text, timestamp}]

@app.post("/sugerencias")
def generar_sugerencias(solicitud: SolicitudSugerencias):
    """Genera sugerencias de preguntas basadas en el historial de chat."""
    try:
        # Extraer el historial reciente
        history = solicitud.history if solicitud.history else []
        
        # Si no hay historial, devolver sugerencias predeterminadas
        if not history:
            return {
                "sugerencias": [
                    "¿Qué es la inteligencia artificial?",
                    "¿Cuáles son los temas principales del curso?",
                    "¿Cómo se evalúa el curso?"
                ]
            }
        
        # Obtener las últimas interacciones para contexto
        recent_history = history[-5:] if len(history) > 5 else history
        
        # Formatear el historial para el prompt
        formatted_history = ""
        for msg in recent_history:
            if msg.get('sender') == 'user':
                formatted_history += f"Usuario: {msg.get('text','')}\n"
            elif msg.get('sender') == 'bot':
                formatted_history += f"Bot: {msg.get('text','')}\n"
        
        # Crear prompt para generar sugerencias
        prompt = f"""
        Basado en la siguiente conversación, genera 3 preguntas sugeridas que el usuario podría querer hacer a continuación.
        Las sugerencias deben ser breves (máximo 60 caracteres), relevantes al contexto de la conversación, y formuladas como preguntas directas.
        Las sugerencias deben ser siempre en español.
        Conversación:
        {formatted_history}
        
        Genera solo las 3 preguntas, sin numeración ni explicación adicional.
        """
        
        try:
            # Generar sugerencias usando el modelo
            response = llm.invoke(prompt)
            
            # Procesar la respuesta para extraer las sugerencias
            sugerencias = []
            for line in response.strip().split('\n'):
                line = line.strip()
                if line and not line.isspace():
                    # Limpiar numeración si existe
                    cleaned_line = re.sub(r'^\d+[\.\)-]\s*', '', line)
                    sugerencias.append(cleaned_line)
            
            # Asegurar que tenemos exactamente 3 sugerencias
            while len(sugerencias) < 3:
                sugerencias.append("¿Necesitas más información sobre algún tema?")
            
            # Limitar a 3 sugerencias
            sugerencias = sugerencias[:3]
            
            return {"sugerencias": sugerencias}
        except Exception as e:
            print(f"Error al generar sugerencias con el modelo: {e}")
            # Devolver sugerencias predeterminadas en caso de error
            return {
                "sugerencias": [
                    "¿Qué es la inteligencia artificial?",
                    "¿Cuáles son los temas principales del curso?",
                    "¿Cómo se evalúa el curso?"
                ]
            }
    except Exception as e:
        print(f"Error en generar_sugerencias: {e}")
        return {"error": str(e)}









@app.post("/auth/login")
async def login_user(request: Request):
    try:
        data = await request.json()
        logger.info(f"Datos de login recibidos: {data}")
        
        email = data.get("email")
        password = data.get("password")
        
        if not email or not password:
            logger.error("Email o contraseña faltantes")
            return {"success": False, "message": "Email y contraseña son requeridos"}
        
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                logger.warning(f"Usuario no encontrado: {email}")
                return {"success": False, "message": "Credenciales incorrectas"}
            
            try:
                if not pwd_context.verify(password, user.password):
                    logger.warning(f"Contraseña incorrecta para: {email}")
                    return {"success": False, "message": "Credenciales incorrectas"}
                
                logger.info(f"Login exitoso: {email}")
                return {
                    "success": True,
                    "user": {
                        "id": user.id,
                        "nombre": user.nombre,
                        "email": user.email
                    }
                }
            except Exception as e:
                logger.error(f"Error al verificar contraseña: {str(e)}")
                return {"success": False, "message": f"Error en autenticación: {str(e)}"}
    except Exception as e:
        logger.error(f"Error general en login: {str(e)}")
        return {"success": False, "message": f"Error general: {str(e)}"}

# --- Endpoints para historial y feedback ---
@app.delete("/chat/session")
def delete_session_endpoint(user_id: str, session_id: str):
    """Elimina una sesión de chat específica."""
    try:
        print(f"delete_session_endpoint: user_id={user_id}, session_id={session_id}")
        with SessionLocal() as db:
            session = db.query(ChatSession).filter(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            ).first()
            
            if session:
                db.delete(session)
                db.commit()
                return {"ok": True}
            else:
                return {"ok": False, "error": "Sesión no encontrada"}
    except Exception as e:
        print("delete_session_endpoint error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/sessions")
def get_sessions_endpoint(user_id: str):
    """Devuelve todas las sesiones previas de un usuario."""
    try:
        print(f"get_sessions_endpoint: user_id={user_id}")
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT session_id, updated_at as created_at FROM chat_sessions WHERE user_id = :user_id ORDER BY updated_at DESC"),
                {"user_id": user_id}
            ).fetchall()
            return [{"session_id": row[0], "created_at": row[1]} for row in result]
    except Exception as e:
        print("get_sessions_endpoint error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/history")
def get_session_endpoint(user_id: str, session_id: str):
    """Obtiene el historial de una sesión de chat."""
    try:
        print(f"get_session_endpoint: user_id={user_id}, session_id={session_id}")
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT history FROM chat_sessions WHERE user_id = :user_id AND session_id = :session_id"),
                {"user_id": user_id, "session_id": session_id}
            ).fetchone()
            if result and result[0]:
                import json
                # Si el resultado ya es un objeto JSON, no necesitamos convertirlo
                if isinstance(result[0], dict) or isinstance(result[0], list):
                    return result[0]
                else:
                    return json.loads(result[0])
            return []
    except Exception as e:
        print("get_session_endpoint error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/history")
def save_session_endpoint(data: SessionIn):
    """Guarda el historial completo de una sesión de chat."""
    try:
        print(f"save_session_endpoint: user_id={data.user_id}, session_id={data.session_id}")
        import json
        history_json = json.dumps(data.history)
        
        with engine.connect() as connection:
            # Verificar si la sesión existe
            exists = connection.execute(
                text("SELECT 1 FROM chat_sessions WHERE user_id = :user_id AND session_id = :session_id"),
                {"user_id": data.user_id, "session_id": data.session_id}
            ).fetchone()
            
            if exists:
                # Actualizar sesión existente
                connection.execute(
                    text("UPDATE chat_sessions SET history = :history WHERE user_id = :user_id AND session_id = :session_id"),
                    {"user_id": data.user_id, "session_id": data.session_id, "history": history_json}
                )
            else:
                # Insertar nueva sesión
                connection.execute(
                    text("INSERT INTO chat_sessions (user_id, session_id, history) VALUES (:user_id, :session_id, :history)"),
                    {"user_id": data.user_id, "session_id": data.session_id, "history": history_json}
                )
            
            connection.commit()
        return {"ok": True}
    except Exception as e:
        print("save_session_endpoint error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/feedback")
def save_feedback_endpoint(fb: FeedbackIn):
    """Guarda feedback para una pregunta/respuesta."""
    try:
        print(f"save_feedback_endpoint: user_id={fb.user_id}, session_id={fb.session_id}")
        with engine.connect() as connection:
            connection.execute(
                text("""
                    INSERT INTO feedback (user_id, session_id, pregunta, respuesta, rating, comentario) 
                    VALUES (:user_id, :session_id, :pregunta, :respuesta, :rating, :comentario)
                """),
                {"user_id": fb.user_id, "session_id": fb.session_id, "pregunta": fb.pregunta, 
                 "respuesta": fb.respuesta, "rating": fb.rating, "comentario": fb.comentario}
            )
            connection.commit()
        return {"ok": True}
    except Exception as e:
        print("save_feedback_endpoint error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/feedback")
def get_feedback_endpoint(user_id: str = None, session_id: str = None):
    """Obtiene feedbacks filtrando por usuario o sesión."""
    try:
        print(f"get_feedback_endpoint: user_id={user_id}, session_id={session_id}")
        query = "SELECT id, user_id, session_id, pregunta, respuesta, rating, created_at FROM feedback WHERE 1=1"
        params = {}
        
        if user_id:
            query += " AND user_id = :user_id"
            params["user_id"] = user_id
        
        if session_id:
            query += " AND session_id = :session_id"
            params["session_id"] = session_id
        
        query += " ORDER BY created_at DESC"
        
        with engine.connect() as connection:
            result = connection.execute(text(query), params).fetchall()
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "session_id": row[2],
                    "pregunta": row[3],
                    "respuesta": row[4],
                    "rating": row[5],
                    "created_at": row[6]
                } for row in result
            ]
    except Exception as e:
        print("get_feedback_endpoint error:", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/message_ratings")
def get_message_ratings_endpoint(user_id: str, session_id: str):
    """Obtiene las calificaciones (ratings) para los mensajes de una sesión específica."""
    try:
        print(f"get_message_ratings_endpoint: user_id={user_id}, session_id={session_id}")
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT pregunta, respuesta, rating 
                    FROM feedback 
                    WHERE user_id = :user_id AND session_id = :session_id
                """),
                {"user_id": user_id, "session_id": session_id}
            ).fetchall()
            
            return [
                {
                    "pregunta": row[0],
                    "respuesta": row[1],
                    "rating": row[2]
                } for row in result
            ]
    except Exception as e:
        print("get_message_ratings_endpoint error:", e)
        raise HTTPException(status_code=500, detail=str(e))


# Si se ejecuta directamente este script
if __name__ == "__main__":
    import uvicorn
    print("Iniciando servidor FastAPI...")
    uvicorn.run(app, host="0.0.0.0", port=8000)