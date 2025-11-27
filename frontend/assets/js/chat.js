// Variable global para controlar si el bot está respondiendo
let isProcessing = false;

document.addEventListener('DOMContentLoaded', async () => {
    // Verificar si hay sesión activa en localStorage
    const userId = localStorage.getItem('userId');
    const userName = localStorage.getItem('userName');
    
    if (!userId || !userName) {
        // Si no hay sesión activa, redirigir al login
        window.location.href = 'pages/login.html';
        return;
    }

    // Verificar sesión con el servidor SIEMPRE al cargar
    console.log('Verificando sesión con el servidor...');
    try {
        const response = await fetch('/auth/verify-role', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ user_id: userId })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            // Si el servidor dice que la sesión no es válida, limpiar y redirigir
            console.error('Sesión inválida según el servidor');
            localStorage.clear();
            window.location.href = 'pages/login.html';
            return;
        }
        
        console.log('Sesión válida confirmada por el servidor');
        
        // Guardar permisos reales del servidor (sobrescribir localStorage)
        localStorage.setItem('userPermisos', data.permisos);

        // Mostrar nombre del usuario
        document.getElementById('user-name').textContent = userName;

        // Mostrar botón del dashboard solo si es admin (según servidor)
        const dashboardButton = document.getElementById('dashboard-button');
        
        if (data.is_admin) {
            dashboardButton.style.display = 'inline-block';
            console.log('Usuario admin confirmado - mostrando botón dashboard');
            
            // Agregar evento para ir al dashboard
            dashboardButton.addEventListener('click', () => {
                console.log('Navegando al dashboard...');
                window.location.href = 'pages/dashboard.html';
            });
        } else {
            dashboardButton.style.display = 'none';
            console.log('Usuario sin permisos de admin - ocultando botón dashboard');
        }
    } catch (error) {
        console.error('Error verificando sesión con el servidor:', error);
        // En caso de error de conexión, por seguridad redirigir al login
        localStorage.clear();
        window.location.href = 'pages/login.html';
        return;
    }

    // Verificar conexión con el backend
    try {
        console.log('Iniciando verificación de conexión...');
        const response = await fetch('/check_connection');
        const data = await response.json();
        
        if (response.ok && data && typeof data === 'object' && data.connected) {
            console.log('Conexión exitosa verificada');
            showNotification('Conexión exitosa con el servidor', 'success', 3000);
        } else {
            console.log('Error en la verificación');
            showNotification('No se pudo conectar con el servidor', 'error', 6000);
        }
    } catch (error) {
        console.error('Error en la conexión:', error);
        showNotification('Error de conexión con el servidor', 'error', 6000);
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
        // Guardar el nuevo ID de sesion
        localStorage.setItem('currentSessionId', currentSessionId);
        // Agregar mensaje de bienvenida con ejemplos de funcionalidades
        addMessage(`Hola! En que puedo ayudarte hoy? 

**Capacidades disponibles:**
- Conversacion sobre temas academicos
- Codigo de programacion con syntax highlighting
- Ecuaciones matematicas con LaTeX
- Copiar codigo y ecuaciones con un clic

**Ejemplos de ecuaciones que puedes pedirme:**
- Ecuacion cuadratica: $ax^2 + bx + c = 0$
- Integral: $\\int_{a}^{b} f(x) dx$
- Matriz: $\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}$

Prueba preguntandome sobre matematicas, programacion o cualquier tema academico!`, 'bot', true, true);
    }

    // Función para generar un ID de sesión único
    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Nueva función para cargar los ratings de mensajes previos
    async function loadMessageRatings(sessionId) {
        try {
            const response = await fetch(`/chat/message_ratings?user_id=${userId}&session_id=${sessionId}`);
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
    function addMessage(message, sender, saveToHistory = true, isWelcomeMessage = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        // Agregar clase especial si es mensaje de bienvenida
        if (isWelcomeMessage && sender === 'bot') {
            messageDiv.classList.add('no-feedback');
        }
        
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
            
            // Crear contenedor de feedback para TODOS los mensajes del bot
            const feedbackContainer = document.createElement('div');
            feedbackContainer.className = 'feedback-container';
                
                // Texto de pregunta
                const feedbackQuestion = document.createElement('div');
                feedbackQuestion.className = 'feedback-question';
                feedbackQuestion.textContent = '¿Te fue útil esta respuesta?';
                
                // Contenedor para el campo de comentario (inicialmente oculto)
                const commentContainer = document.createElement('div');
                commentContainer.className = 'feedback-comment-container';
                
                // Campo de texto para el comentario
                const commentInput = document.createElement('textarea');
                commentInput.className = 'feedback-comment';
                commentInput.placeholder = 'Comentario opcional (max. 300 caracteres)';
                commentInput.maxLength = 300;
                
                // Contador de caracteres
                const charCounter = document.createElement('div');
                charCounter.className = 'char-counter';
                charCounter.textContent = '0 / 300';
                
                // Actualizar contador de caracteres
                commentInput.addEventListener('input', function() {
                    const currentLength = this.value.length;
                    charCounter.textContent = `${currentLength} / 300`;
                });
                
                // Crear contenedor para la fila inferior (contador + boton)
                const bottomRow = document.createElement('div');
                bottomRow.className = 'feedback-bottom-row';
                
                // Boton para enviar el comentario
                const sendButton = document.createElement('button');
                sendButton.className = 'feedback-send-button';
                sendButton.innerHTML = '<span class="material-symbols-outlined">send</span>';
                sendButton.textContent = 'Enviar';
                sendButton.disabled = true;
                
                bottomRow.appendChild(charCounter);
                bottomRow.appendChild(sendButton);
                
                commentContainer.appendChild(commentInput);
                commentContainer.appendChild(bottomRow);
                
                // Mensaje de confirmacion
                const feedbackSent = document.createElement('span');
                feedbackSent.className = 'feedback-sent';
                feedbackSent.textContent = 'Gracias por tu feedback!';
                
                // Variable para almacenar el rating seleccionado
                let selectedRating = null;
                
                // Crear dropdown de estrellas (siempre visible)
                const starsDropdown = document.createElement('div');
                starsDropdown.className = 'stars-dropdown show';
                starsDropdown.innerHTML = `
                    <div class="stars-rating">
                        <span class="star" data-rating="1">★</span>
                        <span class="star" data-rating="2">★</span>
                        <span class="star" data-rating="3">★</span>
                        <span class="star" data-rating="4">★</span>
                        <span class="star" data-rating="5">★</span>
                    </div>
                `;
                
                // Evento para seleccionar estrellas
                const stars = starsDropdown.querySelectorAll('.star');
                stars.forEach(star => {
                    star.addEventListener('click', function() {
                        selectedRating = parseInt(this.getAttribute('data-rating'));
                        
                        // Actualizar estrellas visuales
                        stars.forEach((s, index) => {
                            if (index < selectedRating) {
                                s.classList.add('selected');
                            } else {
                                s.classList.remove('selected');
                            }
                        });
                        
                        // Guardar el rating
                        messageRatings[cleanMessage] = selectedRating;
                        
                        // Mostrar campo de comentario
                        commentContainer.classList.add('show');
                        
                        // Habilitar botón de envío
                        sendButton.disabled = false;
                    });
                    
                    // Efecto hover para preview
                    star.addEventListener('mouseenter', function() {
                        const rating = parseInt(this.getAttribute('data-rating'));
                        stars.forEach((s, index) => {
                            if (index < rating) {
                                s.classList.add('hover');
                            } else {
                                s.classList.remove('hover');
                            }
                        });
                    });
                });
                
                starsDropdown.addEventListener('mouseleave', function() {
                    stars.forEach(s => s.classList.remove('hover'));
                });
                
                // Evento para enviar feedback
                sendButton.addEventListener('click', function() {
                    if (!selectedRating) {
                        showNotification('Por favor selecciona una valoración', 'warning', 3000);
                        return;
                    }
                    
                    const comentario = commentInput.value.trim();
                    
                    // Deshabilitar elementos
                    stars.forEach(s => s.style.pointerEvents = 'none');
                    commentInput.disabled = true;
                    sendButton.disabled = true;
                    
                    // Ocultar el campo de comentario y estrellas
                    commentContainer.style.display = 'none';
                    starsDropdown.style.display = 'none';
                    feedbackQuestion.style.display = 'none';
                    
                    // Mostrar mensaje de éxito
                    feedbackSent.classList.add('show');
                    
                    // Guardar en localStorage para persistir el estado
                    const feedbackKey = `feedback_${currentSessionId}_${cleanMessage}`;
                    localStorage.setItem(feedbackKey, JSON.stringify({
                        rating: selectedRating,
                        comentario: comentario,
                        timestamp: new Date().toISOString()
                    }));
                    
                    // Enviar feedback
                    sendFeedback(selectedRating, comentario).then(() => {
                        console.log('Feedback enviado exitosamente');
                    }).catch((error) => {
                        console.error('Error enviando feedback:', error);
                        showNotification('Error al enviar feedback', 'error', 3000);
                    });
                });
                
                // Verificar si ya se envió feedback para este mensaje
                const feedbackKey = `feedback_${currentSessionId}_${cleanMessage}`;
                const existingFeedback = localStorage.getItem(feedbackKey);
                
                if (existingFeedback) {
                    // Si ya hay feedback guardado, mostrar solo el mensaje de confirmación
                    const savedData = JSON.parse(existingFeedback);
                    selectedRating = savedData.rating;
                    
                    // Ocultar elementos de entrada
                    feedbackQuestion.style.display = 'none';
                    starsDropdown.style.display = 'none';
                    commentContainer.style.display = 'none';
                    
                    // Mostrar mensaje de confirmación
                    feedbackSent.classList.add('show');
                }
                
                // Agregar elementos al contenedor
                feedbackContainer.appendChild(feedbackQuestion);
                feedbackContainer.appendChild(starsDropdown);
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
            const response = await fetch('/chat/feedback', {
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
            const response = await fetch('/chat/history', {
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
            const response = await fetch(`/chat/history?user_id=${userId}&session_id=${sessionId}`);
            const data = await response.json();
            
            if (Array.isArray(data) && data.length > 0) {
                // Actualizar el ID de sesión actual
                currentSessionId = sessionId;
                localStorage.setItem('currentSessionId', sessionId);
                
                // Actualizar el historial
                history = data;
                
                // Limpiar el chat actual
                chatMessages.innerHTML = '';
                
                // Mostrar mensajes del historial
                history.forEach(msg => {
                    // Determinar si es mensaje de bienvenida
                    const isWelcome = msg.sender === 'bot' && (
                        msg.text.includes('Hola') || 
                        msg.text.includes('Bienvenido') ||
                        msg.text.includes('capacidades')
                    );
                    
                    // Agregar mensaje sin guardar (ya está en el historial)
                    addMessage(msg.text, msg.sender, false, isWelcome);
                });
                
                console.log(`Historial cargado: ${data.length} mensajes`);
            } else {
                console.log('No hay mensajes en esta sesión');
                // Actualizar el ID de sesión actual de todos modos
                currentSessionId = sessionId;
                localStorage.setItem('currentSessionId', sessionId);
                history = [];
                chatMessages.innerHTML = '';
            }
        } catch (error) {
            console.error('Error al cargar historial:', error);
        }
    }

    // Función para cargar la lista de sesiones
    // Funcion para cargar la lista de sesiones con paginacion
    const SESSIONS_PER_PAGE = 8;
    let currentPage = 1;
    let allSessions = [];

    async function loadSessionsList() {
        try {
            const response = await fetch(`/chat/sessions?user_id=${userId}`);
            allSessions = await response.json();
            
            displaySessionsPage(currentPage);
        } catch (error) {
            console.error('Error cargando sesiones:', error);
            sessionsList.innerHTML = '<p>Error al cargar las sesiones</p>';
        }
    }

    function displaySessionsPage(page) {
        const startIndex = (page - 1) * SESSIONS_PER_PAGE;
        const endIndex = startIndex + SESSIONS_PER_PAGE;
        const sessionsToDisplay = allSessions.slice(startIndex, endIndex);
        
        sessionsList.innerHTML = '';
        
        if (allSessions.length === 0) {
            sessionsList.innerHTML = '<p>No hay conversaciones guardadas</p>';
            updatePaginationControls();
            return;
        }
        
        sessionsToDisplay.forEach(session => {
            const sessionItem = document.createElement('div');
            sessionItem.className = 'session-item';
            
            // Formatear fecha
            const date = new Date(session.created_at);
            const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
            
            // Crear etiqueta para la sesion activa
            const isCurrentSession = session.session_id === currentSessionId;
            const currentLabel = isCurrentSession ? ' (Actual)' : '';
            
            sessionItem.innerHTML = `
                <span class="session-date">${formattedDate}${currentLabel}</span>
                <span class="delete-session" data-id="${session.session_id}">&times;</span>
            `;
            
            // Añadir evento para cargar la sesion
            sessionItem.addEventListener('click', async function(e) {
                // Evitar que se active si se hace clic en el boton de eliminar
                if (e.target.classList.contains('delete-session')) return;
                
                // Cargar el historial de esta sesión
                await loadSessionHistory(session.session_id);
                
                // Cargar los ratings de esta sesión
                await loadMessageRatings(session.session_id);
                
                historyModal.style.display = 'none';
                showNotification('Conversacion cargada exitosamente', 'success', 3000);
            });
            
            sessionsList.appendChild(sessionItem);
        });
        
        // Añadir eventos para eliminar sesiones
        document.querySelectorAll('.delete-session').forEach(btn => {
            btn.addEventListener('click', async function(e) {
                e.stopPropagation();
                
                // Mostrar mensaje de funcion deshabilitada
                Swal.fire({
                    title: 'Funcion deshabilitada',
                    text: 'La eliminacion de conversaciones esta temporalmente deshabilitada',
                    icon: 'info',
                    confirmButtonColor: '#3085d6',
                    confirmButtonText: 'Entendido'
                });
            });
        });
        
        updatePaginationControls();
    }

    function updatePaginationControls() {
        const totalPages = Math.ceil(allSessions.length / SESSIONS_PER_PAGE);
        const paginationInfo = document.getElementById('pagination-info');
        const prevButton = document.getElementById('prev-page');
        const nextButton = document.getElementById('next-page');
        
        if (paginationInfo) {
            paginationInfo.textContent = `Pagina ${currentPage} de ${totalPages || 1}`;
        }
        
        if (prevButton) {
            prevButton.disabled = currentPage <= 1;
            prevButton.onclick = () => {
                if (currentPage > 1) {
                    currentPage--;
                    displaySessionsPage(currentPage);
                }
            };
        }
        
        if (nextButton) {
            nextButton.disabled = currentPage >= totalPages;
            nextButton.onclick = () => {
                if (currentPage < totalPages) {
                    currentPage++;
                    displaySessionsPage(currentPage);
                }
            };
        }
    }

    // Funcion para enviar una pregunta al bot
    async function sendQuestion() {
        const question = userInput.value.trim();
        if (!question) return;

        // Verificar si ya se está procesando una petición
        if (isProcessing) {
            showNotification('Por favor espera a que el bot termine de responder', 'warning', 3000);
            return;
        }

        // Marcar como procesando y deshabilitar controles
        isProcessing = true;
        userInput.disabled = true;
        sendButton.disabled = true;
        sendButton.classList.add('loading');
        newSessionButton.disabled = true;
        historyButton.disabled = true;
        userInput.placeholder = 'Esperando respuesta...';
        
        // Deshabilitar selector de modelo
        const modelSelectorBtn = document.getElementById('model-selector-btn');
        if (modelSelectorBtn) modelSelectorBtn.disabled = true;

        // Guardar la pregunta para el feedback
        lastQuestion = question;

        // Agregar mensaje del usuario
        addMessage(question, 'user');
        userInput.value = '';

        // Limpiar las sugerencias cuando el usuario envía una pregunta
        suggestionContainer.innerHTML = '';
        suggestionContainer.classList.remove('active');

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
            modelo: selectedModel
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
        } finally {
            // Habilitar controles nuevamente
            isProcessing = false;
            userInput.disabled = false;
            sendButton.disabled = false;
            sendButton.classList.remove('loading');
            newSessionButton.disabled = false;
            historyButton.disabled = false;
            userInput.placeholder = 'Escribe tu pregunta aqui...';
            
            // Habilitar selector de modelo
            const modelSelectorBtn = document.getElementById('model-selector-btn');
            if (modelSelectorBtn) modelSelectorBtn.disabled = false;
            
            userInput.focus();
        }
    }

    // Función para manejar respuesta streaming
    async function useStreamingResponse(pregunta) {
        try {
            // Remover el indicador inmediatamente cuando iniciamos el streaming
            removeThinkingIndicator();
            
            const response = await fetch('/chat/stream', {
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
                            // Silenciar el log de chunks JSON completos que no son errores reales
                            if (data && data.startsWith('{') && data.includes('"status"')) {
                                // Es un JSON válido que ya fue procesado, no mostrar error
                                continue;
                            }
                            // Solo mostrar advertencias para chunks realmente inválidos
                            // console.log('Chunk no es JSON válido:', data);
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
            
            const response = await fetch('/preguntar', {
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
        // Verificar si esta procesando
        if (isProcessing) {
            showNotification('Por favor espera a que el bot termine de responder', 'warning', 3000);
            return;
        }

        currentSessionId = generateSessionId();
        localStorage.setItem('currentSessionId', currentSessionId);
        history = [];
        messageRatings = {};
        chatMessages.innerHTML = '';
        suggestionContainer.innerHTML = '';
        suggestionContainer.classList.remove('active');
        addMessage('Hola! En que puedo ayudarte hoy?', 'bot', true, true);
        
        // Mostrar notificacion especial
        showNewConversationNotification();
    }

    // Funcion para obtener sugerencias del backend
    async function getSuggestions() {
        try {
            const response = await fetch('/sugerencias', {
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


    
    // Funcion para mostrar las sugerencias como botones
    function displaySuggestions() {
        // Limpiar el contenedor de sugerencias
        suggestionContainer.innerHTML = '';
        
        // Si no hay sugerencias, ocultar el contenedor
        if (!suggestions || suggestions.length === 0) {
            suggestionContainer.classList.remove('active');
            return;
        }
        
        // Crear botones para cada sugerencia
        suggestions.forEach(sugerencia => {
            const button = document.createElement('button');
            button.className = 'suggestion-button';
            button.textContent = sugerencia;
            
            // Agregar evento para enviar la sugerencia al hacer clic
            button.addEventListener('click', () => {
                // Verificar si está procesando
                if (isProcessing) {
                    showNotification('Por favor espera a que el bot termine de responder', 'warning', 3000);
                    return;
                }
                
                // Establecer el texto en el campo de entrada
                userInput.value = sugerencia;
                
                // Enviar la pregunta
                sendQuestion();
            });
            
            suggestionContainer.appendChild(button);
        });
        
        // Mostrar el contenedor con animación
        setTimeout(() => {
            suggestionContainer.classList.add('active');
        }, 100);
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
        if (isProcessing) {
            showNotification('Por favor espera a que el bot termine de responder', 'warning', 3000);
            return;
        }
        currentPage = 1;
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
    
    // Verificar si el bot está procesando
    const isProcessingLocal = document.getElementById('send-button')?.classList.contains('loading');
    if (isProcessingLocal) {
        showNotification('Por favor espera a que el bot termine de responder', 'warning', 3000);
        closeModelDropdown();
        return;
    }
    
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
        const response = await fetch('/models/switch', {
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