(function () {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) {
    return;
  }

  let deferredPrompt = null;
  let installButton = null;

  function ensureInstallButton() {
    if (installButton) {
      return installButton;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.hidden = true;
    button.setAttribute("aria-label", "Install app");
    button.textContent = "Install App";
    button.style.position = "fixed";
    button.style.right = "20px";
    button.style.bottom = "20px";
    button.style.zIndex = "10001";
    button.style.padding = "10px 14px";
    button.style.border = "1px solid rgba(255, 107, 0, 0.35)";
    button.style.borderRadius = "999px";
    button.style.background = "rgba(17, 17, 17, 0.96)";
    button.style.color = "#f0f0f0";
    button.style.font = "600 0.85rem Inter, -apple-system, BlinkMacSystemFont, sans-serif";
    button.style.cursor = "pointer";
    button.style.boxShadow = "0 10px 32px rgba(0, 0, 0, 0.28)";

    button.addEventListener("click", async function () {
      if (!deferredPrompt) {
        return;
      }

      deferredPrompt.prompt();
      try {
        await deferredPrompt.userChoice;
      } finally {
        deferredPrompt = null;
        button.hidden = true;
      }
    });

    document.body.appendChild(button);
    installButton = button;
    return button;
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    ensureInstallButton().hidden = false;
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    if (installButton) {
      installButton.hidden = true;
    }
  });

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(() => {
      // Safe no-op: PWA install support should never break the page.
    });
  });
})();

// Global Utilities & UI Logic (Theme, Toast, Button/Icon states)
(function () {
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon = document.getElementById('theme-icon');
  const root = document.documentElement;

  const toastConfig = {
    success: { title: 'Success', icon: 'bi-check-circle-fill' },
    error: { title: 'Error', icon: 'bi-x-circle-fill' },
    danger: { title: 'Error', icon: 'bi-x-circle-fill' },
    warning: { title: 'Warning', icon: 'bi-exclamation-triangle-fill' },
    info: { title: 'Info', icon: 'bi-info-circle-fill' },
  };

  window.showToast = function(message, type = 'info', timeout = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const normalizedType = type === 'danger' ? 'error' : type;
    const variant = toastConfig[normalizedType] || toastConfig.info;
    const toast = document.createElement('div');
    toast.className = `toast-notification ${normalizedType}`;
    toast.setAttribute('role', 'alert');

    const icon = document.createElement('i');
    icon.className = `bi ${variant.icon} toast-icon`;

    const content = document.createElement('div');
    content.className = 'toast-content';

    const title = document.createElement('div');
    title.className = 'toast-title';
    title.textContent = variant.title;

    const body = document.createElement('div');
    body.className = 'toast-message';
    body.textContent = message;

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-close';
    close.setAttribute('aria-label', 'Dismiss notification');
    close.innerHTML = '<i class="bi bi-x-lg"></i>';

    content.append(title, body);
    toast.append(icon, content, close);
    container.appendChild(toast);

    const removeToast = () => {
      toast.style.animation = 'toastSlideOut 0.25s ease forwards';
      setTimeout(() => toast.remove(), 250);
    };

    close.addEventListener('click', (event) => {
      event.stopPropagation();
      removeToast();
    });
    toast.addEventListener('click', removeToast);
    setTimeout(removeToast, timeout);
  };

  window.setButtonBusyState = function(button, contentEl, options = {}) {
    if (!button || !contentEl) return;

    const {
      busy = false,
      busyLabel = 'Working...',
      idleHTML = contentEl.dataset.idleHtml || contentEl.innerHTML,
    } = options;

    if (!contentEl.dataset.idleHtml) {
      contentEl.dataset.idleHtml = idleHTML;
    }

    if (busy) {
      button.disabled = true;
      contentEl.innerHTML = `<span class="btn-spinner" aria-hidden="true"></span> ${busyLabel}`;
      return;
    }

    button.disabled = false;
    contentEl.innerHTML = contentEl.dataset.idleHtml;
  };

  window.setIconBusyState = function(icon, options = {}) {
    if (!icon) return;

    const idleClassName = options.idleClassName || icon.dataset.idleClassName || icon.className;
    if (!icon.dataset.idleClassName) {
      icon.dataset.idleClassName = idleClassName;
    }

    icon.className = options.busy
      ? `${icon.dataset.idleClassName} btn-spinner`
      : icon.dataset.idleClassName;
  };

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
      root.style.setProperty('--text-muted', '#6b7280');
      if (themeIcon) themeIcon.className = 'bi bi-sun-fill';
    } else {
      root.style.setProperty('--bg-primary', '#111111');
      root.style.setProperty('--bg-secondary', '#1a1a1a');
      root.style.setProperty('--bg-card', '#1e1e1e');
      root.style.setProperty('--bg-card-hover', '#252525');
      root.style.setProperty('--border-color', '#2a2a2a');
      root.style.setProperty('--border-subtle', '#222222');
      root.style.setProperty('--text-primary', '#f0f0f0');
      root.style.setProperty('--text-secondary', '#a0a0a0');
      root.style.setProperty('--text-muted', '#8a8a8a');
      if (themeIcon) themeIcon.className = 'bi bi-moon-fill';
    }
  }

  const saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const curr = localStorage.getItem('theme') || 'dark';
      const next = curr === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      applyTheme(next);
      showToast(`Switched to ${next} mode`, 'info');
    });
  }

  // Auto-dismiss flash messages
  setTimeout(() => {
    const fc = document.getElementById('flash-container');
    if (fc) fc.style.opacity = '0', fc.style.transition = '0.5s', setTimeout(() => fc.remove(), 500);
  }, 4000);
})();
