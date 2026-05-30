(() => {
  const defaultPrefs = {
    theme_accent: "#ba5912",
    theme_density: "comfortable",
    theme_chart_palette: "default",
  };

  // Injected by base.html into window.__themeServerPrefs (replaces the old Jinja2 inline)
  const serverPrefs = window.__themeServerPrefs || null;

  const fixedPalettes = {
    pastel: ["#b45309", "#2563eb", "#15803d", "#be185d", "#7c3aed", "#64748b"],
    vivid: ["#b91c1c", "#1d4ed8", "#047857", "#a21caf", "#a16207", "#475569"],
    colorblind: [
      "#0072b2",
      "#a16207",
      "#00875a",
      "#8f3f97",
      "#4d5bd1",
      "#64748b",
    ],
  };

  const normalizeHex = (value) =>
    /^#[0-9a-fA-F]{6}$/.test(String(value || "").trim())
      ? String(value).trim().toLowerCase()
      : null;

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  const hexToRgb = (hex) => ({
    r: parseInt(hex.slice(1, 3), 16),
    g: parseInt(hex.slice(3, 5), 16),
    b: parseInt(hex.slice(5, 7), 16),
  });

  const rgbToHex = ({ r, g, b }) =>
    `#${[r, g, b].map((part) => Math.round(part).toString(16).padStart(2, "0")).join("")}`;

  const mixHex = (hex, target, amount) => {
    const sourceRgb = hexToRgb(hex);
    const targetRgb = hexToRgb(target);
    return rgbToHex({
      r: sourceRgb.r + (targetRgb.r - sourceRgb.r) * amount,
      g: sourceRgb.g + (targetRgb.g - sourceRgb.g) * amount,
      b: sourceRgb.b + (targetRgb.b - sourceRgb.b) * amount,
    });
  };

  const rgbToHsl = ({ r, g, b }) => {
    r /= 255;
    g /= 255;
    b /= 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0;
    let s = 0;
    const l = (max + min) / 2;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h *= 60;
    }
    return { h, s: s * 100, l: l * 100 };
  };

  const hslToHex = (h, s, l) => {
    h = ((h % 360) + 360) % 360;
    s = clamp(s, 0, 100) / 100;
    l = clamp(l, 0, 100) / 100;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;
    let r = 0,
      g = 0,
      b = 0;
    if (h < 60) [r, g, b] = [c, x, 0];
    else if (h < 120) [r, g, b] = [x, c, 0];
    else if (h < 180) [r, g, b] = [0, c, x];
    else if (h < 240) [r, g, b] = [0, x, c];
    else if (h < 300) [r, g, b] = [x, 0, c];
    else [r, g, b] = [c, 0, x];
    return rgbToHex({ r: (r + m) * 255, g: (g + m) * 255, b: (b + m) * 255 });
  };

  const channelLuminance = (value) => {
    value /= 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };

  const luminance = (hex) => {
    const rgb = hexToRgb(hex);
    return (
      0.2126 * channelLuminance(rgb.r) +
      0.7152 * channelLuminance(rgb.g) +
      0.0722 * channelLuminance(rgb.b)
    );
  };

  const contrast = (a, b) => {
    const l1 = luminance(a);
    const l2 = luminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };

  const accessibleAccent = (hex) => {
    const fallback = normalizeHex(hex) || defaultPrefs.theme_accent;
    const hsl = rgbToHsl(hexToRgb(fallback));
    const saturation = clamp(Math.max(hsl.s, 58), 58, 82);
    let best = fallback;
    let bestScore = -1;
    for (let lightness = 30; lightness <= 48; lightness += 1) {
      const candidate = hslToHex(hsl.h, saturation, lightness);
      const score = Math.min(
        contrast(candidate, "#111111"),
        contrast(candidate, "#f0f2f5"),
      );
      if (score > bestScore) {
        best = candidate;
        bestScore = score;
      }
    }
    return best;
  };

  const accessibleAccentFromHue = (hue) =>
    accessibleAccent(hslToHex(Number(hue) || 0, 72, 42));

  const derivedPalette = (accent) => {
    const hsl = rgbToHsl(hexToRgb(accent));
    return [
      accent,
      accessibleAccent(hslToHex(hsl.h + 38, 70, 42)),
      accessibleAccent(hslToHex(hsl.h + 135, 66, 40)),
      accessibleAccent(hslToHex(hsl.h + 245, 68, 42)),
      accessibleAccent(hslToHex(hsl.h + 78, 70, 40)),
      "#64748b",
    ];
  };

  const chartPalette = (palette, accent) =>
    palette === "default"
      ? derivedPalette(accent)
      : fixedPalettes[palette] || derivedPalette(accent);

  const accentDetails = (accent) => {
    const normalized = accessibleAccent(accent);
    const rgb = hexToRgb(normalized);
    const accent2 = derivedPalette(normalized)[1];
    const accent2Rgb = hexToRgb(accent2);
    return {
      accent: normalized,
      accent2,
      rgb,
      accent2Rgb,
      hover: mixHex(normalized, "#000000", 0.12),
      foreground:
        contrast(normalized, "#ffffff") >= contrast(normalized, "#111111")
          ? "#ffffff"
          : "#111111",
    };
  };

  const applyThemeVars = (prefs) => {
    const accent = accessibleAccent(prefs.theme_accent);
    const details = accentDetails(accent);
    const palette = chartPalette(prefs.theme_chart_palette, accent);
    const density =
      prefs.theme_density === "compact" ? "compact" : "comfortable";
    const rootStyle = document.documentElement.style;

    rootStyle.setProperty("--accent", details.accent);
    rootStyle.setProperty(
      "--accent-rgb",
      `${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}`,
    );
    rootStyle.setProperty("--accent-2", details.accent2);
    rootStyle.setProperty(
      "--accent-2-rgb",
      `${details.accent2Rgb.r}, ${details.accent2Rgb.g}, ${details.accent2Rgb.b}`,
    );
    rootStyle.setProperty("--accent-hover", details.hover);
    rootStyle.setProperty(
      "--accent-dim",
      `rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.16)`,
    );
    rootStyle.setProperty(
      "--accent-surface",
      `rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.10)`,
    );
    rootStyle.setProperty(
      "--accent-surface-strong",
      `rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.18)`,
    );
    rootStyle.setProperty("--accent-foreground", details.foreground);
    rootStyle.setProperty(
      "--accent-gradient",
      `linear-gradient(135deg, ${details.accent}, ${details.accent2})`,
    );
    rootStyle.setProperty(
      "--accent-surface-gradient",
      `linear-gradient(135deg, rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.14), rgba(${details.accent2Rgb.r}, ${details.accent2Rgb.g}, ${details.accent2Rgb.b}, 0.10))`,
    );

    rootStyle.setProperty("--radius", density === "compact" ? "8px" : "10px");
    rootStyle.setProperty(
      "--radius-lg",
      density === "compact" ? "12px" : "16px",
    );
    rootStyle.setProperty(
      "--topbar-height",
      density === "compact" ? "50px" : "56px",
    );
    rootStyle.setProperty(
      "--sidebar-width",
      density === "compact" ? "56px" : "64px",
    );

    palette.forEach((color, index) =>
      rootStyle.setProperty(`--chart-${index + 1}`, color),
    );
  };

  // Export utilities so theme-settings.js (and any page scripts) can reuse them
  window.themeColorUtils = {
    defaultPrefs,
    fixedPalettes,
    normalizeHex,
    hexToRgb,
    rgbToHex,
    rgbToHsl,
    hslToHex,
    accessibleAccent,
    accessibleAccentFromHue,
    derivedPalette,
    chartPalette,
    accentDetails,
    applyThemeVars,
  };

  // Apply initial theme from server prefs (if logged in) or localStorage
  let localPrefs = {};
  try {
    localPrefs = JSON.parse(localStorage.getItem("theme_prefs") || "{}");
  } catch {}

  const hasCustomPrefs = (prefs) =>
    Boolean(prefs) &&
    Object.keys(defaultPrefs).some(
      (key) => prefs[key] && prefs[key] !== defaultPrefs[key],
    );

  const initialPrefs =
    serverPrefs &&
    (serverPrefs.theme_preferences_customized || !hasCustomPrefs(localPrefs))
      ? serverPrefs
      : localPrefs;

  const prefs = { ...defaultPrefs, ...initialPrefs };
  applyThemeVars(prefs);

  if (prefs.theme_density === "compact") {
    document.addEventListener("DOMContentLoaded", () =>
      document.body.classList.add("compact"),
    );
  }
})();
// Theme Toggle
const themeToggle = document.getElementById("theme-toggle");
const themeIcon = document.getElementById("theme-icon");
const root = document.documentElement;

