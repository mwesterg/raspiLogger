// static/js/reset_reasons.js

document.addEventListener('DOMContentLoaded', () => {
    const showResetReasonsButton = document.getElementById('show-reset-reasons-button');
    const resetReasonsModal = document.getElementById('reset-reasons-modal');
    const resetReasonsContent = document.getElementById('reset-reasons-content');
    const closeResetReasonsBtn = document.getElementById('close-reset-reasons-btn');

    if (showResetReasonsButton) {
        showResetReasonsButton.addEventListener('click', async () => {
            resetReasonsModal.classList.remove('hidden');
            resetReasonsContent.innerHTML = '<p class="text-gray-400">Loading reset reasons...</p>';
            try {
                const response = await fetch('/reset_reasons');
                const data = await response.json();

                if (data && data.length > 0) {
                    resetReasonsContent.innerHTML = data.map(item => 
                        `<p><span class="text-gray-400">${item.timestamp}:</span> ${item.reason}</p>`
                    ).join('');
                } else {
                    resetReasonsContent.innerHTML = '<p class="text-gray-400">No reset reasons found.</p>';
                }
            } catch (error) {
                console.error('Error fetching reset reasons:', error);
                resetReasonsContent.innerHTML = '<p class="text-red-400">Failed to load reset reasons.</p>';
            }
        });
    }

    if (closeResetReasonsBtn) {
        closeResetReasonsBtn.addEventListener('click', () => {
            resetReasonsModal.classList.add('hidden');
        });
    }

    // Close modal when clicking outside
    if (resetReasonsModal) {
        resetReasonsModal.addEventListener('click', (e) => {
            if (e.target === resetReasonsModal) {
                resetReasonsModal.classList.add('hidden');
            }
        });
    }
});
