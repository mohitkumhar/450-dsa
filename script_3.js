
    // Theme Toggle
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const root = document.documentElement;

    function applyTheme(theme) {
        if (theme === 'light') {
            root.style.setProperty('--bg-primary', '#f0f2f5');
            root.style.setProperty('--bg-secondary', '#ffffff');
            root.style.setProperty('--bg-card', '#ffffff');
            root.style.setProperty('--bg-card-hover', '#f5f5f5');
            root.style.setProperty('--border-color', '#e0e0e0');
            root.style.setProperty('--border-subtle', '#ececec');
            root.style.setProperty('--text-primary', '#111111');
            root.style.setProperty('--text-secondary', '#555555');
            root.style.setProperty('--text-muted', '#999999');
            themeIcon.className = 'bi bi-sun-fill';
        } else {
            root.style.setProperty('--bg-primary', '#111111');
            root.style.setProperty('--bg-secondary', '#1a1a1a');
            root.style.setProperty('--bg-card', '#1e1e1e');
            root.style.setProperty('--bg-card-hover', '#252525');
            root.style.setProperty('--border-color', '#2a2a2a');
            root.style.setProperty('--border-subtle', '#222222');
            root.style.setProperty('--text-primary', '#f0f0f0');
            root.style.setProperty('--text-secondary', '#a0a0a0');
            root.style.setProperty('--text-muted', '#666666');
            themeIcon.className = 'bi bi-moon-fill';
        }
    }

    const saved = localStorage.getItem('theme') || 'dark';
    applyTheme(saved);

    themeToggle.addEventListener('click', () => {
        const curr = localStorage.getItem('theme') || 'dark';
        const next = curr === 'dark' ? 'light' : 'dark';
        localStorage.setItem('theme', next);
        applyTheme(next);
    });

    // Auto-dismiss flash messages
    setTimeout(() => {
        const fc = document.getElementById('flash-container');
        if (fc) fc.style.opacity = '0', fc.style.transition = '0.5s', setTimeout(() => fc.remove(), 500);
    }, 4000);
