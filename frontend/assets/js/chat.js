document.addEventListener('DOMContentLoaded', async () => {
    // Verificar si hay sesión activa
    const userId = localStorage.getItem('userId');
    const userName = localStorage.getItem('userName');
    const userPermisos = localStorage.getItem('userPermisos');
    
    if (!userId || !userName) {
        // Si no hay sesión activa, redirigir al login
        window.location.href = 'pages/login.html';
        return;
    }

    // Mostrar nombre del usuario
    document.getElementById('user-name').textContent = `Usuario: ${userName}`;

    // Verificar permisos y mostrar botón del dashboard si es admin
    const dashboardButton = document.getElementById('dashboard-button');
    console.log('Verificando permisos para dashboard:', userPermisos);
    
    if (userPermisos === 'admin') {
        dashboardButton.style.display = 'inline-block';
        console.log('Usuario admin detectado - mostrando botón dashboard');
        
        // Agregar evento para ir al dashboard
        dashboardButton.addEventListener('click', () => {
            console.log('Navegando al dashboard...');
            window.location.href = 'pages/dashboard.html';
        });
    } else {
        dashboardButton.style.display = 'none';
        console.log('Usuario sin permisos de admin - ocultando botón dashboard');
    }

    // Verificar conexión con el backend
    try {
        console.log('Iniciando verificación de conexión...');
        const response = await fetch('http://localhost:8000/check_connection');
        console.log('Respuesta recibida:', response);
        console.log('Estado de la respuesta:', response.status);
        console.log('Status text:', response.statusText);
        
        const data = await response.json();
        console.log('Datos recibidos:', data);
        console.log('Tipo de datos:', typeof data);
        
        // Verificar que la respuesta es un objeto y tiene la propiedad connected
        if (response.ok && data && typeof data === 'object' && data.connected) {
            console.log('Conexión exitosa verificada');
            Swal.fire({
                icon: 'success',
                title: '¡Conexión exitosa!',
                text: 'El chat está conectado correctamente al servidor.',
                timer: 3000,
                showConfirmButton: false
            });
        } else {
            console.log('Error en la verificación:', {
                responseOk: response.ok,
                isDataObject: data && typeof data === 'object',
                isConnected: data.connected
            });
            Swal.fire({
                icon: 'error',
                title: 'Error de conexión',
                text: 'No se pudo conectar con el servidor. Por favor, intenta de nuevo más tarde.',
                timer: 3000,
                showConfirmButton: false
            });
        }
    } catch (error) {
        console.error('Error en la conexión:', error);
        console.error('Error detallado:', {
            message: error.message,
            name: error.name,
            stack: error.stack
        });
        Swal.fire({
            icon: 'error',
            title: 'Error de conexión',
            text: 'No se pudo conectar con el servidor. Por favor, intenta de nuevo más tarde.',
            timer: 3000,
            showConfirmButton: false
        });
    }

    // Elementos del DOM
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const logoutButton = document.getElementById('logout-button');
    const newSessionButton = document.getElementById('new-session-button');
    const historyButton = document.getElementById('history-button');
    const historyModal = document.getElementById('history-modal');
    const closeModalBtn = document.querySelector('.close');
    const sessionsList = document.getElementById('sessions-list');
    const suggestionContainer = document.getElementById('suggestion-container');

    // Variables para el chat
    let currentSessionId = localStorage.getItem('currentSessionId') || generateSessionId();
    let history = [];
    let lastQuestion = '';
    let lastAnswer = '';
    let messageRatings = {}; // Objeto para almacenar ratings: {respuesta: rating}
    let suggestions = []; // Array para almacenar las sugerencias actuales
    
    // Variables para las figuras
    let figureMap = {};
    let imageData = [];

    // Cargar datos de figuras al inicializar
    await loadFigureData();

    // Cargar historial si existe una sesión actual
    if (localStorage.getItem('currentSessionId')) {
        await Promise.all([
            loadSessionHistory(currentSessionId),
            loadMessageRatings(currentSessionId)
        ]);
    } else {
        // Guardar el nuevo ID de sesión
        localStorage.setItem('currentSessionId', currentSessionId);
        // Agregar mensaje de bienvenida con ejemplos de funcionalidades
        addMessage(`¡Hola! ¿En qué puedo ayudarte hoy? 

**Capacidades disponibles:**
- 💬 Conversación sobre temas académicos
- 📊 Código de programación con syntax highlighting
- 🧮 **Ecuaciones matemáticas** con LaTeX (¡NUEVO!)
- 📋 Copiar código y ecuaciones con un clic

**Ejemplos de ecuaciones que puedes pedirme:**
- Ecuación cuadrática: $ax^2 + bx + c = 0$
- Integral: $\\int_{a}^{b} f(x) dx$
- Matriz: $\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}$

¡Prueba preguntándome sobre matemáticas, programación o cualquier tema académico!`, 'bot');
    }

    // Función para generar un ID de sesión único
    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Nueva función para cargar los ratings de mensajes previos
    async function loadMessageRatings(sessionId) {
        try {
            const response = await fetch(`http://localhost:8000/chat/message_ratings?user_id=${userId}&session_id=${sessionId}`);
            const ratings = await response.json();
            
            // Convertir array de ratings a un objeto para fácil acceso
            messageRatings = {};
            if (Array.isArray(ratings)) {
                ratings.forEach(item => {
                    messageRatings[item.respuesta] = item.rating;
                });
            }
            
            console.log('Ratings cargados:', messageRatings);
        } catch (error) {
            console.error('Error al cargar ratings:', error);
        }
    }

    // Función para cargar los datos de figuras
    async function loadFigureData() {
        try {
            // Cargar mapa de figuras
            const figureResponse = await fetch('assets/figures/mapa_figuras.json');
            if (!figureResponse.ok) {
                throw new Error(`Error al cargar mapa de figuras: ${figureResponse.status} ${figureResponse.statusText}`);
            }
            
            figureMap = await figureResponse.json();
            
            // Cargar datos de imágenes
            const imageResponse = await fetch('assets/figures/imagenes.json');
            if (!imageResponse.ok) {
                throw new Error(`Error al cargar datos de imágenes: ${imageResponse.status} ${imageResponse.statusText}`);
            }
            
            imageData = await imageResponse.json();
            
        } catch (error) {
            console.error('Error al cargar datos de figuras:', error);
        }
    }

    // Función para encontrar la imagen correspondiente a una figura
    function findFigureImage(figureReference) {
        // Extraer número de figura (ej: "2.14" de "Figura 2.14")
        const match = figureReference.match(/Figura\s+(\d+\.?\d*)/i);
        if (!match) return null;
        
        const figureNumber = match[1];
        
        // Verificar que tenemos datos cargados
        if (!figureMap || Object.keys(figureMap).length === 0) return null;
        
        // Buscar en el mapa de figuras
        const epsFile = figureMap[figureNumber];
        if (!epsFile) return null;
        
        // Verificar que tenemos datos de imágenes
        if (!imageData || imageData.length === 0) return null;
        
        // Buscar la imagen PNG correspondiente
        const imageInfo = imageData.find(img => img.archivo === epsFile);
        if (!imageInfo) return null;
        
        return {
            figureNumber,
            epsFile,
            pngFile: imageInfo.png,
            width: imageInfo.ancho,
            height: imageInfo.alto
        };
    }

    // Función modificada para procesar texto y agregar imágenes de figuras (evitar duplicados)
    function processFigureReferences(text) {
        const figureRegex = /Figura\s+(\d+\.?\d*)/gi;
        let processedText = text;
        let figuresFound = [];
        let processedFigures = new Set(); // Para evitar duplicados
        let allMatches = [];
        
        // Primero, encontrar TODAS las coincidencias
        let match;
        figureRegex.lastIndex = 0; // Reset regex
        
        while ((match = figureRegex.exec(text)) !== null) {
            allMatches.push({
                fullMatch: match[0], // "Figura 2.14"
                figureNumber: match[1], // "2.14"
                index: match.index
            });
        }
        
        // Procesar cada coincidencia única
        allMatches.forEach((matchInfo) => {
            const { fullMatch, figureNumber } = matchInfo;
            
            // Solo procesar cada figura una vez
            if (!processedFigures.has(figureNumber)) {
                const imageInfo = findFigureImage(fullMatch);
                if (imageInfo) {
                    figuresFound.push(imageInfo);
                    processedFigures.add(figureNumber);
                    
                    // Reemplazar solo la PRIMERA aparición de esta figura específica
                    const figureRegexForReplace = new RegExp(`Figura\\s+${figureNumber.replace('.', '\\.')}`, 'i');
                    if (processedText.match(figureRegexForReplace)) {
                        const imageMarker = `[FIGURA_${figureNumber}_PLACEHOLDER]`;
                        processedText = processedText.replace(figureRegexForReplace, `${fullMatch}${imageMarker}`);
                    }
                }
            }
        });
        
        return { processedText, figuresFound };
    }

    // Función para insertar imágenes en el contenido HTML
    function insertFigureImages(htmlContent, figuresFound) {
        let modifiedContent = htmlContent;
        
        figuresFound.forEach((figure) => {
            const placeholder = `[FIGURA_${figure.figureNumber}_PLACEHOLDER]`;
            
            if (modifiedContent.includes(placeholder)) {
                const imageHtml = createFigureImageHtml(figure);
                modifiedContent = modifiedContent.replace(placeholder, imageHtml);
            }
        });
        
        return modifiedContent;
    }

    // Función para crear el HTML de una imagen de figura
    function createFigureImageHtml(figure) {
        const maxWidth = 400; // Ancho máximo para las imágenes
        const aspectRatio = figure.height / figure.width;
        const displayWidth = Math.min(maxWidth, figure.width);
        
        const imageUrl = `assets/figures/png/${figure.pngFile}`;
        
        return `
            <div class="figure-container" style="margin: 15px 0;">
                <div class="figure-image-wrapper" style="text-align: center;">
                    <img 
                        src="${imageUrl}" 
                        alt="Figura ${figure.figureNumber}" 
                        class="figure-image"
                        style="
                            max-width: ${displayWidth}px;
                            height: auto;
                            border: 1px solid #e9ecef;
                            border-radius: 8px;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            cursor: pointer;
                            transition: transform 0.2s ease;
                        "
                        onclick="openImageModal('${imageUrl}', 'Figura ${figure.figureNumber}')"
                        onmouseover="this.style.transform='scale(1.02)'"
                        onmouseout="this.style.transform='scale(1)'"
                    />
                    <div class="figure-caption" style="
                        margin-top: 8px;
                        font-size: 12px;
                        color: #6c757d;
                        font-style: italic;
                    ">
                        Figura ${figure.figureNumber} - Clic para ampliar
                    </div>
                </div>
            </div>
        `;
    }

    // Función para formatear mensajes (simplificada para streaming)
    function formatMessage(text) {
        if (!text) return '';
        
        // Configuración básica de marked para streaming
        marked.setOptions({
            breaks: true,
            gfm: true,
            sanitize: false
        });
        
        try {
            return marked.parse(text);
        } catch (error) {
            console.warn('Error al formatear mensaje:', error);
            return text.replace(/\n/g, '<br>');
        }
    }

    // Función modificada para agregar un mensaje al chat con soporte de figuras
    function addMessage(message, sender, saveToHistory = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        // Crear contenedor de contenido para separarlo del feedback
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Variables para manejo de contenido
        let modelLabel = '';
        let cleanMessage = message;
        
        // Si es un mensaje del bot, renderizar markdown y procesar figuras
        if (sender === 'bot') {
            // Extraer la etiqueta del modelo si está presente
            const modelMatch = message.match(/\[Respuesta generada con ([^\]]+)\]/);
            if (modelMatch) {
                modelLabel = modelMatch[1];
                cleanMessage = message.replace(/\[Respuesta generada con [^\]]+\]/g, '').trim();
            }
            
            // Procesar referencias de figuras ANTES del renderizado markdown
            const { processedText, figuresFound } = processFigureReferences(cleanMessage);
            
            // Configurar marked para un renderizado más avanzado con soporte de código
            marked.setOptions({
                breaks: true,
                gfm: true,
                tables: true,
                sanitize: false,
                smartLists: true,
                smartypants: true,
                headerIds: false,
                mangle: false,
                pedantic: false,
                silent: true,
                highlight: function(code, lang) {
                    // Si Prism está disponible y el lenguaje es soportado
                    if (typeof Prism !== 'undefined' && lang && Prism.languages[lang]) {
                        try {
                            return Prism.highlight(code, Prism.languages[lang], lang);
                        } catch (e) {
                            console.warn('Error highlighting code:', e);
                            return code;
                        }
                    }
                    return code;
                }
            });
            
            let processedMessage = processedText;
            
            // Limpieza y normalización de texto mejorada para código y ecuaciones
            processedMessage = processedMessage
                .replace(/[ \t]+/g, ' ')
                .replace(/\n{3,}/g, '\n\n')
                .replace(/^[•·]\s+/gm, '- ')
                .replace(/^\*\s+/gm, '- ')
                .replace(/^-\s+/gm, '- ')
                .replace(/^(\d+)\.\s+/gm, '$1. ')
                .replace(/\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-Za-záéíóúñ]+)*?):\s/g, '**$1:** ')
                .replace(/^(Definición|Características|Aplicaciones|Ejemplos|Ventajas|Desventajas|Tipos|Clasificación|Conclusión):\s*/gmi, '**$1:** ')
                .replace(/^(\d+)\)\s+/gm, '$1. ')
                .replace(/^([a-z])\)\s+/gm, '- ')
                .replace(/^[-=]{3,}$/gm, '\n---\n')
                .replace(/[ \t]+$/gm, '')
                // Mejorar detección de bloques de código con lenguajes
                .replace(/```(\w+)?\n([\s\S]*?)```/g, function(match, lang, code) {
                    const language = lang || 'text';
                    return '```' + language + '\n' + code.trim() + '\n```';
                })
                // Proteger ecuaciones LaTeX durante el procesamiento
                .replace(/\$\$([\s\S]*?)\$\$/g, function(match, equation) {
                    return `LATEX_DISPLAY_${btoa(equation)}_LATEX_DISPLAY`;
                })
                .replace(/\\\[([\s\S]*?)\\\]/g, function(match, equation) {
                    return `LATEX_DISPLAY_${btoa(equation)}_LATEX_DISPLAY`;
                })
                .replace(/\$([^\$\n]+?)\$/g, function(match, equation) {
                    return `LATEX_INLINE_${btoa(equation)}_LATEX_INLINE`;
                })
                .replace(/\\\(([^\\]+?)\\\)/g, function(match, equation) {
                    return `LATEX_INLINE_${btoa(equation)}_LATEX_INLINE`;
                })
                // Mejorar tablas
                .replace(/\|([^|\n]+)\|/g, function(match, content) {
                    return '|' + content.trim() + '|';
                })
                .replace(/\|\s*[-:]+\s*\|/g, function(match) {
                    const cells = match.split('|').filter(cell => cell.trim());
                    return '|' + cells.map(cell => {
                        const cleaned = cell.trim();
                        if (cleaned.includes(':')) {
                            return cleaned;
                        }
                        return cleaned.replace(/-+/, '---');
                    }).join('|') + '|';
                })
                .replace(/^(.+\|.+)$/gm, function(match) {
                    if (!match.startsWith('|') && match.includes('|')) {
                        return '|' + match + '|';
                    }
                    return match;
                })
                .replace(/(.{80,}?)\s+/g, function(match, p1) {
                    return p1.length > 100 ? p1 + '\n' : match;
                });
    
            // Renderizar markdown a HTML con manejo de errores
            let htmlContent;
            try {
                htmlContent = marked.parse(processedMessage);
            } catch (error) {
                console.warn('Error al procesar markdown, usando texto plano:', error);
                htmlContent = `<p>${processedMessage.replace(/\n/g, '<br>')}</p>`;
            }
            
            // Insertar imágenes de figuras en el HTML
            if (figuresFound.length > 0) {
                htmlContent = insertFigureImages(htmlContent, figuresFound);
            }
            
            // Post-procesamiento del HTML para mejorar la presentación
            htmlContent = htmlContent
                .replace(/<h([1-6])>/g, '<h$1 class="bot-heading">')
                .replace(/<p>/g, '<p class="bot-paragraph">')
                .replace(/<ul>/g, '<ul class="bot-list">')
                .replace(/<ol>/g, '<ol class="bot-list-ordered">')
                .replace(/<li>/g, '<li class="bot-list-item">')
                .replace(/<strong>/g, '<strong class="bot-bold">')
                .replace(/<em>/g, '<em class="bot-italic">')
                .replace(/<code>/g, '<code class="bot-code">')
                .replace(/<pre><code>/g, '<pre class="bot-code-block"><code>')
                .replace(/<pre>/g, '<pre class="bot-code-block">')
                .replace(/<blockquote>/g, '<blockquote class="bot-quote">')
                .replace(/<hr>/g, '<hr class="bot-separator">')
                .replace(/<table>/g, '<table class="bot-table">')
                .replace(/<thead>/g, '<thead class="bot-table-head">')
                .replace(/<tbody>/g, '<tbody class="bot-table-body">')
                .replace(/<tr>/g, '<tr class="bot-table-row">')
                .replace(/<th>/g, '<th class="bot-table-header">')
                .replace(/<td>/g, '<td class="bot-table-cell">')
                .replace(/<p class="bot-paragraph">\s*<\/p>/g, '')
                .replace(/<p>\s*<\/p>/g, '')
                .replace(/(<\/li>)\s*(<li)/g, '$1\n$2')
                .replace(/<code class="bot-code">([^<]*)<\/code>/g, (match, content) => {
                    const cleanContent = content.replace(/\s+/g, ' ').trim();
                    return `<code class="bot-code">${cleanContent}</code>`;
                })
                // Restaurar ecuaciones LaTeX protegidas
                .replace(/LATEX_DISPLAY_([A-Za-z0-9+/=]+)_LATEX_DISPLAY/g, function(match, encodedEquation) {
                    try {
                        const equation = atob(encodedEquation);
                        return `$$${equation}$$`;
                    } catch (e) {
                        console.warn('Error decoding LaTeX equation:', e);
                        return match;
                    }
                })
                .replace(/LATEX_INLINE_([A-Za-z0-9+/=]+)_LATEX_INLINE/g, function(match, encodedEquation) {
                    try {
                        const equation = atob(encodedEquation);
                        return `$${equation}$`;
                    } catch (e) {
                        console.warn('Error decoding LaTeX equation:', e);
                        return match;
                    }
                });
            
            contentDiv.innerHTML = htmlContent;
            
            // Aplicar syntax highlighting, ecuaciones matemáticas y funcionalidad de código
            setTimeout(() => {
                try {
                    // Aplicar renderizado de ecuaciones matemáticas primero
                    if (typeof renderMathEquations === 'function') {
                        renderMathEquations(contentDiv);
                    }
                    
                    // Aplicar Prism highlighting si está disponible
                    if (typeof highlightCodeBlocks === 'function') {
                        highlightCodeBlocks(contentDiv);
                    }
                    
                    // Agregar funcionalidad de copiar código
                    if (typeof addCopyFunctionality === 'function') {
                        addCopyFunctionality(contentDiv);
                    }
                    
                    // Agregar funcionalidad de copiar ecuaciones
                    if (typeof addMathCopyFunctionality === 'function') {
                        addMathCopyFunctionality(contentDiv);
                    }
                    
                    // Procesar bloques de código para detectar lenguajes
                    contentDiv.querySelectorAll('pre code').forEach(codeBlock => {
                        const parentPre = codeBlock.parentElement;
                        const classList = codeBlock.className;
                        
                        // Extraer el lenguaje de la clase
                        const langMatch = classList.match(/language-(\w+)/);
                        if (langMatch && langMatch[1]) {
                            const language = langMatch[1];
                            parentPre.setAttribute('data-language', language);
                            parentPre.classList.add(`language-${language}`);
                        }
                    });
                    
                } catch (codeError) {
                    console.warn('Error al procesar código:', codeError);
                }
            }, 100);
            
            // Mejorar el estilo después del renderizado con mejor manejo de errores
            setTimeout(() => {
                try {
                    // Aplicar estilos adicionales a elementos específicos
                    contentDiv.querySelectorAll('p').forEach((p, index) => {
                        if (p.textContent.trim() === '') {
                            p.style.display = 'none';
                        } else {
                            // Agregar espaciado entre párrafos
                            if (index > 0) {
                                p.style.marginTop = '12px';
                            }
                            // Mejorar el manejo de texto largo
                            p.style.wordWrap = 'break-word';
                            p.style.overflowWrap = 'break-word';
                            p.style.hyphens = 'auto';
                        }
                    });
                    
                    // Mejorar listas
                    contentDiv.querySelectorAll('ul, ol').forEach(list => {
                        list.style.marginLeft = '20px';
                        list.style.marginBottom = '12px';
                        list.style.marginTop = '8px';
                        list.style.wordWrap = 'break-word';
                        
                        // Espaciado entre elementos de lista
                        list.querySelectorAll('li').forEach(li => {
                            li.style.marginBottom = '6px';
                            li.style.lineHeight = '1.6';
                            li.style.wordWrap = 'break-word';
                            li.style.overflowWrap = 'break-word';
                            li.style.hyphens = 'auto';
                        });
                    });
                    
                    // Mejorar elementos en negrita
                    contentDiv.querySelectorAll('strong').forEach(strong => {
                        strong.style.color = '#0056b3';
                        strong.style.fontWeight = '600';
                        strong.style.fontSize = '1.02em';
                        strong.style.wordWrap = 'break-word';
                    });
                    
                    // Mejorar elementos en cursiva
                    contentDiv.querySelectorAll('em').forEach(em => {
                        em.style.color = '#555';
                        em.style.fontStyle = 'italic';
                        em.style.backgroundColor = 'rgba(0, 123, 255, 0.05)';
                        em.style.padding = '1px 3px';
                        em.style.borderRadius = '3px';
                        em.style.wordWrap = 'break-word';
                    });
                    
                    // Mejorar encabezados
                    contentDiv.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(heading => {
                        heading.style.color = '#0056b3';
                        heading.style.marginTop = '16px';
                        heading.style.marginBottom = '8px';
                        heading.style.fontWeight = '600';
                        heading.style.borderBottom = '1px solid #e9ecef';
                        heading.style.paddingBottom = '4px';
                        heading.style.wordWrap = 'break-word';
                        heading.style.hyphens = 'auto';
                    });
                    
                    // Mejorar código inline - solo si no tiene clase CSS personalizada
                    contentDiv.querySelectorAll('code:not(pre code):not(.bot-code)').forEach(code => {
                        code.style.backgroundColor = '#f8f9fa';
                        code.style.padding = '3px 8px';
                        code.style.borderRadius = '4px';
                        code.style.fontFamily = '"SFMono-Regular", "Monaco", "Consolas", "Liberation Mono", "Courier New", monospace';
                        code.style.fontSize = '0.9em';
                        code.style.color = '#d73a49';
                        code.style.border = '1px solid #e9ecef';
                        code.style.whiteSpace = 'nowrap';
                        code.style.fontWeight = '600';
                        code.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
                    });
                    
                    // Mejorar bloques de código - solo si no tienen clase CSS personalizada
                    contentDiv.querySelectorAll('pre:not(.bot-code-block)').forEach(pre => {
                        pre.style.backgroundColor = '#282c34';
                        pre.style.border = '1px solid #3e4451';
                        pre.style.borderRadius = '8px';
                        pre.style.padding = '20px';
                        pre.style.margin = '15px 0';
                        pre.style.overflow = 'auto';
                        pre.style.fontFamily = '"SFMono-Regular", "Monaco", "Consolas", "Liberation Mono", "Courier New", monospace';
                        pre.style.fontSize = '0.85em';
                        pre.style.lineHeight = '1.5';
                        pre.style.color = '#abb2bf';
                        pre.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
                        pre.style.position = 'relative';
                        
                        // Estilos para código dentro del pre
                        const codeInPre = pre.querySelector('code');
                        if (codeInPre) {
                            codeInPre.style.background = 'transparent';
                            codeInPre.style.border = 'none';
                            codeInPre.style.padding = '0';
                            codeInPre.style.color = 'inherit';
                            codeInPre.style.fontSize = 'inherit';
                            codeInPre.style.whiteSpace = 'pre';
                            codeInPre.style.borderRadius = '0';
                            codeInPre.style.boxShadow = 'none';
                        }
                    });
                    
                    // Mejorar citas
                    contentDiv.querySelectorAll('blockquote').forEach(quote => {
                        quote.style.borderLeft = '4px solid #007bff';
                        quote.style.paddingLeft = '16px';
                        quote.style.margin = '16px 0';
                        quote.style.color = '#555';
                        quote.style.fontStyle = 'italic';
                        quote.style.backgroundColor = 'rgba(0, 123, 255, 0.05)';
                        quote.style.padding = '12px 16px';
                        quote.style.borderRadius = '0 6px 6px 0';
                        quote.style.wordWrap = 'break-word';
                        quote.style.hyphens = 'auto';
                    });
                    
                    // Mejorar separadores
                    contentDiv.querySelectorAll('hr').forEach(hr => {
                        hr.style.border = 'none';
                        hr.style.borderTop = '2px solid #e9ecef';
                        hr.style.margin = '20px 0';
                        hr.style.opacity = '0.7';
                    });
                    
                    // Aplicar estilos generales para mejor renderizado de texto
                    contentDiv.style.textRendering = 'optimizeLegibility';
                    contentDiv.style.webkitFontSmoothing = 'antialiased';
                    contentDiv.style.mozOsxFontSmoothing = 'grayscale';
                    
                    // Agregar efectos de transición suaves
                    contentDiv.style.opacity = '0';
                    contentDiv.style.transform = 'translateY(10px)';
                    contentDiv.style.transition = 'all 0.3s ease-out';
                    
                    setTimeout(() => {
                        contentDiv.style.opacity = '1';
                        contentDiv.style.transform = 'translateY(0)';
                    }, 50);
                    
                } catch (styleError) {
                    console.warn('Error al aplicar estilos:', styleError);
                }
            }, 100);
            
        } else {
            // Para mensajes del usuario, usar texto plano con mejor formato
            contentDiv.textContent = message;
            contentDiv.style.wordWrap = 'break-word';
            contentDiv.style.overflowWrap = 'break-word';
            contentDiv.style.lineHeight = '1.4';
            contentDiv.style.hyphens = 'auto';
        }
        
        messageDiv.appendChild(contentDiv);
        
        // Si es un mensaje del bot, añadir etiqueta del modelo y sistema de feedback
        if (sender === 'bot') {
            // Agregar etiqueta del modelo si existe
            if (modelLabel) {
                const modelContainer = document.createElement('div');
                modelContainer.style.cssText = `
                    margin-top: 12px;
                    overflow-wrap: break-word;
                    hyphens: auto;
                `;
                
                const modelParagraph = document.createElement('p');
                modelParagraph.className = 'bot-paragraph';
                modelParagraph.style.cssText = `
                    margin-top: 12px;
                    overflow-wrap: break-word;
                    hyphens: auto;
                `;
                
                const modelEmphasis = document.createElement('em');
                modelEmphasis.className = 'bot-italic';
                modelEmphasis.style.cssText = `
                    color: rgb(85, 85, 85);
                    font-style: italic;
                    background-color: rgba(0, 123, 255, 0.05);
                    padding: 1px 3px;
                    border-radius: 3px;
                    overflow-wrap: break-word;
                `;
                modelEmphasis.textContent = `[Respuesta generada con ${modelLabel}]`;
                
                modelParagraph.appendChild(modelEmphasis);
                modelContainer.appendChild(modelParagraph);
                messageDiv.appendChild(modelContainer);
            }
            
            // Guardar la respuesta para el feedback (sin la etiqueta del modelo)
            lastAnswer = cleanMessage;
            
            // Crear contenedor de feedback
            const feedbackContainer = document.createElement('div');
            feedbackContainer.className = 'feedback-container';
            
            // Texto de pregunta
            const feedbackQuestion = document.createElement('span');
            feedbackQuestion.className = 'feedback-question';
            feedbackQuestion.textContent = '¿Te fue útil esta respuesta?';
            
            // Sistema de estrellas
            const starRating = document.createElement('div');
            starRating.className = 'star-rating';
            
            // Crear las 5 estrellas
            for (let i = 1; i <= 5; i++) {
                const star = document.createElement('span');
                star.className = 'star';
                star.innerHTML = '<span class="material-symbols-outlined">star</span>';
                star.setAttribute('data-value', i);
                
                // Verificar si esta respuesta ya tiene rating y aplicarlo
                const existingRating = messageRatings[cleanMessage];
                if (existingRating && i <= existingRating) {
                    star.classList.add('selected');
                }
                
                // Evento para seleccionar estrellas
                star.addEventListener('click', function() {
                    const rating = parseInt(this.getAttribute('data-value'));
                    
                    // Marcar estrellas seleccionadas con animación
                    const stars = this.parentNode.querySelectorAll('.star');
                    stars.forEach((s, index) => {
                        if (parseInt(s.getAttribute('data-value')) <= rating) {
                            s.classList.add('selected');
                            // Animación escalonada
                            setTimeout(() => {
                                s.style.transform = 'scale(1.2)';
                                setTimeout(() => {
                                    s.style.transform = 'scale(1.1)';
                                }, 150);
                            }, index * 50);
                        } else {
                            s.classList.remove('selected');
                            s.style.transform = 'scale(1)';
                        }
                    });
                    
                    // Guardar el rating en la variable local
                    messageRatings[cleanMessage] = rating;
                    
                    // Mostrar campo de comentario con animación
                    const commentContainer = this.parentNode.parentNode.querySelector('.feedback-comment-container');
                    if (commentContainer) {
                        commentContainer.style.display = 'block';
                        
                        // Habilitar botón de envío
                        const sendButton = commentContainer.querySelector('.feedback-send-button');
                        if (sendButton) {
                            sendButton.disabled = false;
                        }
                    }
                });
                
                starRating.appendChild(star);
            }
            
            // Contenedor para el campo de comentario (inicialmente oculto)
            const commentContainer = document.createElement('div');
            commentContainer.className = 'feedback-comment-container';
            commentContainer.style.display = 'none';
            
            // Campo de texto para el comentario
            const commentInput = document.createElement('textarea');
            commentInput.className = 'feedback-comment';
            commentInput.placeholder = 'Comentario opcional (máx. 300 caracteres)';
            commentInput.rows = 2;
            commentInput.maxLength = 300;
            
            // Contador de caracteres
            const charCounter = document.createElement('div');
            charCounter.className = 'char-counter';
            charCounter.textContent = '0 / 300';
            
            // Actualizar contador de caracteres
            commentInput.addEventListener('input', function() {
                const currentLength = this.value.length;
                charCounter.textContent = `${currentLength} / 300`;
                
                // Cambiar color cuando se acerca al límite
                if (currentLength > 270) {
                    charCounter.style.color = '#dc3545';
                } else if (currentLength > 240) {
                    charCounter.style.color = '#ffc107';
                } else {
                    charCounter.style.color = '#6c757d';
                }
                
                // Habilitar/deshabilitar botón según contenido
                const sendButton = this.parentNode.querySelector('.feedback-send-button');
                if (sendButton) {
                    const rating = messageRatings[cleanMessage];
                    sendButton.disabled = !rating || rating < 1;
                }
            });
            
            // Crear contenedor para la fila inferior (contador + botón)
            const bottomRow = document.createElement('div');
            bottomRow.className = 'feedback-bottom-row';
            
            // Mover el contador existente a la fila inferior (ya fue creado arriba)
            
            // Botón para enviar el comentario
            const sendButton = document.createElement('button');
            sendButton.className = 'feedback-send-button';
            sendButton.innerHTML = '<span class="material-symbols-outlined">send</span>';
            sendButton.disabled = true; // Inicialmente deshabilitado
            
            // Agregar elementos a la fila inferior (el charCounter se agregará después)
            bottomRow.appendChild(charCounter);
            bottomRow.appendChild(sendButton);
            
            sendButton.addEventListener('click', function() {
                const rating = messageRatings[cleanMessage];
                const comentario = commentInput.value.trim();
                
                if (!rating || rating < 1) {
                    // Mostrar mensaje de error elegante
                    const errorMsg = document.createElement('div');
                    errorMsg.style.cssText = `
                        color: #dc3545;
                        font-size: 10px;
                        margin-top: 3px;
                        padding: 3px 6px;
                        background: rgba(220, 53, 69, 0.08);
                        border-radius: 3px;
                        border: 1px solid rgba(220, 53, 69, 0.15);
                    `;
                    errorMsg.textContent = 'Por favor, selecciona una calificación con estrellas antes de enviar.';
                    
                    if (!this.parentNode.querySelector('.error-message')) {
                        errorMsg.className = 'error-message';
                        this.parentNode.appendChild(errorMsg);
                        
                        // Remover mensaje después de 3 segundos
                        setTimeout(() => {
                            if (errorMsg.parentNode) {
                                errorMsg.parentNode.removeChild(errorMsg);
                            }
                        }, 3000);
                    }
                    return;
                }
                
                // Animación de carga en el botón
                const originalText = this.innerHTML;
                this.innerHTML = '⏳ Enviando...';
                this.disabled = true;
                
                // Mostrar mensaje de confirmación inmediatamente
                const feedbackSent = this.parentNode.parentNode.querySelector('.feedback-sent');
                if (feedbackSent) {
                    feedbackSent.style.display = 'inline-block';
                    
                    // Desactivar estrellas y campo de comentario
                    const stars = this.parentNode.parentNode.querySelectorAll('.star');
                    stars.forEach(s => {
                        s.style.pointerEvents = 'none';
                        s.style.opacity = '0.7';
                    });
                    
                    commentInput.disabled = true;
                    commentInput.style.opacity = '0.7';
                    charCounter.style.display = 'none';
                    
                    // Cambiar botón a estado de éxito
                    this.innerHTML = '<span class="material-symbols-outlined">check</span>';
                    this.style.background = '#22c55e';
                    this.style.cursor = 'default';
                }
                
                // Enviar feedback con comentario en segundo plano
                sendFeedback(rating, comentario).then(() => {
                    console.log('Feedback enviado exitosamente');
                    // Ocultar contenedor después de 2 segundos
                    setTimeout(() => {
                        if (commentContainer) {
                            commentContainer.style.opacity = '0.8';
                            commentContainer.style.transform = 'scale(0.98)';
                        }
                    }, 2000);
                }).catch((error) => {
                    // Si hay error, revertir el estado
                    console.error('Error enviando feedback:', error);
                    if (feedbackSent) {
                        feedbackSent.style.display = 'none';
                    }
                    this.innerHTML = '<span class="material-symbols-outlined">error</span>';
                    this.style.background = '#ef4444';
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.style.background = '';
                        this.disabled = false;
                        commentInput.disabled = false;
                        commentInput.style.opacity = '1';
                    }, 2000);
                });
            });
            
            // Agregar elementos al contenedor de comentario
            commentContainer.appendChild(commentInput);
            commentContainer.appendChild(bottomRow);
            
            // Mensaje de confirmación (inicialmente oculto)
            const feedbackSent = document.createElement('span');
            feedbackSent.className = 'feedback-sent';
            feedbackSent.textContent = '¡Gracias por tu feedback!';
            
            // Si ya hay rating, mostrar el mensaje de confirmación
            if (messageRatings[cleanMessage]) {
                feedbackSent.style.display = 'inline-block';
                // Desactivar estrellas
                setTimeout(() => {
                    const stars = starRating.querySelectorAll('.star');
                    stars.forEach(s => {
                        s.style.pointerEvents = 'none';
                    });
                }, 100);
            }
            
            // Agregar elementos al contenedor
            feedbackContainer.appendChild(feedbackQuestion);
            feedbackContainer.appendChild(starRating);
            feedbackContainer.appendChild(commentContainer);
            feedbackContainer.appendChild(feedbackSent);
            
            // Agregar contenedor de feedback al mensaje
            messageDiv.appendChild(feedbackContainer);
        }
        
        chatMessages.appendChild(messageDiv);
        
        // Agregar animación de aparición suave
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            messageDiv.style.transition = 'all 0.3s ease-out';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        }, 10);
        
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Guardar en historial local si es necesario
        if (saveToHistory) {
            const timestamp = new Date().toISOString();
            // Para el bot, guardar el mensaje completo con la etiqueta del modelo
            const textToSave = sender === 'bot' ? message : message;
            history.push({ sender, text: textToSave, timestamp });
            saveSessionHistory();
        }
    }

    // Función para enviar feedback
    async function sendFeedback(rating, comentario = '') {
        try {
            const response = await fetch('http://localhost:8000/chat/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId,
                    session_id: currentSessionId,
                    pregunta: lastQuestion,
                    respuesta: lastAnswer,
                    rating: rating,
                    comentario: comentario
                })
            });

            if (!response.ok) {
                console.error('Error al enviar feedback:', await response.json());
                throw new Error('Error al enviar feedback');
            } else {
                console.log('Feedback enviado correctamente');
                return true;
            }
        } catch (error) {
            console.error('Error al enviar feedback:', error);
            throw error;
        }
    }

    // Función para guardar el historial de la sesión actual
    async function saveSessionHistory() {
        try {
            const response = await fetch('http://localhost:8000/chat/history', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId,
                    session_id: currentSessionId,
                    history: history
                })
            });

            if (!response.ok) {
                console.error('Error al guardar historial:', await response.json());
            }
        } catch (error) {
            console.error('Error al guardar historial:', error);
        }
    }

    // Función para cargar el historial de una sesión
    async function loadSessionHistory(sessionId) {
        try {
            const response = await fetch(`http://localhost:8000/chat/history?user_id=${userId}&session_id=${sessionId}`);
            const data = await response.json();
            
            if (Array.isArray(data)) {
                history = data;
                
                // Limpiar el chat current
                chatMessages.innerHTML = '';
                
                // Mostrar mensajes del historial
                history.forEach(msg => {
                    addMessage(msg.text, msg.sender, false);
                });
            }
        } catch (error) {
            console.error('Error al cargar historial:', error);
        }
    }

    // Función para cargar la lista de sesiones
    async function loadSessionsList() {
        try {
            const response = await fetch(`http://localhost:8000/chat/sessions?user_id=${userId}`);
            const sessions = await response.json();
            
            sessionsList.innerHTML = '';
            
            if (sessions.length === 0) {
                sessionsList.innerHTML = '<p>No hay conversaciones guardadas</p>';
                return;
            }
            
            sessions.forEach(session => {
                const sessionItem = document.createElement('div');
                sessionItem.className = 'session-item';
                
                // Formatear fecha
                const date = new Date(session.created_at);
                const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
                
                // Crear etiqueta para la sesión activa
                const isCurrentSession = session.session_id === currentSessionId;
                const currentLabel = isCurrentSession ? ' (Actual)' : '';
                
                sessionItem.innerHTML = `
                    <span class="session-date">${formattedDate}${currentLabel}</span>
                    <span class="delete-session" data-id="${session.session_id}">&times;</span>
                `;
                
                // Añadir evento para cargar la sesión
                sessionItem.addEventListener('click', async function(e) {
                    // Evitar que se active si se hace clic en el botón de eliminar
                    if (e.target.classList.contains('delete-session')) return;
                    
                    currentSessionId = session.session_id;
                    localStorage.setItem('currentSessionId', currentSessionId);
                    
                    // Cargar tanto el historial como los ratings
                    await Promise.all([
                        loadSessionHistory(currentSessionId),
                        loadMessageRatings(currentSessionId)
                    ]);
                    
                    historyModal.style.display = 'none';
                });
                
                sessionsList.appendChild(sessionItem);
            });
            
            // Añadir eventos para eliminar sesiones
            document.querySelectorAll('.delete-session').forEach(btn => {
                btn.addEventListener('click', async function(e) {
                    e.stopPropagation();
                    
                    // Mostrar mensaje de función deshabilitada
                    Swal.fire({
                        title: 'Función deshabilitada',
                        text: 'La eliminación de conversaciones está temporalmente deshabilitada',
                        icon: 'info',
                        confirmButtonColor: '#3085d6',
                        confirmButtonText: 'Entendido'
                    });
                    
                    // El código original se mantiene pero no se ejecuta
                    /* Código original comentado para referencia
                    const sessionId = this.getAttribute('data-id');
                    
                    const result = await Swal.fire({
                        title: '¿Estás seguro?',
                        text: 'Esta acción eliminará permanentemente la conversación',
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonColor: '#d33',
                        cancelButtonColor: '#3085d6',
                        confirmButtonText: 'Sí, eliminar',
                        cancelButtonText: 'Cancelar'
                    });
                    
                    if (result.isConfirmed) {
                        try {
                            await fetch(`http://localhost:8000/chat/session?user_id=${userId}&session_id=${sessionId}`, {
                                method: 'DELETE'
                            });
                            
                            // Si se elimina la sesión actual, crear una nueva
                            if (sessionId === currentSessionId) {
                                currentSessionId = generateSessionId();
                                localStorage.setItem('currentSessionId', currentSessionId);
                                history = [];
                                messageRatings = {}; // Limpiar los ratings
                                chatMessages.innerHTML = '';
                                suggestionContainer.innerHTML = ''; // Limpiar las sugerencias
                                addMessage('¡Hola! ¿En qué puedo ayudarte hoy?', 'bot');
                            }
                            
                            // Recargar la lista de sesiones
                            loadSessionsList();
                        } catch (error) {
                            console.error('Error al eliminar sesión:', error);
                            Swal.fire('Error', 'No se pudo eliminar la conversación', 'error');
                        }
                    }
                    */
                });
            });
        } catch (error) {
            console.error('Error al cargar lista de sesiones:', error);
            sessionsList.innerHTML = '<p>Error al cargar conversaciones</p>';
        }
    }

    // Función para enviar una pregunta al bot
    async function sendQuestion() {
        const question = userInput.value.trim();
        if (!question) return;

        // Guardar la pregunta para el feedback
        lastQuestion = question;

        // Agregar mensaje del usuario
        addMessage(question, 'user');
        userInput.value = '';

        // Limpiar las sugerencias cuando el usuario envía una pregunta
        suggestionContainer.innerHTML = '';

        // Mostrar indicador de "pensando"
        showThinkingIndicator();

        // Obtener el modelo seleccionado
        const modelSelect = document.getElementById('model-select');
        const selectedModel = modelSelect ? modelSelect.value : 'llama3';

        // Preparar el objeto de pregunta
        const pregunta = {
            texto: question,
            userId: userId,
            chatToken: currentSessionId,
            history: history,
            modelo: selectedModel  // Incluir el modelo seleccionado
        };

        try {
            // Intentar usar streaming primero
            const streamingSupported = await useStreamingResponse(pregunta);
            
            // Si streaming falla, usar el endpoint tradicional
            if (!streamingSupported) {
                await useTraditionalResponse(pregunta);
            }
        } catch (error) {
            console.error('Error al comunicarse con el bot:', error);
            
            // Remover indicador de "pensando" en caso de error
            removeThinkingIndicator();
            
            addMessage('Error al comunicarse con el bot. Por favor, inténtalo de nuevo.', 'bot');
        }
    }

    // Función para manejar respuesta streaming
    async function useStreamingResponse(pregunta) {
        try {
            // Remover el indicador inmediatamente cuando iniciamos el streaming
            removeThinkingIndicator();
            
            const response = await fetch('http://localhost:8000/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pregunta)
            });

            if (!response.ok) {
                return false; // Fallback a tradicional
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let botMessageElements = null;
            let accumulatedResponse = '';
            let isStreaming = false;
            let hasStarted = false;

            while (true) {
                const { done, value } = await reader.read();
                
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        
                        if (data === '[DONE]') {
                            // Finalizar streaming
                            if (accumulatedResponse) {
                                finalizeBotMessage(accumulatedResponse);
                            }
                            await getSuggestions();
                            return true;
                        }

                        try {
                            const jsonData = JSON.parse(data);
                            
                            // Asegurar que el indicador esté removido
                            if (!hasStarted) {
                                removeThinkingIndicator();
                                hasStarted = true;
                            }
                            
                            // Manejar diferentes tipos de eventos SSE
                            if (jsonData.status === 'completed' && jsonData.result && jsonData.result.response) {
                                // La respuesta está completa, ahora simular streaming palabra por palabra
                                const fullResponse = jsonData.result.response;
                                
                                // Crear elemento del mensaje si no existe
                                if (!botMessageElements) {
                                    botMessageElements = createBotMessage(true); // Mostrar loader inicialmente
                                }
                                
                                // Convertir loader a mensaje normal antes del streaming
                                convertLoaderToNormalMessage(botMessageElements);
                                
                                // Iniciar streaming palabra por palabra
                                await streamTextWordByWord(botMessageElements, fullResponse);
                                
                                // Finalizar
                                finalizeBotMessage(fullResponse);
                                await getSuggestions();
                                return true;
                            }
                            
                            // Para chunks individuales (si el backend los envía)
                            if (jsonData.chunk) {
                                // Crear elemento del mensaje si no existe
                                if (!botMessageElements) {
                                    botMessageElements = createBotMessage(true); // Mostrar loader inicialmente
                                }
                                
                                // Convertir loader a mensaje normal cuando empezamos a recibir contenido
                                convertLoaderToNormalMessage(botMessageElements);
                                
                                // Acumular respuesta
                                accumulatedResponse += jsonData.chunk;
                                
                                // Actualizar contenido en tiempo real
                                updateBotMessage(botMessageElements, accumulatedResponse);
                            }
                            
                            if (jsonData.error) {
                                addMessage('Error: ' + jsonData.error, 'bot');
                                return true;
                            }
                            
                            // Mostrar indicadores de progreso
                            if (jsonData.status === 'processing' && !isStreaming) {
                                if (!botMessageElements) {
                                    botMessageElements = createBotMessage(true); // Mostrar loader
                                }
                                // Solo mostrar el loader visual, sin texto
                            }
                            
                        } catch (parseError) {
                            console.log('Chunk no es JSON válido:', data);
                        }
                    }
                }
            }

            return true;
        } catch (error) {
            console.error('Error en streaming:', error);
            return false;
        }
    }

    // Nueva función para simular streaming palabra por palabra
    async function streamTextWordByWord(elements, fullText) {
        // Limpiar el mensaje de "generando..."
        elements.textElement.innerHTML = '';
        
        // Limpiar la etiqueta del modelo del texto si está presente
        const cleanText = fullText.replace(/\[Respuesta generada con [^\]]+\]/g, '').trim();
        
        // Extraer texto plano para streaming (sin markdown)
        const plainText = cleanText
            .replace(/\*\*(.*?)\*\*/g, '$1') // Bold
            .replace(/\*(.*?)\*/g, '$1')     // Italic
            .replace(/`(.*?)`/g, '$1')       // Code
            .replace(/#{1,6}\s*(.*)/g, '$1') // Headers
            .replace(/\[(.*?)\]\(.*?\)/g, '$1'); // Links
        
        const words = plainText.split(' ');
        let currentText = '';
        
        // Agregar clase para styling durante streaming
        elements.messageDiv.classList.add('streaming');
        
        for (let i = 0; i < words.length; i++) {
            currentText += (i > 0 ? ' ' : '') + words[i];
            
            // Mostrar texto plano con cursor durante streaming
            elements.textElement.innerHTML = currentText.replace(/\n/g, '<br>') + '<span class="typing-cursor">|</span>';
            
            // Scroll automático
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Pausa entre palabras (ajustable para velocidad de escritura)
            await new Promise(resolve => setTimeout(resolve, 80 + Math.random() * 40));
        }
        
        // Finalizar streaming
        elements.messageDiv.classList.remove('streaming');
        elements.messageDiv.classList.add('complete');
        
        // Convertir el elemento creado por streaming a un mensaje completo con feedback
        await convertStreamingToCompleteMessage(elements, fullText);
        
        // Scroll final
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Nueva función para convertir mensaje de streaming a mensaje completo
    async function convertStreamingToCompleteMessage(elements, fullText) {
        // Remover el mensaje de streaming
        if (elements.messageDiv.parentNode) {
            elements.messageDiv.parentNode.removeChild(elements.messageDiv);
        }
        
        // Agregar el mensaje completo usando la función addMessage normal
        addMessage(fullText, 'bot', true);
    }

    // Función para manejar respuesta tradicional (fallback)
    async function useTraditionalResponse(pregunta) {
        try {
            // Crear mensaje con loader para respuesta tradicional
            const botMessageElements = createBotMessage(true);
            
            const response = await fetch('http://localhost:8000/preguntar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pregunta)
            });

            const data = await response.json();
            
            // Remover indicador de "pensando"
            removeThinkingIndicator();
            
            if (data.respuesta) {
                // Convertir loader a mensaje normal y mostrar respuesta
                convertLoaderToNormalMessage(botMessageElements);
                updateBotMessage(botMessageElements, data.respuesta);
                
                // Solicitar sugerencias después de recibir la respuesta
                await getSuggestions();
            } else if (data.error) {
                convertLoaderToNormalMessage(botMessageElements);
                updateBotMessage(botMessageElements, 'Error: ' + data.error);
            }
        } catch (error) {
            throw error; // Re-lanzar para manejo en sendQuestion
        }
    }

    // Función para crear elemento de mensaje del bot
    function createBotMessage(showLoader = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        const content = document.createElement('div');
        content.className = 'message-content';
        
        const text = document.createElement('div');
        text.className = 'message-text';
        
        if (showLoader) {
            // Mostrar solo el loader sin avatar ni texto
            messageDiv.classList.add('loading-message');
            text.innerHTML = '<span class="loader"></span>';
        }
        
        content.appendChild(text);
        messageDiv.appendChild(content);
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return { 
            textElement: text, 
            messageDiv: messageDiv 
        };
    }

    // Función para convertir el loader a mensaje normal
    function convertLoaderToNormalMessage(botMessageElements) {
        if (botMessageElements && botMessageElements.messageDiv) {
            botMessageElements.messageDiv.classList.remove('loading-message');
            // El contenido se actualizará con updateBotMessage
        }
    }

    // Función para actualizar mensaje del bot en tiempo real
    function updateBotMessage(elements, text) {
        elements.textElement.innerHTML = formatMessage(text);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Función para finalizar mensaje del bot y agregarlo al historial
    function finalizeBotMessage(text) {
        // Limpiar la etiqueta del modelo del texto si está presente para el feedback
        const cleanText = text.replace(/\[Respuesta generada con [^\]]+\]/g, '').trim();
        
        // Guardar la respuesta limpia para el feedback
        lastAnswer = cleanText;
        
        // Agregar al historial con el texto completo (incluyendo etiqueta del modelo)
        if (history.length === 0 || history[history.length - 1].sender !== 'bot') {
            history.push({
                text: text,  // Guardar texto completo con etiqueta
                sender: 'bot',
                timestamp: new Date().toISOString()
            });
        } else {
            // Actualizar el último mensaje del bot si ya existe
            history[history.length - 1].text = text;  // Texto completo con etiqueta
        }
        
        // Guardar historial actualizado
        saveSessionHistory();
    }

    // Función para cerrar sesión
    function logout() {
        localStorage.removeItem('userId');
        localStorage.removeItem('userName');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('currentSessionId');
        window.location.href = 'pages/login.html';
    }

    // Función para crear una nueva conversación
    function newSession() {
        Swal.fire({
            title: '¿Crear nueva conversación?',
            text: 'Comenzarás una nueva conversación con el bot',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#4CAF50',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Sí, comenzar nueva',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                currentSessionId = generateSessionId();
                localStorage.setItem('currentSessionId', currentSessionId);
                history = [];
                messageRatings = {}; // Limpiar los ratings
                chatMessages.innerHTML = '';
                suggestionContainer.innerHTML = ''; // Limpiar las sugerencias
                addMessage('¡Hola! ¿En qué puedo ayudarte hoy?', 'bot');
            }
        });
    }

    // Función para obtener sugerencias del backend
    async function getSuggestions() {
        try {
            const response = await fetch('http://localhost:8000/sugerencias', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    userId: userId,
                    chatToken: currentSessionId,
                    history: history
                })
            });
    
            const data = await response.json();
            
            if (data.sugerencias && Array.isArray(data.sugerencias)) {
                // Actualizar las sugerencias
                suggestions = data.sugerencias;
                
                // Mostrar las sugerencias
                displaySuggestions();
            }
        } catch (error) {
            console.error('Error al obtener sugerencias:', error);
        }
    }


    
    // Función para mostrar las sugerencias como botones
    function displaySuggestions() {
        // Limpiar el contenedor de sugerencias
        suggestionContainer.innerHTML = '';
        
        // Crear botones para cada sugerencia
        suggestions.forEach(sugerencia => {
            const button = document.createElement('button');
            button.className = 'suggestion-button';
            button.textContent = sugerencia;
            
            // Agregar evento para enviar la sugerencia al hacer clic
            button.addEventListener('click', () => {
                // Establecer el texto en el campo de entrada
                userInput.value = sugerencia;
                
                // Enviar la pregunta
                sendQuestion();
            });
            
            suggestionContainer.appendChild(button);
        });
    }


    // Función para mostrar indicador de "pensando"
    function showThinkingIndicator() {
        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'message bot thinking-indicator';
        thinkingDiv.id = 'thinking-indicator';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content thinking-content';
        
        // Crear los tres puntos animados
        const dotsContainer = document.createElement('div');
        dotsContainer.className = 'thinking-dots';
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            dot.className = 'thinking-dot';
            dot.style.animationDelay = `${i * 0.3}s`;
            dotsContainer.appendChild(dot);
        }
        
        contentDiv.appendChild(dotsContainer);
        thinkingDiv.appendChild(contentDiv);
        chatMessages.appendChild(thinkingDiv);
        
        // Hacer scroll hacia abajo
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Añadir estilos CSS dinámicamente si no existen
        if (!document.getElementById('thinking-styles')) {
            const style = document.createElement('style');
            style.id = 'thinking-styles';
            style.textContent = `
                .thinking-indicator {
                    opacity: 0.8;
                }
                
                .thinking-content {
                    display: flex;
                    align-items: center;
                    padding: 10px 0;
                }
                
                .thinking-dots {
                    display: flex;
                    gap: 4px;
                    align-items: center;
                }
                
                .thinking-dot {
                    width: 8px;
                    height: 8px;
                    background-color: #007bff;
                    border-radius: 50%;
                    animation: thinking-bounce 1.4s infinite ease-in-out both;
                }
                
                @keyframes thinking-bounce {
                    0%, 80%, 100% {
                        transform: scale(0.8);
                        opacity: 0.5;
                    }
                    40% {
                        transform: scale(1.2);
                        opacity: 1;
                    }
                }
                
                .thinking-dot:nth-child(1) { animation-delay: -0.32s; }
                .thinking-dot:nth-child(2) { animation-delay: -0.16s; }
                .thinking-dot:nth-child(3) { animation-delay: 0s; }
            `;
            document.head.appendChild(style);
        }
    }

    // Función para remover indicador de "pensando"
    function removeThinkingIndicator() {
        // Buscar y eliminar todos los indicadores existentes
        const thinkingIndicators = document.querySelectorAll('.thinking-indicator, #thinking-indicator');
        
        thinkingIndicators.forEach(indicator => {
            // Eliminar inmediatamente sin animación para evitar problemas de timing
            if (indicator.parentNode) {
                indicator.parentNode.removeChild(indicator);
            }
        });
        
        // También buscar por clase específica
        const thinkingDivs = document.querySelectorAll('.message.bot.thinking-indicator');
        thinkingDivs.forEach(div => {
            if (div.parentNode) {
                div.parentNode.removeChild(div);
            }
        });
        
        console.log('Indicador de pensando eliminado');
    }

    // Event listeners
    sendButton.addEventListener('click', sendQuestion);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendQuestion();
        }
    });

    logoutButton.addEventListener('click', () => {
        Swal.fire({
            title: '¿Cerrar sesión?',
            text: '¿Estás seguro que deseas salir?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, cerrar sesión',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                logout();
            }
        });
    });

    newSessionButton.addEventListener('click', newSession);

    historyButton.addEventListener('click', () => {
        loadSessionsList();
        historyModal.style.display = 'block';
    });

    closeModalBtn.addEventListener('click', () => {
        historyModal.style.display = 'none';
    });

    window.addEventListener('click', (e) => {
        if (e.target === historyModal) {
            historyModal.style.display = 'none';
        }
    });
});



