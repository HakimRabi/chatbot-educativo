# ===== IMPORTS =====
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
import json
import uuid
from pydantic import BaseModel
from datetime import datetime

# Configurar logging primero
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("chatbot_app")

# Crear la aplicación FastAPI
app = FastAPI()

# Ruta para manejar redirecciones incorrectas de /pages/index.html
@app.get("/pages/index.html")
def serve_pages_index_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=301)

# Variable global para el sistema IA
ai_system_instance = None
ai_system_ready = False

# Configurar CORS con headers adicionales
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Processing-Time"]
)

# Montar archivos estáticos - CONFIGURACIÓN CORREGIDA
app.mount("/static", StaticFiles(directory="../frontend"), name="static")
app.mount("/assets", StaticFiles(directory="../frontend/assets"), name="assets")
app.mount("/pages", StaticFiles(directory="../frontend/pages"), name="pages")

# Configurar executor para tareas asíncronas
executor = ThreadPoolExecutor(max_workers=4)

# Ruta raíz - PRINCIPAL
@app.get("/")
def serve_index():
    return FileResponse("../frontend/index.html")

# Agregar ruta adicional para servir index.html directamente
@app.get("/index.html")
def serve_index_direct():
    return FileResponse("../frontend/index.html")

# Agregar ruta específica para el dashboard
@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("../frontend/pages/dashboard.html")

@app.get("/pages/dashboard")
def serve_dashboard_pages():
    return FileResponse("../frontend/pages/dashboard.html")

@app.on_event("startup")
async def startup_event():
    """Evento que se ejecuta al iniciar el servidor"""
    global ai_system_instance, ai_system_ready
    
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO CHATBOT EDUCATIVO")
    logger.info("=" * 60)
    
    # FIRST: Configure routes before anything else
    logger.info("🔧 Configurando rutas del sistema...")
    routes_success = setup_routes()
    if routes_success:
        logger.info("✅ Rutas configuradas exitosamente")
    else:
        logger.warning("⚠️ Problemas configurando algunas rutas")
    
    try:
        # Importar y crear instancia del sistema IA
        from ai_system import AISystem
        ai_system_instance = AISystem()
        
        # Inicializar el sistema de forma síncrona
        logger.info("🔄 Inicializando sistema de inteligencia artificial...")
        start_time = time.time()
        
        success = ai_system_instance.initialize_system()
        
        initialization_time = time.time() - start_time
        
        if success:
            ai_system_ready = True
            logger.info("=" * 60)
            logger.info(f"✅ SISTEMA LISTO EN {initialization_time:.2f} SEGUNDOS")
            logger.info(f"🧠 Modelo: {'ChromaDB' if ai_system_instance.using_chroma else 'FAISS' if ai_system_instance.using_vector_db else 'Solo LLM'}")
            logger.info(f"📚 Documentos: {len(ai_system_instance.documentos)}")
            logger.info(f"📄 Fragmentos: {len(ai_system_instance.fragmentos)}")
            logger.info("🌟 El chatbot está listo para recibir consultas")
            logger.info("=" * 60)
        else:
            logger.error("❌ Error en la inicialización del sistema IA")
            logger.info("🔄 Continuando con sistema básico...")
            ai_system_ready = False
            
    except Exception as e:
        logger.error(f"❌ Error crítico en startup: {e}")
        logger.info("🔄 Continuando sin sistema IA avanzado...")
        ai_system_ready = False

# Modelos básicos
class Pregunta(BaseModel):
    texto: str
    userId: str = None
    chatToken: str = None
    history: list = None

class SessionIn(BaseModel):
    user_id: str
    session_id: str
    history: list

class SolicitudSugerencias(BaseModel):
    userId: str = None
    chatToken: str = None
    history: list = None

class FeedbackIn(BaseModel):
    user_id: str
    session_id: str
    pregunta: str
    respuesta: str
    rating: int
    comentario: str = None

