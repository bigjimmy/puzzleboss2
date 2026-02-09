// Auto-reload on auth failure (e.g., expired OIDC session)
//
// When API calls fail (usually because Apache returned an OIDC redirect
// instead of JSON), reload the page once to trigger re-authentication.
// Uses sessionStorage to prevent infinite reload loops.
//
// Usage:
//   ES module:  import { onFetchSuccess, onFetchFailure } from './auth-reload.js'
//   Non-module: <script type="module" src="./auth-reload.js"></script>
//               then use window.onFetchSuccess() / window.onFetchFailure()

const AUTH_RELOAD_KEY = 'pb_auth_reload_attempted';

/**
 * Call this when an API fetch succeeds. Clears the reload flag so that
 * a future failure will trigger a fresh reload attempt.
 */
function onFetchSuccess() {
    sessionStorage.removeItem(AUTH_RELOAD_KEY);
}

/**
 * Call this when an API fetch fails. On the first failure after a
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

// Expose globally for non-module scripts that load this via
// <script type="module" src="./auth-reload.js"></script>
window.onFetchSuccess = onFetchSuccess;
window.onFetchFailure = onFetchFailure;

export { onFetchSuccess, onFetchFailure };
