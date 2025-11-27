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

// Función especial para notificación de nueva conversación
function showNewConversationNotification() {
    const container = document.getElementById('notificationContainer');
    
    const icon = `<svg aria-hidden="true" fill="none" viewBox="0 0 24 24" style="width: 24px; height: 24px;">
        <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M8.5 11.5 11 14l4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"></path>
    </svg>`;
    
    const closeIcon = `<svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
        <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M6 18 17.94 6M18 18 6.06 6"></path>
    </svg>`;
    
    // Crear elemento de notificación especial
    const notification = document.createElement('li');
    notification.className = 'notification-item success';
    notification.style.background = 'linear-gradient(135deg, #a7f3d0 0%, #6ee7b7 100%)';
    
    notification.innerHTML = `
        <div class="notification-content">
            <div class="notification-icon">${icon}</div>
            <div class="notification-text" style="font-weight: 600;">Nueva conversación iniciada</div>
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
    
    // Auto-remover después de 3 segundos
    setTimeout(removeNotification, 3000);
}