# Función para generar respuestas básicas
def generar_respuesta_rapida(pregunta_texto):
    """Genera respuestas básicas rápidas cuando el sistema IA está sobrecargado"""
    pregunta_lower = pregunta_texto.lower()
    
    # Respuestas rápidas para patrones comunes
    if any(saludo in pregunta_lower for saludo in ["hola", "mi nombre es", "me llamo", "soy"]):
        return "¡Hola! Un gusto conocerte. Soy tu asistente virtual especializado en Fundamentos de Inteligencia Artificial. ¿En qué puedo ayudarte hoy?"
    
    if "inteligencia artificial" in pregunta_lower and any(q in pregunta_lower for q in ["qué es", "que es", "define"]):
        return "La Inteligencia Artificial es un campo de la informática que busca crear sistemas capaces de realizar tareas que normalmente requieren inteligencia humana, como el aprendizaje, razonamiento y toma de decisiones."
    
    if "machine learning" in pregunta_lower or "aprendizaje automático" in pregunta_lower:
        return "Machine Learning es una rama de la IA que permite a las máquinas aprender patrones de los datos sin ser programadas explícitamente para cada tarea específica."
    
    # Respuesta genérica pero útil
    return f"He recibido tu pregunta sobre '{pregunta_texto}'. Te puedo ayudar con conceptos de inteligencia artificial, algoritmos, historia de la IA, machine learning y más. ¿Hay algo específico que te gustaría saber?"

# Función para guardar historial de forma segura
def save_to_history_safe(user_id, chat_token, pregunta, respuesta):
    """Guarda la interacción en el historial de forma segura y rápida"""
    try:
        from models import engine
        from sqlalchemy import text
        
        # Limitar la longitud de pregunta y respuesta para evitar problemas de BD
        pregunta_truncated = pregunta[:500] if len(pregunta) > 500 else pregunta
        respuesta_truncated = respuesta[:2000] if len(respuesta) > 2000 else respuesta
        
        # Crear entradas de historial
        history_entries = [
            {"sender": "user", "text": pregunta_truncated, "timestamp": datetime.now().isoformat()},
            {"sender": "bot", "text": respuesta_truncated, "timestamp": datetime.now().isoformat()}
        ]
        
        with engine.connect() as connection:
            # Verificar si existe la sesión
            existing = connection.execute(
                text("SELECT history FROM chat_sessions WHERE user_id = :user_id AND session_id = :session_id"),
                {"user_id": user_id, "session_id": chat_token}
            ).fetchone()
            
            if existing:
                # Actualizar historial existente
                current_history = []
                if existing[0]:
                    try:
                        if isinstance(existing[0], str):
                            current_history = json.loads(existing[0])
                        elif isinstance(existing[0], (list, dict)):
                            current_history = existing[0] if isinstance(existing[0], list) else [existing[0]]
                        else:
                            current_history = []
                    except json.JSONDecodeError:
                        logger.warning("Error decodificando JSON del historial, creando nuevo historial")
                        current_history = []
                
                current_history.extend(history_entries)
                
                # Limitar el historial a los últimos 50 mensajes para evitar que crezca demasiado
                if len(current_history) > 50:
                    current_history = current_history[-50:]
                
                connection.execute(
                    text("UPDATE chat_sessions SET history = :history WHERE user_id = :user_id AND session_id = :session_id"),
                    {"user_id": user_id, "session_id": chat_token, "history": json.dumps(current_history)}
                )
            else:
                # Crear nueva sesión
                connection.execute(
                    text("INSERT INTO chat_sessions (user_id, session_id, history) VALUES (:user_id, :session_id, :history)"),
                    {"user_id": user_id, "session_id": chat_token, "history": json.dumps(history_entries)}
                )
            
            connection.commit()
            logger.debug(f"Historial guardado para usuario {user_id}, sesión {chat_token}")
            
    except Exception as e:
        logger.warning(f"No se pudo guardar historial: {e}")

async def save_to_history_async(user_id, chat_token, pregunta, respuesta):
    """Versión asíncrona del guardado de historial"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, save_to_history_safe, user_id, chat_token, pregunta, respuesta)
    except Exception as e:
        logger.warning(f"Error en guardado asíncrono de historial: {e}")

async def save_to_history_safe_silent(user_id, chat_token, pregunta, respuesta):
    """Versión silenciosa del guardado de historial que nunca falla"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, lambda: save_to_history_safe(user_id, chat_token, pregunta, respuesta))
    except:
        pass  # Ignorar todos los errores

# Endpoint de verificación de conexión básica
@app.get("/check_connection")
async def check_connection():
    try:
        from models import check_db_connection
        return {"connected": check_db_connection()}
    except:
        return {"connected": False}

