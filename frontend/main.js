document.addEventListener('DOMContentLoaded', () => {
    const videoUrlInput = document.getElementById('video-url');
    const fetchBtn = document.getElementById('fetch-info-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const qualityWarning = document.getElementById('quality-warning');
    const videoInfoCard = document.getElementById('video-info-card');
    const thumbnailImg = document.getElementById('video-thumbnail');
    const titleEl = document.getElementById('video-title');
    const uploaderEl = document.getElementById('video-uploader');
    const descriptionEl = document.getElementById('video-description');
    const formatSelect = document.getElementById('format-select');
    const downloadBtn = document.getElementById('download-btn');
    const downloadThumbBtn = document.getElementById('download-thumb-btn');
    const downloadProgress = document.getElementById('download-progress');
    const showTranscriptBtn = document.getElementById('show-transcript-btn');
    const transcriptSection = document.getElementById('transcript-section');
    const transcriptContent = document.getElementById('transcript-content');
    const copyTranscriptBtn = document.getElementById('copy-transcript-btn');
    const downloadTxtBtn = document.getElementById('download-txt-btn');
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.getElementById('progress-text');

    const loginModal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('login-btn');
    const passwordInput = document.getElementById('app-password');
    const loginError = document.getElementById('login-error');

    const API_BASE = 'http://127.0.0.1:5000/api'; // Cambiar a la URL de Render después
    const APP_PASSWORD = 'pablo'; // CAMBIA TU CONTRASEÑA AQUÍ
    
    // Login Logic
    loginBtn.addEventListener('click', () => {
        if (passwordInput.value === APP_PASSWORD) {
            loginModal.classList.add('hidden');
            localStorage.setItem('app_logged_in', 'true');
        } else {
            loginError.classList.remove('hidden');
            passwordInput.value = '';
        }
    });

    passwordInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loginBtn.click();
    });

    // Check session
    if (localStorage.getItem('app_logged_in') === 'true') {
        loginModal.classList.add('hidden');
    }

    let currentMaxResThumbnail = '';

    fetchBtn.addEventListener('click', async () => {
        const url = videoUrlInput.value.trim();
        if (!url) {
            alert('Por favor, pega una URL válida de YouTube');
            return;
        }

        // Reset UI
        videoInfoCard.classList.add('hidden');
        qualityWarning.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');
        transcriptSection.classList.add('hidden');
        showTranscriptBtn.classList.add('hidden');
        downloadTxtBtn.classList.add('hidden');
        
        // Clear previous info
        titleEl.textContent = '';
        uploaderEl.textContent = '';
        descriptionEl.textContent = '';
        thumbnailImg.src = '';
        formatSelect.innerHTML = '';

        try {
            const response = await fetch(`${API_BASE}/video-info`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (data.error) {
                const cleanError = data.error.replace(/\u001b\[[0-9;]*m/g, '');
                alert(cleanError);
                return;
            }

            // Populate Video Info
            thumbnailImg.src = data.thumbnail;
            titleEl.textContent = data.title;
            uploaderEl.textContent = data.uploader;
            descriptionEl.textContent = data.description;
            currentMaxResThumbnail = data.max_res_thumbnail;

            // Fill Formats
            formatSelect.innerHTML = '';
            data.formats.forEach(f => {
                const option = document.createElement('option');
                option.value = f.format_id;
                const size = f.filesize ? `(${(f.filesize / (1024 * 1024)).toFixed(1)} MB)` : 'Tamaño desconocido';
                option.textContent = `${f.label} - ${size}`;
                formatSelect.appendChild(option);
            });

            if (!data.has_ffmpeg) {
                qualityWarning.classList.remove('hidden');
            }

            if (data.has_subtitles) {
                showTranscriptBtn.classList.remove('hidden');
            }

            videoInfoCard.classList.remove('hidden');
        } catch (error) {
            console.error('Error:', error);
            alert('Error al conectar con el servidor. ¿Está el backend encendido?');
        } finally {
            loadingSpinner.classList.add('hidden');
        }
    });

    downloadBtn.addEventListener('click', async () => {
        const url = videoUrlInput.value.trim();
        const formatId = formatSelect.value;

        downloadBtn.disabled = true;
        downloadProgress.classList.remove('hidden');
        progressFill.style.width = '20%';
        progressText.textContent = 'Procesando descarga en el servidor...';

        try {
            const response = await fetch(`${API_BASE}/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, format_id: formatId })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Error en la descarga');
            }

            // Simular progreso final
            progressFill.style.width = '80%';
            progressText.textContent = 'Preparando archivo para transferencia...';

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            
            // Intentar obtener el nombre del archivo del header o usar el título
            const filename = `${titleEl.textContent.substring(0, 30)}.mp4`;
            a.download = filename;
            
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();

            progressFill.style.width = '100%';
            progressText.textContent = '¡Descarga completada!';
            
            setTimeout(() => {
                downloadProgress.classList.add('hidden');
                downloadBtn.disabled = false;
            }, 3000);

        } catch (error) {
            console.error('Error:', error);
            alert(`Error: ${error.message}`);
        } finally {
            downloadProgress.classList.add('hidden');
            downloadBtn.disabled = false;
        }
    });

    downloadThumbBtn.addEventListener('click', () => {
        if (!currentMaxResThumbnail) return;
        
        const a = document.createElement('a');
        a.href = currentMaxResThumbnail;
        a.download = `miniatura_${titleEl.textContent.substring(0, 20)}.jpg`;
        a.target = '_blank'; // Por si el navegador bloquea la descarga directa de cross-origin
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    showTranscriptBtn.addEventListener('click', async () => {
        const url = videoUrlInput.value.trim();
        transcriptSection.classList.remove('hidden');
        transcriptContent.innerHTML = '<p>Analizando y extrayendo texto... por favor espera.</p>';
        showTranscriptBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE}/transcript`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (data.error) {
                const cleanError = data.error.replace(/\u001b\[[0-9;]*m/g, '');
                transcriptContent.innerHTML = `<p class="error-text">Error: ${cleanError}</p>`;
            } else {
                transcriptContent.innerHTML = `<p>${data.transcript}</p>`;
                downloadTxtBtn.classList.remove('hidden');
            }
        } catch (error) {
            transcriptContent.innerHTML = `<p class="error-text">Error al conectar con el servidor.</p>`;
        } finally {
            showTranscriptBtn.disabled = false;
        }
    });

    copyTranscriptBtn.addEventListener('click', () => {
        const text = transcriptContent.textContent;
        navigator.clipboard.writeText(text).then(() => {
            const originalText = copyTranscriptBtn.textContent;
            copyTranscriptBtn.textContent = '¡Copiado!';
            setTimeout(() => {
                copyTranscriptBtn.textContent = originalText;
            }, 2000);
        });
    });

    downloadTxtBtn.addEventListener('click', () => {
        const text = transcriptContent.textContent;
        const blob = new Blob([text], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `transcripcion_${titleEl.textContent.substring(0, 20)}.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    });
});
