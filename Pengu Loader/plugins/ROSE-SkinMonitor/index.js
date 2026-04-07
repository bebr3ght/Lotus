/**
 * @name Rose-SkinMonitor
 * @author Rose Team
 * @description Skin monitor for Pengu Loader
 * @link https://github.com/Alban1911/Rose-SkinMonitor
 */

console.log("[SkinMonitor] Plugin loaded");

const LOG_PREFIX = "[SkinMonitor]";
const STATE_EVENT = "lu-skin-monitor-state";
const SKIN_SELECTORS = [
  ".skin-name-text", // Classic Champ Select
  ".skin-name", // Swiftplay lobby
];
const POLL_INTERVAL_MS = 250;
const RETRY_BASE_MS = 1000;
const RETRY_MAX_MS = 30000;
let BRIDGE_PORT = 50000; // Default, will be updated from /bridge-port endpoint
let BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
const BRIDGE_PORT_STORAGE_KEY = "rose_bridge_port";
const DISCOVERY_START_PORT = 50000;
const DISCOVERY_END_PORT = 50010;

async function loadBridgePort() {
  try {
    // First, check localStorage for cached port
    const cachedPort = localStorage.getItem(BRIDGE_PORT_STORAGE_KEY);
    if (cachedPort) {
      const port = parseInt(cachedPort, 10);
      if (!isNaN(port) && port > 0) {
        // Verify cached port is still valid with shorter timeout
        try {
          const response = await fetch(`http://127.0.0.1:${port}/bridge-port`, {
            signal: AbortSignal.timeout(50)
          });
          if (response.ok) {
            const portText = await response.text();
            const fetchedPort = parseInt(portText.trim(), 10);
            if (!isNaN(fetchedPort) && fetchedPort > 0) {
              BRIDGE_PORT = fetchedPort;
              BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
              console.log(`${LOG_PREFIX} Loaded bridge port from cache: ${BRIDGE_PORT}`);
              return true;
            }
          }
        } catch (e) {
          // Cached port invalid, continue to discovery
          localStorage.removeItem(BRIDGE_PORT_STORAGE_KEY);
        }
      }
    }

    // OPTIMIZATION: Try default port 50000 FIRST before scanning all ports
    try {
      const response = await fetch(`http://127.0.0.1:50000/bridge-port`, {
        signal: AbortSignal.timeout(50)
      });
      if (response.ok) {
        const portText = await response.text();
        const fetchedPort = parseInt(portText.trim(), 10);
        if (!isNaN(fetchedPort) && fetchedPort > 0) {
          BRIDGE_PORT = fetchedPort;
          BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
          localStorage.setItem(BRIDGE_PORT_STORAGE_KEY, String(BRIDGE_PORT));
          console.log(`${LOG_PREFIX} Loaded bridge port: ${BRIDGE_PORT}`);
          return true;
        }
      }
    } catch (e) {
      // Port 50000 not ready, continue to discovery
    }

    // OPTIMIZATION: Try fallback port 50001 SECOND
    try {
      const response = await fetch(`http://127.0.0.1:50001/bridge-port`, {
        signal: AbortSignal.timeout(50)
      });
      if (response.ok) {
        const portText = await response.text();
        const fetchedPort = parseInt(portText.trim(), 10);
        if (!isNaN(fetchedPort) && fetchedPort > 0) {
          BRIDGE_PORT = fetchedPort;
          BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
          localStorage.setItem(BRIDGE_PORT_STORAGE_KEY, String(BRIDGE_PORT));
          console.log(`${LOG_PREFIX} Loaded bridge port: ${BRIDGE_PORT}`);
          return true;
        }
      }
    } catch (e) {
      // Port 50001 not ready, continue to discovery
    }

    // OPTIMIZATION: Parallel port discovery instead of sequential
    // Try all ports at once, return as soon as one succeeds
    const portPromises = [];
    for (let port = DISCOVERY_START_PORT; port <= DISCOVERY_END_PORT; port++) {
      portPromises.push(
        fetch(`http://127.0.0.1:${port}/bridge-port`, {
          signal: AbortSignal.timeout(100)
        })
          .then(response => {
            if (response.ok) {
              return response.text().then(portText => {
                const fetchedPort = parseInt(portText.trim(), 10);
                if (!isNaN(fetchedPort) && fetchedPort > 0) {
                  return { port: fetchedPort, sourcePort: port };
                }
                return null;
              });
            }
            return null;
          })
          .catch(() => null)
      );
    }

    // Wait for first successful response
    const results = await Promise.allSettled(portPromises);
    for (const result of results) {
      if (result.status === 'fulfilled' && result.value) {
        BRIDGE_PORT = result.value.port;
        BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
        localStorage.setItem(BRIDGE_PORT_STORAGE_KEY, String(BRIDGE_PORT));
        console.log(`${LOG_PREFIX} Loaded bridge port: ${BRIDGE_PORT}`);
        return true;
      }
    }

    // Fallback: try old /port endpoint (parallel as well)
    const legacyPromises = [];
    for (let port = DISCOVERY_START_PORT; port <= DISCOVERY_END_PORT; port++) {
      legacyPromises.push(
        fetch(`http://127.0.0.1:${port}/port`, {
          signal: AbortSignal.timeout(100)
        })
          .then(response => {
            if (response.ok) {
              return response.text().then(portText => {
                const fetchedPort = parseInt(portText.trim(), 10);
                if (!isNaN(fetchedPort) && fetchedPort > 0) {
                  return { port: fetchedPort, sourcePort: port };
                }
                return null;
              });
            }
            return null;
          })
          .catch(() => null)
      );
    }

    const legacyResults = await Promise.allSettled(legacyPromises);
    for (const result of legacyResults) {
      if (result.status === 'fulfilled' && result.value) {
        BRIDGE_PORT = result.value.port;
        BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
        localStorage.setItem(BRIDGE_PORT_STORAGE_KEY, String(BRIDGE_PORT));
        console.log(`${LOG_PREFIX} Loaded bridge port (legacy): ${BRIDGE_PORT}`);
        return true;
      }
    }

    console.warn(`${LOG_PREFIX} Failed to load bridge port, using default (50000)`);
    return false;
  } catch (e) {
    console.warn(`${LOG_PREFIX} Error loading bridge port:`, e);
    return false;
  }
}