# Endpoint básico de preguntas
@app.post("/preguntar")
async def preguntar_basic(pregunta: Pregunta):
    try:
        start_time = time.time()
        respuesta = None
        
        # Verificar si el sistema IA está listo
        if ai_system_ready and ai_system_instance:
            try:
                logger.info(f"Procesando pregunta con IA: {pregunta.texto}")
                
                # Ejecutar procesamiento de pregunta
                loop = asyncio.get_event_loop()
                respuesta = await loop.run_in_executor(executor, ai_system_instance.process_question, pregunta)
                
                processing_time = time.time() - start_time
                logger.info(f"Respuesta IA generada en {processing_time:.2f}s")
                    
            except Exception as ai_error:
                logger.error(f"Error en sistema IA: {ai_error}")
                respuesta = None
        else:
            logger.info("Sistema IA no disponible, usando respuesta básica")
        
        # Si no hay respuesta del sistema IA, usar respuesta básica
        if not respuesta:
            respuesta = generar_respuesta_rapida(pregunta.texto)
            logger.info("Usando respuesta básica")
        
        # Validar que la respuesta no esté vacía
        if not respuesta or respuesta.strip() == "":
            respuesta = "Lo siento, no pude generar una respuesta adecuada. ¿Podrías reformular tu pregunta?"
        
        # Intentar guardar historial sin que falle la respuesta
        if pregunta.userId and pregunta.chatToken:
            try:
                asyncio.create_task(save_to_history_safe_silent(pregunta.userId, pregunta.chatToken, pregunta.texto, respuesta))
            except:
                pass  # Ignorar errores de historial completamente
        
        total_time = time.time() - start_time
        logger.info(f"Respuesta enviada: {len(respuesta)} caracteres en {total_time:.2f}s")
        
        return {"respuesta": respuesta, "status": "success"}
        
    except Exception as e:
        logger.error(f"Error en preguntar_basic: {e}")
        return {"respuesta": "Lo siento, ocurrió un error inesperado. Por favor, inténtalo de nuevo.", "status": "error"}

@app.get("/ai_status")
async def get_ai_status():
    """Endpoint para verificar el estado del sistema IA"""
    global ai_system_ready, ai_system_instance
    
    try:
        if ai_system_ready and ai_system_instance:
            return {
                "success": True,
                "ready": True,
                "message": "Sistema IA listo y operativo",
                "details": {
                    "using_chroma": ai_system_instance.using_chroma,
                    "using_vector_db": ai_system_instance.using_vector_db,
                    "documentos_count": len(ai_system_instance.documentos),
                    "fragmentos_count": len(ai_system_instance.fragmentos),
                    "llm_available": ai_system_instance.llm is not None
                }
            }
        else:
            return {
                "success": True,
                "ready": False,
                "message": "Sistema IA no disponible - usando modo básico",
                "details": {}
            }
    except Exception as e:
        logger.error(f"Error obteniendo estado IA: {e}")
        return {
            "success": False,
            "ready": False,
            "message": f"Error: {str(e)}",
            "details": {}
        }

@app.get("/ai_diagnostics")
async def get_ai_diagnostics():
    """Endpoint para obtener diagnósticos detallados del sistema de IA"""
    global ai_system_instance
    
    try:
        if ai_system_instance and hasattr(ai_system_instance, 'get_error_diagnostics'):
            diagnostics = ai_system_instance.get_error_diagnostics()
            return {"success": True, "diagnostics": diagnostics}
        else:
            return {
                "success": False, 
                "message": "Sistema IA no disponible",
                "basic_info": get_ai_system_info()
            }
    except Exception as e:
        logger.error(f"Error obteniendo diagnósticos: {e}")
        return {
            "success": False, 
            "error": str(e),
            "basic_info": get_ai_system_info()
        }

# Endpoint optimizado para historial que no interfiera
@app.get("/chat/history")
def get_history_basic(user_id: str, session_id: str):
    try:
        from models import engine
        from sqlalchemy import text
        
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT history FROM chat_sessions WHERE user_id = :user_id AND session_id = :session_id"),
                {"user_id": user_id, "session_id": session_id}
            ).fetchone()
            
            if result and result[0]:
                if isinstance(result[0], (dict, list)):
                    return result[0]
                else:
                    return json.loads(result[0])
            return []
    except:
        # Devolver array vacío sin logging de error para evitar spam
        return []

