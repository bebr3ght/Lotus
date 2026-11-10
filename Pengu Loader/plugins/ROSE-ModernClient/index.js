/**
 * @name ROSE-ModernClient
 * @author Lotus
 * @description Modern look and lighter rendering for the League client: theme, performance mode, reduced motion
 */
(function initRoseModernClient() {
  const LOG_PREFIX = "[ROSE-ModernClient]";
  const STORAGE_KEY = "rose_modern_client";
  const STYLE_THEME_ID = "rose-modern-client-theme";
  const STYLE_PERF_ID = "rose-modern-client-performance";
  const STYLE_MOTION_ID = "rose-modern-client-motion";
  const STYLE_PANEL_ID = "rose-modern-client-panel-style";
  const PANEL_ID = "rose-modern-client-panel";
  const PAUSED_ATTR = "data-rose-mc-paused";
  const HOTKEY = { ctrl: true, shift: true, key: "m" };

  const DEFAULTS = Object.freeze({
    theme: true,
    performance: false,
    reducedMotion: false,
    pauseBackgroundVideos: false,
  });

  // Texts go through ROSE-I18n when it is loaded, else stay in English
  const t = (text) => (window.RoseI18n && typeof window.RoseI18n.t === "function" ? window.RoseI18n.t(text) : text);

  function loadSettings() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (stored && typeof stored === "object") {
        const loaded = { ...DEFAULTS };
        for (const key of Object.keys(DEFAULTS)) {
          if (typeof stored[key] === "boolean") loaded[key] = stored[key];
        }
        return loaded;
      }
    } catch (e) {
      console.warn(`${LOG_PREFIX} Could not read settings, using defaults:`, e);
    }
    return { ...DEFAULTS };
  }

  let settings = loadSettings();

  function saveSettings() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (e) {
      console.warn(`${LOG_PREFIX} Could not save settings:`, e);
    }
  }

  // ---------------------------------------------------------------------------
  // Styles
  // ---------------------------------------------------------------------------

  const THEME_CSS = `
    :root {
      --rose-mc-radius: 8px;
      --rose-mc-radius-small: 4px;
      --rose-mc-accent: #c8aa6e;
      --rose-mc-accent-soft: rgba(200, 170, 110, 0.35);
      --rose-mc-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
      --rose-mc-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    }

    body {
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }

    /* Dialogs and flyouts: rounded, soft shadow, frosted backdrop */
    lol-uikit-dialog-frame,
    lol-uikit-flyout-frame,
    lol-uikit-content-block {
      border-radius: var(--rose-mc-radius);
      box-shadow: var(--rose-mc-shadow);
    }

    lol-uikit-dialog-frame {
      backdrop-filter: blur(10px) saturate(1.15);
    }

    /* Buttons and inputs: rounded corners, smooth hover */
    lol-uikit-flat-button,
    lol-uikit-flat-button-secondary,
    lol-uikit-flat-input,
    lol-uikit-dropdown {
      border-radius: var(--rose-mc-radius-small);
      transition: filter 160ms var(--rose-mc-ease), transform 160ms var(--rose-mc-ease);
    }

    lol-uikit-flat-button:hover,
    lol-uikit-flat-button-secondary:hover {
      filter: brightness(1.12);
    }

    lol-uikit-flat-button:active,
    lol-uikit-flat-button-secondary:active {
      transform: translateY(1px);
    }

    /* Thin, discreet scrollbars */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
      background: var(--rose-mc-accent-soft);
      border-radius: 8px;
    }
    ::-webkit-scrollbar-thumb:hover { background: var(--rose-mc-accent); }

    /* Visible keyboard focus */
    :focus-visible {
      outline: 2px solid var(--rose-mc-accent);
      outline-offset: 2px;
    }
  `;

  const PERFORMANCE_CSS = `
    /* Blur is the most expensive effect the client draws */
    *, *::before, *::after {
      backdrop-filter: none !important;
    }

    video[${PAUSED_ATTR}] {
      visibility: hidden !important;
    }
  `;

  const MOTION_CSS = `
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  `;

  const PANEL_CSS = `
    #${PANEL_ID} {
      position: fixed;
      top: 64px;
      right: 24px;
      z-index: 2147483000;
      width: 300px;
      padding: 16px;
      border: 1px solid rgba(200, 170, 110, 0.45);
      border-radius: 10px;
      background: rgba(1, 10, 19, 0.94);
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.55);
      color: #f0e6d2;
      font-family: "LoL Body", "Segoe UI", sans-serif;
      font-size: 13px;
    }
    #${PANEL_ID}[hidden] { display: none; }
    #${PANEL_ID} .rose-mc-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    #${PANEL_ID} .rose-mc-title {
      font-family: "LoL Display", "Segoe UI", sans-serif;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: #c8aa6e;
      text-transform: uppercase;
    }
    #${PANEL_ID} .rose-mc-close {
      border: none;
      background: transparent;
      color: #a09b8c;
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
    }
    #${PANEL_ID} .rose-mc-close:hover { color: #f0e6d2; }
    #${PANEL_ID} label {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 8px 0;
      border-top: 1px solid rgba(120, 90, 40, 0.35);
      cursor: pointer;
    }
    #${PANEL_ID} input[type="checkbox"] {
      margin-top: 2px;
      accent-color: #c8aa6e;
      cursor: pointer;
    }
    #${PANEL_ID} .rose-mc-hint {
      display: block;
      margin-top: 2px;
      color: #a09b8c;
      font-size: 11px;
    }
    #${PANEL_ID} .rose-mc-footer {
      margin-top: 10px;
      color: #7b7a74;
      font-size: 11px;
    }
  `;

  function setStyle(id, css, enabled) {
    const existing = document.getElementById(id);
    if (!enabled) {
      if (existing) existing.remove();
      return;
    }
    if (existing) return;
    const style = document.createElement("style");
    style.id = id;
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
  }

  // ---------------------------------------------------------------------------
  // Background videos
  // ---------------------------------------------------------------------------

  // A looping, muted video without controls is decoration (home, lobby,
  // champion backgrounds). Videos with sound or controls are left alone.
  function isBackgroundVideo(video) {
    return video.loop && (video.muted || video.volume === 0) && !video.controls;
  }

  function pauseVideo(video) {
    try {
      video.pause();
      video.setAttribute(PAUSED_ATTR, "");
    } catch (e) {
      // the video may already be detached
    }
  }

  function pauseBackgroundVideos() {
    document.querySelectorAll("video").forEach((video) => {
      if (isBackgroundVideo(video) && !video.hasAttribute(PAUSED_ATTR)) pauseVideo(video);
    });
  }

  function resumeBackgroundVideos() {
    document.querySelectorAll(`video[${PAUSED_ATTR}]`).forEach((video) => {
      video.removeAttribute(PAUSED_ATTR);
      const playing = video.play();
      if (playing && typeof playing.catch === "function") playing.catch(() => {});
    });
  }

  function onVideoPlay(event) {
    const video = event.target;
    if (video instanceof HTMLVideoElement && isBackgroundVideo(video)) pauseVideo(video);
  }

  let videoObserver = null;
  let videoScanScheduled = false;

  function scheduleVideoScan() {
    if (videoScanScheduled) return;
    videoScanScheduled = true;
    // One scan per frame at most, however many nodes the client adds
    requestAnimationFrame(() => {
      videoScanScheduled = false;
      pauseBackgroundVideos();
    });
  }

  function setVideoWatcher(enabled) {
    if (enabled) {
      pauseBackgroundVideos();
      if (!videoObserver) {
        videoObserver = new MutationObser

[Truncated after 272 lines. To continue, call readFile again with offset=273.]