// Función para actualizar las sugerencias
function actualizarSugerencias() {
    // Obtener el historial de chat current
    const chatHistory = obtenerHistorialChat(); // Implementa esta función según tu lógica actual
    
    // Llamar al endpoint para generar sugerencias
    fetch('/generar_sugerencias', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            history: chatHistory
        }),
    })
    .then(response => response.json())
    .then(data => {
        // Actualizar el texto de los botones con las sugerencias recibidas
        if (data.sugerencias && data.sugerencias.length >= 3) {
            const suggestion1 = document.getElementById('suggestion1');
            const suggestion2 = document.getElementById('suggestion2');
            const suggestion3 = document.getElementById('suggestion3');
            
            if (suggestion1) suggestion1.textContent = data.sugerencias[0];
            if (suggestion2) suggestion2.textContent = data.sugerencias[1];
            if (suggestion3) suggestion3.textContent = data.sugerencias[2];
        }
    })
    .catch(error => {
        console.error('Error al obtener sugerencias:', error);
    });
}

// Añadir event listeners a los botones de sugerencia (comentado - elementos no existen)
/*
document.getElementById('suggestion1').addEventListener('click', function() {
    enviarPreguntaSugerida(this.textContent);
});

document.getElementById('suggestion2').addEventListener('click', function() {
    enviarPreguntaSugerida(this.textContent);
});

document.getElementById('suggestion3').addEventListener('click', function() {
    enviarPreguntaSugerida(this.textContent);
});
*/



