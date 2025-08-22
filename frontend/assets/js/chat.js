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

    // Cargar historial si existe una sesión actual
    if (localStorage.getItem('currentSessionId')) {
        await Promise.all([
            loadSessionHistory(currentSessionId),
            loadMessageRatings(currentSessionId)
        ]);
    } else {
        // Guardar el nuevo ID de sesión
        localStorage.setItem('currentSessionId', currentSessionId);
        // Agregar mensaje de bienvenida
        addMessage('¡Hola! ¿En qué puedo ayudarte hoy?', 'bot');
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

    // Función modificada para agregar un mensaje al chat con soporte de markdown mejorado
    function addMessage(message, sender, saveToHistory = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        // Crear contenedor de contenido para separarlo del feedback
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Si es un mensaje del bot, renderizar markdown
        if (sender === 'bot') {
            // Configurar marked para un renderizado más avanzado
            marked.setOptions({
                breaks: true,        // Convertir saltos de línea simples
                gfm: true,          // GitHub Flavored Markdown
                sanitize: false,    // Permitir HTML seguro
                smartLists: true,   // Listas inteligentes
                smartypants: true,  // Tipografía inteligente
                headerIds: false,   // No generar IDs para headers
                mangle: false,      // No cambiar emails
                pedantic: false,    // No ser estricto con markdown
                silent: true        // No mostrar errores en consola
            });
            
            // Pre-procesamiento mejorado para mejor formato
            let processedMessage = message;
            
            // Limpiar el mensaje de espacios innecesarios y normalizar saltos de línea
            processedMessage = processedMessage
                // Normalizar espacios múltiples
                .replace(/[ \t]+/g, ' ')

                // Normalizar saltos de línea múltiples (máximo 2)
                .replace(/\n{3,}/g, '\n\n')
                
                // Mejorar formato de listas con viñetas
                .replace(/^[•·]\s+/gm, '- ')
                .replace(/^\*\s+/gm, '- ')
                .replace(/^-\s+/gm, '- ')
                
                // Asegurar espaciado correcto para listas numeradas
                .replace(/^(\d+)\.\s+/gm, '$1. ')
                
                // Convertir texto en negritas si no está marcado (patrones comunes)
                .replace(/\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-Za-záéíóúñ]+)*?):\s/g, '**$1:** ')
                
                // Mejorar formato de conceptos clave
                .replace(/^(Definición|Características|Aplicaciones|Ejemplos|Ventajas|Desventajas|Tipos|Clasificación|Conclusión):\s*/gmi, '**$1:** ')
                
                // Convertir enumeraciones simples a listas markdown
                .replace(/^(\d+)\)\s+/gm, '$1. ')
                .replace(/^([a-z])\)\s+/gm, '- ')
                
                // Mejorar separadores
                .replace(/^[-=]{3,}$/gm, '\n---\n')
                
                // Asegurar que las líneas no terminen con espacios
                .replace(/[ \t]+$/gm, '')
                
                // Mejorar formato de tablas - NUEVO
                .replace(/\|([^|\n]+)\|/g, function(match, content) {
                    // Limpiar espacios en celdas de tabla
                    return '|' + content.trim() + '|';
                })
                
                // Asegurar separadores de tabla correctos
                .replace(/\|\s*[-:]+\s*\|/g, function(match) {
                    // Normalizar separadores de tabla
                    const cells = match.split('|').filter(cell => cell.trim());
                    return '|' + cells.map(cell => {
                        const cleaned = cell.trim();
                        if (cleaned.includes(':')) {
                            return cleaned;
                        }
                        return cleaned.replace(/-+/, '---');
                    }).join('|') + '|';
                })
                
                // Detectar y mejorar tablas simples (sin formato markdown)
                .replace(/^(.+\|.+)$/gm, function(match) {
                    // Si la línea contiene pipes pero no está bien formateada
                    if (!match.startsWith('|') && match.includes('|')) {
                        return '|' + match + '|';
                    }
                    return match;
                })
                
                // LÍNEA PROBLEMÁTICA ELIMINADA - Esta causaba el corte de palabras
                // .replace(/(\S{60})(\S)/g, '$1 $2');
                
                // Opcional: Mejorar saltos de línea preservando palabras completas
                .replace(/(.{80,}?)\s+/g, function(match, p1) {
                    // Solo agregar salto si la línea es muy larga y hay un espacio natural
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
            
            
            // Post-procesamiento del HTML para mejorar la presentación
            htmlContent = htmlContent
                // Agregar clases CSS específicas para mejor estilo
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
                
                // Mejorar tablas - NUEVO
                .replace(/<table>/g, '<table class="bot-table">')
                .replace(/<thead>/g, '<thead class="bot-table-head">')
                .replace(/<tbody>/g, '<tbody class="bot-table-body">')
                .replace(/<tr>/g, '<tr class="bot-table-row">')
                .replace(/<th>/g, '<th class="bot-table-header">')
                .replace(/<td>/g, '<td class="bot-table-cell">')
                
                // Limpiar párrafos vacíos
                .replace(/<p class="bot-paragraph">\s*<\/p>/g, '')
                .replace(/<p>\s*<\/p>/g, '')
                
                // Mejorar espaciado en listas
                .replace(/(<\/li>)\s*(<li)/g, '$1\n$2')
                
                // Asegurar que el código inline no se rompa
                .replace(/<code class="bot-code">([^<]*)<\/code>/g, (match, content) => {
                    // Evitar saltos de línea dentro del código inline
                    const cleanContent = content.replace(/\s+/g, ' ').trim();
                    return `<code class="bot-code">${cleanContent}</code>`;
                });
            
            contentDiv.innerHTML = htmlContent;
            
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
                    
                    // Mejorar código inline
                    contentDiv.querySelectorAll('code:not(pre code)').forEach(code => {
                        code.style.backgroundColor = '#f8f9fa';
                        code.style.padding = '2px 6px';
                        code.style.borderRadius = '4px';
                        code.style.fontFamily = '"SFMono-Regular", "Monaco", "Consolas", "Liberation Mono", "Courier New", monospace';
                        code.style.fontSize = '0.9em';
                        code.style.color = '#e83e8c';
                        code.style.border = '1px solid #e9ecef';
                        code.style.whiteSpace = 'pre-wrap';
                        code.style.wordWrap = 'break-word';
                    });
                    
                    // Mejorar bloques de código
                    contentDiv.querySelectorAll('pre').forEach(pre => {
                        pre.style.backgroundColor = '#f8f9fa';
                        pre.style.border = '1px solid #e9ecef';
                        pre.style.borderRadius = '6px';
                        pre.style.padding = '16px';
                        pre.style.margin = '12px 0';
                        pre.style.overflow = 'auto';
                        pre.style.fontFamily = '"SFMono-Regular", "Monaco", "Consolas", "Liberation Mono", "Courier New", monospace';
                        pre.style.fontSize = '0.9em';
                        pre.style.lineHeight = '1.4';
                        pre.style.whiteSpace = 'pre-wrap';
                        pre.style.wordWrap = 'break-word';
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
        
        // Si es un mensaje del bot, añadir sistema de feedback
        if (sender === 'bot') {
            // Guardar la respuesta para el feedback
            lastAnswer = message;
            
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
                star.innerHTML = '★';
                star.setAttribute('data-value', i);
                
                // Verificar si esta respuesta ya tiene rating y aplicarlo
                const existingRating = messageRatings[message];
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
                    messageRatings[message] = rating;
                    
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
            charCounter.style.cssText = `
                text-align: right;
                font-size: 10px;
                color: #6c757d;
                margin-top: 3px;
                font-family: monospace;
            `;
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
                    const rating = messageRatings[message];
                    sendButton.disabled = !rating || rating < 1;
                }
            });
            
            // Botón para enviar el comentario
            const sendButton = document.createElement('button');
            sendButton.className = 'feedback-send-button';
            sendButton.innerHTML = '📤 Enviar';
            sendButton.disabled = true; // Inicialmente deshabilitado
            
            sendButton.addEventListener('click', function() {
                const rating = messageRatings[message];
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
                
                // Enviar feedback con comentario
                sendFeedback(rating, comentario).then(() => {
                    // Mostrar mensaje de confirmación
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
                        this.innerHTML = '✅ Enviado';
                        this.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';
                        this.style.cursor = 'default';
                        
                        // Ocultar contenedor después de 2 segundos
                        setTimeout(() => {
                            commentContainer.style.opacity = '0.8';
                            commentContainer.style.transform = 'scale(0.98)';
                        }, 2000);
                    }
                }).catch((error) => {
                    // Manejar error
                    this.innerHTML = '❌ Error';
                    this.style.background = 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)';
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.style.background = '';
                        this.disabled = false;
                    }, 2000);
                });
            });
            
            // Agregar elementos al contenedor de comentario
            commentContainer.appendChild(commentInput);
            commentContainer.appendChild(charCounter);
            commentContainer.appendChild(sendButton);
            
            // Mensaje de confirmación (inicialmente oculto)
            const feedbackSent = document.createElement('span');
            feedbackSent.className = 'feedback-sent';
            feedbackSent.textContent = '¡Gracias por tu feedback!';
            
            // Si ya hay rating, mostrar el mensaje de confirmación
            if (messageRatings[message]) {
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
            history.push({ sender, text: message, timestamp });
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
                
                // Limpiar el chat actual
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
            // Enviar la pregunta al bot
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
                // Agregar respuesta del bot
                addMessage(data.respuesta, 'bot');
                
                // Solicitar sugerencias después de recibir la respuesta
                await getSuggestions();
            } else if (data.error) {
                addMessage('Error: ' + data.error, 'bot');
            }
        } catch (error) {
            console.error('Error al comunicarse con el bot:', error);
            
            // Remover indicador de "pensando" en caso de error
            removeThinkingIndicator();
            
            addMessage('Error al comunicarse con el bot. Por favor, inténtalo de nuevo.', 'bot');
        }
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
        const thinkingIndicator = document.getElementById('thinking-indicator');
        if (thinkingIndicator) {
            // Añadir animación de salida
            thinkingIndicator.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
            thinkingIndicator.style.opacity = '0';
            thinkingIndicator.style.transform = 'translateY(-10px)';
            
            setTimeout(() => {
                if (thinkingIndicator.parentNode) {
                    thinkingIndicator.parentNode.removeChild(thinkingIndicator);
                }
            }, 300);
        }
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
    // Obtener el historial de chat actual
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

// Añadir event listeners a los botones de sugerencia
document.getElementById('suggestion1').addEventListener('click', function() {
    enviarPreguntaSugerida(this.textContent);
});

document.getElementById('suggestion2').addEventListener('click', function() {
    enviarPreguntaSugerida(this.textContent);
});

document.getElementById('suggestion3').addEventListener('click', function() {
    enviarPreguntaSugerida(this.textContent);
});



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

// Inicializar sugerencias al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    actualizarSugerencias();
});