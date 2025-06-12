import os
import re
import logging
import sys
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
        self.memory = None
        self.vector_store = None
        self.chroma_error_details = None
        self.faiss_error_details = None
        self.is_initialized = False
        
        # No inicializar automáticamente, se hará desde el servidor
    
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
                embeddings = OllamaEmbeddings(model=MODEL_NAME)
                self.llm = OllamaLLM(model=MODEL_NAME, temperature=MODEL_TEMPERATURE)
                logger.info("✅ Embeddings y LLM inicializados correctamente")
            except Exception as e:
                logger.error(f"❌ Error inicializando Ollama: {e}")
                raise
            
            # Intentar configurar ChromaDB con diagnósticos detallados
            if chromadb_available and self.fragmentos:
                chroma_attempts = 0
                max_attempts = 2
                
                while chroma_attempts < max_attempts:
                    try:
                        logger.info(f"🔍 Intento {chroma_attempts + 1}: Configurando ChromaDB en: {CHROMA_PATH}")
                        
                        # Verificar permisos del directorio
                        os.makedirs(CHROMA_PATH, exist_ok=True)
                        test_file = os.path.join(CHROMA_PATH, "test_write.txt")
                        try:
                            with open(test_file, 'w') as f:
                                f.write("test")
                            os.remove(test_file)
                            logger.info("✅ Permisos de escritura verificados")
                        except Exception as perm_error:
                            logger.error(f"❌ No se puede escribir en {CHROMA_PATH}: {perm_error}")
                            raise
                        
                        # Verificar espacio en disco
                        import shutil
                        total, used, free = shutil.disk_usage(CHROMA_PATH)
                        logger.info(f"💾 Espacio libre en disco: {free // (1024**3)} GB")
                        
                        if free < 100 * 1024 * 1024:  # Menos de 100MB
                            logger.warning("⚠️ Poco espacio libre en disco")
                        
                        # Intentar crear ChromaDB con configuración específica
                        logger.info("🔧 Creando vector store con ChromaDB...")
                        
                        # Usar un nombre de colección único para evitar conflictos
                        collection_name = f"chatbot_docs_{int(datetime.now().timestamp())}"
                        
                        self.vector_store = Chroma.from_documents(
                            documents=self.fragmentos,
                            embedding=embeddings,
                            persist_directory=CHROMA_PATH,
                            collection_name=collection_name
                        )
                        
                        logger.info("💾 Persistiendo ChromaDB...")
                        try:
                            self.vector_store.persist()
                        except:
                            # Ignorar errores de persist en versiones nuevas
                            pass
                        
                        # Verificar que se creó correctamente
                        collection_count = self.vector_store._collection.count()
                        logger.info(f"✅ ChromaDB creado con {collection_count} documentos")
                        
                        self.using_chroma = True
                        self.using_vector_db = True
                        logger.info("🎉 ChromaDB inicializado correctamente")
                        break  # Salir del bucle si fue exitoso
                        
                    except Exception as chroma_error:
                        chroma_attempts += 1
                        self.chroma_error_details = {
                            "error": str(chroma_error),
                            "type": type(chroma_error).__name__,
                            "traceback": traceback.format_exc(),
                            "attempt": chroma_attempts
                        }
                        
                        logger.error(f"❌ Error con ChromaDB (intento {chroma_attempts}):")
                        logger.error(f"  Tipo: {type(chroma_error).__name__}")
                        logger.error(f"  Mensaje: {chroma_error}")
                        
                        # Si es el error específico de '_type', intentar reparar
                        if "KeyError: '_type'" in str(chroma_error) and chroma_attempts < max_attempts:
                            logger.info("🔧 Detectado error de configuración corrupta, intentando reparar...")
                            if self.fix_chromadb_config():
                                logger.info("✅ Configuración reparada, reintentando...")
                                continue
                        
                        # Si es el último intento, usar FAISS
                        if chroma_attempts >= max_attempts:
                            logger.error(f"❌ Traceback completo:\n{traceback.format_exc()}")
                            break
                
                # Si ChromaDB falló, usar FAISS
                if not self.using_chroma:
                    try:
                        logger.info("🔄 Intentando fallback a FAISS...")
                        os.makedirs(FAISS_PATH, exist_ok=True)
                        
                        logger.info("🔧 Creando vector store con FAISS...")
                        self.vector_store = FAISS.from_documents(documents=self.fragmentos, embedding=embeddings)
                        
                        logger.info("💾 Guardando FAISS...")
                        self.vector_store.save_local(FAISS_PATH)
                        
                        self.using_chroma = False
                        self.using_vector_db = True
                        logger.info("✅ FAISS inicializado como fallback")
                        
                    except Exception as faiss_error:
                        self.faiss_error_details = {
                            "error": str(faiss_error),
                            "type": type(faiss_error).__name__,
                            "traceback": traceback.format_exc()
                        }
                        logger.error(f"❌ Error con FAISS fallback:")
                        logger.error(f"  Tipo: {type(faiss_error).__name__}")
                        logger.error(f"  Mensaje: {faiss_error}")
                        
                        self.vector_store = None
                        self.using_vector_db = False
            else:
                if not chromadb_available:
                    logger.warning("⚠️ ChromaDB no disponible, usando FAISS...")
                elif not self.fragmentos:
                    logger.warning("⚠️ No hay fragmentos para procesar")
                
                # Intentar FAISS directamente
                if self.fragmentos:
                    try:
                        logger.info("🔧 Configurando FAISS directamente...")
                        os.makedirs(FAISS_PATH, exist_ok=True)
                        
                        self.vector_store = FAISS.from_documents(documents=self.fragmentos, embedding=embeddings)
                        self.vector_store.save_local(FAISS_PATH)
                        
                        self.using_chroma = False
                        self.using_vector_db = True
                        logger.info("✅ FAISS configurado directamente")
                        
                    except Exception as faiss_error:
                        self.faiss_error_details = {
                            "error": str(faiss_error),
                            "type": type(faiss_error).__name__,
                            "traceback": traceback.format_exc()
                        }
                        logger.error(f"❌ Error configurando FAISS: {faiss_error}")
                        self.vector_store = None
                        self.using_vector_db = False
            
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
            self.llm = OllamaLLM(model=MODEL_NAME, temperature=MODEL_TEMPERATURE)
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
            "definicion": [r"(qué|que) (es|son|significa|significan)", r"define|definir|definición"],
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
                return retriever.get_relevant_documents(query)
            elif self.fragmentos:
                import random
                return random.sample(self.fragmentos, min(5, len(self.fragmentos)))
        except Exception as e:
            logger.error(f"Error recuperando documentos: {e}")
        
        return []
    
    def generate_search_query(self, question, conversation_history):
        """Genera una consulta de búsqueda optimizada."""
        try:
            cadena_reescritura = LLMChain(llm=self.llm, prompt=plantilla_reescritura_pregunta)
            
            result = cadena_reescritura.invoke({
                "historial_chat": conversation_history, 
                "pregunta": question
            })
            
            return result['text'].strip()
        except Exception as e:
            logger.error(f"Error generando consulta de búsqueda: {e}")
            return question
    
    def process_question(self, pregunta_obj):
        """Procesa la pregunta principal usando el sistema completo."""
        question_text = pregunta_obj.texto
        
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

# NO crear instancia global automáticamente
# ai_system = AISystem()
ai_system = None

def get_ai_system():
    """Función para obtener la instancia del sistema IA"""
    global ai_system
    if ai_system is None:
        ai_system = AISystem()
    return ai_system
