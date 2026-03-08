// Professional UI Controller
const fetchBtn = document.getElementById('fetchBtn');
const videoUrlInput = document.getElementById('videoUrl');
const mainLoader = document.getElementById('mainLoader');
const resultsArea = document.getElementById('resultsArea');
const errorArea = document.getElementById('errorArea');

const API_BASE = "";
const WS_BASE = `ws://${window.location.host}`;
const CLIENT_ID = Math.random().toString(36).substring(7);

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `pro-toast ${type}`;

    const icon = type === 'success' ? 'check-circle' : 'alert-circle';
    const iconColor = type === 'success' ? '#10b981' : '#ef4444';

    toast.innerHTML = `
        <i data-lucide="${icon}" style="color: ${iconColor}; width: 18px;"></i>
        <span style="font-weight: 500; font-size: 0.95rem;">${message}</span>
    `;

    container.appendChild(toast);
    lucide.createIcons();

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function setupProgressSocket() {
    const socket = new WebSocket(`${WS_BASE}/ws/progress/${CLIENT_ID}`);
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const card = document.querySelector(`[data-format-id="${data.format_id}"]`);
        if (!card) return;

        const btn = card.querySelector('.btn-download');
        const progressContainer = card.querySelector('.download-progress-container');
        const progressFill = card.querySelector('.download-progress-fill');

        if (data.status === 'downloading') {
            btn.classList.add('downloading');
            btn.disabled = true;
            const progress = Math.round(data.progress || 0);

            // Using the badge-style percentage display
            btn.innerHTML = `
                <span class="dl-status-text">Downloading...</span>
                <span class="dl-percent-badge">${progress}%</span>
            `;

            if (progressContainer) {
                progressContainer.style.display = 'block';
                progressFill.style.width = `${progress}%`;
            }
        } else if (data.status === 'merging') {
            btn.innerHTML = `<span class="loader" style="display:inline-block; width:14px; height:14px; border-width: 2px;"></span> Finishing...`;
            if (progressFill) progressFill.style.width = '100%';
        } else if (data.status === 'ready') {
            btn.innerHTML = `<span>Finalizing...</span>`;
            if (progressFill) progressFill.style.width = '100%';
        }
    };
    socket.onclose = () => setTimeout(setupProgressSocket, 3000);
}

setupProgressSocket();

