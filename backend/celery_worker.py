# ===== CELERY WORKER PARA PROCESAMIENTO ASINCRÓNICO =====
# Archivo: celery_worker.py
# Propósito: Worker dedicado para procesamiento de IA en segundo plano

import os
import sys
import logging
import traceback
import time
from datetime import datetime
from celery import Celery, Task
from celery.utils.log import get_task_logger

# Agregar el directorio backend al path para imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports del sistema de IA
from ai_system import AISystem
from config import *

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('celery_worker.log')
    ]
)

# Logger específico para Celery
logger = get_task_logger(__name__)

# ===== CONFIGURACIÓN DE CELERY =====
# Crear la aplicación Celery
celery_app = Celery('chatbot_worker')

# Configuración de Celery
celery_app.config_from_object({
    # Broker y Backend (Redis)
    'broker_url': 'redis://localhost:6379/0',
    'result_backend': 'redis://localhost:6379/0',
    
    # Serialización
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    
    # Timezone
    'timezone': 'UTC',
    'enable_utc': True,
    
    # Configuración de workers
    'worker_prefetch_multiplier': 1,  # Procesar una tarea a la vez por worker
    'task_acks_late': True,  # Confirmar tarea solo después de completarla
    'worker_disable_rate_limits': False,
    
    # Pool configuration para Windows
    'worker_pool': 'threads',  # Usar threads en lugar de prefork para Windows
    'worker_concurrency': 2,   # 2 threads concurrentes
    
    # Timeouts
    'task_soft_time_limit': 300,  # 5 minutos soft limit
    'task_time_limit': 600,       # 10 minutos hard limit
    
    # Retry policy
    'task_default_retry_delay': 60,
    'task_max_retries': 3,
    
    # Monitoreo
    'worker_send_task_events': True,
    'task_send_sent_event': True,
})

# ===== INSTANCIA GLOBAL DEL SISTEMA IA =====
# Se inicializa cuando el worker arranca
ai_system_instance = None

def initialize_ai_system():
    """Inicializar el sistema de IA en el worker"""
    global ai_system_instance
    
    if ai_system_instance is None:
        logger.info("🚀 Inicializando sistema de IA en worker...")
        try:
            ai_system_instance = AISystem()
            
            # Inicializar el sistema completamente
            logger.info("📚 Cargando documentos y configurando vector store...")
            ai_system_instance.initialize_system()
            logger.info(f"✅ Sistema de IA inicializado correctamente")
            logger.info(f"   - Modelo actual: {ai_system_instance.current_model}")
            logger.info(f"   - Vector store: {'Sí' if ai_system_instance.using_vector_db else 'No'}")
            logger.info(f"   - Documentos: {len(ai_system_instance.documentos)}")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando sistema de IA: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    return ai_system_instance

# ===== TASK BASE CLASS =====
# class CallbackTask(Task):
#     """Clase base para tareas con callbacks de progreso"""
#     
#     def on_success(self, retval, task_id, args, kwargs):
#         """Callback ejecutado cuando la tarea es exitosa"""
#         logger.info(f"✅ Tarea {task_id} completada exitosamente")
#     
#     def on_failure(self, exc, task_id, args, kwargs, einfo):
#         """Callback ejecutado cuando la tarea falla"""
#         logger.error(f"❌ Tarea {task_id} falló: {exc}")
#         logger.error(f"Traceback: {einfo}")
#     
#     def on_retry(self, exc, task_id, args, kwargs, einfo):
#         """Callback ejecutado cuando la tarea se reintenta"""
#         logger.warning(f"🔄 Reintentando tarea {task_id}: {exc}")

# ===== TAREAS ASINCRÓNICAS =====

