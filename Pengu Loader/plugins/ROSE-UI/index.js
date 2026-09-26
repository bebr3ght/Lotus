/**
 * @name Rose-UI
 * @author Rose Team
 * @description Interface unlocker for Pengu Loader
 * @link https://github.com/Alban1911/Rose-UI
 */
(function enableLockedSkinPreview() {
  const LOG_PREFIX = "[Rose-UI][skin-preview]";
  const INLINE_ID = "lpp-ui-unlock-skins-css-inline";
  const BORDER_CLASS = "lpp-skin-border";
  const HIDDEN_CLASS = "lpp-skin-hidden";
  const CHROMA_CONTAINER_CLASS = "lpp-chroma-container";
  const VISIBLE_OFFSETS = new Set([0, 1, 2, 3, 4]);

  const DISCORD_INVITE_URL = "https://discord.com/invite/roseskins";
  const ROSE_DISCORD_GUILD_ID = "1490473857075642621";
  const ROSE_GITHUB_REPO_API_URL = "https://api.github.com/repos/Alban1911/Rose";
  const ROSE_GITHUB_BADGE_FALLBACK_URL =
    "https://img.shields.io/badge/GitHub-Stars-32A832?style=flat&logo=github&logoColor=white";
  let roseGithubStarsPromise = null;

  function getRoseGithubStars() {
    if (roseGithubStarsPromise) return roseGithubStarsPromise;

    roseGithubStarsPromise = fetch(ROSE_GITHUB_REPO_API_URL, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("GitHub API request failed");
        return response.json();
      })
      .then((repository) => {
        const stars = Number(repository && repository.stargazers_count);
        return Number.isSafeInteger(stars) && stars >= 0 ? stars : null;
      })
      .catch(() => null);

    return roseGithubStarsPromise;
  }

  function getRoseGithubBadgeUrl(stars) {
    const message = encodeURIComponent(stars + " stars");
    return "https://img.shields.io/badge/GitHub-" + message + "-32A832?style=flat&logo=github&logoColor=white";
  }

  function fixPenguWelcomeBadges(shadowRoot) {
    const badges = shadowRoot.querySelectorAll(
      'img[src*="img.shields.io/discord/"], img[src*="img.shields.io/github/stars/"]'
    );

    badges.forEach((badge) => {
      const source = badge.getAttribute("src") || "";

      if (source.includes("/discord/")) {
        const fixedSource = source.replace(/\/discord\/\d+/, "/discord/" + ROSE_DISCORD_GUILD_ID);
        if (fixedSource !== source) badge.setAttribute("src", fixedSource);
        return;
      }

      if (source.includes("/github/stars/")) {
        badge.setAttribute("src", ROSE_GITHUB_BADGE_FALLBACK_URL);
        getRoseGithubStars().then((stars) => {
          if (stars === null || !badge.isConnected) return;
          badge.setAttribute("src", getRoseGithubBadgeUrl(stars));
        });
      }
    });
  }

  function setupPenguWelcomeBadgeFix() {
    let attachedHost = null;
    let shadowObserver = null;

    const attach = () => {
      const host = document.getElementById("pengu-root");
      const shadowRoot = host && host.shadowRoot;
      if (!shadowRoot) return false;

      if (attachedHost === host) { fixPenguWelcomeBadges(shadowRoot); return true; }

      if (shadowObserver) shadowObserver.disconnect();
      attachedHost = host;
      fixPenguWelcomeBadges(shadowRoot);
      shadowObserver = new MutationObserver(() => { fixPenguWelcomeBadges(shadowRoot); });
      shadowObserver.observe(shadowRoot, {
        attributes: true,
        attributeFilter: ["src"],
        childList: true,
        subtree: true,
      });
      return true;
    };

    if (attach()) return;

    const documentObserver = new MutationObserver(() => {
      if (attach()) documentObserver.disconnect();
    });
    documentObserver.observe(document.documentElement, { childList: true, subtree: true });
    setTimeout(() => documentObserver.disconnect(), 30000);
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

  let lastBaseSkinSkipRequest = 0;
  const BASE_SKIN_SKIP_REQUEST_TIME_WINDOW_MS = 5000;

  function handleSkipBaseSkin(payload) {
    lastBaseSkinSkipRequest = Date.now();
    log.info("received base skin skip request from rose");
  }

  function interceptChampSelectWebsocket() {
    if (!window.rcp || typeof window.rcp.postInit !== "function") {
      setTimeout(interceptChampSelectWebsocket, 500);
      return;
    }
    window.rcp.postInit("rcp-fe-lol-champ-select", (api) => {
      try {
        const ws = api.champSelectBinding.socket._websocket;
        const parentOnMessage = ws.onmessage;

        ws.onmessage = function (event) {
          try {
            const payload = JSON.parse(event.data);
            if (payload[1] == "OnJsonApiEvent") {
              const eventData = payload[2];
              if (eventData["uri"] == "/lol-champ-select/v1/skin-selector-info") {
                if (eventData["data"]?.["selectedSkinId"] != 0) {
                  if (Date.now() - lastBaseSkinSkipRequest < BASE_SKIN_SKIP_REQUEST_TIME_WINDOW_MS) {
                    log.info("skipping base skin");
                    return;
                  }
                }
              }
            }
            return parentOnMessage.call(this, event);
          } catch (e) {
            log.error("Error during WebSocket response parse: ", e);
          }
        };
        log.info("Websocket Interception successful");
      } catch (e) {
        log.error("Failed WebSocket interception: ", e);
      }
    });
  }

  const INLINE_RULES = `
    lol-uikit-navigation-item.menu_item_Golden\\ Rose {
      position: relative;
    }

    /* Prevent active state styling for Golden Rose */
    lol-uikit-navigation-item.menu_item_Golden\\ Rose .section.active::before,
    lol-uikit-navigation-item.menu_item_Golden\\ Rose .section.active::after,
    lol-uikit-navigation-item.menu_item_Golden\\ Rose .section.active,
    lol-uikit-navigation-item.menu_item_Golden\\ Rose .section.active .section-glow,
    lol-uikit-navigation-item.menu_item_Golden\\ Rose .section.active .section-glow-container {
      display: none !important;
      background: none !important;
      background-image: none !important;
    }

    /* Prevent hover state from showing navigation pointer */
    lol-uikit-navigation-item.menu_item_Golden\\ Rose .section:hover::after {
      opacity: 0 !important;
      background: none !important;
      background-image: none !important;
    }

    .skin-selection-carousel .skin-selection-item {
      position: relative;
      z-index: 1;
    }

    .skin-selection-carousel .skin-selection-item .skin-selection-item-information {
      position: relative;
      z-index: 2;
    }

    .skin-selection-carousel .skin-selection-item.disabled,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"] {
      filter: grayscale(0) saturate(1.1) contrast(1.05) !important;
      -webkit-filter: grayscale(0) saturate(1.1) contrast(1.05) !important;
      pointer-events: auto !important;
      cursor: pointer !important;
    }

    .skin-selection-carousel .skin-selection-item.disabled .skin-selection-thumbnail,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"] .skin-selection-thumbnail {
      filter: grayscale(0) saturate(1.15) contrast(1.05) !important;
      -webkit-filter: grayscale(0) saturate(1.15) contrast(1.05) !important;
      transition: filter 0.25s ease;
    }

    /* Hover glow effect for owned skins (matching official client) */
    .skin-selection-carousel .skin-selection-item:not(.disabled):not([aria-disabled="true"]):not(.skin-selection-item-selected):hover .skin-selection-thumbnail {
      filter: brightness(1.2) saturate(1.1) !important;
      -webkit-filter: brightness(1.2) saturate(1.1) !important;
      transition: filter 0.25s ease;
    }

    /* Hover glow effect for unowned skins (identical to owned - override base filters on hover) */
    .skin-selection-carousel .skin-selection-item.disabled:not(.skin-selection-item-selected):hover .skin-selection-thumbnail,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"]:not(.skin-selection-item-selected):hover .skin-selection-thumbnail {
      filter: brightness(1.2) saturate(1.1) !important;
      -webkit-filter: brightness(1.2) saturate(1.1) !important;
      transition: filter 0.25s ease;
    }

    .skin-selection-carousel .skin-selection-item.disabled::before,
    .skin-selection-carousel .skin-selection-item.disabled::after,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"]::before,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"]::after,
    .skin-selection-carousel .skin-selection-item.disabled .skin-selection-thumbnail::before,
    .skin-selection-carousel .skin-selection-item.disabled .skin-selection-thumbnail::after,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"] .skin-selection-thumbnail::before,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"] .skin-selection-thumbnail::after {
      display: none !important;
    }

    .skin-selection-carousel .skin-selection-item.disabled .locked-state,
    .skin-selection-carousel .skin-selection-item[aria-disabled="true"] .locked-state {
      display: none !important;
    }

    .skin-selection-carousel .skin-selection-item.${HIDDEN_CLASS} {
      pointer-events: none !important;
    }

    .champion-select .uikit-background-switcher.locked:after {
      background: none !important;
    }

    .unlock-skin-hit-area {
      display: none !important;
      pointer-events: none !important;
    }

    .unlock-skin-hit-area .locked-state {
      display: none !important;
    }

    .skin-selection-carousel-container .skin-selection-carousel .skin-selection-item .skin-selection-thumbnail {
      height: 100% !important;
      margin: 0 !important;
      transition: filter 0.25s ease !important;
      transform: none !important;
    }

    .skin-selection-carousel-container .skin-selection-carousel .skin-selection-item.skin-selection-item-selected {
      background: #3c3c41 !important;
    }

    .skin-selection-carousel-container .skin-selection-carousel .skin-selection-item.skin-selection-item-selected .skin-selection-thumbnail {
      height: 100% !important;
      margin: 0 !important;
    }

    .skin-selection-carousel .skin-selection-item .lpp-skin-border {
      position: absolute;
      inset: -2px;
      border: 2px solid transparent;
      border-image-source: linear-gradient(0deg, #4f4f54 0%, #3c3c41 50%, #29272b 100%);
      border-image-slice: 1;
      border-radius: inherit;
      box-sizing: border-box;
      pointer-events: none;
      z-index: 0;
    }

    .skin-selection-carousel .skin-selection-item.skin-carousel-offset-2 .lpp-skin-border {
      border: 2px solid transparent;
      border-image-source: linear-gradient(0deg, #c8aa6e 0%, #c89b3c 44%, #a07b32 59%, #785a28 100%);
      border-image-slice: 1;
      box-shadow: inset 0 0 0 1px rgba(1, 10, 19, 0.6);
    }

    /* Golden border on hover for all skins (matching official client) */
    .skin-selection-carousel .skin-selection-item:not(.skin-selection-item-selected):hover .lpp-skin-border {
      border: 2px solid transparent;
      border-image-source: linear-gradient(0deg, #c8aa6e 0%, #c89b3c 44%, #a07b32 59%, #785a28 100%);
      border-image-slice: 1;
      box-shadow: inset 0 0 0 1px rgba(1, 10, 19, 0.6);
    }

    .skin-selection-carousel .skin-selection-item .${CHROMA_CONTAINER_CLASS} {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: flex-end;
      justify-content: center;
      pointer-events: none;
      z-index: 4;
      overflow: hidden;
    }

    .skin-selection-carousel .skin-selection-item .${CHROMA_CONTAINER_CLASS} .chroma-button {
      display: none !important;
      pointer-events: none !important;
    }
    /* Rose owns chroma selection; keep the native client flyout closed. */
    .shared-skin-chroma-modal {
      display: none !important;
      pointer-events: none !important;
    }
    .chroma-button.chroma-selection {
      display: none !important;
    }

    /* Remove grey filters and locks */
    .thumbnail-wrapper {
      filter: grayscale(0) saturate(1) contrast(1) !important;
      -webkit-filter: grayscale(0) saturate(1) contrast(1) !important;
    }

    .skin-thumbnail-img {
      filter: grayscale(0) saturate(1) contrast(1) !important;
      -webkit-filter: grayscale(0) saturate(1) contrast(1) !important;
    }

    .locked-state {
      display: none !important;
    }

    .unlock-skin-hit-area {
      display: none !important;
      pointer-events: none !important;
    }

    .skin-selection-carousel-container {
      clip-path: inset(-200px -9999px -9999px -9999px) !important;
    }
    @keyframes rose-rgb-glow {
      0% {
        background-color: hsl(340, 35%, 72%);
        filter: drop-shadow(0 0 3px hsla(340, 35%, 72%, 0.35));
      }
      20% {
        background-color: hsl(280, 25%, 72%);
        filter: drop-shadow(0 0 3px hsla(280, 25%, 72%, 0.35));
      }
      40% {
        background-color: hsl(210, 35%, 72%);
        filter: drop-shadow(0 0 3px hsla(210, 35%, 72%, 0.35));
      }
      60% {
        background-color: hsl(150, 25%, 70%);
        filter: drop-shadow(0 0 3px hsla(150, 25%, 70%, 0.35));
      }
      80% {
        background-color: hsl(35, 35%, 72%);
        filter: drop-shadow(0 0 3px hsla(35, 35%, 72%, 0.35));
      }
      100% {
        background-color: hsl(340, 35%, 72%);
        filter: drop-shadow(0 0 3px hsla(340, 35%, 72%, 0.35));
      }
    }

    /* Применяем мягкую пастельную анимацию к нашей розе */
    body lol-uikit-navigation-item.menu_item_Golden .menu-item-icon-wrapper .menu-item-icon.rose-rgb-icon {
      animation: rose-rgb-glow 12s linear infinite !important;
      background-size: cover !important;
      -webkit-mask-size: 100% 100% !important;
      -webkit-mask-repeat: no-repeat !important;
      transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
    }

    body lol-uikit-navigation-item.menu_item_Golden:hover .menu-item-icon-wrapper .menu-item-icon.rose-rgb-icon {
      transform: scale(1.08) !important;
    }
  `;

  const log = {
    info: (msg, extra) => console.info(`${LOG_PREFIX} ${msg}`, extra ?? ""),
    warn: (msg, extra) => console.warn(`${LOG_PREFIX} ${msg}`, extra ?? ""),
    error: (msg, extra) => console.error(`${LOG_PREFIX} ${msg}`, extra ?? ""),
  };

  function injectInlineRules() {
    if (document.getElementById(INLINE_ID)) return;
    const styleTag = document.createElement("style");
    styleTag.id = INLINE_ID;
    styleTag.textContent = INLINE_RULES;
    document.head.appendChild(styleTag);
    log.info("inline styles applied");
  }

  function ensureBorderFrame(skinItem) {
    if (!skinItem) return;

    let border = skinItem.querySelector(`.${BORDER_CLASS}`);
    if (!border) {
      border = document.createElement("div");
      border.className = BORDER_CLASS;
      border.setAttribute("aria-hidden", "true");
    }

    const chromaContainer = skinItem.querySelector(`.${CHROMA_CONTAINER_CLASS}`);
    if (chromaContainer && border.nextSibling !== chromaContainer) {
      skinItem.insertBefore(border, chromaContainer);
      return;
    }
    if (border.parentElement !== skinItem || border !== skinItem.firstChild) {
      skinItem.insertBefore(border, skinItem.firstChild || null);
    }
  }

  
  function ensureChromaContainer(skinItem) {
    if (!skinItem) return;

    const chromaButton = skinItem.querySelector(".outer-mask .chroma-button");
    if (!chromaButton) return;

    let container = skinItem.querySelector(`.${CHROMA_CONTAINER_CLASS}`);
    if (!container) {
      container = document.createElement("div");
      container.className = CHROMA_CONTAINER_CLASS;
      container.setAttribute("aria-hidden", "true");
      skinItem.appendChild(container);
    } else if (container.parentElement !== skinItem) {
      skinItem.appendChild(container);
    }

    if (container.previousSibling && !container.previousSibling.classList?.contains(BORDER_CLASS)) {
      const border = skinItem.querySelector(`.${BORDER_CLASS}`);
      if (border) skinItem.insertBefore(border, container);
    }
    if (chromaButton.parentElement !== container) container.appendChild(chromaButton);
  }

  function parseCarouselOffset(skinItem) {
    const offsetClass = Array.from(skinItem.classList).find((cls) => cls.startsWith("skin-carousel-offset"));
    if (!offsetClass) return null;
    const match = offsetClass.match(/skin-carousel-offset-(-?\d+)/);
    if (!match) return null;
    const value = Number.parseInt(match[1], 10);
    return Number.isNaN(value) ? null : value;
  }

  function isOffsetVisible(offset) {
    if (offset === null) return true;
    return VISIBLE_OFFSETS.has(offset);
  }

  function applyOffsetVisibility(skinItem) {
    if (!skinItem) return;
    const offset = parseCarouselOffset(skinItem);
    const shouldBeVisible = isOffsetVisible(offset);
    skinItem.classList.toggle("lpp-visible-skin", shouldBeVisible);
    skinItem.classList.toggle(HIDDEN_CLASS, !shouldBeVisible);
    if (shouldBeVisible) skinItem.style.removeProperty("pointer-events");
    else skinItem.style.setProperty("pointer-events", "none", "important");
  }

  function markSkinsAsOwned() {
    document.querySelectorAll(".thumbnail-wrapper.unowned").forEach((wrapper) => {
      wrapper.classList.remove("unowned");
      wrapper.classList.add("owned");
    });
    document.querySelectorAll(".purchase-available").forEach((element) => {
      element.classList.remove("purchase-available");
      element.classList.add("active");
    });
    document.querySelectorAll(".purchase-disabled").forEach((element) => {
      element.classList.remove("purchase-disabled");
    });
  }

  // ---------------------------------------------------------------------------
  // swiftplayBanners is completely rewritten to use backend state!
  // ---------------------------------------------------------------------------
  let lastSwiftplayData = null;
  const swiftplayManualBanners = new Map(); // originalSrc -> newSrc
  const swiftplayHistoricUncentered = new Map(); // champId -> uncenteredSplashUrl (для главного лобби)
  const swiftplayHistoricCentered = new Map(); // champId -> centeredSplashUrl (для меню выбора)
  const swiftplayHistoricCenteredByAlias = new Map(); // alias -> centeredSplashUrl

  function champFolder(src) {
    const match = /\/Characters\/([^/]+)\//i.exec(src || "");
    return match ? match[1].toLowerCase() : null;
  }

  function pickedSplash(wrapper) {
    const thumb = wrapper.querySelector(".skin-thumbnail-img");
    const match = thumb && /url\(["']?([^"')]+)["']?\)/.exec(thumb.style.backgroundImage);
    return match ? match[1].replace("_splash_tile_", "_splash_centered_") : null;
  }

  function clientSplash(img) {
    const src = img.getAttribute("src");
    return img.dataset.roseBanner && src === img.dataset.roseBanner ? img.dataset.roseOriginal : src;
  }

  async function handleSwiftplayState(data) {
    log.info("handleSwiftplayState received", data);
    lastSwiftplayData = data;
    if (!data || !data.active || !data.skins) return;

    swiftplayHistoricUncentered.clear();
    swiftplayHistoricCentered.clear();
    swiftplayHistoricCenteredByAlias.clear();

    for (const skinData of data.skins) {
      const champId = skinData.championId;
      const skinId = skinData.skinId;

      if (skinId % 1000 === 0) continue;

      try {
        const response = await fetch(`/lol-game-data/assets/v1/champions/${champId}.json`);
        if (!response.ok) continue;
        const champJson = await response.json();
        const alias = champJson.alias.toLowerCase();

        let targetSkin = champJson.skins.find((s) => s.id === skinId);
        if (!targetSkin && champJson.skins) {
          for (const s of champJson.skins) {
            if (s.chromas && s.chromas.some((c) => c.id === skinId)) {
              targetSkin = s;
              break;
            }
          }
        }

        if (targetSkin) {
          // 1. Uncentered Splash (для большого фона в лобби за спиной)
          let uncenteredPath = targetSkin.uncenteredSplashPath || targetSkin.splashPath;
          if (uncenteredPath) {
            const fullUncenteredUrl = uncenteredPath.startsWith("/lol-game-data")
              ? uncenteredPath
              : `/lol-game-data/assets/${uncenteredPath.replace(/^\//, "")}`;
            swiftplayHistoricUncentered.set(champId, fullUncenteredUrl);
          }

          // 2. Centered Splash (для узких плашек в меню выбора)
          let tilePath = targetSkin.tilePath;
          if (tilePath) {
            let centeredUrl = tilePath;
            // Превращаем путь тайла в путь центрированного баннера
            if (tilePath.includes("_splash_tile_")) {
              centeredUrl = tilePath.replace("_splash_tile_", "_splash_centered_");
            } else {
              centeredUrl = targetSkin.uncenteredSplashPath || targetSkin.splashPath; // фоллбек
            }
            
            if (!centeredUrl.startsWith("/lol-game-data")) {
              centeredUrl = `/lol-game-data/assets/${centeredUrl.replace(/^\//, "")}`;
            }
            
            swiftplayHistoricCentered.set(champId, centeredUrl);
            swiftplayHistoricCenteredByAlias.set(alias, centeredUrl);
          }
        }
      } catch (e) {
        log.error(`Failed to fetch splash for champ ${champId}`, e);
      }
    }

    applySwiftplayBannerReplacement();
  }

  function applySwiftplayBannerReplacement() {
    if (!lastSwiftplayData || !lastSwiftplayData.skins) return;
    const skins = lastSwiftplayData.skins;

    // 1. Отслеживаем ручной выбор из карусели
    try {
      const activeCarouselSkin = document.querySelector(".quick-play-skin-select-component .thumbnail-wrapper.active-skin");
      const selectedHitboxTile = document.querySelector(".quick-play-loadout-selection-hitbox.selected .champion-slot-tile");
      
      if (activeCarouselSkin && selectedHitboxTile) {
        const original = clientSplash(selectedHitboxTile);
        const picked = pickedSplash(activeCarouselSkin);
        if (original && picked && champFolder(original) === champFolder(picked)) {
          swiftplayManualBanners.set(original, picked);
        }
      }
    } catch (e) {
      log.error("Error tracking manual swiftplay selection", e);
    }

    // 2. Применяем к главным баннерам лобби (за спиной игрока)
    try {
      const localBanner = document.querySelector('.v2-banner-component.local-player');
      if (localBanner) {
        skins.forEach((skinInfo, index) => {
          const { championId } = skinInfo;
          // Для лобби берем UNCENTERED арт
          const bannerUrl = swiftplayHistoricUncentered.get(championId) || skinInfo.bannerUrl;
          if (!bannerUrl) return;

          if (index === 0) {
            localBanner.querySelectorAll('img').forEach(img => {
              if (img.src && img.src.includes('/champion-splashes/') && !img.src.includes(bannerUrl)) {
                img.src = bannerUrl;
              }
            });
            localBanner.querySelectorAll('div, [class*="backdrop"], [class*="background"]').forEach(el => {
              const bg = el.style.backgroundImage;
              if (bg && bg.includes('/champion-splashes/')) {
                const newBg = `url("${bannerUrl}")`;
                if (el.style.backgroundImage !== newBg) {
                  el.style.setProperty('background-image', newBg, 'important');
                }
              }
            });
          }
        });
      }
    } catch (e) {
      log.error("Error applying main lobby banners", e);
    }

    // 3. Применяем к меню выбора (хитбоксы на твоем скриншоте)
    try {
      const loadoutHitboxes = document.querySelectorAll('.quick-play-loadout-selection-hitbox');
      loadoutHitboxes.forEach(hitbox => {
        const tileImg = hitbox.querySelector('.champion-slot-tile');
        if (!tileImg) return;

        const currentSrc = tileImg.getAttribute('src');
        if (!currentSrc) return;

        if (currentSrc !== tileImg.dataset.roseBanner) {
          tileImg.dataset.roseOriginal = currentSrc;
        }
        const originalSrc = tileImg.dataset.roseOriginal;

        // Приоритет 1: Ручной выбор из карусели
        let targetSrc = swiftplayManualBanners.get(originalSrc);

        // Приоритет 2: Исторические данные (CENTERED арт)
        if (!targetSrc) {
          const folder = champFolder(originalSrc);
          if (folder) {
            targetSrc = swiftplayHistoricCenteredByAlias.get(folder);
          }
          if (!targetSrc) {
            const iconImg = hitbox.querySelector('.champion-icon');
            if (iconImg) {
              const match = /\/(\d+)\.png/.exec(iconImg.getAttribute('src') || iconImg.src || "");
              if (match) {
                const champId = parseInt(match[1], 10);
                targetSrc = swiftplayHistoricCentered.get(champId);
              }
            }
          }
        }

        // Применяем новый src
        if (targetSrc && currentSrc !== targetSrc) {
          tileImg.dataset.roseBanner = targetSrc;
          tileImg.setAttribute('src', targetSrc);
        } else if (!targetSrc && tileImg.dataset.roseBanner && currentSrc === tileImg.dataset.roseBanner) {
          tileImg.setAttribute('src', originalSrc);
          delete tileImg.dataset.roseBanner;
        }
      });
    } catch (e) {
      log.error("Error applying loadout hitbox banners", e);
    }
  }

  // Запускаем цикл замены часто, чтобы перебивать рендер Ember.js
  setInterval(() => {
    try {
      applySwiftplayBannerReplacement();
    } catch (e) {}
  }, 150);

  function removeAgeRatingInChampSelect() {
    if (!document.querySelector(".champion-select") && !document.querySelector(".skin-selection-carousel")) return;
    document.querySelectorAll(".vng-age-rating").forEach((el) => el.remove());
    document.querySelectorAll(".vng-age-rating-container").forEach((el) => el.remove());
  }

  function scanSkinSelection() {
    injectInlineRules();

    document.querySelectorAll(".skin-selection-item").forEach((skinItem) => {
      ensureChromaContainer(skinItem);
      ensureBorderFrame(skinItem);
      applyOffsetVisibility(skinItem);
    });

    markSkinsAsOwned();
    removeAgeRatingInChampSelect();
  }

  function setupSkinObserver() {
    const observer = new MutationObserver(() => {
      scanSkinSelection();
      markSkinsAsOwned();
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class"],
    });

    const intervalId = setInterval(() => {
      scanSkinSelection();
      markSkinsAsOwned();
    }, 500);

    const handleResize = () => { scanSkinSelection(); };
    window.addEventListener("resize", handleResize, { passive: true });

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") scanSkinSelection();
    }, false);

    return () => {
      observer.disconnect();
      clearInterval(intervalId);
      window.removeEventListener("resize", handleResize);
    };
  }

  let skinObserverCleanup = null;

  function startSkinObserverGated() {
    if (skinObserverCleanup) return;
    skinObserverCleanup = setupSkinObserver();
  }

  function stopSkinObserverGated() {
    if (!skinObserverCleanup) return;
    try { skinObserverCleanup(); } catch (e) {}
    skinObserverCleanup = null;
  }

  function handlePhaseChangeFromPython(data) {
      const phase = data && data.phase;
      if (!phase) return;
      if (phase === "InProgress") {
        stopSkinObserverGated();
      } else {
        startSkinObserverGated();
        if (phase === "Lobby" && bridge) {
          bridge.send({ type: "request-swiftplay-state" });
        }
      }
    }

  function attachGoldenRoseListeners(navItem) {
    if (navItem.dataset.lppDiscordAttached === "true") return;

    navItem.addEventListener("click", (e) => {
      const lastActiveNavItem = document.querySelector(".main-nav-bar > * > lol-uikit-navigation-item[active]");
      if (lastActiveNavItem) lastActiveNavItem.setAttribute("roseLastActive", true);

      const event = new CustomEvent("rose-open-settings", {
        detail: { navItem: navItem },
        bubbles: true,
        cancelable: true,
      });
      window.dispatchEvent(event);
      log.info("Dispatched rose-open-settings event from Golden Rose button");
    }, true);

    const setupSectionHandlers = () => {
      const section = navItem.querySelector(".section");
      if (section && !section.dataset.lppDiscordHandler) {
        section.dataset.lppDiscordHandler = "true";

        section.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          const event = new CustomEvent("rose-open-settings", {
            detail: { navItem: navItem },
            bubbles: true,
            cancelable: true,
          });
          window.dispatchEvent(event);
          log.info("Dispatched rose-open-settings event from Golden Rose section");
          section.classList.remove("active");
        }, true);

        const activeObserver = new MutationObserver((mutations) => {
          mutations.forEach((mutation) => {
            if (mutation.type === "attributes" && mutation.attributeName === "class") {
              if (section.classList.contains("active")) section.classList.remove("active");
            }
          });
        });
        activeObserver.observe(section, { attributes: true, attributeFilter: ["class"] });
        navItem.dataset.lppActiveObserver = "true";
        return true;
      }
      return false;
    };

    if (!setupSectionHandlers()) {
      const sectionObserver = new MutationObserver(() => {
        if (setupSectionHandlers()) sectionObserver.disconnect();
      });
      sectionObserver.observe(navItem, { childList: true, subtree: true });
      setTimeout(() => {
        setupSectionHandlers();
        sectionObserver.disconnect();
      }, 500);
    }

    navItem.dataset.lppDiscordAttached = "true";
  }

  function injectGoldenRoseNavItem() {
    const rightNavMenu = document.querySelector(".right-nav-menu");
    if (!rightNavMenu) return false;

    const existingItem = rightNavMenu.querySelector(
      'lol-uikit-navigation-item .menu-item-icon[style*="golden_rose.png"]'
    );
    if (existingItem) {
      existingItem.classList.add("rose-rgb-icon");
      const navItem = existingItem.closest("lol-uikit-navigation-item");
      if (navItem) attachGoldenRoseListeners(navItem);
      return true;
    }

    const navItem = document.createElement("lol-uikit-navigation-item");
    navItem.id = `ember${Date.now()}`;
    navItem.className = "main-navigation-menu-item menu_item_Golden Rose ember-view";

    const iconWrapper = document.createElement("div");
    iconWrapper.className = "menu-item-icon-wrapper";

    const glow = document.createElement("div");
    glow.className = "menu-item-glow";

    const icon = document.createElement("div");
    icon.className = "menu-item-icon rose-rgb-icon";
    icon.style.webkitMaskImage = `url(http://127.0.0.1:${
      window.__roseBridge ? window.__roseBridge.port : 50000
    }/asset/golden_rose.png)`;

    iconWrapper.appendChild(glow);
    iconWrapper.appendChild(icon);
    navItem.appendChild(iconWrapper);

    const firstChild = rightNavMenu.firstChild;
    if (firstChild) rightNavMenu.insertBefore(navItem, firstChild);
    else rightNavMenu.appendChild(navItem);

    const separator = document.createElement("div");
    separator.className = "right-nav-vertical-rule";
    rightNavMenu.insertBefore(separator, navItem.nextSibling);

    attachGoldenRoseListeners(navItem);

    log.info("Golden Rose navigation item injected");
    return true;
  }

  function setupNavObserver() {
    if (injectGoldenRoseNavItem()) return;

    const observer = new MutationObserver(() => {
      if (injectGoldenRoseNavItem()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    const intervalId = setInterval(() => {
      if (injectGoldenRoseNavItem()) {
        clearInterval(intervalId);
        observer.disconnect();
      }
    }, 500);
  }

  let _initializing = false;
  let _initialized = false;
  let _retryCount = 0;
  const MAX_RETRIES = 100;

  async function init() {
    if (_initialized) return;

    if (_initializing) {
      if (!document || !document.head) {
        if (_retryCount >= MAX_RETRIES) {
          log.error(`Init failed: Maximum retry count (${MAX_RETRIES}) reached. Document still not ready.`);
          _initializing = false;
          _retryCount = 0;
          return;
        }
        _retryCount++;
        requestAnimationFrame(() => {
          init().catch((err) => {
            log.error("Init failed:", err);
            _initializing = false;
          });
        });
        return;
      }
    } else {
      _initializing = true;

      if (!document || !document.head) {
        if (_retryCount >= MAX_RETRIES) {
          log.error(`Init failed: Maximum retry count (${MAX_RETRIES}) reached. Document still not ready.`);
          _initializing = false;
          _retryCount = 0;
          return;
        }
        _retryCount++;
        requestAnimationFrame(() => {
          init().catch((err) => {
            log.error("Init failed:", err);
            _initializing = false;
          });
        });
        return;
      }
    }

    try {
      const bridge = await waitForBridge();

      bridge.subscribe("skip-base-skin", handleSkipBaseSkin);
      bridge.subscribe("phase-change", handlePhaseChangeFromPython);
      bridge.subscribe("swiftplay-state", handleSwiftplayState); // NEW: Listen to swiftplay state

      setupPenguWelcomeBadgeFix();

      interceptChampSelectWebsocket();
      injectInlineRules();
      scanSkinSelection();
      startSkinObserverGated();
      setupNavObserver();
      log.info("skin preview overrides active");
      _initialized = true;
      _retryCount = 0;
    } catch (err) {
      log.error("Init failed:", err);
      throw err;
    } finally {
      _initializing = false;
    }
  }

  if (typeof document === "undefined") {
    log.warn("document unavailable; aborting");
    return;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      init().catch((err) => { log.error("Init failed:", err); });
    }, { once: true });
  } else {
    init().catch((err) => { log.error("Init failed:", err); });
  }
  
})();