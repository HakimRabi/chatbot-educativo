@echo off
echo Configurando Ollama para RTX 3060...
set OLLAMA_GPU_MEMORY_FRACTION=0.85
set OLLAMA_NUM_PARALLEL=2
set OLLAMA_MAX_LOADED_MODELS=1
set OLLAMA_NUM_THREAD=8
set OLLAMA_KEEP_ALIVE=10m
set OLLAMA_HOST=0.0.0.0:11434
set CUDA_VISIBLE_DEVICES=0
echo Reiniciando Ollama con nueva configuracion...
taskkill /F /IM ollama.exe >nul 2>&1
timeout /t 2 >nul
start "" ollama serve
echo Ollama optimizado iniciado