// Función para enviar la pregunta sugerida
function enviarPreguntaSugerida(texto) {
    // Establecer el texto en el campo de entrada
    userInput.value = texto;
    
    // Enviar la pregunta usando la función existente
    sendQuestion();
}

// Actualizar sugerencias después de cada respuesta del bot
function despuesDeLaRespuestaDelBot() {
    // Tu código existente para manejar la respuesta
    
    // Actualizar sugerencias
    actualizarSugerencias();
}

// ========================================
// FUNCIONALIDAD DE TOGGLE DE TEMA
// ========================================

// Inicializar tema desde localStorage o usar tema claro por defecto
function initializeTheme() {
    const savedTheme = localStorage.getItem('chatbot-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Si no hay tema guardado, usar la preferencia del sistema
    const theme = savedTheme || (prefersDark ? 'dark' : 'light');
    
    applyTheme(theme);
    updateThemeIcon(theme);
}

// Aplicar tema al body
function applyTheme(theme) {
    if (theme === 'dark') {
        document.body.classList.add('dark-theme');
    } else {
        document.body.classList.remove('dark-theme');
    }
}

// Actualizar icono del botón según el tema
function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

// Toggle entre temas
function toggleTheme() {
    const isDark = document.body.classList.contains('dark-theme');
    const newTheme = isDark ? 'light' : 'dark';
    
    applyTheme(newTheme);
    updateThemeIcon(newTheme);
    
    // Guardar preferencia en localStorage
    localStorage.setItem('chatbot-theme', newTheme);
    
    console.log(`Tema cambiado a: ${newTheme}`);
}

// Event listener para el botón de toggle de tema
document.addEventListener('DOMContentLoaded', () => {
    // Inicializar tema
    initializeTheme();
    
    // Agregar event listener al botón de toggle
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
        console.log('Event listener del tema agregado correctamente');
    }
    
    // Escuchar cambios en la preferencia del sistema
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        // Solo cambiar automáticamente si no hay preferencia guardada
        if (!localStorage.getItem('chatbot-theme')) {
            const theme = e.matches ? 'dark' : 'light';
            applyTheme(theme);
            updateThemeIcon(theme);
        }
    });
});

