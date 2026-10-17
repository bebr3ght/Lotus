/**
 * @name Rose-SkinMonitor
 * @author Rose Team
 * @description Skin monitor for Pengu Loader
 * @link https://github.com/Alban1911/Rose-SkinMonitor
 */

console.log("[SkinMonitor] Plugin loaded");

const LOG_PREFIX = "[SkinMonitor]";
let skinSyncErrorLogged = false;
const STATE_EVENT = "lu-skin-monitor-state";
const SKIN_SELECTORS = [
  ".skin-name-text", // Classic Champ Select
  ".skins-pane__skin-title", // Rift Classic (JADE) Champ Select
  ".skin-name", // Swiftplay lobby
];
const POLL_INTERVAL_MS = 250;
const RETRY_BASE_MS = 1000;
const RETRY_MAX_MS = 30000;

let BRIDGE_PORT = 50000;
let BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
const BRIDGE_PORT_STORAGE_KEY = "rose_bridge_port";
// Every port Rose's bridge can take (BRIDGE_FIRST_PORT, BRIDGE_PORT_COUNT in pengu/core/skin_monitor.py)
const DISCOVERY_START_PORT = 50000;
const DISCOVERY_END_PORT = 50099;

async function loadBridgePort() {
  try {
    const cachedPort = localStorage.getItem(BRIDGE_PORT_STORAGE_KEY);
    if (cachedPort) {
      const port = parseInt(cachedPort, 10);
      if (!isNaN(port) && port > 0) {
        try {
          const response = await fetch(`http://127.0.0.1:${port}/bridge-port`, {
            signal: AbortSignal.timeout(50),
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
          localStorage.removeItem(BRIDGE_PORT_STORAGE_KEY);
        }
      }
    }

    try {
      const response = await fetch(`http://127.0.0.1:50000/bridge-port`, {
        signal: AbortSignal.timeout(50),
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
    } catch (e) {}

    try {
      const response = await fetch(`http://127.0.0.1:50001/bridge-port`, {
        signal: AbortSignal.timeout(50),
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
    } catch (e) {}

    const portPromises = [];
    for (let port = DISCOVERY_START_PORT; port <= DISCOVERY_END_PORT; port++) {
      portPromises.push(
        fetch(`http://127.0.0.1:${port}/bridge-port`, { signal: AbortSignal.timeout(100) })
          .then((response) => {
            if (response.ok) {
              return response.text().then((portText) => {
                const fetchedPort = parseInt(portText.trim(), 10);
                if (!isNaN(fetchedPort) && fetchedPort > 0) return { port: fetchedPort, sourcePort: port };
                return null;
              });
            }
            return null;
          })
          .catch(() => null)
      );
    }
    const results = await Promise.allSettled(portPromises);
    for (const result of results) {
      if (result.status === "fulfilled" && result.value) {
        BRIDGE_PORT = result.value.port;
        BRIDGE_URL = `ws://127.0.0.1:${BRIDGE_PORT}`;
        localStorage.setItem(BRIDGE_PORT_STORAGE_KEY, String(BRIDGE_PORT));
        console.log(`${LOG_PREFIX} Loaded bridge port: ${BRIDGE_PORT}`);
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

const _subscribers = new Map();
const _readyCallbacks = new Set();
const _disconnectCallbacks = new Set();

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

// Called when an open connection to Rose closes (not on failed reconnect attempts)
function onDisconnect(cb) {
  _disconnectCallbacks.add(cb);
}

function _notifySubscribers(data) {
  if (!data || !data.type) return;
  const subs = _subscribers.get(data.type);
  if (!subs) return;
  for (const cb of subs) {
    try { cb(data); } catch (e) { console.warn(`${LOG_PREFIX} Subscriber error for "${data.type}":`, e); }
  }
}
function _notifyReady() {
  for (const cb of _readyCallbacks) {
    try { cb(); } catch (e) { console.warn(`${LOG_PREFIX} onReady callback error:`, e); }
  }
}

function _notifyDisconnect() {
  for (const cb of _disconnectCallbacks) {
    try { cb(); } catch (e) {
      console.warn(`${LOG_PREFIX} onDisconnect callback error:`, e);
    }
  }
}

function sanitizeSkinName(name) {
  return String(name || "").trim();
}

function resyncSkinAfterConnect() {
  try {
    const current = readCurrentSkin();
    const name = current || lastLoggedSkin || null;
    if (!name) return;

    const cleanName = sanitizeSkinName(name);
    if (!cleanName) return;

    sendBridgePayload({
      type: "skin-sync",
      skin: cleanName,
      originalName: name,
      timestamp: Date.now(),
    });
  } catch (e) {
    // Rose would inject without knowing the hovered skin: say why, once
    if (!skinSyncErrorLogged) {
      skinSyncErrorLogged = true;
      console.warn(`${LOG_PREFIX} Could not send the hovered skin to Rose:`, e);
    }
  }
}

function publishSkinState(payload) {
  const name = payload?.skinName || lastLoggedSkin || null;

  const detail = {
    name: name,
    skinId: Number.isFinite(payload?.skinId) ? payload.skinId : null,
    championId: Number.isFinite(payload?.championId) ? payload.championId : null,
    hasChromas: Boolean(payload?.hasChromas),
    updatedAt: Date.now(),
  };
  window.__roseSkinState = detail;
  try {
    window.__roseCurrentSkin = detail.name;
    if (name) lastLoggedSkin = name;
  } catch {}
  window.dispatchEvent(new CustomEvent(STATE_EVENT, { detail }));
}

function logHover(skinName) {
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

if (typeof window !== "undefined") {
  window.__roseBridgeEmit = sendBridgePayload;
}

function sendToBridge(payload) {
  if (!bridgeSocket || bridgeSocket.readyState === WebSocket.CLOSING || bridgeSocket.readyState === WebSocket.CLOSED) {
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
  if (stopped) return;
  if (bridgeSocket && (bridgeSocket.readyState === WebSocket.OPEN || bridgeSocket.readyState === WebSocket.CONNECTING)) return;

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

  let opened = false;
  bridgeSocket.addEventListener("open", () => {
    opened = true;
    bridgeReady = true;
    retryDelay = RETRY_BASE_MS;
    if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
    flushBridgeQueue();
    resyncSkinAfterConnect();
    bridgeErrorLogged = false;
    bridgeSetupWarned = false;
    window.__roseBridgeEmit = sendBridgePayload;
    _notifyReady();
  });

  bridgeSocket.addEventListener("message", (event) => {
    let data = null;
    try { data = JSON.parse(event.data); }
    catch (error) { console.log(`${LOG_PREFIX} Bridge message: ${event.data}`); return; }

    _notifySubscribers(data);

    if (data && data.type === "skin-state") {
      publishSkinState(data);
      return;
    }
    if (data && data.type === "skin-mods-response") {
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-skin-mods", { detail: data }));
      return;
    }
    if (data && data.type === "maps-response") {
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-maps", { detail: data }));
      return;
    }
    if (data && data.type === "fonts-response") {
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-fonts", { detail: data }));
      return;
    }
    if (data && data.type === "announcers-response") {
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-announcers", { detail: data }));
      return;
    }
    if (data && data.type === "category-mods-response") {
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-category-mods", { detail: data }));
      return;
    }
    if (data && data.type === "others-response") {
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-others", { detail: data }));
      return;
    }

    if (data && data.type === "champion-locked") {
      if (data.locked === false) {
        lastLoggedSkin = null;
        window.__roseSkinState = null;
        window.__roseCurrentSkin = null;
      }
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-champion-locked", { detail: data }));
      return;
    }
    if (data && data.type === "phase-change" && data.phase === "Lobby") {
      lastLoggedSkin = null;
      window.__roseSkinState = null;
      window.__roseCurrentSkin = null;
      console.log(`${LOG_PREFIX} Reset skin state for new game (Lobby phase)`);
      window.dispatchEvent(new CustomEvent("rose-custom-wheel-reset"));
      return;
    }

    console.log(`${LOG_PREFIX} Bridge message: ${event.data}`);
  });

  bridgeSocket.addEventListener("close", () => {
    bridgeReady = false;
    if (opened) _notifyDisconnect();
    scheduleBridgeRetry();
  });

  bridgeSocket.addEventListener("error", (error) => {
    if (!bridgeErrorLogged) { console.warn(`${LOG_PREFIX} Bridge socket error`, error); bridgeErrorLogged = true; }
    bridgeReady = false;
    scheduleBridgeRetry();
  });
}

function flushBridgeQueue() {
  if (!bridgeSocket || bridgeSocket.readyState !== WebSocket.OPEN) return;
  while (bridgeQueue.length) {
    const payload = bridgeQueue.shift();
    try { bridgeSocket.send(payload); }
    catch (error) {
      console.warn(`${LOG_PREFIX} Bridge flush failed`, error);
      bridgeQueue.unshift(payload);
      resetBridgeSocket();
      break;
    }
  }
}

function scheduleBridgeRetry() {
  if (bridgeReady || stopped) return;
  if (retryTimer) return;
  retryTimer = setTimeout(() => { retryTimer = null; setupBridgeSocket(); }, retryDelay);
  retryDelay = Math.min(retryDelay * 2, RETRY_MAX_MS);
}

function resetBridgeSocket() {
  if (bridgeSocket) {
    try { bridgeSocket.close(); }
    catch (error) { console.warn(`${LOG_PREFIX} Bridge socket close failed`, error); }
  }
  bridgeSocket = null;
  bridgeReady = false;
}

function isVisible(element) {
  if (typeof element.offsetParent === "undefined") return true;
  return element.offsetParent !== null;
}

function readCurrentSkin() {
  for (const selector of SKIN_SELECTORS) {
    const nodes = document.querySelectorAll(selector);
    if (!nodes.length) continue;

    let candidate = null;
    nodes.forEach((node) => {
      const name = node.textContent.trim();
      if (!name) return;
      if (isVisible(node)) candidate = name;
      else if (!candidate) candidate = name;
    });
    if (candidate) return candidate;
  }
  return null;
}

function reportSkinIfChanged() {
  const name = readCurrentSkin();
  if (!name || name === lastLoggedSkin) return;
  lastLoggedSkin = name;
  logHover(name);
}

function attachObservers() {
  if (observer) observer.disconnect();
  observer = new MutationObserver(reportSkinIfChanged);
  observer.observe(document.body, { childList: true, subtree: true });

  document.querySelectorAll("*").forEach((node) => {
    if (!node.shadowRoot || !(node.shadowRoot instanceof Node)) return;
    try { observer.observe(node.shadowRoot, { childList: true, subtree: true }); }
    catch (error) { console.warn(`${LOG_PREFIX} Cannot observe shadowRoot`, error); }
  });

  if (!pollTimer) pollTimer = setInterval(reportSkinIfChanged, POLL_INTERVAL_MS);
}

let monitoring = false;

function startMonitoring() {
  if (monitoring) return;
  monitoring = true;
  console.log(`${LOG_PREFIX} Starting skin monitoring`);
  attachObservers();
  reportSkinIfChanged();
}

function stopMonitoring() {
  if (!monitoring) return;
  monitoring = false;
  console.log(`${LOG_PREFIX} Stopping skin monitoring (out-of-game phase)`);
  if (observer) { observer.disconnect(); observer = null; }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  lastLoggedSkin = null;
}

function handlePhaseChange(data) {
  const phase = data && data.phase;
  if (!phase) return;
  if (phase === "InProgress") stopMonitoring();
  else startMonitoring();
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

// ====== SWIFTPLAY LOCKS PANEL ======
// Одно место решает, что видно, и оно же рисует.
//
// Раньше здесь стоял setInterval на 150 мс, который каждые 150 мс дёргал
// getComputedStyle и размеры 16 элементов (принудительный layout всего окна),
// а на swiftplay-state висело два обработчика сразу, из-за чего панель
// перерисовывалась дважды на каждое обновление. Это и были и мигание, и лаги
// клиента. Хуже, кнопка проверяла только "мы вообще в лобби" - и потому
// появлялась в лобби ранкеда, где панели делать нечего.
//
// Теперь: события приходят по подписке, а layout читается только когда он
// изменился — и только для того, чтобы понять, пора ли перерисовать.

const SMART_PANEL_PANEL_ID = "rose-swiftplay-smart-panel";
const SMART_PANEL_BUTTON_ID = "rose-smart-panel-toggle";
const SMART_PANEL_STYLE_ID = "rose-smart-panel-style";
const SMART_PANEL_CONTAINER_ID = "rsp-skins-container";

// Как часто проверяем "мы в лобби" и "открыто ли меню". Оба вопроса требуют
// чтения layout, поэтому ответы кэшируются, а стили пишутся только при смене.
const SMART_PANEL_AMBIENT_MS = 1000;
// Не чаще, чем раз в секунду просим у Rose актуальное состояние
const SMART_PANEL_REQUEST_MS = 1000;

// Меню клиента живут в собственном слое: lol-uikit-dialog-frame, например,
// имеет inline z-index: 0. Чтобы гарантированно оказаться ПОД меню, нужен
// слой ниже нуля, поэтому берём минимальный z-index из открытых меню и
// вычитаем единицу.
const SMART_PANEL_BASE_Z = 1000;

let smartPanelOpen = false;   // переключатель пользователя
let smartPanelState = null;   // последний swiftplay-state от Rose
let smartPanelDrawn = "";     // подпись нарисованного содержимого
let smartPanelInLobby = false;
let smartPanelBehind = null;  // кэш "панель под открытым меню"
let smartPanelRequestedAt = 0;

const SMART_PANEL_OVERLAY_SELECTORS = [
    'lol-perks-v2-editor',
    'lol-perks-v2-main-view',
    '.perks-editor-modal',
    'lol-uikit-full-page-modal',
    'lol-uikit-dialog-frame',
    '.champion-customization-flyout',
    '.quick-play-champion-select-component',
    '.quick-play-skin-select-component',
    '.quick-play-loadout-container',
    '#rose-custom-wheel-panel-container',
    '#lu-custom-skin-panel-container',
    '#lu-chroma-panel-container',
    '#forms-wheel-panel-container',
    '#rose-settings-panel',
    '#champion-selection-dialog',
    '#skin-selection-dialog',
    '#add-custom-mods-dialog',
    '#category-mods-manage-dialog',
    '#champion-mods-manage-dialog'
];

function isActuallyInLobby() {
    const lobbyBanners = document.querySelector('.v2-banner-component.local-player');
    return !!(lobbyBanners && lobbyBanners.offsetParent !== null);
}

// Видимые (не пустые, не скрытые) элементы-меню — их реальные слои нужны,
// чтобы встать под самый нижний из них.
function getOpenOverlayElements() {
    const open = [];
    for (const selector of SMART_PANEL_OVERLAY_SELECTORS) {
        const el = document.querySelector(selector);
        if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) open.push(el);
    }
    return open;
}

function isOverlayOpen() {
    if (getOpenOverlayElements().length) return true;

    const flyouts = document.querySelectorAll('lol-uikit-flyout-frame');
    for (const f of flyouts) {
        if (f.id !== 'rose-settings-flyout' && !f.closest('#rose-custom-wheel-panel-container, #lu-chroma-panel-container, #forms-wheel-panel-container')) {
            if (f.offsetWidth > 0 || f.offsetHeight > 0) return true;
        }
    }

    return false;
}

function resolveBehindZIndex() {
    let lowest = 0;
    for (const el of getOpenOverlayElements()) {
        const parsed = Number.parseInt(getComputedStyle(el).zIndex, 10);
        const z = Number.isFinite(parsed) ? parsed : 0;
        if (z < lowest) lowest = z;
    }
    return lowest - 1;
}

// Панель и кнопка не исчезают при открытом меню, а уходят под него и
// перестают перехватывать клики (меню должно кликаться свободно).
function applySmartPanelLayer(el, interactive, behind) {
    if (!el) return;
    el.style.zIndex = behind ? resolveBehindZIndex() : SMART_PANEL_BASE_Z;
    el.style.pointerEvents = behind ? 'none' : (interactive ? 'auto' : 'none');
}

function escapeSmartPanelText(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function ensureSmartPanelStyle() {
    // Один раз на страницу: раньше <style> добавлялся при каждом создании панели,
    // то есть один и тот же блок правил накапливался в <head> за весь сеанс
    if (document.getElementById(SMART_PANEL_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = SMART_PANEL_STYLE_ID;
    style.textContent = `
        #${SMART_PANEL_PANEL_ID} {
            position: fixed;
            bottom: 100px;
            left: 30px;
            background: rgba(1, 10, 19, 0.98);
            border: 1px solid #463714;
            border-top: 2px solid #c8aa6e;
            padding: 12px;
            z-index: ${SMART_PANEL_BASE_Z};
            display: flex;
            flex-direction: column;
            gap: 10px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.8);
            min-width: 260px;
            max-width: 450px;
            pointer-events: none;
        }
        #${SMART_PANEL_PANEL_ID} .rsp-header {
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
        #${SMART_PANEL_PANEL_ID} .rsp-item { display: flex; align-items: flex-start; gap: 12px; margin: 4px 0; }
        #${SMART_PANEL_PANEL_ID} .rsp-icon { width: 34px; height: 34px; border-radius: 50%; border: 1px solid #785a28; flex-shrink: 0; }
        #${SMART_PANEL_PANEL_ID} .rsp-text { display: flex; flex-direction: column; min-width: 0; }
        #${SMART_PANEL_PANEL_ID} .rsp-champ { color: #a09b8c; font-size: 9px; text-transform: uppercase; font-weight: bold; }
        #${SMART_PANEL_PANEL_ID} .rsp-skin {
            color: #f0e6d2;
            font-size: 13px;
            font-weight: bold;
            line-height: 1.2;
            white-space: normal;
            word-wrap: break-word;
            overflow: visible;
            text-overflow: clip;
        }
        #${SMART_PANEL_PANEL_ID} .rsp-empty { color: #a09b8c; font-size: 12px; }
    `;
    document.head.appendChild(style);
}

function ensureSmartPanel() {
    let panel = document.getElementById(SMART_PANEL_PANEL_ID);
    if (panel) return panel;
    ensureSmartPanelStyle();
    panel = document.createElement('div');
    panel.id = SMART_PANEL_PANEL_ID;
    panel.innerHTML = `
        <div class="rsp-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c8aa6e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
            <span>Swiftplay Locks</span>
        </div>
        <div class="rsp-body" id="${SMART_PANEL_CONTAINER_ID}"></div>
    `;
    document.body.appendChild(panel);
    smartPanelDrawn = "";
    return panel;
}

function ensureSmartPanelToggle() {
    let btn = document.getElementById(SMART_PANEL_BUTTON_ID);
    if (btn) return btn;
    ensureSmartPanelStyle();
    btn = document.createElement('div');
    btn.id = SMART_PANEL_BUTTON_ID;
    btn.title = 'Swiftplay Locks';
    btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>`;

    btn.style.position = 'fixed';
    btn.style.width = '22px';
    btn.style.height = '22px';
    btn.style.background = 'transparent';
    btn.style.border = 'none';
    btn.style.outline = 'none';
    btn.style.boxShadow = 'none';
    btn.style.display = 'flex';
    btn.style.alignItems = 'center';
    btn.style.justifyContent = 'center';
    btn.style.cursor = 'pointer';
    btn.style.zIndex = String(SMART_PANEL_BASE_Z);
    btn.style.transition = 'color 0.2s';

    btn.addEventListener('mouseenter', () => { btn.style.color = '#f0e6d2'; });
    btn.addEventListener('mouseleave', () => { btn.style.color = smartPanelOpen ? '#0acbe6' : '#c8aa6e'; });
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        smartPanelOpen = !smartPanelOpen;
        if (smartPanelOpen) requestSmartPanelState();
        applySmartPanel();
    });

    document.body.appendChild(btn);
    return btn;
}

function positionSmartPanelToggle(btn) {
    // Справа от lol-uikit-info-icon
    const infoIcon = document.querySelector('.lobby-header lol-uikit-info-icon, .parties-game-info-panel lol-uikit-info-icon, lol-uikit-info-icon');
    if (!infoIcon) return;
    const rect = infoIcon.getBoundingClientRect();
    if (rect.right > 0 && rect.top > 0) {
        btn.style.left = `${Math.round(rect.right + 8)}px`;
        btn.style.top = `${Math.round(rect.top + (rect.height - 22) / 2)}px`;
    }
}

function removeSmartPanel() {
    const panel = document.getElementById(SMART_PANEL_PANEL_ID);
    if (panel) panel.remove();
    const btn = document.getElementById(SMART_PANEL_BUTTON_ID);
    if (btn) btn.remove();
    smartPanelDrawn = "";
    smartPanelBehind = null;
}

// Содержимое перерисовывается только когда оно действительно изменилось:
// пересборка innerHTML на каждое событие и была причиной мигания.
function drawSmartPanel(panel, skins) {
    const signature = skins
        .map(s => `${s.championId}:${s.skinId}:${s.skinName}:${s.isOwned ? 1 : 0}`)
        .join('|');
    if (signature === smartPanelDrawn) return;
    smartPanelDrawn = signature;

    const container = panel.querySelector(`#${SMART_PANEL_CONTAINER_ID}`);
    if (!container) return;
    if (!skins.length) {
        container.innerHTML = '<div class="rsp-empty">No champions picked yet</div>';
        return;
    }
    container.innerHTML = skins.map(skin => {
        const ownedBadge = skin.isOwned
            ? `<span style="color: #0acbe6; font-size: 10px; margin-left: 6px; text-shadow: 0 0 4px rgba(10, 203, 230, 0.5); vertical-align: baseline;">&#10004; OWNED</span>`
            : '';
        const borderColor = skin.isOwned ? '#0acbe6' : '#785a28';
        const opacity = skin.isOwned ? '0.85' : '1';

        return `
            <div class="rsp-item" style="opacity: ${opacity};">
                <img class="rsp-icon" src="/lol-game-data/assets/v1/champion-icons/${skin.championId}.png" style="border-color: ${borderColor};">
                <div class="rsp-text">
                    <span class="rsp-champ">${escapeSmartPanelText(skin.championName)}</span>
                    <span class="rsp-skin">${escapeSmartPanelText(skin.skinName)}${ownedBadge}</span>
                </div>
            </div>
        `;
    }).join('');
}

// Единственное место, где решается что видно
function applySmartPanel() {
    const state = smartPanelState;
    // Панель - только для лобби Swiftplay. Флаг active приходит от Rose, но он
    // обновляется не мгновенно, поэтому в нём не полагаемся: за лобби раньше
    // цеплялся и рейтинг, где такой панели быть не должно вообще.
    if (!smartPanelInLobby || !state || !state.active) {
        removeSmartPanel();
        return;
    }

    const skins = Array.isArray(state.skins) ? state.skins : [];
    const btn = ensureSmartPanelToggle();
    const panel = ensureSmartPanel();
    btn.style.color = smartPanelOpen ? '#0acbe6' : '#c8aa6e';
    positionSmartPanelToggle(btn);
    drawSmartPanel(panel, skins);
    panel.style.display = smartPanelOpen ? 'flex' : 'none';

    // Слой читаем один раз на обновление, а не на каждый элемент
    const behind = isOverlayOpen();
    smartPanelBehind = behind;
    applySmartPanelLayer(btn, true, behind);
    applySmartPanelLayer(panel, false, behind);
}

function requestSmartPanelState() {
    const now = Date.now();
    if (now - smartPanelRequestedAt < SMART_PANEL_REQUEST_MS) return;
    smartPanelRequestedAt = now;
    if (window.__roseBridge && window.__roseBridge.ready) {
        window.__roseBridge.send({ type: "request-swiftplay-state" });
    }
}

function updateSmartPanelState(data) {
    smartPanelState = data || null;
    applySmartPanel();
}

function handleSmartPanelPhaseChange(data) {
    const phase = data && data.phase;
    smartPanelInLobby = phase === "Lobby";
    if (smartPanelInLobby) {
        requestSmartPanelState();
    } else {
        removeSmartPanel();
    }
    applySmartPanel();
}

// Раз в секунду: поправка на то, что события не приходят, когда клиент просто
// перерисовал лобби. Ничего не пишется, если ничего не изменилось.
setInterval(() => {
    const inLobby = isActuallyInLobby();
    if (inLobby !== smartPanelInLobby) {
        smartPanelInLobby = inLobby;
        if (inLobby) {
            requestSmartPanelState();
        } else {
            removeSmartPanel();
        }
        applySmartPanel();
        return;
    }
    if (!inLobby) return;
    // Меню могло открыться или закрыться - слой надо поправить, но только если он
    // изменился. Пересчёт layout без нужды и был тем самым лагом.
    if (isOverlayOpen() !== smartPanelBehind) applySmartPanel();
}, SMART_PANEL_AMBIENT_MS);

async function start() {
  if (!document.body) {
    console.log(`${LOG_PREFIX} Waiting for document.body...`);
    setTimeout(start, 250);
    return;
  }

  stopped = false;
  retryDelay = RETRY_BASE_MS;

  await loadBridgePort();

  if (typeof window !== "undefined") {
    window.__roseBridge = Object.freeze({
      send: sendBridgePayload,
      subscribe,
      unsubscribe,
      onReady,
      onDisconnect,
      get port() { return BRIDGE_PORT; },
      get ready() { return bridgeReady; },
    });
    
    // Подписки панели ровно в одном месте. Раньше их было два: здесь и в
    // setupPhaseSubscription(), вызванной сразу при загрузке файла, - и каждое
    // обновление перерисовывало панель дважды.
    subscribe("swiftplay-state", updateSmartPanelState);
    subscribe("phase-change", handleSmartPanelPhaseChange);
  }

  installFindMatchObserver();
  setupBridgeSocket();
  subscribe("phase-change", handlePhaseChange);
  startMonitoring();
}

function stop() {
  stopped = true;
  if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
  monitoring = false;
  if (observer) { observer.disconnect(); observer = null; }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (bridgeSocket) { bridgeSocket.close(); bridgeSocket = null; }
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