# Otros endpoints básicos del chat
@app.post("/chat/history")
def save_history_basic(data: SessionIn):
    try:
        from models import engine
        from sqlalchemy import text
        
        history_json = json.dumps(data.history)
        
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM chat_sessions WHERE user_id = :user_id AND session_id = :session_id"),
                {"user_id": data.user_id, "session_id": data.session_id}
            ).fetchone()
            
            if exists:
                connection.execute(
                    text("UPDATE chat_sessions SET history = :history WHERE user_id = :user_id AND session_id = :session_id"),
                    {"user_id": data.user_id, "session_id": data.session_id, "history": history_json}
                )
            else:
                connection.execute(
                    text("INSERT INTO chat_sessions (user_id, session_id, history) VALUES (:user_id, :session_id, :history)"),
                    {"user_id": data.user_id, "session_id": data.session_id, "history": history_json}
                )
            
            connection.commit()
            return {"ok": True}
    except Exception as db_error:
        logger.warning(f"No se pudo guardar en BD: {db_error}")
        return {"ok": True}

@app.get("/chat/sessions")
def get_sessions_basic(user_id: str):
    try:
        from models import engine
        from sqlalchemy import text
        
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT session_id, updated_at as created_at FROM chat_sessions WHERE user_id = :user_id ORDER BY updated_at DESC"),
                {"user_id": user_id}
            ).fetchall()
            return [{"session_id": row[0], "created_at": row[1]} for row in result]
    except:
        return []

@app.get("/chat/message_ratings")
def get_ratings_basic(user_id: str, session_id: str):
    try:
        from models import engine
        from sqlalchemy import text
        
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
    except:
        return []

@app.delete("/chat/session")
def delete_session_basic(user_id: str, session_id: str):
    try:
        from models import SessionLocal, ChatSession
        
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
    except:
        return {"ok": True}

@app.post("/chat/feedback")
def save_feedback_basic(fb: FeedbackIn):
    try:
        from models import engine
        from sqlalchemy import text
        
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
    except:
        return {"ok": True}