// ========================================
// FUNCIONALIDAD DEL DROPDOWN DE MODELOS
// ========================================

let currentSelectedModel = 'ollama3'; // Modelo por defecto

// Función para manejar el dropdown de modelos
function initializeModelSelector() {
    const selectorBtn = document.getElementById('model-selector-btn');
    const dropdownMenu = document.getElementById('model-dropdown-menu');
    const modelOptions = document.querySelectorAll('.model-option');
    
    if (!selectorBtn || !dropdownMenu) {
        console.log('Elementos del selector de modelo no encontrados');
        return;
    }
    
    // Toggle dropdown
    selectorBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleModelDropdown();
    });
    
    // Cerrar dropdown al hacer clic fuera
    document.addEventListener('click', (e) => {
        if (!selectorBtn.contains(e.target) && !dropdownMenu.contains(e.target)) {
            closeModelDropdown();
        }
    });
    
    // Marcar modelo seleccionado por defecto
    updateSelectedModel(currentSelectedModel);
    
    console.log('Selector de modelo inicializado correctamente');
}

function toggleModelDropdown() {
    const selectorBtn = document.getElementById('model-selector-btn');
    const dropdownMenu = document.getElementById('model-dropdown-menu');
    
    const isOpen = !dropdownMenu.classList.contains('hidden');
    
    if (isOpen) {
        closeModelDropdown();
    } else {
        openModelDropdown();
    }
}

