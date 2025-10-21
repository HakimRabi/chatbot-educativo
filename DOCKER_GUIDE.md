# 🐳 Guía de Docker para Chatbot Educativo

## 📋 Archivos Creados

### Dockerfiles:
- ✅ `backend/Dockerfile` - Imagen del backend FastAPI
- ✅ `backend/Dockerfile.worker` - Imagen del worker Celery
- ✅ `frontend/Dockerfile` - Imagen del frontend con Nginx

### Configuración:
- ✅ `frontend/nginx.conf` - Configuración de Nginx con proxy al backend
- ✅ `docker-compose.yml` - Orquestación de todos los servicios
- ✅ `.env` - Variables de entorno
- ✅ `.dockerignore` - Archivos excluidos de las imágenes
- ✅ `requirements.txt` - Actualizado con dependencias de MySQL

## 🚀 Paso 1: Configuración Inicial

### 1.1 Editar el archivo `.env`

Abre el archivo `.env` y configura tu password de MySQL:

```env
MYSQL_PASSWORD=TU_PASSWORD_REAL_DE_MYSQL
SECRET_KEY=cambia-esto-por-algo-super-seguro-123456789
```

### 1.2 Verificar que los servicios locales estén corriendo

```powershell
# Verificar Ollama
ollama list

# Verificar MySQL (debe estar corriendo)
# Puedes usar MySQL Workbench o:
mysql -u root -p -e "SHOW DATABASES;"

# Si Redis Docker está corriendo, detenerlo (docker-compose lo levantará)
docker stop chatbot_redis
```

## 🔨 Paso 2: Construir las Imágenes

```powershell
# Navegar a la raíz del proyecto
cd "c:\Users\hakim\OneDrive\Desktop\backup ultima v\chatbot-educativo"

# Construir todas las imágenes (puede tardar varios minutos)
docker-compose build

# O construir cada servicio individualmente:
docker-compose build backend
docker-compose build worker
docker-compose build frontend
```

### Salida esperada:
```
[+] Building 45.2s (17/17) FINISHED
 => [backend internal] load build definition
 => => transferring dockerfile
 => [backend] Building...
 ...
 => => writing image sha256:...
 => => naming to docker.io/library/chatbot-educativo-backend
```

## 🚀 Paso 3: Levantar los Contenedores

### 3.1 Iniciar todos los servicios

```powershell
# Modo detached (en segundo plano)
docker-compose up -d

# O ver los logs en tiempo real
docker-compose up
```

### 3.2 Verificar que todo esté corriendo

```powershell
# Ver el estado de los contenedores
docker-compose ps

# Debería mostrar:
# NAME                  STATUS    PORTS
# chatbot_backend       Up        0.0.0.0:8000->8000/tcp
# chatbot_frontend      Up        0.0.0.0:80->80/tcp
# chatbot_redis         Up        0.0.0.0:6379->6379/tcp
# chatbot_worker        Up
```

### 3.3 Ver logs

```powershell
# Ver todos los logs
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f backend
docker-compose logs -f worker
docker-compose logs -f frontend
docker-compose logs -f redis
```

## ✅ Paso 4: Verificar que Funciona

### 4.1 Probar el Backend

```powershell
# Verificar conexión
curl http://localhost:8000/check_connection

# Respuesta esperada:
# {"connected":true}
```

### 4.2 Probar el Frontend

Abre tu navegador y ve a:
```
http://localhost
```

Deberías ver la interfaz del chatbot.

### 4.3 Verificar Worker Celery (Opcional)

Si levantaste Flower (monitoreo de Celery):
```powershell
docker-compose --profile monitoring up -d
```

Luego ve a: `http://localhost:5555`

## 🛠️ Comandos Útiles

### Gestión de Contenedores

```powershell
# Detener todos los contenedores
docker-compose stop

# Detener y eliminar contenedores
docker-compose down

# Detener, eliminar contenedores Y volúmenes (¡cuidado! borra datos)
docker-compose down -v

# Reiniciar un servicio específico
docker-compose restart backend
docker-compose restart worker

# Reconstruir sin caché
docker-compose build --no-cache

# Reconstruir y reiniciar un servicio
docker-compose up -d --build backend
```

### Debugging

```powershell
# Entrar a un contenedor en ejecución
docker exec -it chatbot_backend bash
docker exec -it chatbot_worker bash

# Ver uso de recursos
docker stats

# Ver logs con timestamps
docker-compose logs -f --timestamps backend

# Ver solo los últimos 100 logs
docker-compose logs --tail=100 backend
```

### Limpieza

```powershell
# Eliminar imágenes no utilizadas
docker image prune -a

# Eliminar volúmenes no utilizados
docker volume prune

# Limpieza completa del sistema Docker
docker system prune -a --volumes
```

## 🔍 Troubleshooting

### Problema: No se puede conectar a MySQL

**Solución:**
1. Verifica que MySQL esté corriendo localmente
2. Verifica que el puerto 3306 esté abierto
3. Verifica el password en `.env`
4. En el contenedor, `host.docker.internal` debe apuntar al host

```powershell
# Probar conexión desde el contenedor
docker exec -it chatbot_backend bash
apt-get update && apt-get install -y mysql-client
mysql -h host.docker.internal -u root -p
```

### Problema: No se puede conectar a Ollama

**Solución:**
1. Verifica que Ollama esté corriendo: `ollama list`
2. Verifica que esté en el puerto 11434
3. Prueba desde el contenedor:

```powershell
docker exec -it chatbot_backend bash
curl http://host.docker.internal:11434/api/tags
```

### Problema: Error al construir imágenes

**Solución:**
1. Limpia la caché de Docker:
```powershell
docker-compose build --no-cache
```

2. Verifica que no haya archivos grandes en el contexto:
```powershell
# Ver tamaño del contexto
Get-ChildItem -Recurse | Measure-Object -Property Length -Sum
```

### Problema: Contenedor se detiene inmediatamente

**Solución:**
```powershell
# Ver logs para identificar el error
docker-compose logs backend
docker-compose logs worker

# Verificar configuración
docker-compose config
```

## 📊 Monitoreo

### Ver métricas en tiempo real

```powershell
# CPU, RAM, Network de todos los contenedores
docker stats

# Solo un contenedor
docker stats chatbot_backend
```

### Flower (Monitoreo de Celery)

```powershell
# Levantar con Flower
docker-compose --profile monitoring up -d

# Acceder a: http://localhost:5555
```

## 🎯 Siguiente Paso: Subir a AWS ECR

Una vez que verifiques que todo funciona localmente, estamos listos para:

1. ✅ Las imágenes Docker están construidas y funcionando
2. 🔜 Configurar AWS CLI
3. 🔜 Autenticar con Amazon ECR
4. 🔜 Push de las imágenes a ECR
5. 🔜 Desplegar en AWS (ECS/Fargate)

## 📝 Notas Importantes

- Los PDFs en `backend/data/pdfs` están incluidos en la imagen
- Los datos de ChromaDB y FAISS se persisten en volúmenes
- Redis data se persiste en el volumen `chatbot-educativo_redis_data`
- El backend y worker comparten los mismos volúmenes de datos
- Ollama y MySQL se mantienen en el host (no dockerizados)

## 🔐 Seguridad

Antes de ir a producción:
- ✅ Cambiar `SECRET_KEY` en `.env`
- ✅ Cambiar passwords de bases de datos
- ✅ No commitear el archivo `.env` al repositorio
- ✅ Usar secrets de Docker/AWS para credenciales sensibles
- ✅ Configurar HTTPS en Nginx
- ✅ Configurar firewall y security groups en AWS
