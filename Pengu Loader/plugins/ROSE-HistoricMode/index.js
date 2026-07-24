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

  function isOverlayOpen() {
    const overlays =[
      'lol-perks-v2-editor',           
      'lol-perks-v2-main-view',        
      '.perks-editor-modal',           
      'lol-uikit-full-page-modal',     
      '.champion-customization-flyout',
      'lol-uikit-dialog-frame',        
      '.modal-root',
      '#rose-custom-wheel-panel-container',
      '#lu-chroma-panel-container',
      '#forms-wheel-panel-container',
      '#rose-settings-panel'
    ];
    for (const selector of overlays) {
      const el = document.querySelector(selector);
      if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) return true;
    }
    const backdrop = document.querySelector('.lol-uikit-layer-manager-wrapper');
    if (backdrop && backdrop.children.length > 1) return true;
    return false;
  }
  
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
  let historicFlagImageUrl = null; // HTTP URL from Python
  const pendingHistoricFlagRequest = new Map(); // Track pending requests
  let isInChampSelect = false; // Track if we're in ChampSelect phase
  let pythonChromaState = null;
  let championLocked = false;
  let customModTargetSkinId = null;
  let customModAffectedSkinIds = new Set();
  let historicEntryAvailable = false;
  let historicBaseSkinId = null;
  let currentLabelChampionId = null;
  let currentViewType = null;

  function getCurrentEffectiveSkinId() {
    const skinState = window.__roseSkinState || {};
    const baseSkinId = Number(skinState.skinId);
    const chromaState = pythonChromaState || {};
    const selectedChromaId = Number(chromaState.selectedChromaId);
    const chromaBaseSkinId = Number(chromaState.currentSkinId);

    if (
      Number.isFinite(selectedChromaId) &&
      selectedChromaId > 0 &&
      (!Number.isFinite(chromaBaseSkinId) ||
        !Number.isFinite(baseSkinId) ||
        chromaBaseSkinId === baseSkinId)
    ) {
      return selectedChromaId;
    }

    return Number.isFinite(baseSkinId) && baseSkinId > 0 ? baseSkinId : null;
  }

  function customModAppliesToSkin(skinId) {
    const numericSkinId = Number(skinId);
    if (!Number.isFinite(numericSkinId) || numericSkinId <= 0) return false;
    return (
      customModTargetSkinId === numericSkinId ||
      customModAffectedSkinIds.has(numericSkinId)
    );
  }


  function isHistoricHistoryMarkerActive() {
    if (!historicEntryAvailable || !Number.isFinite(historicBaseSkinId)) {
      return false;
    }

    const currentBaseSkinId = Number((window.__roseSkinState || {}).skinId);
    return currentBaseSkinId === historicBaseSkinId;
  }

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
      customModPopupActive = false;
      customModTargetSkinId = null;
      customModAffectedSkinIds = new Set();
      historicModeActive = false;
      historicEntryAvailable = false;
      historicBaseSkinId = null;
      log("debug", "Entered ChampSelect phase - enabling plugin");
      // Try to update flag when entering ChampSelect
      if (historicModeActive) {
        setTimeout(() => {
          updateHistoricFlag();
        }, 100);
      }
    } else if (!isInChampSelect && wasInChampSelect) {
      customModPopupActive = false;
      customModTargetSkinId = null;
      customModAffectedSkinIds = new Set();
      historicModeActive = false;
      historicEntryAvailable = false;
      historicBaseSkinId = null;
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

  function showSkinName(skinName) {
    const id = SHOW_SKIN_NAME_ID;
    let text = skinName;
    // If an element with the same id already exists, directly update the content and reset the timer
    let popup = document.getElementById(id);
    if (popup) {
      const pTag = popup.querySelector("p");
      if (pTag) {
        pTag.textContent = text;
      }
      resetTimer(popup);
      return;
    }

    // Inject dialog frame styles
    injectDialogFrameStyles();

    // Create container
    popup = document.createElement("div");
    popup.id = id;

    // Set styles
    Object.assign(popup.style, {
      position: "fixed",
      bottom: "calc(10% + 215px)",
      left: "50%",
      transform: "translate(-50%, 0)",
      zIndex: "0",
      background: "transparent",
      color: "#b2a580",
      padding: "0",
      margin: "0",
      fontSize: "14px",
      lineHeight: "1.4",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      maxWidth: "300px",
      width: "auto",
      boxSizing: "border-box",
      pointerEvents: "none",
      visibility: "visible",
      opacity: "1",
      zIndex: "1000000",
    });

    // Create toast-body div
    const toastBody = document.createElement("div");
    toastBody.className = "toast-body";
    Object.assign(toastBody.style, {
      display: "flex",
      flexDirection: "column",
      justifyContent: "space-between",
      boxSizing: "border-box",
      position: "relative",
      width: "auto",
      margin: "0 auto",
    });

    // Create toast-content div
    const toastContent = document.createElement("div");
    toastContent.className = "toast-content";
    Object.assign(toastContent.style, {
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      width: "100%",
    });

    // Create lol-uikit-dialog-frame wrapper
    let dialogFrame;
    try {
      dialogFrame = document.createElement("lol-uikit-dialog-frame");
      dialogFrame.className = "lol-uikit-dialog-frame top dismissable-icon";
    } catch (e) {
      dialogFrame = document.createElement("div");
      dialogFrame.className = "lol-uikit-dialog-frame top dismissable-icon";
    }
    Object.assign(dialogFrame.style, {
      position: "relative",
      display: "inline-block",
    });

    // Create lol-uikit-content-block element
    let contentBlock;
    try {
      contentBlock = document.createElement("lol-uikit-content-block");
      contentBlock.className = "lol-ready-check-notification-party-dodge";
      contentBlock.setAttribute("type", "notification");
    } catch (e) {
      contentBlock = document.createElement("div");
      contentBlock.className =
        "lol-uikit-content-block lol-ready-check-notification-party-dodge";
      contentBlock.setAttribute("type", "notification");
    }

    // Set CSS custom properties
    contentBlock.style.setProperty(
      "--champion-preview-hover-animation-percentage",
      "0%"
    );
    contentBlock.style.setProperty("--column-height", "95px");
    contentBlock.style.setProperty(
      "--font-display",
      '"LoL Display","Times New Roman",Times,Baskerville,Georgia,serif'
    );
    contentBlock.style.setProperty(
      "--font-body",
      '"LoL Body",Arial,"Helvetica Neue",Helvetica,sans-serif'
    );
    contentBlock.style.setProperty(
      "--plug-transform1",
      "scale(1) rotate(0deg)"
    );
    contentBlock.style.setProperty(
      "--plug-transform2",
      "scale(1.075) rotate(1deg)"
    );
    contentBlock.style.setProperty(
      "--plug-filter1",
      "drop-shadow(0 0 0 rgb(66 60 40 / 0%))"
    );
    contentBlock.style.setProperty(
      "--plug-filter2",
      "drop-shadow(0 0 12px rgb(66 59 40 / 80%))"
    );
    contentBlock.style.setProperty("--plug-color1", "#423828");
    contentBlock.style.setProperty("--plug-color2", "#fcf0d7");
    contentBlock.style.setProperty(
      "--plug-box-shadow1",
      "0 0 0 rgb(66 58 40 / 0%)"
    );
    contentBlock.style.setProperty(
      "--plug-box-shadow2",
      "0 0 12px rgb(66 55 40 / 80%), inset 0 0 12px rgb(66 56 40 / 40%)"
    );
    contentBlock.style.setProperty("--plug-color-button", "#857a72");
    contentBlock.style.setProperty("--plug-color-buttonDisabled", "#72655a");
    contentBlock.style.setProperty("--plug-color-buttonHover", "#a89d8f");
    contentBlock.style.setProperty(
      "--plug-selected-item-border",
      "2px solid #7d644b"
    );
    contentBlock.style.setProperty(
      "--plug-selected-item-box-shadow",
      "0 0 10px rgb(194 129 68 / 50%)"
    );
    contentBlock.style.setProperty(
      "--plug-smoothGlow-box-shadow0",
      "0 0 8px rgb(66 55 40 / 40%), 0 0 12px rgb(66 54 40 / 20%)"
    );
    contentBlock.style.setProperty(
      "--plug-smoothGlow-box-shadow25",
      "0 0 10px rgb(66 55 40 / 50%), 0 0 16px rgb(66 57 40 / 10%), 0 0 30px rgb(66 55 40 / 20%)"
    );
    contentBlock.style.setProperty(
      "--plug-smoothGlow-box-shadow50",
      "0 0 12px rgb(66 56 40 / 60%), 0 0 20px rgb(66 54 40 / 30%), 0 0 30px rgb(66 55 40 / 10%)"
    );
    contentBlock.style.setProperty(
      "--plug-smoothGlow-box-shadow75",
      "0 0 10px rgb(66 55 40 / 50%), 0 0 16px rgb(66 56 40 / 10%), 0 0 30px rgb(66 54 40 / 20%)"
    );
    contentBlock.style.setProperty(
      "--plug-smoothGlow-box-shadow100",
      "0 0 8px rgb(66 58 40 / 40%), 0 0 12px rgb(66 56 40 / 20%)"
    );
    contentBlock.style.setProperty(
      "--plug-search-input-border",
      "1px solid #533e1c"
    );
    contentBlock.style.setProperty(
      "--plug-search-inputFocus-border-color",
      "#81602b"
    );
    contentBlock.style.setProperty(
      "--plug-search-inputFocus-box-shadow",
      "0 0 10px rgba(84, 58, 96, 0.3)"
    );
    contentBlock.style.setProperty("--plug-jsbutton-color", "#81602b");
    contentBlock.style.setProperty(
      "--plug-soft-text-glow-kda1",
      "rgb(255 155 0) 0px 0px 17px"
    );
    contentBlock.style.setProperty(
      "--plug-soft-text-glow-kda2",
      "rgb(255 143 0 / 37%) 0px 0px 76px"
    );
    contentBlock.style.setProperty("--plug-scrollable-color", "#785a28");

    // Set regular CSS properties
    Object.assign(contentBlock.style, {
      WebkitUserSelect: "none",
      position: "relative",
      background: "transparent",
      width: "auto",
      display: "inline-block",
      boxSizing: "border-box",
      paddingLeft: "25px",
      paddingRight: "25px",
    });

    // Create paragraph with skin name (preserving case)
    const pTag = document.createElement("p");
    pTag.textContent = text;

    // Create lol-uikit-dialog-frame-sub-border element
    const subBorder = document.createElement("div");
    subBorder.className = "lol-uikit-dialog-frame-sub-border";

    // Set CSS custom properties
    subBorder.style.setProperty(
      "--champion-preview-hover-animation-percentage",
      "0%"
    );
    subBorder.style.setProperty("--column-height", "95px");
    subBorder.style.setProperty(
      "--font-display",
      '"LoL Display","Times New Roman",Times,Baskerville,Georgia,serif'
    );
    subBorder.style.setProperty(
      "--font-body",
      '"LoL Body",Arial,"Helvetica Neue",Helvetica,sans-serif'
    );
    subBorder.style.setProperty("--plug-transform1", "scale(1) rotate(0deg)");
    subBorder.style.setProperty(
      "--plug-transform2",
      "scale(1.075) rotate(1deg)"
    );
    subBorder.style.setProperty(
      "--plug-filter1",
      "drop-shadow(0 0 0 rgb(66 60 40 / 0%))"
    );
    subBorder.style.setProperty(
      "--plug-filter2",
      "drop-shadow(0 0 12px rgb(66 59 40 / 80%))"
    );
    subBorder.style.setProperty("--plug-color1", "#423828");
    subBorder.style.setProperty("--plug-color2", "#fcf0d7");
    subBorder.style.setProperty(
      "--plug-box-shadow1",
      "0 0 0 rgb(66 58 40 / 0%)"
    );
    subBorder.style.setProperty(
      "--plug-box-shadow2",
      "0 0 12px rgb(66 55 40 / 80%), inset 0 0 12px rgb(66 56 40 / 40%)"
    );
    subBorder.style.setProperty("--plug-color-button", "#857a72");
    subBorder.style.setProperty("--plug-color-buttonDisabled", "#72655a");
    subBorder.style.setProperty("--plug-color-buttonHover", "#a89d8f");
    subBorder.style.setProperty(
      "--plug-selected-item-border",
      "2px solid #7d644b"
    );
    subBorder.style.setProperty(
      "--plug-selected-item-box-shadow",
      "0 0 10px rgb(194 129 68 / 50%)"
    );
    subBorder.style.setProperty(
      "--plug-smoothGlow-box-shadow0",
      "0 0 8px rgb(66 55 40 / 40%), 0 0 12px rgb(66 54 40 / 20%)"
    );
    subBorder.style.setProperty(
      "--plug-smoothGlow-box-shadow25",
      "0 0 10px rgb(66 55 40 / 50%), 0 0 16px rgb(66 57 40 / 10%), 0 0 30px rgb(66 55 40 / 20%)"
    );
    subBorder.style.setProperty(
      "--plug-smoothGlow-box-shadow50",
      "0 0 12px rgb(66 56 40 / 60%), 0 0 20px rgb(66 54 40 / 30%), 0 0 30px rgb(66 55 40 / 10%)"
    );
    subBorder.style.setProperty(
      "--plug-smoothGlow-box-shadow75",
      "0 0 10px rgb(66 55 40 / 50%), 0 0 16px rgb(66 56 40 / 10%), 0 0 30px rgb(66 54 40 / 20%)"
    );
    subBorder.style.setProperty(
      "--plug-smoothGlow-box-shadow100",
      "0 0 8px rgb(66 58 40 / 40%), 0 0 12px rgb(66 56 40 / 20%)"
    );
    subBorder.style.setProperty(
      "--plug-search-input-border",
      "1px solid #533e1c"
    );
    subBorder.style.setProperty(
      "--plug-search-inputFocus-border-color",
      "#81602b"
    );
    subBorder.style.setProperty(
      "--plug-search-inputFocus-box-shadow",
      "0 0 10px rgba(84, 58, 96, 0.3)"
    );
    subBorder.style.setProperty("--plug-jsbutton-color", "#81602b");
    subBorder.style.setProperty(
      "--plug-soft-text-glow-kda1",
      "rgb(255 155 0) 0px 0px 17px"
    );
    subBorder.style.setProperty(
      "--plug-soft-text-glow-kda2",
      "rgb(255 143 0 / 37%) 0px 0px 76px"
    );
    subBorder.style.setProperty("--plug-scrollable-color", "#785a28");

    // Set regular CSS properties (subBorder will be styled by CSS rules)
    Object.assign(subBorder.style, {
      WebkitUserSelect: "none",
    });

    // Create before pseudo-element
    const beforeElement = document.createElement("div");
    beforeElement.setAttribute("data-pseudo", "before");
    Object.assign(beforeElement.style, {
      position: "absolute",
      display: "block",
      content: '""',
    });
    subBorder.insertBefore(beforeElement, subBorder.firstChild);

    // Create after pseudo-element
    const afterElement = document.createElement("div");
    afterElement.setAttribute("data-pseudo", "after");
    Object.assign(afterElement.style, {
      position: "absolute",
      display: "block",
      content: '""',
    });
    subBorder.appendChild(afterElement);

    // Close button — lets the user dismiss the popup and cancel injection
    const closeBtn = document.createElement("div");
    closeBtn.className = "lol-uikit-dialog-frame-toast-close-button";
    closeBtn.style.pointerEvents = "auto";
    closeBtn.addEventListener("click", () => {
      removeHistoricSkinName();
      dismissActivePopup();
    });

    // Build the nested structure
    contentBlock.appendChild(pTag);
    dialogFrame.appendChild(contentBlock);
    dialogFrame.appendChild(subBorder);
    dialogFrame.appendChild(closeBtn);
    toastContent.appendChild(dialogFrame);
    toastBody.appendChild(toastContent);

    popup.appendChild(toastBody);

    // Find the same container as the random skin button to match stacking context
    function findNamePanelContainer() {
      // Only try to find container when in ChampSelect
      if (!isInChampSelect) {
        return null;
      }

      // Find the carousel container to match its stacking context (same as random skin button)
      const carouselContainer = document.querySelector(".skin-selection-carousel-container");
      if (carouselContainer) {
        return carouselContainer;
      }

      // Fallback: find the carousel itself
      const carousel = document.querySelector(".skin-selection-carousel");
      if (carousel) {
        return carousel;
      }

      // Last fallback: find the main champ select container and then div.visible
      const mainContainer = document.querySelector(".champion-select-main-container");
      if (mainContainer) {
        const visibleDiv = mainContainer.querySelector("div.visible");
        if (visibleDiv) {
          return visibleDiv;
        }
      }

      return null;
    }

    // Try to append to the same container as random skin button
    const targetContainer = findNamePanelContainer();
    if (targetContainer) {
      // Ensure container has positioning context
      const containerComputedStyle = window.getComputedStyle(targetContainer);
      if (containerComputedStyle.position === 'static') {
        targetContainer.style.position = 'relative';
      }

      // Get container's position relative to viewport
      const containerRect = targetContainer.getBoundingClientRect();

      // Calculate position relative to container (convert from fixed to absolute)
      // The original position is: bottom: calc(10% + 350px), left: 50%
      const viewportHeight = window.innerHeight;
      const bottomOffset = viewportHeight * 0.1 + 265; // 10% + 265px
      const topPosition = viewportHeight - bottomOffset;

      // Update styles for absolute positioning relative to container
      popup.style.position = "absolute";
      popup.style.bottom = "auto";
      popup.style.top = `${topPosition - containerRect.top}px`;
      popup.style.left = "50%";
      popup.style.transform = "translate(-50%, 0)";

      targetContainer.appendChild(popup);
    } else {
      // Fallback: append to body if container not found
      document.body.appendChild(popup);
    }

    // Auto close timer
    resetTimer(popup);

    function resetTimer(el) {
      if (el._timer) clearTimeout(el._timer);
      el._timer = setTimeout(() => el.remove(), 125000); // Remove after 125 seconds
    }
  }

  const handleHistoricSkinNameUpdate = (payload) => {
    // A custom-mod popup owns this same visual layer. Historic-state
    // broadcasts can arrive slightly after the custom-mod selection, so do
    // not let an inactive historic update erase the custom-mod name.
    if (customModPopupActive) return;

    if (payload.historicSkinName && payload.historicSkinName !== "None") {
      showSkinName(payload.historicSkinName);
    } else {
      removeHistoricSkinName();
    }
  };

  function handleCustomModStateUpdate(data) {
    log("info", "Received custom mod state", {
      active: data?.active === true,
      modName: data?.modName || null,
      skinId: data?.skinId || null,
      currentSkinId: getCurrentEffectiveSkinId(),
    });

    if (data.active && data.modName) {
      customModTargetSkinId = data.skinId ? Number(data.skinId) : null;
      customModAffectedSkinIds = new Set(
        (Array.isArray(data.affectedSkinIds) ? data.affectedSkinIds : [])
          .map((value) => Number(value))
          .filter((value) => Number.isFinite(value) && value > 0)
      );
      if (customModTargetSkinId) {
        customModAffectedSkinIds.add(customModTargetSkinId);
      }
      customModPopupActive = true;
      showSkinName(data.modName);
      log("info", "Displayed custom mod popup", {
        modName: data.modName,
        skinId: customModTargetSkinId,
        affectedSkinIds: [...customModAffectedSkinIds],
      });
    } else {
      customModPopupActive = false;
      customModTargetSkinId = null;
      customModAffectedSkinIds = new Set();
      removeHistoricSkinName();
    }
  }


  function handleChromaStateUpdate(data) {
    pythonChromaState = data || null;
    if (
      customModPopupActive &&
      !customModAppliesToSkin(getCurrentEffectiveSkinId())
    ) {
      customModPopupActive = false;
      customModTargetSkinId = null;
      customModAffectedSkinIds = new Set();
      removeHistoricSkinName();
    }
  }

  function handleSkinStateUpdate(data) {
    if (customModPopupActive) {
      const nextSkinId = Number(data?.skinId);
      const currentEffectiveSkinId = getCurrentEffectiveSkinId();
      if (
        (
          customModAppliesToSkin(currentEffectiveSkinId) ||
          customModAppliesToSkin(nextSkinId)
        )
      ) {
        return;
      }

      customModPopupActive = false;
      customModTargetSkinId = null;
      customModAffectedSkinIds = new Set();
      removeHistoricSkinName();
    }

    if (isInChampSelect) {
      updateHistoricFlag();
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

    if (!isOverlayOpen()) {
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
    bridge.subscribe("chroma-state", handleChromaStateUpdate);
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