fetchBtn.addEventListener('click', async () => {
    const url = videoUrlInput.value.trim();
    if (!url || fetchBtn.disabled) return;

    // Reset UI
    fetchBtn.disabled = true;
    mainLoader.style.display = 'block';
    const btnLabel = fetchBtn.querySelector('.btn-label');
    btnLabel.style.display = 'none';
    errorArea.style.display = 'none';
    resultsArea.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/api/info`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Service unavailable');

        renderResults(data, url);
        resultsArea.style.display = 'flex';
        showToast("Links generated successfully!");
    } catch (err) {
        errorArea.textContent = err.message;
        errorArea.style.display = 'block';
        showToast(err.message, "error");
    } finally {
        fetchBtn.disabled = false;
        mainLoader.style.display = 'none';
        btnLabel.style.display = 'inline';
    }
});

function renderResults(data, originalUrl) {
    resultsArea.innerHTML = `
        <div class="result-card" style="display: flex; gap: 3rem; align-items: flex-start; flex-wrap: wrap;">
            <img src="${data.thumbnail}" style="width: 320px; border-radius: 12px; border: 1px solid var(--border-dim); background: #f1f5f9;">
            <div style="flex: 1; min-width: 300px;">
                <h2 style="font-size: 2rem; line-height: 1.2; margin-bottom: 1rem;">${data.title}</h2>
                <p style="color: var(--text-secondary); font-size: 1.1rem;">Source: ${data.uploader} • Length: ${formatDuration(data.duration)}</p>
            </div>
        </div>

        <div class="result-card">
            <h3 class="section-head">Video Quality Options</h3>
            <div class="format-grid">
                ${data.video_formats.map(f => `
                    <div class="format-item" data-format-id="${f.id}">
                        <div class="format-label">${f.quality}</div>
                        <div class="format-info">MP4 • ${formatBytes(f.filesize) || 'N/A'}</div>
                        <button class="btn-download" onclick="performDownload('${originalUrl}', '${f.id}', 'mp4', this)">
                            Download Video
                        </button>
                        <div class="download-progress-container">
                            <div class="download-progress-fill"></div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="result-card">
            <h3 class="section-head">Audio Extraction</h3>
            <div class="format-grid" style="grid-template-columns: 1fr;">
                ${data.audio_formats.map(f => `
                    <div class="format-item audio-item" data-format-id="${f.id}">
                        <div class="audio-main">
                            <div class="audio-meta">
                                <div class="format-label">High Quality MP3</div>
                                <div class="format-info">192kbps • ${formatBytes(f.filesize) || 'N/A'}</div>
                            </div>
                            <div class="audio-actions">
                                <button class="btn-download" onclick="performDownload('${originalUrl}', '${f.id}', 'mp3', this)">
                                    <i data-lucide="music" style="width: 16px;"></i> Download MP3
                                </button>
                                <div class="download-progress-container">
                                    <div class="download-progress-fill"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    lucide.createIcons();
}

function finishButtonStyle(btn, progressContainer) {
    btn.innerHTML = `<i data-lucide="check" style="width: 18px;"></i> Downloaded`;
    btn.classList.remove('downloading');
    btn.classList.add('completed');
    btn.disabled = false;
    lucide.createIcons();
    if (progressContainer) {
        setTimeout(() => {
            progressContainer.style.display = 'none';
        }, 3000);
    }
}

async function performDownload(url, formatId, ext, btn) {
    if (btn.disabled) return;

    btn.disabled = true;
    const item = btn.closest('.format-item');
    const progressContainer = item ? item.querySelector('.download-progress-container') : null;
    const progressFill = item ? item.querySelector('.download-progress-fill') : null;

    btn.innerHTML = `<span>Saving...</span>`;
    showToast(`Requesting ${ext.toUpperCase()}...`);

    try {
        const timestamp = Math.floor(Date.now() / 1000);
        const decorativeName = `VideoQuest_${timestamp}.${ext}`;
        const downloadUrl = `${API_BASE}/api/download/${decorativeName}?url=${encodeURIComponent(url)}&format_id=${formatId}&ext=${ext}&client_id=${CLIENT_ID}`;

        const response = await fetch(downloadUrl);
        if (!response.ok) throw new Error("Server error during download");

        const contentLength = response.headers.get('content-length');
        const total = parseInt(contentLength, 10);
        let loaded = 0;

        const reader = response.body.getReader();
        const chunks = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            chunks.push(value);
            loaded += value.length;

            if (total) {
                const percent = Math.round((loaded / total) * 100);
                btn.innerHTML = `<span>Saving...</span> <span class="dl-percent-badge">${percent}%</span>`;
                if (progressFill) progressFill.style.width = `${percent}%`;
            } else {
                btn.innerHTML = `<span>Saving...</span> <span class="dl-percent-badge">${(loaded / 1024 / 1024).toFixed(1)}MB</span>`;
                if (progressFill) progressFill.style.width = '100%';
            }
        }

        const blob = new Blob(chunks);
        const blobUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = decorativeName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);

        finishButtonStyle(btn, progressContainer);
        showToast("Download complete!");

    } catch (err) {
        console.error(err);
        showToast("Connection or memory error", "error");
        btn.disabled = false;
        btn.innerHTML = "Retry Download";
    }
}

function formatDuration(seconds) {
    if (!seconds) return "Unknown";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hrs > 0 ? hrs + ':' : ''}${mins.toString().padStart(hrs > 0 ? 2 : 1, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatBytes(bytes) {
    if (!bytes) return null;
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(2) * 1 + ' ' + ['B', 'KB', 'MB', 'GB'][i];
}
