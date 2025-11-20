const LOG_FILE_PATH = '/requests.log';


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

    } catch (error) {
        console.error("Error loading server logs:", error);
        logDisplayElement.innerHTML = `<span class="log-message">Error loading logs: ${error.message}</span>`;
    }
}

// Start the process when the entire document is loaded
document.addEventListener('DOMContentLoaded', fetchAndDisplayLogs);