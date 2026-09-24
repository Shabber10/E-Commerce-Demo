// Main Interactive Script for E-Commerce Platform

document.addEventListener('DOMContentLoaded', () => {
    // Password visibility toggle handler
    const toggleButtons = document.querySelectorAll('.password-toggle-btn');
    toggleButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const targetInputId = button.getAttribute('data-target');
            const targetInput = document.getElementById(targetInputId);
            if (!targetInput) return;

            if (targetInput.type === 'password') {
                targetInput.type = 'text';
                button.innerHTML = '👁️‍🗨️';
                button.setAttribute('aria-label', 'Hide password');
            } else {
                targetInput.type = 'password';
                button.innerHTML = '👁️';
                button.setAttribute('aria-label', 'Show password');
            }
        });
    });

    // Auto-dismiss flash alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        const closeBtn = alert.querySelector('.alert-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-10px)';
                setTimeout(() => alert.remove(), 250);
            });
        }

        setTimeout(() => {
            if (document.body.contains(alert)) {
                alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-10px)';
                setTimeout(() => alert.remove(), 400);
            }
        }, 5000);
    });
});