let lastLoggedSkin = null;
let pollTimer = null;
let observer = null;
let bridgeSocket = null;
let bridgeReady = false;
let bridgeQueue = [];
let bridgeErrorLogged = false;
let bridgeSetupWarned = false;
let retryTimer = null;
let stopped = false;
let retryDelay = RETRY_BASE_MS;

// --- Bridge subscription infrastructure ---
const _subscribers = new Map(); // type -> Set<callback>
const _readyCallbacks = new Set();

function subscribe(type, cb) {
  if (!_subscribers.has(type)) _subscribers.set(type, new Set());
  _subscribers.get(type).add(cb);
}

function unsubscribe(type, cb) {
  const subs = _subscribers.get(type);
  if (subs) subs.delete(cb);
}

function onReady(cb) {
  _readyCallbacks.add(cb);
  if (bridgeReady) cb();
}

function _notifySubscribers(data) {
  if (!data || !data.type) return;
  const subs = _subscribers.get(data.type);
  if (!subs) return;
  for (const cb of subs) {
    try { cb(data); } catch (e) {
      console.warn(`${LOG_PREFIX} Subscriber error for "${data.type}":`, e);
    }
  }
}

function _notifyReady() {
  for (const cb of _readyCallbacks) {
    try { cb(); } catch (e) {
      console.warn(`${LOG_PREFIX} onReady callback error:`, e);
    }
  }
}

function sanitizeSkinName(name) {
  // Keep the raw UI name intact.
  // Any matching/normalization (including chroma suffix handling) should happen server-side.
  return String(name || "").trim();
}

function resyncSkinAfterConnect() {
  try {
    // On reconnect, backend may have missed the last hover (or hover happened before lock).
    // Send a best-effort snapshot immediately so injection doesn't depend on a new hover.
    const current = readCurrentSkin();
    const name = current || lastLoggedSkin || null;
    if (!name) return;

    // Match logHover() sanitization
    const cleanName = sanitizeSkinName(name);
    if (!cleanName) return;

    sendBridgePayload({
      type: "skin-sync",
      skin: cleanName,
      originalName: name,
      timestamp: Date.now(),
    });
  } catch {
    // ignore
  }
}

