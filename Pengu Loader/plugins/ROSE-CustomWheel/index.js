/**
 * @name ROSE-CustomWheel
 * @author Rose Team
 * @description Custom mod wheel for Pengu Loader - displays installed mods for hovered skins
 * @link https://github.com/Alban1911/ROSE-CustomWheel
 */
(function createCustomWheel() {
  const LOG_PREFIX = "[ROSE-CustomWheel]";
  console.log(`${LOG_PREFIX} JS Loaded`);

  const BUTTON_CLASS = "rose-custom-wheel-button";
  const BUTTON_SELECTOR = `.${BUTTON_CLASS}`;
  const PANEL_CLASS = "rose-custom-wheel-panel";
  const PANEL_ID = "rose-custom-wheel-panel-container";
  const REQUEST_TYPE = "request-skin-mods";
  const EVENT_SKIN_STATE = "lu-skin-monitor-state";

  let isOpen = false;
  let panel = null;
  let button = null;
  let championSelectRoot = null;
  let championSelectObserver = null;
  let championLocked = false;
  let currentSkinData = null;

  // --- Трекинг выбранных модов (апстрим) ---
  let selectedModId = null; // Track which mod is currently selected
  let selectedModSkinId = null; // Track which skin the selected mod belongs to
  // -----------------------------------------

  let pythonChromaState = null;
  let currentPhase = null;
  let selectionRequestCounter = 0;
  let skinModsRequestCounter = 0;
  let latestSkinModsRequestId = null;
  let lastSkinModsRequestKey = null;
  let lastSkinModsRequestAt = 0;
  let pendingSelectionRequest = null;
  let currentSkinMods = [];
  let activeTab = "skins"; 
  let selectedMapId = null;
  let selectedFontId = null;
  let selectedAnnouncerId = null;
  let isGlobalMode = false;

  let hideEmptyCategories = false;
  let selectedCategoryIds = Object.create(null);
  let isFirstOpenInSession = true; 
  
  // Кэши данных
  let lastCategoryModsById = {}; 
  let lastMapsList = null;
  let lastFontsList = null;
  let lastAnnouncersList = null;
  
  let emittedHistoricSelectionKeys = new Set(); 
  let rightPaneMode = "summary"; 

  let bridge = null;
  let isSwiftplayMode = false;

  function isActuallyInLobby() {
    const lobbyBanners = document.querySelector('.v2-banner-component.local-player');
    return !!(lobbyBanners && lobbyBanners.offsetParent !== null);
  }

  function isOverlayOpen() {
    if (isGlobalMode) return false;
    const overlays = [
      'lol-perks-v2-editor',           
      'lol-perks-v2-main-view',        
      '.perks-editor-modal',           
      'lol-uikit-full-page-modal'
    ];
    for (const selector of overlays) {
      const el = document.querySelector(selector);
      if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) return true;
    }
    return false;
  }

  const OTHER_CATEGORY_TABS = [
    { id: "ui", label: "UI", prefixes: ["ui/"] },
    { id: "voiceover", label: "Voiceover", prefixes: ["voiceover/", "vo/"] },
    { id: "loading_screen", label: "Loading Screen", prefixes: ["loading_screen/", "loading-screen/", "loading screen/"] },
    { id: "vfx", label: "VFX", prefixes: ["vfx/"] },
    { id: "sfx", label: "SFX", prefixes: ["sfx/"] },
    { id: "others", label: "Others", prefixes: [] },
  ];

  const SUMMARY_TABS = [
    { id: "skins", label: "Skins" },
    { id: "maps", label: "Maps" },
    { id: "fonts", label: "Fonts" },
    { id: "announcers", label: "Announcers" },
    ...OTHER_CATEGORY_TABS.map((t) => ({ id: t.id, label: t.label })),
  ];

  const SUMMARY_ICONS = {
    skins: '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    maps: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    fonts: '<svg viewBox="0 0 24 24"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>',
    announcers: '<svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
    ui: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>',
    voiceover: '<svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>',
    loading_screen: '<svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    vfx: '<svg viewBox="0 0 24 24"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/><path d="M19 13l.75 2.25L22 16l-2.25.75L19 19l-.75-2.25L16 16l2.25-.75L19 13z"/><path d="M5 17l.75 2.25L8 20l-2.25.75L5 23l-.75-2.25L2 20l2.25-.75L5 17z"/></svg>',
    sfx: '<svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
    others: '<svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
  };

  function waitForBridge() {
    return new Promise((resolve, reject) => {
      const timeout = 10000;
      const interval = 50;
      let elapsed = 0;
      const check = () => {
        if (window.__roseBridge) return resolve(window.__roseBridge);
        elapsed += interval;
        if (elapsed >= timeout) return reject(new Error("Bridge not available"));
        setTimeout(check, interval);
      };
      check();
    });
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') return String(str);
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function getSelectedIdsForCategory(categoryId) {
    const key = String(categoryId || "").trim();
    if (!key) return [];
    if (!Array.isArray(selectedCategoryIds[key])) {
      selectedCategoryIds[key] = [];
    }
    return selectedCategoryIds[key];
  }

  function getSelectedSummaryForTab(tabId) {
    if (tabId === "skins") {
      if (!championLocked && !(isSwiftplayMode && isActuallyInLobby())) return "Waiting for champ lock…";
      if (!isSelectedModForSkin()) return "None";
      return visibleNameForId(currentSkinMods, selectedModId, ["relativePath", "modName"]);
    }
    if (tabId === "maps") return selectedMapId ? visibleNameForId(lastMapsList, selectedMapId, ["id", "name"]) : "None";
    if (tabId === "fonts") return selectedFontId ? visibleNameForId(lastFontsList, selectedFontId, ["id", "name"]) : "None";
    if (tabId === "announcers") return selectedAnnouncerId ? visibleNameForId(lastAnnouncersList, selectedAnnouncerId, ["id", "name"]) : "None";

    const selected = getSelectedIdsForCategory(tabId);
    if (!selected.length) return "None";
    const items = lastCategoryModsById[tabId] || [];
    return selected.map((id) => visibleNameForId(items, id, ["id", "name", "modName"])).join(", ");
  }

  function cleanModName(raw) {
    if (!raw || typeof raw !== "string") return raw;
    let name = raw.replace(/\\/g, "/");
    const lastSlash = name.lastIndexOf("/");
    if (lastSlash >= 0) name = name.substring(lastSlash + 1);
    name = name.replace(/\.(fantome|wad|zip)$/i, "");
    name = name.replace(/[_\-]/g, " ");
    name = name.replace(/\b\w/g, (c) => c.toUpperCase());
    return name.trim() || raw;
  }

  function visibleModName(mod, fallback = "Unnamed mod") {
    const alias = typeof mod?.displayName === "string" ? mod.displayName.trim() : "";
    if (alias) return alias;
    return cleanModName(mod?.modName || mod?.name) || fallback;
  }

  function visibleNameForId(items, id, keys) {
    const wanted = String(id || "").replace(/\\/g, "/");
    const match = (items || []).find((item) =>
      keys.some((key) => String(item?.[key] || "").replace(/\\/g, "/") === wanted)
    );
    if (match) return visibleModName(match, cleanModName(wanted) || wanted);
    return cleanModName(wanted) || wanted;
  }

  function getTabLabel(tabId) {
    return SUMMARY_TABS.find((t) => t.id === tabId)?.label || String(tabId || "");
  }

  function tabHasInstalledMods(tabId) {
    if (tabId === "skins") return true;
    if (tabId === "maps") return Array.isArray(lastMapsList) && lastMapsList.length > 0;
    if (tabId === "fonts") return Array.isArray(lastFontsList) && lastFontsList.length > 0;
    if (tabId === "announcers") return Array.isArray(lastAnnouncersList) && lastAnnouncersList.length > 0;

    if (OTHER_CATEGORY_TABS.some((t) => t.id === tabId)) {
      if (!Object.prototype.hasOwnProperty.call(lastCategoryModsById, tabId)) return false;
      const mods = lastCategoryModsById[tabId];
      return Array.isArray(mods) && mods.length > 0;
    }
    return true;
  }

  function getVisibleSummaryTabs() {
    if (!hideEmptyCategories) return SUMMARY_TABS;
    return SUMMARY_TABS.filter((tab) => tab.id === "skins" || tabHasInstalledMods(tab.id));
  }

  function isSummaryTabVisible(tabId) {
    return getVisibleSummaryTabs().some((tab) => tab.id === tabId);
  }

  function ensureActiveTabVisible() {
    if (!isSummaryTabVisible(activeTab)) activeTab = "skins";
  }

  function syncActiveTabContent() {
    if (!panel) return;
    panel.querySelectorAll(".tab-content").forEach((content) => {
      if (content && content.dataset && content.dataset.tab === activeTab) {
        content.classList.add("active");
      } else if (content) {
        content.classList.remove("active");
      }
    });
  }

  function syncSummaryRowVisibility() {
    if (!panel || !panel._summaryRowsByTab) return;
    const visibleIds = new Set(getVisibleSummaryTabs().map((tab) => tab.id));
    for (const tab of SUMMARY_TABS) {
      const row = panel._summaryRowsByTab[tab.id];
      if (row) row.style.display = visibleIds.has(tab.id) ? "" : "none";
    }
  }

  function applyVisibleCategoryState() {
    syncSummaryRowVisibility();
    if (rightPaneMode === "picker" && !isSummaryTabVisible(activeTab)) {
      ensureActiveTabVisible();
      syncActiveTabContent();
      setRightPaneMode("picker");
    }
  }

  function refreshSummaryValues() {
    if (!panel || !panel._summaryValuesByTab) return;
    for (const tab of SUMMARY_TABS) {
      const el = panel._summaryValuesByTab[tab.id];
      const raw = getSelectedSummaryForTab(tab.id);
      if (el) el.textContent = raw;
      
      const row = panel._summaryRowsByTab && panel._summaryRowsByTab[tab.id];
      if (row) {
        if (raw !== "None" && raw !== "Waiting for champ lock…") row.classList.add("active");
        else row.classList.remove("active");
      }
    }
    syncSummaryRowVisibility();
    refreshButtonBadgeFromSelections();
  }

  function setRightPaneMode(mode) {
    if (mode === "picker") {
      ensureActiveTabVisible();
      syncActiveTabContent();
    }
    rightPaneMode = mode;
    if (!panel) return;

    if (panel._summaryView) panel._summaryView.style.display = mode === "summary" ? "flex" : "none";
    if (panel._pickerView) {
      if (mode === "picker") panel._pickerView.classList.add("active");
      else panel._pickerView.classList.remove("active");
    }
    if (panel._backBtn) panel._backBtn.style.display = mode === "picker" ? "inline-block" : "none";
    
    if (panel._rightTitle) {
      if (mode === "picker") {
        const icon = SUMMARY_ICONS[activeTab] || "";
        panel._rightTitle.innerHTML = `<span class="rose-wheel-title-icon">${icon}</span> Choose \u2022 ${escapeHtml(getTabLabel(activeTab))}`;
      } else {
        panel._rightTitle.textContent = "Custom Mods";
      }
    }
  }

  function getCurrentSkinContext() {
    const state = window.__roseSkinState || {};
    const championId = Number(state.championId);
    let skinId = Number(state.skinId);
    const selectedChromaId = Number(pythonChromaState?.selectedChromaId);
    const currentSkinId = Number(pythonChromaState?.currentSkinId);

    const chromaBelongsToChampion =
      Number.isFinite(selectedChromaId) && selectedChromaId > 0 &&
      Number.isFinite(championId) && championId > 0 &&
      Math.floor(selectedChromaId / 1000) === championId;
      
    const chromaContextMatches =
      !Number.isFinite(currentSkinId) || currentSkinId <= 0 ||
      Math.floor(currentSkinId / 1000) === championId;

    if (chromaBelongsToChampion && chromaContextMatches) {
      skinId = selectedChromaId;
    }

    return { championId, skinId };
  }

  function isSelectedModForSkin(skinId = getCurrentSkinContext().skinId) {
    const selectedSkinId = Number(selectedModSkinId);
    const currentSkinId = Number(skinId);
    return Boolean(selectedModId) &&
      Number.isFinite(selectedSkinId) &&
      Number.isFinite(currentSkinId) &&
      selectedSkinId === currentSkinId;
  }

  function handleChromaStateUpdate(data) {
    pythonChromaState = data && typeof data === "object" ? data : null;
    requestModsForCurrentSkin();
    if (isOpen && activeTab === "skins") refreshSummaryValues();
  }

  function resetStaleChromaStateForSkin(skinId) {
    if (!pythonChromaState) return;
    const incomingSkinId = Number(skinId);
    const selectedChromaId = Number(pythonChromaState.selectedChromaId);
    const currentSkinId = Number(pythonChromaState.currentSkinId);
    if (!Number.isFinite(incomingSkinId) || incomingSkinId <= 0) return;

    if (incomingSkinId !== selectedChromaId && incomingSkinId !== currentSkinId) {
      pythonChromaState = null;
    }
  }

  function resetCustomSkinSessionState() {
    pythonChromaState = null;
    selectedModId = null;
    selectedModSkinId = null;
    pendingSelectionRequest = null;
    latestSkinModsRequestId = null;
    currentSkinMods = [];
  }

  function handlePhaseChange(data) {
    const phase = String(data?.phase || "");
    const previousPhase = currentPhase;
    currentPhase = phase;

    if (phase === "ChampSelect" && previousPhase !== "ChampSelect") {
      resetCustomSkinSessionState();
    } else if (phase !== "ChampSelect" && previousPhase === "ChampSelect") {
      resetCustomSkinSessionState();
    }
  }

  function createSelectionRequestId() {
    selectionRequestCounter += 1;
    return `${LOG_PREFIX}-${Date.now()}-${selectionRequestCounter}`;
  }

  // ==== Стилизация ====
  function getPluginCSS() {
    const btn = BUTTON_CLASS;
    const pnl = PANEL_CLASS;
    return `
.${btn} {
  position: absolute !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  white-space: nowrap !important;
  min-width: 130px !important;
  height: 30px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  letter-spacing: 0.05em !important;
  text-transform: uppercase !important;
  background: #1e2328 !important;
  color: #cdbe91 !important;
  border: 1px solid #c8aa6e !important;
  transition: background 0.2s, color 0.2s !important;
  cursor: pointer !important;
  pointer-events: auto !important;
  font-family: "Beaufort for LOL", serif !important;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
  box-sizing: border-box;
  padding: 0 12px !important;
  z-index: 50 !important;
}
.${btn}:hover {
  background: #463714 !important;
  color: #f0e6d2 !important;
}
.${btn}:active {
  background: #1e2328 !important;
}
.${btn} .count-badge {
  position: absolute !important;
  top: -6px !important;
  right: -6px !important;
  left: auto !important;
  bottom: auto !important;
  transform: none !important;
  min-width: 18px !important;
  height: 18px !important;
  padding: 0 4px !important;
  background: #c89b3c !important;
  color: #010a13 !important;
  border: 1px solid #f0e6d2 !important;
  border-radius: 9px !important;
  font-size: 11px !important;
  font-weight: bold !important;
  display: none;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
  box-sizing: border-box !important;
  box-shadow: 0 2px 5px rgba(0,0,0,0.7) !important;
  z-index: 51 !important;
  pointer-events: none !important;
}

.${btn}[data-hidden], .${btn}[data-hidden] * {
  pointer-events: none !important; cursor: default !important; visibility: hidden !important;
}

.${pnl} { position: fixed; z-index: 10000; pointer-events: none; -webkit-user-select: none; font-family: "Spiegel", "LoL Body", Arial, sans-serif; }
.${pnl}[data-no-button] { pointer-events: none; cursor: default !important; }
.${pnl}[data-no-button] * { pointer-events: none !important; cursor: default !important; }
.${pnl} .flyout { position: fixed; overflow: visible; pointer-events: all; -webkit-user-select: none; width: auto !important; filter: drop-shadow(0 0 10px rgba(0,0,0,0.5)); }

.${pnl} .flyout .caret, .${pnl} .flyout [class*="caret"],
.${pnl} lol-uikit-flyout-frame .caret, .${pnl} lol-uikit-flyout-frame [class*="caret"],
.${pnl} .flyout::part(caret), .${pnl} lol-uikit-flyout-frame::part(caret) {
  display: none !important; visibility: hidden !important; content: none !important;
}

.${pnl} .chroma-modal {
  background: #010a13; border-radius: 2px; box-shadow: 0 0 20px rgba(0, 0, 0, 0.8);
  display: flex; flex-direction: column; width: 980px; max-width: calc(100vw - 80px); min-width: 720px;
  position: relative; z-index: 0; padding: 16px; box-sizing: border-box; overflow: hidden;
  color: #f0e6d2; height: 520px !important; min-height: 420px !important; max-height: calc(100vh - 120px) !important;
}

.${pnl} .rose-wheel-right-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding-bottom: 10px; border-bottom: 1px solid #3c3c41; margin-bottom: 10px; flex-shrink: 0;
}
.${pnl} .rose-wheel-right-title { font-weight: 700; color: #f0e6d2; font-size: 13px; display: flex; align-items: center; gap: 6px; }
.${pnl} .rose-wheel-right-title .rose-wheel-title-icon { width: 18px; height: 18px; flex-shrink: 0; }
.${pnl} .rose-wheel-right-title .rose-wheel-title-icon svg { width: 18px; height: 18px; fill: none; stroke: #c8aa6e; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

.${pnl} .rose-wheel-summary { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 6px; padding: 6px 2px; overflow-y: auto; }
.${pnl} .rose-wheel-summary::-webkit-scrollbar { width: 6px; }
.${pnl} .rose-wheel-summary::-webkit-scrollbar-track { background: rgba(0,0,0,0.3); }
.${pnl} .rose-wheel-summary::-webkit-scrollbar-thumb { background: #5b5a56; border-radius: 3px; }

.${pnl} .rose-wheel-summary-row {
  display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 12px; padding: 8px;
  border: 1px solid #3c3c41; border-left: 3px solid transparent;
  background: linear-gradient(to right, rgba(30, 35, 40, 0.8), rgba(30, 35, 40, 0.5)); cursor: pointer; transition: all 0.2s ease;
}
.${pnl} .rose-wheel-summary-row:hover { background: linear-gradient(to right, rgba(40, 45, 50, 0.9), rgba(40, 45, 50, 0.7)); border-color: #5c5c61; border-left-color: #c8aa6e; transform: translateX(2px); }
.${pnl} .rose-wheel-summary-row.active { border-left: 3px solid #c8aa6e; }

.${pnl} .rose-wheel-summary-icon { width: 18px; height: 18px; flex-shrink: 0; color: #5b5a56; transition: color 0.2s ease; }
.${pnl} .rose-wheel-summary-icon svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.${pnl} .rose-wheel-summary-left { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.${pnl} .rose-wheel-summary-label { color: #a09b8c; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.${pnl} .rose-wheel-summary-value { color: #f0e6d2; font-size: 13px; font-weight: 700; word-break: break-word; }

.${pnl} .rose-wheel-picker { flex: 1; min-height: 0; display: none; }
.${pnl} .rose-wheel-picker.active { display: flex; flex-direction: column; min-height: 0; }
.${pnl} .tab-content { display: none; width: 100%; background: transparent; }
.${pnl} .tab-content.active { display: flex; flex-direction: column; height: 100%; }

.${pnl} .mod-selection { pointer-events: all; flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px; margin-top: 4px; }
.${pnl} .mod-selection::-webkit-scrollbar { width: 6px; }
.${pnl} .mod-selection::-webkit-scrollbar-track { background: rgba(0,0,0,0.3); }
.${pnl} .mod-selection::-webkit-scrollbar-thumb { background: #5b5a56; border-radius: 3px; }

.${pnl} .mod-selection ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.${pnl} .mod-selection li {
  background: linear-gradient(to right, rgba(30, 35, 40, 0.9), rgba(30, 35, 40, 0.6));
  border: 1px solid #3c3c41; border-left: 3px solid transparent; padding: 10px; transition: all 0.2s ease;
  display: flex; flex-direction: column; gap: 4px; cursor: pointer;
}
.${pnl} .mod-selection li:hover { background: linear-gradient(to right, rgba(40, 45, 50, 0.9), rgba(40, 45, 50, 0.7)); border-color: #5c5c61; border-left-color: #c8aa6e; transform: translateX(2px); }
.${pnl} .mod-selection li.selected-row { border-left-color: #c8aa6e; background: linear-gradient(to right, rgba(200, 170, 110, 0.12), rgba(30, 35, 40, 0.6)); }

.${pnl} .mod-name-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; }
.${pnl} .mod-name { color: #f0e6d2; font-size: 13px; font-weight: 700; letter-spacing: 0.5px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.${pnl} .mod-name.none-label { font-style: italic; color: #8b8b8b; }
.${pnl} .mod-description { color: #a09b8c; font-size: 11px; font-weight: 400; line-height: 1.4; word-wrap: break-word; }

.${pnl} .rose-wheel-back-button, .${pnl} .mod-select-button {
  background: transparent !important; border: 1px solid #c8aa6e !important; color: #c8aa6e !important;
  cursor: pointer !important; transition: all 0.2s ease !important; flex-shrink: 0 !important;
  border-radius: 0 !important; display: flex !important; align-items: center !important; justify-content: center !important; outline: none !important;
}
.${pnl} .rose-wheel-back-button { padding: 4px 10px !important; font-size: 11px !important; font-weight: 700 !important; text-transform: uppercase !important; }
.${pnl} .mod-select-button { width: 26px !important; height: 26px !important; font-size: 20px !important; padding: 0 !important; line-height: 1 !important; }
.${pnl} .rose-wheel-back-button:hover, .${pnl} .mod-select-button:hover {
  background: rgba(200, 170, 110, 0.15) !important; box-shadow: 0 0 8px rgba(200, 170, 110, 0.3) !important; color: #f0e6d2 !important; border-color: #f0e6d2 !important;
}
`;
  }

  function injectCSS() {
    const styleId = "rose-custom-wheel-css";
    if (document.getElementById(styleId)) return;
    const styleTag = document.createElement("style");
    styleTag.id = styleId;
    styleTag.textContent = getPluginCSS();
    document.head.appendChild(styleTag);
  }

  function createButton() {
    if (button) return button;
    button = document.createElement("button");
    button.className = BUTTON_CLASS;
    button.textContent = "Custom Mods";

    const countBadge = document.createElement("div");
    countBadge.className = "count-badge";
    countBadge.textContent = "0";
    button.appendChild(countBadge);
    button._countBadge = countBadge;

    button.addEventListener("click", (e) => {
      e.stopPropagation(); 
      e.preventDefault();
      if (isOpen) { closePanel(); } else { togglePanel(); }
    });
    return button;
  }

  function updateButtonVisibility(btn, shouldShow) {
    if (!btn) return;
    if (shouldShow) {
      btn.style.setProperty("display", "flex", "important");
      btn.style.visibility = "visible"; 
      btn.style.pointerEvents = "auto"; 
      btn.style.opacity = "1";
      btn.removeAttribute("data-hidden");
    } else {
      btn.style.setProperty("display", "none", "important");
      btn.style.visibility = "hidden"; 
      btn.style.pointerEvents = "none"; 
      btn.style.opacity = "0";
      btn.setAttribute("data-hidden", "true");
      if (panel && panel.parentNode && !isGlobalMode) closePanel();
    }
  }

  function sendDeselect(expectedModId = selectedModId) {
    const { championId, skinId } = getCurrentSkinContext();
    if (!bridge || !championId || !skinId) return;
    const requestId = createSelectionRequestId();
    pendingSelectionRequest = { requestId, operation: "deselect" };
    bridge.send({ type: "select-skin-mod", championId, skinId, modId: null, expectedModId, requestId });
  }

  function sendSelect(modId, modData) {
    const { championId, skinId } = getCurrentSkinContext();
    if (!bridge || !championId || !skinId) return;
    const requestId = createSelectionRequestId();
    pendingSelectionRequest = { requestId, operation: "select", modId };
    bridge.send({ type: "select-skin-mod", championId, skinId, modId, modData, requestId });
  }

  function requestModsForCurrentSkin() {
    if (!bridge) return;
    const { championId, skinId } = getCurrentSkinContext();
    if (!championLocked && !(isSwiftplayMode && isActuallyInLobby())) {
      currentSkinMods = []; return;
    }
    const requestKey = `${championId}:${skinId}`;
    const now = Date.now();
    if (requestKey === lastSkinModsRequestKey && now - lastSkinModsRequestAt < 750) return;
    lastSkinModsRequestKey = requestKey; lastSkinModsRequestAt = now;
    
    bridge.send({ type: REQUEST_TYPE, championId, skinId, requestId: createSelectionRequestId() });
  }

  function handleModSelect(modId, listItem, modData) {
    if (selectedModId === modId && isSelectedModForSkin(getCurrentSkinContext().skinId)) {
      sendDeselect();
      listItem.classList.remove("selected-row");
    } else {
      sendSelect(modId, modData);
      const allItems = listItem.parentElement.querySelectorAll("li");
      allItems.forEach(i => i.classList.remove("selected-row"));
      listItem.classList.add("selected-row");
    }
    updateNoneRow(panel?._modList, !selectedModId);
    refreshSummaryValues();
    refreshButtonBadgeFromSelections();
  }

  function updateModEntries(mods) {
    if (!panel || !panel._modList) return;
    const listEl = panel._modList;
    listEl.innerHTML = "";

    const loadingEl = panel._modsLoading;
    if (!mods || mods.length === 0) {
      if (loadingEl) { loadingEl.textContent = "No skins found"; loadingEl.style.display = "block"; }
      return;
    }
    if (loadingEl) loadingEl.style.display = "none";

    const noneLi = document.createElement("li");
    noneLi.setAttribute("data-mod-id", "__none__");
    const noneRow = document.createElement("div"); noneRow.className = "mod-name-row";
    const noneName = document.createElement("div"); noneName.className = "mod-name none-label"; noneName.textContent = "None";
    noneRow.appendChild(noneName);
    if (!selectedModId) noneLi.classList.add("selected-row");
    noneLi.addEventListener("click", () => {
      if (selectedModId) sendDeselect();
      const allLis = listEl.querySelectorAll("li");
      allLis.forEach(l => l.classList.remove("selected-row"));
      noneLi.classList.add("selected-row");
      refreshSummaryValues(); refreshButtonBadgeFromSelections();
    });
    noneLi.appendChild(noneRow); listEl.appendChild(noneLi);

    mods.forEach(mod => {
      const li = document.createElement("li");
      const modId = mod.relativePath || mod.modName || `mod-${Date.now()}`;
      li.setAttribute("data-mod-id", modId);
      
      const row = document.createElement("div"); row.className = "mod-name-row";
      const name = document.createElement("div"); name.className = "mod-name"; name.textContent = visibleModName(mod);
      row.appendChild(name);
      li.appendChild(row);

      if (mod.description) {
        const desc = document.createElement("div"); desc.className = "mod-description"; desc.textContent = mod.description;
        li.appendChild(desc);
      }

      if (selectedModId === modId && isSelectedModForSkin(getCurrentSkinContext().skinId)) {
        li.classList.add("selected-row");
      }

      li.addEventListener("click", () => handleModSelect(modId, li, mod));
      listEl.appendChild(li);
    });
  }

  // --- Единый универсальный рендерер списков для Карт, Шрифтов, Дикторов и др. ---
  function updateCategoryEntries(categoryId, items) {
    if (!panel) return;
    const listEl = (categoryId === "maps") ? panel._mapsList :
                   (categoryId === "fonts") ? panel._fontsList :
                   (categoryId === "announcers") ? panel._announcersList :
                   panel[`_${categoryId}List`];
                   
    const loadingEl = (categoryId === "maps") ? panel._mapsLoading :
                      (categoryId === "fonts") ? panel._fontsLoading :
                      (categoryId === "announcers") ? panel._announcersLoading :
                      panel[`_${categoryId}Loading`];
                      
    if (!listEl || !loadingEl) return;

    listEl.innerHTML = "";
    const isSingleSelect = (categoryId === "maps" || categoryId === "fonts" || categoryId === "announcers");
    
    let selectedIds = isSingleSelect ? [] : getSelectedIdsForCategory(categoryId);
    let selectedSingleId = (categoryId === "maps") ? selectedMapId :
                           (categoryId === "fonts") ? selectedFontId :
                           (categoryId === "announcers") ? selectedAnnouncerId : null;

    if (!items || items.length === 0) {
      const label = getTabLabel(categoryId);
      loadingEl.textContent = `No ${label.toLowerCase()} found`;
      loadingEl.style.display = "block";
      return;
    }

    loadingEl.style.display = "none";

    // Опция "None"
    {
      const noneItem = document.createElement("li");
      noneItem.setAttribute("data-item-id", "__none__");
      const noneRow = document.createElement("div"); noneRow.className = "mod-name-row";
      const noneName = document.createElement("div"); noneName.className = "mod-name none-label"; noneName.textContent = "None";
      noneRow.appendChild(noneName);

      const isNoneActive = isSingleSelect ? !selectedSingleId : (selectedIds.length === 0);
      if (isNoneActive) noneItem.classList.add("selected-row");

      noneItem.addEventListener("click", () => {
        if (isSingleSelect) {
          if (categoryId === "maps") {
            selectedMapId = null;
            if (bridge) bridge.send({ type: "select-map", mapId: null });
          } else if (categoryId === "fonts") {
            selectedFontId = null;
            if (bridge) bridge.send({ type: "select-font", fontId: null });
          } else if (categoryId === "announcers") {
            selectedAnnouncerId = null;
            if (bridge) bridge.send({ type: "select-announcer", announcerId: null });
          }
        } else {
          const ids = getSelectedIdsForCategory(categoryId);
          for (const id of [...ids]) {
            if (bridge) bridge.send({ type: "select-other", category: categoryId, otherId: id, otherData: null, action: "deselect" });
          }
          ids.length = 0;
        }

        const allLis = listEl.querySelectorAll("li");
        allLis.forEach(l => l.classList.remove("selected-row"));
        noneItem.classList.add("selected-row");

        refreshSummaryValues();
        refreshButtonBadgeFromSelections();
      });

      noneItem.appendChild(noneRow);
      listEl.appendChild(noneItem);
    }

    items.forEach((item) => {
      const listItem = document.createElement("li");
      const itemId = item.id || item.relativePath || item.name || `item-${Date.now()}-${Math.random()}`;

      const nameRow = document.createElement("div"); nameRow.className = "mod-name-row";
      const nameEl = document.createElement("div"); nameEl.className = "mod-name";
      nameEl.textContent = visibleModName(item);
      nameRow.appendChild(nameEl);

      listItem.setAttribute("data-item-id", itemId);

      const isSelected = isSingleSelect ? (selectedSingleId === itemId) : selectedIds.includes(itemId);
      if (isSelected) {
        listItem.classList.add("selected-row");
      }

      listItem.addEventListener("click", () => {
        if (isSingleSelect) {
          if (selectedSingleId === itemId) {
            if (categoryId === "maps") { selectedMapId = null; if (bridge) bridge.send({ type: "select-map", mapId: null }); }
            else if (categoryId === "fonts") { selectedFontId = null; if (bridge) bridge.send({ type: "select-font", fontId: null }); }
            else if (categoryId === "announcers") { selectedAnnouncerId = null; if (bridge) bridge.send({ type: "select-announcer", announcerId: null }); }
            listItem.classList.remove("selected-row");
          } else {
            if (categoryId === "maps") { selectedMapId = itemId; if (bridge) bridge.send({ type: "select-map", mapId: itemId, mapData: item }); }
            else if (categoryId === "fonts") { selectedFontId = itemId; if (bridge) bridge.send({ type: "select-font", fontId: itemId, fontData: item }); }
            else if (categoryId === "announcers") { selectedAnnouncerId = itemId; if (bridge) bridge.send({ type: "select-announcer", announcerId: itemId, announcerData: item }); }
            
            const allLis = listEl.querySelectorAll("li");
            allLis.forEach(l => l.classList.remove("selected-row"));
            listItem.classList.add("selected-row");
          }
          updateNoneRow(listEl, !(categoryId === "maps" ? selectedMapId : categoryId === "fonts" ? selectedFontId : selectedAnnouncerId));
        } else {
          handleCategoryModSelect(categoryId, itemId, listItem, item);
        }

        refreshSummaryValues();
        refreshButtonBadgeFromSelections();
      });

      listItem.appendChild(nameRow);

      if (item.description) {
        const desc = document.createElement("div"); desc.className = "mod-description"; desc.textContent = item.description;
        listItem.appendChild(desc);
      }

      listEl.appendChild(listItem);
    });
  }

  function updateMapsEntries(items) { updateCategoryEntries("maps", items); }
  function updateFontsEntries(items) { updateCategoryEntries("fonts", items); }
  function updateAnnouncersEntries(items) { updateCategoryEntries("announcers", items); }
  function updateOtherCategoryEntries(categoryId, items) { updateCategoryEntries(categoryId, items); }

  function handleCategoryModSelect(categoryId, otherId, listItem, otherData) {
    const selectedIds = getSelectedIdsForCategory(categoryId);
    const index = selectedIds.indexOf(otherId);
    if (index !== -1) {
      selectedIds.splice(index, 1);
      listItem.classList.remove("selected-row");
      if (bridge) bridge.send({ type: "select-other", category: categoryId, otherId, otherData, action: "deselect" });
    } else {
      selectedIds.push(otherId);
      listItem.classList.add("selected-row");
      if (bridge) bridge.send({ type: "select-other", category: categoryId, otherId, otherData, action: "select" });
    }

    const listEl = panel?.[`_${categoryId}List`];
    updateNoneRow(listEl, selectedIds.length === 0);
    refreshSummaryValues();
    refreshButtonBadgeFromSelections();
    applyVisibleCategoryState();
  }

  function updateNoneRow(listEl, isNoneActive) {
    const noneLi = listEl?.querySelector('[data-item-id="__none__"], [data-mod-id="__none__"]');
    if (!noneLi) return;
    if (isNoneActive) noneLi.classList.add("selected-row");
    else noneLi.classList.remove("selected-row");
  }

  function createPanel() {
    if (panel) return panel;
    const existing = document.getElementById(PANEL_ID);
    if (existing) existing.remove();

    panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.className = PANEL_CLASS;
    panel.style.display = "none";
    
    let flyout;
    try { flyout = document.createElement("lol-uikit-flyout-frame"); flyout.className = "flyout"; flyout.setAttribute("show", "true"); }
    catch { flyout = document.createElement("div"); flyout.className = "flyout"; }
    
    let content;
    try { content = document.createElement("lc-flyout-content"); }
    catch { content = document.createElement("div"); content.className = "lc-flyout-content"; }

    const modal = document.createElement("div"); modal.className = "chroma-modal rose-custom-wheel-modal";
    
    // Header
    const header = document.createElement("div"); header.className = "rose-wheel-right-header";
    const title = document.createElement("div"); title.className = "rose-wheel-right-title"; title.textContent = "Custom Mods";
    const headerBtns = document.createElement("div"); headerBtns.style.display="flex"; headerBtns.style.gap="12px";
    
    const backBtn = document.createElement("button"); backBtn.className="rose-wheel-back-button"; backBtn.textContent="Back"; backBtn.style.display="none";
    backBtn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); setRightPaneMode("summary"); refreshSummaryValues(); });
    
    const closeBtn = document.createElement("button"); closeBtn.innerHTML="&times;"; 
    closeBtn.style.cssText = "background:transparent;border:none;color:#a09b8c;font-size:24px;cursor:pointer;line-height:0.5;padding:0;";
    closeBtn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); closePanel(); });
    
    headerBtns.appendChild(backBtn); headerBtns.appendChild(closeBtn);
    header.appendChild(title); header.appendChild(headerBtns);

    // Summary View (Категории)
    const summaryView = document.createElement("div"); summaryView.className = "rose-wheel-summary";
    panel._summaryValuesByTab = {}; panel._summaryRowsByTab = {};

    SUMMARY_TABS.forEach(tab => {
      const row = document.createElement("div"); row.className = "rose-wheel-summary-row";
      const left = document.createElement("div"); left.className = "rose-wheel-summary-left";
      const label = document.createElement("div"); label.className = "rose-wheel-summary-label";
      
      const iconSpan = document.createElement("span"); iconSpan.className = "rose-wheel-summary-icon"; iconSpan.innerHTML = SUMMARY_ICONS[tab.id] || "";
      const labelText = document.createElement("span"); labelText.textContent = tab.label;
      label.appendChild(iconSpan); label.appendChild(labelText);
      
      const value = document.createElement("div"); value.className = "rose-wheel-summary-value"; value.textContent = "None";
      panel._summaryValuesByTab[tab.id] = value;
      left.appendChild(label); left.appendChild(value);

      const btnContainer = document.createElement("div");
      const addBtn = document.createElement("button"); addBtn.className="mod-select-button"; addBtn.textContent="+";
      
      const switchTab = (tabName) => {
        if (!isSummaryTabVisible(tabName)) tabName = "skins";
        activeTab = tabName;
        syncActiveTabContent();
        
        if (tabName === "skins") {
          if (currentSkinMods && currentSkinMods.length) updateModEntries(currentSkinMods);
          requestModsForCurrentSkin();
        } else if (tabName === "maps") {
          if (lastMapsList && lastMapsList.length) updateMapsEntries(lastMapsList);
          requestMaps();
        } else if (tabName === "fonts") {
          if (lastFontsList && lastFontsList.length) updateFontsEntries(lastFontsList);
          requestFonts();
        } else if (tabName === "announcers") {
          if (lastAnnouncersList && lastAnnouncersList.length) updateAnnouncersEntries(lastAnnouncersList);
          requestAnnouncers();
        } else if (OTHER_CATEGORY_TABS.some(t => t.id === tabName)) {
          if (lastCategoryModsById[tabName] && lastCategoryModsById[tabName].length) {
            updateOtherCategoryEntries(tabName, lastCategoryModsById[tabName]);
          }
          requestCategoryMods(tabName);
        }
        
        if (rightPaneMode === "picker") {
          const icon = SUMMARY_ICONS[activeTab] || "";
          panel._rightTitle.innerHTML = `<span class="rose-wheel-title-icon">${icon}</span> Choose \u2022 ${escapeHtml(getTabLabel(activeTab))}`;
        }
      };

      addBtn.addEventListener("click", (e) => { 
        e.stopPropagation(); 
        if (tab.id === "skins") {
          openChampionSelection();
        } else {
          if (bridge) bridge.send({ type: "add-custom-mods-category-selected", category: tab.id });
        }
      });
      row.addEventListener("click", (e) => { if(e.target !== addBtn) { switchTab(tab.id); setRightPaneMode("picker"); } });
      
      btnContainer.appendChild(addBtn); row.appendChild(left); row.appendChild(btnContainer);
      panel._summaryRowsByTab[tab.id] = row; summaryView.appendChild(row);
    });

    // Picker View
    const pickerView = document.createElement("div"); pickerView.className = "rose-wheel-picker";
    const scrollable = document.createElement("div"); scrollable.className = "mod-selection";

    const createList = () => { const ul = document.createElement("ul"); ul.style.cssText="list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px;"; return ul; };
    const createLoad = (txt) => { const div = document.createElement("div"); div.className="mod-loading"; div.textContent=txt; div.style.display="none"; return div; };
    const createContent = (id) => { const div = document.createElement("div"); div.className="tab-content"; div.dataset.tab=id; return div; };

    panel._modList = createList(); panel._mapsList = createList(); panel._fontsList = createList(); panel._announcersList = createList();
    panel._modsLoading = createLoad("Waiting for mods..."); panel._mapsLoading = createLoad("Loading maps..."); panel._fontsLoading = createLoad("Loading fonts..."); panel._announcersLoading = createLoad("Loading announcers...");
    
    const modsContent = createContent("skins"); modsContent.classList.add("active"); modsContent.appendChild(panel._modsLoading); modsContent.appendChild(panel._modList);
    const mapsContent = createContent("maps"); mapsContent.appendChild(panel._mapsLoading); mapsContent.appendChild(panel._mapsList);
    const fontsContent = createContent("fonts"); fontsContent.appendChild(panel._fontsLoading); fontsContent.appendChild(panel._fontsList);
    const announcersContent = createContent("announcers"); announcersContent.appendChild(panel._announcersLoading); announcersContent.appendChild(panel._announcersList);
    
    scrollable.appendChild(modsContent); scrollable.appendChild(mapsContent); scrollable.appendChild(fontsContent); scrollable.appendChild(announcersContent);

    OTHER_CATEGORY_TABS.forEach(t => {
      const lst = createList(); const ld = createLoad(`Loading ${t.label.toLowerCase()}...`); const cnt = createContent(t.id);
      cnt.appendChild(ld); cnt.appendChild(lst); scrollable.appendChild(cnt);
      panel[`_${t.id}List`] = lst; panel[`_${t.id}Loading`] = ld; panel[`_${t.id}Content`] = cnt;
    });

    pickerView.appendChild(scrollable);
    
    panel._summaryView = summaryView; panel._pickerView = pickerView; panel._backBtn = backBtn; panel._rightTitle = title;
    modal.appendChild(header); modal.appendChild(summaryView); modal.appendChild(pickerView);
    content.appendChild(modal); flyout.appendChild(content); panel.appendChild(flyout);

    setRightPaneMode("summary");
    document.body.appendChild(panel);
    return panel;
  }

  function positionPanel(panelElement) {
    if (!panelElement) return;
    const flyout = panelElement.querySelector(".flyout");
    if (!flyout) return;

    let flyoutRect = flyout.getBoundingClientRect();
    if (!flyoutRect.width) flyoutRect = { width: 980, height: 520 };

    const cx = (window.innerWidth - flyoutRect.width) / 2;
    const cy = (window.innerHeight - flyoutRect.height) / 2;

    flyout.style.position = "fixed";
    flyout.style.top = `${Math.max(10, cy)}px`;
    flyout.style.left = `${Math.max(10, cx)}px`;
  }

  function togglePanel() {
    if (document.getElementById(PANEL_ID) && isOpen) { closePanel(); return; }
    closePanel();
    
    if (!panel) createPanel();
    panel.style.display = "block";
    isOpen = true;
    
    if (isFirstOpenInSession) { activeTab = "skins"; isFirstOpenInSession = false; }
    setRightPaneMode("summary");
    refreshSummaryValues();
    
    requestModsForCurrentSkin(); requestMaps(); requestFonts(); requestAnnouncers();
    OTHER_CATEGORY_TABS.forEach(t => requestCategoryMods(t.id));

    positionPanel(panel);
    
    setTimeout(() => {
      const closeHandler = (e) => {
        const flyout = panel ? panel.querySelector(".flyout") : null;
        if (!panel || !panel.parentNode) { document.removeEventListener("click", closeHandler); return; }
        if ((flyout && flyout.contains(e.target)) || (button && button.contains(e.target))) return;
        closePanel(); document.removeEventListener("click", closeHandler);
      };
      document.addEventListener("click", closeHandler);
    }, 200);
  }

  function closePanel() {
    if (panel) panel.style.display = "none";
    isOpen = false;
    isGlobalMode = false;
  }

  function requestMaps() { if (bridge) bridge.send({ type: "request-maps" }); }
  function requestFonts() { if (bridge) bridge.send({ type: "request-fonts" }); }
  function requestAnnouncers() { if (bridge) bridge.send({ type: "request-announcers" }); }
  function requestCategoryMods(cat) { if (bridge) bridge.send({ type: "request-category-mods", category: cat }); }

  function handleMapsResponse(data) {
    const detail = data?.detail || data;
    if (!detail || detail.type !== "maps-response") return;
    lastMapsList = Array.isArray(detail.maps) ? detail.maps : [];
    if (detail.historicMod && !selectedMapId) {
      const hm = lastMapsList.find(m => (m.id||"").replace(/\\/g,"/") === String(detail.historicMod).replace(/\\/g,"/"));
      if (hm) selectedMapId = hm.id || hm.name;
    }
    refreshSummaryValues();
    if (isOpen && rightPaneMode === "picker" && activeTab === "maps") updateMapsEntries(lastMapsList);
  }

  function handleFontsResponse(data) {
    const detail = data?.detail || data;
    if (!detail || detail.type !== "fonts-response") return;
    lastFontsList = Array.isArray(detail.fonts) ? detail.fonts : [];
    if (detail.historicMod && !selectedFontId) {
      const hf = lastFontsList.find(f => (f.id||"").replace(/\\/g,"/") === String(detail.historicMod).replace(/\\/g,"/"));
      if (hf) selectedFontId = hf.id || hf.name;
    }
    refreshSummaryValues();
    if (isOpen && rightPaneMode === "picker" && activeTab === "fonts") updateFontsEntries(lastFontsList);
  }

  function handleAnnouncersResponse(data) {
    const detail = data?.detail || data;
    if (!detail || detail.type !== "announcers-response") return;
    lastAnnouncersList = Array.isArray(detail.announcers) ? detail.announcers : [];
    if (detail.historicMod && !selectedAnnouncerId) {
      const ha = lastAnnouncersList.find(a => (a.id||"").replace(/\\/g,"/") === String(detail.historicMod).replace(/\\/g,"/"));
      if (ha) selectedAnnouncerId = ha.id || ha.name;
    }
    refreshSummaryValues();
    if (isOpen && rightPaneMode === "picker" && activeTab === "announcers") updateAnnouncersEntries(lastAnnouncersList);
  }

  function handleCategoryModsResponse(data) {
    const detail = data?.detail || data;
    if (!detail || detail.type !== "category-mods-response") return;

    const category = String(detail.category || "").trim();
    if (!OTHER_CATEGORY_TABS.some((t) => t.id === category)) return;

    const modsList = Array.isArray(detail.mods) ? detail.mods : [];
    lastCategoryModsById[category] = modsList;

    const historicMod = detail.historicMod;
    const historicMods = Array.isArray(historicMod) ? historicMod : (historicMod ? [historicMod] : []);
    if (historicMods.length > 0) {
      for (const historicPath of historicMods) {
        const match = modsList.find((m) => {
          const id = (m?.id || "").replace(/\\/g, "/");
          return id === String(historicPath).replace(/\\/g, "/");
        });
        if (!match) continue;
        const otherId = match.id || match.name || `other-${Date.now()}-${Math.random()}`;
        const selectedIds = getSelectedIdsForCategory(category);
        if (!selectedIds.includes(otherId)) {
          selectedIds.push(otherId);
          const key = `${category}:${otherId}`;
          if (!emittedHistoricSelectionKeys.has(key)) {
            emittedHistoricSelectionKeys.add(key);
            if (bridge) bridge.send({ type: "select-other", category, otherId, otherData: match, action: "select" });
          }
        }
      }
    }

    refreshSummaryValues();
    refreshButtonBadgeFromSelections();
    applyVisibleCategoryState();

    if (!isOpen || rightPaneMode !== "picker" || activeTab !== category) return;
    updateOtherCategoryEntries(category, modsList);
  }

  function handleOthersResponse(data) {
    const detail = data?.detail || data;
    if (!detail || detail.type !== "others-response") return;

    const othersList = Array.isArray(detail.others) ? detail.others : [];
    lastCategoryModsById["others"] = othersList;

    const historicMod = detail.historicMod;
    const historicMods = Array.isArray(historicMod) ? historicMod : (historicMod ? [historicMod] : []);
    
    const selectedIds = getSelectedIdsForCategory("others");
    if (historicMods.length > 0 && selectedIds.length === 0) {
      for (const historicPath of historicMods) {
        const historicOther = othersList.find(other => {
          const otherId = other.id || "";
          return otherId.replace(/\\/g, "/") === String(historicPath).replace(/\\/g, "/");
        });
        if (historicOther) {
          const otherId = historicOther.id || historicOther.name || `other-${Date.now()}-${Math.random()}`;
          if (!selectedIds.includes(otherId)) {
            selectedIds.push(otherId);
            const key = `others:${otherId}`;
            if (!emittedHistoricSelectionKeys.has(key)) {
              emittedHistoricSelectionKeys.add(key);
              if (bridge) bridge.send({ type: "select-other", category: "others", otherId, otherData: historicOther, action: "select" });
            }
          }
        }
      }
    }

    refreshSummaryValues();
    refreshButtonBadgeFromSelections();

    if (!isOpen || rightPaneMode !== "picker" || activeTab !== "others") return;
    updateOtherCategoryEntries("others", othersList);
  }

  function handleSkinState(e) {
    skinMonitorState = e?.detail || null;
    resetStaleChromaStateForSkin(skinMonitorState?.skinId);
    requestModsForCurrentSkin();
  }

  // --- Безопасная привязка кнопки над панелью выхода ---
  function attachToChampionSelect() {
    if (!button) createButton();
    if (!panel) createPanel();

    const inCS = !!document.querySelector(".champion-select");
    const inLobby = isActuallyInLobby();

    if (inCS) {
      const csRoot = document.querySelector(".champion-select");
      if (csRoot && button.parentNode !== csRoot) {
        csRoot.appendChild(button);
      }
      // Размещаем кнопку НАД контролами выхода (bottom: 75px, right: 25px)
      button.style.position = "absolute";
      button.style.right = "25px";
      button.style.bottom = "75px";
      button.style.left = "auto";
      button.style.top = "auto";
      button.style.zIndex = "50";
    } else if (inLobby && isSwiftplayMode) {
      if (button.parentNode !== document.body) document.body.appendChild(button);
      button.style.position = "fixed";
      button.style.bottom = "210px";
      button.style.right = "225px";
      button.style.left = "auto";
      button.style.top = "auto";
      button.style.zIndex = "50";
    }
  }

  function updateChampionSelectTarget() {
    const t = document.querySelector(".champion-select");
    const il = isActuallyInLobby();
    if (!t && !il) { championSelectRoot = null; if (button?.parentNode) button.remove(); if (!isGlobalMode) closePanel(); return; }
    if (t && t !== championSelectRoot) { championSelectRoot = t; isFirstOpenInSession = true; }
    else if (il && isSwiftplayMode && championSelectRoot !== "swiftplay") { championSelectRoot = "swiftplay"; isFirstOpenInSession = true; }
    attachToChampionSelect();
  }

  function updateButtonBadge(count) {
    if (!button || !button._countBadge) return;
    const badge = button._countBadge;
    if (count > 0) {
      badge.textContent = String(count);
      badge.style.setProperty("display", "flex", "important");
    } else {
      badge.textContent = "0"; 
      badge.style.setProperty("display", "none", "important");
    }
  }

  function getSelectedModsCount() {
    let count = 0;
    const inLobby = isActuallyInLobby();
    if ((championLocked || (isSwiftplayMode && inLobby)) && selectedModId) count += 1;
    if (selectedMapId) count += 1;
    if (selectedFontId) count += 1;
    if (selectedAnnouncerId) count += 1;
    for (const t of OTHER_CATEGORY_TABS) {
      const ids = getSelectedIdsForCategory(t.id);
      if (Array.isArray(ids) && ids.length) {
        count += new Set(ids).size;
      }
    }
    return count;
  }

  function refreshButtonBadgeFromSelections() {
    updateButtonBadge(getSelectedModsCount());
  }

  // --- Модальные окна с z-index 20000+ (открываются поверх CustomWheel) ---
  function openChampionSelection() {
    const existingDialog = document.getElementById("champion-selection-dialog");
    if (existingDialog) existingDialog.remove();

    const dialog = document.createElement("div");
    dialog.id = "champion-selection-dialog";
    dialog.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:20000 !important;background:rgba(0,0,0,0.65);display:flex;align-items:center;justify-content:center;pointer-events:all;";
    dialog.addEventListener("click", (e) => { if (e.target === dialog) closeChampionSelection(); });
    document.body.appendChild(dialog);

    const flyoutFrame = document.createElement("div");
    flyoutFrame.style.cssText = "max-height:75vh;width:700px;overflow:hidden;background:#010a13;border:1px solid #c8aa6e;padding:20px;box-sizing:border-box;font-family:'Beaufort for LOL',serif;color:#cdbe91;";
    flyoutFrame.addEventListener("click", (e) => e.stopPropagation());

    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;";
    
    const titleWrapper = document.createElement("div");
    titleWrapper.style.cssText = "font-size:18px;font-weight:bold;color:#c8aa6e;";
    titleWrapper.textContent = "Select Champion";
    header.appendChild(titleWrapper);

    const closeBtn = document.createElement("button");
    closeBtn.innerHTML = "&times;";
    closeBtn.style.cssText = "background:transparent;border:none;color:#a09b8c;font-size:24px;cursor:pointer;";
    closeBtn.addEventListener("click", closeChampionSelection);
    header.appendChild(closeBtn);
    flyoutFrame.appendChild(header);

    const searchInput = document.createElement("input");
    searchInput.type = "search";
    searchInput.placeholder = "Search champions...";
    searchInput.style.cssText = "width:100%;padding:8px;background:#1e2328;border:1px solid #5c5b56;color:#cdbe91;box-sizing:border-box;margin-bottom:12px;outline:none;";
    flyoutFrame.appendChild(searchInput);

    const loading = document.createElement("div");
    loading.id = "champion-loading";
    loading.textContent = "Loading champions...";
    loading.style.cssText = "color:#cdbe91;text-align:center;padding:20px;";
    flyoutFrame.appendChild(loading);

    const championsGrid = document.createElement("div");
    championsGrid.id = "champions-grid";
    championsGrid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:8px;max-height:45vh;overflow-y:auto;";
    flyoutFrame.appendChild(championsGrid);

    dialog.appendChild(flyoutFrame);

    if (bridge) bridge.send({ type: "add-custom-mods-champion-selected", action: "list" });

    searchInput.addEventListener("input", (e) => {
      const term = e.target.value.toLowerCase().trim();
      const all = window.__roseAllChampions || [];
      renderChampionsGrid(all.filter(c => c.name.toLowerCase().includes(term)));
    });

    window.__roseChampionRenderer = renderChampionsGrid;
  }

  function closeChampionSelection() {
    const dialog = document.getElementById("champion-selection-dialog");
    if (dialog) dialog.remove();
    delete window.__roseChampionRenderer;
    delete window.__roseAllChampions;
  }

  function renderChampionsGrid(champions) {
    const grid = document.getElementById("champions-grid");
    if (!grid) return;
    grid.innerHTML = "";

    champions.forEach((champ) => {
      const card = document.createElement("div");
      card.style.cssText = "display:flex;flex-direction:column;align-items:center;cursor:pointer;padding:6px;border:1px solid transparent;border-radius:4px;transition:0.2s;";
      card.addEventListener("mouseenter", () => card.style.borderColor = "#c8aa6e");
      card.addEventListener("mouseleave", () => card.style.borderColor = "transparent");
      
      const img = document.createElement("img");
      img.src = `/lol-game-data/assets/v1/champion-icons/${champ.id}.png`;
      img.style.cssText = "width:60px;height:60px;border-radius:50%;border:2px solid #5b5a56;object-fit:cover;";
      card.appendChild(img);

      const name = document.createElement("div");
      name.style.cssText = "margin-top:6px;font-size:11px;color:#a09b8c;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:80px;";
      name.textContent = champ.name;
      card.appendChild(name);

      card.addEventListener("click", () => {
        closeChampionSelection();
        openSkinSelection(champ.id);
      });
      grid.appendChild(card);
    });
  }

  function openSkinSelection(championId) {
    const existing = document.getElementById("skin-selection-dialog");
    if (existing) existing.remove();

    window.__roseSelectedSkinIds = new Set();

    const dialog = document.createElement("div");
    dialog.id = "skin-selection-dialog";
    dialog.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:20001 !important;background:rgba(0,0,0,0.65);display:flex;align-items:center;justify-content:center;pointer-events:all;";
    dialog.addEventListener("click", (e) => { if (e.target === dialog) closeSkinSelection(); });
    document.body.appendChild(dialog);

    const flyoutFrame = document.createElement("div");
    flyoutFrame.style.cssText = "max-height:75vh;width:700px;background:#010a13;border:1px solid #c8aa6e;padding:20px;box-sizing:border-box;font-family:'Beaufort for LOL',serif;color:#cdbe91;display:flex;flex-direction:column;";
    flyoutFrame.addEventListener("click", (e) => e.stopPropagation());

    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;";
    
    const title = document.createElement("div");
    title.id = "skin-selection-title";
    title.style.cssText = "font-size:18px;font-weight:bold;color:#c8aa6e;";
    title.textContent = "Select Skins & Chromas";
    header.appendChild(title);

    const closeBtn = document.createElement("button");
    closeBtn.innerHTML = "&times;";
    closeBtn.style.cssText = "background:transparent;border:none;color:#a09b8c;font-size:24px;cursor:pointer;";
    closeBtn.addEventListener("click", closeSkinSelection);
    header.appendChild(closeBtn);
    flyoutFrame.appendChild(header);

    const loading = document.createElement("div");
    loading.id = "skin-loading";
    loading.textContent = "Loading skins...";
    loading.style.cssText = "color:#cdbe91;text-align:center;padding:20px;";
    flyoutFrame.appendChild(loading);

    const skinsList = document.createElement("div");
    skinsList.id = "skins-list";
    skinsList.style.cssText = "display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;max-height:50vh;overflow-y:auto;padding-right:6px;";
    flyoutFrame.appendChild(skinsList);

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;align-items:center;justify-content:space-between;margin-top:16px;padding-top:12px;border-top:1px solid #463714;";
    
    const count = document.createElement("span");
    count.id = "skin-selection-count";
    count.textContent = "0 targets selected";
    actions.appendChild(count);

    const confirmBtn = document.createElement("button");
    confirmBtn.textContent = "Confirm & Select Mod";
    confirmBtn.disabled = true;
    confirmBtn.style.cssText = "padding:8px 16px;border:1px solid #c8aa6e;background:#1e2328;color:#c8aa6e;cursor:pointer;font-weight:bold;";
    confirmBtn.addEventListener("click", () => {
      const selected = Array.from(window.__roseSelectedSkinIds || []);
      if (!selected.length) return;
      closeSkinSelection();
      if (bridge) bridge.send({
        type: "add-custom-mods-skin-selected",
        action: "create",
        championId: championId,
        skinIds: selected,
      });
    });
    actions.appendChild(confirmBtn);
    flyoutFrame.appendChild(actions);

    dialog.appendChild(flyoutFrame);

    if (bridge) bridge.send({ type: "add-custom-mods-skin-selected", action: "list", championId });
  }

  function closeSkinSelection() {
    const dialog = document.getElementById("skin-selection-dialog");
    if (dialog) dialog.remove();
    delete window.__roseSelectedSkinIds;
  }

  function handleChampionsListResponse(payload) {
    const loading = document.getElementById("champion-loading");
    if (loading) loading.style.display = "none";
    window.__roseAllChampions = payload.champions || [];
    renderChampionsGrid(window.__roseAllChampions);
  }

  function handleChampionSkinsResponse(payload) {
    const loading = document.getElementById("skin-loading");
    if (loading) loading.style.display = "none";

    const title = document.getElementById("skin-selection-title");
    if (title && payload.championName) title.textContent = `Select Skins - ${payload.championName}`;

    const skinsList = document.getElementById("skins-list");
    if (!skinsList) return;
    skinsList.innerHTML = "";

    const skins = payload.skins || [];
    skins.forEach((skin) => {
      const card = document.createElement("div");
      card.style.cssText = "display:flex;flex-direction:column;align-items:center;cursor:pointer;padding:6px;border:1px solid #4a4a48;border-radius:4px;background:#151b21;transition:0.2s;";
      
      const img = document.createElement("img");
      img.src = skin.tilePath || `/lol-game-data/assets/v1/champion-tiles/${skin.id}.jpg`;
      img.style.cssText = "width:100%;height:140px;object-fit:cover;border-radius:2px;";
      img.onerror = () => { img.style.display = "none"; };
      card.appendChild(img);

      const name = document.createElement("div");
      name.style.cssText = "margin-top:6px;font-size:11px;color:#a09b8c;text-align:center;line-height:1.2;word-break:break-word;";
      name.textContent = skin.name || `Skin ${skin.id}`;
      card.appendChild(name);

      card.addEventListener("click", () => {
        const id = Number(skin.id || skin.skinId);
        const set = window.__roseSelectedSkinIds || new Set();
        if (set.has(id)) {
          set.delete(id);
          card.style.borderColor = "#4a4a48";
          card.style.background = "#151b21";
        } else {
          set.add(id);
          card.style.borderColor = "#c8aa6e";
          card.style.background = "#463714";
        }
        window.__roseSelectedSkinIds = set;

        const countEl = document.getElementById("skin-selection-count");
        if (countEl) countEl.textContent = `${set.size} target${set.size === 1 ? "" : "s"} selected`;

        const btn = document.querySelector("#skin-selection-dialog button:last-child");
        if (btn) btn.disabled = set.size === 0;
      });

      skinsList.appendChild(card);
    });
  }

  function handleSelectionResult(data) {
    const detail = data?.detail || data;
    if (!detail || detail.type !== "custom-mod-selection-result") return;
    if (pendingSelectionRequest && detail.requestId !== pendingSelectionRequest.requestId) return;
    
    pendingSelectionRequest = null;
    if (!detail.success) {
      console.warn(`${LOG_PREFIX} Selection failed: ${detail.error}`);
      return;
    }

    if (detail.operation === "deselect") { 
      selectedModId = null; 
      selectedModSkinId = null; 
    } else if (detail.operation === "select") {
      selectedModId = String(detail.relativePath || detail.modId || "");
      selectedModSkinId = Number(detail.skinId || getCurrentSkinContext().skinId);
    }
    if (isOpen && activeTab === "skins") refreshSummaryValues();
  }

  function handleModsResponse(data) {
    const detail = data?.detail || data;
    if (!detail || detail.type !== "skin-mods-response") return;

    hideEmptyCategories = Boolean(detail.hideEmptyCategories);
    applyVisibleCategoryState();

    currentSkinMods = detail.mods || [];
    if (detail.historicMod && !selectedModId) {
      const match = currentSkinMods.find(m => (m.relativePath || "").replace(/\\/g, "/") === String(detail.historicMod).replace(/\\/g, "/"));
      if (match) {
        selectedModId = match.relativePath || match.modName;
        selectedModSkinId = Number(match.skinId);
      }
    }

    refreshSummaryValues();
    if (isOpen && rightPaneMode === "picker" && activeTab === "skins") {
      updateModEntries(currentSkinMods);
    }
  }

  // --- Инициализация ---
  async function init() {
    if (window._roseCustomWheelInit) return;
    window._roseCustomWheelInit = true;

    injectCSS();
    bridge = await waitForBridge();
    
    if (window.__roseSkinState) skinMonitorState = window.__roseSkinState;

    bridge.subscribe("skin-mods-response", handleModsResponse);
    bridge.subscribe("custom-mod-selection-result", handleSelectionResult);
    bridge.subscribe("chroma-state", handleChromaStateUpdate);
    bridge.subscribe("phase-change", handlePhaseChange);
    bridge.subscribe("champion-locked", (d) => {
      championLocked = Boolean(d?.locked);
      if (!championLocked) { resetCustomSkinSessionState(); if (!isGlobalMode) closePanel(); }
      else requestModsForCurrentSkin();
    });
    bridge.subscribe("settings-data", (d) => { hideEmptyCategories = Boolean(d?.hideEmptyCategories); applyVisibleCategoryState(); });
    bridge.subscribe("maps-response", handleMapsResponse);
    bridge.subscribe("fonts-response", handleFontsResponse);
    bridge.subscribe("announcers-response", handleAnnouncersResponse);
    bridge.subscribe("category-mods-response", handleCategoryModsResponse);
    bridge.subscribe("others-response", handleOthersResponse);
    bridge.subscribe("champions-list-response", handleChampionsListResponse);
    bridge.subscribe("champion-skins-response", handleChampionSkinsResponse);

    // Авто-обновление при добавлении мода
    bridge.subscribe("folder-opened-response", (data) => {
      const detail = data?.detail || data;
      if (detail && detail.success) {
        if (detail.category) {
          if (detail.category === "maps") requestMaps();
          else if (detail.category === "fonts") requestFonts();
          else if (detail.category === "announcers") requestAnnouncers();
          else requestCategoryMods(detail.category);
        } else {
          requestModsForCurrentSkin();
        }
      }
    });

    bridge.subscribe("custom-mod-state", (data) => {
      if (!data) return;
      if (!data.active && selectedModId) {
        selectedModId = null;
        selectedModSkinId = null;
        if (panel && panel._modList) {
          panel._modList.querySelectorAll("li.selected-row").forEach((li) => li.classList.remove("selected-row"));
          updateNoneRow(panel._modList, true);
        }
        refreshSummaryValues();
      } else if (data.active && (data.relativePath || data.modName)) {
        selectedModId = String(data.relativePath || data.modName);
        selectedModSkinId = Number(data.skinId) || Number(getCurrentSkinContext().skinId);
        refreshSummaryValues();
      }
    });

    bridge.onReady(() => {
      requestModsForCurrentSkin();
      bridge.send({ type: "settings-request" });
      requestMaps(); 
      requestFonts(); 
      requestAnnouncers();
      for (const t of OTHER_CATEGORY_TABS) {
        requestCategoryMods(t.id);
      }
    });

    window.addEventListener(EVENT_SKIN_STATE, handleSkinState, { passive: true });
    window.addEventListener("resize", () => { if (isOpen && panel) positionPanel(panel); });

    // Открытие из настроек (Global Mode)
    window.addEventListener("rose-open-custom-wheel", () => {
      isGlobalMode = true;
      if (!panel) createPanel();
      if (!panel.parentNode) document.body.appendChild(panel);
      
      panel.style.display = "block";
      isOpen = true;

      if (isFirstOpenInSession) {
        activeTab = "skins";
        isFirstOpenInSession = false;
      }

      setRightPaneMode("summary");
      refreshSummaryValues();

      requestModsForCurrentSkin();
      requestMaps();
      requestFonts();
      requestAnnouncers();
      for (const t of OTHER_CATEGORY_TABS) {
        requestCategoryMods(t.id);
      }

      positionPanel(panel);

      setTimeout(() => {
        const closeHandler = (e) => {
          const flyout = panel ? panel.querySelector(".flyout") : null;
          if (!panel || !panel.parentNode) {
            document.removeEventListener("click", closeHandler);
            return;
          }
          if (flyout && flyout.contains(e.target)) return;
          closePanel();
          document.removeEventListener("click", closeHandler);
        };
        document.addEventListener("click", closeHandler);
      }, 200);
    });

    // Безопасный цикл проверки и монтирования кнопки в ChampSelect
    setInterval(() => {
      const inCS = !!document.querySelector(".champion-select");
      const inLobby = isActuallyInLobby();
      const overlayActive = isOverlayOpen();
      
      const shouldShow = (inCS || (inLobby && isSwiftplayMode)) && !overlayActive;

      if (shouldShow) { 
        if (!button) createButton();
        attachToChampionSelect(); 
        updateButtonVisibility(button, true); 
      } else { 
        if (button) updateButtonVisibility(button, false); 
      }
    }, 150);

    new MutationObserver(updateChampionSelectTarget).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();