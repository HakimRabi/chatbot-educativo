@echo off
REM Script para ejecutar pruebas de carga ASINCRONAS + GPU  
REM Instala dependencias y ejecuta el test asíncrono con workers Celery + GPU

echo ==========================================
echo   PRUEBAS DE CARGA ASINCRONAS + GPU
echo   Chatbot Educativo - Test Worker + GPU
echo ==========================================

echo.
echo [1/4] Verificando e instalando dependencias...
pip install -r ..\requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)

echo [2/4] Verificando estado del servidor...
curl -s "http://localhost:8000/check_connection" >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: No se puede conectar al servidor en localhost:8000
    echo         Asegurate de que el servidor este ejecutandose
    echo.
    echo Continuar de todas formas? [S/N]
    set /p continue=
    if /i "%continue%" neq "S" (
        echo Cancelado por el usuario
        pause
        exit /b 1
    )
)

echo [3/4] Verificando worker Celery...
curl -s -X POST "http://localhost:8000/chat/async" -H "Content-Type: application/json" -d "{\"texto\":\"test\",\"modelo\":\"ollama3\"}" >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: El endpoint asincrono podria no estar disponible
    echo          Asegurate de que el worker Celery este ejecutandose
    echo          Ejecuta: start_worker.bat
    echo.
    echo Continuar de todas formas? [S/N]
    set /p continue=
    if /i "%continue%" neq "S" (
        echo Cancelado por el usuario
        pause
        exit /b 1
    )
)

echo [4/4] Ejecutando pruebas de carga ASINCRONAS + GPU...
echo.
echo Configuracion:
echo   - Arquitectura: Asincrona (Celery Worker)
echo   - GPU: Habilitada con monitoreo pynvml
echo   - Usuarios: 1, 5, 10, 20 (simultaneos)
echo   - Modelo: ollama3
echo   - Endpoints: /chat/async + /chat/status/{task_id}
echo.

python async_gpu_load_test.py --url http://localhost:8000 --users 1 5 10 20

echo.
echo ==========================================
echo Pruebas ASINCRONAS + GPU completadas
echo Revisa los archivos .json generados
echo ==========================================
pause