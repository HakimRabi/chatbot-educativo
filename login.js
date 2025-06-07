document.addEventListener('DOMContentLoaded', async () => {
    // Verificar si ya hay una sesión activa
    const userId = localStorage.getItem('userId');
    const userName = localStorage.getItem('userName');
    
    if (userId && userName) {
        // Si hay sesión activa, redirigir al chat
        window.location.href = 'index.html';
    }

    // Verificar conexión con el backend
    try {
        const response = await fetch('http://localhost:8000/check_connection');
        const data = await response.json();
        
        if (!response.ok || !data.connected) {
            Swal.fire({
                icon: 'error',
                title: 'Error de conexión',
                text: 'No se pudo conectar con el servidor. Por favor, intenta de nuevo más tarde.',
                timer: 3000,
                showConfirmButton: false
            });
        } else {
            console.log('Conexión exitosa al servidor');
        }
    } catch (error) {
        console.error('Error en la conexión:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error de conexión',
            text: 'No se pudo conectar con el servidor. Por favor, intenta de nuevo más tarde.',
            timer: 3000,
            showConfirmButton: false
        });
    }

    // Modal de registro
    const modal = document.getElementById('register-modal');
    const registerLink = document.getElementById('register-link');
    const closeBtn = document.querySelector('.close');

    registerLink.addEventListener('click', (e) => {
        e.preventDefault();
        modal.style.display = 'block';
    });

    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // Agregar debug info al formulario de login
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        
        console.log('Intentando login con:', { email });
        
        // Validación básica del lado del cliente
        if (!email || !password) {
            Swal.fire({
                icon: 'error',
                title: 'Campos requeridos',
                text: 'Por favor, completa todos los campos.'
            });
            return;
        }
        
        try {
            console.log('Enviando solicitud de login...');
            
            // Mostrar datos que se enviarán
            const loginData = { email, password };
            console.log('Datos de login a enviar:', loginData);
            
            const response = await fetch('http://localhost:8000/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(loginData)
            });
            
            console.log('Respuesta recibida:', response.status, response.statusText);
            
            // Intenta obtener el cuerpo de la respuesta como texto primero
            const responseText = await response.text();
            console.log('Respuesta texto:', responseText);
            
            // Luego convierte el texto a JSON si es posible
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
                
                // Guardar información de sesión
                localStorage.setItem('userId', data.user.id);
                localStorage.setItem('userName', data.user.nombre);
                localStorage.setItem('userEmail', data.user.email);
                
                Swal.fire({
                    icon: 'success',
                    title: '¡Bienvenido!',
                    text: `Hola ${data.user.nombre}, has iniciado sesión correctamente.`,
                    timer: 2000,
                    showConfirmButton: false
                }).then(() => {
                    // Redirigir al chat
                    window.location.href = 'index.html';
                });
            } else {
                console.error('Error en login:', data);
                Swal.fire({
                    icon: 'error',
                    title: 'Error de autenticación',
                    text: data.message || data.detail || 'Credenciales incorrectas. Por favor, intenta de nuevo.',
                });
            }
        } catch (error) {
            console.error('Error en la autenticación:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Ocurrió un error durante la autenticación. Por favor, intenta de nuevo más tarde.',
            });
        }
    });

    // Agregar debug info al formulario de registro
    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const nombre = document.getElementById('reg-nombre').value;
        const email = document.getElementById('reg-email').value;
        const password = document.getElementById('reg-password').value;
        const confirmPassword = document.getElementById('reg-confirm-password').value;
        
        console.log('Intentando registro con:', { nombre, email });
        
        // Validación básica
        if (!nombre || !email || !password || !confirmPassword) {
            Swal.fire({
                icon: 'error',
                title: 'Campos requeridos',
                text: 'Por favor, completa todos los campos.'
            });
            return;
        }
        
        if (password !== confirmPassword) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Las contraseñas no coinciden.',
            });
            return;
        }
        
        try {
            console.log('Enviando solicitud de registro...');
            
            // Mostrar datos que se enviarán
            const registerData = { nombre, email, password };
            console.log('Datos de registro a enviar:', registerData);
            
            const response = await fetch('http://localhost:8000/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(registerData)
            });
            
            console.log('Respuesta recibida:', response.status, response.statusText);
            
            // Intenta obtener el cuerpo de la respuesta como texto primero
            const responseText = await response.text();
            console.log('Respuesta texto:', responseText);
            
            // Luego convierte el texto a JSON si es posible
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
                
                Swal.fire({
                    icon: 'success',
                    title: '¡Registro exitoso!',
                    text: 'Tu cuenta ha sido creada correctamente. Ahora puedes iniciar sesión.',
                    timer: 2000,
                    showConfirmButton: false
                }).then(() => {
                    // Cerrar modal y limpiar formulario
                    modal.style.display = 'none';
                    document.getElementById('register-form').reset();
                    
                    // Rellenar el formulario de login con el email recién registrado
                    document.getElementById('email').value = email;
                });
            } else {
                console.error('Error en registro:', data);
                Swal.fire({
                    icon: 'error',
                    title: 'Error de registro',
                    text: data.message || data.detail || 'No se pudo completar el registro. Por favor, intenta de nuevo.',
                });
            }
        } catch (error) {
            console.error('Error en el registro:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Ocurrió un error durante el registro. Por favor, intenta de nuevo más tarde.',
            });
        }
    });

    // Opcionalmente, podemos probar los endpoints de debug
    try {
        console.log('Verificando conexión con el servidor de diagnóstico...');
        const debugResponse = await fetch('http://localhost:8001/debug/check_db');
        if (debugResponse.ok) {
            const debugData = await debugResponse.json();
            console.log('Diagnóstico de base de datos:', debugData);
        }
    } catch (error) {
        console.log('Servidor de diagnóstico no disponible. Esto es normal si aún no lo has iniciado.');
    }
});