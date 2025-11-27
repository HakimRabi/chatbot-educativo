class Dashboard {
    /**
     * 1. INICIALIZACIÓN Y CONFIGURACIÓN PRINCIPAL
     */
    constructor() {
        // Propiedades de estado
        this.currentSection = 'overview';
        this.refreshInterval = null;
        this.resourcesInterval = null;  // Intervalo para recursos
        this.charts = {};
        this.apiBaseUrl = ''; // Base URL for API calls (usa rutas relativas a través de nginx)

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

        // Datos y paginación de Sesiones (Tasks)
        this.sessionsData = [];
        this.filteredSessions = [];
        this.sessionsAutoRefresh = false;
        this.sessionsRefreshInterval = null;
        this.sessionsCurrentPage = 1;
        this.sessionsPerPage = 5;
        this.totalSessions = 0;

        this.init();
    }

    async init() {
        await this.checkAuth(); // Ahora es async y esperamos la verificación
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

    async checkAuth() {
        const userId = localStorage.getItem('userId');
        const userName = localStorage.getItem('userName');
        
        console.log('Verificando autenticación en dashboard:');
        console.log('- userId:', userId);
        console.log('- userName:', userName);
        
        if (!userId || !userName) {
            console.log('Usuario no autenticado, redirigiendo a login');
            window.location.href = '../pages/login.html';
            return;
        }
        
        // Verificar rol contra el servidor
        try {
            const response = await fetch('/auth/verify-role', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_id: userId })
            });
            
            const data = await response.json();
            
            console.log('Respuesta de verificación de rol:', data);
            
            if (!data.success || !data.is_admin) {
                console.log('Usuario sin permisos de admin según el servidor');
                // Limpiar localStorage
                localStorage.removeItem('userId');
                localStorage.removeItem('userName');
                localStorage.removeItem('userPermisos');
                
                Swal.fire({
                    icon: 'error',
                    title: 'Acceso Denegado',
                    text: 'No tienes permisos para acceder al dashboard administrativo.',
                    confirmButtonText: 'Volver al Login'
                }).then(() => {
                    window.location.href = '../pages/login.html';
                });
                return;
            }
            
            console.log('Acceso autorizado al dashboard por el servidor');
            document.getElementById('userName').textContent = userName;
        } catch (error) {
            console.error('Error verificando rol con el servidor:', error);
            // En caso de error de conexión, redirigir al login por seguridad
            localStorage.clear();
            window.location.href = '../pages/login.html';
        }
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

        // --- LISTENERS PARA SELECTOR DE RANGO DE FECHAS ---
        const applyDateRangeBtn = document.getElementById('applyDateRange');
        if (applyDateRangeBtn) {
            applyDateRangeBtn.addEventListener('click', () => this.applyDateRangeFilter());
        }

        // Inicializar fechas por defecto (últimos 5 días)
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(endDate.getDate() - 5);
        
        const startDateInput = document.getElementById('startDate');
        const endDateInput = document.getElementById('endDate');
        
        if (startDateInput && endDateInput) {
            startDateInput.value = startDate.toISOString().split('T')[0];
            endDateInput.value = endDate.toISOString().split('T')[0];
        }

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

        // --- LISTENERS PARA SESIONES ---
        const sessionsSearch = document.getElementById('sessionsSearch');
        if (sessionsSearch) {
            sessionsSearch.addEventListener('input', () => this.filterSessions());
        }
        
        const statusFilterSessions = document.getElementById('statusFilterSessions');
        if (statusFilterSessions) {
            statusFilterSessions.addEventListener('change', () => this.filterSessions());
        }
        
        const modelFilterSessions = document.getElementById('modelFilterSessions');
        if (modelFilterSessions) {
            modelFilterSessions.addEventListener('change', () => this.filterSessions());
        }
        
        const autoRefreshToggle = document.getElementById('autoRefreshToggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('click', () => this.toggleSessionsAutoRefresh());
        }

        const closeSessionModal = document.getElementById('closeSessionModal');
        if (closeSessionModal) {
            closeSessionModal.addEventListener('click', () => {
                document.getElementById('sessionDetailModal').style.display = 'none';
            });
        }

        // Paginación de Sesiones
        const sessionsPrevPage = document.getElementById('sessionsPrevPage');
        if (sessionsPrevPage) {
            sessionsPrevPage.addEventListener('click', () => {
                if (this.sessionsCurrentPage > 1) {
                    this.sessionsCurrentPage--;
                    this.renderSessionsTable();
                }
            });
        }
        
        const sessionsNextPage = document.getElementById('sessionsNextPage');
        if (sessionsNextPage) {
            sessionsNextPage.addEventListener('click', () => {
                const totalPages = Math.ceil(this.filteredSessions.length / this.sessionsPerPage);
                if (this.sessionsCurrentPage < totalPages) {
                    this.sessionsCurrentPage++;
                    this.renderSessionsTable();
                }
            });
        }

        // --- LISTENERS PARA DIAGNOSTICOS ---
        this.setupDiagnosticsListeners();
    }

    setupDiagnosticsListeners() {
        // User buttons para seleccionar cantidad de usuarios
        document.querySelectorAll('.user-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.user-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('customUsers').value = '';
            });
        });

        // Custom users input
        const customUsers = document.getElementById('customUsers');
        if (customUsers) {
            customUsers.addEventListener('input', () => {
                if (customUsers.value) {
                    document.querySelectorAll('.user-btn').forEach(b => b.classList.remove('active'));
                }
            });
        }

        // Start stress test button
        const startBtn = document.getElementById('startStressTest');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.startStressTest());
        }

        // Stop stress test button
        const stopBtn = document.getElementById('stopStressTest');
        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopStressTest());
        }
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
        'feedback': 'Gestion de Feedback',
        'users': 'Gestion de Usuarios',
        'sessions': 'Sesiones de Chat Activas',
        'resources': 'Monitor de Recursos',
        'system': 'Estado del Sistema',
        'diagnostics': 'Diagnosticos del Sistema'
    };        document.getElementById('sectionTitle').textContent = titles[sectionName] || 'Dashboard';
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
            case 'sessions':
                this.loadSessionsData();
                break;
            case 'resources':
                this.loadResourcesData();
                this.startResourcesMonitoring();
                break;
            case 'system':
                this.loadSystemHealth();
                break;
            case 'diagnostics':
                this.loadDiagnosticsData();
                break;
            default:
                this.stopResourcesMonitoring();
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
            
            // Actualizar sesiones activas (simulado por ahora)
            this.updateActiveSessions();
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
        
        // Elementos systemStatusIcon y systemStatusText no existen en el HTML actual
        // Se eliminó el código que intentaba acceder a ellos para evitar errores
        
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
    
    async applyDateRangeFilter() {
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        
        if (!startDate || !endDate) {
            alert('Por favor selecciona ambas fechas');
            return;
        }
        
        if (new Date(startDate) > new Date(endDate)) {
            alert('La fecha de inicio debe ser anterior a la fecha de fin');
            return;
        }
        
        try {
            // Calcular días entre fechas
            const start = new Date(startDate);
            const end = new Date(endDate);
            const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
            
            const response = await fetch(`${this.apiBaseUrl}/dashboard/user-sessions?days=${days}`);
            const sessions = await response.json();
            
            if (sessions.error) {
                console.error('Error loading filtered sessions:', sessions.error);
                return;
            }
            
            this.updateSessionsChart(sessions.daily_sessions || []);
        } catch (error) {
            console.error('Error applying date range filter:', error);
            alert('Error al aplicar el filtro de fechas');
        }
    }
    
    async updateActiveSessions() {
        try {
            // Por ahora simulamos las sesiones activas
            // En el futuro se consultará el endpoint real de tasks activas
            const activeSessionsElement = document.getElementById('activeSessions');
            if (activeSessionsElement) {
                // Aquí se conectará con el endpoint de sesiones activas cuando esté implementado
                activeSessionsElement.textContent = '0';
                console.log('Sesiones activas (pendiente de implementación completa)');
            }
        } catch (error) {
            console.error('Error updating active sessions:', error);
        }
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
            { id: 'aiHealth', key: 'ai_system_ready', label: 'Sistema de IA' },
            { id: 'phi4Health', key: 'phi4_status', label: 'Modelo Phi4' },
            { id: 'workersHealth', key: 'workers_status', label: 'Workers Celery' }
        ];
        
        indicators.forEach(indicator => {
            const element = document.getElementById(indicator.id);
            if (!element) return;
            
            let isHealthy = false;
            let statusText = 'Error';
            
            if (indicator.id === 'dbHealth') {
                isHealthy = health[indicator.key] || health[indicator.fallbackKey] || false;
                statusText = isHealthy ? 'Funcionando' : 'Desconectado';
            } else if (indicator.id === 'aiHealth') {
                isHealthy = health[indicator.key] || false;
                statusText = isHealthy ? 'Activo' : 'Inactivo';
            } else if (indicator.id === 'phi4Health') {
                const modelsStatus = health[indicator.key] || health['models_status'] || {};
                const modelsDetail = health['models_detail'] || '';
                
                if (modelsDetail === 'Ambos funcionando') {
                    isHealthy = true;
                    statusText = 'Ambos activos';
                } else if (modelsDetail === 'Solo Llama3') {
                    isHealthy = true;
                    statusText = 'Solo Llama3';
                } else if (modelsDetail === 'Solo Phi4') {
                    isHealthy = true;
                    statusText = 'Solo Phi4';
                } else if (modelsDetail === 'Ninguno disponible') {
                    isHealthy = false;
                    statusText = 'Ninguno disponible';
                } else {
                    isHealthy = false;
                    statusText = modelsDetail || 'Desconocido';
                }
            } else if (indicator.id === 'workersHealth') {
                const workersStatus = health[indicator.key] || 'unknown';
                const workersCount = health.workers_count || 0;
                isHealthy = workersStatus === 'activo' && workersCount > 0;
                
                if (workersStatus === 'activo' && workersCount > 0) {
                    statusText = `${workersCount} activo${workersCount > 1 ? 's' : ''}`;
                } else if (workersStatus === 'inactivo') {
                    statusText = 'Inactivo';
                } else if (workersStatus === 'error') {
                    statusText = 'Error';
                } else {
                    statusText = 'Desconocido';
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
     * 7. SECCIÓN: MONITOR DE RECURSOS
     */
    async loadResourcesData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/system-resources`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const resources = await response.json();
            
            if (resources.success) {
                this.updateResourcesUI(resources);
            } else {
                console.error('Error en recursos:', resources.error);
                this.showResourcesError();
            }
        } catch (error) {
            console.error('Error loading system resources:', error);
            this.showResourcesError();
        }
    }

    updateResourcesUI(resources) {
        // CPU
        const cpuPercent = resources.cpu.usage_percent || 0;
        document.getElementById('cpuUsage').textContent = `${cpuPercent.toFixed(1)}%`;
        document.getElementById('cpuProgress').style.width = `${cpuPercent}%`;
        document.getElementById('cpuProgress').className = `progress-fill ${this.getProgressClass(cpuPercent)}`;
        document.getElementById('cpuDetails').textContent = 
            `${resources.cpu.count_physical} núcleos físicos, ${resources.cpu.count_logical} lógicos | ${resources.cpu.frequency_current}`;
        
        // GPU
        if (resources.gpu.available) {
            const gpuLoad = resources.gpu.load_percent || parseFloat(resources.gpu.load) || 0;
            const gpuLoadText = resources.gpu.load || `${gpuLoad.toFixed(1)}%`;
            document.getElementById('gpuUsage').textContent = gpuLoadText;
            document.getElementById('gpuProgress').style.width = `${gpuLoad}%`;
            document.getElementById('gpuProgress').className = `progress-fill ${this.getProgressClass(gpuLoad)}`;
            
            let gpuDetails = resources.gpu.name || 'N/A';
            if (resources.gpu.vendor) {
                gpuDetails = `${resources.gpu.vendor} - ${gpuDetails}`;
            }
            if (resources.gpu.memory_used && resources.gpu.memory_total) {
                gpuDetails += ` | ${resources.gpu.memory_used} / ${resources.gpu.memory_total}`;
            }
            document.getElementById('gpuDetails').textContent = gpuDetails;
        } else {
            document.getElementById('gpuUsage').textContent = 'N/A';
            document.getElementById('gpuProgress').style.width = '0%';
            document.getElementById('gpuDetails').textContent = resources.gpu.message || 'GPU no disponible';
        }
        
        // RAM
        document.getElementById('ramUsage').textContent = `${resources.memory.percent.toFixed(1)}%`;
        document.getElementById('ramProgress').style.width = `${resources.memory.percent}%`;
        document.getElementById('ramProgress').className = `progress-fill ${this.getProgressClass(resources.memory.percent)}`;
        document.getElementById('ramDetails').textContent = 
            `${resources.memory.used} / ${resources.memory.total} | ${resources.memory.available} disponibles`;
        
        // Disco
        document.getElementById('diskUsage').textContent = `${resources.disk.percent.toFixed(1)}%`;
        document.getElementById('diskProgress').style.width = `${resources.disk.percent}%`;
        document.getElementById('diskProgress').className = `progress-fill ${this.getProgressClass(resources.disk.percent)}`;
        document.getElementById('diskDetails').textContent = 
            `${resources.disk.used} / ${resources.disk.total} | ${resources.disk.free} libres`;
        
        // Temperatura
        const cpuTemp = resources.cpu.temperature;
        document.getElementById('tempValue').textContent = cpuTemp;
        
        let tempDetails = `CPU: ${cpuTemp}`;
        if (resources.gpu.available && resources.gpu.temperature) {
            tempDetails += ` | GPU: ${resources.gpu.temperature}`;
        }
        document.getElementById('tempDetails').textContent = tempDetails;
        
        // Red
        document.getElementById('networkValue').textContent = 
            `${resources.network.bytes_recv} ↓ / ${resources.network.bytes_sent} ↑`;
        document.getElementById('netReceived').textContent = resources.network.bytes_recv;
        document.getElementById('netSent').textContent = resources.network.bytes_sent;
        
        // Especificaciones del Sistema
        const specsHTML = `
            <div class="spec-item">
                <strong>Sistema Operativo:</strong> ${resources.system.platform} ${resources.system.platform_release}
            </div>
            <div class="spec-item">
                <strong>Arquitectura:</strong> ${resources.system.architecture}
            </div>
            <div class="spec-item">
                <strong>Procesador:</strong> ${resources.system.processor}
            </div>
            <div class="spec-item">
                <strong>Hostname:</strong> ${resources.system.hostname}
            </div>
            <div class="spec-item">
                <strong>CPU:</strong> ${resources.cpu.count_physical} núcleos físicos, ${resources.cpu.count_logical} lógicos
            </div>
            <div class="spec-item">
                <strong>Frecuencia CPU:</strong> ${resources.cpu.frequency_current} (Max: ${resources.cpu.frequency_max})
            </div>
            ${resources.gpu.available ? `
            <div class="spec-item">
                <strong>GPU:</strong> ${resources.gpu.name}
            </div>
            <div class="spec-item">
                <strong>VRAM:</strong> ${resources.gpu.memory_total}
            </div>` : ''}
        `;
        document.getElementById('systemSpecs').innerHTML = specsHTML;
    }

    getProgressClass(percent) {
        if (percent < 50) return 'progress-low';
        if (percent < 80) return 'progress-medium';
        return 'progress-high';
    }

    showResourcesError() {
        const errorHTML = '<div class="error">Error al cargar métricas del sistema</div>';
        ['cpuUsage', 'gpuUsage', 'ramUsage', 'diskUsage', 'tempValue', 'networkValue'].forEach(id => {
            document.getElementById(id).textContent = 'Error';
        });
        document.getElementById('systemSpecs').innerHTML = errorHTML;
    }

    startResourcesMonitoring() {
        // Cargar inmediatamente
        this.loadResourcesData();
        
        // Actualizar cada 5 segundos (óptimo para no sobrecargar)
        if (this.resourcesInterval) {
            clearInterval(this.resourcesInterval);
        }
        this.resourcesInterval = setInterval(() => {
            if (this.currentSection === 'resources') {
                this.loadResourcesData();
            }
        }, 5000);
    }

    stopResourcesMonitoring() {
        if (this.resourcesInterval) {
            clearInterval(this.resourcesInterval);
            this.resourcesInterval = null;
        }
    }
    
    /**
     * 8. MÉTODOS UTILITARIOS Y DE CONFIGURACIÓN
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

    // ==================== SESIONES ====================
    async loadSessionsData() {
        try {
            const response = await fetch('/dashboard/active-tasks', {
                headers: {
                    'user-id': this.userId
                }
            });
            
            if (!response.ok) {
                throw new Error('Error al cargar sesiones');
            }
            
            const data = await response.json();
            this.sessionsData = data.tasks || [];
            this.totalSessions = this.sessionsData.length;
            
            // Actualizar estadísticas con los valores correctos del backend
            const stats = data.stats || {};
            const tasksProcessingEl = document.getElementById('tasksProcessing');
            const tasksPendingEl = document.getElementById('tasksPending');
            const tasksCompletedEl = document.getElementById('tasksCompleted');
            const tasksFailedEl = document.getElementById('tasksFailed');
            
            if (tasksProcessingEl) tasksProcessingEl.textContent = stats.processing || 0;
            if (tasksPendingEl) tasksPendingEl.textContent = stats.pending || 0;
            if (tasksCompletedEl) tasksCompletedEl.textContent = stats.completed || 0;
            if (tasksFailedEl) tasksFailedEl.textContent = stats.failed || 0;
            
            console.log('Stats actualizadas:', stats);
            
            // Aplicar filtros y renderizar
            this.filterSessions();
            
        } catch (error) {
            console.error('Error loading sessions:', error);
            this.showError('Error al cargar las sesiones activas');
        }
    }

    renderSessionsTable(tasks = null) {
        const tbody = document.getElementById('sessionsTableBody');
        const displayTasks = tasks || this.filteredSessions;
        
        if (!displayTasks || displayTasks.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center py-4 text-gray-500">
                        <i class="fas fa-inbox text-4xl mb-2"></i>
                        <p>No se encontraron sesiones</p>
                    </td>
                </tr>
            `;
            this.updateSessionsPaginationInfo();
            this.updateSessionsPaginationControls();
            return;
        }
        
        // Aplicar paginación
        const start = (this.sessionsCurrentPage - 1) * this.sessionsPerPage;
        const end = start + this.sessionsPerPage;
        const paginatedTasks = displayTasks.slice(start, end);
        
        tbody.innerHTML = paginatedTasks.map(task => {
            const statusBadge = this.getStatusBadge(task.status);
            const ragBadge = task.vector_db_used ? 
                '<span class="badge badge-rag-enabled">RAG</span>' : 
                '<span class="badge badge-rag-disabled">Sin RAG</span>';
            
            const truncatedQuery = task.query && task.query.length > 50 ? 
                task.query.substring(0, 50) + '...' : task.query || '-';
            
            const elapsedTime = this.formatElapsedTime(task);
            const formattedDate = this.formatDateTime(task.created_at);
            const userName = task.username ? `${task.username} (ID: ${task.user_id})` : `Usuario #${task.user_id}`;
            
            return `
                <tr class="hover:bg-gray-50 transition-colors cursor-pointer" onclick="dashboard.showSessionDetail('${task.task_id}')">
                    <td class="px-4 py-3">
                        <code class="task-id-badge" title="Click para copiar" onclick="event.stopPropagation(); dashboard.copyTaskId('${task.task_id}')">
                            ${task.task_id.substring(0, 8)}...
                        </code>
                    </td>
                    <td class="px-4 py-3">
                        <span class="font-medium">${userName}</span>
                    </td>
                    <td class="px-4 py-3">
                        <span class="text-gray-700" title="${task.query || '-'}">${truncatedQuery}</span>
                    </td>
                    <td class="px-4 py-3">
                        <span class="badge badge-model">${task.model || 'N/A'}</span>
                    </td>
                    <td class="px-4 py-3">${statusBadge}</td>
                    <td class="px-4 py-3">
                        <span class="text-gray-600">${elapsedTime}</span>
                    </td>
                    <td class="px-4 py-3">
                        <span class="text-gray-600">${task.worker_name || '-'}</span>
                    </td>
                    <td class="px-4 py-3 text-center">
                        ${ragBadge}
                        ${task.documents_count ? `<span class="ml-1 text-xs text-gray-500">(${task.documents_count} docs)</span>` : ''}
                    </td>
                    <td class="px-4 py-3">
                        <span class="text-gray-600 text-sm">${formattedDate}</span>
                    </td>
                    <td class="px-4 py-3">
                        <button class="btn-action" onclick="event.stopPropagation(); dashboard.showSessionDetail('${task.task_id}')" title="Ver detalles">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn-action btn-delete" onclick="event.stopPropagation(); dashboard.deleteTask('${task.task_id}')" title="Eliminar tarea">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
        this.updateSessionsPaginationInfo();
        this.updateSessionsPaginationControls();
    }

    getStatusBadge(status) {
        const badges = {
            'pending': '<span class="badge badge-pending"><i class="fas fa-clock mr-1"></i> Pendiente</span>',
            'processing': '<span class="badge badge-processing"><i class="fas fa-spinner fa-spin mr-1"></i> Procesando</span>',
            'completed': '<span class="badge badge-completed"><i class="fas fa-check-circle mr-1"></i> Completado</span>',
            'failed': '<span class="badge badge-failed"><i class="fas fa-times-circle mr-1"></i> Fallido</span>'
        };
        return badges[status] || `<span class="badge badge-secondary">${status}</span>`;
    }

    formatElapsedTime(task) {
        // Prioridad 1: Tiempo de procesamiento completado
        if (task.processing_time !== null && task.processing_time !== undefined) {
            return `${parseFloat(task.processing_time).toFixed(2)}s`;
        }
        
        // Prioridad 2: Calcularlo si está procesando
        if (task.status === 'processing' && task.started_at) {
            const start = new Date(task.started_at);
            const now = new Date();
            const elapsed = (now - start) / 1000;
            return `${elapsed.toFixed(0)}s`;
        }
        
        // Prioridad 3: Estados especiales
        if (task.status === 'pending') {
            return 'En espera';
        }
        
        if (task.status === 'failed') {
            return 'Fallido';
        }
        
        return '-';
    }

    formatDateTime(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        const now = new Date();
        const diff = (now - date) / 1000; // segundos
        
        if (diff < 60) return 'Hace un momento';
        if (diff < 3600) return `Hace ${Math.floor(diff / 60)} min`;
        if (diff < 86400) return `Hace ${Math.floor(diff / 3600)} h`;
        
        return date.toLocaleDateString('es-ES', { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    filterSessions() {
        const searchTerm = document.getElementById('sessionsSearch').value.toLowerCase();
        const statusFilter = document.getElementById('statusFilterSessions').value;
        const modelFilter = document.getElementById('modelFilterSessions').value;
        
        this.filteredSessions = this.sessionsData.filter(task => {
            const matchesSearch = !searchTerm || 
                task.task_id.toLowerCase().includes(searchTerm) ||
                (task.query && task.query.toLowerCase().includes(searchTerm)) ||
                (task.username && task.username.toLowerCase().includes(searchTerm));
            
            const matchesStatus = !statusFilter || task.status === statusFilter;
            const matchesModel = !modelFilter || task.model === modelFilter;
            
            return matchesSearch && matchesStatus && matchesModel;
        });
        
        // Reset a la primera página cuando se aplica un filtro
        this.sessionsCurrentPage = 1;
        this.renderSessionsTable();
    }

    toggleSessionsAutoRefresh() {
        this.sessionsAutoRefresh = !this.sessionsAutoRefresh;
        const button = document.getElementById('autoRefreshToggle');
        
        if (this.sessionsAutoRefresh) {
            button.classList.add('active');
            button.innerHTML = '<i class="fas fa-pause mr-2"></i>Auto-refresh ON';
            
            // Refresh inmediato
            this.loadSessionsData();
            
            // Configurar intervalo de 5 segundos
            this.sessionsRefreshInterval = setInterval(() => {
                this.loadSessionsData();
            }, 5000);
            
            this.showSuccess('Auto-refresh activado (cada 5s)');
        } else {
            button.classList.remove('active');
            button.innerHTML = '<i class="fas fa-play mr-2"></i>Auto-refresh OFF';
            
            if (this.sessionsRefreshInterval) {
                clearInterval(this.sessionsRefreshInterval);
                this.sessionsRefreshInterval = null;
            }
            
            this.showInfo('Auto-refresh desactivado');
        }
    }

    async showSessionDetail(taskId) {
        const task = this.sessionsData.find(t => t.task_id === taskId);
        if (!task) {
            this.showError('No se encontró la sesión');
            return;
        }
        
        const modal = document.getElementById('sessionDetailModal');
        const content = document.getElementById('sessionDetailContent');
        
        // Construir HTML del detalle
        const html = `
            <div class="session-detail-grid">
                <div class="detail-section">
                    <h4 class="detail-section-title">Información General</h4>
                    <div class="detail-item">
                        <span class="detail-label">Task ID:</span>
                        <span class="detail-value" onclick="dashboard.copyTaskId('${task.task_id}')" title="Click para copiar" style="cursor: pointer; user-select: all;">
                            ${task.task_id}
                        </span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Usuario:</span>
                        <span class="detail-value">${task.username || 'Usuario #' + task.user_id}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Estado:</span>
                        <span class="detail-value">${this.getStatusBadge(task.status)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Modelo:</span>
                        <span class="badge badge-model">${task.model || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Worker:</span>
                        <span class="detail-value">${task.worker_name || 'No asignado'}</span>
                    </div>
                </div>

                <div class="detail-section">
                    <h4 class="detail-section-title">Tiempos</h4>
                    <div class="detail-item">
                        <span class="detail-label">Creado:</span>
                        <span class="detail-value">${new Date(task.created_at).toLocaleString('es-ES')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Iniciado:</span>
                        <span class="detail-value">${task.started_at ? new Date(task.started_at).toLocaleString('es-ES') : 'No iniciado'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Finalizado:</span>
                        <span class="detail-value">${task.completed_at ? new Date(task.completed_at).toLocaleString('es-ES') : 'En curso'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Tiempo de procesamiento:</span>
                        <span class="detail-value font-semibold">${this.formatElapsedTime(task)}</span>
                    </div>
                </div>

                <div class="detail-section">
                    <h4 class="detail-section-title">RAG & Documentos</h4>
                    <div class="detail-item">
                        <span class="detail-label">Vector DB usado:</span>
                        <span class="detail-value">
                            ${task.vector_db_used ? 
                                '<span class="badge badge-rag-enabled"><i class="fas fa-check mr-1"></i>Sí</span>' : 
                                '<span class="badge badge-rag-disabled"><i class="fas fa-times mr-1"></i>No</span>'}
                        </span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Documentos consultados:</span>
                        <span class="detail-value font-semibold">${task.documents_count || 0}</span>
                    </div>
                </div>

                ${task.error_message ? `
                <div class="detail-section error-section">
                    <h4 class="detail-section-title text-red-600">Error</h4>
                    <div class="detail-item">
                        <pre class="error-message">${task.error_message}</pre>
                    </div>
                </div>
                ` : ''}

                <div class="detail-section full-width">
                    <h4 class="detail-section-title">Consulta</h4>
                    <div class="query-box">
                        ${task.query_full || task.query || '<em class="text-gray-400">Sin consulta</em>'}
                    </div>
                </div>

                ${(task.response_full || task.response) ? `
                <div class="detail-section full-width">
                    <h4 class="detail-section-title">Respuesta</h4>
                    <div class="response-box">
                        ${task.response_full || task.response}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
        
        content.innerHTML = html;
        modal.style.display = 'block';
    }

    copyTaskId(taskId) {
        navigator.clipboard.writeText(taskId).then(() => {
            showNotification('Task ID copiado al portapapeles', 'success', 2000);
        }).catch(() => {
            showNotification('Error al copiar Task ID', 'error', 3000);
        });
    }

    deleteTask(taskId) {
        const task = this.sessionsData.find(t => t.task_id === taskId);
        const taskInfo = task ? `Task ${taskId.substring(0, 8)}...` : taskId;

        Swal.fire({
            title: '¿Eliminar tarea?',
            html: `Se eliminará la tarea <strong>${taskInfo}</strong>.<br><br>Esta acción no se puede deshacer.`,
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
                        text: 'Eliminando tarea...',
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });
                    
                    const response = await fetch(`/dashboard/tasks/${taskId}`, {
                        method: 'DELETE',
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        Swal.fire('Eliminado', data.message || 'La tarea ha sido eliminada.', 'success');
                        this.loadSessionsData();
                    } else {
                        throw new Error(data.detail || data.message || 'Error al eliminar.');
                    }
                } catch (error) {
                    console.error('Error al eliminar tarea:', error);
                    Swal.fire('Error', `No se pudo eliminar la tarea. ${error.message}`, 'error');
                }
            }
        });
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        // Detener auto-refresh de sesiones también
        if (this.sessionsRefreshInterval) {
            clearInterval(this.sessionsRefreshInterval);
            this.sessionsAutoRefresh = false;
        }
    }

    updateSessionsPaginationInfo() {
        const totalFiltered = this.filteredSessions.length;
        const start = totalFiltered > 0 ? (this.sessionsCurrentPage - 1) * this.sessionsPerPage + 1 : 0;
        const end = Math.min(this.sessionsCurrentPage * this.sessionsPerPage, totalFiltered);
        
        const infoElement = document.getElementById('sessionsPaginationInfo');
        if (infoElement) {
            infoElement.textContent = `Mostrando ${start} - ${end} de ${totalFiltered} sesiones`;
        }
    }

    updateSessionsPaginationControls() {
        const totalPages = Math.ceil(this.filteredSessions.length / this.sessionsPerPage);
        const prevBtn = document.getElementById('sessionsPrevPage');
        const nextBtn = document.getElementById('sessionsNextPage');
        
        if (prevBtn) {
            prevBtn.disabled = this.sessionsCurrentPage === 1;
        }
        if (nextBtn) {
            nextBtn.disabled = this.sessionsCurrentPage >= totalPages || totalPages === 0;
        }
    }

    logout() {
        Swal.fire({
            title: 'Cerrar sesion?',
            text: 'Estas seguro que deseas salir del dashboard?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Si, cerrar sesion',
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

    // =====================================================
    // DIAGNOSTICS - STRESS TESTS METHODS
    // =====================================================

    async loadDiagnosticsData() {
        try {
            // Cargar hardware info
            await this.loadHardwareInfo();
            
            // Cargar historial de tests
            await this.loadDiagnosticsHistory();
            
        } catch (error) {
            console.error('Error loading diagnostics data:', error);
        }
    }

    async loadHardwareInfo() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/hardware`);
            const data = await response.json();
            
            if (data.success && data.hardware) {
                const hw = data.hardware;
                document.getElementById('hwCpu').textContent = hw.cpu_model || 'N/A';
                document.getElementById('hwCores').textContent = `${hw.cpu_cores || 0} cores (${hw.cpu_threads || 0} threads)`;
                document.getElementById('hwGpu').textContent = hw.gpu_model || 'No detectada';
                document.getElementById('hwVram').textContent = hw.gpu_vram_gb ? `${hw.gpu_vram_gb} GB` : 'N/A';
                document.getElementById('hwRam').textContent = hw.ram_total_gb ? `${hw.ram_total_gb} GB` : 'N/A';
                document.getElementById('hwOs').textContent = hw.os || 'N/A';
            }
        } catch (error) {
            console.error('Error loading hardware info:', error);
            document.getElementById('hwCpu').textContent = 'Error al cargar';
        }
    }

    async loadDiagnosticsHistory() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/tests?limit=20`);
            const data = await response.json();
            
            const tbody = document.getElementById('diagnosticsHistoryBody');
            if (!tbody) return;
            
            if (!data.success || !data.tests || data.tests.length === 0) {
                tbody.innerHTML = '<tr><td colspan="10" class="text-center">No hay tests registrados</td></tr>';
                return;
            }
            
            tbody.innerHTML = data.tests.map(test => {
                const config = test.config || {};
                const summary = test.summary || {};
                const peak = summary.resources_peak || {};
                const timing = summary.timing || {};
                
                const statusClass = `badge-test-${test.status.toLowerCase()}`;
                const statusText = {
                    'COMPLETED': 'Completado',
                    'PROCESSING': 'En Proceso',
                    'FAILED': 'Fallido',
                    'PENDING': 'Pendiente'
                }[test.status] || test.status;
                
                return `
                    <tr>
                        <td>${test.name || 'Sin nombre'}</td>
                        <td>${config.concurrent_users || '-'}</td>
                        <td>${config.model_target || '-'}</td>
                        <td>${test.duration_seconds ? test.duration_seconds.toFixed(1) + 's' : '-'}</td>
                        <td>${peak.cpu_max_percent ? peak.cpu_max_percent.toFixed(1) + '%' : '-'}</td>
                        <td>${peak.gpu_max_percent ? peak.gpu_max_percent.toFixed(1) + '%' : '-'}</td>
                        <td>${timing.avg_latency_ms ? timing.avg_latency_ms.toFixed(0) + 'ms' : '-'}</td>
                        <td><span class="${statusClass}">${statusText}</span></td>
                        <td>${test.created_at ? new Date(test.created_at).toLocaleString() : '-'}</td>
                        <td>
                            <button class="btn-icon btn-view" onclick="dashboard.viewTestDetail('${test.test_id}')" title="Ver detalle">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn-icon btn-export btn-excel" onclick="dashboard.exportTest('${test.test_id}', 'xlsx')" title="Exportar Excel">
                                <i class="fas fa-file-excel"></i>
                            </button>
                            <button class="btn-icon btn-export" onclick="dashboard.exportTest('${test.test_id}', 'json')" title="Exportar JSON">
                                <i class="fas fa-file-code"></i>
                            </button>
                            <button class="btn-icon btn-delete" onclick="dashboard.deleteTest('${test.test_id}')" title="Eliminar">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
            
        } catch (error) {
            console.error('Error loading diagnostics history:', error);
            const tbody = document.getElementById('diagnosticsHistoryBody');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Error al cargar historial</td></tr>';
            }
        }
    }

    getStressTestConfig() {
        // Obtener usuarios seleccionados
        let concurrentUsers = 10;
        const activeBtn = document.querySelector('.user-btn.active');
        if (activeBtn) {
            concurrentUsers = parseInt(activeBtn.dataset.users);
        }
        const customUsers = document.getElementById('customUsers');
        if (customUsers && customUsers.value) {
            concurrentUsers = parseInt(customUsers.value);
        }

        // Obtener complejidad
        const complexityRadio = document.querySelector('input[name="complexity"]:checked');
        const complexity = complexityRadio ? complexityRadio.value : 'medium';

        // Obtener modelo
        const modelRadio = document.querySelector('input[name="model"]:checked');
        const model = modelRadio ? modelRadio.value : 'phi4';

        return {
            test_type: document.getElementById('testType').value,
            concurrent_users: concurrentUsers,
            queries_per_user: parseInt(document.getElementById('queriesPerUser').value),
            duration_seconds: parseInt(document.getElementById('maxDuration').value),
            ramp_up_seconds: parseInt(document.getElementById('rampUp').value),
            query_complexity: complexity,
            model_target: model,
            use_rag: document.getElementById('useRag').checked,
            snapshot_interval_seconds: parseInt(document.getElementById('snapshotInterval').value)
        };
    }

    async startStressTest() {
        const name = document.getElementById('testName').value || `Test ${new Date().toLocaleString()}`;
        const config = this.getStressTestConfig();
        
        // Confirmar inicio
        const result = await Swal.fire({
            title: 'Iniciar Test de Estres',
            html: `
                <p>Se iniciara un test con la siguiente configuracion:</p>
                <ul style="text-align: left; margin-top: 10px;">
                    <li><strong>Usuarios:</strong> ${config.concurrent_users}</li>
                    <li><strong>Queries/Usuario:</strong> ${config.queries_per_user}</li>
                    <li><strong>Modelo:</strong> ${config.model_target}</li>
                    <li><strong>RAG:</strong> ${config.use_rag ? 'Si' : 'No'}</li>
                </ul>
                <p style="margin-top: 10px; color: #666;">Esto puede generar carga en el sistema.</p>
            `,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Iniciar Test',
            cancelButtonText: 'Cancelar'
        });

        if (!result.isConfirmed) return;

        try {
            const userId = localStorage.getItem('userId') || 1;
            
            const response = await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/tests/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, config, user_id: userId })
            });

            const data = await response.json();

            if (data.success) {
                this.currentTestId = data.test_id;
                this.showRunningTest(name);
                this.startTestPolling(data.test_id);
                
                Swal.fire({
                    icon: 'success',
                    title: 'Test Iniciado',
                    text: 'El test de estres se ha iniciado correctamente.',
                    timer: 2000,
                    showConfirmButton: false
                });
            } else {
                throw new Error(data.detail || 'Error iniciando test');
            }
        } catch (error) {
            console.error('Error starting stress test:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.message || 'No se pudo iniciar el test de estres'
            });
        }
    }

    showRunningTest(name) {
        const container = document.getElementById('runningTestContainer');
        if (container) {
            container.style.display = 'block';
            document.getElementById('runningTestName').textContent = name;
            document.getElementById('runningLog').innerHTML = '';
        }
    }

    hideRunningTest() {
        const container = document.getElementById('runningTestContainer');
        if (container) {
            container.style.display = 'none';
        }
    }

    startTestPolling(testId) {
        this.testPollingInterval = setInterval(async () => {
            try {
                const response = await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/tests/${testId}/status`);
                const data = await response.json();

                if (data.success) {
                    // Actualizar logs
                    const logContainer = document.getElementById('runningLog');
                    if (logContainer && data.logs) {
                        logContainer.innerHTML = data.logs.slice(-50).join('<br>');
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }

                    // Actualizar metricas si hay snapshots
                    if (data.snapshots && data.snapshots.length > 0) {
                        const latest = data.snapshots[data.snapshots.length - 1];
                        this.updateRunningMetrics(latest);
                    }

                    // Si termino, detener polling
                    if (!data.is_running || data.status === 'COMPLETED' || data.status === 'FAILED') {
                        this.stopTestPolling();
                        this.hideRunningTest();
                        this.loadDiagnosticsHistory();
                        
                        const statusText = data.status === 'COMPLETED' ? 'completado' : 'fallido';
                        Swal.fire({
                            icon: data.status === 'COMPLETED' ? 'success' : 'error',
                            title: `Test ${statusText}`,
                            text: data.status === 'COMPLETED' 
                                ? 'El test se ha completado. Revisa los resultados en el historial.'
                                : 'El test ha fallido. Revisa los logs para mas detalles.'
                        });
                    }
                }
            } catch (error) {
                console.error('Error polling test status:', error);
            }
        }, 2000);
    }

    stopTestPolling() {
        if (this.testPollingInterval) {
            clearInterval(this.testPollingInterval);
            this.testPollingInterval = null;
        }
    }

    updateRunningMetrics(snapshot) {
        const sys = snapshot.system || {};
        const gpu = snapshot.gpu || {};

        // CPU
        const cpuPct = sys.cpu_percent || 0;
        document.getElementById('runningCpu').style.width = `${cpuPct}%`;
        document.getElementById('runningCpuValue').textContent = `${cpuPct.toFixed(1)}%`;

        // RAM
        const ramPct = sys.ram_percent || 0;
        document.getElementById('runningRam').style.width = `${ramPct}%`;
        document.getElementById('runningRamValue').textContent = `${ramPct.toFixed(1)}%`;

        // GPU
        const gpuPct = gpu.gpu_percent || 0;
        document.getElementById('runningGpu').style.width = `${gpuPct}%`;
        document.getElementById('runningGpuValue').textContent = `${gpuPct.toFixed(1)}%`;

        // Temperature
        const temp = gpu.temperature_c || 0;
        const tempPct = Math.min((temp / 100) * 100, 100);
        document.getElementById('runningTemp').style.width = `${tempPct}%`;
        document.getElementById('runningTempValue').textContent = `${temp}C`;
    }

    async stopStressTest() {
        if (!this.currentTestId) return;

        const result = await Swal.fire({
            title: 'Detener Test?',
            text: 'El test se marcara como fallido.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Si, detener',
            cancelButtonText: 'Cancelar'
        });

        if (!result.isConfirmed) return;

        try {
            await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/tests/${this.currentTestId}/stop`, {
                method: 'POST'
            });
            
            this.stopTestPolling();
            this.hideRunningTest();
            this.loadDiagnosticsHistory();
            
        } catch (error) {
            console.error('Error stopping test:', error);
        }
    }

    async viewTestDetail(testId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/tests/${testId}`);
            const data = await response.json();

            if (!data.success || !data.test) {
                throw new Error('No se pudo cargar el detalle del test');
            }

            const test = data.test;
            const config = test.config || {};
            const summary = test.summary || {};
            const peak = summary.resources_peak || {};
            const avg = summary.resources_avg || {};
            const timing = summary.timing || {};
            const throughput = summary.throughput || {};

            Swal.fire({
                title: test.name,
                html: `
                    <div style="text-align: left; max-height: 400px; overflow-y: auto;">
                        <h4 style="margin-bottom: 10px; color: #333;">Configuracion</h4>
                        <table style="width: 100%; margin-bottom: 20px;">
                            <tr><td><strong>Usuarios:</strong></td><td>${config.concurrent_users || '-'}</td></tr>
                            <tr><td><strong>Queries/Usuario:</strong></td><td>${config.queries_per_user || '-'}</td></tr>
                            <tr><td><strong>Modelo:</strong></td><td>${config.model_target || '-'}</td></tr>
                            <tr><td><strong>RAG:</strong></td><td>${config.use_rag ? 'Si' : 'No'}</td></tr>
                            <tr><td><strong>Duracion:</strong></td><td>${test.duration_seconds?.toFixed(2) || '-'}s</td></tr>
                        </table>

                        <h4 style="margin-bottom: 10px; color: #333;">Resultados</h4>
                        <table style="width: 100%; margin-bottom: 20px;">
                            <tr><td><strong>Queries Exitosas:</strong></td><td>${summary.successful_queries || 0} / ${summary.total_queries || 0}</td></tr>
                            <tr><td><strong>Tasa Exito:</strong></td><td>${summary.success_rate?.toFixed(1) || 0}%</td></tr>
                            <tr><td><strong>Throughput:</strong></td><td>${throughput.queries_per_second?.toFixed(2) || 0} QPS</td></tr>
                        </table>

                        <h4 style="margin-bottom: 10px; color: #333;">Latencia</h4>
                        <table style="width: 100%; margin-bottom: 20px;">
                            <tr><td><strong>Promedio:</strong></td><td>${timing.avg_latency_ms?.toFixed(0) || '-'} ms</td></tr>
                            <tr><td><strong>Min:</strong></td><td>${timing.min_latency_ms?.toFixed(0) || '-'} ms</td></tr>
                            <tr><td><strong>Max:</strong></td><td>${timing.max_latency_ms?.toFixed(0) || '-'} ms</td></tr>
                            <tr><td><strong>P95:</strong></td><td>${timing.p95_latency_ms?.toFixed(0) || '-'} ms</td></tr>
                        </table>

                        <h4 style="margin-bottom: 10px; color: #333;">Recursos (Pico)</h4>
                        <table style="width: 100%; margin-bottom: 20px;">
                            <tr><td><strong>CPU Max:</strong></td><td>${peak.cpu_max_percent?.toFixed(1) || '-'}%</td></tr>
                            <tr><td><strong>RAM Max:</strong></td><td>${peak.ram_max_percent?.toFixed(1) || '-'}%</td></tr>
                            <tr><td><strong>GPU Max:</strong></td><td>${peak.gpu_max_percent?.toFixed(1) || '-'}%</td></tr>
                            <tr><td><strong>Temp Max:</strong></td><td>${peak.temperature_max_c || '-'}C</td></tr>
                        </table>
                    </div>
                `,
                width: 600,
                showConfirmButton: true,
                confirmButtonText: 'Cerrar'
            });

        } catch (error) {
            console.error('Error viewing test detail:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo cargar el detalle del test'
            });
        }
    }

    async exportTest(testId, format = 'csv') {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/tests/${testId}/export?format=${format}`);
            
            if (!response.ok) {
                throw new Error('Error exportando test');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `stress_test_${testId}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

        } catch (error) {
            console.error('Error exporting test:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo exportar el test'
            });
        }
    }

    async deleteTest(testId) {
        const result = await Swal.fire({
            title: 'Eliminar Test?',
            text: 'Esta accion no se puede deshacer.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            confirmButtonText: 'Si, eliminar',
            cancelButtonText: 'Cancelar'
        });

        if (!result.isConfirmed) return;

        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/diagnostics/tests/${testId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Test Eliminado',
                    timer: 1500,
                    showConfirmButton: false
                });
                this.loadDiagnosticsHistory();
            } else {
                throw new Error(data.detail || 'Error eliminando test');
            }

        } catch (error) {
            console.error('Error deleting test:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: error.message || 'No se pudo eliminar el test'
            });
        }
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