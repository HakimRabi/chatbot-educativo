// ========================================
// VARIABLES GLOBALES Y CONFIGURACIÓN
// ========================================
const slider = document.getElementById('formsSlider');
let isLoginView = true;

// Cloudflare Turnstile tokens
let turnstileLoginToken = null;
let turnstileRegisterToken = null;

// Callbacks para Turnstile
function onTurnstileLoginSuccess(token) {
    turnstileLoginToken = token;
    document.getElementById('btnLogin').disabled = false;
    console.log('✅ Turnstile Login verificado');
}

function onTurnstileRegisterSuccess(token) {
    turnstileRegisterToken = token;
    document.getElementById('btnRegister').disabled = false;
    console.log('✅ Turnstile Registro verificado');
}

// Textos para el efecto typewriter
const textLong = "alumno@uandresbello.edu";
const textShort = "alumno@unab.cl";
const delayTyping = 100;
const delayDeleting = 50;
const delayPause = 1500;

// ========================================
// SISTEMA DE NOTIFICACIONES
// ========================================
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('notificationContainer');
    
    // SVG icons para cada tipo
    const icons = {
        success: `<svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M8.5 11.5 11 14l4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"></path>
        </svg>`,
        error: `<svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="m15 9-6 6m0-6 6 6m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"></path>
        </svg>`,
        info: `<svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M10 11h2v5m-2 0h4m-2.592-8.5h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"></path>
        </svg>`,
        warning: `<svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M12 13V8m0 8h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"></path>
        </svg>`
    };
    
    const closeIcon = `<svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
        <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M6 18 17.94 6M18 18 6.06 6"></path>
    </svg>`;
    
    // Crear elemento de notificación
    const notification = document.createElement('li');
    notification.className = `notification-item ${type}`;
    
    notification.innerHTML = `
        <div class="notification-content">
            <div class="notification-icon">${icons[type]}</div>
            <div class="notification-text">${message}</div>
        </div>
        <div class="notification-icon notification-close">${closeIcon}</div>
        <div class="notification-progress-bar"></div>
    `;
    
    // Agregar al contenedor
    container.appendChild(notification);
    
    // Función para remover la notificación
    const removeNotification = () => {
        notification.classList.add('removing');
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 300);
    };
    
    // Event listener para el botón de cerrar
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', removeNotification);
    
    // Auto-remover después de la duración especificada
    setTimeout(removeNotification, duration);
}

// ========================================
// VERIFICACIÓN DE SESIÓN ACTIVA
// ========================================
document.addEventListener('DOMContentLoaded', async () => {
    // Verificar si ya hay una sesión activa
    const userId = localStorage.getItem('userId');
    const userName = localStorage.getItem('userName');
    
    if (userId && userName) {
        window.location.replace(window.location.origin + '/index.html');
    }

    // Verificar conexión con el backend
    try {
        const response = await fetch('/check_connection');
        const data = await response.json();
        
        if (!response.ok || !data.connected) {
            showNotification('No se pudo conectar con el servidor. Verifica tu conexión.', 'error', 6000);
        } else {
            console.log('Conexión exitosa al servidor');
            showNotification('Conexión exitosa con el servidor', 'success', 3000);
        }
    } catch (error) {
        console.error('Error en la conexión:', error);
        showNotification('Error de conexión con el servidor. Intenta de nuevo más tarde.', 'error', 6000);
    }

    // Iniciar animación typewriter en ambos inputs
    typeWriterEffect('email', textLong, textShort);
    typeWriterEffect('reg-email', textLong, textShort);

    // Event listeners para cambiar entre login y registro
    document.getElementById('toggleToRegister').addEventListener('click', toggleForm);
    document.getElementById('toggleToLogin').addEventListener('click', toggleForm);

    // Event listeners para los formularios
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('register-form').addEventListener('submit', handleRegister);
});

