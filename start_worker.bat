@echo off
REM ================================================================
REM  CELERY WORKER - CHATBOT EDUCATIVO
REM  Ejecuta el worker Celery para procesar tareas asincrónicas
REM ================================================================

echo.
echo ================================================================
echo   🚀 INICIANDO CELERY WORKER - CHATBOT EDUCATIVO
echo ================================================================
echo.

REM Cambiar al directorio backend
cd /d "%~dp0backend"

REM Verificar que el archivo celery_worker.py existe
if not exist "celery_worker.py" (
    echo ❌ ERROR: No se encuentra celery_worker.py en el directorio backend
    echo 📁 Directorio actual: %CD%
    pause
    exit /b 1
)

REM ================================================================
REM  CONFIGURACIÓN OPTIMIZADA PARA PRODUCCIÓN
REM ================================================================
set CELERY_WORKER_PREFETCH_MULTIPLIER=1
set CELERY_WORKER_MAX_TASKS_PER_CHILD=100
set CELERY_WORKER_MAX_MEMORY_PER_CHILD=200000
set CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=True
set CELERY_TASK_ACKS_LATE=True
set CELERY_WORKER_DISABLE_RATE_LIMITS=True

REM Mostrar información del worker
echo 📋 Configuración del Worker OPTIMIZADA:
echo    - Pool: threads (optimizado para I/O)
echo    - Concurrency: 4 workers (optimizado para RTX 3060)
echo    - Prefetch: 1 (evita sobrecarga)
echo    - Max tasks per child: 100
echo    - Log Level: info
echo    - App: celery_worker
echo.

REM Ejecutar el worker Celery OPTIMIZADO
echo 🔄 Iniciando 4 workers optimizados...
echo.
python -m celery -A celery_worker worker --loglevel=info --pool=threads --concurrency=4

REM Si llega aquí, el worker se cerró
echo.
echo ⚠️ Worker Celery se ha cerrado
pause
