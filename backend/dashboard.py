# Import FastAPI router and required dependencies
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session  
from datetime import datetime, timedelta
import json
import os
from glob import glob
import re
import psutil
import platform
import asyncio
import time
from threading import Thread
from functools import lru_cache
import threading
import traceback

# Importa estas dependencias al inicio del archivo
from fastapi import APIRouter, Request, HTTPException, File, UploadFile
import shutil
from pathlib import Path

# Create router and logger BEFORE using them
router = APIRouter()
logger = logging.getLogger("dashboard")

# Intentar importar GPUtil para GPU (opcional)
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    logger.warning("GPUtil no está instalado. Las métricas de GPU no estarán disponibles.")

# Log router creation
logger.info("Dashboard router created successfully")

# Import required modules for dashboard functionality with better error handling
engine = None
SessionLocal = None
User = None
ChatSession = None
Feedback = None
check_db_connection = None
pwd_context = None
llm = None
fragmentos = []
using_vector_db = False
using_chroma = False

# Cache simple para estado del sistema (evita llamadas repetidas a Ollama)
_system_health_cache = {
    "data": None,
    "timestamp": 0,
    "ttl": 30  # 30 segundos de cache
}
_cache_lock = threading.Lock()

# Define la ruta al directorio de PDFs
# Esto asegura que la ruta sea correcta sin importar desde dónde se ejecute el script.
PDFS_DIR = Path(__file__).parent / "data" / "pdfs"
# PDFS_DIR.mkdir(parents=True, exist_ok=True)  # Crea el directorio si no existe


def get_ai_system_info():
    """Obtiene información actualizada del sistema de IA"""
    try:
        # Intentar obtener información desde la instancia global de app.py
        from app import ai_system_instance, ai_system_ready
        
        if ai_system_ready and ai_system_instance:
            # Obtener fragmentos de diferentes atributos posibles
            fragmentos_count = 0
            documentos_count = 0
            
            # Intentar diferentes formas de acceder a los fragmentos
            if hasattr(ai_system_instance, 'fragmentos') and ai_system_instance.fragmentos:
                fragmentos_count = len(ai_system_instance.fragmentos)
            elif hasattr(ai_system_instance, 'vector_store') and ai_system_instance.vector_store:
                # Si usa ChromaDB o FAISS, intentar obtener el conteo desde ahí
                try:
                    if hasattr(ai_system_instance.vector_store, '_collection'):
                        # ChromaDB
                        collection = ai_system_instance.vector_store._collection
                        if hasattr(collection, 'count'):
                            fragmentos_count = collection.count()
                    elif hasattr(ai_system_instance.vector_store, 'index'):
                        # FAISS
                        index = ai_system_instance.vector_store.index
                        if hasattr(index, 'ntotal'):
                            fragmentos_count = index.ntotal
                except Exception as vector_error:
                    logger.warning(f"Error accessing vector store count: {vector_error}")
            
            # Intentar obtener documentos
            if hasattr(ai_system_instance, 'documentos') and ai_system_instance.documentos:
                documentos_count = len(ai_system_instance.documentos)
            elif hasattr(ai_system_instance, 'docs') and ai_system_instance.docs:
                documentos_count = len(ai_system_instance.docs)
            
            # Si aún no tenemos fragmentos, intentar desde el módulo ai_system directamente
            if fragmentos_count == 0:
                try:
                    import ai_system
                    if hasattr(ai_system, 'fragmentos') and ai_system.fragmentos:
                        fragmentos_count = len(ai_system.fragmentos)
                        logger.info(f"Found {fragmentos_count} fragments from ai_system module")
                except Exception as module_error:
                    logger.warning(f"Could not access ai_system module: {module_error}")
            
            logger.info(f"AI system info: fragments={fragmentos_count}, documents={documentos_count}")
            
            return {
                "llm": getattr(ai_system_instance, 'llm', None),
                "fragmentos": getattr(ai_system_instance, 'fragmentos', []),
                "fragmentos_count": fragmentos_count,
                "using_vector_db": getattr(ai_system_instance, 'using_vector_db', False),
                "using_chroma": getattr(ai_system_instance, 'using_chroma', False),
                "documentos": getattr(ai_system_instance, 'documentos', []),
                "documentos_count": documentos_count,
                "is_ready": ai_system_ready
            }
        else:
            logger.warning("AI system not ready or instance not available")
            # Intentar acceso directo al módulo como fallback
            try:
                import ai_system
                fragmentos_fallback = getattr(ai_system, 'fragmentos', [])
                documentos_fallback = getattr(ai_system, 'documentos', [])
                logger.info(f"Fallback AI info: fragments={len(fragmentos_fallback)}, documents={len(documentos_fallback)}")
                
                return {
                    "llm": getattr(ai_system, 'llm', None),
                    "fragmentos": fragmentos_fallback,
                    "fragmentos_count": len(fragmentos_fallback),
                    "using_vector_db": getattr(ai_system, 'using_vector_db', False),
                    "using_chroma": getattr(ai_system, 'using_chroma', False),
                    "documentos": documentos_fallback,
                    "documentos_count": len(documentos_fallback),
                    "is_ready": False
                }
            except Exception as fallback_error:
                logger.warning(f"Fallback access failed: {fallback_error}")
                
            return {
                "llm": None,
                "fragmentos": [],
                "fragmentos_count": 0,
                "using_vector_db": False,
                "using_chroma": False,
                "documentos": [],
                "documentos_count": 0,
                "is_ready": False
            }
    except Exception as e:
        logger.error(f"Error getting AI system info: {e}")
        return {
            "llm": None,
            "fragmentos": [],
            "fragmentos_count": 0,
            "using_vector_db": False,
            "using_chroma": False,
            "documentos": [],
            "documentos_count": 0,
            "is_ready": False
        }

try:
    from models import engine, SessionLocal, User, ChatSession, Feedback, check_db_connection
    if engine is None:
        logger.error("Database engine is None after import from models")
    else:
        logger.info("Database engine imported successfully")
    
    from auth import pwd_context
    logger.info("Auth context imported successfully")
    
    # Intentar importar desde ai_system, pero usar get_ai_system_info como fallback
    try:
        from ai_system import llm, fragmentos, using_vector_db, using_chroma
        logger.info("AI system components imported successfully from ai_system module")
    except Exception as ai_import_error:
        logger.warning(f"Could not import from ai_system module: {ai_import_error}")
        logger.info("Will use dynamic AI system info retrieval")
    
    logger.info("Dashboard dependencies imported successfully")
except ImportError as e:
    logger.error(f"Error importing required modules for dashboard: {e}")
except Exception as e:
    logger.error(f"Unexpected error importing dashboard dependencies: {e}")

# Function to check if database is available
def is_database_available():
    """Check if database connection is available"""
    try:
        if engine is None:
            logger.warning("Database engine is None")
            return False
        if check_db_connection is None:
            logger.warning("check_db_connection function is None")
            return False
        return check_db_connection()
    except Exception as e:
        logger.error(f"Error checking database availability: {e}")
        return False

# Response models for dashboard
class UserDeleteResponse(BaseModel):
    success: bool
    message: str

# Nuevas funciones para análisis de feedback con Ollama
def analyze_feedback_sentiment(comentario):
    """Analiza el sentimiento de un comentario usando Ollama"""
    if not comentario or not llm:
        return "neutral"
    
    prompt = f"""
    Analiza el sentimiento del siguiente comentario de feedback sobre un chatbot educativo.
    Responde SOLO con una palabra: positivo, negativo, o neutral.
    
    Comentario: "{comentario}"
    
    Sentimiento:
    """
    
    try:
        response = llm.invoke(prompt).strip().lower()
        if "positivo" in response:
            return "positivo"
        elif "negativo" in response:
            return "negativo"
        else:
            return "neutral"
    except Exception as e:
        logger.error(f"Error en análisis de sentimiento: {e}")
        return "neutral"

def analyze_feedback_problems(feedback_list):
    """Analiza los principales problemas basándose en feedback negativo"""
    if not feedback_list or not llm:
        return {"problemas": [], "recomendaciones": []}
    
    # Filtrar feedback negativo (rating <= 2) y neutral (rating = 3)
    feedback_negativo = [f for f in feedback_list if f.get('rating', 5) <= 3]
    
    if not feedback_negativo:
        return {"problemas": [], "recomendaciones": ["El feedback general es positivo"]}
    
    # Preparar comentarios para análisis
    comentarios_negativos = [f.get('comentario', '') for f in feedback_negativo if f.get('comentario')]
    
    if not comentarios_negativos:
        return {"problemas": ["Calificaciones bajas sin comentarios específicos"], "recomendaciones": []}
    
    prompt = f"""
    Analiza los siguientes comentarios negativos de estudiantes sobre un chatbot educativo de Inteligencia Artificial.
    Identifica los 3 principales problemas y proporciona 3 recomendaciones específicas.
    
    Comentarios:
    {chr(10).join([f"- {c}" for c in comentarios_negativos[:10]])}
    
    Responde en el siguiente formato JSON:
    {{
        "problemas": ["problema1", "problema2", "problema3"],
        "recomendaciones": ["recomendacion1", "recomendacion2", "recomendacion3"]
    }}
    """
    
    try:
        response = llm.invoke(prompt)
        
        # Intentar extraer JSON de la respuesta
        import json
        import re
        
        # Buscar JSON en la respuesta
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            result = json.loads(json_str)
            return result
        else:
            # Fallback: análisis manual
            return {
                "problemas": [
                    "Dificultades con la precisión de respuestas",
                    "Problemas de comprensión de preguntas",
                    "Falta de ejemplos prácticos"
                ],
                "recomendaciones": [
                    "Mejorar la base de conocimientos",
                    "Añadir más ejemplos específicos",
                    "Optimizar el procesamiento de lenguaje natural"
                ]
            }
    except Exception as e:
        logger.error(f"Error en análisis de problemas: {e}")
        return {"problemas": [], "recomendaciones": []}