// ========================================
// EFECTO TYPEWRITER
// ========================================
function typeWriterEffect(elementId, text1, text2) {
    const elem = document.getElementById(elementId);
    if (!elem) return;
    
    let currentText = "";
    let isDeleting = false;
    let isSecondPhase = false;
    
    function loop() {
        const targetText = isSecondPhase ? text2 : text1;
        
        if (isDeleting) {
            currentText = targetText.substring(0, currentText.length - 1);
        } else {
            currentText = targetText.substring(0, currentText.length + 1);
        }

        elem.setAttribute("placeholder", currentText + "|");

        let typeSpeed = isDeleting ? delayDeleting : delayTyping;

        if (!isDeleting && currentText === targetText) {
            typeSpeed = delayPause;
            
            if(!isSecondPhase) {
                isDeleting = true;
            } else {
                isDeleting = true;
            }
        } else if (isDeleting && currentText === '') {
            isDeleting = false;
            if(!isSecondPhase) {
                isSecondPhase = true;
            } else {
                isSecondPhase = false;
            }
        }

        setTimeout(loop, typeSpeed);
    }
    loop();
}

// ========================================
// FUNCIONES DE VALIDACIÓN Y ERRORES
// ========================================
function clearError(containerId, errorId) {
    const container = document.getElementById(containerId);
    const error = document.getElementById(errorId);
    if (container) container.classList.remove('error');
    if (error) error.style.display = 'none';
}

function showError(containerId, errorId, msg) {
    const container = document.getElementById(containerId);
    const errElem = document.getElementById(errorId);
    
    if (msg && errElem) errElem.textContent = msg;
    if (container) container.classList.add('error');
    if (errElem) errElem.style.display = 'block';
}

function isValidDomain(email) {
    const regex = /^[a-zA-Z0-9._%+-]+@(unab\.cl|uandresbello\.edu)$/i;
    return regex.test(email);
}

// ========================================
// TOGGLE ENTRE LOGIN Y REGISTRO
// ========================================
function toggleForm() {
    // Limpiar todos los errores
    const errors = document.querySelectorAll('.error-message');
    errors.forEach(e => e.style.display = 'none');
    
    const inputs = document.querySelectorAll('.inputForm');
    inputs.forEach(i => i.classList.remove('error'));

    // Limpiar los formularios
    document.getElementById('login-form').reset();
    document.getElementById('register-form').reset();

    // Animar el slider
    if (isLoginView) {
        slider.style.transform = 'translateX(-50%)';
    } else {
        slider.style.transform = 'translateX(0%)';
    }
    isLoginView = !isLoginView;
}

// ========================================
// MANEJO DE LOGIN
// ========================================
async function handleLogin(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    let isValid = true;

    // Limpiar errores previos
    clearError('loginEmailContainer', 'loginEmailError');
    clearError('loginPassContainer', 'loginPassError');

    // Validaciones
    if (!isValidDomain(email)) {
        showError('loginEmailContainer', 'loginEmailError', 'Solo correos @unab.cl o @uandresbello.edu');
        isValid = false;
    }

    if (password.trim() === '') {
        showError('loginPassContainer', 'loginPassError', 'Contraseña requerida');
        isValid = false;
    }

    if (!isValid) return;

    // Mostrar loader
    const btn = document.getElementById('btnLogin');
    btn.classList.add('loading');

    try {
        console.log('Intentando login con:', { email });
        
        // Verificar token de Turnstile
        if (!turnstileLoginToken) {
            btn.classList.remove('loading');
            Swal.fire({
                icon: 'warning',
                title: 'Verificación requerida',
                text: 'Por favor, completa la verificación de seguridad.',
            });
            return;
        }

        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password, turnstile_token: turnstileLoginToken })
        });
        
        console.log('Respuesta recibida:', response.status, response.statusText);
        
        const responseText = await response.text();
        console.log('Respuesta texto:', responseText);
        
        let data;
        try {
            data = JSON.parse(responseText);
            console.log('Datos parseados:', data);
        } catch (parseError) {
            console.error('Error al parsear respuesta JSON:', parseError);
            data = { success: false, message: 'Error al procesar la respuesta del servidor' };
        }
        
        if (response.ok && data.success) {
            console.log('Login exitoso:', data);
            console.log('Datos del usuario:', data.user);
            console.log('Permisos del usuario:', data.user.permisos);
            
            const userPermisos = data.user.permisos || 'usuario';
            console.log('Permisos asignados:', userPermisos);
            
            // Guardar información de sesión
            localStorage.setItem('userId', data.user.id);
            localStorage.setItem('userName', data.user.nombre);
            localStorage.setItem('userEmail', data.user.email);
            localStorage.setItem('userPermisos', userPermisos);
            
            console.log('Permisos guardados en localStorage:', localStorage.getItem('userPermisos'));
            
            Swal.fire({
                icon: 'success',
                title: '¡Bienvenido!',
                text: `Hola ${data.user.nombre}, has iniciado sesión correctamente como ${userPermisos}`,
                timer: 2000,
                showConfirmButton: false
            }).then(() => {
                console.log('Redirigiendo según permisos:', userPermisos);
                if (userPermisos === 'admin') {
                    console.log('Redirigiendo a dashboard de admin');
                    window.location.href = '../pages/dashboard.html';
                } else {
                    console.log('Redirigiendo a chat principal');
                    window.location.href = '/index.html';
                }
            });
        } else {
            console.error('Error en login:', data);
            btn.classList.remove('loading');
            Swal.fire({
                icon: 'error',
                title: 'Error de autenticación',
                text: data.message || data.detail || 'Credenciales incorrectas. Por favor, intenta de nuevo.',
            });
        }
    } catch (error) {
        console.error('Error en la autenticación:', error);
        btn.classList.remove('loading');
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Ocurrió un error durante la autenticación. Por favor, intenta de nuevo más tarde.',
        });
    }
}

