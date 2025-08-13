// modals.js

import { logLevels } from './log_feeds.js';
import { fetchStats } from './stats.js';
import { fetchConnectionStatus } from './connection_status.js';

document.addEventListener('DOMContentLoaded', () => {
    // --- Reset Logic ---
    const resetDatabaseButton = document.getElementById('reset-database-button-in-modal');
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

    const flashDeviceButton = document.getElementById('flash-device-button');
    const flashModal = document.getElementById('flash-modal');
    const closeFlashModalBtn = document.getElementById('close-flash-modal-btn');
    const firmwareFileInput = document.getElementById('firmware-file-input');
    const startFlashBtn = document.getElementById('start-flash-btn');
    const flashOutput = document.getElementById('flash-output');


    resetDatabaseButton.addEventListener('click', () => {
        modal.classList.remove('hidden');
    });

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

    if (flashDeviceButton) {
        flashDeviceButton.addEventListener('click', () => {
            flashModal.classList.remove('hidden');
            flashOutput.innerHTML = ''; // Clear previous output
            firmwareFileInput.value = ''; // Clear selected file
        });
    }

    if (closeFlashModalBtn) {
        closeFlashModalBtn.addEventListener('click', () => {
            flashModal.classList.add('hidden');
        });
    }

    const viewAllLogsModal = document.getElementById('view-all-logs-modal');
    const closeViewAllLogsModalBtn = document.getElementById('close-view-all-logs-modal-btn');
    const viewAllLogsTitle = document.getElementById('view-all-logs-title');
    const viewAllLogsContent = document.getElementById('view-all-logs-content');

    if (startFlashBtn) {
        startFlashBtn.addEventListener('click', () => {
            const file = firmwareFileInput.files[0];
            if (!file) {
                flashOutput.innerHTML = '<p class="text-red-500">Please select a firmware file.</p>';
                return;
            }

            flashOutput.innerHTML = '<p class="text-yellow-500">Starting flash...</p>';
            const formData = new FormData();
            formData.append('firmware', file);

            fetch('/flash_device', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    flashOutput.innerHTML += `<p class="text-green-500">Flash successful!</p><pre>${data.output}</pre>`;
                } else {
                    flashOutput.innerHTML += `<p class="text-red-500">Flash failed: ${data.message}</p><pre>${data.output}</pre>`;
                }
            })
            .catch(error => {
                flashOutput.innerHTML += `<p class="text-red-500">Error during flash: ${error}</p>`;
                console.error('Error:', error);
            });
        });
    }

    document.querySelectorAll('.view-all-logs-btn').forEach(button => {
        button.addEventListener('click', (event) => {
            const logLevel = event.target.dataset.logLevel;
            viewAllLogsTitle.textContent = `All ${logLevel} Logs`;
            viewAllLogsContent.innerHTML = '<p class="text-gray-500">Loading...</p>';
            viewAllLogsModal.classList.remove('hidden');

            fetch(`/all_logs/${logLevel}`)
                .then(response => response.json())
                .then(logs => {
                    viewAllLogsContent.innerHTML = '';
                    if (logs.length > 0) {
                        logs.forEach(log => {
                            viewAllLogsContent.innerHTML += `<div>(${log.timestamp}) ${log.tag}: ${log.message}</div>`;
                        });
                    } else {
                        viewAllLogsContent.innerHTML = '<p class="text-gray-500">No logs found for this level.</p>';
                    }
                })
                .catch(error => {
                    console.error('Error fetching all logs:', error);
                    viewAllLogsContent.innerHTML = '<p class="text-red-500">Error loading logs.</p>';
                });
        });
    });

    if (closeViewAllLogsModalBtn) {
        closeViewAllLogsModalBtn.addEventListener('click', () => {
            viewAllLogsModal.classList.add('hidden');
        });
    }

    const viewAppLogsButton = document.getElementById('view-app-logs-button');
    const appLogsModal = document.getElementById('app-logs-modal');
    const closeAppLogsModalBtn = document.getElementById('close-app-logs-modal-btn');
    const appLogsContent = document.getElementById('app-logs-content');

    if (viewAppLogsButton) {
        viewAppLogsButton.addEventListener('click', () => {
            appLogsModal.classList.remove('hidden');
            appLogsContent.innerHTML = '<p class="text-gray-500">Loading application logs...</p>';
            fetch('/app_logs')
                .then(response => response.json())
                .then(data => {
                    if (data.logs) {
                        appLogsContent.textContent = data.logs;
                    } else {
                        appLogsContent.innerHTML = `<p class="text-red-500">${data.message || 'Error loading logs.'}</p>`;
                    }
                })
                .catch(error => {
                    console.error('Error fetching app logs:', error);
                    appLogsContent.innerHTML = '<p class="text-red-500">Error loading application logs.</p>';
                });
        });
    }

    if (closeAppLogsModalBtn) {
        closeAppLogsModalBtn.addEventListener('click', () => {
            appLogsModal.classList.add('hidden');
        });
    }
});