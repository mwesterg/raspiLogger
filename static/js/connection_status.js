// connection_status.js

function fetchConnectionStatus() {
    fetch('/connection_status')
        .then(response => response.json())
        .then(data => {
            const indicator = document.getElementById('connection-indicator');
            const text = document.getElementById('connection-text');
            const deviceInfo = document.getElementById('device-info');
            if (data.connected) {
                indicator.classList.remove('bg-red-600');
                indicator.classList.add('bg-green-600');
                text.textContent = `Connected at ${data.port}`;
                let deviceInfoHTML = '';
                if(data.device_info) {
                    deviceInfoHTML += `<div class="flex flex-wrap gap-x-6 gap-y-1">`; // Flex container for key-value pairs
                    if (data.device_info.chip_type) {
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">Chip:</span> ${data.device_info.chip_type}</span>`;
                    }
                    if (data.device_info.features) {
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">Features:</span> ${data.device_info.features}</span>`;
                    }
                    if (data.device_info.mac_address) {
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">MAC:</span> ${data.device_info.mac_address}</span>`;
                    }
                    if (data.device_info.app_version) {
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">App Ver:</span> ${data.device_info.app_version}</span>`;
                    }
                    if (data.device_info.project_name) {
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">Project:</span> ${data.device_info.project_name}</span>`;
                    }
                    if (data.device_info.reset_reason && data.device_info.reset_reason.length > 0) {
                        const lastReset = data.device_info.reset_reason[data.device_info.reset_reason.length - 1];
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">Last Reset:</span> ${lastReset.reason} (${lastReset.timestamp})</span>`;
                    }
                    if (data.device_info.compile_time) {
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">Compile:</span> ${data.device_info.compile_time}</span>`;
                    }
                    if (data.device_info.esp_idf_version) {
                        deviceInfoHTML += `<span><span class="font-semibold text-gray-400">IDF Ver:</span> ${data.device_info.esp_idf_version}</span>`;
                    }
                    deviceInfoHTML += `</div>`;
                }
                deviceInfo.innerHTML = deviceInfoHTML;
            } else {
                indicator.classList.remove('bg-green-600');
                indicator.classList.add('bg-red-600');
                text.textContent = 'Disconnected';
                deviceInfo.innerHTML = '';
            }
        });
}

export { fetchConnectionStatus };