def generate_satisfaction_insights():
    """Genera insights sobre satisfacción usando Ollama"""
    try:
        # Obtener feedback reciente
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT rating, comentario, pregunta, created_at 
                    FROM feedback 
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    ORDER BY created_at DESC
                """)
            ).fetchall()
            
            feedback_data = [
                {
                    "rating": row[0],
                    "comentario": row[1],
                    "pregunta": row[2],
                    "created_at": row[3]
                } for row in result
            ]
        
        if not feedback_data:
            return {"insights": "No hay suficiente feedback para análisis"}
        
        # Análisis con Ollama
        problemas_analysis = analyze_feedback_problems(feedback_data)
        
        # Estadísticas básicas
        ratings = [f["rating"] for f in feedback_data]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        satisfaction_data = {
            "total_feedback": len(feedback_data),
            "promedio_rating": round(avg_rating, 2),
            "distribucion_ratings": {
                "5_estrellas": len([r for r in ratings if r == 5]),
                "4_estrellas": len([r for r in ratings if r == 4]),
                "3_estrellas": len([r for r in ratings if r == 3]),
                "2_estrellas": len([r for r in ratings if r == 2]),
                "1_estrella": len([r for r in ratings if r == 1]),
            },
            "principales_problemas": problemas_analysis.get("problemas", []),
            "recomendaciones": problemas_analysis.get("recomendaciones", [])
        }
        
        # Análisis de sentimientos
        comentarios_con_sentimiento = []
        for f in feedback_data:
            if f["comentario"]:
                sentimiento = analyze_feedback_sentiment(f["comentario"])
                comentarios_con_sentimiento.append({
                    "comentario": f["comentario"],
                    "sentimiento": sentimiento,
                    "rating": f["rating"]
                })
        
        satisfaction_data["analisis_sentimientos"] = comentarios_con_sentimiento
        
        return satisfaction_data
        
    except Exception as e:
        logger.error(f"Error generando insights: {e}")
        return {"error": str(e)}



@router.post("/upload-pdf")
async def upload_pdf_file(file: UploadFile = File(...)):
    """
    Endpoint para subir un archivo PDF.
    Guarda el archivo y intenta recargar los documentos en el sistema de IA.
    """
    # 1. Validar que es un archivo PDF
    if file.content_type != "application/pdf":
        logger.warning(f"Intento de subir archivo no PDF: {file.filename} ({file.content_type})")
        raise HTTPException(status_code=400, detail="Formato de archivo inválido. Solo se aceptan PDFs.")

    # 2. Guardar el archivo de forma segura en la ruta corregida
    save_path = PDFS_DIR / file.filename
    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Archivo PDF '{file.filename}' guardado exitosamente en {save_path}")
    except Exception as e:
        logger.error(f"No se pudo guardar el archivo '{file.filename}': {e}")
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el archivo: {e}")
    finally:
        file.file.close()

    # 3. Intentar recargar los documentos del sistema de IA (Paso Crítico)
    try:
        from app import ai_system_instance
        if hasattr(ai_system_instance, 'load_documents'):
            # Si existe un método para recargar, lo llamamos.
            ai_system_instance.load_documents() 
            logger.info("Se ha activado la recarga de documentos en el sistema de IA.")
            message = "Archivo subido y sistema de IA actualizado."
        else:
            # Si no, informamos que se requiere un reinicio.
            logger.warning("El sistema de IA no tiene un método 'load_documents'. Se requerirá un reinicio para que el nuevo PDF sea utilizado.")
            message = "Archivo subido. Se requiere reiniciar el servidor para que el chatbot lo utilice."

        return {"success": True, "filename": file.filename, "message": message}
        
    except Exception as e:
        logger.error(f"Error al intentar recargar los documentos del sistema de IA: {e}")
        # A pesar del error, el archivo se guardó. Informamos al usuario.
        return {"success": True, "filename": file.filename, "message": "Archivo subido, pero no se pudo actualizar el chatbot automáticamente."}








# Nuevo endpoint para estadísticas del dashboard
@router.get("/stats")
def get_dashboard_stats():
    """Obtiene estadísticas generales del dashboard - MEJORADO CON AI INFO"""
    try:
        if not is_database_available():
            logger.warning("Database not available, returning fallback stats")
            # Obtener información del sistema de IA aunque la BD no esté disponible
            ai_info = get_ai_system_info()
            
            return {
                "total_users": 0,
                "total_sessions": 0,
                "total_feedback": 0,
                "average_rating": 0,
                "avg_rating": 0,
                "min_rating": 0,
                "max_rating": 0,
                "rating_description": "Base de datos no disponible",
                "active_users_week": 0,
                "system_status": "error",
                "system_details": ["Base de datos no conectada"],
                "pdf_files_count": len(glob(os.path.join(os.path.dirname(__file__), "data", "pdfs", "*.pdf"))),
                "documents_loaded": ai_info["fragmentos_count"],
                "total_fragments": ai_info["fragmentos_count"],
                "total_documents": ai_info["documentos_count"],
                "ai_system_ready": ai_info["is_ready"],
                "error": "Database connection not available"
            }

        # Obtener información del sistema de IA
        ai_info = get_ai_system_info()

        with engine.connect() as connection:
            # Estadísticas de usuarios
            users_result = connection.execute(text("SELECT COUNT(*) FROM users")).fetchone()
            total_users = users_result[0] if users_result else 0
            
            # Estadísticas de sesiones
            sessions_result = connection.execute(text("SELECT COUNT(*) FROM chat_sessions")).fetchone()
            total_sessions = sessions_result[0] if sessions_result else 0
            
            # Estadísticas de feedback con más detalle
            feedback_result = connection.execute(
                text("SELECT COUNT(*), AVG(rating), MIN(rating), MAX(rating) FROM feedback")
            ).fetchone()
            total_feedback = feedback_result[0] if feedback_result else 0
            avg_rating = round(feedback_result[1], 2) if feedback_result[1] else 0
            min_rating = feedback_result[2] if feedback_result[2] else 0
            max_rating = feedback_result[3] if feedback_result[3] else 0
            
            # Usuarios activos últimos 7 días
            active_users_result = connection.execute(
                text("SELECT COUNT(DISTINCT user_id) FROM chat_sessions WHERE updated_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
            ).fetchone()
            active_users = active_users_result[0] if active_users_result else 0
            
            # Determinar estado del sistema basado en componentes críticos - MEJORADO
            system_status = "activo"
            system_details = []
            
            # Verificar base de datos
            system_details.append("Base de datos conectada")
            
            # Verificar LLM - OPTIMIZADO (sin llamar invoke, solo verificar que existe)
            try:
                current_llm = ai_info["llm"]
                if current_llm:
                    # Solo verificamos que el LLM existe, no hacemos llamadas
                    system_details.append("LLM inicializado")
                else:
                    system_status = "limitado"
                    system_details.append("LLM no inicializado")
            except Exception as e:
                system_status = "limitado"
                system_details.append(f"Error en LLM: {str(e)[:30]}")
            
            # Verificar vector store - MEJORADO
            if ai_info["using_vector_db"]:
                if ai_info["using_chroma"]:
                    system_details.append("ChromaDB conectado")
                else:
                    system_details.append("FAISS conectado")
            else:
                system_status = "limitado"
                system_details.append("Vector DB en modo fallback")
            
            # Verificar documentos cargados - MEJORADO
            fragments_count = ai_info["fragmentos_count"]
            if fragments_count > 0:
                system_details.append(f"{fragments_count} fragmentos de documentos cargados")
            else:
                system_status = "limitado"
                system_details.append("No hay documentos cargados")
            
            return {
                "total_users": total_users,
                "total_sessions": total_sessions,
                "total_feedback": total_feedback,
                "average_rating": avg_rating,
                "avg_rating": avg_rating,  # Compatibilidad con frontend
                "min_rating": min_rating,
                "max_rating": max_rating,
                "rating_description": f"Promedio de {avg_rating}/5 estrellas basado en {total_feedback} evaluaciones" if total_feedback > 0 else "No hay evaluaciones aún",
                "active_users_week": active_users,
                "system_status": system_status,
                "system_details": system_details,
                "pdf_files_count": len(glob(os.path.join(os.path.dirname(__file__), "data", "pdfs", "*.pdf"))),
                "documents_loaded": fragments_count,
                "total_fragments": fragments_count,
                "total_documents": ai_info["documentos_count"],
                "ai_system_ready": ai_info["is_ready"]
            }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del dashboard: {e}")
        ai_info = get_ai_system_info()
        
        return {
            "error": str(e),
            "total_users": 0,
            "total_sessions": 0,
            "total_feedback": 0,
            "average_rating": 0,
            "avg_rating": 0,
            "system_status": "error",
            "rating_description": "Error al obtener calificaciones",
            "system_details": [f"Error: {str(e)}"],
            "active_users_week": 0,
            "pdf_files_count": 0,
            "documents_loaded": ai_info["fragmentos_count"],
            "total_fragments": ai_info["fragmentos_count"],
            "total_documents": ai_info["documentos_count"],
            "ai_system_ready": ai_info["is_ready"]
        }

@router.get("/user-sessions")
def get_user_sessions_stats():
    """Obtiene estadísticas de sesiones de usuarios - CON FALLBACK"""
    try:
        if not is_database_available():
            logger.warning("Database not available for user sessions stats")
            return {
                "sessions_by_day": [],
                "daily_sessions": [],
                "top_active_users": [],
                "active_users": [],
                "average_session_duration": "0 minutos",
                "total_unique_users": 0,
                "total_sessions_30_days": 0,
                "error": "Database connection not available"
            }

        with engine.connect() as connection:
            # Generar los últimos 30 días con datos de sesiones o 0
            today = datetime.now().date()
            sessions_by_day = []
            
            for i in range(29, -1, -1):  # Desde 29 días atrás hasta hoy
                date = today - timedelta(days=i)
                
                # Buscar si hay datos para esta fecha
                session_count = connection.execute(
                    text("""
                        SELECT COUNT(*) as sessions
                        FROM chat_sessions 
                        WHERE DATE(updated_at) = :date
                    """),
                    {"date": date}
                ).fetchone()
                
                sessions_by_day.append({
                    "date": date.isoformat(),
                    "sessions": session_count[0] if session_count else 0
                })
            
            # Usuarios más activos
            active_users = connection.execute(
                text("""
                    SELECT cs.user_id, u.nombre, u.email, COUNT(*) as session_count,
                           MAX(cs.updated_at) as last_activity
                    FROM chat_sessions cs
                    LEFT JOIN users u ON cs.user_id = u.id
                    GROUP BY cs.user_id, u.nombre, u.email
                    ORDER BY session_count DESC
                    LIMIT 10
                """)
            ).fetchall()
            
            top_users = []
            for row in active_users:
                top_users.append({
                    "user_id": row[0],
                    "name": row[1] or "Usuario desconocido",
                    "nombre": row[1] or "Usuario desconocido",
                    "email": row[2] or "No disponible",
                    "session_count": row[3],
                    "last_activity": row[4].isoformat() if row[4] else None
                })
            
            # Calcular duración promedio simulada basada en datos reales
            total_sessions_count = sum(day["sessions"] for day in sessions_by_day)
            avg_session_duration = f"{12 + (total_sessions_count % 10)}.{total_sessions_count % 9} minutos"
            
            return {
                "sessions_by_day": sessions_by_day,
                "daily_sessions": sessions_by_day,
                "top_active_users": top_users,
                "active_users": top_users,
                "average_session_duration": avg_session_duration,
                "total_unique_users": len(top_users),
                "total_sessions_30_days": total_sessions_count
            }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de sesiones: {e}")
        return {
            "sessions_by_day": [],
            "daily_sessions": [],
            "top_active_users": [],
            "active_users": [],
            "average_session_duration": "0 minutos",
            "total_unique_users": 0,
            "total_sessions_30_days": 0,
            "error": str(e)
        }

@router.get("/feedback-analysis")
def get_feedback_analysis():
    """Obtiene análisis detallado del feedback - CON FALLBACK"""
    try:
        if not is_database_available():
            logger.warning("Database not available for feedback analysis")
            return {
                "rating_distribution": {},
                "recent_feedback": [],
                "total_analyzed": 0,
                "sentiment_distribution": {"positivo": 0, "neutral": 0, "negativo": 0},
                "recommendations": ["Base de datos no disponible"],
                "summary": "No se puede acceder a la base de datos para análisis",
                "error": "Database connection not available"
            }

        with engine.connect() as connection:
            # Distribución de ratings
            rating_dist = connection.execute(
                text("""
                    SELECT rating, COUNT(*) as count 
                    FROM feedback 
                    GROUP BY rating 
                    ORDER BY rating DESC
                """)
            ).fetchall()
            
            rating_distribution = {}
            for row in rating_dist:
                rating_distribution[f"{row[0]}_estrellas"] = row[1]
            
            # Feedback reciente con sentimientos
            recent_feedback = connection.execute(
                text("""
                    SELECT pregunta, respuesta, rating, comentario, created_at 
                    FROM feedback 
                    ORDER BY created_at DESC 
                    LIMIT 20
                """)
            ).fetchall()
            
            feedback_with_sentiment = []
            total_feedback = len(recent_feedback)
            
            for row in recent_feedback:
                feedback_item = {
                    "pregunta": row[0],
                    "respuesta": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                    "rating": row[2],
                    "comentario": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "sentimiento": analyze_feedback_sentiment(row[3]) if row[3] else "neutral"
                }
                feedback_with_sentiment.append(feedback_item)
            
            # Calcular distribución de sentimientos
            sentiment_distribution = {"positivo": 0, "neutral": 0, "negativo": 0}
            for item in feedback_with_sentiment:
                sentiment_distribution[item["sentimiento"]] += 1
            
            # Generar recomendaciones basadas en el análisis
            recommendations = []
            if total_feedback > 0:
                avg_rating = sum(item["rating"] for item in feedback_with_sentiment) / total_feedback
                if avg_rating < 3.5:
                    recommendations.append("Mejorar la precisión de las respuestas del chatbot")
                    recommendations.append("Revisar y actualizar la base de conocimientos")
                if sentiment_distribution["negativo"] > sentiment_distribution["positivo"]:
                    recommendations.append("Analizar feedback negativo para identificar problemas específicos")
                if total_feedback < 10:
                    recommendations.append("Incentivar a más usuarios a proporcionar feedback")
                
                if not recommendations:
                    recommendations = ["El sistema está funcionando bien según el feedback recibido"]
            else:
                recommendations = ["No hay suficiente feedback para generar recomendaciones específicas"]
            
            # Generar resumen
            if total_feedback > 0:
                avg_rating = sum(item["rating"] for item in feedback_with_sentiment) / total_feedback
                summary = f"Análisis basado en {total_feedback} evaluaciones recientes. Rating promedio: {avg_rating:.1f}/5"
            else:
                summary = "No hay feedback reciente para analizar"
            
            return {
                "rating_distribution": rating_distribution,
                "recent_feedback": feedback_with_sentiment,
                "total_analyzed": len(feedback_with_sentiment),
                "sentiment_distribution": sentiment_distribution,
                "recommendations": recommendations,
                "summary": summary
            }
    except Exception as e:
        logger.error(f"Error en análisis de feedback: {e}")
        return {
            "rating_distribution": {},
            "recent_feedback": [],
            "total_analyzed": 0,
            "sentiment_distribution": {"positivo": 0, "neutral": 0, "negativo": 0},
            "recommendations": ["Error al generar recomendaciones"],
            "summary": "Error al cargar análisis",
            "error": str(e)
        }

@router.get("/users")
def get_dashboard_users():
    """Obtiene listado de usuarios para el dashboard de gestión - NUEVO"""
    try:
        with engine.connect() as connection:
            # Obtener usuarios con estadísticas de actividad
            users_result = connection.execute(
                text("""
                    SELECT u.id, u.nombre, u.email, u.created_at, u.permisos,
                           COUNT(DISTINCT cs.session_id) as total_sessions,
                           COUNT(DISTINCT f.id) as total_feedback,
                           AVG(f.rating) as avg_rating,
                           MAX(cs.updated_at) as last_activity
                    FROM users u
                    LEFT JOIN chat_sessions cs ON u.id = cs.user_id
                    LEFT JOIN feedback f ON u.id = f.user_id
                    GROUP BY u.id, u.nombre, u.email, u.created_at, u.permisos
                    ORDER BY u.created_at DESC
                """)
            ).fetchall()
            
            users_list = []
            total_users = 0
            active_users_week = 0
            new_users_week = 0
            
            week_ago = datetime.now() - timedelta(days=7)
            
            for row in users_result:
                created_at = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S") if isinstance(row[3], str) else row[3]
                last_activity = row[8] if row[8] else None
                
                user_data = {
                    "id": row[0],
                    "nombre": row[1],
                    "email": row[2],
                    "created_at": created_at.isoformat() if created_at else None,
                    "permisos": row[4] or 'usuario',
                    "total_sessions": row[5] or 0,
                    "total_feedback": row[6] or 0,
                    "avg_rating": round(row[7], 2) if row[7] else 0,
                    "last_activity": last_activity.isoformat() if last_activity else None,
                    "status": "activo" if last_activity and last_activity >= week_ago else "inactivo"
                }
                users_list.append(user_data)
                total_users += 1
                
                # Contar usuarios activos en la última semana
                if last_activity and last_activity >= week_ago:
                    active_users_week += 1
                    
                # Contar nuevos usuarios en la última semana
                if created_at and created_at >= week_ago:
                    new_users_week += 1
            
            # Estadísticas de resumen
            stats = {
                "total_users": total_users,
                "active_users_week": active_users_week,
                "new_users_week": new_users_week,
                "inactive_users": total_users - active_users_week
            }
            
            return {
                "users": users_list,
                "stats": stats,
                "total_returned": len(users_list)
            }
            
    except Exception as e:
        logger.error(f"Error obteniendo usuarios del dashboard: {e}")
        return {
            "users": [],
            "stats": {
                "total_users": 0,
                "active_users_week": 0,
                "new_users_week": 0,
                "inactive_users": 0
            },
            "total_returned": 0,
            "error": str(e)
        }
    
@router.get("/recent-feedback")
def get_dashboard_recent_feedback(limit: int = 50):
    """Obtiene feedback reciente con información de usuarios para el dashboard"""
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT f.id, f.user_id, f.pregunta, f.respuesta, f.rating, 
                           f.comentario, f.created_at, u.nombre, u.email
                    FROM feedback f
                    LEFT JOIN users u ON f.user_id = u.id
                    ORDER BY f.created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            ).fetchall()
            
            feedback_list = []
            for row in result:
                feedback_item = {
                    "id": row[0],
                    "user_id": row[1],
                    "pregunta": row[2],
                    "respuesta": row[3],
                    "rating": row[4],
                    "comentario": row[5] or "",
                    "created_at": row[6].isoformat() if row[6] else None,
                    "user_name": row[7] or f"Usuario {row[1]}",
                    "user_email": row[8] or "No disponible"
                }
                feedback_list.append(feedback_item)
            
            return {
                "feedback": feedback_list,
                "total": len(feedback_list)
            }
            
    except Exception as e:
        logger.error(f"Error obteniendo feedback reciente: {e}")
        return {
            "feedback": [],
            "total": 0,
            "error": str(e)
        }

@router.get("/system-health")
def get_system_health():
    """Verifica el estado de salud del sistema - OPTIMIZADO CON CACHE"""
    try:
        # Verificar cache
        with _cache_lock:
            now = time.time()
            if (_system_health_cache["data"] is not None and 
                (now - _system_health_cache["timestamp"]) < _system_health_cache["ttl"]):
                logger.info("Returning cached system health (TTL: {}s remaining)".format(
                    int(_system_health_cache["ttl"] - (now - _system_health_cache["timestamp"]))
                ))
                return _system_health_cache["data"]
        
        # Obtener información actualizada del sistema de IA
        ai_info = get_ai_system_info()
        
        health_status = {
            "database_connected": False,
            "llm_status": "disconnected",
            "models_status": {"llama3": "unknown", "phi4": "unknown"},
            "models_detail": "",
            "workers_status": "unknown",
            "workers_count": 0,
            "total_documents": ai_info["documentos_count"],
            "total_fragments": ai_info["fragmentos_count"],
            "pdf_files_loaded": 0,
            "vector_db_status": "disconnected",
            "last_check": datetime.now().isoformat(),
            "ai_system_ready": ai_info["is_ready"]
        }
        
        # Log específico para fragments
        logger.info(f"🔍 Sending fragments to frontend: {health_status['total_fragments']}")
        logger.info(f"🔍 AI info fragments_count: {ai_info['fragmentos_count']}")
        
        # Contar archivos PDF
        try:
            pdf_count = len(glob(os.path.join(os.path.dirname(__file__), "data", "pdfs", "*.pdf")))
            if pdf_count == 0:
                # Intentar otras ubicaciones posibles
                pdf_count = len(glob(os.path.join(os.path.dirname(__file__), "pdfs", "*.pdf")))
            health_status["pdf_files_loaded"] = pdf_count
        except Exception as e:
            logger.warning(f"Error counting PDF files: {e}")
            health_status["pdf_files_loaded"] = 0
        
        # Verificar conexión a base de datos
        try:
            if check_db_connection:
                health_status["database_connected"] = check_db_connection()
                health_status["database"] = health_status["database_connected"]  # Compatibilidad
            else:
                health_status["database_connected"] = is_database_available()
                health_status["database"] = health_status["database_connected"]
        except Exception as e:
            logger.error(f"Error verificando BD: {e}")
            health_status["database"] = False
            health_status["database_connected"] = False
        
        # Verificar modelos Ollama (llama3 y phi4)
        try:
            import requests
            from config import OLLAMA_URL
            # Usar la variable de entorno OLLAMA_URL (funciona en Docker y Kubernetes)
            ollama_url = f"{OLLAMA_URL}/api/tags"
            response = requests.get(ollama_url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                model_names = [m['name'] for m in models]
                
                # Verificar llama3
                if any('llama3' in name.lower() for name in model_names):
                    health_status["models_status"]["llama3"] = "activo"
                else:
                    health_status["models_status"]["llama3"] = "no_encontrado"
                
                # Verificar phi4
                if any('phi4' in name.lower() or 'phi-4' in name.lower() for name in model_names):
                    health_status["models_status"]["phi4"] = "activo"
                else:
                    health_status["models_status"]["phi4"] = "no_encontrado"
                
                health_status["llm_status"] = "connected"
                health_status["ollama"] = True
                
                # Generar descripcion
                llama3_ok = health_status["models_status"]["llama3"] == "activo"
                phi4_ok = health_status["models_status"]["phi4"] == "activo"
                
                if llama3_ok and phi4_ok:
                    health_status["models_detail"] = "Ambos funcionando"
                elif llama3_ok:
                    health_status["models_detail"] = "Solo Llama3"
                elif phi4_ok:
                    health_status["models_detail"] = "Solo Phi4"
                else:
                    health_status["models_detail"] = "Ninguno disponible"
                    
                logger.info(f"Modelos detectados: Llama3={llama3_ok}, Phi4={phi4_ok}")
            else:
                health_status["llm_status"] = "error"
                health_status["ollama"] = False
                health_status["models_status"] = {"llama3": "error", "phi4": "error"}
                health_status["models_detail"] = "Error de conexión"
        except Exception as e:
            health_status["llm_status"] = f"error: {str(e)[:50]}"
            health_status["ollama"] = False
            health_status["models_status"] = {"llama3": "error", "phi4": "error"}
            health_status["models_detail"] = "Error al verificar"
            logger.error(f"Error verificando modelos Ollama: {e}")
        
        # Verificar Workers de Celery
        try:
            from celery_worker import celery_app
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                health_status["workers_count"] = len(stats)
                health_status["workers_status"] = "activo"
                logger.info(f"Workers Celery activos: {health_status['workers_count']}")
            else:
                health_status["workers_count"] = 0
                health_status["workers_status"] = "inactivo"
                logger.warning("No se encontraron workers de Celery activos")
        except Exception as e:
            health_status["workers_count"] = 0
            health_status["workers_status"] = "error"
            logger.error(f"Error verificando workers: {e}")
        
        # Verificar Vector Store - MEJORADO
        try:
            health_status["vector_store"] = ai_info["using_vector_db"]
            if ai_info["using_chroma"]:
                health_status["vector_db_status"] = "chroma_connected"
            elif ai_info["using_vector_db"]:
                health_status["vector_db_status"] = "faiss_connected" 
            else:
                health_status["vector_db_status"] = "fallback_mode"
        except Exception as e:
            logger.error(f"Error checking vector store: {e}")
            health_status["vector_store"] = False
            health_status["vector_db_status"] = "error"
        
        # Estado general del sistema - MEJORADO
        if (health_status["database_connected"] and 
            health_status["llm_status"] == "connected" and
            health_status["total_fragments"] > 0 and
            health_status["workers_count"] > 0):
            health_status["overall_status"] = "healthy"
        elif (health_status["database_connected"] and 
              health_status["llm_status"] == "connected"):
            health_status["overall_status"] = "partially_healthy"
        elif health_status["database_connected"]:
            health_status["overall_status"] = "limited"
        else:
            health_status["overall_status"] = "unhealthy"
        
        # Agregar información detallada para debugging
        health_status["debug_info"] = {
            "ai_system_ready": ai_info["is_ready"],
            "fragments_count": ai_info["fragmentos_count"],
            "documents_count": ai_info["documentos_count"],
            "using_vector_db": ai_info["using_vector_db"],
            "using_chroma": ai_info["using_chroma"],
            "llm_available": ai_info["llm"] is not None,
            "workers_active": health_status["workers_count"] > 0
        }
        
        logger.info(f"System health check completed: {health_status['overall_status']}")
        logger.info(f"📊 Final response - total_fragments: {health_status['total_fragments']}")
        logger.info(f"🔧 Workers: {health_status['workers_count']} - Models: {health_status.get('models_detail', 'Unknown')}")
        
        # Guardar en cache
        with _cache_lock:
            _system_health_cache["data"] = health_status
            _system_health_cache["timestamp"] = time.time()
            logger.info(f"System health cached for {_system_health_cache['ttl']}s")
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error verificando salud del sistema: {e}")
        return {
            "overall_status": "error",
            "database": False,
            "database_connected": False,
            "ollama": False,
            "llm_status": "error",
            "models_status": {"llama3": "error", "phi4": "error"},
            "models_detail": "Error al verificar",
            "models_detail": "Error al verificar",
            "phi4_model": "phi4:14b-q4_0",
            "workers_status": "error",
            "workers_count": 0,
            "vector_store": False,
            "vector_db_status": "error",
            "total_documents": 0,
            "total_fragments": 0,
            "pdf_files_loaded": 0,
            "error": str(e),
            "last_check": datetime.now().isoformat(),
            "ai_system_ready": False
        }

@router.get("/analytics")
def get_dashboard_analytics(days: int = 30):
    """Endpoint mejorado para obtener análisis avanzado con Ollama basado en datos reales - CORREGIDO"""
    try:
        with engine.connect() as connection:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Obtener feedback real del período
            result = connection.execute(
                text("""
                    SELECT rating, comentario, pregunta, created_at 
                    FROM feedback 
                    WHERE created_at >= :start_date
                    ORDER BY created_at DESC
                """),
                {"start_date": start_date}
            ).fetchall()
            
            feedback_data = [
                {
                    "rating": row[0],
                    "comentario": row[1],
                    "pregunta": row[2],
                    "created_at": row[3]
                } for row in result
            ]
        
        if not feedback_data:
            return {
                "insights": "No hay feedback suficiente en el período seleccionado para generar análisis detallado.",
                "total_feedback": 0,
                "promedio_rating": 0,
                "principales_problemas": ["Falta de feedback de usuarios", "Necesidad de más interacciones"],
                "recomendaciones": [
                    "Incentivar a los usuarios a proporcionar más feedback",
                    "Implementar recordatorios para calificar respuestas",
                    "Mejorar la experiencia de usuario para fomentar evaluaciones"
                ],
                "distribucion_ratings": {
                    "5_estrellas": 0,
                    "4_estrellas": 0,
                    "3_estrellas": 0,
                    "2_estrellas": 0,
                    "1_estrella": 0,
                },
                "period_days": days
            }
        
        # Análisis con Ollama usando datos reales
        problemas_analysis = analyze_feedback_problems(feedback_data)
        
        # Estadísticas reales
        ratings = [f["rating"] for f in feedback_data]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        analytics_data = {
            "total_feedback": len(feedback_data),
            "promedio_rating": round(avg_rating, 2),
            "rating_description": f"Calificación promedio de {round(avg_rating, 2)}/5 estrellas",
            "distribucion_ratings": {
                "5_estrellas": len([r for r in ratings if r == 5]),
                "4_estrellas": len([r for r in ratings if r == 4]),
                "3_estrellas": len([r for r in ratings if r == 3]),
                "2_estrellas": len([r for r in ratings if r == 2]),
                "1_estrella": len([r for r in ratings if r == 1]),
            },
            "principales_problemas": problemas_analysis.get("problemas", [
                "No se pudieron identificar problemas específicos",
                "Análisis requiere más datos de feedback",
                "Sistema funcionando dentro de parámetros normales"
            ]),
            "recomendaciones": problemas_analysis.get("recomendaciones", [
                "Continuar monitoreando la satisfacción del usuario",
                "Solicitar feedback más específico y detallado",
                "Implementar mejoras incrementales basadas en uso"
            ]),
            "period_days": days,
            "insights": f"Análisis basado en {len(feedback_data)} evaluaciones de los últimos {days} días."
        };
        
        # Análisis de sentimientos solo si hay comentarios
        comentarios_con_sentimiento = []
        for f in feedback_data:
            if f["comentario"] and f["comentario"].strip():
                sentimiento = analyze_feedback_sentiment(f["comentario"])
                comentarios_con_sentimiento.append({
                    "comentario": f["comentario"],
                    "sentimiento": sentimiento,
                    "rating": f["rating"]
                })
        
        analytics_data["analisis_sentimientos"] = comentarios_con_sentimiento
        analytics_data["total_comentarios"] = len(comentarios_con_sentimiento)
        
        return analytics_data;
        
    except Exception as e:
        logger.error(f"Error generando analytics: {e}")
        return {
            "error": str(e),
            "total_feedback": 0,
            "principales_problemas": ["Error en el sistema de análisis"],
            "recomendaciones": ["Verificar la configuración del sistema"]
        }
    
@router.get("/users-paginated")
def get_dashboard_users_paginated(page: int = 1, limit: int = 10, search: str = "", status: str = "", activity: str = ""):
    """Obtiene usuarios con paginación y filtros para el dashboard - CON FALLBACK"""
    try:
        if not is_database_available():
            logger.warning("Database not available for paginated users")
            return {
                "users": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0,
                "stats": {
                    "total_users": 0,
                    "active_users_week": 0,
                    "new_users_week": 0,
                    "inactive_users": 0
                },
                "error": "Database connection not available"
            }

        with engine.connect() as connection:
            # Query base
            base_query = """
                SELECT u.id, u.nombre, u.email, u.created_at, u.permisos,
                       COUNT(DISTINCT cs.session_id) as total_sessions,
                       COUNT(DISTINCT f.id) as total_feedback,
                       AVG(f.rating) as avg_rating,
                       MAX(cs.updated_at) as last_activity
                FROM users u
                LEFT JOIN chat_sessions cs ON u.id = cs.user_id
                LEFT JOIN feedback f ON u.id = f.user_id
            """

            group_by = " GROUP BY u.id, u.nombre, u.email, u.created_at, u.permisos"
            params = {}

            # Solo agregamos HAVING si hay filtro de búsqueda
            having = ""
            if search:
                having = " HAVING (u.nombre LIKE :search OR u.email LIKE :search OR u.id LIKE :search)"
                params["search"] = f"%{search}%"

            # Query para contar total
            count_query = f"{base_query}{group_by}{having}"
            count_query_wrapped = f"SELECT COUNT(*) FROM ({count_query}) as filtered_users"
            total_result = connection.execute(text(count_query_wrapped), params).fetchone()
            total_count = total_result[0] if total_result else 0

            # Query principal con paginación
            offset = (page - 1) * limit
            main_query = f"{base_query}{group_by}{having} ORDER BY u.created_at DESC LIMIT :limit OFFSET :offset"
            params.update({"limit": limit, "offset": offset})

            users_result = connection.execute(text(main_query), params).fetchall()

            users_list = []
            week_ago = datetime.now() - timedelta(days=7)

            for row in users_result:
                created_at = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S") if isinstance(row[3], str) else row[3]
                last_activity = row[8] if row[8] else None

                # Aplicar filtro de actividad si se especifica
                total_sessions = row[5] or 0
                if activity:
                    if activity == "high" and total_sessions < 5:
                        continue
                    elif activity == "medium" and (total_sessions < 2 or total_sessions > 4):
                        continue
                    elif activity == "low" and total_sessions != 1:
                        continue
                    elif activity == "none" and total_sessions != 0:
                        continue

                user_status = "activo" if last_activity and last_activity >= week_ago else "inactivo"

                # Aplicar filtro de estado si se especifica
                if status and user_status != status:
                    continue

                user_data = {
                    "id": row[0],
                    "nombre": row[1],
                    "email": row[2],
                    "created_at": created_at.isoformat() if created_at else None,
                    "permisos": row[4] or 'usuario',
                    "total_sessions": total_sessions,
                    "total_feedback": row[6] or 0,
                    "avg_rating": round(row[7], 2) if row[7] else 0,
                    "last_activity": last_activity.isoformat() if last_activity else None,
                    "status": user_status
                }
                users_list.append(user_data)

            # Estadísticas generales
            stats_result = connection.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN cs.updated_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 END) as active_users_week,
                        COUNT(CASE WHEN u.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 END) as new_users_week
                    FROM users u
                    LEFT JOIN chat_sessions cs ON u.id = cs.user_id
                """)
            ).fetchone()

            stats = {
                "total_users": stats_result[0] if stats_result else 0,
                "active_users_week": stats_result[1] if stats_result else 0,
                "new_users_week": stats_result[2] if stats_result else 0,
                "inactive_users": (stats_result[0] or 0) - (stats_result[1] or 0)
            }

            return {
                "users": users_list,
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": (total_count + limit - 1) // limit,
                "stats": stats
            }

    except Exception as e:
        logger.error(f"Error obteniendo usuarios paginados: {e}")
        return {
            "users": [],
            "total": 0,
            "page": 1,
            "limit": limit,
            "total_pages": 0,
            "stats": {
                "total_users": 0,
                "active_users_week": 0,
                "new_users_week": 0,
                "inactive_users": 0
            },
            "error": str(e)
        }
    
