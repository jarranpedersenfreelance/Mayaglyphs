const LOG_FILE_PATH = '/requests.log';

function scrollToBottom() {
    const logContainer = document.getElementById('log-display');
    
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

async function fetchAndDisplayLogs() {
    const logDisplayElement = document.getElementById('log-display');

    try {
        const response = await fetch(LOG_FILE_PATH);

        if (!response.ok) {
            if (response.status === 404) {
                throw new Error(`Log file '${LOG_FILE_PATH}' not found on the server.`);
            }
            throw new Error(`Failed to fetch log file: HTTP status ${response.status}`);
        }

        const logContent = await response.text();

        if (logContent.trim() === '') {
            logDisplayElement.innerHTML = '<span class="log-message">The log file is currently empty.</span>';
        } else {
            logDisplayElement.textContent = logContent;
        }
        scrollToBottom();

    } catch (error) {
        console.error("Error loading server logs:", error);
        logDisplayElement.innerHTML = `<span class="log-message">Error loading logs: ${error.message}</span>`;
    }
}

async function fetchLogStats() {
    try {
        const response = await fetch('/api/logs/stats');
        if (response.ok) {
            const data = await response.json();
            const size = data.size;
            // Format bytes to KB or MB
            let formattedSize = size + " B";
            if (size > 1024 * 1024) formattedSize = (size / (1024 * 1024)).toFixed(2) + " MB";
            else if (size > 1024) formattedSize = (size / 1024).toFixed(2) + " KB";
            
            document.getElementById('log-size-display').textContent = `Current Size: ${formattedSize}`;
        }
    } catch (error) {
        console.error("Error fetching stats", error);
    }
}

async function performSearch() {
    const term = document.getElementById('search-input').value;
    if (!term) return; // Don't search empty

    const logDisplayElement = document.getElementById('log-display');
    logDisplayElement.innerHTML = '<span class="log-message">Searching...</span>';

    try {
        const response = await fetch(`/api/logs/search?q=${encodeURIComponent(term)}`);
        const data = await response.json();
        
        if (data.results && data.results.length > 0) {
            logDisplayElement.textContent = data.results.join('\n');
        } else {
            logDisplayElement.innerHTML = '<span class="log-message">No matches found.</span>';
        }
        
    } catch (error) {
        logDisplayElement.innerHTML = `<span class="log-message">Search failed: ${error.message}</span>`;
    }
}

function archiveLogs() {
    if(!confirm("This will download the current log file and then clear it from the server. Continue?")) return;
    window.location.href = '/api/logs/archive';
    
    // Reload the view after a short delay to show empty logs
    setTimeout(() => {
        resetView();
        fetchLogStats();
    }, 2000);
}

function resetView() {
    document.getElementById('search-input').value = '';
    fetchAndDisplayLogs();
    fetchLogStats();
}

document.addEventListener('DOMContentLoaded', () => {
    fetchAndDisplayLogs();
    fetchLogStats();
});