// log_feeds.js

const logLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

function fetchLogsForLevel(level) {
    fetch(`/latest_logs/${level}`)
        .then(response => response.json())
        .then(logs => {
            const feed = document.getElementById(`${level.toLowerCase()}-log-feed`);
            if (logs.length === 0) {
                feed.innerHTML = `<p class="text-gray-500">No ${level.toLowerCase()} logs.</p>`;
                return;
            }
            
            let logHTML = '';
            logs.forEach(log => {
                // Store the full message in a data attribute for easy retrieval
                logHTML += `
                    <div class="log-entry flex justify-between items-center py-1 border-b border-gray-700 last:border-b-0">
                        <div class="whitespace-nowrap overflow-hidden text-ellipsis flex-1 pr-2">
                            (${log.timestamp}) ${log.tag}: ${log.message}
                        </div>
                        <button class="view-log-btn bg-blue-600 hover:bg-blue-700 text-white text-xs px-2 py-1 rounded"
                                data-full-message="${log.message}">View</button>
                    </div>
                `;
            });
            feed.innerHTML = logHTML;

            // Add event listeners to the new "View" buttons
            feed.querySelectorAll('.view-log-btn').forEach(button => {
                button.addEventListener('click', (event) => {
                    const fullMessage = event.target.dataset.fullMessage;
                    const logDetailModal = document.getElementById('log-detail-modal');
                    const logDetailContent = document.getElementById('log-detail-content');
                    
                    logDetailContent.textContent = fullMessage; // Use textContent to prevent XSS
                    logDetailModal.classList.remove('hidden');
                });
            });
        });
}

export { logLevels, fetchLogsForLevel };