function publishSkinState(payload) {
  // Use payload name, fallback to lastLoggedSkin if available (improves reliability if backend doesn't echo name)
  const name = payload?.skinName || lastLoggedSkin || null;

  const detail = {
    name: name,
    skinId: Number.isFinite(payload?.skinId) ? payload.skinId : null,
    championId: Number.isFinite(payload?.championId)
      ? payload.championId
      : null,
    hasChromas: Boolean(payload?.hasChromas),
    updatedAt: Date.now(),
  };
  window.__roseSkinState = detail;
  try {
    window.__roseCurrentSkin = detail.name;
    // Update lastLoggedSkin to match ensuring consistency if payload brought a new name
    if (name) lastLoggedSkin = name;
  } catch {
    // ignore
  }
  window.dispatchEvent(new CustomEvent(STATE_EVENT, { detail }));
}

function logHover(skinName) {
  // Sanitize skin name (currently: keep raw text, only trim).
  const cleanName = sanitizeSkinName(skinName);

  if (cleanName !== skinName) {
    console.log(`${LOG_PREFIX} Sanitized skin name: '${skinName}' -> '${cleanName}'`);
  }

  console.log(`${LOG_PREFIX} Hovered skin: ${cleanName}`);
  sendBridgePayload({ skin: cleanName, originalName: skinName, timestamp: Date.now() });
}

function sendBridgePayload(obj) {
  try {
    const payload = JSON.stringify(obj);
    sendToBridge(payload);
  } catch (error) {
    console.warn(`${LOG_PREFIX} Failed to serialize bridge payload`, error);
  }
}

// window.__roseBridge is exposed in start() after port discovery completes,
// so that consumer plugins' waitForBridge() won't resolve until the port is known.
if (typeof window !== "undefined") {
  window.__roseBridgeEmit = sendBridgePayload; // backward compat (available early)
}

function sendToBridge(payload) {
  if (
    !bridgeSocket ||
    bridgeSocket.readyState === WebSocket.CLOSING ||
    bridgeSocket.readyState === WebSocket.CLOSED
  ) {
    bridgeQueue.push(payload);
    setupBridgeSocket();
    return;
  }

  if (bridgeSocket.readyState === WebSocket.CONNECTING) {
    bridgeQueue.push(payload);
    return;
  }

  try {
    bridgeSocket.send(payload);
  } catch (error) {
    console.warn(`${LOG_PREFIX} Bridge send failed`, error);
    bridgeQueue.push(payload);
    resetBridgeSocket();
  }
}