function openModelDropdown() {
    const selectorBtn = document.getElementById('model-selector-btn');
    const dropdownMenu = document.getElementById('model-dropdown-menu');
    
    dropdownMenu.classList.remove('hidden');
    selectorBtn.classList.add('active');
}

function closeModelDropdown() {
    const selectorBtn = document.getElementById('model-selector-btn');
    const dropdownMenu = document.getElementById('model-dropdown-menu');
    
    dropdownMenu.classList.add('hidden');
    selectorBtn.classList.remove('active');
}

function selectModel(modelValue) {
    console.log('Modelo seleccionado:', modelValue);
    
    // Actualizar el modelo actual
    currentSelectedModel = modelValue;
    
    // Actualizar la interfaz
    updateSelectedModel(modelValue);
    
    // Actualizar el select oculto si existe (para compatibilidad)
    const hiddenSelect = document.getElementById('model-select');
    if (hiddenSelect) {
        hiddenSelect.value = modelValue;
    }
    
    // Cerrar el dropdown
    closeModelDropdown();
    
    // Mostrar alerta de cambio de modelo
    showModelChangeAlert(modelValue);
    
    // Cambiar modelo en el backend
    changeModelInBackend(modelValue);
    
    console.log(`Modelo cambiado a: ${modelValue}`);
}

