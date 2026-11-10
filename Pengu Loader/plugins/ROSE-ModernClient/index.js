/**
 * @name ROSE-ModernClient
 * @author Lotus
 * @description Modern look and lighter rendering for the League client: theme, accent colors, ambient glow, performance mode, reduced motion
 */
(function initRoseModernClient() {
  const LOG_PREFIX = "[ROSE-ModernClient]";
  const STORAGE_KEY = "rose_modern_client";
  const STYLE_ID = "rose-modern-client-style";
  const PANEL_STYLE_ID = "rose-modern-client-panel-style";
  const PANEL_ID = "rose-modern-client-panel";
  const GLOW_ID = "rose-modern-client-glow";
  const PAUSED_ATTR = "data-rose-mc-paused";

  // RGB triplets, used as rgba(var(--rose-mc-accent-rgb), alpha)
  const ACCENTS = Object.freeze({
    gold: { label: "Gold", rgb: "200, 170, 110" },
    hextech: { label: "Hextech", rgb: "10, 200, 185" },
    violet: { label: "Violet", rgb: "170, 120, 255" },
    crimson: { label: "Crimson", rgb: "235, 75, 95" },
  });

  const DEFAULTS = Object.freeze({
    theme: true,
    glow: true,
    performance: false,
    reducedMotion: false,
    pauseBackgroundVideos: false,
    accent: "gold",
    intensity: 60,
  });

  const BOOLEAN_KEYS = ["theme", "glow", "performance", "reducedMotion", "pauseBackgroundVideos"];

  // Texts go through ROSE-I18n when it is loaded, else stay in English
  const t = (text) => (window.RoseI18n && typeof window.RoseI18n.t === "function" ? window.RoseI18n.t(text) : text);

  function sanitize(source) {
    const next = { ...DEFAULTS };
    if (!source || typeof source !== "object") return next;
    for (const key of BOOLEAN_KEYS) {
      if (typeof source[key] === "boolean") next[key] = source[key];
    }
    if (typeof source.accent === "string" && ACCENTS[source.accent]) next.accent = source.accent;
    const intensity = Number(source.intensity);
    if (Number.isFinite(intensity)) next.intensity = Math.min(100, Math.max(0, Math.round(intensity)));
    return next;
  }

  function loadSettings() {
    try {
      return sanitize(JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"));
    } catch (e) {
      console.warn(`${LOG_PREFIX} Could not read settings, using defaults:`, e);
      return { ...DEFAULTS };
    }
  }

  let settings = loadSettings();

  function saveSettings() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (e) {
      console.warn(`${LOG_PREFIX} Could not save settings:`, e);
    }
  }

  const pausesVideos = () => settings.performance || settings.pauseBackgroundVideos;
  const reducesMotion = () => settings.performance || settings.reducedMotion;

  // ---------------------------------------------------------------------------
  // Styles
  // ---------------------------------------------------------------------------

  // --rose-mc-i is the intensity from 0 to 1. Custom properties inherit into
  // shadow roots, so the same variables work inside the client's components.
  const A = (alpha) => `rgba(var(--rose-mc-accent-rgb), ${alpha})`;

  // Styles for the page itself. Components with a shadow root (buttons,
  // navigation items, frames) only take what is set on the host element:
  // filters and inherited properties such as text-shadow.
  const DOCUMENT_THEME_CSS = `
    body {
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }

    /* Social sidebar: accent tint at the top and a thin accent edge */
    .rcp-fe-viewport-sidebar {
      background:
        linear-gradient(180deg, ${A("calc(0.05 + 0.17 * var(--rose-mc-i))")} 0%, rgba(1, 10, 19, 0) 45%),
        linear-gradient(180deg, rgb(4, 16, 28), rgb(1, 10, 19)) !important;
      box-shadow: inset 1px 0 0 ${A("calc(0.25 + 0.45 * var(--rose-mc-i))")};
    }

    /* Navigation tabs: glow on hover and on the active tab */
    lol-uikit-navigation-bar {
      box-shadow: 0 1px 0 ${A("calc(0.15 + 0.35 * var(--rose-mc-i))")};
    }
    lol-uikit-navigation-item {
      transition: text-shadow 200ms ease, filter 200ms ease;
    }
    lol-uikit-navigation-item:hover {
      text-shadow: 0 0 calc(4px + 10px * var(--rose-mc-i)) ${A(0.85)};
      filter: brightness(1.15);
    }
    lol-uikit-navigation-item[active] {
      text-shadow: 0 0 calc(4px + 12px * var(--rose-mc-i)) ${A(0.95)};
    }

    /* Buttons: soft accent glow on hover, press feedback */
    lol-uikit-flat-button,
    lol-uikit-flat-button-secondary,
    lol-parties-comm-button,
    lol-player-notifications-button {
      transition: filter 180ms ease, transform 120ms ease;
    }
    lol-uikit-flat-button:hover,
    lol-uikit-flat-button-secondary:hover,
    lol-parties-comm-button:hover,
    lol-player-notifications-button:hover {
      filter: brightness(1.15) drop-shadow(0 0 calc(3px + 9px * var(--rose-mc-i)) ${A(0.75)});
    }
    lol-uikit-flat-button:active,
    lol-uikit-flat-button-secondary:active {
      transform: translateY(1px);
    }

    /* Play button, when the client marks it with a play-button class */
    .rcp-fe-viewport-persistent [class*="play-button"] {
      filter: drop-shadow(0 0 calc(4px + 12px * var(--rose-mc-i)) ${A(0.55)});
      transition: filter 200ms ease;
    }
    .rcp-fe-viewport-persistent [class*="play-button"]:hover {
      filter: brightness(1.1) drop-shadow(0 0 calc(6px + 16px * var(--rose-mc-i)) ${A(0.85)});
    }

    /* Text fields: accent glow while typing */
    lol-uikit-flat-input {
      transition: filter 180ms ease;
    }
    lol-uikit-flat-input:focus-within {
      filter: drop-shadow(0 0 calc(3px + 7px * var(--rose-mc-i)) ${A(0.7)});
    }

    /* Dialogs and cards: depth plus a faint accent halo */
    lol-uikit-dialog-frame,
    lol-uikit-content-block,
    lol-parties-game-info-panel {
      filter: drop-shadow(0 12px 28px rgba(0, 0, 0, 0.55))
        drop-shadow(0 0 calc(10px * var(--rose-mc-i)) ${A(0.3)});
    }

    :focus-visible {
      outline: 2px solid ${A(0.9)};
      outline-offset: 2px;
    }

    #${GLOW_ID} {
      position: fixed;
      inset: 0;
      z-index: 2147482000;
      pointer-events: none;
      mix-blend-mode: screen;
      opacity: calc(0.15 + 0.6 * var(--rose-mc-i));
      background:
        radial-gradient(ellipse 45% 35% at 0% 0%, ${A(0.22)}, transparent 70%),
        radial-gradient(ellipse 40% 30% at 100% 100%, ${A(0.16)}, transparent 70%);
    }
  `;

  // Styles that also go inside every open shadow root
  const SCROLLBAR_CSS = `
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: ${A(0.35)}; border-radius: 8px; }
    ::-webkit-scrollbar-thumb:hover { background: ${A(0.8)}; }
  `;

  const PERFORMANCE_CSS = `
    *, *::before, *::after { backdrop-filter: none !important; }
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
      width: 320px;
      padding: 16px;
      border: 1px solid ${A(0.5)};
      border-radius: 12px;
      background: linear-gradient(180deg, ${A(0.12)}, rgba(1, 10, 19, 0) 40%), rgba(1, 10, 19, 0.96);
      box-shadow: 0 14px 40px rgba(0, 0, 0, 0.6), 0 0 24px ${A(0.15)};
      color: #f0e6d2;
      font-family: "LoL Body", "Segoe UI", sans-serif;
      font-size: 13px;
    }
    #${PANEL_ID}[hidden] { display: none; }
    #${PANEL_ID} .rose-mc-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }
    #${PANEL_ID} .rose-mc-title {
      font-family: "LoL Display", "Segoe UI", sans-serif;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: rgb(var(--rose-mc-accent-rgb));
      text-shadow: 0 0 10px ${A(0.5)};
    }
    #${PANEL_ID} button { font: inherit; cursor: pointer; }
    #${PANEL_ID} .rose-mc-close {
      border: none;
      background: transparent;
      color: #a09b8c;
      font-size: 18px;
      line-height: 1;
    }
    #${PANEL_ID} .rose-mc-close:hover { color: #f0e6d2; }
    #${PANEL_ID} label.rose-mc-option {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 8px 0;
      border-top: 1px solid rgba(120, 90, 40, 0.3);
      cursor: pointer;
    }
    #${PANEL_ID} input[type="checkbox"],
    #${PANEL_ID} input[type="range"] {
      accent-color: rgb(var(--rose-mc-accent-rgb));
      cursor: pointer;
    }
    #${PANEL_ID} input[type="checkbox"] { margin-top: 2px; }
    #${PANEL_ID} input:disabled { cursor: default; opacity: 0.6; }
    #${PANEL_ID} .rose-mc-hint {
      display: block;
      margin-top: 2px;
      color: #a09b8c;
      font-size: 11px;
    }
    #${PANEL_ID} .rose-mc-row {
      padding: 10px 0 8px;
      border-top: 1px solid rgba(120, 90, 40, 0.3);
    }
    #${PANEL_ID} .rose-mc-row-title {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    #${PANEL_ID} .rose-mc-swatches { display: flex; gap: 8px; }
    #${PANEL_ID} .rose-mc-swatch {
      flex: 1;
      padding: 6px 0;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.03);
      color: #cdbe91;
      font-size: 11px;
    }
    #${PANEL_ID} .rose-mc-swatch::before {
      content: "";
      display: block;
      width: 14px;
      height: 14px;
      margin: 0 auto 4px;
      border-radius: 50%;
      background: rgb(var(--swatch));
      box-shadow: 0 0 8px rgba(var(--swatch), 0.7);
    }
    #${PANEL_ID} .rose-mc-swatch[aria-pressed="true"] {
      border-color: rgb(var(--swatch));
      background: rgba(var(--swatch), 0.12);
      color: #f0e6d2;
    }
    #${PANEL_ID} input[type="range"] { width: 100%; }
    #${PANEL_ID} .rose-mc-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 10px;
      color: #7b7a74;
      font-size: 11px;
    }
    #${PANEL_ID} .rose-mc-reset {
      padding: 4px 10px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 6px;
      background: transparent;
      color: #a09b8c;
      font-size: 11px;
    }
    #${PANEL_ID} .rose-mc-reset:hover { color: #f0e6d2; border-color: ${A(0.6)}; }
  `;

  function documentCss() {
    let css = "";
    if (settings.theme) css += DOCUMENT_THEME_CSS + SCROLLBAR_CSS;
    if (settings.performance) css += PERFORMANCE_CSS;
    if (reducesMotion()) css += MOTION_CSS;
    return css;
  }

  function shadowCss() {
    let css = "";
    if (settings.theme) css += SCROLLBAR_CSS;
    if (settings.performance) css += PERFORMANCE_CSS;
    if (reducesMotion()) css += MOTION_CSS;
    return css;
  }

  function setStyleTag(id, css) {
    let style = document.getElementById(id);
    if (!css) {
      if (style) style.remove();
      return;
    }
    if (!style) {
      style = document.createElement("style");
      style.id = id;
      (document.head || document.documentElement).appendChild(style);
    }
    if (style.textContent !== css) style.textContent = css;
  }

  function applyVariables() {
    const root = document.documentElement;
    root.style.setProperty("--rose-mc-accent-rgb", ACCENTS[settings.accent].rgb);
    root.style.setProperty("--rose-mc-i", String(settings.intensity / 100));
  }

  // ---------------------------------------------------------------------------
  // Shadow roots
  // ---------------------------------------------------------------------------

  // One stylesheet shared by every shadow root: updating it restyles all of
  // them at once. Older engines without adoptedStyleSheets get a style tag.
  const canAdopt = typeof CSSStyleSheet === "function" && "adoptedStyleSheets" in ShadowRoot.prototype && "replaceSync" in CSSStyleSheet.prototype;
  const shadowSheet = canAdopt ? new CSSStyleSheet() : null;
  const SHADOW_STYLE_CLASS = "rose-mc-shadow-style";

  const roots = new Set();
  const knownRoots = new WeakSet();
  let rootObserver = null;
  let pendingNodes = new Set();
  let flushScheduled = false;

  function injectInto(root) {
    if (shadowSheet) {
      if (!root.adoptedStyleSheets.includes(shadowSheet)) {
        root.adoptedStyleSheets = [...root.adoptedStyleSheets, shadowSheet];
      }
      return;
    }
    let style = root.querySelector(`style.${SHADOW_STYLE_CLASS}`);
    if (!style) {
      style = document.createElement("style");
      style.className = SHADOW_STYLE_CLASS;
      root.appendChild(style);
    }
    style.textContent = shadowCss();
  }

  function refreshShadowStyles() {
    if (shadowSheet) {
      shadowSheet.replaceSync(shadowCss());
      return;
    }
    for (const root of roots) injectInto(root);
  }

  function registerRoot(root) {
    if (!root || knownRoots.has(root)) return;
    knownRoots.add(root);
    roots.add(root);
    injectInto(root);
    if (rootObserver) rootObserver.observe(root, { childList: true, subtree: true });
    // play does not cross shadow boundaries, so listen on each root
    root.addEventListener("play", onVideoPlay, true);
    scanNode(root);
  }

  function scanNode(node) {
    if (!node || typeof node.querySelectorAll !== "function") return;
    if (node.shadowRoot) registerRoot(node.shadowRoot);
    node.querySelectorAll("*").forEach((el) => {
      if (el.shadowRoot) registerRoot(el.shadowRoot);
    });
    if (pausesVideos()) {
      if (node instanceof HTMLVideoElement) maybePause(node);
      node.querySelectorAll("video").forEach(maybePause);
    }
  }

  function flushPending() {
    flushScheduled = false;
    const nodes = pendingNodes;
    pendingNodes = new Set();
    nodes.forEach((node) => {
      if (node.isConnected) scanNode(node);
    });
    // Forget roots whose host left the page
    for (const root of roots) {
      if (!root.host || !root.host.isConnected) roots.delete(root);
    }
  }

  function onMutations(records) {
    for (const record of records) {
      record.addedNodes.forEach((node) => {
        if (node.nodeType === Node.ELEMENT_NODE) pendingNodes.add(node);
      });
    }
    if (!flushScheduled && pendingNodes.size) {
      flushScheduled = true;
      // One pass per frame, however many nodes the client adds
      requestAnimationFrame(flushPending);
    }
  }

  function watchShadowRoots() {
    rootObserver = new MutationObserver(onMutations);
    rootObserver.observe(document.documentElement, { childList: true, subtree: true });

    // Catch components created later, before they fill their shadow root
    const originalAttachShadow = Element.prototype.attachShadow;
    if (typeof originalAttachShadow === "function" && !originalAttachShadow.__roseModernClient) {
      const patched = function attachShadow(init) {
        const root = originalAttachShadow.call(this, init);
        if (init && init.mode === "open") {
          Promise.resolve().then(() => registerRoot(root));
        }
        return root;
      };
      patched.__roseModernClient = true;
      Element.prototype.attachShadow = patched;
    }

    scanNode(document.documentElement);
  }

  // ---------------------------------------------------------------------------
  // Background videos
  // ---------------------------------------------------------------------------

  // A looping, muted video without controls is decoration (home screen,
  // lobby, champion backgrounds). Videos with sound or controls stay as they are.
  function isBackgroundVideo(video) {
    return video.loop && (video.muted || video.volume === 0) && !video.controls;
  }

  function maybePause(video) {
    if (!isBackgroundVideo(video) || video.hasAttribute(PAUSED_ATTR)) return;
    try {
      video.pause();
      video.setAttribute(PAUSED_ATTR, "");
    } catch (e) {
      // the video may already be detached
    }
  }

  function onVideoPlay(event) {
    const video = event.target;
    if (!pausesVideos() || !(video instanceof HTMLVideoElement) || !isBackgroundVideo(video)) return;
    video.removeAttribute(PAUSED_ATTR);
    maybePause(video);
  }

  function allVideos() {
    const videos = [...document.querySelectorAll("video")];
    for (const root of roots) videos.push(...root.querySelectorAll("video"));
    return videos;
  }

  function applyVideos() {
    if (pausesVideos()) {
      allVideos().forEach(maybePause);
      return;
    }
    allVideos().forEach((video) => {
      if (!video.hasAttribute(PAUSED_ATTR)) return;
      video.removeAttribute(PAUSED_ATTR);
      const playing = video.play();
      if (playing && typeof playing.catch === "function") playing.catch(() => {});
    });
  }

  // ---------------------------------------------------------------------------
  // Ambient glow
  // ---------------------------------------------------------------------------

  function applyGlow() {
    const enabled = settings.theme && settings.glow && !settings.performance;
    let glow = document.getElementById(GLOW_ID);
    if (!enabled) {
      if (glow) glow.remove();
      return;
    }
    if (!glow && document.body) {
      glow = document.createElement("div");
      glow.id = GLOW_ID;
      glow.setAttribute("aria-hidden", "true");
      document.body.appendChild(glow);
    }
  }

  // ---------------------------------------------------------------------------
  // Apply
  // ---------------------------------------------------------------------------

  function apply() {
    applyVariables();
    setStyleTag(STYLE_ID, documentCss());
    refreshShadowStyles();
    applyGlow();
    applyVideos();
  }

  function update(changes) {
    settings = sanitize({ ...settings, ...(changes || {}) });
    saveSettings();
    apply();
    syncPanel();
  }

  // ---------------------------------------------------------------------------
  // Settings panel (Ctrl+Shift+M)
  // ---------------------------------------------------------------------------

  const OPTIONS = [
    { key: "theme", label: "Modern theme", hint: "Accent glow on tabs and buttons, tinted sidebar, slim scrollbars" },
    { key: "glow", label: "Ambient glow", hint: "Soft accent light in the corners of the client" },
    { key: "performance", label: "Performance mode", hint: "No blur, no animations, paused background videos" },
    { key: "reducedMotion", label: "Reduce motion", hint: "Shorter animations and transitions" },
    { key: "pauseBackgroundVideos", label: "Pause background videos", hint: "Lower CPU and GPU use on the home screen" },
  ];

  let panel = null;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function buildPanel() {
    setStyleTag(PANEL_STYLE_ID, PANEL_CSS);

    panel = el("div");
    panel.id = PANEL_ID;
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", t("Modern Client"));

    const header = el("div", "rose-mc-header");
    const close = el("button", "rose-mc-close", "\u00d7");
    close.type = "button";
    close.setAttribute("aria-label", t("Close"));
    close.addEventListener("click", () => togglePanel(false));
    header.append(el("span", "rose-mc-title", t("Modern Client")), close);
    panel.appendChild(header);

    for (const option of OPTIONS) {
      const label = el("label", "rose-mc-option");
      const input = el("input");
      input.type = "checkbox";
      input.dataset.key = option.key;
      input.addEventListener("change", () => update({ [option.key]: input.checked }));
      const text = el("span", "", t(option.label));
      text.appendChild(el("span", "rose-mc-hint", t(option.hint)));
      label.append(input, text);
      panel.appendChild(label);
    }

    const accentRow = el("div", "rose-mc-row");
    accentRow.appendChild(el("div", "rose-mc-row-title", t("Accent color")));
    const swatches = el("div", "rose-mc-swatches");
    for (const [id, accent] of Object.entries(ACCENTS)) {
      const swatch = el("button", "rose-mc-swatch", t(accent.label));
      swatch.type = "button";
      swatch.dataset.accent = id;
      swatch.style.setProperty("--swatch", accent.rgb);
      swatch.addEventListener("click", () => update({ accent: id }));
      swatches.appendChild(swatch);
    }
    accentRow.appendChild(swatches);
    panel.appendChild(accentRow);

    const intensityRow = el("div", "rose-mc-row");
    const intensityTitle = el("div", "rose-mc-row-title");
    const intensityValue = el("span", "rose-mc-hint rose-mc-intensity-value");
    intensityTitle.append(el("span", "", t("Effect strength")), intensityValue);
    const range = el("input");
    range.type = "range";
    range.min = "0";
    range.max = "100";
    range.step = "5";
    range.className = "rose-mc-intensity";
    range.setAttribute("aria-label", t("Effect strength"));
    // Live preview while dragging, saved when released
    range.addEventListener("input", () => {
      document.documentElement.style.setProperty("--rose-mc-i", String(Number(range.value) / 100));
      intensityValue.textContent = `${range.value}%`;
    });
    range.addEventListener("change", () => update({ intensity: Number(range.value) }));
    intensityRow.append(intensityTitle, range);
    panel.appendChild(intensityRow);

    const footer = el("div", "rose-mc-footer");
    const reset = el("button", "rose-mc-reset", t("Reset"));
    reset.type = "button";
    reset.addEventListener("click", () => update({ ...DEFAULTS }));
    footer.append(el("span", "", t("Ctrl+Shift+M to open or close")), reset);
    panel.appendChild(footer);

    document.body.appendChild(panel);
    syncPanel();
  }

  function syncPanel() {
    if (!panel) return;
    panel.querySelectorAll("input[data-key]").forEach((input) => {
      const key = input.dataset.key;
      // Performance mode covers these and turns the glow off
      const covered = settings.performance && (key === "reducedMotion" || key === "pauseBackgroundVideos");
      const blocked = key === "glow" && (settings.performance || !settings.theme);
      input.checked = covered || (!blocked && Boolean(settings[key]));
      input.disabled = covered || blocked;
    });
    panel.querySelectorAll(".rose-mc-swatch").forEach((swatch) => {
      swatch.setAttribute("aria-pressed", String(swatch.dataset.accent === settings.accent));
    });
    const range = panel.querySelector(".rose-mc-intensity");
    if (range) range.value = String(settings.intensity);
    const value = panel.querySelector(".rose-mc-intensity-value");
    if (value) value.textContent = `${settings.intensity}%`;
  }

  function togglePanel(force) {
    if (!panel) {
      if (!document.body) return;
      buildPanel();
    }
    panel.hidden = typeof force === "boolean" ? !force : !panel.hidden;
  }

  function onKeyDown(event) {
    if (event.key === "Escape" && panel && !panel.hidden) {
      togglePanel(false);
      return;
    }
    if (event.ctrlKey && event.shiftKey && !event.altKey && typeof event.key === "string" && event.key.toLowerCase() === "m") {
      event.preventDefault();
      togglePanel();
    }
  }

  // ---------------------------------------------------------------------------
  // Start
  // ---------------------------------------------------------------------------

  function start() {
    try {
      apply();
      watchShadowRoots();
    } catch (e) {
      console.error(`${LOG_PREFIX} Could not apply settings:`, e);
    }
    window.addEventListener("keydown", onKeyDown, true);
    if (window.RoseI18n && typeof window.RoseI18n.onChange === "function") {
      // Rebuild the panel in the new language
      window.RoseI18n.onChange(() => {
        if (!panel) return;
        const wasOpen = !panel.hidden;
        panel.remove();
        panel = null;
        if (wasOpen) togglePanel(true);
      });
    }
    console.log(`${LOG_PREFIX} Ready (Ctrl+Shift+M for settings)`, { ...settings });
  }

  window.RoseModernClient = Object.freeze({
    get settings() { return { ...settings }; },
    get shadowRoots() { return roots.size; },
    update,
    reset() { update({ ...DEFAULTS }); },
    open() { togglePanel(true); },
    close() { togglePanel(false); },
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