function setupBridgeSocket() {
  if (stopped) {
    return;
  }

  if (
    bridgeSocket &&
    (bridgeSocket.readyState === WebSocket.OPEN ||
      bridgeSocket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  try {
    bridgeSocket = new WebSocket(BRIDGE_URL);
  } catch (error) {
    if (!bridgeSetupWarned) {
      console.warn(`${LOG_PREFIX} Bridge socket setup failed`, error);
      bridgeSetupWarned = true;
    }
    scheduleBridgeRetry();
    return;
  }

  bridgeSocket.addEventListener("open", () => {
    bridgeReady = true;
    retryDelay = RETRY_BASE_MS;
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    flushBridgeQueue();
    resyncSkinAfterConnect();
    bridgeErrorLogged = false;
    bridgeSetupWarned = false;
    window.__roseBridgeEmit = sendBridgePayload;
    _notifyReady();
  });

  bridgeSocket.addEventListener("message", (event) => {
    let data = null;
    try {
      data = JSON.parse(event.data);
    } catch (error) {
      console.log(`${LOG_PREFIX} Bridge message: ${event.data}`);
      return;
    }

    // Notify all bridge subscribers
    _notifySubscribers(data);

    if (data && data.type === "skin-state") {
      publishSkinState(data);
      return;
    }

    if (data && data.type === "skin-mods-response") {
      window.dispatchEvent(
        new CustomEvent("rose-custom-wheel-skin-mods", { detail: data })
      );
      return;
    }

    if (data && data.type === "maps-response") {
      window.dispatchEvent(
        new CustomEvent("rose-custom-wheel-maps", { detail: data })
      );
      return;
    }

    if (data && data.type === "fonts-response") {
      window.dispatchEvent(
        new CustomEvent("rose-custom-wheel-fonts", { detail: data })
      );
      return;
    }

    if (data && data.type === "announcers-response") {
      window.dispatchEvent(
        new CustomEvent("rose-custom-wheel-announcers", { detail: data })
      );
      return;
    }

    if (data && data.type === "category-mods-response") {
      window.dispatchEvent(
        new CustomEvent("rose-custom-wheel-category-mods", { detail: data })
      );
      return;
    }

    if (data && data.type === "others-response") {
      window.dispatchEvent(
        new CustomEvent("rose-custom-wheel-others", { detail: data })
      );
      return;
    }

    // Reset skin state when entering Lobby phase (so same skin in next game triggers detection)
    if (data && data.type === "champion-locked") {
      window.dispatchEvent(
        new CustomEvent("rose-custom-wheel-champion-locked", { detail: data })
      );
      return;
    }

    if (data && data.type === "phase-change" && data.phase === "Lobby") {
      lastLoggedSkin = null;
      console.log(`${LOG_PREFIX} Reset skin state for new game (Lobby phase)`);
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-reset"));
      return;
    }

    console.log(`${LOG_PREFIX} Bridge message: ${event.data}`);
  });

  bridgeSocket.addEventListener("close", () => {
    bridgeReady = false;
    scheduleBridgeRetry();
  });

  bridgeSocket.addEventListener("error", (error) => {
    if (!bridgeErrorLogged) {
      console.warn(`${LOG_PREFIX} Bridge socket error`, error);
      bridgeErrorLogged = true;
    }
    bridgeReady = false;
    scheduleBridgeRetry();
  });
}

function flushBridgeQueue() {
  if (!bridgeSocket || bridgeSocket.readyState !== WebSocket.OPEN) {
    return;
  }

  while (bridgeQueue.length) {
    const payload = bridgeQueue.shift();
    try {
      bridgeSocket.send(payload);
    } catch (error) {
      console.warn(`${LOG_PREFIX} Bridge flush failed`, error);
      bridgeQueue.unshift(payload);
      resetBridgeSocket();
      break;
    }
  }
}

function scheduleBridgeRetry() {
  if (bridgeReady || stopped) {
    return;
  }

  if (retryTimer) {
    return;
  }

  retryTimer = setTimeout(() => {
    retryTimer = null;
    setupBridgeSocket();
  }, retryDelay);
  retryDelay = Math.min(retryDelay * 2, RETRY_MAX_MS);
}

function resetBridgeSocket() {
  if (bridgeSocket) {
    try {
      bridgeSocket.close();
    } catch (error) {
      console.warn(`${LOG_PREFIX} Bridge socket close failed`, error);
    }
  }

  bridgeSocket = null;
  bridgeReady = false;
}

function isVisible(element) {
  if (typeof element.offsetParent === "undefined") {
    return true;
  }
  return element.offsetParent !== null;
}

function readCurrentSkin() {
  for (const selector of SKIN_SELECTORS) {
    const nodes = document.querySelectorAll(selector);
    if (!nodes.length) {
      continue;
    }

    let candidate = null;

    nodes.forEach((node) => {
      const name = node.textContent.trim();
      if (!name) {
        return;
      }

      if (isVisible(node)) {
        candidate = name;
      } else if (!candidate) {
        candidate = name;
      }
    });

    if (candidate) {
      return candidate;
    }
  }

  return null;
}

function reportSkinIfChanged() {
  const name = readCurrentSkin();
  if (!name || name === lastLoggedSkin) {
    return;
  }

  lastLoggedSkin = name;
  logHover(name);
}

function attachObservers() {
  if (observer) {
    observer.disconnect();
  }

  observer = new MutationObserver(reportSkinIfChanged);
  observer.observe(document.body, { childList: true, subtree: true });

  document.querySelectorAll("*").forEach((node) => {
    if (!node.shadowRoot || !(node.shadowRoot instanceof Node)) {
      return;
    }

    try {
      observer.observe(node.shadowRoot, { childList: true, subtree: true });
    } catch (error) {
      console.warn(`${LOG_PREFIX} Cannot observe shadowRoot`, error);
    }
  });

  if (!pollTimer) {
    pollTimer = setInterval(reportSkinIfChanged, POLL_INTERVAL_MS);
  }
}

function installFindMatchObserver() {
  try {
    const po = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.name && entry.name.includes("sfx-lobby-button-find-match-hover")) {
          console.log(`${LOG_PREFIX} Find-Match hover detected via PerformanceObserver`);
          sendBridgePayload({ type: "find-match-hover", timestamp: Date.now() });
        }
      }
    });
    po.observe({ type: "resource", buffered: false });
    console.log(`${LOG_PREFIX} Find-Match observer installed`);
  } catch (e) {
    console.warn(`${LOG_PREFIX} Failed to install Find-Match observer`, e);
  }
}

