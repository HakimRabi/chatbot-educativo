class Dashboard {
    /**
     * 1. INICIALIZACIÓN Y CONFIGURACIÓN PRINCIPAL
     */
    constructor() {
        // Propiedades de estado
        this.currentSection = 'overview';
        this.refreshInterval = null;
        this.charts = {};
        this.apiBaseUrl = 'http://127.0.0.1:8000'; // Base URL for API calls

        // Datos y paginación de Feedback
        this.feedbackData = [];
        this.filteredFeedback = [];
        this.feedbackCurrentPage = 1;
        this.feedbackPerPage = 10;
        this.totalFeedback = 0;
        
        // Datos y paginación de Usuarios
        this.usersData = [];
        this.filteredUsers = [];
        this.currentPage = 1;
        this.usersPerPage = 10;
        this.totalUsers = 0;

        this.init();
    }

    init() {
        this.checkAuth();
        this.testConnection(); // Test API connection first
        this.applySavedPreferences();
        this.setupEventListeners();
        this.setupNavigation();
        this.loadData();
        this.startAutoRefresh();
    }

    async testConnection() {
        try {
            console.log('Testing dashboard API connection...');
            const response = await fetch(`${this.apiBaseUrl}/dashboard/check-access`);
            const data = await response.json();
            
            if (data.success) {
                console.log('✅ Dashboard API connection successful');
            } else {
                console.warn('⚠️ Dashboard API responded but with error:', data.message);
            }
        } catch (error) {
            console.error('❌ Dashboard API connection failed:', error);
            this.showError('No se pudo conectar con el servidor del dashboard');
        }
    }

    checkAuth() {
        const userId = localStorage.getItem('userId');
        const userName = localStorage.getItem('userName');
        const userPermisos = localStorage.getItem('userPermisos');
        
        console.log('Verificando autenticación en dashboard:');
        console.log('- userId:', userId);
        console.log('- userName:', userName);
        console.log('- userPermisos:', userPermisos);
        
        if (!userId || !userName) {
            console.log('Usuario no autenticado, redirigiendo a login');
            window.location.href = '../pages/login.html';
            return;
        }
        
        // Verificar permisos con manejo de undefined/null
        const permisos = userPermisos || 'usuario';
        console.log('Permisos procesados:', permisos);
        
        if (permisos !== 'admin') {
            console.log('Usuario sin permisos de admin, permisos actuales:', permisos);
            Swal.fire({
                icon: 'error',
                title: 'Acceso Denegado',
                text: 'No tienes permisos para acceder al dashboard administrativo.',
                confirmButtonText: 'Volver al Chat'
            }).then(() => {
                window.location.href = '../index.html';
            });
            return;
        }
        
        console.log('Acceso autorizado al dashboard');
        document.getElementById('userName').textContent = userName;
    }
    
    setupEventListeners() {
        // --- LISTENERS GENERALES ---
        document.getElementById('logoutBtn').addEventListener('click', () => this.logout());
        document.getElementById('refreshBtn').addEventListener('click', () => this.loadData());

        // --- LISTENERS PARA MODALES (INCLUYENDO CONFIGURACIÓN) ---
        document.querySelector('.btn-settings').addEventListener('click', () => {
            document.getElementById('settingsModal').style.display = 'block';
        });

        document.getElementById('closeSettingsModal').addEventListener('click', () => {
            document.getElementById('settingsModal').style.display = 'none';
        });
        
        document.getElementById('closeFeedbackModal').addEventListener('click', () => {
            document.getElementById('feedbackModal').style.display = 'none';
        });

        document.getElementById('closeUserModal').addEventListener('click', () => {
            document.getElementById('userActionModal').style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            const feedbackModal = document.getElementById('feedbackModal');
            const userModal = document.getElementById('userActionModal');
            const settingsModal = document.getElementById('settingsModal');

            if (e.target === feedbackModal) feedbackModal.style.display = 'none';
            if (e.target === userModal) userModal.style.display = 'none';
            if (e.target === settingsModal) settingsModal.style.display = 'none';
        });
        
        // --- LISTENERS PARA CONFIGURACIÓN DE APARIENCIA ---
        document.getElementById('darkModeToggle').addEventListener('change', (e) => {
            this.toggleDarkMode(e.target.checked);
        });

        document.querySelectorAll('.color-swatch').forEach(swatch => {
            swatch.addEventListener('click', () => {
                document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
                swatch.classList.add('active');
                this.setAccentColor(swatch.dataset.color);
            });
        });

        // --- LISTENERS PARA SECCIONES ---
        document.getElementById('feedbackSearch').addEventListener('input', () => this.filterFeedback());
        document.getElementById('ratingFilter').addEventListener('change', () => this.filterFeedback());
        document.getElementById('loadSuggestionsBtn').addEventListener('click', () => this.loadImprovementSuggestions());

        // --- NUEVOS LISTENERS PARA CARGA DE PDF ---
        document.getElementById('uploadPdfBtn').addEventListener('click', () => {
            document.getElementById('pdfUploadInput').click();
        });

        document.getElementById('pdfUploadInput').addEventListener('change', (event) => {
            this.handlePdfUpload(event);
        });
        
        document.getElementById('usersSearch').addEventListener('input', () => this.filterUsers());
        document.getElementById('statusFilter').addEventListener('change', () => this.filterUsers());
        document.getElementById('activityFilter').addEventListener('change', () => this.filterUsers());

        // Paginación de Usuarios
        document.getElementById('usersPrevPage').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadUsersData();
            }
        });
        document.getElementById('usersNextPage').addEventListener('click', () => {
            const totalPages = Math.ceil(this.totalUsers / this.usersPerPage);
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.loadUsersData();
            }
        });

        // Paginación de Feedback
        document.getElementById('feedbackPrevPage').addEventListener('click', () => {
            if (this.feedbackCurrentPage > 1) {
                this.feedbackCurrentPage--;
                this.loadFeedbackData();
            }
        });
        document.getElementById('feedbackNextPage').addEventListener('click', () => {
            const totalPages = Math.ceil(this.totalFeedback / this.feedbackPerPage);
            if (this.feedbackCurrentPage < totalPages) {
                this.feedbackCurrentPage++;
                this.loadFeedbackData();
            }
        });
    }

    setupNavigation() {
        const menuItems = document.querySelectorAll('.menu-item');
        menuItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                menuItems.forEach(mi => mi.classList.remove('active'));
                item.classList.add('active');
                const section = item.dataset.section;
                this.showSection(section);
            });
        });
    }


    async handlePdfUpload(event) {
        const file = event.target.files[0];

        if (!file) {
            return; // No se seleccionó archivo
        }

        if (file.type !== 'application/pdf') {
            Swal.fire({
                icon: 'error',
                title: 'Archivo Inválido',
                text: 'Por favor, selecciona solo archivos PDF.'
            });
            event.target.value = ''; // Resetear el input
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        Swal.fire({
            title: 'Subiendo archivo...',
            text: `Subiendo ${file.name}`,
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/upload-pdf`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                // Lanza un error con el mensaje del servidor si está disponible
                throw new Error(result.detail || 'Error en la respuesta del servidor');
            }

            if (result.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Éxito!',
                    text: result.message || `El archivo ${result.filename} se ha subido correctamente.`
                });
                // Actualizar la sección del sistema para reflejar el nuevo conteo de PDFs
                this.loadSystemHealth(); 
            } else {
                // Esto es por si la respuesta es OK pero success: false
                throw new Error(result.message || 'La carga del archivo falló.');
            }

        } catch (error) {
            console.error('Error al subir el PDF:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error de Carga',
                text: error.message || 'No se pudo subir el archivo. Revisa la consola para más detalles.'
            });
        } finally {
            // Limpiar el valor del input para permitir subir el mismo archivo de nuevo
            event.target.value = '';
        }
    }

    /**
     * 2. GESTIÓN DE SECCIONES Y CARGA DE DATOS
     */
    showSection(sectionName) {
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        
        const targetSection = document.getElementById(`${sectionName}-section`);
        if (targetSection) {
            targetSection.classList.add('active');
        }
        
        const titles = {
            'overview': 'Resumen del Sistema',
            'feedback': 'Gestión de Feedback',
            'users': 'Gestión de Usuarios',
            'system': 'Estado del Sistema'
        };
        
        document.getElementById('sectionTitle').textContent = titles[sectionName] || 'Dashboard';
        this.currentSection = sectionName;
        
        this.loadSectionData(sectionName);
    }

    async loadData() {
        try {
            this.showLoading();
            await this.loadOverviewData();
            this.loadSectionData(this.currentSection);
            this.updateLastRefresh();
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Error al cargar los datos del dashboard');
        }
    }
    
    loadSectionData(section) {
        switch(section) {
            case 'overview':
                this.loadOverviewData();
                break;
            case 'feedback':
                this.loadFeedbackData();
                break;
            case 'users':
                this.loadUsersData();
                break;
            case 'system':
                this.loadSystemHealth();
                break;
        }
    }

    /**
     * 3. SECCIÓN: OVERVIEW (RESUMEN)
     */
    async loadOverviewData() {
        try {
            const [statsResponse, analysisResponse, sessionsResponse] = await Promise.all([
                fetch(`${this.apiBaseUrl}/dashboard/stats`),
                fetch(`${this.apiBaseUrl}/dashboard/feedback-analysis`),
                fetch(`${this.apiBaseUrl}/dashboard/user-sessions`)
            ]);

            const stats = await statsResponse.json();
            const analysis = await analysisResponse.json();
            const sessions = await sessionsResponse.json();

            // Check for errors in responses
            if (stats.error) {
                console.warn('Stats API returned error:', stats.error);
                this.showDatabaseWarning();
            }
            if (analysis.error) {
                console.warn('Feedback analysis API returned error:', analysis.error);
            }
            if (sessions.error) {
                console.warn('Sessions API returned error:', sessions.error);
            }

            this.updateStatsCards(stats);
            this.updateFeedbackAnalysis(analysis);
            this.updateSessionsChart(sessions.daily_sessions || []);
        } catch (error) {
            console.error('Error loading overview data:', error);
            this.showError('Error de conexión al cargar datos del dashboard');
        }
    }

    showDatabaseWarning() {
        const warningDiv = document.createElement('div');
        warningDiv.className = 'database-warning';
        warningDiv.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>Atención:</strong> La base de datos no está disponible. 
                Algunos datos pueden no estar actualizados.
            </div>
        `;
        
        // Insert warning at the top of the dashboard
        const mainContent = document.querySelector('.main-content');
        if (mainContent && !mainContent.querySelector('.database-warning')) {
            mainContent.insertBefore(warningDiv, mainContent.firstChild);
        }
    }

    updateStatsCards(stats) {
        document.getElementById('totalUsers').textContent = stats.total_users || '0';
        document.getElementById('totalSessions').textContent = stats.total_sessions || '0';
        
        const avgRatingElement = document.getElementById('avgRating');
        if (stats.average_rating && stats.average_rating > 0) {
            avgRatingElement.textContent = `${stats.average_rating}/5`;
            avgRatingElement.title = stats.rating_description || '';
        } else {
            avgRatingElement.textContent = 'Sin datos';
            avgRatingElement.title = 'No hay evaluaciones disponibles';
        }
        
        const systemStatusIcon = document.getElementById('systemStatusIcon');
        const systemStatusText = document.getElementById('systemStatus');
        
        if (stats.system_status === 'activo') {
            systemStatusIcon.className = 'stat-icon system-status active';
            systemStatusText.textContent = 'Activo';
            systemStatusText.style.color = '#28a745';
        } else if (stats.system_status === 'limitado') {
            systemStatusIcon.className = 'stat-icon system-status warning';
            systemStatusText.textContent = 'Limitado';
            systemStatusText.style.color = '#ffc107';
        } else {
            systemStatusIcon.className = 'stat-icon system-status inactive';
            systemStatusText.textContent = 'Inactivo';
            systemStatusText.style.color = '#dc3545';
        }
        
        // AGREGAR: Mostrar fragmentos también en el overview si hay datos
        if (stats.total_fragments !== undefined) {
            console.log(`📊 Stats contains fragments data: ${stats.total_fragments}`);
        }
    }

    updateFeedbackAnalysis(analysis) {
        const container = document.getElementById('feedbackAnalysis');
        if (analysis.error) {
            container.innerHTML = '<div class="error">Error al cargar análisis</div>';
            return;
        }

        const sentiment = analysis.sentiment_distribution || {};
        const recommendations = analysis.recommendations || [];

        container.innerHTML = `
            <div class="summary">
                <strong>Resumen:</strong> ${analysis.summary || 'No hay suficiente feedback para análisis'}
            </div>
            <div class="sentiment-distribution">
                <div class="sentiment-item positive"><div>Positivo</div><div>${sentiment.positivo || 0}</div></div>
                <div class="sentiment-item neutral"><div>Neutral</div><div>${sentiment.neutral || 0}</div></div>
                <div class="sentiment-item negative"><div>Negativo</div><div>${sentiment.negativo || 0}</div></div>
            </div>
            ${recommendations.length > 0 ? `
                <div class="recommendations">
                    <strong>Recomendaciones:</strong>
                    <ul>${recommendations.map(rec => `<li>${rec}</li>`).join('')}</ul>
                </div>` : ''}
        `;
    }

    updateSessionsChart(sessionsData) {
        const canvas = document.getElementById('sessionsChart');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        if (this.charts.sessions) {
            this.charts.sessions.destroy();
        }

        if (!sessionsData || sessionsData.length === 0) {
            canvas.style.display = 'none';
            const container = canvas.parentElement;
            if (container.querySelector('.no-data-message') === null) {
                 container.innerHTML = '<div class="no-data-message" style="display: flex; align-items: center; justify-content: center; height: 100%; color: #666;">No hay datos de sesiones disponibles</div>';
            }
            return;
        }

        canvas.style.display = 'block';
        const noDataMessage = canvas.parentElement.querySelector('.no-data-message');
        if(noDataMessage) noDataMessage.remove();

        const labels = sessionsData.map(item => new Date(item.date).toLocaleDateString('es-ES', { month: 'short', day: 'numeric' }));
        const data = sessionsData.map(item => item.sessions);
        const maxValue = Math.max(...data);

        this.charts.sessions = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Sesiones',
                    data: data,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#007bff',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: '#007bff',
                        borderWidth: 1
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, precision: 0, callback: value => Math.floor(value) },
                        max: maxValue > 0 ? maxValue + 1 : 5,
                        grid: { color: 'rgba(0,0,0,0.1)' }
                    },
                    x: {
                        maxTicksLimit: 8,
                        grid: { display: false },
                        ticks: { maxRotation: 45 }
                    }
                },
                elements: { point: { hoverRadius: 8 } }
            }
        });

        setTimeout(() => {
            if (this.charts.sessions) this.charts.sessions.resize();
        }, 100);
    }
    
    /**
     * 4. SECCIÓN: GESTIÓN DE FEEDBACK
     */
    async loadFeedbackData() {
        try {
            const searchTerm = document.getElementById('feedbackSearch')?.value || '';
            const ratingFilter = document.getElementById('ratingFilter')?.value || '';
            
            const params = new URLSearchParams();
            params.append('page', this.feedbackCurrentPage.toString());
            params.append('limit', this.feedbackPerPage.toString());
            if (searchTerm.trim()) params.append('search', searchTerm.trim());
            if (ratingFilter) params.append('rating', ratingFilter);
            
            const url = `${this.apiBaseUrl}/dashboard/feedback-paginated?${params.toString()}`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading feedback data:', data.error);
                if (data.error.includes('Database connection not available')) {
                    document.getElementById('feedbackTableBody').innerHTML = 
                        '<tr><td colspan="6" class="error">Base de datos no disponible. Verifique la conexión.</td></tr>';
                } else {
                    document.getElementById('feedbackTableBody').innerHTML = 
                        '<tr><td colspan="6" class="error">Error al cargar feedback</td></tr>';
                }
                return;
            }
            
            if (!data.success) {
                console.error('Feedback API returned unsuccessful response:', data.error);
                document.getElementById('feedbackTableBody').innerHTML = 
                    '<tr><td colspan="6" class="error">Error en la respuesta del servidor</td></tr>';
                return;
            }
            
            this.feedbackData = data.feedback || [];
            this.totalFeedback = data.total || 0;
            
            this.displayFeedbackTable(this.feedbackData);
            this.updateFeedbackPaginationInfo();
            this.updateFeedbackPaginationControls();
            
        } catch (error) {
            console.error('Error loading feedback data:', error);
            document.getElementById('feedbackTableBody').innerHTML = 
                '<tr><td colspan="6" class="error">Error de conexión al cargar feedback</td></tr>';
        }
    }

    async loadImprovementSuggestions() {
        const container = document.getElementById('improvementSuggestions');
        container.innerHTML = '<div class="loading">Analizando feedback para generar sugerencias...</div>';
        container.classList.add('visible');

        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/feedback-analysis`);
            const analysis = await response.json();

            if (analysis.error) {
                container.innerHTML = `<div class="error">Error al cargar sugerencias: ${analysis.error}</div>`;
                return;
            }

            const recommendations = analysis.recommendations || [];

            if (recommendations.length > 0) {
                const suggestionsHTML = `
                    <ul class="suggestions-list">
                        ${recommendations.slice(0, 3).map(rec => `<li>${rec}</li>`).join('')}
                    </ul>
                `;
                container.innerHTML = suggestionsHTML;
            } else {
                container.innerHTML = '<div class="text-center">No se encontraron sugerencias específicas.</div>';
            }

        } catch (error) {
            console.error('Error fetching improvement suggestions:', error);
            container.innerHTML = '<div class="error">No se pudieron cargar las sugerencias.</div>';
        }
    }

    filterFeedback() {
        this.feedbackCurrentPage = 1;
        this.loadFeedbackData();
    }


    displayFeedbackTable(feedbackList) {
        const tbody = document.getElementById('feedbackTableBody');
        if (!feedbackList || feedbackList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">No hay feedback disponible</td></tr>';
            return;
        }

        tbody.innerHTML = feedbackList.map(feedback => `
            <tr>
                <td class="user-info-cell">
                    <div class="user-name">${feedback.user_name || 'Usuario desconocido'}</div>
                    <div class="user-id">ID: ${feedback.user_id}</div>
                </td>
                <td>
                    <div class="question-preview" title="${feedback.pregunta || 'Sin pregunta'}">
                        ${this.truncateText(feedback.pregunta || 'Sin pregunta', 50)}
                    </div>
                </td>
                <td class="rating-cell">
                    <div class="rating-display">
                        <div class="rating-stars">${this.generateStars(feedback.rating || 0)}</div>
                        <span class="rating-value">${feedback.rating || 0}/5</span>
                    </div>
                </td>
                <td>
                    <div class="comment-preview" title="${feedback.comentario || 'Sin comentario'}">
                        ${feedback.comentario ? this.truncateText(feedback.comentario, 60) : '<em>Sin comentario</em>'}
                    </div>
                </td>
                <td class="feedback-date">${this.formatDate(feedback.created_at)}</td>
                <td class="actions-cell">
                    <button class="btn-view-details" onclick="dashboard.showFeedbackDetails('${feedback.id}')" title="Ver detalles">
                        <i class="fas fa-eye"></i>
                        <span>Ver detalles</span>
                    </button>
                </td>
            </tr>
        `).join('');
    }


    showFeedbackDetails(feedbackId) {
        const feedback = this.feedbackData.find(f => f.id == feedbackId);
        if (!feedback) {
            console.error('Feedback not found:', feedbackId);
            return;
        }

        const modal = document.getElementById('feedbackModal');
        const detailsContainer = document.getElementById('feedbackDetails');
        
        detailsContainer.innerHTML = `
            <div class="feedback-details">
                <div class="detail-section">
                    <h4>Información del Usuario</h4>
                    <p><strong>Nombre:</strong> ${feedback.user_name || 'Usuario desconocido'}</p>
                    <p><strong>Email:</strong> ${feedback.user_email || 'No disponible'}</p>
                    <p><strong>ID Usuario:</strong> ${feedback.user_id}</p>
                </div>
                <div class="detail-section">
                    <h4>Pregunta</h4>
                    <p>${feedback.pregunta || 'Sin pregunta'}</p>
                </div>
                <div class="detail-section">
                    <h4>Respuesta</h4>
                    <p>${feedback.respuesta || 'Sin respuesta'}</p>
                </div>
                <div class="detail-section">
                    <h4>Evaluación</h4>
                    <p><strong>Rating:</strong> ${this.generateStars(feedback.rating)} (${feedback.rating}/5)</p>
                    <p><strong>Comentario:</strong> ${feedback.comentario || '<em>Sin comentario</em>'}</p>
                    <p><strong>Fecha:</strong> ${this.formatDate(feedback.created_at)}</p>
                </div>
            </div>
        `;
        
        modal.style.display = 'block';
    }

    updateFeedbackPaginationInfo() {
        const startIndex = (this.feedbackCurrentPage - 1) * this.feedbackPerPage + 1;
        const endIndex = Math.min(this.feedbackCurrentPage * this.feedbackPerPage, this.totalFeedback);
        
        document.getElementById('feedbackPageInfo').textContent = 
            this.totalFeedback === 0 ? 'No se encontró feedback' :
            `Mostrando ${startIndex}-${endIndex} de ${this.totalFeedback} evaluaciones`;
    }

    updateFeedbackPaginationControls() {
        const totalPages = Math.ceil(this.totalFeedback / this.feedbackPerPage);
        document.getElementById('feedbackPrevPage').disabled = this.feedbackCurrentPage <= 1;
        document.getElementById('feedbackNextPage').disabled = this.feedbackCurrentPage >= totalPages;
        
        const pageNumbersContainer = document.getElementById('feedbackPageNumbers');
        this.renderPageNumbers(pageNumbersContainer, this.feedbackCurrentPage, totalPages, (pageNum) => {
            this.feedbackCurrentPage = pageNum;
            this.loadFeedbackData();
        });
    }

    /**
     * 5. SECCIÓN: GESTIÓN DE USUARIOS
     */
    async loadUsersData() {
        const params = new URLSearchParams();
        params.append('page', this.currentPage.toString());
        params.append('limit', this.usersPerPage.toString());
        
        const searchTerm = document.getElementById('usersSearch')?.value || '';
        const statusFilter = document.getElementById('statusFilter')?.value || '';
        const activityFilter = document.getElementById('activityFilter')?.value || '';
        
        if (searchTerm.trim()) params.append('search', searchTerm.trim());
        if (statusFilter) params.append('status', statusFilter);
        if (activityFilter) params.append('activity', activityFilter);

        await this.loadUsersDataWithFilters(params);
    }
    
    filterUsers() {
        this.currentPage = 1;
        this.loadUsersData();
    }
    
    async loadUsersDataWithFilters(params) {
        try {
            const url = `${this.apiBaseUrl}/dashboard/users-paginated?${params.toString()}`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading filtered users data:', data.error);
                if (data.error.includes('Database connection not available')) {
                    document.getElementById('usersTableBody').innerHTML = 
                        '<tr><td colspan="11" class="error">Base de datos no disponible. Verifique la conexión.</td></tr>';
                } else {
                    document.getElementById('usersTableBody').innerHTML = 
                        '<tr><td colspan="11" class="error">Error al cargar datos filtrados</td></tr>';
                }
                return;
            }
            
            this.usersData = data.users || [];
            this.totalUsers = data.total || 0;
            
            this.displayUsersTable(this.usersData);
            this.updatePaginationControls('users', data.total_pages || 0);
            this.updatePaginationInfo('users');
            
        } catch (error) {
            console.error('Error loading filtered users data:', error);
            document.getElementById('usersTableBody').innerHTML = 
                '<tr><td colspan="11" class="error">Error de conexión al cargar usuarios</td></tr>';
        }
    }

    displayUsersTable(usersList) {
        const tbody = document.getElementById('usersTableBody');
        if (usersList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center">No se encontraron usuarios</td></tr>';
            return;
        }

        tbody.innerHTML = usersList.map(user => `
            <tr>
                <td class="user-id">${user.id}</td>
                <td class="user-info-cell">
                    <div class="user-name">${user.nombre}</div>
                    <div class="user-email">${user.email}</div>
                </td>
                <td class="user-email" style="display: table-cell;">${user.email}</td>
                <td class="user-permissions"><span class="permission-badge ${user.permisos || 'usuario'}">${user.permisos || 'usuario'}</span></td>
                <td>${this.formatDate(user.created_at)}</td>
                <td class="user-stats">
                    <span class="stat-number">${user.total_sessions || 0}</span>
                    <span class="stat-label">sesiones</span>
                </td>
                <td class="user-stats">
                    <span class="stat-number">${user.total_feedback || 0}</span>
                    <span class="stat-label">evaluaciones</span>
                </td>
                <td class="user-rating">
                    <div class="rating-display">
                        ${user.avg_rating > 0 ? `
                            <div class="rating-stars">${this.generateStars(Math.round(user.avg_rating))}</div>
                            <span class="rating-value">${user.avg_rating}/5</span>
                        ` : '<span class="rating-value">Sin rating</span>'}
                    </div>
                </td>
                <td><span class="status-badge ${user.status}">${user.status}</span></td>
                <td class="last-activity">${user.last_activity ? this.formatDate(user.last_activity) : 'Sin actividad'}</td>
                <td class="actions-cell">
                    <button class="btn-action btn-view" onclick="dashboard.viewUserDetails(${user.id})" title="Ver detalles"><i class="fas fa-eye"></i></button>
                    <button class="btn-action btn-edit" onclick="dashboard.editUser(${user.id})" title="Editar"><i class="fas fa-edit"></i></button>
                    <button class="btn-action btn-delete" onclick="dashboard.deleteUser(${user.id})" title="Eliminar"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');
    }

    updatePaginationInfo(type) {
        if (type === 'users') {
            const startIndex = (this.currentPage - 1) * this.usersPerPage + 1;
            const endIndex = Math.min(this.currentPage * this.usersPerPage, this.totalUsers);
            document.getElementById('usersPageInfo').textContent = this.totalUsers === 0 ? 'No se encontraron usuarios' : `Mostrando ${startIndex}-${endIndex} de ${this.totalUsers} usuarios`;
        }
    }

    updatePaginationControls(type, totalPages) {
        if (type === 'users') {
            document.getElementById('usersPrevPage').disabled = this.currentPage <= 1;
            document.getElementById('usersNextPage').disabled = this.currentPage >= totalPages;
            
            const pageNumbersContainer = document.getElementById('usersPageNumbers');
            this.renderPageNumbers(pageNumbersContainer, this.currentPage, totalPages, (pageNum) => {
                this.currentPage = pageNum;
                this.loadUsersData();
            });
        }
    }

    renderPageNumbers(container, currentPage, totalPages, pageChangeCallback) {
        container.innerHTML = '';
        if (totalPages <= 1) return;

        const maxVisiblePages = 5;
        let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
        if (endPage - startPage < maxVisiblePages - 1) {
            startPage = Math.max(1, endPage - maxVisiblePages + 1);
        }

        if (startPage > 1) {
            container.appendChild(this.createPageNumber(1, currentPage, pageChangeCallback));
            if (startPage > 2) container.appendChild(this.createPageDots());
        }

        for (let i = startPage; i <= endPage; i++) {
            container.appendChild(this.createPageNumber(i, currentPage, pageChangeCallback));
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) container.appendChild(this.createPageDots());
            container.appendChild(this.createPageNumber(totalPages, currentPage, pageChangeCallback));
        }
    }
    
    createPageNumber(pageNum, currentPage, callback) {
        const span = document.createElement('span');
        span.className = `page-number ${pageNum === currentPage ? 'active' : ''}`;
        span.textContent = pageNum;
        span.addEventListener('click', () => callback(pageNum));
        return span;
    }

    createFeedbackPageNumber(pageNum) {
        return this.createPageNumber(pageNum, this.feedbackCurrentPage, (newPage) => {
            this.feedbackCurrentPage = newPage;
            this.loadFeedbackData();
        });
    }

    viewUserDetails(userId) {
        const user = this.usersData.find(u => u.id === userId);
        if (!user) return;

        const modal = document.getElementById('userActionModal');
        const detailsContainer = document.getElementById('userActionDetails');
        
        detailsContainer.innerHTML = `
            <div class="user-details">
                <div class="detail-section">
                    <h4>Información Personal</h4>
                    <p><strong>ID:</strong> ${user.id}</p>
                    <p><strong>Nombre:</strong> ${user.nombre}</p>
                    <p><strong>Email:</strong> ${user.email}</p>
                    <p><strong>Permisos:</strong> <span class="permission-badge ${user.permisos || 'usuario'}">${user.permisos || 'usuario'}</span></p>
                    <p><strong>Fecha de Registro:</strong> ${this.formatDate(user.created_at)}</p>
                </div>
                <div class="detail-section">
                    <h4>Estadísticas de Actividad</h4>
                    <p><strong>Total de Sesiones:</strong> ${user.total_sessions || 0}</p>
                    <p><strong>Total de Evaluaciones:</strong> ${user.total_feedback || 0}</p>
                    <p><strong>Rating Promedio:</strong> ${user.avg_rating > 0 ? `${user.avg_rating}/5` : 'Sin calificaciones'}</p>
                    <p><strong>Estado:</strong> <span class="status-badge ${user.status}">${user.status}</span></p>
                    <p><strong>Última Actividad:</strong> ${user.last_activity ? this.formatDate(user.last_activity) : 'Sin actividad registrada'}</p>
                </div>
                <div class="detail-section action-buttons">
                    <button class="btn btn-primary" onclick="dashboard.editUser(${user.id})"><i class="fas fa-edit"></i> Editar Usuario</button>
                </div>
            </div>`;
        
        modal.style.display = 'block';
    }

    editUser(userId) {
        const user = this.usersData.find(u => u.id === userId);
        if (!user) {
            Swal.fire({ icon: 'error', title: 'Error', text: 'Usuario no encontrado' });
            return;
        }

        Swal.fire({
            title: 'Editar Usuario',
            html: `
                <div class="edit-user-form">
                    <div class="form-group"><label for="edit-nombre">Nombre:</label><input type="text" id="edit-nombre" class="swal2-input" value="${user.nombre}" placeholder="Nombre completo"></div>
                    <div class="form-group"><label for="edit-email">Email:</label><input type="email" id="edit-email" class="swal2-input" value="${user.email}" placeholder="correo@ejemplo.com"></div>
                    <div class="form-group"><label for="edit-password">Nueva Contraseña:</label><input type="password" id="edit-password" class="swal2-input" placeholder="Dejar vacío para mantener actual"></div>
                    <div class="form-group"><label for="edit-permisos">Permisos:</label>
                        <select id="edit-permisos" class="swal2-select">
                            <option value="usuario" ${user.permisos === 'usuario' ? 'selected' : ''}>Usuario</option>
                            <option value="admin" ${user.permisos === 'admin' ? 'selected' : ''}>Administrador</option>
                        </select>
                    </div>
                </div>`,
            showCancelButton: true,
            confirmButtonText: 'Guardar Cambios',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#007bff',
            cancelButtonColor: '#6c757d',
            width: '500px',
            preConfirm: () => {
                const nombre = document.getElementById('edit-nombre').value.trim();
                const email = document.getElementById('edit-email').value.trim();
                const password = document.getElementById('edit-password').value.trim();
                const permisos = document.getElementById('edit-permisos').value;

                if (!nombre || !email) {
                    Swal.showValidationMessage('El nombre y email son requeridos');
                    return false;
                }
                if (!this.validateEmail(email)) {
                    Swal.showValidationMessage('Por favor ingrese un email válido');
                    return false;
                }
                if (password && password.length < 6) {
                    Swal.showValidationMessage('La contraseña debe tener al menos 6 caracteres');
                    return false;
                }
                return { nombre, email, password, permisos };
            }
        }).then((result) => {
            if (result.isConfirmed) {
                this.updateUser(userId, result.value);
            }
        });
    }

    async updateUser(userId, userData) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/users/${userId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(userData)
            });
            const result = await response.json();

            if (result.success) {
                Swal.fire({ icon: 'success', title: '¡Éxito!', text: 'Usuario actualizado correctamente', timer: 2000, showConfirmButton: false });
                this.loadUsersData();
            } else {
                Swal.fire({ icon: 'error', title: 'Error', text: result.message || 'Error al actualizar el usuario' });
            }
        } catch (error) {
            console.error('Error updating user:', error);
            Swal.fire({ icon: 'error', title: 'Error de conexión', text: 'No se pudo conectar con el servidor' });
        }
    }

    deleteUser(userId) {
        const user = this.usersData.find(u => u.id === userId);
        const userName = user ? user.nombre : `ID ${userId}`;

        Swal.fire({
            title: '¿Estás seguro?',
            html: `Se eliminará al usuario <strong>${userName}</strong> y todos sus datos asociados (sesiones y feedback).<br><br><strong>¡Esta acción es irreversible!</strong>`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        }).then(async (result) => {
            if (result.isConfirmed) {
                try {
                    Swal.fire({
                        title: 'Eliminando...',
                        text: `Eliminando al usuario ${userName}.`,
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });
                    
                    const response = await fetch(`${this.apiBaseUrl}/dashboard/users/${userId}`, {
                        method: 'DELETE',
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        Swal.fire('¡Eliminado!', data.message || 'El usuario ha sido eliminado.', 'success');
                        this.loadUsersData();
                    } else {
                        throw new Error(data.detail || data.message || 'Error desconocido al eliminar.');
                    }
                } catch (error) {
                    console.error('Error al eliminar usuario:', error);
                    Swal.fire('Error',`No se pudo eliminar al usuario. ${error.message}`,'error');
                }
            }
        });
    }

    /**
     * 6. SECCIÓN: ESTADO DEL SISTEMA
     */
    async loadSystemHealth() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/system-health`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const health = await response.json();
            
            console.log('System health data:', health); // Debug logging
            
            this.updateHealthIndicators(health);
            
            // Mostrar información mejorada - CORREGIDO
            document.getElementById('pdfFiles').textContent = health.pdf_files_loaded || '0';
            
            // AGREGAR: Mostrar fragmentos explícitamente
            const fragmentsElement = document.getElementById('totalFragments');
            if (fragmentsElement) {
                const fragmentsCount = health.total_fragments || '0';
                fragmentsElement.textContent = fragmentsCount;
                console.log(`✅ Fragmentos mostrados en UI: ${fragmentsCount}`);
            } else {
                console.error('❌ Element totalFragments not found in DOM');
            }
            
            // Mostrar estado del vector store si existe el elemento
            const vectorStoreElement = document.getElementById('vectorStoreStatus');
            if (vectorStoreElement) {
                const vectorStatus = health.vector_db_status || 'desconocido';
                vectorStoreElement.textContent = vectorStatus;
                vectorStoreElement.className = `status ${health.vector_store ? 'active' : 'inactive'}`;
                console.log(`✅ Vector store status: ${vectorStatus}`);
            }
            
            const lastCheckDate = health.last_check ? this.formatDate(health.last_check) : '--';
            document.getElementById('lastHealthCheck').textContent = lastCheckDate;
            
            // Mostrar información de debug si está disponible
            if (health.debug_info) {
                console.log('AI System Debug Info:', health.debug_info);
                console.log(`🔍 Debug fragments_count: ${health.debug_info.fragments_count}`);
                console.log(`🔍 Debug documents_count: ${health.debug_info.documents_count}`);
            }
            
        } catch (error) {
            console.error('Error loading system health:', error);
            this.updateHealthIndicators({ 
                database: false, 
                ollama: false,
                database_connected: false,
                llm_status: 'error'
            });
            document.getElementById('pdfFiles').textContent = 'Error';
            
            // Asegurarse de mostrar error en fragmentos también
            const fragmentsElement = document.getElementById('totalFragments');
            if (fragmentsElement) {
                fragmentsElement.textContent = 'Error';
            }
            
            document.getElementById('lastHealthCheck').textContent = 'Error';
        }
    }

    updateHealthIndicators(health) {
        const indicators = [
            { id: 'dbHealth', key: 'database_connected', fallbackKey: 'database', label: 'Base de Datos' },
            { id: 'ollamaHealth', key: 'llm_status', label: 'Modelo Ollama' }
        ];
        
        indicators.forEach(indicator => {
            const element = document.getElementById(indicator.id);
            if (!element) return;
            
            let isHealthy = false;
            let statusText = 'Error';
            
            if (indicator.id === 'dbHealth') {
                isHealthy = health[indicator.key] || health[indicator.fallbackKey] || false;
                statusText = isHealthy ? 'Funcionando' : 'Desconectado';
            } else if (indicator.id === 'ollamaHealth') {
                const llmStatus = health[indicator.key] || 'disconnected';
                isHealthy = llmStatus === 'connected';
                
                if (llmStatus === 'connected') {
                    statusText = 'Funcionando';
                } else if (llmStatus === 'not_initialized') {
                    statusText = 'No inicializado';
                } else if (llmStatus.startsWith('error')) {
                    statusText = 'Error';
                } else {
                    statusText = 'Desconectado';
                }
            }
            
            element.className = `health-status ${isHealthy ? 'healthy' : 'unhealthy'}`;
            element.innerHTML = `<i class="fas fa-circle"></i> <span>${statusText}</span>`;
        });
        
        // Actualizar estado general del sistema si existe el elemento
        const overallStatusElement = document.getElementById('overallSystemStatus');
        if (overallStatusElement && health.overall_status) {
            const statusMap = {
                'healthy': { text: 'Saludable', class: 'healthy' },
                'partially_healthy': { text: 'Parcialmente funcional', class: 'warning' },
                'limited': { text: 'Limitado', class: 'warning' },
                'unhealthy': { text: 'Con problemas', class: 'unhealthy' },
                'error': { text: 'Error', class: 'unhealthy' }
            };
            
            const status = statusMap[health.overall_status] || { text: 'Desconocido', class: 'unhealthy' };
            overallStatusElement.className = `health-status ${status.class}`;
            overallStatusElement.innerHTML = `<i class="fas fa-circle"></i> <span>${status.text}</span>`;
        }
    }
    
    /**
     * 7. MÉTODOS UTILITARIOS Y DE CONFIGURACIÓN
     */
    applySavedPreferences() {
        const savedMode = localStorage.getItem('themeMode');
        if (savedMode === 'dark') {
            document.body.classList.add('dark-mode');
            document.getElementById('darkModeToggle').checked = true;
        }

        const savedColor = localStorage.getItem('themeColor') || 'blue';
        this.setAccentColor(savedColor);
        
        document.querySelectorAll('.color-swatch').forEach(swatch => {
            swatch.classList.toggle('active', swatch.dataset.color === savedColor);
        });
    }

    toggleDarkMode(isDark) {
        if (isDark) {
            document.body.classList.add('dark-mode');
            localStorage.setItem('themeMode', 'dark');
        } else {
            document.body.classList.remove('dark-mode');
            localStorage.setItem('themeMode', 'light');
        }
    }

    setAccentColor(colorName) {
        document.body.classList.remove('theme-blue', 'theme-green', 'theme-purple', 'theme-orange');
        if (colorName !== 'blue') {
            document.body.classList.add(`theme-${colorName}`);
        }
        localStorage.setItem('themeColor', colorName);
    }

    generateStars(rating) {
        let stars = '';
        for (let i = 1; i <= 5; i++) {
            stars += `<i class="fas fa-star${i <= rating ? '' : ' star-empty'}" style="color: ${i <= rating ? '#ffc107' : '#e4e5e9'}"></i>`;
        }
        return stars;
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    formatDate(dateString) {
        if (!dateString) return '--';
        return new Date(dateString).toLocaleDateString('es-ES', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    }

    validateEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    createPageDots() {
        const span = document.createElement('span');
        span.className = 'page-number dots';
        span.textContent = '...';
        return span;
    }

    updateLastRefresh() {
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('es-ES');
    }

    showLoading() {
        document.querySelectorAll('.loading').forEach(el => {
            el.style.display = 'flex';
        });
    }

    showError(message) {
        Swal.fire({
            icon: 'error', title: 'Error', text: message,
            timer: 3000, showConfirmButton: false
        });
    }

    /**
     * 8. GESTIÓN DE SESIÓN Y CICLO DE VIDA
     */
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => this.loadData(), 5 * 60 * 1000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }

    logout() {
        Swal.fire({
            title: '¿Cerrar sesión?',
            text: '¿Estás seguro que deseas salir del dashboard?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, cerrar sesión',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                localStorage.removeItem('userId');
                localStorage.removeItem('userName');
                localStorage.removeItem('userEmail');
                this.stopAutoRefresh();
                window.location.href = '../pages/login.html';
            }
        });
    }
}

// Inicializar el dashboard
const dashboard = new Dashboard();

// Gestionar el refresco automático según la visibilidad de la página
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        dashboard.stopAutoRefresh();
    } else {
        dashboard.startAutoRefresh();
    }
});