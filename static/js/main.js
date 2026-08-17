document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('theme-toggle');
    const currentTheme = localStorage.getItem('theme') || 'light';

    if (currentTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        if (themeToggleBtn) themeToggleBtn.innerHTML = '☀️ Light Mode';
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
        if (themeToggleBtn) themeToggleBtn.innerHTML = '🌙 Dark Mode';
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            let theme = document.documentElement.getAttribute('data-theme');
            if (theme === 'dark') {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
                themeToggleBtn.innerHTML = '🌙 Dark Mode';
            } else {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
                themeToggleBtn.innerHTML = '☀️ Light Mode';
            }
        });
    }
});