// ====== SWIFTPLAY SMART PANEL (FULL TEXT & STABLE HIDE) ======
function updateSwiftplaySmartPanel(data) {
    let panel = document.getElementById('rose-swiftplay-smart-panel');
    
    // ПРОВЕРКА: Видны ли баннеры игроков? (Это признак того, что мы ВНУТРИ лобби, а не в меню выбора)
    const lobbyBanners = document.querySelector('.v2-banner-component.local-player');
    const isVisibleInDOM = lobbyBanners && lobbyBanners.offsetParent !== null;
    
    // Если мы не в лобби или данных нет - прячем мгновенно
    if (!data.active || !isVisibleInDOM || !data.skins || data.skins.length === 0) {
        if (panel) panel.style.display = 'none';
        return;
    }

    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'rose-swiftplay-smart-panel';
        panel.innerHTML = `
            <div class="rsp-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c8aa6e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                <span>Swiftplay Locks</span>
            </div>
            <div class="rsp-body" id="rsp-skins-container"></div>
        `;
        document.body.appendChild(panel);
        
        const style = document.createElement('style');
        style.textContent = `
            #rose-swiftplay-smart-panel {
                position: fixed;
                bottom: 100px;
                left: 30px;
                background: rgba(1, 10, 19, 0.98);
                border: 1px solid #463714;
                border-top: 2px solid #c8aa6e;
                padding: 12px;
                z-index: ;
                display: flex;
                flex-direction: column;
                gap: 10px;
                box-shadow: 0 8px 16px rgba(0,0,0,0.8);
                min-width: 260px;
                max-width: 450px; /* Чтобы не на весь экран, но достаточно широко */
                pointer-events: none;
            }
            .rsp-header {
                color: #c8aa6e;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
                display: flex;
                align-items: center; gap: 8px;
                margin-bottom: 4px;
                border-bottom: 1px solid rgba(200, 170, 110, 0.2);
                padding-bottom: 6px;
            }
            .rsp-item { display: flex; align-items: flex-start; gap: 12px; margin: 4px 0; }
            .rsp-icon { width: 34px; height: 34px; border-radius: 50%; border: 1px solid #785a28; flex-shrink: 0; }
            .rsp-text { display: flex; flex-direction: column; min-width: 0; }
            .rsp-champ { color: #a09b8c; font-size: 9px; text-transform: uppercase; font-weight: bold; }
            
            /* СТИЛЬ ДЛЯ ПОЛНОГО НАЗВАНИЯ */
            .rsp-skin { 
                color: #f0e6d2; 
                font-size: 13px; 
                font-weight: bold; 
                line-height: 1.2;
                white-space: normal; /* Разрешаем перенос */
                word-wrap: break-word; /* Переносим длинные слова */
                overflow: visible; 
                text-overflow: clip; 
            }
        `;
        document.head.appendChild(style);
    }

    const container = document.getElementById('rsp-skins-container');
        container.innerHTML = data.skins.map(skin => {
            // Если скин куплен официально, делаем красивый бейдж
            const ownedBadge = skin.isOwned 
                ? `<span style="color: #0acbe6; font-size: 10px; margin-left: 6px; text-shadow: 0 0 4px rgba(10, 203, 230, 0.5); vertical-align: baseline;">✔ OWNED</span>` 
                : '';
                
            // Если куплен — меняем цвет рамки иконки
            const borderColor = skin.isOwned ? '#0acbe6' : '#785a28';
            const opacity = skin.isOwned ? '0.85' : '1';
            
            return `
                <div class="rsp-item" style="opacity: ${opacity};">
                    <img class="rsp-icon" src="/lol-game-data/assets/v1/champion-icons/${skin.championId}.png" style="border-color: ${borderColor};">
                    <div class="rsp-text">
                        <span class="rsp-champ">${skin.championName}</span>
                        <span class="rsp-skin">${skin.skinName}${ownedBadge}</span>
                    </div>
                </div>
            `;
        }).join('');
        
        // Включаем панель ТОЛЬКО если в этот момент руны не открыты
        if (!isOverlayOpen()) {
            panel.style.display = 'flex';
        }
}

// ====== УЛУЧШЕННЫЙ КОНТРОЛЛЕР ВИДИМОСТИ (БЕЗ ЗАДЕРЖЕК) ======