# Rutas de autenticación básicas
@app.post("/auth/login")
async def login_basic(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
        
        try:
            from models import SessionLocal, User, pwd_context
            
            with SessionLocal() as db:
                user = db.query(User).filter(User.email == email).first()
                
                if not user:
                    return {"success": False, "message": "Credenciales incorrectas"}
                
                if not pwd_context.verify(password, user.password):
                    return {"success": False, "message": "Credenciales incorrectas"}
                
                # Asegurar que permisos tenga un valor por defecto
                permisos = user.permisos if user.permisos is not None else 'usuario'
                
                logger.info(f"Login exitoso en app.py: {email}, permisos: {permisos}")
                
                return {
                    "success": True,
                    "user": {
                        "id": user.id,
                        "nombre": user.nombre,
                        "email": user.email,
                        "permisos": permisos  # Agregar permisos aquí
                    }
                }
        except Exception as db_error:
            logger.warning(f"Error de BD en login: {db_error}")
            # Autenticación básica de prueba si no hay BD
            if email == "test@test.com" and password == "123456":
                return {
                    "success": True,
                    "user": {
                        "id": 5,
                        "nombre": "Usuario Test",
                        "email": "test@test.com",
                        "permisos": "usuario"  # Agregar permisos por defecto
                    }
                }
            else:
                return {"success": False, "message": "Credenciales incorrectas"}
            
    except Exception as e:
        logger.error(f"Error en login_basic: {e}")
        return {"success": False, "message": "Error en login"}

@app.post("/auth/register")
async def register_basic(request: Request):
    try:
        data = await request.json()
        nombre = data.get("nombre")
        email = data.get("email")
        password = data.get("password")
        
        if not all([nombre, email, password]):
            return {"success": False, "message": "Todos los campos son requeridos"}
        
        try:
            from models import SessionLocal, User, pwd_context
            from datetime import datetime
            
            with SessionLocal() as db:
                existing_user = db.query(User).filter(User.email == email).first()
                if existing_user:
                    return {"success": False, "message": "El email ya está registrado"}
                
                hashed_password = pwd_context.hash(password)
                new_user = User(
                    nombre=nombre,
                    email=email,
                    password=hashed_password,
                    permisos='usuario',  # Asignar permisos por defecto
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                
                return {
                    "success": True,
                    "message": "Usuario registrado exitosamente",
                    "user": {
                        "id": new_user.id,
                        "nombre": new_user.nombre,
                        "email": new_user.email,
                        "permisos": new_user.permisos or 'usuario'  # Incluir permisos
                    }
                }
        except Exception as db_error:
            logger.warning(f"Error de BD en registro: {db_error}")
            return {
                "success": True,
                "message": "Usuario registrado exitosamente (modo prueba)",
                "user": {
                    "id": 6,
                    "nombre": nombre,
                    "email": email,
                    "permisos": "usuario"  # Agregar permisos por defecto
                }
            }
            
    except Exception as e:
        logger.error(f"Error en register_basic: {e}")
        return {"success": False, "message": "Error en registro"}

# Endpoint básico de sugerencias
@app.post("/sugerencias")
def sugerencias_basic(solicitud: SolicitudSugerencias):
    try:
        return {
            "sugerencias": [
                "¿Qué es la inteligencia artificial?",
                "¿Cuáles son los algoritmos principales?",
                "¿Cómo funciona el machine learning?"
            ]
        }
    except Exception as e:
        logger.error(f"Error en sugerencias_basic: {e}")
        return {"error": "Error generando sugerencias"}

def setup_basic_routes():
    """Esta función ya no es necesaria porque las rutas están definidas arriba"""
    logger.info("Rutas básicas ya están configuradas")

# Función para configurar las rutas después de que todo esté cargado
def setup_routes():
    """Configura las rutas de la aplicación de forma diferida."""
    logger.info("🔧 STARTING route configuration process...")
    all_routes_configured_successfully = True

    # Configure Auth Router
    try:
        from auth import router as auth_router
        app.include_router(auth_router, prefix="/auth", tags=["auth"])
        logger.info("✅ Auth router configured and included successfully.")
    except ImportError as e:
        logger.error(f"❌ Failed to import auth_router: {e}")
        all_routes_configured_successfully = False
    except Exception as e:
        logger.error(f"❌ Error configuring auth_router: {e}")
        all_routes_configured_successfully = False

    # Configure Chat Router
    try:
        from chat import router as chat_router
        app.include_router(chat_router, prefix="/chat", tags=["chat"])
        logger.info("✅ Chat router configured and included successfully.")
        
        # Compatibility routes from chat module
        try:
            from chat import preguntar as chat_preguntar_func, generar_sugerencias as chat_sugerencias_func
            
            @app.post("/sugerencias_compat")
            def generar_sugerencias_compat(solicitud: SolicitudSugerencias):
                return chat_sugerencias_func(solicitud)
                
            @app.post("/preguntar_compat") 
            def preguntar_compat(pregunta_data: Pregunta):
                return chat_preguntar_func(pregunta_data)
            logger.info("✅ Chat compatibility routes configured.")
        except ImportError as chat_funcs_error:
            logger.warning(f"⚠️ Could not import chat functions for compatibility routes: {chat_funcs_error}")

    except ImportError as e:
        logger.error(f"❌ Failed to import chat_router: {e}")
        all_routes_configured_successfully = False
    except Exception as e:
        logger.error(f"❌ Error configuring chat_router: {e}")
        all_routes_configured_successfully = False

    # Configure Dashboard Router - ENHANCED CRITICAL SECTION
    dashboard_success = False
    try:
        logger.info("🔧 Attempting to import dashboard router...")
        
        # Force fresh import of dashboard module
        import importlib
        import sys
        if 'dashboard' in sys.modules:
            importlib.reload(sys.modules['dashboard'])
        
        from dashboard import router as dashboard_router
        logger.info(f"✅ Successfully imported dashboard_router: {type(dashboard_router)}")
        
        # Detailed inspection of dashboard router
        if dashboard_router is None:
            logger.error("❌ CRITICAL: dashboard_router is None after import!")
            raise ImportError("dashboard_router is None")
        
        if not hasattr(dashboard_router, 'routes'):
            logger.error("❌ CRITICAL: dashboard_router missing 'routes' attribute!")
            raise ImportError("dashboard_router missing routes")
        
        routes_count = len(dashboard_router.routes)
        logger.info(f"📊 Dashboard router contains {routes_count} routes")
        
        if routes_count == 0:
            logger.error("❌ CRITICAL: Dashboard router has 0 routes!")
            raise ImportError("Dashboard router has no routes")
        
        # Log each route in detail
        for idx, route in enumerate(dashboard_router.routes):
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = ', '.join(route.methods)
                logger.info(f"  📋 Route [{idx}]: {methods} {route.path}")
            else:
                logger.info(f"  📋 Route [{idx}]: {type(route)} - path: {getattr(route, 'path', 'MISSING')}")
        
        # Include dashboard router with enhanced logging
        logger.info("🔧 Including dashboard router in main FastAPI app...")
        
        # Count routes before inclusion
        routes_before = len(app.routes)
        dashboard_routes_before = len([r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/dashboard')])
        
        logger.info(f"📊 App routes before dashboard inclusion: {routes_before} (dashboard: {dashboard_routes_before})")
        
        # Include the router
        app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
        
        # Count routes after inclusion
        routes_after = len(app.routes)
        dashboard_routes_after = len([r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/dashboard')])
        
        logger.info(f"📊 App routes after dashboard inclusion: {routes_after} (dashboard: {dashboard_routes_after})")
        logger.info(f"📊 Routes added: {routes_after - routes_before}")
        
        if dashboard_routes_after == 0:
            logger.error("❌ CRITICAL: No dashboard routes found on app after inclusion!")
            raise Exception("Dashboard routes not registered on app")
        elif dashboard_routes_after != routes_count:
            logger.warning(f"⚠️ Route count mismatch: expected {routes_count}, got {dashboard_routes_after}")
        else:
            logger.info("✅ Dashboard routes successfully registered!")
            dashboard_success = True
        
        # Verify specific routes exist
        dashboard_routes = [r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/dashboard')]
        for route in dashboard_routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                methods = ', '.join(route.methods)
                logger.info(f"  ✅ VERIFIED: {methods} {route.path}")
        
        if not dashboard_success:
            logger.error("❌ Dashboard router inclusion verification failed")
            all_routes_configured_successfully = False
        
    except ImportError as e:
        logger.error(f"❌ FAILED to import dashboard module: {e}")
        all_routes_configured_successfully = False
        # Try fallback manual route registration
        logger.info("🔧 Attempting fallback dashboard route registration...")
        try:
            register_dashboard_routes_fallback()
            logger.info("✅ Fallback dashboard routes registered")
        except Exception as fallback_error:
            logger.error(f"❌ Fallback route registration failed: {fallback_error}")
            
    except Exception as e:
        logger.error(f"❌ Unexpected error configuring dashboard: {e}", exc_info=True)
        all_routes_configured_successfully = False

    # Final comprehensive verification
    total_routes = len(app.routes)
    dashboard_final_count = len([r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/dashboard')])
    auth_routes = len([r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/auth')])
    chat_routes = len([r for r in app.routes if hasattr(r, 'path') and r.path.startswith('/chat')])
    
    logger.info("=" * 50)
    logger.info("📋 FINAL ROUTE CONFIGURATION SUMMARY:")
    logger.info(f"  📊 Total routes: {total_routes}")
    logger.info(f"  🔐 Auth routes: {auth_routes}")
    logger.info(f"  💬 Chat routes: {chat_routes}")
    logger.info(f"  📊 Dashboard routes: {dashboard_final_count}")
    logger.info("=" * 50)
    
    if all_routes_configured_successfully and dashboard_final_count > 0:
        logger.info("✅ Route configuration completed successfully!")
    else:
        logger.warning("⚠️ Route configuration completed with issues!")
        
    return all_routes_configured_successfully

def register_dashboard_routes_fallback():
    """Fallback function to manually register dashboard routes if router inclusion fails"""
    logger.info("🔧 Registering dashboard routes manually as fallback...")
    
    # Import dashboard functions directly
    try:
        from dashboard import (
            get_dashboard_stats, get_user_sessions_stats, get_feedback_analysis,
            get_dashboard_users, get_system_health, get_dashboard_analytics,
            check_dashboard_access
        )
        
        # Register routes manually
        app.add_api_route("/dashboard/stats", get_dashboard_stats, methods=["GET"], tags=["dashboard"])
        app.add_api_route("/dashboard/user-sessions", get_user_sessions_stats, methods=["GET"], tags=["dashboard"])
        app.add_api_route("/dashboard/feedback-analysis", get_feedback_analysis, methods=["GET"], tags=["dashboard"])
        app.add_api_route("/dashboard/users", get_dashboard_users, methods=["GET"], tags=["dashboard"])
        app.add_api_route("/dashboard/system-health", get_system_health, methods=["GET"], tags=["dashboard"])
        app.add_api_route("/dashboard/analytics", get_dashboard_analytics, methods=["GET"], tags=["dashboard"])
        app.add_api_route("/dashboard/check-access", check_dashboard_access, methods=["GET"], tags=["dashboard"])
        
        logger.info("✅ Fallback dashboard routes registered successfully")
        
    except ImportError as e:
        logger.error(f"❌ Failed to import dashboard functions for fallback: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to register fallback dashboard routes: {e}")
        raise

# Función para obtener información del sistema IA
def get_ai_system_info():
    """Obtiene información del sistema de IA de forma segura"""
    global ai_system_instance
    
    try:
        if ai_system_instance:
            return {
                "using_chroma": getattr(ai_system_instance, 'using_chroma', False),
                "using_vector_db": getattr(ai_system_instance, 'using_vector_db', False),
                "documentos_count": len(getattr(ai_system_instance, 'documentos', [])),
                "fragmentos_count": len(getattr(ai_system_instance, 'fragmentos', [])),
                "llm_available": getattr(ai_system_instance, 'llm', None) is not None,
                "cadena_available": getattr(ai_system_instance, 'cadena', None) is not None,
                "is_ready": ai_system_ready
            }
        else:
            return {
                "using_chroma": False,
                "using_vector_db": False,
                "documentos_count": 0,
                "fragmentos_count": 0,
                "llm_available": False,
                "cadena_available": False,
                "is_ready": False
            }
    except Exception as e:
        logger.error(f"Error obteniendo info del sistema IA: {e}")
        return {
            "using_chroma": False,
            "using_vector_db": False,
            "documentos_count": 0,
            "fragmentos_count": 0,
            "llm_available": False,
            "cadena_available": False,
            "is_ready": False
        }

# Inicialización del servidor
if __name__ == "__main__":
    import uvicorn
    
    # Agregar una ruta catch-all para manejar cualquier ruta no encontrada
    @app.get("/{full_path:path}")
    def catch_all(full_path: str):
        # Si la ruta contiene 'index.html' o termina en '/', servir el index principal
        if 'index.html' in full_path or full_path.endswith('/') or full_path == '':
            return FileResponse("../frontend/index.html")
        # De lo contrario, devolver 404
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
    
    print("=" * 60)
    print("🚀 CHATBOT EDUCATIVO - SERVIDOR FASTAPI")
    print("=" * 60)
    print("📋 Configurando rutas...")
    
    # Configurar rutas
    routes_configured = setup_routes()
    
    if routes_configured:
        print("✅ Rutas configuradas correctamente")
        print("📑 Rutas disponibles:")
        dashboard_count = 0
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                methods = ', '.join(route.methods)
                print(f"  {methods}: {route.path}")
                if route.path.startswith('/dashboard'):
                    dashboard_count += 1
        
        print(f"📊 Total de rutas del dashboard registradas: {dashboard_count}")
        
        if dashboard_count == 0:
            print("⚠️ No se encontraron rutas del dashboard registradas")
            print("🔄 Intentando importar dashboard manualmente...")
            try:
                import dashboard
                print("✅ Dashboard importado exitosamente")
            except Exception as e:
                print(f"❌ Error importando dashboard: {e}")
        else:
            print("✅ Dashboard endpoints loaded successfully")
    else:
        print("⚠️ Algunas rutas no se pudieron configurar")
    
    print("=" * 60)
    print("🔄 El sistema de IA se inicializará durante el startup del servidor")
    print("⏳ Esto puede tomar 30-60 segundos en el primer arranque")
    print("=" * 60)
    
    # Iniciar servidor
    try:
        print("🚀 Iniciando servidor en http://127.0.0.1:8000")
        print("=" * 60)
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"Error iniciando servidor: {e}")
        print(f"❌ Error iniciando servidor: {e}")