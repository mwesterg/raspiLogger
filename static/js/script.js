const logLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

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
                            } else {
                            indicator.classList.remove('bg-green-600');
                            indicator.classList.add('bg-red-600');
                            text.textContent = 'Disconnected';
                            deviceInfo.innerHTML = '';
                        }
                    });
            }

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

            // Fetch initial data on page load
            fetchConnectionStatus();
            fetchStats();
            logLevels.forEach(level => fetchLogsForLevel(level));
            
            // Set intervals to fetch data periodically
            setInterval(fetchConnectionStatus, 5000);
            setInterval(fetchStats, 5000);
            logLevels.forEach(level => {
                setInterval(() => fetchLogsForLevel(level), 3000);
            });

            // --- Reset Logic ---
            const resetDatabaseButton = document.getElementById('reset-database-button');
            const modal = document.getElementById('reset-modal');
            const confirmBtn = document.getElementById('confirm-reset-btn');
            const cancelBtn = document.getElementById('cancel-reset-btn');

            const showBootLogsButton = document.getElementById('show-boot-logs-button');
            const bootLogsModal = document.getElementById('boot-logs-modal');
            const closeBootLogsBtn = document.getElementById('close-boot-logs-btn');
            const bootLogsContent = document.getElementById('boot-logs-content');
            const bootLogDate = document.getElementById('boot-log-date');

            const restartDeviceButton = document.getElementById('restart-device-button');

            const filterLogsButton = document.getElementById('filter-logs-button');
            const filterLogsModal = document.getElementById('filter-logs-modal');
            const closeFilterLogsBtn = document.getElementById('close-filter-logs-btn');
            const tagDropdown = document.getElementById('tag-dropdown');
            const filteredLogsContent = document.getElementById('filtered-logs-content');

            const configButton = document.getElementById('config-button');
            const configModal = document.getElementById('config-modal');
            const closeConfigModalBtn = document.getElementById('close-config-modal-btn');

            if (resetDatabaseButton) {
                resetDatabaseButton.addEventListener('click', () => {
                    modal.classList.remove('hidden');
                });
            }

            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    modal.classList.add('hidden');
                });
            }

            if (confirmBtn) {
                confirmBtn.addEventListener('click', () => {
                    fetch('/reset', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        modal.classList.add('hidden');
                        if(data.success) {
                            fetchStats(); // Immediately update the stats on the page
                            logLevels.forEach(level => {
                                 const feed = document.getElementById(`${level.toLowerCase()}-log-feed`);
                                 feed.innerHTML = `<p class="text-gray-500">No ${level.toLowerCase()} logs.</p>`;
                            });
                        } else {
                            console.error('An error occurred during reset: ' + data.message);
                        }
                    })
                    .catch(error => {
                        modal.classList.add('hidden');
                        console.error('Error:', error);
                    });
                });
            }

            if (showBootLogsButton) {
                showBootLogsButton.addEventListener('click', () => {
                    fetch('/boot_logs')
                        .then(response => response.json())
                        .then(data => {
                            bootLogsContent.innerHTML = '';
                            if (data.boot_logs && data.boot_logs.length > 0) {
                                data.boot_logs.forEach(log => {
                                    bootLogsContent.innerHTML += `<div>${log}</div>`;
                                });
                            } else {
                                bootLogsContent.innerHTML = '<p class="text-gray-500">No boot logs available.</p>';
                            }
                            if (data.boot_timestamp) {
                                bootLogDate.textContent = `Boot Time: ${data.boot_timestamp}`;
                            } else {
                                bootLogDate.textContent = '';
                            }
                            bootLogsModal.classList.remove('hidden');
                        })
                        .catch(error => {
                            console.error('Error fetching boot logs:', error);
                            bootLogsContent.innerHTML = '<p class="text-red-500">Error loading boot logs.</p>';
                            bootLogsModal.classList.remove('hidden');
                        });
                });
            }

            if (closeBootLogsBtn) {
                closeBootLogsBtn.addEventListener('click', () => {
                    bootLogsModal.classList.add('hidden');
                });
            }

            if (restartDeviceButton) {
                restartDeviceButton.addEventListener('click', () => {
                    fetch('/restart_device', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if(data.success) {
                            console.log('Device restart initiated.');
                        } else {
                            console.error('Error initiating device restart: ' + data.message);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                    });
                });
            }

            if (filterLogsButton) {
                filterLogsButton.addEventListener('click', () => {
                    filterLogsModal.classList.remove('hidden');
                    fetch('/tags')
                        .then(response => response.json())
                        .then(tags => {
                            tagDropdown.innerHTML = '<option value="">Select a Tag</option>';
                            tags.forEach(tag => {
                                tagDropdown.innerHTML += `<option value="${tag}">${tag}</option>`;
                            });
                        })
                        .catch(error => {
                            console.error('Error fetching tags:', error);
                        });
                });
            }

            if (closeFilterLogsBtn) {
                closeFilterLogsBtn.addEventListener('click', () => {
                    filterLogsModal.classList.add('hidden');
                    filteredLogsContent.innerHTML = ''; // Clear content when closing
                    tagDropdown.value = ''; // Reset dropdown
                });
            }

            if (tagDropdown) {
                tagDropdown.addEventListener('change', (event) => {
                    const selectedTag = event.target.value;
                    if (selectedTag) {
                        fetch(`/filtered_logs/${selectedTag}`)
                            .then(response => response.json())
                            .then(logs => {
                                filteredLogsContent.innerHTML = '';
                                if (logs.length > 0) {
                                    logs.forEach(log => {
                                        filteredLogsContent.innerHTML += `<div>(${log.timestamp}) ${log.tag}: ${log.message}</div>`;
                                    });
                                } else {
                                    filteredLogsContent.innerHTML = '<p class="text-gray-500">No logs found for this tag.</p>';
                                }
                            })
                            .catch(error => {
                                console.error('Error fetching filtered logs:', error);
                                filteredLogsContent.innerHTML = '<p class="text-red-500">Error loading filtered logs.</p>';
                            });
                    } else {
                        filteredLogsContent.innerHTML = ''; // Clear if no tag selected
                    }
                });
            }

            if (configButton) {
                configButton.addEventListener('click', () => {
                    configModal.classList.remove('hidden');
                });
            }

            if (closeConfigModalBtn) {
                closeConfigModalBtn.addEventListener('click', () => {
                    configModal.classList.add('hidden');
                });
            }

// Sidebar Toggle Logic
document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const sidebarToggle = document.getElementById('sidebar-toggle');

    if (sidebar && mainContent && sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('sidebar-hidden');
            mainContent.classList.toggle('main-content-full');
        });
    }
});