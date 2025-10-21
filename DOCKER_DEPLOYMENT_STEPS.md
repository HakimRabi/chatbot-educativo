# 📋 Plan de Despliegue Docker → AWS ECR

## ✅ Fase 1: Preparación (COMPLETADO)

### Archivos Docker Creados:
1. **backend/Dockerfile** - Imagen del backend FastAPI
   - Base: Python 3.11-slim
   - Incluye: MySQL libs, build tools, PDFs
   - Puerto: 8000

2. **backend/Dockerfile.worker** - Imagen del Celery worker
   - Base: Python 3.11-slim
   - Configuración: --pool=solo --concurrency=2

3. **frontend/Dockerfile** - Imagen del frontend Nginx
   - Base: nginx:alpine
   - Sirve archivos estáticos y proxy al backend

4. **docker-compose.yml** - Orquestación de servicios
   - Redis (broker de Celery)
   - Backend (FastAPI)
   - Worker (Celery)
   - Frontend (Nginx)
   - Flower (opcional, monitoreo Celery)

5. **frontend/nginx.conf** - Configuración de Nginx
   - Reverse proxy a backend:8000
   - Manejo de rutas /api/, /auth/, /chat/, /preguntar
   - Health checks

6. **.env** - Variables de entorno
7. **.dockerignore** - Optimización del build

### Dependencias Actualizadas:
- ✅ numpy==1.26.4 (compatible con langchain)
- ✅ langchain==0.3.13 (versión actualizada)
- ✅ langchain-ollama==0.2.3
- ✅ langchain-community==0.3.13
- ✅ pymysql==1.1.1
- ✅ sqlalchemy==2.0.32
- ✅ cryptography==42.0.8

## 🔄 Fase 2: Build de Imágenes (EN PROGRESO)

### Estado Actual:
```bash
docker-compose build --no-cache
```
**Status**: Instalando dependencias del sistema (gcc, g++, MySQL libs)
**Progreso**: ~20% completado
**Tiempo estimado**: 5-10 minutos más

### Lo que está sucediendo ahora:
1. ✅ Descargando imágenes base (Python 3.11-slim)
2. 🔄 Instalando paquetes del sistema (build-essential, gcc, g++, curl)
3. 🔄 Instalando librerías MySQL (MariaDB client libraries)
4. ⏳ Pendiente: pip install requirements.txt (~500MB de paquetes Python)
5. ⏳ Pendiente: Copiar código backend y PDFs
6. ⏳ Pendiente: Build de frontend (Nginx - rápido)

## 📊 Fase 3: Pruebas Locales (PRÓXIMO)

### Pasos a seguir después del build:

1. **Verificar imágenes creadas:**
   ```powershell
   docker images
   ```
   Deberías ver:
   - chatbot-educativo-backend
   - chatbot-educativo-worker
   - chatbot-educativo-frontend

2. **Iniciar los contenedores:**
   ```powershell
   docker-compose up -d
   ```

3. **Verificar estado de los servicios:**
   ```powershell
   docker-compose ps
   docker-compose logs backend
   docker-compose logs worker
   ```

4. **Probar endpoints:**
   - Backend health: `http://localhost:8000/check_connection`
   - Frontend: `http://localhost`
   - Flower (opcional): `http://localhost:5555`

5. **Verificar logs:**
   ```powershell
   # Ver todos los logs
   docker-compose logs -f
   
   # Ver logs de un servicio específico
   docker-compose logs -f backend
   docker-compose logs -f worker
   ```

## 🚀 Fase 4: Despliegue a AWS ECR (PENDIENTE)

### Pre-requisitos:
- [ ] AWS CLI instalado
- [ ] Credenciales AWS configuradas
- [ ] Cuenta AWS con acceso a ECR

