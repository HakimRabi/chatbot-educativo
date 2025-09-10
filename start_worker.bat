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

REM Mostrar información del worker
echo 📋 Configuración del Worker:
echo    - Pool: threads (compatible Windows)
echo    - Concurrency: 2 workers
echo    - Log Level: info
echo    - App: celery_worker
echo.

REM Ejecutar el worker Celery
echo 🔄 Iniciando worker...
echo.
python -m celery -A celery_worker worker --loglevel=info --pool=threads --concurrency=2

REM Si llega aquí, el worker se cerró
echo.
echo ⚠️ Worker Celery se ha cerrado
pause
