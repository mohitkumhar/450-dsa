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
