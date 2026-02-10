// pb-utils.js — Shared JavaScript utilities for Puzzleboss pages
//
// Provides:
//   - Auth-reload on API failure (migrated from auth-reload.js)
//   - HTML/attribute escaping (XSS protection)
//   - API fetch wrapper with auth callbacks
//   - Status message display helper
//
// Usage:
//   ES module:  import { onFetchSuccess, onFetchFailure, apiCall, ... } from './pb-utils.js'
//   Non-module: <script type="module" src="./pb-utils.js"></script>
//               then use window.pbUtils.escapeHtml(...) etc.

// ─── API proxy constant ──────────────────────────────────────────────
const API_PROXY = './apicall.php';

// ─── Auth-reload (from auth-reload.js) ───────────────────────────────
const AUTH_RELOAD_KEY = 'pb_auth_reload_attempted';

/**
 * Call when an API fetch succeeds. Clears the reload flag so that
 * a future failure will trigger a fresh reload attempt.
 */
function onFetchSuccess() {
    sessionStorage.removeItem(AUTH_RELOAD_KEY);
}

/**
 * Call when an API fetch fails. On the first failure after a
 * successful fetch, reloads the page (which triggers OIDC re-auth).
 * Returns true if a reload was triggered (caller should abort).
 */
function onFetchFailure() {
    if (!sessionStorage.getItem(AUTH_RELOAD_KEY)) {
        sessionStorage.setItem(AUTH_RELOAD_KEY, Date.now().toString());
        location.reload();
        return true;
    }
    return false;
}

// ─── HTML escaping ───────────────────────────────────────────────────

/** Escape a string for safe insertion into HTML content. */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/** Escape a string for safe insertion into HTML attribute values. */
function escapeAttr(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// ─── API fetch wrapper ───────────────────────────────────────────────

/**
 * Fetch JSON from the API proxy with automatic auth-reload handling.
 *
 * @param {string} path  - Query string appended to API_PROXY (e.g. '?apicall=config')
 * @param {object} [opts] - Optional fetch options (method, headers, body).
 *                           Defaults to GET. If body is a plain object, it is
 *                           JSON-stringified and Content-Type is set automatically.
 * @returns {Promise<object>} Parsed JSON response
 * @throws {Error} If the response contains an error field or unexpected status
 */
async function apiCall(path, opts = {}) {
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
        opts.body = JSON.stringify(opts.body);
        opts.headers = { 'Content-Type': 'application/json', ...opts.headers };
    }
    const resp = await fetch(API_PROXY + path, opts);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    onFetchSuccess();
    return data;
}

// ─── Status message helper ───────────────────────────────────────────

/**
 * Display a status message in a container element.
 *
 * @param {string|Element} target - Element or element ID to set innerHTML on
 * @param {'success'|'error'|''} type - Message type (maps to .status-msg CSS class)
 * @param {string} html - Pre-escaped HTML content for the message
 * @param {number} [autoHideMs] - If set, clear the message after this many ms
 */
function showStatus(target, type, html, autoHideMs) {
    const el = typeof target === 'string' ? document.getElementById(target) : target;
    if (!el) return;
    el.innerHTML = '<div class="status-msg ' + type + '">' + html + '</div>';
    if (autoHideMs) {
        setTimeout(() => { el.innerHTML = ''; }, autoHideMs);
    }
}

// ─── Expose globally for non-module scripts ──────────────────────────
// Traditional pages load this as <script type="module" src="./pb-utils.js">
// and then call window.onFetchSuccess(), window.pbUtils.escapeHtml(), etc.

window.onFetchSuccess = onFetchSuccess;
window.onFetchFailure = onFetchFailure;
window.pbUtils = {
    API_PROXY,
    escapeHtml,
    escapeAttr,
    apiCall,
    showStatus,
};

// ─── ES module exports ───────────────────────────────────────────────
export {
    API_PROXY,
    onFetchSuccess,
    onFetchFailure,
    escapeHtml,
    escapeAttr,
    apiCall,
    showStatus,
};