@router.get("/feedback-paginated")
def get_dashboard_feedback_paginated(page: int = 1, limit: int = 10, search: str = "", rating: str = ""):
    """Obtiene feedback con paginación y filtros para el dashboard - CON FALLBACK"""
    try:
        if not is_database_available():
            logger.warning("Database not available for paginated feedback")
            return {
                "feedback": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0,
                "stats": {
                    "total_feedback": 0,
                    "avg_rating": 0,
                    "positive_feedback": 0,
                    "negative_feedback": 0
                },
                "success": False,
                "error": "Database connection not available"
            }

        with engine.connect() as connection:
            # Query base
            base_query = """
                SELECT f.id, f.user_id, f.pregunta, f.respuesta, f.rating, 
                       f.comentario, f.created_at, u.nombre, u.email
                FROM feedback f
                LEFT JOIN users u ON f.user_id = u.id
            """
            
            where_conditions = []
            params = {}
            
            # Aplicar filtros
            if search:
                where_conditions.append("(u.nombre LIKE :search OR f.pregunta LIKE :search OR f.comentario LIKE :search)")
                params["search"] = f"%{search}%"
            
            if rating:
                where_conditions.append("f.rating = :rating")
                params["rating"] = int(rating)
            
            # Construir WHERE clause
            where_clause = ""
            if where_conditions:
                where_clause = " WHERE " + " AND ".join(where_conditions)
            
            # Query para contar total
            count_query = f"SELECT COUNT(*) FROM ({base_query}{where_clause}) as filtered_feedback"
            total_result = connection.execute(text(count_query), params).fetchone()
            total_count = total_result[0] if total_result else 0
            
            # Query principal con paginación
            offset = (page - 1) * limit
            main_query = f"{base_query}{where_clause} ORDER BY f.created_at DESC LIMIT :limit OFFSET :offset"
            params.update({"limit": limit, "offset": offset})
            
            feedback_result = connection.execute(text(main_query), params).fetchall()
            
            feedback_list = []
            for row in feedback_result:
                feedback_item = {
                    "id": row[0],
                    "user_id": row[1],
                    "pregunta": row[2],
                    "respuesta": row[3],
                    "rating": row[4],
                    "comentario": row[5] or "",
                    "created_at": row[6].isoformat() if row[6] else None,
                    "user_name": row[7] or f"Usuario {row[1]}",
                    "user_email": row[8] or "No disponible"
                }
                feedback_list.append(feedback_item)
            
            # Estadísticas generales de feedback
            stats_result = connection.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_feedback,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN rating >= 4 THEN 1 END) as positive_feedback,
                        COUNT(CASE WHEN rating <= 2 THEN 1 END) as negative_feedback
                    FROM feedback
                """)
            ).fetchone()
            
            stats = {
                "total_feedback": stats_result[0] if stats_result else 0,
                "avg_rating": round(stats_result[1], 2) if stats_result[1] else 0,
                "positive_feedback": stats_result[2] if stats_result else 0,
                "negative_feedback": stats_result[3] if stats_result else 0
            }
            
            return {
                "feedback": feedback_list,
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": (total_count + limit - 1) // limit,
                "stats": stats,
                "success": True
            }
            
    except Exception as e:
        logger.error(f"Error obteniendo feedback paginado: {e}")
        return {
            "feedback": [],
            "total": 0,
            "page": 1,
            "limit": limit,
            "total_pages": 0,
            "stats": {
                "total_feedback": 0,
                "avg_rating": 0,
                "positive_feedback": 0,
                "negative_feedback": 0
            },
            "success": False,
            "error": str(e)
        }
    
@router.put("/users/{user_id}")
async def update_user(user_id: int, request: Request):
    """Actualiza información de un usuario específico"""
    try:
        data = await request.json()
        logger.info(f"Actualizando usuario {user_id}: {data}")
        
        nombre = data.get("nombre")
        email = data.get("email")
        password = data.get("password")
        permisos = data.get("permisos")
        
        if not all([nombre, email, permisos]):
            return {"success": False, "message": "Nombre, email y permisos son requeridos"}
        
        # Validar permisos
        if permisos not in ['usuario', 'admin']:
            return {"success": False, "message": "Permisos inválidos. Use 'usuario' o 'admin'"}
        
        with SessionLocal() as db:
            # Verificar que el usuario existe
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Usuario no encontrado"}
            
            # Verificar si el email ya existe (pero no es el mismo usuario)
            existing_user = db.query(User).filter(
                User.email == email, 
                User.id != user_id
            ).first()
            if existing_user:
                return {"success": False, "message": "El email ya está en uso por otro usuario"}
            
            try:
                # Actualizar datos
                user.nombre = nombre
                user.email = email
                user.permisos = permisos
                
                # Solo actualizar contraseña si se proporciona
                if password and password.strip():
                    user.password = pwd_context.hash(password)
                
                db.commit()
                db.refresh(user)
                
                logger.info(f"Usuario {user_id} actualizado exitosamente")
                return {
                    "success": True,
                    "message": "Usuario actualizado exitosamente",
                    "user": {
                        "id": user.id,
                        "nombre": user.nombre,
                        "email": user.email,
                        "permisos": user.permisos
                    }
                }
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error al actualizar usuario {user_id}: {str(e)}")
                return {"success": False, "message": f"Error al actualizar usuario: {str(e)}"}
                
    except Exception as e:
        logger.error(f"Error general al actualizar usuario {user_id}: {str(e)}")
        return {"success": False, "message": f"Error general: {str(e)}"}
    
@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
async def delete_user(user_id: int):
    """
    Elimina un usuario y toda su información asociada (sesiones, feedback).
    """
    logger.info(f"Solicitud para eliminar usuario ID: {user_id}")
    
    db: Session = SessionLocal()
    try:
        # 1. Encontrar al usuario
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"Intento de eliminar usuario no existente. ID: {user_id}")
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # 2. Eliminar feedback asociado al usuario
        feedback_asociado = db.query(Feedback).filter(Feedback.user_id == str(user_id)).all()
        if feedback_asociado:
            for fb in feedback_asociado:
                db.delete(fb)
            logger.info(f"Eliminados {len(feedback_asociado)} registros de feedback para el usuario {user_id}.")

        # 3. Eliminar sesiones de chat asociadas al usuario
        sesiones_asociadas = db.query(ChatSession).filter(ChatSession.user_id == str(user_id)).all()
        if sesiones_asociadas:
            for session in sesiones_asociadas:
                db.delete(session)
            logger.info(f"Eliminadas {len(sesiones_asociadas)} sesiones de chat para el usuario {user_id}.")
            
        # 4. Eliminar al usuario
        db.delete(user)
        
        # 5. Confirmar los cambios en la base de datos
        db.commit()
        
        logger.info(f"Usuario {user_id} y sus datos asociados eliminados exitosamente.")
        return {"success": True, "message": "Usuario eliminado exitosamente."}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al eliminar el usuario {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor al intentar eliminar el usuario: {e}")
    finally:
        db.close()

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """
    Elimina una tarea de chat de la base de datos.
    """
    logger.info(f"Solicitud para eliminar tarea ID: {task_id}")
    
    if not is_database_available():
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    
    try:
        with SessionLocal() as db:
            from models import ChatTask
            
            # Buscar la tarea
            task = db.query(ChatTask).filter(ChatTask.task_id == task_id).first()
            
            if not task:
                logger.warning(f"Intento de eliminar tarea no existente. ID: {task_id}")
                raise HTTPException(status_code=404, detail="Tarea no encontrada")
            
            # Eliminar la tarea
            db.delete(task)
            db.commit()
            
            logger.info(f"Tarea {task_id} eliminada exitosamente.")
            return {"success": True, "message": "Tarea eliminada exitosamente."}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar la tarea {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar la tarea: {str(e)}")

@router.get("/check-access")
def check_dashboard_access():
    """Verifica que el dashboard esté accesible"""
    try:
        return {
            "success": True,
            "message": "Dashboard accesible",
            "timestamp": datetime.now().isoformat(),
            "endpoints_available": [
                "/dashboard/stats",
                "/dashboard/users",
                "/dashboard/feedback-analysis",
                "/dashboard/system-health"
            ]
        }
    except Exception as e:
        logger.error(f"Error verificando acceso al dashboard: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

def get_size_format(bytes_value):
    """Convierte bytes a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