// Función para mostrar alerta de cambio de modelo
function showModelChangeAlert(modelValue) {
    const alert = document.getElementById('model-change-alert');
    const message = document.getElementById('model-change-message');
    
    if (alert && message) {
        // Obtener el nombre del modelo para mostrar
        const selectedOption = document.querySelector(`[data-model="${modelValue}"]`);
        const modelName = selectedOption ? selectedOption.querySelector('.model-name').textContent : modelValue;
        
        message.textContent = `Se cambió al modelo ${modelName}`;
        alert.classList.add('show');
        
        // Ocultar después de 3 segundos
        setTimeout(() => {
            alert.classList.remove('show');
        }, 3000);
    }
}

// Función para cambiar modelo en el backend
async function changeModelInBackend(modelValue) {
    try {
        const response = await fetch('http://localhost:8000/models/switch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                model: modelValue 
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('Modelo cambiado en el backend:', result);
        } else {
            console.error('Error al cambiar modelo en el backend');
        }
    } catch (error) {
        console.error('Error de conexión al cambiar modelo:', error);
    }
}

function updateSelectedModel(modelValue) {
    const modelOptions = document.querySelectorAll('.model-option');
    
    // Remover selección anterior
    modelOptions.forEach(option => {
        option.classList.remove('selected');
    });
    
    // Marcar la nueva selección
    const selectedOption = document.querySelector(`[data-model="${modelValue}"]`);
    if (selectedOption) {
        selectedOption.classList.add('selected');
        
        // Actualizar el texto del botón principal
        const modelName = selectedOption.querySelector('.model-name').textContent;
        const modelText = document.querySelector('.model-text');
        if (modelText) {
            modelText.textContent = modelName;
        }
    }
}

// Función para obtener el modelo actual
function getCurrentModel() {
    return currentSelectedModel;
}

// Inicializar el selector de modelo cuando cargue la página
document.addEventListener('DOMContentLoaded', () => {
    initializeModelSelector();
});

// Inicializar sugerencias al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    actualizarSugerencias();
});