# UNAB-IA Mentor v0.4.7

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg) ![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg) ![LangChain](https://img.shields.io/badge/LangChain-Integrado-purple.svg) ![Ollama](https://img.shields.io/badge/Ollama-Llama%203-orange.svg)

Asistente académico inteligente diseñado para apoyar a estudiantes del curso "Fundamentos de Inteligencia Artificial" de la Universidad Andrés Bello. El sistema utiliza un modelo de lenguaje local (LLM) a través de Ollama y técnicas de Retrieval-Augmented Generation (RAG) para responder preguntas basadas en el material académico del curso.

## Tabla de Contenidos
1.  [Acerca del Proyecto](#acerca-del-proyecto)
2.  [Características Principales](#características-principales)
3.  [Arquitectura del Sistema](#arquitectura-del-sistema)
4.  [Stack Tecnológico](#stack-tecnológico)
5.  [Instalación y Puesta en Marcha](#instalación-y-puesta-en-marcha)
    * [Prerrequisitos](#prerrequisitos)
    * [Configuración del Backend](#configuración-del-backend)
    * [Configuración del Frontend](#configuración-del-frontend)
6.  [Uso del Chatbot](#uso-del-chatbot)
7.  [Estructura del Proyecto](#estructura-del-proyecto)
8.  [Futuras Mejoras](#futuras-mejoras)
9.  [Licencia](#licencia)

## Acerca del Proyecto

**UNAB-IA Mentor** nace como una herramienta de apoyo educativo para resolver dudas y facilitar el aprendizaje de los conceptos clave de la inteligencia artificial. El chatbot está conectado a una base de conocimientos documental (archivos PDF del curso) y es capaz de:
* Responder preguntas específicas sobre el contenido del syllabus y material de estudio.
* Mantener el contexto de la conversación para un diálogo fluido y natural.
* Adaptar el estilo y la profundidad de sus respuestas según la intención del usuario.

## Características Principales

* **🧠 Sistema RAG (Retrieval-Augmented Generation):** Utiliza una base de datos vectorial (ChromaDB con fallback a FAISS) para encontrar los fragmentos de texto más relevantes de los documentos PDF y así generar respuestas precisas y contextualizadas.
* **🤖 LLM Local con Ollama:** Integra el modelo Llama 3 (u otros compatibles con Ollama), garantizando la privacidad y el control total sobre el motor de IA.
* **🔍 Análisis de Intención y Complejidad:** El sistema analiza cada pregunta para determinar la intención del usuario (ej. definición, comparación, ejemplo) y la complejidad de la respuesta requerida, seleccionando la plantilla de prompt más adecuada para una respuesta de alta calidad.
* **🔐 Autenticación y Sesiones de Usuario:** Incluye un sistema de registro e inicio de sesión. Las conversaciones son guardadas y asociadas a cada usuario en una base de datos MySQL, permitiendo consultar el historial.
* **⭐️ Sistema de Feedback:** Los usuarios pueden calificar las respuestas del bot (1 a 5 estrellas) y dejar comentarios, lo que permite la recolección de datos para futuras mejoras del modelo.
* **💡 Sugerencias Dinámicas:** Después de cada respuesta, el bot propone preguntas de seguimiento para guiar al usuario y facilitar la exploración de temas relacionados.
* **🎨 Frontend Interactivo:** Interfaz de chat limpia y moderna construida con HTML, CSS y JavaScript, con renderizado de Markdown para una mejor legibilidad de las respuestas.

## Arquitectura del Sistema

El proyecto sigue una arquitectura cliente-servidor desacoplada:

1.  **Frontend:** Una aplicación web estática (HTML, CSS, JS) que se comunica con el backend a través de peticiones HTTP.
2.  **Backend (FastAPI):** Un servidor API que recibe las preguntas del usuario.
3.  **Capa de Orquestación (LangChain):** Gestiona la lógica de RAG, la selección de prompts y la interacción con el LLM.
4.  **Motor de IA (Ollama):** Ejecuta el modelo de lenguaje Llama 3 de forma local.
5.  **Base de Datos Vectorial (Chroma/FAISS):** Almacena y permite la búsqueda de los embeddings de los documentos.
6.  **Base de Datos Relacional (MySQL):** Persiste la información de usuarios, sesiones e historial de chat.

## Stack Tecnológico

* **Backend:** Python, FastAPI, LangChain, SQLAlchemy
* **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
* **LLM:** Ollama (Llama 3)
* **Bases de Datos:**
    * MySQL (Datos de usuario y conversaciones)
    * ChromaDB / FAISS (Base de datos vectorial)
* **Librerías Clave:** `pydantic`, `passlib`, `python-dotenv`, `marked.js`, `sweetalert2`

## Instalación y Puesta en Marcha

Sigue estos pasos para ejecutar el proyecto en tu entorno local.

### Prerrequisitos

* **Python 3.9+**
* **Ollama instalado y ejecutándose:** [Descargar Ollama](https://ollama.com/)
* **Modelo Llama 3:** Ejecuta `ollama pull llama3` en tu terminal.
* **Servidor MySQL** instalado y accesible.

### Configuración del Backend

1.  **Clona el repositorio:**
    ```bash
    git clone [https://github.com/tu-usuario/unab-ia-mentor.git](https://github.com/tu-usuario/unab-ia-mentor.git)
    cd unab-ia-mentor
    ```

2.  **Crea un entorno virtual y actívalo:**
    ```bash
    python -m venv venv
    # En Windows
    venv\Scripts\activate
    # En macOS/Linux
    source venv/bin/activate
    ```

3.  **Crea el archivo `requirements.txt`** con el siguiente contenido:
    ```txt
    fastapi
    uvicorn[standard]
    sqlalchemy
    mysql-connector-python
    langchain
    langchain-community
    langchain-ollama
    pypdf
    faiss-cpu
    chromadb
    passlib[bcrypt]
    python-dotenv
    ```

4.  **Instala las dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Crea un archivo `.env`** en la raíz del proyecto y configúralo con tus credenciales de MySQL:
    ```env
    DB_USER="tu_usuario_mysql"
    DB_PASSWORD="tu_password_mysql"
    DB_HOST="127.0.0.1"
    DB_PORT="3306"
    DB_NAME="bd_chatbot"
    ```

6.  **Crea la base de datos `bd_chatbot`** en tu servidor MySQL. Las tablas se crearán automáticamente al iniciar la aplicación por primera vez.

7.  **Añade tus documentos:** Coloca los archivos PDF que servirán como base de conocimiento en la carpeta `/pdfs/`.

8.  **Inicia el servidor:**
    ```bash
    uvicorn app:app --reload
    ```
    El backend estará disponible en `http://localhost:8000`.

### Configuración del Frontend

No requiere pasos adicionales. Simplemente abre `http://localhost:8000` en tu navegador, ya que FastAPI está configurado para servir el archivo `index.html` en la ruta raíz.

## Uso del Chatbot

1.  **Registro/Login:** La primera vez, regístrate con un nombre, email y contraseña. Luego, inicia sesión.
2.  **Interfaz de Chat:** Se presentará la ventana principal del chat.
3.  **Realiza una pregunta:** Escribe tu pregunta en el campo de texto y presiona "Enviar" o la tecla Enter.
4.  **Usa las sugerencias:** Haz clic en los botones de sugerencia para explorar temas relacionados.
5.  **Califica las respuestas:** Usa el sistema de estrellas para dar tu feedback sobre la utilidad de cada respuesta.
6.  **Gestiona tus conversaciones:** Usa los botones "Nueva conversación" para empezar de cero o "Historial" para ver y cargar chats anteriores.

## Estructura del Proyecto
/chatbot-educativo/
├── /backend/
│   ├── app.py                     # Lógica principal del backend (FastAPI)
│   ├── ai_system.py               # Lógica del sistema de IA (RAG, LLM)
│   ├── models.py                  # Modelos de base de datos (SQLAlchemy)
│   ├── requirements.txt           # Dependencias de Python
│   └── ...                        # Otros módulos y archivos de configuración del backend
├── /frontend/
│   ├── index.html                 # Página principal del chat
│   ├── login.html                 # Página de inicio de sesión
│   ├── /assets/
│   │   ├── /css/
│   │   │   └── style.css          # Hojas de estilo (ej. style.css, index.css)
│   │   ├── /js/
│   │   │   ├── chat.js            # Lógica del chat en el frontend
│   │   │   ├── login.js           # Lógica del login en el frontend
│   │   │   └── ...                # Otros scripts JS
│   │   └── /img/                  # (Opcional) Imágenes y otros recursos estáticos
│   ├── /pages/                    # (Opcional) Otras páginas HTML (ej. about.html)
│   │   └── ...
├── /pdfs/                         # Documentos PDF fuente para el RAG
│   └── tu_documento.pdf
├── /chroma_db/                    # Base de datos vectorial (generada por ChromaDB)
├── .env                           # Variables de entorno (configuración local)
├── .gitignore                     # Archivos y carpetas a ignorar por Git
└── README.md                      # Este archivo


## Futuras Mejoras

- [ ] Implementar un sistema de caché más avanzado para las respuestas comunes.
- [ ] Soporte para más tipos de documentos (.docx, .txt).
- [ ] Panel de administración para visualizar el feedback de los usuarios.
- [ ] Desplegar la aplicación en un servicio en la nube (ej. AWS, Google Cloud).

## Licencia

Distribuido bajo la Licencia MIT. Ver `LICENSE` para más información.