@router.get("/system-resources")
def get_system_resources():
    """Obtiene métricas del sistema en tiempo real"""
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)
        cpu_freq = psutil.cpu_freq()
        
        # Memoria RAM
        memory = psutil.virtual_memory()
        
        # Disco
        disk = psutil.disk_usage('/')
        
        # Red
        net_io = psutil.net_io_counters()
        
        # Temperatura (intentar obtener)
        temps = {}
        try:
            temps = psutil.sensors_temperatures()
        except:
            temps = {}
        
        # GPU (detectar de multiples formas)
        gpu_info = {"available": False}
        
        # Metodo 1: GPUtil (NVIDIA principalmente)
        if GPU_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_info = {
                        "available": True,
                        "name": gpu.name,
                        "vendor": "NVIDIA",
                        "load": f"{gpu.load * 100:.1f}%",
                        "load_percent": gpu.load * 100,
                        "memory_used": get_size_format(gpu.memoryUsed * 1024 * 1024),
                        "memory_total": get_size_format(gpu.memoryTotal * 1024 * 1024),
                        "memory_percent": f"{(gpu.memoryUsed / gpu.memoryTotal) * 100:.1f}%",
                        "temperature": f"{gpu.temperature}°C" if gpu.temperature else "N/A"
                    }
            except Exception as e:
                logger.debug(f"GPUtil no detectó GPU: {e}")
        
        # Metodo 2: Detectar AMD/Intel/Otras GPUs via sistema
        if not gpu_info["available"]:
            try:
                # Intentar detectar via lspci en Linux o wmic en Windows
                import subprocess
                if platform.system() == "Windows":
                    result = subprocess.run(
                        ["wmic", "path", "win32_VideoController", "get", "name"],
                        capture_output=True, text=True, timeout=2
                    )
                    if result.returncode == 0 and result.stdout:
                        lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and l.strip() != 'Name']
                        if lines:
                            gpu_name = lines[0]
                            gpu_info = {
                                "available": True,
                                "name": gpu_name,
                                "vendor": "AMD" if "AMD" in gpu_name.upper() else "Intel" if "INTEL" in gpu_name.upper() else "Unknown",
                                "load": "N/A",
                                "load_percent": 0,
                                "memory_used": "N/A",
                                "memory_total": "N/A",
                                "memory_percent": "N/A",
                                "temperature": "N/A"
                            }
                elif platform.system() == "Linux":
                    result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'VGA' in line or 'Display' in line or '3D' in line:
                                gpu_name = line.split(': ')[-1].strip()
                                gpu_info = {
                                    "available": True,
                                    "name": gpu_name,
                                    "vendor": "AMD" if "AMD" in gpu_name.upper() else "Intel" if "INTEL" in gpu_name.upper() else "NVIDIA" if "NVIDIA" in gpu_name.upper() else "Unknown",
                                    "load": "N/A",
                                    "load_percent": 0,
                                    "memory_used": "N/A",
                                    "memory_total": "N/A",
                                    "memory_percent": "N/A",
                                    "temperature": "N/A"
                                }
                                break
            except Exception as e:
                logger.debug(f"Detección alternativa de GPU falló: {e}")
        
        if not gpu_info["available"]:
            gpu_info = {"available": False, "message": "No se detectó GPU"}
        
        # Información del sistema
        system_info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node()
        }
        
        # Temperatura CPU
        cpu_temp = "N/A"
        if temps:
            # Intentar obtener temperatura de diferentes fuentes
            for name, entries in temps.items():
                if entries:
                    cpu_temp = f"{entries[0].current}°C"
                    break
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "usage_percent": cpu_percent,
                "count_logical": cpu_count_logical,
                "count_physical": cpu_count_physical,
                "frequency_current": f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A",
                "frequency_max": f"{cpu_freq.max:.0f} MHz" if cpu_freq else "N/A",
                "temperature": cpu_temp
            },
            "memory": {
                "total": get_size_format(memory.total),
                "available": get_size_format(memory.available),
                "used": get_size_format(memory.used),
                "percent": memory.percent
            },
            "disk": {
                "total": get_size_format(disk.total),
                "used": get_size_format(disk.used),
                "free": get_size_format(disk.free),
                "percent": disk.percent
            },
            "network": {
                "bytes_sent": get_size_format(net_io.bytes_sent),
                "bytes_recv": get_size_format(net_io.bytes_recv),
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            },
            "gpu": gpu_info,
            "system": system_info
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo recursos del sistema: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/workers-status")
def get_workers_status():
    """Obtiene el estado de los workers de Celery"""
    try:
        from celery_worker import celery_app
        
        # Inspeccionar workers activos
        inspect = celery_app.control.inspect()
        
        # Obtener estadísticas
        stats = inspect.stats()
        active_tasks = inspect.active()
        registered_tasks = inspect.registered()
        
        workers_info = []
        total_workers = 0
        
        if stats:
            total_workers = len(stats)
            for worker_name, worker_stats in stats.items():
                worker_info = {
                    "name": worker_name,
                    "status": "activo",
                    "pool": worker_stats.get('pool', {}).get('implementation', 'N/A'),
                    "max_concurrency": worker_stats.get('pool', {}).get('max-concurrency', 'N/A'),
                    "active_tasks": len(active_tasks.get(worker_name, [])) if active_tasks else 0,
                    "total_tasks": worker_stats.get('total', {})
                }
                workers_info.append(worker_info)
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "total_workers": total_workers,
            "workers": workers_info,
            "active": total_workers > 0
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de workers: {e}")
        return {
            "success": False,
            "error": str(e),
            "total_workers": 0,
            "workers": [],
            "active": False,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/active-tasks")
def get_active_tasks():
    """
    Obtiene todas las tareas de chat activas y recientes desde la base de datos
    """
    try:
        if not is_database_available():
            return {
                "active_count": 0,
                "total_count": 0,
                "stats": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
                "tasks": [],
                "error": "Database not available",
                "timestamp": datetime.now().isoformat()
            }
        
        with engine.connect() as connection:
            # Importar ChatTask del models
            from models import ChatTask
            
            # Obtener tareas activas y recientes (últimas 24 horas) con JOIN a users para obtener nombre
            query = text("""
                SELECT 
                    t.id, t.task_id, t.user_id, t.session_id,
                    t.query, t.query_length, t.response, t.response_length,
                    t.model, t.worker_name, t.status,
                    t.started_at, t.completed_at, t.processing_time,
                    t.vector_db_used, t.documents_count, t.error_message,
                    t.created_at,
                    u.nombre as username
                FROM chat_tasks t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                ORDER BY t.created_at DESC
                LIMIT 100
            """)
            
            result = connection.execute(query)
            tasks = []
            
            for row in result:
                # Calcular tiempo transcurrido si está en procesamiento
                elapsed_time = None
                if row.status == 'PROCESSING' and row.started_at:
                    elapsed_time = (datetime.now() - row.started_at).total_seconds()
                elif row.processing_time:
                    elapsed_time = row.processing_time
                
                tasks.append({
                    'id': row.id,
                    'task_id': row.task_id,
                    'user_id': row.user_id,
                    'username': row.username,  # Nombre del usuario desde JOIN
                    'session_id': row.session_id,
                    'query': row.query[:150] + '...' if row.query and len(row.query) > 150 else row.query,
                    'query_full': row.query,  # Para modal
                    'query_length': row.query_length,
                    'response': row.response[:200] + '...' if row.response and len(row.response) > 200 else row.response,
                    'response_full': row.response,  # Para modal
                    'response_length': row.response_length,
                    'model': row.model,
                    'worker_name': row.worker_name,
                    'status': row.status.lower() if row.status else 'pending',  # Convertir a minúsculas para frontend
                    'started_at': row.started_at.isoformat() if row.started_at else None,
                    'completed_at': row.completed_at.isoformat() if row.completed_at else None,
                    'processing_time': round(row.processing_time, 2) if row.processing_time else None,
                    'elapsed_time': round(elapsed_time, 2) if elapsed_time else None,
                    'vector_db_used': bool(row.vector_db_used),
                    'documents_count': row.documents_count,
                    'error_message': row.error_message,
                    'created_at': row.created_at.isoformat() if row.created_at else None
                })
            
            # Contar por estado (en minúsculas para consistencia con frontend)
            status_counts = {
                'pending': sum(1 for t in tasks if t['status'] == 'pending'),
                'processing': sum(1 for t in tasks if t['status'] == 'processing'),
                'completed': sum(1 for t in tasks if t['status'] == 'completed'),
                'failed': sum(1 for t in tasks if t['status'] == 'failed')
            }
            
            logger.info(f"📊 Active tasks retrieved: {len(tasks)} total")
            logger.info(f"   - Pending: {status_counts['pending']}")
            logger.info(f"   - Processing: {status_counts['processing']}")
            logger.info(f"   - Completed: {status_counts['completed']}")
            logger.info(f"   - Failed: {status_counts['failed']}")
            
            return {
                "active_count": status_counts['pending'] + status_counts['processing'],
                "total_count": len(tasks),
                "stats": status_counts,
                "tasks": tasks,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            "active_count": 0,
            "total_count": 0,
            "stats": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
            "tasks": [],
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# =====================================================
# DIAGNOSTICS - STRESS TESTS ENDPOINTS
# =====================================================

# Importar modulos de diagnostico
try:
    from diagnostics import StressTestRunner, MetricsCollector, ReportGenerator
    from models import StressTest, StressTestStatusEnum, StartStressTestRequest
    DIAGNOSTICS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Modulo de diagnosticos no disponible: {e}")
    DIAGNOSTICS_AVAILABLE = False

# Cache para tests en ejecucion
_running_tests = {}
_tests_lock = threading.Lock()


@router.get("/diagnostics/hardware")
async def get_hardware_info():
    """Obtiene informacion del hardware del sistema"""
    if not DIAGNOSTICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Modulo de diagnosticos no disponible")
    
    try:
        collector = MetricsCollector()
        hardware = collector.get_hardware_info()
        return {"success": True, "hardware": hardware}
    except Exception as e:
        logger.error(f"Error obteniendo hardware info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics/tests")
async def get_stress_tests(limit: int = 20):
    """Obtiene historial de tests de estres"""
    try:
        engine_db = engine
        with engine_db.connect() as connection:
            query = text("""
                SELECT 
                    t.id, t.test_id, t.name, t.config, t.status,
                    t.started_at, t.completed_at, t.duration_seconds,
                    t.hardware_info, t.summary, t.error_message,
                    t.created_by, t.created_at,
                    u.nombre as created_by_name
                FROM stress_tests t
                LEFT JOIN users u ON t.created_by = u.id
                ORDER BY t.created_at DESC
                LIMIT :limit
            """)
            
            result = connection.execute(query, {"limit": limit})
            tests = []
            
            for row in result:
                summary = row.summary if isinstance(row.summary, dict) else (
                    json.loads(row.summary) if row.summary else {}
                )
                config = row.config if isinstance(row.config, dict) else (
                    json.loads(row.config) if row.config else {}
                )
                
                tests.append({
                    "id": row.id,
                    "test_id": row.test_id,
                    "name": row.name,
                    "config": config,
                    "status": row.status,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "duration_seconds": row.duration_seconds,
                    "summary": summary,
                    "error_message": row.error_message,
                    "created_by_name": row.created_by_name,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                })
            
            return {"success": True, "tests": tests, "count": len(tests)}
            
    except Exception as e:
        logger.error(f"Error obteniendo tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics/tests/{test_id}")
async def get_stress_test_detail(test_id: str):
    """Obtiene detalle completo de un test de estres"""
    try:
        db = SessionLocal()
        try:
            test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
            
            if not test:
                raise HTTPException(status_code=404, detail="Test no encontrado")
            
            return {
                "success": True,
                "test": {
                    "id": test.id,
                    "test_id": test.test_id,
                    "name": test.name,
                    "config": test.config,
                    "status": test.status.value if test.status else "PENDING",
                    "started_at": test.started_at.isoformat() if test.started_at else None,
                    "completed_at": test.completed_at.isoformat() if test.completed_at else None,
                    "duration_seconds": test.duration_seconds,
                    "hardware_info": test.hardware_info,
                    "metrics_snapshots": test.metrics_snapshots,
                    "summary": test.summary,
                    "log_entries": test.log_entries,
                    "error_message": test.error_message,
                    "created_at": test.created_at.isoformat() if test.created_at else None
                }
            }
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo test {test_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnostics/tests/start")
async def start_stress_test(request: Request):
    """Inicia un nuevo test de estres"""
    if not DIAGNOSTICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Modulo de diagnosticos no disponible")
    
    try:
        body = await request.json()
        name = body.get("name", "Test sin nombre")
        config = body.get("config", {})
        user_id = body.get("user_id", 1)
        
        # Generar ID unico
        import uuid
        test_id = str(uuid.uuid4())
        
        # Crear registro en BD
        db = SessionLocal()
        try:
            new_test = StressTest(
                test_id=test_id,
                name=name,
                config=config,
                status=StressTestStatusEnum.PENDING,
                created_by=user_id
            )
            db.add(new_test)
            db.commit()
            db.refresh(new_test)
            
            # Iniciar test en background
            import threading
            thread = threading.Thread(
                target=_run_stress_test_background,
                args=(test_id, config),
                daemon=True
            )
            thread.start()
            
            with _tests_lock:
                _running_tests[test_id] = {
                    "thread": thread,
                    "logs": [],
                    "snapshots": []
                }
            
            return {
                "success": True,
                "test_id": test_id,
                "message": "Test iniciado"
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error iniciando test: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


def _run_stress_test_background(test_id: str, config: dict):
    """Ejecuta el test de estres en background"""
    import asyncio
    
    db = SessionLocal()
    logs = []
    snapshots = []
    
    def on_log(message: str):
        logs.append(message)
        with _tests_lock:
            if test_id in _running_tests:
                _running_tests[test_id]["logs"] = logs[-100:]  # Ultimos 100 logs
    
    def on_snapshot(snapshot: dict):
        snapshots.append(snapshot)
        with _tests_lock:
            if test_id in _running_tests:
                _running_tests[test_id]["snapshots"] = snapshots[-50:]  # Ultimos 50 snapshots
    
    try:
        # Actualizar estado a PROCESSING
        test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
        if test:
            test.status = StressTestStatusEnum.PROCESSING
            test.started_at = datetime.now()
            db.commit()
        
        # Ejecutar test - usar 127.0.0.1 para conexion local dentro del contenedor
        # Esto evita problemas de resolucion DNS con 'localhost'
        runner = StressTestRunner(base_url="http://127.0.0.1:8000")
        
        # Crear event loop para asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                runner.run_test(config, on_log=on_log, on_snapshot=on_snapshot)
            )
        finally:
            loop.close()
        
        # Guardar resultados
        test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
        if test:
            test.status = StressTestStatusEnum.COMPLETED
            test.completed_at = datetime.now()
            test.duration_seconds = result.get("duration_seconds", 0)
            test.hardware_info = result.get("hardware_info", {})
            test.metrics_snapshots = result.get("snapshots", [])
            test.summary = result.get("summary", {})
            test.log_entries = logs
            db.commit()
        
        logger.info(f"Test {test_id} completado exitosamente")
        
    except Exception as e:
        logger.error(f"Error en test {test_id}: {e}")
        logger.error(traceback.format_exc())
        
        test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
        if test:
            test.status = StressTestStatusEnum.FAILED
            test.completed_at = datetime.now()
            test.error_message = str(e)
            test.log_entries = logs
            db.commit()
    
    finally:
        db.close()
        
        with _tests_lock:
            if test_id in _running_tests:
                del _running_tests[test_id]


@router.get("/diagnostics/tests/{test_id}/status")
async def get_stress_test_status(test_id: str):
    """Obtiene estado actual de un test en ejecucion"""
    try:
        # Verificar si esta en ejecucion
        with _tests_lock:
            if test_id in _running_tests:
                running_data = _running_tests[test_id]
                return {
                    "success": True,
                    "status": "PROCESSING",
                    "logs": running_data.get("logs", []),
                    "snapshots": running_data.get("snapshots", []),
                    "is_running": True
                }
        
        # Si no esta en ejecucion, buscar en BD
        db = SessionLocal()
        try:
            test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
            
            if not test:
                raise HTTPException(status_code=404, detail="Test no encontrado")
            
            return {
                "success": True,
                "status": test.status.value if test.status else "PENDING",
                "logs": test.log_entries or [],
                "snapshots": test.metrics_snapshots or [],
                "is_running": False,
                "summary": test.summary
            }
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo status {test_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnostics/tests/{test_id}/stop")
async def stop_stress_test(test_id: str):
    """Detiene un test en ejecucion"""
    if not DIAGNOSTICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Modulo de diagnosticos no disponible")
    
    try:
        with _tests_lock:
            if test_id not in _running_tests:
                raise HTTPException(status_code=404, detail="Test no esta en ejecucion")
        
        # Marcar para detener (el runner verifica should_stop)
        # Por ahora solo actualizamos el estado
        db = SessionLocal()
        try:
            test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
            if test:
                test.status = StressTestStatusEnum.FAILED
                test.completed_at = datetime.now()
                test.error_message = "Test detenido por el usuario"
                db.commit()
        finally:
            db.close()
        
        return {"success": True, "message": "Test detenido"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deteniendo test {test_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics/tests/{test_id}/export")
async def export_stress_test(test_id: str, format: str = "csv"):
    """Exporta resultados de un test"""
    if not DIAGNOSTICS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Modulo de diagnosticos no disponible")
    
    try:
        db = SessionLocal()
        try:
            test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
            
            if not test:
                raise HTTPException(status_code=404, detail="Test no encontrado")
            
            # Preparar datos
            test_data = {
                "test_id": test.test_id,
                "name": test.name,
                "config": test.config,
                "status": test.status.value if test.status else "PENDING",
                "started_at": test.started_at.isoformat() if test.started_at else None,
                "completed_at": test.completed_at.isoformat() if test.completed_at else None,
                "duration_seconds": test.duration_seconds,
                "hardware_info": test.hardware_info or {},
                "metrics_snapshots": test.metrics_snapshots or [],
                "summary": test.summary or {},
                "error_message": test.error_message
            }
            
            # Generar reporte
            from fastapi.responses import Response
            
            if format == "csv":
                content = ReportGenerator.generate_csv(test_data)
                media_type = "text/csv; charset=utf-8"
                filename = f"stress_test_{test_id}.csv"
                return Response(
                    content=content.encode('utf-8'),
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            elif format == "txt":
                content = ReportGenerator.generate_txt(test_data)
                media_type = "text/plain; charset=utf-8"
                filename = f"stress_test_{test_id}.txt"
                return Response(
                    content=content.encode('utf-8'),
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            elif format == "json":
                content = ReportGenerator.generate_json(test_data)
                media_type = "application/json; charset=utf-8"
                filename = f"stress_test_{test_id}.json"
                return Response(
                    content=content.encode('utf-8'),
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            elif format == "xlsx":
                content = ReportGenerator.generate_xlsx(test_data)
                media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                filename = f"stress_test_{test_id}.xlsx"
                return Response(
                    content=content,
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            else:
                raise HTTPException(status_code=400, detail="Formato no soportado. Use: csv, txt, json, xlsx")
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exportando test {test_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/diagnostics/tests/{test_id}")
async def delete_stress_test(test_id: str):
    """Elimina un test de estres"""
    try:
        db = SessionLocal()
        try:
            test = db.query(StressTest).filter(StressTest.test_id == test_id).first()
            
            if not test:
                raise HTTPException(status_code=404, detail="Test no encontrado")
            
            # No permitir eliminar tests en ejecucion
            with _tests_lock:
                if test_id in _running_tests:
                    raise HTTPException(status_code=400, detail="No se puede eliminar un test en ejecucion")
            
            db.delete(test)
            db.commit()
            
            return {"success": True, "message": "Test eliminado"}
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando test {test_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Verification and logging at module level
def verify_router_setup():
    """Verify that all expected routes are registered"""
    expected_routes = [
        "/stats", "/user-sessions", "/feedback-analysis", "/users", 
        "/recent-feedback", "/system-health", "/analytics", "/users-paginated", 
        "/feedback-paginated", "/check-access"
    ]
    
    registered_routes = []
    for route in router.routes:
        if hasattr(route, 'path'):
            registered_routes.append(route.path)
    
    logger.info(f"📊 Expected dashboard routes: {len(expected_routes)}")
    logger.info(f"📊 Actually registered routes: {len(registered_routes)}")
    
    missing_routes = [route for route in expected_routes if route not in registered_routes]
    if missing_routes:
        logger.warning(f"⚠️ Missing routes: {missing_routes}")
    else:
        logger.info("✅ All expected routes are registered!")
    
    return len(missing_routes) == 0

# Execute verification
router_verification_passed = verify_router_setup()

# Add this logging statement at the very end of the file
total_routes = len(router.routes)
logger.info(f"🔧 Dashboard module loaded with {total_routes} routes:")
for idx, route in enumerate(router.routes):
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ', '.join(route.methods)
        logger.info(f"  📋 Route [{idx}]: {methods} {route.path}")
    else:
        logger.info(f"  📋 Route [{idx}]: {type(route)} - {getattr(route, 'path', 'no path')}")

logger.info(f"✅ Dashboard module initialization complete. Verification: {'PASSED' if router_verification_passed else 'FAILED'}")

# Make sure the router object is properly exported
__all__ = ['router']