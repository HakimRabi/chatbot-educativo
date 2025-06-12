import re
import os
import json
import pickle
import hashlib
import logging
from datetime import datetime
from glob import glob
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger("chatbot_utils")

def clean_llm_response(response_text):
    """Limpia la respuesta del LLM eliminando saltos de línea que cortan palabras."""
    if not response_text:
        return response_text
    
    # Paso 1: Identificar y corregir palabras cortadas por saltos de línea
    corrected_text = re.sub(r'([a-zA-ZáéíóúñÁÉÍÓÚÑ])\n([a-zA-ZáéíóúñÁÉÍÓÚÑ])', r'\1\2', response_text)
    
    # Paso 2: Corregir casos específicos donde las palabras se cortan al final de línea
    corrected_text = re.sub(r'([a-zA-ZáéíóúñÁÉÍÓÚÑ]{2,})\n([a-zA-ZáéíóúñÁÉÍÓÚÑ]{1,})', r'\1\2', corrected_text)
    
    # Paso 3: Normalizar espacios múltiples
    corrected_text = re.sub(r' {2,}', ' ', corrected_text)
    
    # Paso 4: Preservar saltos de línea intencionales
    corrected_text = re.sub(r'([.!?:;])\s*\n', r'\1\n\n', corrected_text)
    
    # Paso 5: Limpiar saltos de línea múltiples excesivos
    corrected_text = re.sub(r'\n{3,}', '\n\n', corrected_text)
    
    # Paso 6: Eliminar espacios al final de las líneas
    corrected_text = re.sub(r' +\n', '\n', corrected_text)
    
    # Paso 7: Eliminar espacios al inicio y final
    corrected_text = corrected_text.strip()
    
    return corrected_text

def get_file_hash(file_path):
    """Calcula el hash SHA-256 de un archivo para detectar cambios."""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculando hash de {file_path}: {e}")
        return None

def get_file_metadata(file_path):
    """Obtiene metadatos del archivo (hash, tamaño, fecha de modificación)."""
    try:
        stat = os.stat(file_path)
        return {
            "path": file_path,
            "hash": get_file_hash(file_path),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "name": os.path.basename(file_path)
        }
    except Exception as e:
        logger.error(f"Error obteniendo metadatos de {file_path}: {e}")
        return None

def save_cache_metadata(cache_dir, pdf_metadata, fragments_count):
    """Guarda metadatos del cache para verificación posterior."""
    metadata_file = os.path.join(cache_dir, "cache_metadata.json")
    metadata = {
        "created_at": datetime.now().isoformat(),
        "pdf_files": pdf_metadata,
        "total_fragments": fragments_count,
        "cache_version": "1.0"
    }
    
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error guardando metadatos del cache: {e}")
        return False

def load_cache_metadata(cache_dir):
    """Carga metadatos del cache si existen."""
    metadata_file = os.path.join(cache_dir, "cache_metadata.json")
    
    if not os.path.exists(metadata_file):
        return None
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando metadatos del cache: {e}")
        return None

def save_fragments_cache(cache_dir, fragments):
    """Guarda los fragmentos procesados en cache."""
    fragments_file = os.path.join(cache_dir, "fragments.pkl")
    
    try:
        with open(fragments_file, 'wb') as f:
            pickle.dump(fragments, f)
        return True
    except Exception as e:
        logger.error(f"Error guardando fragmentos en cache: {e}")
        return False