const toastConfig = {
  success: { title: "Success", icon: "bi-check-circle-fill" },
  error: { title: "Error", icon: "bi-x-circle-fill" },
  danger: { title: "Error", icon: "bi-x-circle-fill" },
  warning: { title: "Warning", icon: "bi-exclamation-triangle-fill" },
  info: { title: "Info", icon: "bi-info-circle-fill" },
};

window.showToast = function (message, type = "info", timeout = 4000) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const normalizedType = type === "danger" ? "error" : type;
  const variant = toastConfig[normalizedType] || toastConfig.info;
  const toast = document.createElement("div");
  toast.className = `toast-notification ${normalizedType}`;
  toast.setAttribute("role", "alert");

  const icon = document.createElement("i");
  icon.className = `bi ${variant.icon} toast-icon`;

  const content = document.createElement("div");
  content.className = "toast-content";

  const title = document.createElement("div");
  title.className = "toast-title";
  title.textContent = variant.title;

  const body = document.createElement("div");
  body.className = "toast-message";
  body.textContent = message;

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "Dismiss notification");
  close.innerHTML = '<i class="bi bi-x-lg"></i>';

  content.append(title, body);
  toast.append(icon, content, close);
  container.appendChild(toast);

  const removeToast = () => {
    toast.style.animation = "toastSlideOut 0.25s ease forwards";
    setTimeout(() => toast.remove(), 250);
  };

  close.addEventListener("click", (event) => {
    event.stopPropagation();
    removeToast();
  });
  toast.addEventListener("click", removeToast);
  setTimeout(removeToast, timeout);
};

