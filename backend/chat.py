from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from datetime import datetime
from database import engine
from models import SolicitudSugerencias
from ai_system import ai_system
import re
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/feedback")
def get_feedback_endpoint(user_id: str = None, session_id: str = None):
    try:
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
        logger.error(f"Error obteniendo feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/message_ratings")
def get_message_ratings_endpoint(user_id: str, session_id: str):
    try:
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
        logger.error(f"Error obteniendo ratings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sugerencias")
def generar_sugerencias(solicitud: SolicitudSugerencias):
    try:
        history = solicitud.history if solicitud.history else []
        
        if not history:
            return {
                "sugerencias": [
                    "¿Qué es la inteligencia artificial?",
                    "¿Cuáles son los temas principales del curso?",
                    "¿Cómo se evalúa el curso?"
                ]
            }
        
        recent_history = history[-5:] if len(history) > 5 else history
        
        formatted_history = ""
        for msg in recent_history:
            if msg.get('sender') == 'user':
                formatted_history += f"Usuario: {msg.get('text','')}\n"
            elif msg.get('sender') == 'bot':
                formatted_history += f"Bot: {msg.get('text','')}\n"
        
        prompt = f"""
        Genera exactamente 3 preguntas cortas y directas (máximo 6 palabras cada una) basadas en esta conversación.
        Las preguntas deben ser relevantes para el contexto de inteligencia artificial y el curso actual.
        
        Las sugerencias deben ser siempre en español.
        REGLAS ESTRICTAS:
        1. Máximo 6 palabras por pregunta
        2. Usar palabras simples y directas
        3. Siempre empezar con: ¿Qué, ¿Cómo, ¿Cuál, ¿Por qué, ¿Dónde
        4. NO usar palabras técnicas largas
        5. Ser específico pero conciso
        6. Relacionado con inteligencia artificial
        
        Ejemplos de formato correcto:
        - ¿Qué son las redes neuronales?
        - ¿Cómo funciona el machine learning?
        - ¿Cuál es la diferencia principal?

        Conversación:
        {formatted_history}
        
        Responde SOLO las 3 preguntas, una por línea, sin números ni explicaciones adicionales:
        """
        
        try:
            if ai_system.llm is None:
                logger.warning("LLM no disponible para sugerencias")
                return {
                    "sugerencias": [
                        "¿Puedes explicar más sobre este tema?",
                        "¿Qué ejemplos hay de esto?",
                        "¿Cómo se aplica en la práctica?"
                    ]
                }
            
            response = ai_system.llm.invoke(prompt)
            
            sugerencias = []
            for line in response.strip().split('\n'):
                line = line.strip()
                if line and not line.isspace():
                    cleaned_line = re.sub(r'^\d+[\.\)-]\s*', '', line)
                    cleaned_line = re.sub(r'¿¿+', '¿', cleaned_line)
                    cleaned_line = re.sub(r'\?\?+', '?', cleaned_line)
                    if not cleaned_line.endswith('?') and ('qué' in cleaned_line.lower() or 'cómo' in cleaned_line.lower() or 'cuál' in cleaned_line.lower() or 'por qué' in cleaned_line.lower()):
                        cleaned_line += '?'
                    sugerencias.append(cleaned_line)
            
            while len(sugerencias) < 3:
                sugerencias.append("¿Necesitas más información sobre algún tema?")
            
            sugerencias = sugerencias[:3]
            sugerencias = [s[:120] + "..." if len(s) > 120 else s for s in sugerencias]
            
            return {"sugerencias": sugerencias}
            
        except Exception as e:
            logger.error(f"Error generando sugerencias con el modelo: {e}")
            return {
                "sugerencias": [
                    "¿Puedes explicar más sobre este tema?",
                    "¿Qué ejemplos hay de esto?",
                    "¿Cómo se aplica en la práctica?"
                ]
            }
    except Exception as e:
        logger.error(f"Error en generar_sugerencias: {e}")
        return {"error": str(e)}