def load_fragments_cache(cache_dir):
    """Carga los fragmentos desde cache."""
    fragments_file = os.path.join(cache_dir, "fragments.pkl")
    
    if not os.path.exists(fragments_file):
        return None
    
    try:
        with open(fragments_file, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.error(f"Error cargando fragmentos desde cache: {e}")
        return None

def check_cache_validity(cache_metadata, current_pdf_files):
    """Verifica si el cache sigue siendo válido comparando archivos PDF."""
    if not cache_metadata:
        logger.info("No hay metadatos de cache previos")
        return False, []
    
    cached_files = {f["path"]: f for f in cache_metadata.get("pdf_files", [])}
    current_files = {f["path"]: f for f in current_pdf_files}
    
    # Verificar archivos eliminados
    removed_files = set(cached_files.keys()) - set(current_files.keys())
    if removed_files:
        logger.info(f"Archivos eliminados detectados: {removed_files}")
        return False, []
    
    # Verificar archivos nuevos o modificados
    new_or_modified = []
    for path, current_meta in current_files.items():
        if path not in cached_files:
            logger.info(f"Archivo nuevo detectado: {path}")
            new_or_modified.append(current_meta)
        elif cached_files[path]["hash"] != current_meta["hash"]:
            logger.info(f"Archivo modificado detectado: {path}")
            new_or_modified.append(current_meta)
        elif cached_files[path]["mtime"] != current_meta["mtime"]:
            logger.info(f"Fecha de modificación cambiada: {path}")
            new_or_modified.append(current_meta)
    
    cache_valid = len(new_or_modified) == 0
    
    logger.info(f"Cache {'válido' if cache_valid else 'inválido'}. Archivos a procesar: {len(new_or_modified)}")
    return cache_valid, new_or_modified

def process_pdf_files_optimized(pdfs_dir, cache_dir):
    """Procesa archivos PDF de manera optimizada usando cache."""
    logger.info("🚀 Iniciando procesamiento optimizado de archivos PDF...")
    
    os.makedirs(cache_dir, exist_ok=True)
    
    pdf_files = glob(os.path.join(pdfs_dir, "*.pdf"))
    if not pdf_files:
        logger.warning("No se encontraron archivos PDF")
        return [], []
    
    logger.info(f"📁 Encontrados {len(pdf_files)} archivos PDF")
    
    current_pdf_metadata = []
    for pdf_path in pdf_files:
        metadata = get_file_metadata(pdf_path)
        if metadata:
            current_pdf_metadata.append(metadata)
    
    cache_metadata = load_cache_metadata(cache_dir)
    cache_valid, files_to_process = check_cache_validity(cache_metadata, current_pdf_metadata)
    
    if cache_valid:
        logger.info("✅ Cache válido, cargando fragmentos desde cache...")
        cached_fragments = load_fragments_cache(cache_dir)
        if cached_fragments:
            logger.info(f"📄 Cargados {len(cached_fragments)} fragmentos desde cache")
            return [], cached_fragments
        else:
            logger.warning("⚠️ Metadatos válidos pero no se pudieron cargar fragmentos, reprocesando...")
            files_to_process = current_pdf_metadata
    
    if not files_to_process:
        files_to_process = current_pdf_metadata
    
    logger.info(f"🔄 Procesando {len(files_to_process)} archivos...")
    
    existing_fragments = []
    if cache_valid and cache_metadata:
        existing_fragments = load_fragments_cache(cache_dir) or []
        logger.info(f"📄 Manteniendo {len(existing_fragments)} fragmentos existentes")
    
    new_documents = []
    processed_files = set()
    
    for file_metadata in files_to_process:
        file_path = file_metadata["path"]
        
        if file_path in processed_files:
            continue
        
        try:
            logger.info(f"📖 Procesando: {file_metadata['name']} ({file_metadata['size']/1024/1024:.1f} MB)")
            
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            new_documents.extend(docs)
            processed_files.add(file_path)
            
            logger.info(f"✅ Procesado: {file_metadata['name']} - {len(docs)} páginas")
            
        except Exception as e:
            logger.error(f"❌ Error procesando {file_path}: {e}")
            continue
    
    all_fragments = existing_fragments.copy()
    
    if new_documents:
        logger.info(f"🔧 Dividiendo {len(new_documents)} documentos en fragmentos...")
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        new_fragments = splitter.split_documents(new_documents)
        all_fragments.extend(new_fragments)
        logger.info(f"📄 Creados {len(new_fragments)} nuevos fragmentos (Total: {len(all_fragments)})")
    
    if all_fragments:
        logger.info("💾 Guardando cache actualizado...")
        
        if save_fragments_cache(cache_dir, all_fragments):
            logger.info("✅ Fragmentos guardados en cache")
        
        if save_cache_metadata(cache_dir, current_pdf_metadata, len(all_fragments)):
            logger.info("✅ Metadatos guardados en cache")
    
    logger.info(f"🎉 Procesamiento completado: {len(all_fragments)} fragmentos totales")
    return new_documents, all_fragments

def analyze_question_complexity(question):
    """Analiza la complejidad de la pregunta para determinar el tipo de respuesta necesaria."""
    detailed_patterns = [
        r"explica|explicar|detalla|detallar|describe|describir|expón|exponer|desarrolla|desarrollar",
        r"(¿cómo|como)(\s+se)?(\s+hace|\s+funciona|\s+realiza|\s+desarrolla|\s+implementa|\s+ejecuta|\s+lleva a cabo|\s+logra|\s+consigue)",
        r"cuál es la (diferencia|distinción|discrepancia|divergencia)|diferencias entre|distingue entre|contrasta",
        r"qué (significa|implica|conlleva|supone|involucra|representa|denota|comprende|abarca)",
        r"profundiza|ahonda|elabora|amplía|ampliar|extiende|extender|expande|expandir",
        r"analiza|analizar|análisis|examina|examinar|estudia|estudiar|investiga|investigar",
        r"comparación|comparar|compara|coteja|cotejar|contrasta|contrastar|equipara|equiparar"
    ]
    
    concise_patterns = [
        r"^(¿)?(cuándo|cuando|donde|dónde|quién|quien|qué|que|cuál|cual)(\s+es|\s+son|\s+será|\s+fue|\s+fueron|\s+ha sido|\s+han sido)?\??$",
        r"menciona|lista|enumera|nombra|cita|indica|señala|especifica",
        r"(¿cuáles|cuales) son (los|las) (tipos|clases|categorías|variedades|modalidades|formas|ejemplos)"
    ]
    
    word_count = len(question.split())
    
    for pattern in detailed_patterns:
        if re.search(pattern, question.lower()):
            return "detailed"
    
    for pattern in concise_patterns:
        if re.search(pattern, question.lower()):
            return "concise"
    
    if word_count <= 10:
        return "concise"
    else:
        return "mixed"

def extract_keywords(text):
    """Extrae palabras clave relevantes del texto de la pregunta."""
    stopwords = [
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "a", "ante", "bajo", "con", "de", "desde", "en", "entre", "hacia", "hasta",
        "y", "e", "ni", "o", "u", "pero", "que", "si", "como", "cuando",
        "yo", "me", "tú", "te", "él", "ella", "nosotros", "vosotros", "ellos", "ellas",
        "es", "son", "está", "están", "fue", "fueron", "será", "serán"
    ]
    
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\d+', '', text)
    
    words = text.split()
    
    keywords = []
    for word in words:
        if word not in stopwords and (len(word) > 2 or word.upper() in ["IA", "ML", "DL", "NLP", "CV"]):
            keywords.append(word)
    
    return keywords[:10] if len(keywords) > 10 else keywords
