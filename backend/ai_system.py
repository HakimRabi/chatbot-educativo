import os
import re
import logging
import sys
import time
import traceback
from glob import glob
from datetime import datetime
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain.chains import LLMChain, RetrievalQA
from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores import FAISS, Chroma
from langchain_community.document_loaders import PyPDFLoader

from config import *
from utils import *
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
        self.llm_cache = {}  # Cache para múltiples modelos
        self.current_model = None
        self.memory = None
        self.vector_store = None
        self.chroma_error_details = None
        self.faiss_error_details = None
        self.is_initialized = False
        self.data_dir = os.path.dirname(CHROMA_PATH) if CHROMA_PATH else "data"
        
        # No inicializar automáticamente, se hará desde el servidor
    
    def get_or_create_llm(self, model_name=None):
        """Obtiene o crea una instancia de LLM para el modelo especificado"""
        if model_name is None:
            model_name = DEFAULT_MODEL
            
        # Verificar si el modelo está disponible
        if model_name not in AVAILABLE_MODELS:
            logger.warning(f"Modelo {model_name} no disponible, usando {DEFAULT_MODEL}")
            model_name = DEFAULT_MODEL
            
        # Usar cache para evitar recrear instancias
        if model_name in self.llm_cache:
            logger.debug(f"Usando LLM cacheado para modelo: {model_name}")
            return self.llm_cache[model_name]
            
        try:
            model_config = AVAILABLE_MODELS[model_name]
            logger.info(f"Creando nueva instancia LLM para modelo: {model_name}")
            
            llm_instance = OllamaLLM(
                model=model_config["name"],
                temperature=model_config["temperature"]
            )
            
            # Cachear la instancia
            self.llm_cache[model_name] = llm_instance
            logger.info(f"✅ LLM {model_name} creado y cacheado")
            
            return llm_instance
            
        except Exception as e:
            logger.error(f"❌ Error creando LLM para {model_name}: {e}")
            # Fallback al modelo por defecto
            if model_name != DEFAULT_MODEL:
                return self.get_or_create_llm(DEFAULT_MODEL)
            raise
    
    def switch_model(self, model_name):
        """Cambia el modelo activo del sistema"""
        try:
            logger.info(f"Cambiando modelo de {self.current_model} a {model_name}")
            
            # Obtener o crear la instancia del LLM
            new_llm = self.get_or_create_llm(model_name)
            
            # Actualizar el LLM principal
            self.llm = new_llm
            self.current_model = model_name
            
            # Recrear la cadena de RetrievalQA si existe vector store
            if self.vector_store is not None:
                logger.info("Actualizando RetrievalQA con nuevo modelo...")
                retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
                
                self.cadena = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=retriever,
                    return_source_documents=True,
                    chain_type_kwargs={"prompt": PROMPT_QA_SIMPLE}
                )
                logger.info(f"✅ RetrievalQA actualizado con modelo {model_name}")
            
            logger.info(f"✅ Modelo cambiado exitosamente a: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cambiando modelo a {model_name}: {e}")
            return False
    
    def get_available_models(self):
        """Retorna la lista de modelos disponibles"""
        return AVAILABLE_MODELS
    
    def get_current_model(self):
        """Retorna el modelo actualmente activo"""
        return self.current_model or DEFAULT_MODEL
    
    def check_chromadb_dependencies(self):
        """Verifica las dependencias necesarias para ChromaDB."""
        try:
            import chromadb
            logger.info(f"ChromaDB version: {chromadb.__version__}")
            
            # Verificar sqlite3
            import sqlite3
            logger.info(f"SQLite3 version: {sqlite3.sqlite_version}")
            
            # Verificar que se puede crear un cliente
            try:
                client = chromadb.Client()
                logger.info("ChromaDB client creation test: SUCCESS")
                return True
            except Exception as client_error:
                logger.error(f"ChromaDB client creation failed: {client_error}")
                return False
                
        except ImportError as e:
            logger.error(f"ChromaDB import failed: {e}")
            return False
        except Exception as e:
            logger.error(f"ChromaDB dependency check failed: {e}")
            return False

    def setup_chroma_vectorstore(self, documents, embeddings, persist_directory):
        """Configura ChromaDB con reutilización inteligente de persistencia"""
        try:
            import chromadb
            from langchain_chroma import Chroma
            
            logger.info(f"🔍 Configurando ChromaDB en: {persist_directory}")
            
            # Crear directorio si no existe
            os.makedirs(persist_directory, exist_ok=True)
            
            # Verificar si existe una base de datos persistida
            try:
                client = chromadb.PersistentClient(path=persist_directory)
                collection_name = "langchain"
                
                # API actualizada para ChromaDB v0.6.0+
                try:
                    # Intentar obtener la colección directamente
                    collection = client.get_collection(collection_name)
                    doc_count = collection.count()
                    
                    if doc_count > 0 and doc_count >= len(documents):
                        logger.info(f"🔄 Reutilizando ChromaDB existente con {doc_count} documentos")
                        
                        # Cargar vector store existente SIN recrear
                        vector_store = Chroma(
                            client=client,
                            collection_name=collection_name,
                            embedding_function=embeddings,
                            persist_directory=persist_directory
                        )
                        
                        logger.info("✅ ChromaDB cargado desde persistencia - ¡Inicio rápido!")
                        return vector_store
                        
                    elif doc_count > 0 and doc_count < len(documents):
                        logger.info(f"📄 Base existente ({doc_count} docs) vs nuevos ({len(documents)} docs)")
                        logger.info("🔄 Actualizando base de datos...")
                        
                        # Cargar existente y agregar documentos faltantes
                        vector_store = Chroma(
                            client=client,
                            collection_name=collection_name,
                            embedding_function=embeddings,
                            persist_directory=persist_directory
                        )
                        
                        # Agregar documentos nuevos
                        new_docs = documents[doc_count:]
                        if new_docs:
                            vector_store.add_documents(new_docs)
                            logger.info(f"➕ Agregados {len(new_docs)} documentos nuevos")
                        
                        return vector_store
                    else:
                        logger.info("📋 Colección vacía, recreando...")
                        
                except ValueError as ve:
                    # La colección no existe
                    if "does not exist" in str(ve) or "Collection" in str(ve):
                        logger.info("📋 No existe colección previa, creando nueva...")
                    else:
                        raise ve
                        
            except Exception as e:
                # Si hay error de corrupted database, limpiarla
                if "_type" in str(e) or "corrupted" in str(e).lower():
                    logger.warning(f"🗑️ Base de datos corrupta detectada: {e}")
                    logger.info("🧹 Limpiando base de datos corrupta...")
                    
                    try:
                        import shutil
                        if os.path.exists(persist_directory):
                            # Hacer backup por seguridad
                            backup_path = f"{persist_directory}_backup_{int(datetime.now().timestamp())}"
                            shutil.move(persist_directory, backup_path)
                            logger.info(f"📁 Backup creado en: {backup_path}")
                            
                            # Recrear directorio limpio
                            os.makedirs(persist_directory, exist_ok=True)
                            logger.info("✅ Directorio ChromaDB limpiado")
                        
                    except Exception as cleanup_error:
                        logger.error(f"❌ Error limpiando DB: {cleanup_error}")
                else:
                    logger.warning(f"⚠️ Error verificando base existente: {e}")
                
                logger.info("🔄 Creando nueva base de datos...")
            
            # Crear nueva base de datos
            logger.info("🔧 Creando nuevo vector store con ChromaDB...")
            
            vector_store = Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                persist_directory=persist_directory,
                collection_name=collection_name
            )
            
            logger.info(f"💾 ChromaDB creado con {len(documents)} documentos")
            return vector_store
            
        except Exception as e:
            logger.error(f"❌ Error configurando ChromaDB: {e}")
            raise

    def setup_vector_database(self):
        """Configura la base de datos vectorial con optimización de persistencia"""
        try:
            logger.info("🔍 Configurando base de datos vectorial...")
            
            if not self.fragmentos:
                logger.warning("⚠️ No hay fragmentos disponibles")
                return False
            
            # Configurar embeddings
            embeddings = OllamaEmbeddings(model="nomic-embed-text")
            
            # Configurar ChromaDB con persistencia optimizada
            chroma_path = os.path.join(self.data_dir, "chroma_db")
            
            # Verificar si existe base de datos previa
            if os.path.exists(chroma_path):
                chroma_files = [f for f in os.listdir(chroma_path) if not f.startswith('.')]
                if chroma_files:
                    logger.info(f"📁 Base de datos ChromaDB existente encontrada ({len(chroma_files)} archivos)")
                    
                    try:
                        # Intentar cargar base existente
                        start_time = time.time()
                        vector_store = self.setup_chroma_vectorstore(
                            self.fragmentos, embeddings, chroma_path
                        )
                        
                        load_time = time.time() - start_time
                        logger.info(f"⚡ Base de datos cargada en {load_time:.2f} segundos")
                        
                        self.vector_store = vector_store
                        self.using_chroma = True
                        self.using_vector_db = True
                        
                        logger.info("🎉 ChromaDB inicializado con persistencia")
                        return True
                        
                    except Exception as load_error:
                        logger.warning(f"⚠️ Error cargando base existente: {load_error}")
                        logger.info("🔄 Recreando base de datos...")
            
            # Crear nueva base de datos si no existe o falló la carga
            logger.info("🔧 Creando nueva base de datos ChromaDB...")
            start_time = time.time()
            
            vector_store = self.setup_chroma_vectorstore(
                self.fragmentos, embeddings, chroma_path
            )
            
            creation_time = time.time() - start_time
            logger.info(f"⚡ Base de datos creada en {creation_time:.2f} segundos")
            
            self.vector_store = vector_store
            self.using_chroma = True
            self.using_vector_db = True
            
            logger.info("🎉 ChromaDB creado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup_vector_database: {e}")
            # Continuar con fallback a FAISS si es necesario
            return self.setup_faiss_fallback(embeddings)

    def setup_faiss_fallback(self, embeddings):
        """Configura FAISS como fallback si ChromaDB falla"""
        try:
            logger.info("🔄 Configurando FAISS como fallback...")
            os.makedirs(FAISS_PATH, exist_ok=True)
            
            self.vector_store = FAISS.from_documents(documents=self.fragmentos, embedding=embeddings)
            self.vector_store.save_local(FAISS_PATH)
            
            self.using_chroma = False
            self.using_vector_db = True
            logger.info("✅ FAISS configurado como fallback")
            return True
            
        except Exception as faiss_error:
            self.faiss_error_details = {
                "error": str(faiss_error),
                "type": type(faiss_error).__name__,
                "traceback": traceback.format_exc()
            }
            logger.error(f"❌ Error configurando FAISS: {faiss_error}")
            self.vector_store = None
            self.using_vector_db = False
            return False
    
    def get_error_diagnostics(self):
        """Retorna información detallada sobre errores ocurridos."""
        diagnostics = {
            "chromadb_available": self.check_chromadb_dependencies(),
            "using_chroma": self.using_chroma,
            "using_vector_db": self.using_vector_db,
            "fragmentos_count": len(self.fragmentos),
            "documentos_count": len(self.documentos),
            "llm_available": self.llm is not None,
            "vector_store_available": self.vector_store is not None,
            "chroma_error": self.chroma_error_details,
            "faiss_error": self.faiss_error_details
        }
        
        # Información del sistema
        diagnostics["system_info"] = {
            "python_version": sys.version,
            "platform": sys.platform,
            "chroma_path": CHROMA_PATH,
            "faiss_path": FAISS_PATH,
            "chroma_path_exists": os.path.exists(CHROMA_PATH),
            "faiss_path_exists": os.path.exists(FAISS_PATH)
        }
        
        # Verificar versiones específicas
        try:
            import chromadb
            diagnostics["chromadb_version"] = chromadb.__version__
        except:
            diagnostics["chromadb_version"] = "No disponible"
        
        try:
            import langchain_community
            diagnostics["langchain_community_version"] = langchain_community.__version__
        except:
            diagnostics["langchain_community_version"] = "No disponible"
            
        return diagnostics

    def fix_chromadb_config(self):
        """Intenta reparar la configuración corrupta de ChromaDB."""
        try:
            import shutil
            import sqlite3
            
            # Backup del directorio actual
            if os.path.exists(CHROMA_PATH):
                backup_path = f"{CHROMA_PATH}_backup_{int(datetime.now().timestamp())}"
                logger.info(f"Creando backup en: {backup_path}")
                shutil.copytree(CHROMA_PATH, backup_path)
                
                # Intentar limpiar la base de datos
                db_path = os.path.join(CHROMA_PATH, "chroma.sqlite3")
                if os.path.exists(db_path):
                    try:
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        
                        # Verificar la tabla de configuraciones
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collections';")
                        if cursor.fetchone():
                            # Limpiar configuraciones corruptas
                            cursor.execute("DELETE FROM collections WHERE configuration NOT LIKE '%_type%';")
                            conn.commit()
                            logger.info("Configuraciones corruptas limpiadas")
                        
                        conn.close()
                        return True
                        
                    except Exception as db_error:
                        logger.error(f"Error reparando BD: {db_error}")
                        conn.close()
                
                # Si no se puede reparar, eliminar completamente
                logger.info("Eliminando directorio ChromaDB corrupto")
                shutil.rmtree(CHROMA_PATH)
                return True
                
        except Exception as e:
            logger.error(f"Error en fix_chromadb_config: {e}")
            
        return False

    def initialize_system(self):
        """Inicializa el sistema de IA completo de forma síncrona."""
        if self.is_initialized:
            logger.info("Sistema ya inicializado")
            return True
            
        try:
            logger.info("🚀 Iniciando sistema de IA...")
            
            # Verificar dependencias de ChromaDB
            logger.info("📋 Verificando dependencias...")
            chromadb_available = self.check_chromadb_dependencies()
            logger.info(f"ChromaDB dependencies available: {chromadb_available}")
            
            # Procesar PDFs
            logger.info("📚 Procesando archivos PDF...")
            self.documentos, self.fragmentos = process_pdf_files_optimized(PDFS_DIR, CACHE_DIR)
            
            if not self.fragmentos:
                logger.warning("No se encontraron fragmentos en cache, cargando PDFs directamente...")
                pdf_files = glob(os.path.join(PDFS_DIR, "*.pdf"))
                logger.info(f"Archivos PDF encontrados: {len(pdf_files)}")
                
                if pdf_files:
                    for i, pdf_path in enumerate(pdf_files):
                        try:
                            logger.info(f"📄 Cargando PDF {i+1}/{len(pdf_files)}: {os.path.basename(pdf_path)}")
                            loader = PyPDFLoader(pdf_path)
                            self.documentos.extend(loader.load())
                        except Exception as e:
                            logger.error(f"Error cargando {pdf_path}: {e}")
                    
                    if self.documentos:
                        logger.info(f"✅ Documentos cargados: {len(self.documentos)}")
                        logger.info("🔧 Fragmentando documentos...")
                        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
                        self.fragmentos = splitter.split_documents(self.documentos)
                        logger.info(f"✅ Fragmentos generados: {len(self.fragmentos)}")
            else:
                logger.info(f"✅ Fragmentos cargados desde cache: {len(self.fragmentos)}")
            
            # Inicializar embeddings y LLM
            logger.info("🧠 Inicializando modelo de lenguaje...")
            try:
                embeddings = OllamaEmbeddings(model="nomic-embed-text")
                self.llm = self.get_or_create_llm(DEFAULT_MODEL)
                self.current_model = DEFAULT_MODEL
                logger.info(f"✅ Embeddings y LLM inicializados correctamente con modelo: {DEFAULT_MODEL}")
            except Exception as e:
                logger.error(f"❌ Error inicializando Ollama: {e}")
                raise
            
            # Configurar base de datos vectorial con optimización
            if chromadb_available and self.fragmentos:
                success = self.setup_vector_database()
                if not success:
                    logger.warning("⚠️ Falló configuración vectorial, usando modo básico")
            else:
                if not chromadb_available:
                    logger.warning("⚠️ ChromaDB no disponible")
                elif not self.fragmentos:
                    logger.warning("⚠️ No hay fragmentos para procesar")
            
            # Configurar cadena de recuperación
            if self.vector_store is not None:
                logger.info("⚙️ Configurando RetrievalQA...")
                retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
                
                self.cadena = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=retriever,
                    return_source_documents=True,
                    chain_type_kwargs={"prompt": PROMPT_QA_SIMPLE}
                )
                
                logger.info(f"✅ RetrievalQA configurado con {'ChromaDB' if self.using_chroma else 'FAISS'}")
            else:
                logger.warning("⚠️ No se pudo configurar vector store - funcionando sin RAG")
            
            # Crear memoria para conversación
            self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            
            self.is_initialized = True
            logger.info(f"🎉 Sistema IA LISTO: ChromaDB={self.using_chroma}, VectorDB={self.using_vector_db}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error crítico en inicialización: {e}")
            logger.error(f"Traceback completo:\n{traceback.format_exc()}")
            self.setup_fallback()
            return False

    def setup_fallback(self):
        """Configura el sistema en modo fallback."""
        try:
            logger.info("Configurando sistema en modo fallback...")
            self.llm = self.get_or_create_llm(DEFAULT_MODEL)
            self.current_model = DEFAULT_MODEL
            self.cadena = load_qa_chain(self.llm, chain_type="stuff")
            self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            self.using_vector_db = False
            logger.info("Sistema fallback configurado")
        except Exception as e:
            logger.error(f"Error en fallback: {e}")
    
    def detect_question_type(self, question_text):
        """Detecta el tipo de pregunta basado en patrones."""
        patrones_tipo_pregunta = {
            "saludo": [r"^(hola|buenos días|buenas tardes|buenas noches|saludos|hey|qué tal|cómo estás)"],
            "despedida": [r"^(adiós|chao|hasta luego|nos vemos|gracias por tu ayuda|gracias|hasta pronto)"],
            "definicion": [r"(qué|que) (es|son|significa|significan)", r"define|definir|definición", r"\b(explica|explique|explicar)\b"],
            "ejemplo": [r"(dame|da|muestra|pon) (un|unos|algunos)? ejemplos?", r"ejemplos? de"],
            "comparacion": [r"(compara|comparación|diferencias?) (entre|de)", r"(qué|que|cuál|cual) es (mejor|peor)"],
            "resumen": [r"(resume|resumen|síntesis|sintetiza)", r"(en pocas palabras|brevemente)"],
            "aclaracion": [r"(puedes|podrías) (explicar|aclarar) (mejor|de nuevo)", r"no (entiendo|comprendo)"],
            "seguimiento": [r"(y|pero) (qué|que|cómo|como)", r"(puedes|podrías) (ampliar|expandir)"],
            "syllabus": [r"(syllabus|programa|temario|contenido)", r"(coordinador|profesor|docente)"]
        }
        
        for tipo, patrones in patrones_tipo_pregunta.items():
            for patron in patrones:
                if re.search(patron, question_text.lower()):
                    return tipo
        
        return None
    
    def get_template_by_type(self, tipo_pregunta):
        """Retorna la plantilla apropiada según el tipo de pregunta."""
        template_map = {
            "saludo": plantilla_saludo,
            "despedida": plantilla_despedida,
            "definicion": plantilla_definicion,
            "ejemplo": plantilla_ejemplo,
            "comparacion": plantilla_comparacion,
            "resumen": plantilla_resumen,
            "aclaracion": plantilla_aclaracion,
            "seguimiento": plantilla_seguimiento,
            "syllabus": plantilla_especifica
        }
        
        return template_map.get(tipo_pregunta)
    
    def retrieve_relevant_documents(self, query):
        """Recupera documentos relevantes para la consulta."""
        try:
            if self.vector_store is not None:
                retriever = self.vector_store.as_retriever(
                    search_type="mmr",
                    search_kwargs={"k": 8, "lambda_mult": 0.5}
                )
                # Usar invoke en lugar de get_relevant_documents (deprecado)
                return retriever.invoke(query)
            elif self.fragmentos:
                import random
                return random.sample(self.fragmentos, min(5, len(self.fragmentos)))
        except Exception as e:
            logger.error(f"Error recuperando documentos: {e}")
        
        return []
    
    def generate_search_query(self, question, conversation_history):
        """Genera una consulta de búsqueda optimizada."""
        try:
            # Usar RunnableSequence en lugar de LLMChain (deprecado)
            cadena_reescritura = plantilla_reescritura_pregunta | self.llm
            
            result = cadena_reescritura.invoke({
                "historial_chat": conversation_history, 
                "pregunta": question
            })
            
            # El resultado directo del pipeline es el texto
            return result.strip() if isinstance(result, str) else str(result).strip()
        except Exception as e:
            logger.error(f"Error generando consulta de búsqueda: {e}")
            return question
    
    def process_question(self, pregunta_obj):
        """Procesa la pregunta principal usando el sistema completo."""
        question_text = pregunta_obj.texto
        
        # Manejar cambio de modelo si se especifica
        if hasattr(pregunta_obj, 'modelo') and pregunta_obj.modelo:
            if pregunta_obj.modelo != self.current_model:
                logger.info(f"Cambiando modelo para esta consulta: {pregunta_obj.modelo}")
                self.switch_model(pregunta_obj.modelo)
        
        # Construir historial de conversación
        conversation_history = ""
        if pregunta_obj.history and isinstance(pregunta_obj.history, list):
            history_limit = min(10, len(pregunta_obj.history))
            recent_history = pregunta_obj.history[-history_limit:]
            
            for msg in recent_history:
                if msg.get('sender') == 'user':
                    conversation_history += f"Usuario: {msg.get('text','')}\n"
                elif msg.get('sender') == 'bot':
                    conversation_history += f"Bot: {msg.get('text','')}\n"
        
        # Analizar tipo y complejidad
        tipo_pregunta = self.detect_question_type(question_text)
        tipo_respuesta = analyze_question_complexity(question_text)
        
        logger.info(f"Tipo pregunta: {tipo_pregunta}, Tipo respuesta: {tipo_respuesta}")
        
        # Generar consulta optimizada
        search_query = self.generate_search_query(question_text, conversation_history)
        
        # Recuperar documentos relevantes
        documentos_relevantes = self.retrieve_relevant_documents(search_query)
        contexto_documentos = "\n".join([doc.page_content for doc in documentos_relevantes])
        
        # Seleccionar plantilla y generar respuesta
        plantilla_seleccionada = self.get_template_by_type(tipo_pregunta)
        usar_retrieval_qa = plantilla_seleccionada is None
        
        try:
            if usar_retrieval_qa and self.cadena and self.using_vector_db:
                result = self.cadena.invoke({"query": question_text})
                respuesta = result["result"]
                logger.info("Respuesta generada con RetrievalQA")
            
            elif plantilla_seleccionada:
                respuesta = self._generate_with_template(
                    plantilla_seleccionada, question_text, 
                    conversation_history, contexto_documentos
                )
                logger.info("Respuesta generada con plantilla personalizada")
            
            else:
                respuesta = self._generate_fallback_response(
                    question_text, conversation_history, contexto_documentos
                )
                logger.info("Respuesta generada con fallback")
            
            # Limpiar respuesta
            respuesta_limpia = clean_llm_response(respuesta)
            respuesta_limpia = self._clean_response_artifacts(respuesta_limpia)
            
            return respuesta_limpia.strip()
            
        except Exception as e:
            logger.error(f"Error procesando pregunta: {e}")
            return "Lo siento, no puedo procesar tu pregunta en este momento."
    
    def _generate_with_template(self, template, question, conversation, context_docs):
        """Genera respuesta usando plantilla específica."""
        if template in [plantilla_saludo, plantilla_despedida]:
            return self.llm.invoke(template.format(contexto=contexto_base))
        
        template_modificado = (
            "{contexto}\n\n"
            "INFORMACIÓN RELEVANTE DE DOCUMENTOS:\n"
            "{contexto_documentos}\n\n"
            "{instrucciones_especificas}\n\n"
            "Conversación previa:\n{conversacion}\n\n"
            "Pregunta: {pregunta}\n\n"
            "Respuesta basada en documentos y contexto:"
        )
        
        # Extraer instrucciones específicas
        template_str = template.template
        instrucciones_match = re.search(r'Instrucciones específicas: ([^\\n]+(?:\\n[^\\n]+)*?)\\n\\n', template_str)
        instrucciones = instrucciones_match.group(1) if instrucciones_match else "Responde de manera clara y educativa."
        
        prompt_formateado = template_modificado.format(
            contexto=contexto_base,
            contexto_documentos=context_docs or "No se encontraron documentos específicamente relevantes.",
            instrucciones_especificas=instrucciones,
            conversacion=conversation,
            pregunta=question
        )
        
        return self.llm.invoke(prompt_formateado)
    
    def _generate_fallback_response(self, question, conversation, context_docs):
        """Genera respuesta usando el método fallback general."""
        prompt_fallback = f"""
        {contexto_base}
        
        INFORMACIÓN RELEVANTE DE DOCUMENTOS:
        {context_docs or "No se encontraron documentos específicamente relevantes."}
        
        CONVERSACIÓN PREVIA:
        {conversation}
        
        PREGUNTA DEL ESTUDIANTE: {question}
        
        Responde de manera educativa y clara, usando la información de los documentos cuando sea relevante:
        """
        
        return self.llm.invoke(prompt_fallback)
    
    def _clean_response_artifacts(self, response):
        """Limpia artefactos comunes en las respuestas del LLM."""
        # Eliminar frases introductorias genéricas
        response = re.sub(r'^Como (un )?asistente educativo( conversacional)?,?\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^Basado en (el syllabus|los documentos|la información)( del curso)?,?\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^¡Claro! Aquí tienes un resumen:\s*', '', response, flags=re.IGNORECASE)
        
        # Normalizar saltos de línea
        response = re.sub(r'\n{3,}', '\n\n', response)
        
        return response

    def generate_dynamic_suggestions(self, conversation_history):
        """Genera sugerencias dinámicas basadas en el historial de conversación."""
        try:
            if not self.llm or not conversation_history:
                return self._get_fallback_suggestions()
            
            # Extraer la última respuesta del bot (limitada para velocidad)
            ultima_respuesta_bot = ""
            
            # Buscar solo la última respuesta del bot (más rápido)
            for mensaje in reversed(conversation_history):
                if isinstance(mensaje, dict) and mensaje.get('sender') == 'bot':
                    ultima_respuesta_bot = mensaje.get('text', '')
                    break
            
            if not ultima_respuesta_bot or len(ultima_respuesta_bot) < 20:
                logger.info("No se encontró respuesta válida del bot, usando sugerencias por defecto")
                return self._get_fallback_suggestions()
            
            # Limitar el tamaño de la respuesta para velocidad (máximo 300 caracteres)
            if len(ultima_respuesta_bot) > 300:
                ultima_respuesta_bot = ultima_respuesta_bot[:300] + "..."
            
            # Usar plantilla simplificada para generar sugerencias
            from templates import plantilla_sugerencias_dinamicas
            
            prompt_formateado = plantilla_sugerencias_dinamicas.format(
                ultima_respuesta=ultima_respuesta_bot,
                contexto_conversacion="IA y Machine Learning"  # Contexto fijo para velocidad
            )
            
            logger.info("Generando sugerencias dinámicas rápidas")
            respuesta_llm = self.llm.invoke(prompt_formateado)
            
            # Procesar la respuesta para extraer las sugerencias
            sugerencias = self._parse_suggestions_from_response_fast(respuesta_llm)
            
            if len(sugerencias) >= 2:  # Reducir requisito a 2 sugerencias mínimo
                logger.info(f"Sugerencias dinámicas generadas exitosamente: {len(sugerencias)}")
                # Asegurar que tenemos exactamente 3 sugerencias
                while len(sugerencias) < 3:
                    sugerencias.extend(self._get_contextual_fallback_suggestions(ultima_respuesta_bot))
                return sugerencias[:3]
            else:
                logger.info("LLM no generó suficientes sugerencias, usando fallback contextual")
                return self._get_contextual_fallback_suggestions(ultima_respuesta_bot)
                
        except Exception as e:
            logger.error(f"Error generando sugerencias dinámicas: {e}")
            return self._get_fallback_suggestions()
    
    def _parse_suggestions_from_response_fast(self, respuesta_llm):
        """Versión optimizada para extraer sugerencias más rápido."""
        try:
            # Limpiar la respuesta
            respuesta_limpia = respuesta_llm.strip()
            
            # Dividir por líneas y procesar más eficientemente
            lineas = [linea.strip() for linea in respuesta_limpia.split('\n') if linea.strip()]
            
            sugerencias = []
            for linea in lineas[:6]:  # Solo revisar las primeras 6 líneas para velocidad
                # Limpiar numeración básica
                linea_limpia = re.sub(r'^\d+[\.\)\-\s]*', '', linea).strip()
                linea_limpia = re.sub(r'^[\-\*\•\s]+', '', linea_limpia).strip()
                
                # Verificar que sea una pregunta válida y corta
                if (linea_limpia and 
                    (linea_limpia.startswith('¿') or linea_limpia.lower().startswith(('qué', 'cómo', 'por qué', 'cuál', 'cuáles'))) and
                    len(linea_limpia) > 8 and len(linea_limpia.split()) <= 12):  # Aumentar límite ligeramente
                    
                    # Asegurar que termine con signo de interrogación
                    if not linea_limpia.endswith('?'):
                        linea_limpia += '?'
                    
                    sugerencias.append(linea_limpia)
                    
                    # Salir temprano si ya tenemos 3 sugerencias
                    if len(sugerencias) >= 3:
                        break
            
            return sugerencias
            
        except Exception as e:
            logger.error(f"Error procesando sugerencias del LLM: {e}")
            return []
    
    def _get_contextual_fallback_suggestions(self, ultima_respuesta):
        """Genera sugerencias contextuales basadas en palabras clave de la última respuesta."""
        try:
            respuesta_lower = ultima_respuesta.lower()
            
            # Detectar palabras clave y generar sugerencias específicas
            if any(keyword in respuesta_lower for keyword in ['machine learning', 'aprendizaje automático', 'ml']):
                return [
                    "¿Qué tipos de ML existen?",
                    "¿Cómo funciona el aprendizaje supervisado?",
                    "¿Cuáles son las aplicaciones principales?"
                ]
            elif any(keyword in respuesta_lower for keyword in ['algoritmo', 'algoritmos']):
                return [
                    "¿Qué algoritmos son más eficientes?",
                    "¿Cómo se evalúa un algoritmo?",
                    "¿Cuál es mejor para clasificación?"
                ]
            elif any(keyword in respuesta_lower for keyword in ['red neural', 'redes neuronales', 'neural']):
                return [
                    "¿Cómo funciona el backpropagation?",
                    "¿Qué son las capas ocultas?",
                    "¿Cuándo usar redes profundas?"
                ]
            elif any(keyword in respuesta_lower for keyword in ['datos', 'dataset', 'entrenamiento']):
                return [
                    "¿Cómo preparar los datos?",
                    "¿Qué es el overfitting?",
                    "¿Cuántos datos necesito?"
                ]
            elif any(keyword in respuesta_lower for keyword in ['ia', 'inteligencia artificial', 'ai']):
                return [
                    "¿Qué es la IA simbólica?",
                    "¿Cómo funciona el procesamiento de lenguaje?",
                    "¿Cuáles son las aplicaciones actuales?"
                ]
            else:
                return self._get_fallback_suggestions()
                
        except Exception as e:
            logger.error(f"Error en sugerencias contextuales: {e}")
            return self._get_fallback_suggestions()
    
    def _get_fallback_suggestions(self):
        """Retorna sugerencias por defecto cuando no se pueden generar dinámicamente."""
        return [
            "¿Qué es la inteligencia artificial?",
            "¿Cómo funciona el machine learning?",
            "¿Cuáles son los algoritmos principales?"
        ]

# NO crear instancia global automáticamente
# ai_system = AISystem()
ai_system = None

def get_ai_system():
    """Función para obtener la instancia del sistema IA"""
    global ai_system
    if ai_system is None:
        ai_system = AISystem()
    return ai_system