function isActuallyInLobby() {
    const lobbyBanners = document.querySelector('.v2-banner-component.local-player');
    return !!(lobbyBanners && lobbyBanners.offsetParent !== null);
}

let isPanelRequested = false; // Флаг от спама запросов

function isOverlayOpen() {
    const overlays =[
        'lol-perks-v2-editor',           
        'lol-perks-v2-main-view',        
        '.perks-editor-modal',           
        'lol-uikit-full-page-modal',     
        '.champion-customization-flyout',
        'lol-uikit-dialog-frame',        
        '.modal-root'                    
    ];

    for (const selector of overlays) {
        const el = document.querySelector(selector);
        if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) return true;
    }
    
    const backdrop = document.querySelector('.lol-uikit-layer-manager-wrapper');
    if (backdrop && backdrop.children.length > 1) return true;

    return false;
}

// Глобальная функция решения: показывать панель или нет
function shouldShowSmartPanel() {
    return isActuallyInLobby() && !isOverlayOpen();
}

setInterval(() => {
    const panel = document.getElementById('rose-swiftplay-smart-panel');
    if (!panel) return;

    const inLobby = isActuallyInLobby();
    const overlayActive = isOverlayOpen();

    const shouldShow = inLobby && !overlayActive;

    if (shouldShow) {
        // КРИТИЧЕСКИЙ ФИКС: Мы НЕ делаем panel.style.display = 'flex' здесь!
        // Мы только просим бэкенд дать нам актуальные данные, если еще не просили.
        if (panel.style.display === 'none' && !isPanelRequested) {
            isPanelRequested = true; // Запоминаем, что послали запрос
            if (window.__roseBridge && window.__roseBridge.ready) {
                window.__roseBridge.send({type: "request-swiftplay-state"});
            }
        }
    } else {
        // Если открыты руны или вышли из лобби — жестко прячем
        if (panel.style.display !== 'none') {
            panel.style.display = 'none';
        }
        isPanelRequested = false; // Сбрасываем флаг, чтобы при возврате снова запросить
    }
}, 150);

// Реактивное скрытие через события фаз (доп. страховка)
function setupPhaseSubscription() {
    if (window.__roseBridge && window.__roseBridge.subscribe) {
        window.__roseBridge.subscribe("phase-change", (data) => {
            const panel = document.getElementById('rose-swiftplay-smart-panel');
            if (panel && data.phase !== "Lobby") {
                panel.style.display = 'none';
            }
        });
    } else {
        setTimeout(setupPhaseSubscription, 500);
    }
}
setupPhaseSubscription();

async function start() {
  if (!document.body) {
    console.log(`${LOG_PREFIX} Waiting for document.body...`);
    setTimeout(start, 250);
    return;
  }

  stopped = false;
  retryDelay = RETRY_BASE_MS;

  // Load bridge port before initializing socket
  await loadBridgePort();

  // Expose the shared bridge API now that the port is known.
  // Consumer plugins poll for this object via waitForBridge().
  if (typeof window !== "undefined") {
    window.__roseBridge = Object.freeze({
      send: sendBridgePayload,
      subscribe,
      unsubscribe,
      onReady,
      get port() { return BRIDGE_PORT; },
      get ready() { return bridgeReady; },
    });
    
    subscribe("swiftplay-state", updateSwiftplaySmartPanel);
    subscribe("phase-change", (data) => { 
      // Запрашиваем состояние свифтплея, чтобы обновить (или убить) панель
      if (bridgeSocket && bridgeReady) {
          sendBridgePayload({type: "request-swiftplay-state"});
      }
      // Жестко прячем панель, если мы вышли из лобби
      if (data.phase !== "Lobby") {
          const panel = document.getElementById('rose-swiftplay-smart-panel');
          if (panel) panel.style.display = 'none';
      }
    });
  }

  installFindMatchObserver();
  setupBridgeSocket();
  attachObservers();
  reportSkinIfChanged();
}

function stop() {
  stopped = true;

  if (retryTimer) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }

  if (observer) {
    observer.disconnect();
    observer = null;
  }

  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }

  if (bridgeSocket) {
    bridgeSocket.close();
    bridgeSocket = null;
  }
}

function whenReady(callback) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", callback, { once: true });
    return;
  }

  callback();
}

whenReady(start);
window.addEventListener("beforeunload", stop);
