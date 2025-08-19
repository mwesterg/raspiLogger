// main.js

import { fetchConnectionStatus } from './connection_status.js';
import { fetchStats } from './stats.js';
import { logLevels, fetchLogsForLevel } from './log_feeds.js';
import './modals.js'; // Import modals to ensure event listeners are set up
import './sidebar_toggle.js'; // Import sidebar_toggle to ensure event listeners are set up
import './reset_reasons.js'; // Import reset_reasons to ensure event listeners are set up


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