### 4.1. Configurar AWS CLI:
```powershell
# Instalar AWS CLI (si no está instalado)
# Descargar de: https://aws.amazon.com/cli/

# Configurar credenciales
aws configure
# AWS Access Key ID: [TU_ACCESS_KEY]
# AWS Secret Access Key: [TU_SECRET_KEY]
# Default region name: us-east-1
# Default output format: json
```

### 4.2. Obtener Account ID:
```powershell
aws sts get-caller-identity --query Account --output text
```

### 4.3. Autenticar Docker con ECR:
```powershell
# Reemplazar REGION y ACCOUNT_ID con tus valores
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

### 4.4. Crear repositorios ECR:
```powershell
# Backend
aws ecr create-repository --repository-name chatbot-educativo-backend --region us-east-1

# Worker
aws ecr create-repository --repository-name chatbot-educativo-worker --region us-east-1

# Frontend
aws ecr create-repository --repository-name chatbot-educativo-frontend --region us-east-1
```

### 4.5. Etiquetar imágenes:
```powershell
# Reemplazar ACCOUNT_ID con tu Account ID de AWS
$ACCOUNT_ID = "TU_ACCOUNT_ID_AQUI"
$REGION = "us-east-1"

# Backend
docker tag chatbot-educativo-backend:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/chatbot-educativo-backend:latest

# Worker
docker tag chatbot-educativo-worker:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/chatbot-educativo-worker:latest

# Frontend
docker tag chatbot-educativo-frontend:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/chatbot-educativo-frontend:latest
```

### 4.6. Push a ECR:
```powershell
# Backend
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/chatbot-educativo-backend:latest

# Worker
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/chatbot-educativo-worker:latest

# Frontend
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/chatbot-educativo-frontend:latest
```

## 📝 Notas Importantes

### Arquitectura de Conexiones:
- **MySQL**: Local en Windows (host.docker.internal:3306)
- **Ollama**: Local en Windows (http://host.docker.internal:11434)
- **Redis**: Contenedor Docker (redis:7.2-alpine)
- **PDFs**: Incluidos en la imagen del backend

### Volúmenes de Datos:
```yaml
volumes:
  - ./backend/data/chroma_db:/app/data/chroma_db
  - ./backend/data/faiss_index:/app/data/faiss_index
  - ./backend/data/cache:/app/data/cache
```

### Puertos Expuestos:
- **Frontend**: 80 → Nginx
- **Backend**: 8000 → FastAPI
- **Redis**: 6379 → Broker
- **Flower**: 5555 → Monitoreo (opcional)

## 🔍 Troubleshooting

### Error: Cannot connect to MySQL
- Verificar que MySQL Server esté corriendo en Windows
- Verificar password en .env: `MYSQL_PASSWORD=tu_password`
- Verificar host: debe ser `host.docker.internal` no `localhost`

### Error: Cannot connect to Ollama
- Verificar que Ollama esté corriendo: `ollama list`
- Verificar URL: `http://host.docker.internal:11434`

### Build muy lento
- Normal en la primera vez (descarga ~2GB de paquetes)
- Usar `docker-compose build --parallel` para builds paralelos

### Worker no procesa tareas
- Verificar logs: `docker-compose logs worker`
- Verificar Redis: `docker-compose logs redis`
- Verificar que worker tenga acceso a los PDFs

## 📊 Próximos Pasos Después de ECR

Una vez las imágenes estén en ECR:
1. **AWS ECS** - Elastic Container Service (recomendado)
2. **AWS EKS** - Kubernetes (para escala mayor)
3. **AWS Fargate** - Sin gestión de servidores
4. **EC2** - Máquinas virtuales tradicionales

## 🎯 Estado Actual

**FASE ACTUAL**: Fase 2 - Build de Imágenes (20% completado)
**ACCIÓN REQUERIDA**: Esperar a que termine `docker-compose build`
**TIEMPO ESTIMADO**: 5-10 minutos
**SIGUIENTE PASO**: Pruebas locales con `docker-compose up -d`
