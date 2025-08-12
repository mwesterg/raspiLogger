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
                    deviceInfoHTML += `<div class="grid grid-cols-2 gap-x-4">`;
                    if (data.device_info.chip_type) {
                        deviceInfoHTML += `<div><span class="font-semibold">Chip Type:</span> ${data.device_info.chip_type}</div>`;
                    }
                    if (data.device_info.features) {
                        deviceInfoHTML += `<div><span class="font-semibold">Features:</span> ${data.device_info.features}</div>`;
                    }
                    if (data.device_info.mac_address) {
                        deviceInfoHTML += `<div><span class="font-semibold">MAC Address:</span> ${data.device_info.mac_address}</div>`;
                    }
                    if (data.device_info.app_version) {
                        deviceInfoHTML += `<div><span class="font-semibold">App Version:</span> ${data.device_info.app_version}</div>`;
                    }
                    if (data.device_info.project_name) {
                        deviceInfoHTML += `<div><span class="font-semibold">Project Name:</span> ${data.device_info.project_name}</div>`;
                    }
                    if (data.device_info.reset_reason) {
                        deviceInfoHTML += `<div><span class="font-semibold">Reset Reason:</span> ${data.device_info.reset_reason}</div>`;
                    }
                    if (data.device_info.compile_time) {
                        deviceInfoHTML += `<div><span class="font-semibold">Compile Time:</span> ${data.device_info.compile_time}</div>`;
                    }
                    if (data.device_info.esp_idf_version) {
                        deviceInfoHTML += `<div><span class="font-semibold">ESP-IDF Version:</span> ${data.device_info.esp_idf_version}</div>`;
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