// ========================================
// MANEJO DE REGISTRO
// ========================================
async function handleRegister(e) {
    e.preventDefault();
    
    const nombre = document.getElementById('reg-nombre').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;
    const confirmPassword = document.getElementById('reg-confirm-password').value;
    let isValid = true;

    // Limpiar errores previos
    clearError('regNameContainer', 'regNameError');
    clearError('regEmailContainer', 'regEmailError');
    clearError('regPassContainer', 'regPassError');
    clearError('regConfirmContainer', 'regConfirmError');

    // Validaciones
    if (nombre === '') {
        showError('regNameContainer', 'regNameError', 'El nombre es requerido');
        isValid = false;
    }

    if (!isValidDomain(email)) {
        showError('regEmailContainer', 'regEmailError', 'Solo correos @unab.cl o @uandresbello.edu');
        isValid = false;
    }

    if (password.length < 6) {
        showError('regPassContainer', 'regPassError', 'Mínimo 6 caracteres');
        isValid = false;
    }

    if (password !== confirmPassword) {
        showError('regConfirmContainer', 'regConfirmError', 'Las contraseñas no coinciden');
        isValid = false;
    }

    if (!isValid) return;

    // Mostrar loader
    const btn = document.getElementById('btnRegister');
    btn.classList.add('loading');

    try {
        console.log('Intentando registro con:', { nombre, email });
        
        // Verificar token de Turnstile
        if (!turnstileRegisterToken) {
            btn.classList.remove('loading');
            Swal.fire({
                icon: 'warning',
                title: 'Verificación requerida',
                text: 'Por favor, completa la verificación de seguridad.',
            });
            return;
        }
        
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ nombre, email, password, turnstile_token: turnstileRegisterToken })
        });
        
        console.log('Respuesta recibida:', response.status, response.statusText);
        
        const responseText = await response.text();
        console.log('Respuesta texto:', responseText);
        
        let data;
        try {
            data = JSON.parse(responseText);
            console.log('Datos parseados:', data);
        } catch (parseError) {
            console.error('Error al parsear respuesta JSON:', parseError);
            data = { success: false, message: 'Error al procesar la respuesta del servidor' };
        }
        
        if (response.ok && data.success) {
            console.log('Registro exitoso:', data);
            
            btn.classList.remove('loading');
            
            Swal.fire({
                icon: 'success',
                title: '¡Registro exitoso!',
                text: 'Tu cuenta ha sido creada correctamente. Ahora puedes iniciar sesión.',
                timer: 2000,
                showConfirmButton: false
            }).then(() => {
                // Limpiar formulario de registro
                document.getElementById('register-form').reset();
                
                // Volver al login y pre-llenar el email
                toggleForm();
                document.getElementById('email').value = email;
            });
        } else {
            console.error('Error en registro:', data);
            btn.classList.remove('loading');
            Swal.fire({
                icon: 'error',
                title: 'Error de registro',
                text: data.message || data.detail || 'No se pudo completar el registro. Por favor, intenta de nuevo.',
            });
        }
    } catch (error) {
        console.error('Error en el registro:', error);
        btn.classList.remove('loading');
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Ocurrió un error durante el registro. Por favor, intenta de nuevo más tarde.',
        });
    }
}