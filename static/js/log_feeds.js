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
                logHTML += `<div class="log-entry whitespace-nowrap overflow-hidden text-ellipsis">(${log.timestamp}) ${log.tag}: ${log.message}</div>`;
            });
            feed.innerHTML = logHTML;
        });
}

export { logLevels, fetchLogsForLevel };