FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements PROD (más ligero y rápido)
COPY backend/requirements-prod.txt ./requirements.txt

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Invalidar cache para forzar recopia de archivos actualizados
ARG BUILD_DATE
RUN echo "Build date: ${BUILD_DATE}"

# Copiar código del backend
COPY backend/ .

# Limpiar __pycache__ para evitar usar archivos .pyc viejos
RUN find . -type d -name __pycache__ -exec rm -rf {} + || true
RUN find . -type f -name "*.pyc" -delete || true

# TEMPORAL: PDFs deshabilitados para testing rápido
# RUN if [ -d "data/pdfs" ]; then cp -r data/pdfs/* /app/data/pdfs/ || true; fi
RUN mkdir -p /app/data/pdfs

# Crear directorios necesarios
RUN mkdir -p data/cache data/chroma_db data/faiss_index data/pdfs

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/check_connection || exit 1

# Comando de inicio
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
