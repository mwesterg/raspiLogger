const logLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

            function fetchConnectionStatus() {
                fetch('/connection_status')
                    .then(response => response.json())
                    .then(data => {
                        const indicator = document.getElementById('connection-indicator');
                        const text = document.getElementById('connection-text');
                        const deviceInfo = document.getElementById('device-info');
                        if (data.connected) {
                            indicator.classList.remove('bg-red-500');
                            indicator.classList.add('bg-green-500');
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
                            indicator.classList.remove('bg-green-500');
                            indicator.classList.add('bg-red-500');
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
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-gray-500">Total Msgs</p><p class="text-2xl font-bold">${data.total_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-blue-500">Debug</p><p class="text-2xl font-bold">${data.debug_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-green-500">Info</p><p class="text-2xl font-bold">${data.info_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-yellow-500">Warning</p><p class="text-2xl font-bold">${data.warning_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-red-500">Error</p><p class="text-2xl font-bold">${data.error_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-gray-500">Other</p><p class="text-2xl font-bold">${data.other_messages || 0}</p></div>
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
            console.log('resetDatabaseButton:', resetDatabaseButton);
            const modal = document.getElementById('reset-modal');
            console.log('modal:', modal);
            const confirmBtn = document.getElementById('confirm-reset-btn');
            console.log('confirmBtn:', confirmBtn);
            const cancelBtn = document.getElementById('cancel-reset-btn');
            console.log('cancelBtn:', cancelBtn);

            const showBootLogsButton = document.getElementById('show-boot-logs-button');
            console.log('showBootLogsButton:', showBootLogsButton);
            const bootLogsModal = document.getElementById('boot-logs-modal');
            console.log('bootLogsModal:', bootLogsModal);
            const closeBootLogsBtn = document.getElementById('close-boot-logs-btn');
            console.log('closeBootLogsBtn:', closeBootLogsBtn);
            const bootLogsContent = document.getElementById('boot-logs-content');
            console.log('bootLogsContent:', bootLogsContent);
            const bootLogDate = document.getElementById('boot-log-date');
            console.log('bootLogDate:', bootLogDate);

            const restartDeviceButton = document.getElementById('restart-device-button');
            console.log('restartDeviceButton:', restartDeviceButton);

            const filterLogsButton = document.getElementById('filter-logs-button');
            console.log('filterLogsButton:', filterLogsButton);
            const filterLogsModal = document.getElementById('filter-logs-modal');
            console.log('filterLogsModal:', filterLogsModal);
            const closeFilterLogsBtn = document.getElementById('close-filter-logs-btn');
            console.log('closeFilterLogsBtn:', closeFilterLogsBtn);
            const tagDropdown = document.getElementById('tag-dropdown');
            console.log('tagDropdown:', tagDropdown);
            const filteredLogsContent = document.getElementById('filtered-logs-content');
            console.log('filteredLogsContent:', filteredLogsContent);

            if (resetDatabaseButton) {
                resetDatabaseButton.addEventListener('click', () => {
                    console.log('Reset Database button clicked');
                    modal.classList.remove('hidden');
                });
            } else {
                console.error('resetDatabaseButton not found!');
            }

            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    console.log('Cancel button clicked');
                    modal.classList.add('hidden');
                });
            } else {
                console.error('cancelBtn not found!');
            }

            if (confirmBtn) {
                confirmBtn.addEventListener('click', () => {
                    console.log('Confirm Reset button clicked');
                    fetch('/reset', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        modal.classList.add('hidden');
                        if(data.success) {
                            console.log('Reset successful');
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
                    console.log('Show Boot Logs button clicked');
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
            } else {
                console.error('showBootLogsButton not found!');
            }

            if (closeBootLogsBtn) {
                closeBootLogsBtn.addEventListener('click', () => {
                    console.log('Close Boot Logs button clicked');
                    bootLogsModal.classList.add('hidden');
                });
            } else {
                console.error('closeBootLogsBtn not found!');
            }

            if (restartDeviceButton) {
                restartDeviceButton.addEventListener('click', () => {
                    console.log('Restart Device button clicked');
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
            } else {
                console.error('restartDeviceButton not found!');
            }

            if (filterLogsButton) {
                filterLogsButton.addEventListener('click', () => {
                    console.log('Filter Logs button clicked');
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
            } else {
                console.error('filterLogsButton not found!');
            }

            if (closeFilterLogsBtn) {
                closeFilterLogsBtn.addEventListener('click', () => {
                    console.log('Close Filter Logs button clicked');
                    filterLogsModal.classList.add('hidden');
                    filteredLogsContent.innerHTML = ''; // Clear content when closing
                    tagDropdown.value = ''; // Reset dropdown
                });
            }

            if (tagDropdown) {
                tagDropdown.addEventListener('change', (event) => {
                    const selectedTag = event.target.value;
                    if (selectedTag) {
                        console.log(`Tag selected: ${selectedTag}`);
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
            } else {
                console.error('tagDropdown not found!');
            }