@celery_app.task(bind=True)
def process_chat_task(self, user_input, model_name=None, conversation_id=None):
    """
    Tarea asincrónica para procesar consultas de chat
    
    Args:
        user_input (str): Consulta del usuario
        model_name (str, optional): Modelo a usar
        conversation_id (str, optional): ID de conversación
    
    Returns:
        dict: Resultado del procesamiento
    """
    task_id = self.request.id
    start_time = time.time()
    current_time = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
    
    logger.info(f"🔄 Iniciando tarea {task_id}")
    logger.info(f"   - 🕒 Hora inicio: {current_time}")
    logger.info(f"   - Input: {user_input[:100]}...")
    logger.info(f"   - Modelo: {model_name or 'default'}")
    logger.info(f"   - Usuario: {(conversation_id or 'N/A')[:8]}...")
    
    try:
        # Actualizar estado: PROCESANDO
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Inicializando sistema de IA...',
                'progress': 10,
                'start_time': start_time
            }
        )
        
        # Inicializar sistema de IA
        ai_system = initialize_ai_system()
        
        # Actualizar estado: CAMBIANDO MODELO (si es necesario)
        if model_name and model_name != ai_system.current_model:
            self.update_state(
                state='PROCESSING',
                meta={
                    'status': f'Cambiando a modelo {model_name}...',
                    'progress': 20,
                    'start_time': start_time
                }
            )
            
            logger.info(f"🔄 Cambiando modelo a: {model_name}")
            ai_system.switch_model(model_name)
        
        # Actualizar estado: PROCESANDO CONSULTA
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Procesando consulta con IA...',
                'progress': 40,
                'start_time': start_time
            }
        )
        
        # Procesar la consulta
        logger.info(f"🤖 Procesando consulta...")
        
        # Crear objeto pregunta compatible con process_question
        from models import Pregunta
        pregunta_obj = Pregunta(
            texto=user_input,
            userId=conversation_id or task_id,
            chatToken=conversation_id or task_id,
            history=[]  # Por ahora vacío, se podría implementar historial después
        )
        
        result = ai_system.process_question(pregunta_obj)
        
        # Agregar etiqueta del modelo a la respuesta
        model_used = ai_system.current_model
        response_with_model = f"{result}\n\n[Respuesta generada con {model_used}]"
        
        end_time = time.time()
        processing_time = end_time - start_time
        completion_time = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
        
        # Resultado final
        final_result = {
            'task_id': task_id,
            'status': 'completed',
            'response': response_with_model,  # Ahora incluye la etiqueta del modelo
            'model_used': model_used,
            'processing_time': round(processing_time, 2),
            'timestamp': datetime.utcnow().isoformat(),
            'conversation_id': conversation_id or task_id,
            'metadata': {
                'input_length': len(user_input),
                'response_length': len(response_with_model),
                'vector_db_used': ai_system.using_vector_db,
                'documents_count': len(ai_system.documentos)
            }
        }
        
        logger.info(f"✅ Tarea {task_id} completada en {processing_time:.2f}s")
        logger.info(f"   - 🕒 Hora fin: {completion_time}")
        logger.info(f"   - Modelo: {model_used}")
        logger.info(f"   - Respuesta: {len(response_with_model)} chars (con etiqueta)")
        logger.info(f"   - 📊 Performance: {len(user_input)} chars input → {len(result)} chars output (+ etiqueta)")
        
        return final_result
        
    except Exception as e:
        error_msg = f"Error procesando consulta: {str(e)}"
        logger.error(f"❌ Tarea {task_id} falló: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Actualizar estado: ERROR
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'Error en procesamiento',
                'error': error_msg,
                'progress': 0,
                'start_time': start_time
            }
        )
        
        # Re-lanzar excepción para que Celery la maneje
        raise

@celery_app.task(bind=True)
def switch_model_task(self, model_name):
    """
    Tarea asincrónica para cambiar el modelo activo
    
    Args:
        model_name (str): Nombre del modelo a activar
        
    Returns:
        dict: Estado del cambio de modelo
    """
    task_id = self.request.id
    logger.info(f"🔄 Cambiando modelo a: {model_name} (Tarea: {task_id})")
    
    try:
        # Inicializar sistema si no existe
        ai_system = initialize_ai_system()
        
        # Cambiar modelo
        ai_system.switch_model(model_name)
        
        result = {
            'task_id': task_id,
            'status': 'completed',
            'previous_model': ai_system.current_model,
            'new_model': model_name,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Modelo cambiado exitosamente a: {model_name}")
        return result
        
    except Exception as e:
        error_msg = f"Error cambiando modelo: {str(e)}"
        logger.error(f"❌ Error en tarea {task_id}: {error_msg}")
        raise

@celery_app.task
def health_check_task():
    """
    Tarea de health check para verificar el estado del worker
    
    Returns:
        dict: Estado del sistema
    """
    try:
        # Verificar conexión a Redis
        from redis import Redis
        r = Redis(host='localhost', port=6379, db=0)
        redis_status = r.ping()
        
        # Verificar sistema de IA
        ai_system = ai_system_instance
        ai_status = ai_system is not None and ai_system.is_initialized
        
        return {
            'status': 'healthy',
            'redis_connection': redis_status,
            'ai_system_initialized': ai_status,
            'current_model': ai_system.current_model if ai_system else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Health check falló: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

# ===== MANEJO DE SEÑALES CELERY =====
from celery.signals import worker_ready, worker_shutdown

@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Se ejecuta cuando el worker está listo"""
    logger.info("🚀 Worker de Celery listo - inicializando sistema de IA...")
    try:
        initialize_ai_system()
        logger.info("✅ Worker completamente inicializado")
    except Exception as e:
        logger.error(f"❌ Error inicializando worker: {e}")

@worker_shutdown.connect
def worker_shutdown_handler(sender, **kwargs):
    """Se ejecuta cuando el worker se cierra"""
    logger.info("🛑 Worker de Celery cerrándose...")

# ===== CONFIGURACIÓN PARA EJECUTAR =====
if __name__ == '__main__':
    # Ejecutar worker directamente con pool de threads para Windows
    import sys
    sys.argv = ['worker', '--loglevel=info', '--pool=threads', '--concurrency=2']
    celery_app.worker_main()
