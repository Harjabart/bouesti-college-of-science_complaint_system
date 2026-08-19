document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // 1. LIGHT / DARK THEME TOGGLE
    // ==========================================
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');
    const htmlTag = document.documentElement;

    // Retrieve saved theme preference (defaulting to 'light')
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = htmlTag.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            applyTheme(newTheme);
        });
    }

    function applyTheme(theme) {
        htmlTag.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);

        if (themeToggleBtn) {
            if (theme === 'dark') {
                if (themeIcon) themeIcon.className = 'fas fa-sun';
                if (themeText) themeText.textContent = 'Light Mode';
            } else {
                if (themeIcon) themeIcon.className = 'fas fa-moon';
                if (themeText) themeText.textContent = 'Dark Mode';
            }
        }
    }

    // ==========================================
    // 2. FLASH ALERT AUTO-DISMISSAL
    // ==========================================
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 500);
        }, 5000); // Automatically fades out after 5 seconds
    });

    // ==========================================
    // 3. FILE UPLOAD SIZE & TYPE VALIDATION
    // ==========================================
    const fileInput = document.getElementById('file');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                // 16MB file limit validation
                const maxSize = 16 * 1024 * 1024;
                if (file.size > maxSize) {
                    alert('File size exceeds the 16MB limit. Please choose a smaller file.');
                    fileInput.value = ''; // Reset file input
                }
            }
        });
    }
});