/**
 * @name ROSE-HistoricMode
 * @author Rose Team
 * @description Historic mode for Pengu Loader
 * @link https://github.com/FlorentTariolle/Rose-HistoricMode
 */
(function initHistoricMode() {
  const LOG_PREFIX = "[ROSE-HistoricMode]";
  const REWARDS_SELECTOR = ".skin-selection-item-information.loyalty-reward-icon--rewards";
  const HISTORIC_FLAG_ASSET_PATH = "historic_flag.png";
  const SHOW_SKIN_NAME_ID = "historic-popup-layer";
  let bridge = null;

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

  function decodeHTMLEntities(text) {
    if (typeof text !== 'string') return text;
    const textArea = document.createElement('textarea');
    textArea.innerHTML = text;
    return textArea.value;
  }

  let historicModeActive = false;
  let customModPopupActive = false;
  let currentRewardsElement = null;
  let historicFlagImageUrl = null;
  const pendingHistoricFlagRequest = new Map();
  let isInChampSelect = false;
  let championLocked = false;

  let currentLabelChampionId = null;
  let currentViewType = null;

  const CSS_RULES = `
    .skin-selection-item-information.loyalty-reward-icon--rewards.lu-historic-flag-active {
      background-repeat: no-repeat !important;
      background-size: contain !important;
      height: 32px !important;
      width: 32px !important;
      position: absolute !important;
      right: -14px !important;
      top: -14px !important;
      pointer-events: none !important;
      cursor: default !important;
      -webkit-user-select: none !important;
      list-style-type: none !important;
      content: " " !important;
    }

    /* === BEAUTIFUL AUTO-LOCK BADGE STYLES === */
    #rose-historic-locked-label {
      z-index: 10000;
      pointer-events: none;
      transition: opacity 0.3s ease;
    }

    /* Classic View: Centered globally at bottom */
    #rose-historic-locked-label.is-classic-view {
      position: fixed;
      bottom: 230px; 
      left: 50%;
      transform: translateX(-50%);
    }

    /* Swiftplay & Collection View: Positioned absolutely INSIDE their container (above carousel) */
    #rose-historic-locked-label.is-collection-view,
    #rose-historic-locked-label.is-swiftplay-view {
      position: absolute;
      bottom: 120px; /* Идеально над каруселью скинов */
      left: 50%;
      transform: translateX(-50%);
    }

    .rose-historic-badge {
      background: linear-gradient(180deg, rgba(1,10,19,0.9) 0%, rgba(1,10,19,0.95) 100%);
      border: 1px solid #463714;
      border-top: 1px solid #785a28;
      box-shadow: 0 4px 12px rgba(0,0,0,0.8);
      padding: 6px 16px;
      color: #c8aa6e;
      font-family: "Beaufort for LOL", serif;
      font-size: 13px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
      border-radius: 4px;
      text-transform: uppercase;
      letter-spacing: 1px;
    }

    .rose-historic-badge-text {
      color: #f0e6d2;
      text-shadow: 0 1px 3px rgba(0,0,0,1);
    }
  `;

  function log(level, message, data = null) {
    const payload = { type: "chroma-log", source: "LU-HistoricMode", level: level, message: message, timestamp: Date.now() };
    if (data) payload.data = data;
    if (bridge) bridge.send(payload);
  }

  function handlePhaseChange(data) {
    const wasInChampSelect = isInChampSelect;
    isInChampSelect = data.phase === "ChampSelect" || data.phase === "FINALIZATION";

    if (isInChampSelect && !wasInChampSelect) {
      if (historicModeActive) setTimeout(updateHistoricFlag, 100);
    } else if (!isInChampSelect && wasInChampSelect) {
      customModPopupActive = false;
      championLocked = false;
      removeHistoricSkinName();
      if (currentRewardsElement) {
        hideFlagOnElement(currentRewardsElement);
        currentRewardsElement = null;
      }
    }
  }

  function handleLocalAssetUrl(data) {
    const assetPath = data.assetPath;
    let url = data.url;
    if (url && typeof url === 'string') url = url.replace('localhost', '127.0.0.1');

    if (assetPath === HISTORIC_FLAG_ASSET_PATH && url) {
      historicFlagImageUrl = url;
      pendingHistoricFlagRequest.delete(HISTORIC_FLAG_ASSET_PATH);
      if (isInChampSelect && historicModeActive) updateHistoricFlag();
    }
  }

  function handleHistoricStateUpdate(data) {
    historicModeActive = data.active === true;
    if (currentLabelChampionId && currentViewType && bridge) {
      bridge.send({type: "request-historic-label", championId: currentLabelChampionId, viewType: currentViewType});
    }
    setTimeout(updateHistoricFlag, 100);
    if (historicModeActive) setTimeout(updateHistoricFlag, 1000);
  }

  function findRewardsElement() {
    if (!isInChampSelect) return null;
    const selectedItem = document.querySelector(".skin-selection-item.skin-selection-item-selected");
    if (selectedItem) {
      const info = selectedItem.querySelector(".skin-selection-item-information.loyalty-reward-icon--rewards");
      if (info) return info;
    }
    const element = document.querySelector(REWARDS_SELECTOR);
    if (element) return element;
    
    const carousel = document.querySelector(".skin-selection-carousel");
    if (carousel) {
      const items = carousel.querySelectorAll(".skin-selection-item");
      for (const item of items) {
        const info = item.querySelector(".skin-selection-item-information");
        if (info && info.classList.contains("loyalty-reward-icon--rewards")) return info;
      }
    }
    return null;
  }

  function injectDialogFrameStyles() {
    if (document.getElementById("rose-historic-mode-dialog-frame-styles")) return;
    const style = document.createElement("style");
    style.id = "rose-historic-mode-dialog-frame-styles";
    style.textContent = CSS_RULES; 
    document.head.appendChild(style);
  }

  function handleCustomModStateUpdate(data) {
    if (data.active && data.modName) {
      const currentSkinId = Number((window.__roseSkinState || {}).skinId);
      const modSkinId = data.skinId ? Number(data.skinId) : null;
      if (modSkinId && currentSkinId && modSkinId !== currentSkinId) {
        customModPopupActive = false;
        removeHistoricSkinName();
        return;
      }
      customModPopupActive = true;
    } else {
      customModPopupActive = false;
      removeHistoricSkinName();
    }
  }

  function handleSkinStateUpdate(data) {
    if (customModPopupActive) {
      customModPopupActive = false;
      removeHistoricSkinName();
    }
  }

  function removeHistoricSkinName() {
    document.getElementById(SHOW_SKIN_NAME_ID)?.remove();
  }

  function requestHistoricFlagImage() {
    if (!historicFlagImageUrl && !pendingHistoricFlagRequest.has(HISTORIC_FLAG_ASSET_PATH)) {
      pendingHistoricFlagRequest.set(HISTORIC_FLAG_ASSET_PATH, true);
      if (bridge) bridge.send({ type: "request-local-asset", assetPath: HISTORIC_FLAG_ASSET_PATH, timestamp: Date.now() });
    }
  }

  function updateHistoricFlag() {
    if (!isInChampSelect) return;

    const element = findRewardsElement();

    if (!element) {
      if (!isInChampSelect) return;
      if (!updateHistoricFlag._retryCount) updateHistoricFlag._retryCount = 0;
      if (updateHistoricFlag._retryCount < 5) {
        updateHistoricFlag._retryCount++;
        setTimeout(() => {
          if (isInChampSelect) updateHistoricFlag();
          else updateHistoricFlag._retryCount = 0;
        }, 500);
      } else {
        updateHistoricFlag._retryCount = 0;
      }
      return;
    }

    updateHistoricFlag._retryCount = 0;

    if (currentRewardsElement && currentRewardsElement !== element) {
      hideFlagOnElement(currentRewardsElement);
    }
    currentRewardsElement = element;

    if (historicModeActive) {
      if (!historicFlagImageUrl) {
        requestHistoricFlagImage();
        return;
      }

      element.style.setProperty("display", "block", "important");
      element.style.setProperty("visibility", "visible", "important");
      element.style.setProperty("opacity", "1", "important");

      element.classList.add("lu-historic-flag-active");
      element.style.setProperty("background-image", `url("${historicFlagImageUrl}")`, "important");
      element.style.setProperty("background-repeat", "no-repeat", "important");
      element.style.setProperty("background-size", "contain", "important");
      element.style.setProperty("height", "32px", "important");
      element.style.setProperty("width", "32px", "important");
      element.style.setProperty("position", "absolute", "important");
      element.style.setProperty("right", "-14px", "important");
      element.style.setProperty("top", "-14px", "important");
      element.style.setProperty("pointer-events", "none", "important");
    } else {
      hideFlagOnElement(element);
    }
  }

  function hideFlagOnElement(element) {
    if (!element) return;
    element.classList.remove("lu-historic-flag-active");

    const hasRandomFlag = element.classList.contains("lu-random-flag-active");
    if (!hasRandomFlag) {
      element.style.removeProperty("background-image");
      element.style.removeProperty("background-repeat");
      element.style.removeProperty("background-size");
      element.style.removeProperty("height");
      element.style.removeProperty("width");
      element.style.removeProperty("position");
      element.style.removeProperty("right");
      element.style.removeProperty("top");
      element.style.setProperty("display", "none", "important");
      element.style.setProperty("visibility", "hidden", "important");
      element.style.setProperty("opacity", "0", "important");
    } else {
      const bgImage = element.style.getPropertyValue("background-image");
      if (bgImage && bgImage.includes("historic_flag.png")) {
        element.style.removeProperty("background-image");
      }
    }
  }

  // ==============================
  // TRANSPARENCY LABEL LOGIC 
  // ==============================

  function handleHistoricLabelResponse(data) {
    const { championId, hasHistoric, skinName, viewType } = data;
    
    let wrapper = document.getElementById('rose-historic-locked-label');
    
    if (!hasHistoric) {
        if (wrapper) wrapper.remove();
        return;
    }

    let targetContainer = document.body;

    // В Коллекции: добавляем прямо в контейнер чемпиона, чтобы абсолютная позиция работала от него
    if (viewType === 'collection-view') {
        const collectionDetail = document.querySelector('.collection-champion-detail');
        if (collectionDetail) targetContainer = collectionDetail;
    } 
    // В Swiftplay: добавляем в модальное окно выбора скинов
    else if (viewType === 'swiftplay-view') {
        const swiftplayActive = document.querySelector('.thumbnail-wrapper.active-skin');
        if (swiftplayActive) {
            const modal = swiftplayActive.closest('.lol-uikit-dialog-frame') || swiftplayActive.closest('.ember-view');
            if (modal) targetContainer = modal;
        }
    }

    if (!wrapper) {
        wrapper = document.createElement('div');
        wrapper.id = 'rose-historic-locked-label';
        
        wrapper.innerHTML = `
            <div class="rose-historic-badge">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#c8aa6e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
                AUTO-LOCK: <span class="rose-historic-badge-text"></span>
            </div>
        `;
    }
    
    // Перемещаем элемент в нужный контейнер (Важно для правильного `position: absolute`)
    if (wrapper.parentElement !== targetContainer) {
        targetContainer.appendChild(wrapper);
    }
    
    const textSpan = wrapper.querySelector('.rose-historic-badge-text');
    if (textSpan) textSpan.textContent = decodeHTMLEntities(skinName);

    wrapper.className = `is-${viewType}`;
  }

  function scanHistoricLabelContext() {
    let targetChampId = null;
    let targetViewType = null;

    // 1. Check Collection Menu
    const collectionDetail = document.querySelector('.collection-champion-detail');
    if (collectionDetail && collectionDetail.offsetParent !== null) {
      const bg = document.querySelector('lol-uikit-parallax-background');
      if (bg && bg.style.backgroundImage) {
        const match = bg.style.backgroundImage.match(/champion-splashes\/(\d+)\//);
        if (match) {
          targetChampId = parseInt(match[1]);
          targetViewType = 'collection-view';
        }
      }
    }
    // 2. Check Classic Champ Select (ONLY IF LOCKED)
    else {
      const champSelect = document.querySelector('.champion-select');
      if (champSelect && champSelect.offsetParent !== null) {
        const state = window.__roseSkinState;
        if (state && state.championId && championLocked) {
          targetChampId = state.championId;
          targetViewType = 'classic-view';
        }
      }
    }

    // 3. Check Swiftplay Lobby
    if (!targetChampId) {
      const swiftplayActive = document.querySelector('.thumbnail-wrapper.active-skin');
      if (swiftplayActive && swiftplayActive.offsetParent !== null) {
        const state = window.__roseSkinState;
        if (state && state.championId) {
          targetChampId = state.championId;
          targetViewType = 'swiftplay-view';
        }
      }
    }

    // If we found a valid context
    if (targetChampId && targetViewType) {
      if (currentLabelChampionId !== targetChampId || currentViewType !== targetViewType) {
        currentLabelChampionId = targetChampId;
        currentViewType = targetViewType;
        if (bridge) bridge.send({type: "request-historic-label", championId: targetChampId, viewType: targetViewType});
      }
    } else {
      // Clean up if no context
      if (currentLabelChampionId !== null) {
        currentLabelChampionId = null;
        currentViewType = null;
        const wrapper = document.getElementById('rose-historic-locked-label');
        if (wrapper) wrapper.remove();
      }
    }
  }

  async function init() {
    log("info", "Initializing LU-HistoricMode plugin");
    bridge = await waitForBridge();

    historicModeActive = false;
    injectDialogFrameStyles();

    bridge.subscribe("historic-state", handleHistoricStateUpdate);
    bridge.subscribe("custom-mod-state", handleCustomModStateUpdate);
    bridge.subscribe("skin-state", handleSkinStateUpdate);
    bridge.subscribe("local-asset-url", handleLocalAssetUrl);
    bridge.subscribe("phase-change", handlePhaseChange);
    
    // Subscribe to champion-locked to control label visibility in Classic
    bridge.subscribe("champion-locked", (data) => {
      championLocked = data.locked === true;
      scanHistoricLabelContext(); // Force immediate update
    });
    
    bridge.subscribe("historic-label-response", handleHistoricLabelResponse);

    bridge.onReady(() => {
      requestHistoricFlagImage();
    });

    const observer = new MutationObserver(() => {
      if (isInChampSelect && historicModeActive) {
        updateHistoricFlag();
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    // Start transparency label scanner
    setInterval(scanHistoricLabelContext, 500);

    log("info", "LU-HistoricMode plugin initialized");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();