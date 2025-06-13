# Chatbot Educativo - UNAB IA Mentor

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg) 
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg) 
![LangChain](https://img.shields.io/badge/LangChain-Integrado-purple.svg) 
![Ollama](https://img.shields.io/badge/Ollama-Llama%203-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

Asistente académico inteligente diseñado para apoyar a estudiantes del curso "Fundamentos de Inteligencia Artificial" de la Universidad Andrés Bello. El sistema utiliza modelos de lenguaje locales (LLM) a través de Ollama y técnicas de Retrieval-Augmented Generation (RAG) para responder preguntas basadas en el material académico del curso.

## 📋 Tabla de Contenidos
- [Características Principales](#-características-principales)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Stack Tecnológico](#-stack-tecnológico)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [API Documentation](#-api-documentation)
- [Contribución](#-contribución)
- [Licencia](#-licencia)
- [Autores](#-autores)

## 🚀 Características Principales

### 🧠 Sistema RAG Avanzado
- **Base de conocimientos vectorial**: Utiliza ChromaDB para búsqueda semántica
- **Procesamiento de PDFs**: Indexación automática de documentos académicos (syllabus del curso)
- **Respuestas contextualizadas**: Genera respuestas basadas en el material del curso CINF103

### 🤖 IA Local y Privada
- **Ollama Integration**: Soporte para múltiples modelos (Llama 3, Mistral, etc.)
- **Privacidad total**: Todo el procesamiento ocurre localmente
- **Sin dependencias de APIs externas**: Funciona completamente offline

### 👤 Gestión de Usuarios
- **Autenticación segura**: Sistema de registro e inicio de sesión con hash de contraseñas
- **Historial personalizado**: Cada usuario mantiene su propio historial de conversaciones
- **Sesiones persistentes**: Las conversaciones se guardan automáticamente en MySQL

### ⭐ Sistema de Feedback
- **Calificación de respuestas**: Sistema de 5 estrellas para evaluar respuestas
- **Comentarios detallados**: Los usuarios pueden dejar feedback específico
- **Dashboard de analytics**: Panel para revisar métricas y estadísticas

### 💡 Funcionalidades Inteligentes
- **Análisis de intención**: Detecta el tipo de pregunta y adapta la respuesta
- **Sugerencias dinámicas**: Propone preguntas de seguimiento relevantes
- **Renderizado Markdown**: Respuestas formateadas para mejor legibilidad
- **Sistema de templates**: Templates dinámicos para diferentes tipos de respuesta

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Frontend     │    │   FastAPI       │    │     Ollama      │
│   (HTML/JS)     │◄──►│    Backend      │◄──►│   (LLM Local)   │
│                 │    │                 │    │                 │
│ • Chat UI       │    │ • Auth System   │    │ • Llama 3       │
│ • Dashboard     │    │ • RAG Pipeline  │    │ • Mistral       │
│ • Login System  │    │ • API Endpoints │    │ • Custom Models │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │
                               ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │     MySQL       │    │   ChromaDB      │
                    │                 │    │                 │
                    │ • Users         │    │ • Vector Store  │
                    │ • Conversations │    │ • PDF Content   │
                    │ • Feedback      │    │ • Embeddings    │
                    │ • Sessions      │    │ • Semantic Search│
                    └─────────────────┘    └─────────────────┘
```

## 🛠️ Stack Tecnológico

### Backend
- **FastAPI**: Framework web moderno y rápido para APIs
- **LangChain**: Orquestación de LLM y pipeline RAG
- **SQLAlchemy**: ORM para manejo de base de datos
- **Ollama**: Interface para modelos de lenguaje locales
- **ChromaDB**: Base de datos vectorial para embeddings
- **PyPDF**: Procesamiento y extracción de texto de PDFs

### Frontend
- **HTML5/CSS3**: Estructura y estilos modernos con diseño responsivo
- **JavaScript Vanilla**: Lógica del cliente sin frameworks externos
- **Marked.js**: Renderizado de Markdown en tiempo real
- **SweetAlert2**: Modales y notificaciones elegantes

### Bases de Datos
- **MySQL**: Almacenamiento de usuarios, conversaciones y feedback
- **ChromaDB**: Base de datos vectorial para búsqueda semántica

### Librerías Principales
```
fastapi
langchain-ollama
chromadb
sqlalchemy
mysql-connector-python
pypdf
passlib[bcrypt]
python-dotenv
uvicorn
```

## 📦 Instalación

### Prerrequisitos

1. **Python 3.9+**
2. **Ollama**: [Descargar e instalar](https://ollama.com/)
3. **MySQL Server 8.0+**
4. **Git**

### Pasos de Instalación

1. **Clonar el repositorio**
```bash
git clone https://github.com/tu-usuario/chatbot-educativo.git
cd chatbot-educativo
```

2. **Crear entorno virtual**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Instalar modelo Ollama**
```bash
ollama pull llama3
# Modelos alternativos
ollama pull mistral
ollama pull codellama
```

## ⚙️ Configuración

### 1. Variables de Entorno

Crear archivo `.env` en la carpeta `backend`:

```env
# Base de Datos MySQL
DB_USER=tu_usuario_mysql
DB_PASSWORD=tu_password_mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=bd_chatbot

# Configuración del Modelo Ollama
OLLAMA_MODEL=llama3
OLLAMA_URL=http://localhost:11434

# Configuración de la Aplicación
SECRET_KEY=tu_clave_secreta_muy_segura_aqui
DEBUG=True
CACHE_TTL=3600
```

### 2. Base de Datos MySQL

```sql
CREATE DATABASE bd_chatbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Documentos PDF

Coloca el syllabus y documentos académicos en `/backend/data/pdfs/`. El sistema los indexará automáticamente.

## 🚀 Uso

### Método 1: Usando el script batch (Windows)

```bash
# Desde la raíz del proyecto
startAPI.bat
```

### Método 2: Manual

```bash
# Asegúrate de que Ollama esté ejecutándose
ollama serve

# Navegar al backend e iniciar servidor
cd backend
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Acceder a la Aplicación

1. **Frontend**: `http://localhost:8000` 
2. **Login**: `http://localhost:8000/pages/login.html`
3. **Dashboard**: `http://localhost:8000/pages/dashboard.html`
4. **API Docs**: `http://localhost:8000/docs`

### Funcionalidades Disponibles

- **💬 Chat Inteligente**: Pregunta sobre contenidos del curso CINF103
- **📚 Base de Conocimientos**: Respuestas basadas en el syllabus oficial
- **📊 Dashboard**: Visualiza estadísticas y métricas de uso
- **⭐ Sistema de Feedback**: Califica respuestas para mejorar el sistema
- **🔍 Búsqueda Semántica**: Encuentra información relevante automáticamente

## 📁 Estructura del Proyecto

```
chatbot-educativo/
├── 📁 backend/
│   ├── 🐍 app.py                    # Servidor FastAPI principal
│   ├── 🧠 ai_system.py              # Sistema RAG y procesamiento IA
│   ├── 🔐 auth.py                   # Sistema de autenticación
│   ├── 💬 chat.py                   # Lógica del chat y conversaciones
│   ├── ⚙️ config.py                 # Configuración y variables
│   ├── 📊 dashboard.py              # Endpoints del dashboard
│   ├── 🗃️ models.py                # Modelos de base de datos SQLAlchemy
│   ├── 📋 templates.py              # Sistema de templates dinámicos
│   ├── 🛠️ utils.py                  # Utilidades y funciones auxiliares
│   └── 📁 data/
│       ├── 📁 cache/                # Caché de respuestas
│       ├── 📁 chroma_db/            # Base de datos vectorial ChromaDB
│       └── 📁 pdfs/                 # Documentos fuente (Syllabus CINF103)
├── 📁 frontend/
│   ├── 🌐 index.html                # Página principal del chat
│   ├── 📁 pages/
│   │   ├── 🔐 login.html            # Página de autenticación
│   │   └── 📊 dashboard.html        # Panel de control y estadísticas
│   └── 📁 assets/
│       ├── 📁 css/
│       │   ├── 💬 index.css         # Estilos del chat
│       │   ├── 🔐 login.css         # Estilos del login
│       │   └── 📊 dashboard.css     # Estilos del dashboard
│       └── 📁 js/
│           ├── 💬 chat.js           # Lógica del chat
│           ├── 🔐 login.js          # Lógica del login
│           └── 📊 dashboard.js      # Lógica del dashboard
├── 🚀 startAPI.bat                  # Script de inicio rápido (Windows)
├── 🔧 .env                          # Variables de entorno
├── 📋 requirements.txt              # Dependencias Python
└── 📖 README.md                     # Este archivo
```

## 📚 API Documentation

Documentación interactiva disponible en:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Endpoints Principales

#### Autenticación
- `POST /auth/register` - Registro de nuevos usuarios
- `POST /auth/login` - Inicio de sesión
- `POST /auth/logout` - Cerrar sesión

#### Chat y Conversaciones
- `POST /chat/message` - Enviar mensaje al chatbot
- `GET /chat/history/{user_id}` - Obtener historial del usuario
- `POST /chat/new-session` - Crear nueva sesión de chat

#### Dashboard y Analytics
- `GET /dashboard/stats/{user_id}` - Estadísticas del usuario
- `GET /dashboard/feedback-summary` - Resumen de feedback

#### Feedback
- `POST /feedback` - Enviar calificación y comentarios

## 🤝 Contribución

¡Las contribuciones son bienvenidas! Sigue estos pasos:

1. Fork el proyecto
2. Crea una rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

### Roadmap Futuro

- [ ] 🔄 Sistema de caché inteligente para respuestas frecuentes
- [ ] 📄 Soporte para documentos Word (.docx) y texto plano
- [ ] 🌐 API REST pública con autenticación JWT
- [ ] 🐳 Containerización con Docker
- [ ] ☁️ Despliegue en la nube (AWS/GCP/Azure)
- [ ] 📱 Aplicación móvil nativa
- [ ] 🔍 Búsqueda avanzada con filtros temporales
- [ ] 🎨 Temas personalizables para la interfaz

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para más detalles.

---

## 👥 Autores

### **Creado por:**

**🎓 Luis Marcano**  
**🎓 Hakim Rabi**  
**🎓 Luciano Aguilar**

---

### 🏛️ **Universidad Andrés Bello - Chile**
### 📚 **Proyecto de Título - Ingeniería Civil Informática**

---

## 📞 Contacto y Enlaces

**🔗 Proyecto**: [https://github.com/HakimRabi/chatbot-educativo](https://github.com/HakimRabi/chatbot-educativo)

**🏫 Universidad**: [Universidad Andrés Bello](https://www.unab.cl/)

---

### 💡 Sobre el Proyecto

*Este chatbot educativo representa la culminación de nuestro proyecto de título en Ingeniería Civil Informática. Desarrollado específicamente para el curso CINF103 de la Universidad Andrés Bello, demuestra la implementación práctica de sistemas RAG (Retrieval-Augmented Generation) y modelos de lenguaje locales en el ámbito educativo chileno.*

*El sistema procesa el syllabus oficial del curso y otros materiales académicos para proporcionar asistencia inteligente a los estudiantes, manteniendo la privacidad de los datos mediante el uso de modelos locales a través de Ollama.*

---

### ⚡ Quick Start

```bash
# Instalación ultra-rápida
git clone https://github.com/tu-usuario/chatbot-educativo.git
cd chatbot-educativo

# Setup automático
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# Configurar variables de entorno (.env)
# Configurar base de datos MySQL
# Colocar syllabus en /backend/data/pdfs/

# ¡Listo para usar!
ollama serve
startAPI.bat
```

**🚀 ¡Ya tienes tu asistente IA educativo funcionando!**

---

*Desarrollado con ❤️ para la comunidad educativa de la Universidad Andrés Bello*

**© 2025 - Proyecto de Título UNAB - Ingeniería Civil Informática**
