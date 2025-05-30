document.addEventListener('DOMContentLoaded', async () => {
    // Verificar si hay sesión activa
    const userId = localStorage.getItem('userId');
    const userName = localStorage.getItem('userName');
    
    if (!userId || !userName) {
        // Si no hay sesión activa, redirigir al login
        window.location.href = 'login.html';
        return;
    }

    // Mostrar nombre del usuario
    document.getElementById('user-name').textContent = `Usuario: ${userName}`;

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

    // Función modificada para agregar un mensaje al chat
    function addMessage(message, sender, saveToHistory = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        // Crear contenedor de contenido para separarlo del feedback
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = message;
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
                    
                    // Marcar estrellas seleccionadas
                    const stars = this.parentNode.querySelectorAll('.star');
                    stars.forEach(s => {
                        if (parseInt(s.getAttribute('data-value')) <= rating) {
                            s.classList.add('selected');
                        } else {
                            s.classList.remove('selected');
                        }
                    });
                    
                    // Guardar el rating en la variable local
                    messageRatings[message] = rating;
                    
                    // Mostrar campo de comentario
                    const commentContainer = this.parentNode.parentNode.querySelector('.feedback-comment-container');
                    if (commentContainer) {
                        commentContainer.style.display = 'block';
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
            commentInput.placeholder = 'Escribe un comentario adicional (opcional)';
            commentInput.rows = 2;
            
            // Botón para enviar el comentario
            const sendButton = document.createElement('button');
            sendButton.className = 'feedback-send-button';
            sendButton.textContent = 'Enviar feedback';
            sendButton.addEventListener('click', function() {
                const rating = messageRatings[message];
                const comentario = commentInput.value.trim();
                
                // Enviar feedback con comentario
                sendFeedback(rating, comentario);
                
                // Mostrar mensaje de confirmación
                const feedbackSent = this.parentNode.parentNode.querySelector('.feedback-sent');
                if (feedbackSent) {
                    feedbackSent.style.display = 'inline-block';
                    
                    // Desactivar estrellas y campo de comentario
                    const stars = this.parentNode.parentNode.querySelectorAll('.star');
                    stars.forEach(s => {
                        s.style.pointerEvents = 'none';
                    });
                    
                    commentInput.disabled = true;
                    sendButton.disabled = true;
                    commentContainer.style.opacity = '0.7';
                }
            });
            
            // Agregar elementos al contenedor de comentario
            commentContainer.appendChild(commentInput);
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
            } else {
                console.log('Feedback enviado correctamente');
            }
        } catch (error) {
            console.error('Error al enviar feedback:', error);
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

        // Preparar el objeto de pregunta
        const pregunta = {
            texto: question,
            userId: userId,
            chatToken: currentSessionId,
            history: history
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
            addMessage('Error al comunicarse con el bot. Por favor, inténtalo de nuevo.', 'bot');
        }
    }

    // Función para cerrar sesión
    function logout() {
        localStorage.removeItem('userId');
        localStorage.removeItem('userName');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('currentSessionId');
        window.location.href = 'login.html';
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
        const sugerencias = data.sugerencias;
        document.getElementById('suggestion1').textContent = sugerencias[0];
        document.getElementById('suggestion2').textContent = sugerencias[1];
        document.getElementById('suggestion3').textContent = sugerencias[2];
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
    const inputField = document.getElementById('messageInput'); // Ajusta según el ID de tu campo de entrada
    inputField.value = texto;
    
    // Enviar el formulario o activar la función de envío
    enviarMensaje(); // Implementa esta función según tu lógica actual
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