window.setButtonBusyState = function (button, contentEl, options = {}) {
  if (!button || !contentEl) return;

  const {
    busy = false,
    busyLabel = "Working...",
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

window.setIconBusyState = function (icon, options = {}) {
  if (!icon) return;

  const idleClassName =
    options.idleClassName || icon.dataset.idleClassName || icon.className;
  if (!icon.dataset.idleClassName) {
    icon.dataset.idleClassName = idleClassName;
  }

  icon.className = options.busy
    ? `${icon.dataset.idleClassName} btn-spinner`
    : icon.dataset.idleClassName;
};

function applyTheme(theme) {
  if (theme === "light") {
    root.style.setProperty("--bg-primary", "#f0f2f5");
    root.style.setProperty("--bg-secondary", "#ffffff");
    root.style.setProperty("--bg-card", "#ffffff");
    root.style.setProperty("--bg-card-hover", "#f5f5f5");
    root.style.setProperty("--border-color", "#e0e0e0");
    root.style.setProperty("--border-subtle", "#ececec");
    root.style.setProperty("--text-primary", "#111111");
    root.style.setProperty("--text-secondary", "#555555");

    root.style.setProperty("--text-muted", "#6b7280");
    document.documentElement.dataset.theme = "light";

    themeIcon.className = "bi bi-sun-fill";
  } else {
    root.style.setProperty("--bg-primary", "#111111");
    root.style.setProperty("--bg-secondary", "#1a1a1a");
    root.style.setProperty("--bg-card", "#1e1e1e");
    root.style.setProperty("--bg-card-hover", "#252525");
    root.style.setProperty("--border-color", "#2a2a2a");
    root.style.setProperty("--border-subtle", "#222222");
    root.style.setProperty("--text-primary", "#f0f0f0");
    root.style.setProperty("--text-secondary", "#a0a0a0");

    root.style.setProperty("--text-muted", "#8a8a8a");
    document.documentElement.dataset.theme = "dark";

    themeIcon.className = "bi bi-moon-fill";
  }
}

const saved = localStorage.getItem("theme") || "dark";
applyTheme(saved);

themeToggle.addEventListener("click", () => {
  const curr = localStorage.getItem("theme") || "dark";
  const next = curr === "dark" ? "light" : "dark";
  localStorage.setItem("theme", next);
  applyTheme(next);
  showToast(`Switched to ${next} mode`, "info");
});

const themeUtils = window.themeColorUtils;
const defaultThemePrefs = themeUtils.defaultPrefs;
const themePrefsStorageKey = "theme_prefs";
const themeUserAuthenticated = document.body.dataset.authenticated === "1";
const themeSettingsBtn = document.getElementById("theme-settings-btn");
const themeSettingsModal = document.getElementById("theme-settings-modal");
const themeSettingsClose = document.getElementById("theme-settings-close");
const themeSettingsReset = document.getElementById("theme-settings-reset");
const themeSettingsSave = document.getElementById("theme-settings-save");
const accentHueInput = document.getElementById("accent-hue-input");
const accentPickerValue = document.getElementById("accent-picker-value");
const accentPickerLabel = document.getElementById("accent-picker-label");
const accentPickerPreview = document.getElementById("accent-picker-preview");
const densityButtons = Array.from(document.querySelectorAll("[data-density]"));
const paletteButtons = Array.from(document.querySelectorAll("[data-palette]"));
let persistedThemePrefs = { ...defaultThemePrefs };
let draftThemePrefs = { ...defaultThemePrefs };

const chartPalettes = { default: true, ...themeUtils.fixedPalettes };

function normalizeHex(value) {
  return themeUtils.normalizeHex(value);
}

function normalizeThemePrefs(prefs = {}) {
  const normalized = {
    theme_accent: themeUtils.accessibleAccent(
      prefs.theme_accent || defaultThemePrefs.theme_accent,
    ),
    theme_density:
      prefs.theme_density === "compact" ? "compact" : "comfortable",
    theme_chart_palette: chartPalettes[prefs.theme_chart_palette]
      ? prefs.theme_chart_palette
      : defaultThemePrefs.theme_chart_palette,
  };
  normalized.theme_preferences_customized = Boolean(
    prefs.theme_preferences_customized ||
    Object.keys(defaultThemePrefs).some(
      (key) => normalized[key] !== defaultThemePrefs[key],
    ),
  );
  return normalized;
}

function themePrefsPayload(prefs) {
  const normalized = normalizeThemePrefs(prefs);
  return {
    theme_accent: normalized.theme_accent,
    theme_density: normalized.theme_density,
    theme_chart_palette: normalized.theme_chart_palette,
  };
}

function hasCustomThemePrefs(prefs) {
  if (!prefs) return false;
  const normalized = normalizeThemePrefs(prefs);
  return Object.keys(defaultThemePrefs).some(
    (key) => normalized[key] !== defaultThemePrefs[key],
  );
}

function updateThemeControls(prefs = draftThemePrefs) {
  densityButtons.forEach((button) => {
    const isActive = button.dataset.density === prefs.theme_density;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  paletteButtons.forEach((button) => {
    const isActive = button.dataset.palette === prefs.theme_chart_palette;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
  document.querySelectorAll(".accent-swatch").forEach((swatch) => {
    const swatchAccent = themeUtils.accessibleAccent(swatch.dataset.accent);
    const isActive = swatchAccent === prefs.theme_accent;
    swatch.classList.toggle("active", isActive);
    swatch.setAttribute("aria-pressed", String(isActive));
  });
  if (accentHueInput) {
    const hsl = themeUtils.rgbToHsl(themeUtils.hexToRgb(prefs.theme_accent));
    accentHueInput.value = String(Math.round(hsl.h));
    accentPickerValue.textContent = prefs.theme_accent.toUpperCase();
    accentPickerLabel.textContent = accentLabelForHue(hsl.h);
    accentPickerPreview.style.background = "var(--accent-gradient)";
  }
  updatePalettePreviews(prefs.theme_accent);
}

function accentLabelForHue(hue) {
  if (hue < 22 || hue >= 340) return "Red";
  if (hue < 50) return "Orange";
  if (hue < 82) return "Amber";
  if (hue < 155) return "Green";
  if (hue < 190) return "Teal";
  if (hue < 230) return "Blue";
  if (hue < 285) return "Purple";
  return "Rose";
}

function updatePalettePreviews(accent) {
  const previewMap = {
    default: themeUtils.chartPalette("default", accent),
    pastel: themeUtils.chartPalette("pastel", accent),
    vivid: themeUtils.chartPalette("vivid", accent),
    colorblind: themeUtils.chartPalette("colorblind", accent),
  };
  paletteButtons.forEach((button) => {
    const colors = previewMap[button.dataset.palette] || previewMap.default;
    button
      .querySelectorAll(".chart-palette-preview span")
      .forEach((span, index) => {
        span.style.background = colors[index] || colors[0];
      });
  });
}

function applyAccentColor(color) {
  const details = themeUtils.accentDetails(color);
  root.style.setProperty("--accent", details.accent);
  root.style.setProperty(
    "--accent-rgb",
    `${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}`,
  );
  root.style.setProperty("--accent-2", details.accent2);
  root.style.setProperty(
    "--accent-2-rgb",
    `${details.accent2Rgb.r}, ${details.accent2Rgb.g}, ${details.accent2Rgb.b}`,
  );
  root.style.setProperty("--accent-hover", details.hover);
  root.style.setProperty(
    "--accent-dim",
    `rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.16)`,
  );
  root.style.setProperty(
    "--accent-surface",
    `rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.10)`,
  );
  root.style.setProperty(
    "--accent-surface-strong",
    `rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.18)`,
  );
  root.style.setProperty("--accent-foreground", details.foreground);
  root.style.setProperty(
    "--accent-gradient",
    `linear-gradient(135deg, ${details.accent}, ${details.accent2})`,
  );
  root.style.setProperty(
    "--accent-surface-gradient",
    `linear-gradient(135deg, rgba(${details.rgb.r}, ${details.rgb.g}, ${details.rgb.b}, 0.14), rgba(${details.accent2Rgb.r}, ${details.accent2Rgb.g}, ${details.accent2Rgb.b}, 0.10))`,
  );
}

function applyDensity(density) {
  const nextDensity = density === "compact" ? "compact" : "comfortable";
  document.body.classList.toggle("compact", nextDensity === "compact");
  root.style.setProperty(
    "--radius",
    nextDensity === "compact" ? "8px" : "10px",
  );
  root.style.setProperty(
    "--radius-lg",
    nextDensity === "compact" ? "12px" : "16px",
  );
  root.style.setProperty(
    "--topbar-height",
    nextDensity === "compact" ? "50px" : "56px",
  );
  root.style.setProperty(
    "--sidebar-width",
    nextDensity === "compact" ? "56px" : "64px",
  );
}

function applyChartPalette(palette, accent = draftThemePrefs.theme_accent) {
  const colors = themeUtils.chartPalette(palette, accent);
  colors.forEach((color, index) => {
    root.style.setProperty(`--chart-${index + 1}`, color);
  });
}

function applyThemeVisuals(prefs) {
  const normalized = normalizeThemePrefs(prefs);
  applyAccentColor(normalized.theme_accent);
  applyDensity(normalized.theme_density);
  applyChartPalette(normalized.theme_chart_palette, normalized.theme_accent);
  updateThemeControls(normalized);
  if (typeof window.refreshThemedCharts === "function") {
    window.refreshThemedCharts();
  }
}

function readLocalThemePrefs() {
  try {
    return JSON.parse(localStorage.getItem(themePrefsStorageKey) || "{}");
  } catch {
    return {};
  }
}

function writeLocalThemePrefs(prefs) {
  localStorage.setItem(
    themePrefsStorageKey,
    JSON.stringify(themePrefsPayload(prefs)),
  );
}

function setPersistedThemePrefs(prefs) {
  persistedThemePrefs = normalizeThemePrefs(prefs);
  draftThemePrefs = { ...persistedThemePrefs };
  applyThemeVisuals(persistedThemePrefs);
  syncThemeForm(persistedThemePrefs);
}

function setDraftThemePrefs(prefs) {
  draftThemePrefs = normalizeThemePrefs({ ...draftThemePrefs, ...prefs });
  applyThemeVisuals(draftThemePrefs);
  syncThemeForm(draftThemePrefs);
}

function syncThemeForm(prefs = draftThemePrefs) {
  updateThemeControls(prefs);
}

function getThemeFormPrefs() {
  return {
    theme_accent: draftThemePrefs.theme_accent,
    theme_density: draftThemePrefs.theme_density,
    theme_chart_palette: draftThemePrefs.theme_chart_palette,
  };
}

function openThemeSettings() {
  draftThemePrefs = { ...persistedThemePrefs };
  syncThemeForm();
  themeSettingsModal.classList.add("open");
  accentHueInput.focus();
}

function closeThemeSettings({ revert = true } = {}) {
  themeSettingsModal.classList.remove("open");
  if (revert) {
    draftThemePrefs = { ...persistedThemePrefs };
    applyThemeVisuals(persistedThemePrefs);
    syncThemeForm(persistedThemePrefs);
  }
  themeSettingsBtn.focus();
}

async function persistThemePrefs(
  prefs,
  { silent = false, closePanel = false } = {},
) {
  const payload = themePrefsPayload(prefs);
  applyThemeVisuals(payload);

  if (!themeUserAuthenticated) {
    writeLocalThemePrefs(payload);
    setPersistedThemePrefs({
      ...payload,
      theme_preferences_customized: hasCustomThemePrefs(payload),
    });
    if (!silent) showToast("Theme settings saved", "success");
    if (closePanel) closeThemeSettings({ revert: false });
    return true;
  }

  themeSettingsSave.disabled = true;
  try {
    const response = await fetch(themePrefsUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": themeCsrfToken,
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      const errors = result.errors
        ? Object.values(result.errors).join(" ")
        : result.error;
      throw new Error(errors || "Unable to save theme settings.");
    }
    setPersistedThemePrefs(result);
    writeLocalThemePrefs(result);
    if (!silent) showToast("Theme settings saved", "success");
    if (closePanel) closeThemeSettings({ revert: false });
    return true;
  } catch (error) {
    if (!silent)
      showToast(error.message || "Unable to save theme settings.", "error");
    return false;
  } finally {
    themeSettingsSave.disabled = false;
  }
}

async function refreshThemePrefs() {
  const localPrefs = readLocalThemePrefs();
  if (!themeUserAuthenticated) {
    setPersistedThemePrefs(localPrefs);
    return;
  }

  try {
    const response = await fetch(themePrefsUrl);
    if (!response.ok) return;
    const serverPrefs = await response.json();
    if (
      !serverPrefs.theme_preferences_customized &&
      hasCustomThemePrefs(localPrefs)
    ) {
      setDraftThemePrefs(localPrefs);
      await persistThemePrefs(localPrefs, { silent: true });
      return;
    }
    setPersistedThemePrefs(serverPrefs);
    writeLocalThemePrefs(serverPrefs);
  } catch {
    setPersistedThemePrefs(serverThemePrefs || {});
  }
}

async function saveThemePrefs() {
  const prefs = getThemeFormPrefs();
  await persistThemePrefs(prefs, { closePanel: true });
}

const localInitialThemePrefs = readLocalThemePrefs();
const initialThemePrefs =
  themeUserAuthenticated &&
  serverThemePrefs &&
  (serverThemePrefs.theme_preferences_customized ||
    !hasCustomThemePrefs(localInitialThemePrefs))
    ? serverThemePrefs
    : localInitialThemePrefs;
setPersistedThemePrefs(initialThemePrefs);
refreshThemePrefs();

themeSettingsBtn.addEventListener("click", openThemeSettings);
themeSettingsClose.addEventListener("click", () => closeThemeSettings());
themeSettingsModal.addEventListener("click", (event) => {
  if (event.target === themeSettingsModal) closeThemeSettings();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && themeSettingsModal.classList.contains("open")) {
    closeThemeSettings();
  }
});
accentHueInput.addEventListener("input", () => {
  setDraftThemePrefs({
    theme_accent: themeUtils.accessibleAccentFromHue(accentHueInput.value),
  });
});
densityButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setDraftThemePrefs({ theme_density: button.dataset.density });
  });
});
paletteButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setDraftThemePrefs({ theme_chart_palette: button.dataset.palette });
  });
});
document.querySelectorAll(".accent-swatch").forEach((swatch) => {
  swatch.addEventListener("click", () => {
    const nextAccent = swatch.dataset.accent;
    setDraftThemePrefs({ theme_accent: nextAccent });
  });
});
themeSettingsReset.addEventListener("click", () => {
  setDraftThemePrefs(defaultThemePrefs);
});
themeSettingsSave.addEventListener("click", saveThemePrefs);

// Auto-dismiss flash messages
setTimeout(() => {
  const fc = document.getElementById("flash-container");
  if (fc)
    ((fc.style.opacity = "0"),
      (fc.style.transition = "0.5s"),
      setTimeout(() => fc.remove(), 500));
}, 4000);
