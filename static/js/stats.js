// stats.js

function fetchStats() {
    fetch('/stats')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('stats-container');
            container.innerHTML = `
                <div class="bg-gray-800 p-4 rounded-lg shadow-md text-center"><p class="text-sm text-gray-400">Total Msgs</p><p class="text-2xl font-bold">${data.total_messages || 0}</p></div>
                <div class="bg-gray-800 p-4 rounded-lg shadow-md text-center"><p class="text-sm text-blue-400">Debug</p><p class="text-2xl font-bold">${data.debug_messages || 0}</p></div>
                <div class="bg-gray-800 p-4 rounded-lg shadow-md text-center"><p class="text-sm text-green-400">Info</p><p class="text-2xl font-bold">${data.info_messages || 0}</p></div>
                <div class="bg-gray-800 p-4 rounded-lg shadow-md text-center"><p class="text-sm text-yellow-400">Warning</p><p class="text-2xl font-bold">${data.warning_messages || 0}</p></div>
                <div class="bg-gray-800 p-4 rounded-lg shadow-md text-center"><p class="text-sm text-red-400">Error</p><p class="text-2xl font-bold">${data.error_messages || 0}</p></div>
                <div class="bg-gray-800 p-4 rounded-lg shadow-md text-center"><p class="text-sm text-gray-400">Other</p><p class="text-2xl font-bold">${data.other_messages || 0}</p></div>
            `;
        });
}

export { fetchStats };