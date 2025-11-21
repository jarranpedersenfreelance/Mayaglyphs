let currentLogType = 'requests'; 

function scrollToBottom() {
    const logContainer = document.getElementById('log-display');
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    if (i === 0) return `${bytes} ${sizes[i]}`;
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
}

/**
 * Switches the active log tab and triggers a view reset.
 * @param {string} type - 'requests' or 'error'
 */
function switchTab(type) {
    currentLogType = type;

    // Update UI Classes for active tab
    document.getElementById('tab-requests').classList.toggle('active', type === 'requests');
    document.getElementById('tab-errors').classList.toggle('active', type === 'error');

    // Update Title in the controls wrapper
    const titleText = type === 'requests' 
        ? "Log Management (Requests) (1000 Search Return Max)" 
        : "Log Management (Errors) (1000 Search Return Max)";
    document.querySelector('.controls-wrapper h2').textContent = titleText;

    // Reset search input and reload logs for the new tab
    resetView();
}

/**
 * Fetches and displays the contents of the currently selected log file.
 */
async function fetchAndDisplayLogs() {
    const logDisplayElement = document.getElementById('log-display');

    // Determine file path based on current state
    const filePath = currentLogType === 'error' 
        ? '/api/logs/errors.log' 
        : '/api/logs/requests.log';

    try {
        const response = await fetch(filePath);

        if (!response.ok) {
            // Check for 404 specifically, which often means the file hasn't been created yet
            if (response.status === 404) {
                logDisplayElement.innerHTML = '<span class="log-message">No log file found (File empty).</span>';
                return;
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

/**
 * Fetches and displays the size of the currently selected log file.
 */
async function fetchLogStats() {
    try {
        const response = await fetch(`/api/logs/stats?type=${currentLogType}`);
        if (response.ok) {
            const data = await response.json();
            const size = data.size;
            const maxSize = data.max_size;
            
            // Format both sizes
            const formattedSize = formatBytes(size);
            const formattedMaxSize = formatBytes(maxSize);
            
            const displayElement = document.getElementById('log-size-display');
            displayElement.textContent = `Size: ${formattedSize} / ${formattedMaxSize}`;
            
            // Toggle Color: Red if full, Yellow otherwise
            if (size >= maxSize) {
                displayElement.classList.remove('status-warning');
                displayElement.classList.add('status-error');
            } else {
                displayElement.classList.remove('status-error');
                displayElement.classList.add('status-warning');
            }
        }
    } catch (error) {
        console.error("Error fetching stats", error);
    }
}

/**
 * Performs a search on the currently selected log file using the term in the input box.
 */
async function performSearch() {
    const term = document.getElementById('search-input').value;
    const logDisplayElement = document.getElementById('log-display');
    const countDisplay = document.getElementById('search-count-display');

    if (!term) {
        countDisplay.textContent = '';
        fetchAndDisplayLogs(); // If search box is empty, show full logs
        return; 
    }

    logDisplayElement.innerHTML = '<span class="log-message">Searching...</span>';
    countDisplay.textContent = 'Searching...';

    try {
        // Append search term AND currentLogType to the query
        const response = await fetch(`/api/logs/search?q=${encodeURIComponent(term)}&type=${currentLogType}`);
        const data = await response.json();

        const resultCount = data.count || 0;
        countDisplay.textContent = `${resultCount} Match${resultCount !== 1 ? 'es' : ''}`;
        
        if (data.results && resultCount > 0) {
            logDisplayElement.textContent = data.results.join('\n'); // Join results with newline
        } else {
            logDisplayElement.innerHTML = '<span class="log-message">No matches found.</span>';
        }
        
    } catch (error) {
        logDisplayElement.innerHTML = `<span class="log-message">Search failed: ${error.message}</span>`;
    }
}

/**
 * Triggers the log archiving/clearing process for the current log file.
 */
function archiveLogs() {
    const typeLabel = currentLogType === 'requests' ? 'Request' : 'Error';
    if(!confirm(`This will download the current ${typeLabel} log file and then clear it from the server. Continue?`)) return;
    
    // Redirect with type param to trigger archive/download on the server
    window.location.href = `/api/logs/archive?type=${currentLogType}`;
    
    // Reload the view after a short delay to show empty logs and updated stats
    setTimeout(() => {
        resetView();
    }, 2000);
}

/**
 * Clears the search input and reloads the current log view and stats.
 */
function resetView() {
    document.getElementById('search-input').value = '';
    document.getElementById('search-count-display').textContent = '';
    fetchAndDisplayLogs();
    fetchLogStats();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Ensure the initial H2 title is set correctly when the page loads
    document.querySelector('.controls-wrapper h2').textContent = "Log Management (Requests) (1000 Search Return Max)";
    fetchAndDisplayLogs();
    fetchLogStats();
});