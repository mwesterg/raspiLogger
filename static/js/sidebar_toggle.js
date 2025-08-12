// sidebar_toggle.js

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