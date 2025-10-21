@echo off
REM Script para ejecutar pruebas de carga SINCRONAS + GPU
REM Instala dependencias y ejecuta el test sincrónico optimizado para GPU

echo ========================================
echo   PRUEBAS DE CARGA SINCRONAS + GPU
echo   Chatbot Educativo - Test de Rendimiento
echo ========================================

echo.
echo [1/3] Verificando e instalando dependencias...
pip install -r ..\requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)

echo [2/3] Verificando estado del servidor...
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

echo [3/3] Ejecutando pruebas de carga SINCRONAS + GPU...
echo.
echo Configuracion:
echo   - Arquitectura: Sincrona (FastAPI directo)
echo   - GPU: Habilitada con monitoreo pynvml
echo   - Usuarios: 1, 5, 10, 20 (simultaneos)
echo   - Modelo: ollama3
echo   - Endpoint: /preguntar
echo.

python sync_gpu_load_test.py --url http://localhost:8000 --users 1 5 10 20

echo.
echo ========================================
echo Pruebas SINCRONAS + GPU completadas
echo Revisa los archivos .json generados
echo ========================================
pause