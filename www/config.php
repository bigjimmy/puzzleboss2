<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Configuration Management</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <style>
    .toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .filter-input {
      padding: 6px 12px;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      font-size: 14px;
      width: 300px;
    }
    .filter-input:focus {
      outline: none;
      border-color: var(--primary-blue);
      box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.15);
    }
    body.status-page .refresh-btn {
      background: var(--bg-white);
      color: var(--text-primary);
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      padding: 6px 16px;
      cursor: pointer;
      font-size: 14px;
      font-weight: normal;
      text-align: center;
      min-width: 0;
    }
    body.status-page .refresh-btn:hover {
      background: var(--bg-light-gray);
    }
    .config-count {
      color: var(--text-secondary);
      font-size: 14px;
    }

    /* Category sections */
    .config-category {
      background: var(--bg-white);
      border: 1px solid var(--border-medium);
      border-radius: 8px;
      margin-bottom: 15px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .category-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 15px;
      cursor: pointer;
      user-select: none;
      border-bottom: 1px solid var(--border-light);
    }
    .category-header:hover {
      background: var(--bg-light-gray);
      border-radius: 8px 8px 0 0;
    }
    .category-header h3 {
      margin: 0;
      font-size: 1em;
      flex: 1;
    }
    .collapse-icon {
      display: inline-block;
      transition: transform 0.2s;
      font-size: 12px;
    }
    .collapse-icon.collapsed {
      transform: rotate(-90deg);
    }
    .category-body {
      padding: 0;
    }
    .category-body.hidden {
      display: none;
    }

    /* Config rows */
    .config-row {
      display: flex;
      align-items: flex-start;
      padding: 10px 15px;
      border-bottom: 1px solid var(--border-light);
      gap: 15px;
    }
    .config-row:last-child {
      border-bottom: none;
    }
    .config-row:hover {
      background: #fafafa;
    }
    .config-row.just-saved {
      background: var(--success-bg-light);
    }
    .config-key {
      font-family: var(--font-mono);
      font-size: 13px;
      font-weight: 600;
      min-width: 280px;
      max-width: 280px;
      padding-top: 6px;
      word-break: break-all;
      color: var(--text-primary);
    }
    .config-key .key-description {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      font-weight: normal;
      font-size: 11px;
      color: var(--text-tertiary);
      margin-top: 2px;
      display: block;
    }
    .config-value {
      flex: 1;
      min-width: 0;
    }
    .config-value input[type="text"] {
      width: 100%;
      padding: 5px 8px;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 13px;
      box-sizing: border-box;
    }
    .config-value textarea {
      width: 100%;
      padding: 5px 8px;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 12px;
      box-sizing: border-box;
      resize: vertical;
      min-height: 60px;
    }
    .config-value input:focus,
    .config-value textarea:focus {
      outline: none;
      border-color: var(--primary-blue);
      box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.15);
    }
    .config-value .current-display {
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 4px;
      word-break: break-all;
      max-height: 60px;
      overflow-y: auto;
    }
    .config-value .current-display.empty {
      color: var(--text-tertiary);
      font-style: italic;
    }
    .config-actions {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 70px;
    }
    body.status-page .save-btn {
      background: var(--primary-blue);
      color: white;
      border: none;
      border-radius: 4px;
      padding: 5px 14px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      min-width: 60px;
      text-align: center;
    }
    body.status-page .save-btn:hover {
      background: var(--primary-blue-hover);
    }
    body.status-page .save-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    body.status-page .save-btn.saved {
      background: green;
    }
    body.status-page .revert-btn {
      background: var(--bg-white);
      color: var(--text-secondary);
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      padding: 3px 10px;
      cursor: pointer;
      font-size: 11px;
      min-width: 0;
      font-weight: normal;
      text-align: center;
    }
    body.status-page .revert-btn:hover {
      background: var(--bg-light-gray);
    }

    /* Boolean toggle styling */
    .bool-toggle {
      display: inline-flex;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      overflow: hidden;
      margin-top: 2px;
    }
    .bool-toggle span {
      padding: 4px 14px;
      font-size: 13px;
      cursor: pointer;
      user-select: none;
      transition: all 0.15s;
      border-right: 1px solid var(--border-medium);
    }
    .bool-toggle span:last-child {
      border-right: none;
    }
    .bool-toggle span.active-true {
      background: #d4f4dd;
      color: green;
      font-weight: 600;
    }
    .bool-toggle span.active-false {
      background: #fee;
      color: #c00;
      font-weight: 600;
    }
    .bool-toggle span:not(.active-true):not(.active-false) {
      background: var(--bg-white);
      color: var(--text-tertiary);
    }
    .bool-toggle span:hover:not(.active-true):not(.active-false) {
      background: var(--bg-light-gray);
    }

    /* Number input */
    .config-value input[type="number"] {
      width: 120px;
      padding: 5px 8px;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 13px;
    }
    .config-value input[type="number"]:focus {
      outline: none;
      border-color: var(--primary-blue);
      box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.15);
    }

    /* Add new config */
    .add-config {
      display: flex;
      gap: 10px;
      align-items: flex-start;
      padding: 10px 15px;
    }
    .add-config input[type="text"] {
      padding: 5px 8px;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 13px;
    }
    .add-config textarea {
      padding: 5px 8px;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 13px;
      resize: vertical;
      min-height: 36px;
    }

    /* Status messages */
    #status-area {
      margin-bottom: 10px;
    }
    .status-msg {
      padding: 10px;
      margin: 5px 0;
      border-radius: 4px;
      font-size: 14px;
    }
    .status-msg.success { background: var(--success-bg); }
    .status-msg.error { background: var(--error-bg); }

    /* Warning modal */
    .modal-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.5);
      z-index: 1000;
      justify-content: center;
      align-items: center;
    }
    .modal-overlay.active {
      display: flex;
    }
    .modal {
      background: white;
      border-radius: 8px;
      padding: 30px;
      max-width: 520px;
      width: 90%;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    }
    .modal h3 {
      margin-top: 0;
      color: #b45309;
    }
    .modal .warning {
      background: #fff8f0;
      border: 1px solid #fed7aa;
      border-radius: 4px;
      padding: 12px;
      margin: 15px 0;
      font-size: 14px;
      line-height: 1.6;
    }
    .modal-buttons {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      margin-top: 20px;
    }
    body.status-page .modal-buttons button {
      padding: 8px 20px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      font-weight: normal;
      min-width: 0;
    }
    body.status-page .btn-cancel {
      background: var(--bg-white);
      color: var(--text-primary);
      border: 1px solid var(--border-medium);
    }
    body.status-page .btn-cancel:hover {
      background: var(--bg-light-gray);
    }
    body.status-page .btn-ok {
      background: var(--primary-blue);
      color: white;
      border: 1px solid var(--primary-blue);
    }
    body.status-page .btn-ok:hover {
      background: var(--primary-blue-hover);
    }

    /* Status select dropdown */
    .config-value select.status-select {
      padding: 5px 8px;
      border: 1px solid var(--border-medium);
      border-radius: 4px;
      font-size: 14px;
      min-width: 200px;
    }
    .config-value select.status-select:focus {
      outline: none;
      border-color: var(--primary-blue);
      box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.15);
    }

    /* Structured metadata editors */
    .meta-editor {
      width: 100%;
    }
    .meta-editor .editor-note {
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 8px;
      padding: 8px 10px;
      background: var(--bg-light-blue);
      border-radius: 4px;
      border: 1px solid var(--border-blue);
      line-height: 1.5;
    }
    .meta-editor .editor-note strong {
      color: var(--primary-blue-dark);
    }
    .meta-editor table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    .meta-editor th {
      text-align: left;
      padding: 4px 6px;
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 2px solid var(--border-medium);
      white-space: nowrap;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .meta-editor td {
      padding: 3px 4px;
      border-bottom: 1px solid var(--border-light);
      vertical-align: middle;
    }
    .meta-editor tr:last-child td {
      border-bottom: none;
    }
    .meta-editor input[type="text"],
    .meta-editor input[type="number"] {
      width: 100%;
      padding: 3px 6px;
      border: 1px solid var(--border-light);
      border-radius: 3px;
      font-family: var(--font-mono);
      font-size: 12px;
      box-sizing: border-box;
    }
    .meta-editor select {
      padding: 3px 6px;
      border: 1px solid var(--border-light);
      border-radius: 3px;
      font-size: 12px;
    }
    .meta-editor input:focus,
    .meta-editor select:focus {
      outline: none;
      border-color: var(--primary-blue);
    }
    .meta-editor .col-name {
      font-weight: 600;
      white-space: nowrap;
    }
    .meta-editor .col-name input[readonly] {
      background: transparent;
      border-color: transparent;
      color: var(--text-primary);
      cursor: default;
    }
    .meta-editor .col-emoji {
      width: 50px;
      text-align: center;
    }
    .meta-editor .col-emoji input {
      text-align: center;
      width: 50px;
    }
    .meta-editor .col-text {
      width: 50px;
    }
    .meta-editor .col-text input {
      width: 50px;
      text-align: center;
    }
    .meta-editor .col-order {
      width: 55px;
    }
    .meta-editor .col-order input {
      width: 55px;
      text-align: center;
    }
    .meta-editor .col-type {
      width: 90px;
    }
    .meta-editor .col-desc {
      min-width: 200px;
    }
    .meta-editor .col-dbkey {
      width: 170px;
    }
    .meta-editor .col-actions {
      width: 30px;
      text-align: center;
    }
    body.status-page .meta-editor .remove-row-btn {
      background: none;
      border: none;
      color: var(--text-tertiary);
      cursor: pointer;
      font-size: 16px;
      padding: 2px 6px;
      min-width: 0;
      font-weight: normal;
      line-height: 1;
    }
    body.status-page .meta-editor .remove-row-btn:hover {
      color: #c00;
      background: none;
    }
    body.status-page .meta-editor .add-row-btn {
      background: var(--bg-white);
      color: var(--primary-blue);
      border: 1px dashed var(--border-medium);
      border-radius: 4px;
      padding: 4px 12px;
      cursor: pointer;
      font-size: 12px;
      font-weight: normal;
      min-width: 0;
      margin-top: 6px;
    }
    body.status-page .meta-editor .add-row-btn:hover {
      background: var(--bg-light-blue);
      border-color: var(--primary-blue);
    }

    /* Full-width layout for metadata editors */
    .config-row.wide-editor {
      flex-direction: column;
      gap: 8px;
    }
    .config-row.wide-editor .config-key {
      max-width: none;
      min-width: 0;
    }
    .config-row.wide-editor .config-value {
      width: 100%;
    }
    .config-row.wide-editor .config-actions {
      align-self: flex-end;
      flex-direction: row;
    }
  </style>
</head>
<body class="status-page">

<?php
// Permissions check — same as admin.php (puzztech only)
require('puzzlebosslib.php');

$username = "";
if (!isset($_SERVER['REMOTE_USER'])) {
  if ($noremoteusertestmode == 'true') {
    $username = "testuser";
  }
  if (isset($_GET['assumedid'])) {
    $username = $_GET['assumedid'];
  }
  if ($username == "") {
    echo '<br>authenticated REMOTE_USER not provided<br>';
    echo '</body></html>';
    exit(2);
  }
} else {
  $username = $_SERVER['REMOTE_USER'];
}

$uid = getuid($username);
$allowed = checkpriv("puzztech", $uid);

if (!$allowed) {
?>
<div class="status-header">
  <h1>ACCESS DENIED</h1>
</div>
<?= render_navbar() ?>
<p>Access to this page is restricted to users with the <strong>puzztech</strong> role. Contact puzzleboss or puzztech for assistance.</p>
</body>
</html>
<?php
  exit(2);
}

// Config is already loaded via puzzlebosslib.php ($config object from /huntinfo)
// Convert to associative array for iteration
$configArr = (array) $huntinfo->config;
ksort($configArr);

// Category definitions: key => [label, description]
$categories = [
  'hunt' => ['Current Hunt Adjustments', 'Settings you may change during the hunt'],
  'general' => ['General', 'Core team and hunt settings'],
  'bigjimmy' => ['BigJimmy Bot', 'Sheet activity polling bot configuration'],
  'google' => ['Google Sheets & Drive', 'Google API and sheet template settings'],
  'discord' => ['Discord (Puzzcord)', 'Discord bot integration'],
  'memcache' => ['Memcache', 'Response caching layer'],
  'llm' => ['LLM & AI', 'Gemini AI, natural language queries, and wiki RAG'],
  'urls' => ['URLs & Email', 'Service endpoints and email configuration'],
  'metadata' => ['Status & Metrics Metadata', 'JSON definitions for puzzle statuses and bot metrics'],
  'other' => ['Other', 'Uncategorized configuration values'],
];

// Map config keys to categories
$keyCategoryMap = [
  'bookmarklet_js' => 'hunt',
  'hunt_domain' => 'hunt',

  'TEAMNAME' => 'general',
  'HUNT_FOLDER_NAME' => 'general',
  'DOMAINNAME' => 'general',
  'LOGLEVEL' => 'general',

  'BIGJIMMY_ABANDONED_STATUS' => 'bigjimmy',
  'BIGJIMMY_ABANDONED_TIMEOUT_MINUTES' => 'bigjimmy',
  'BIGJIMMY_AUTOASSIGN' => 'bigjimmy',
  'BIGJIMMY_PUZZLEPAUSETIME' => 'bigjimmy',
  'BIGJIMMY_QUOTAFAIL_DELAY' => 'bigjimmy',
  'BIGJIMMY_QUOTAFAIL_MAX_RETRIES' => 'bigjimmy',
  'BIGJIMMY_THREADCOUNT' => 'bigjimmy',

  'SKIP_GOOGLE_API' => 'google',
  'SHEETS_TEMPLATE_ID' => 'google',

  'SKIP_PUZZCORD' => 'discord',
  'PUZZCORD_HOST' => 'discord',
  'PUZZCORD_PORT' => 'discord',
  'DISCORD_EMAIL_WEBHOOK' => 'discord',

  'MEMCACHE_ENABLED' => 'memcache',
  'MEMCACHE_HOST' => 'memcache',
  'MEMCACHE_PORT' => 'memcache',

  'GEMINI_API_KEY' => 'llm',
  'GEMINI_MODEL' => 'llm',
  'GEMINI_SYSTEM_INSTRUCTION' => 'llm',
  'WIKI_URL' => 'llm',
  'WIKI_CHROMADB_PATH' => 'llm',
  'WIKI_EXCLUDE_PREFIXES' => 'llm',
  'WIKI_PRIORITY_PAGES' => 'llm',

  'ACCT_URI' => 'urls',
  'BIN_URI' => 'urls',
  'REGEMAIL' => 'urls',
  'MAILRELAY' => 'urls',

  'STATUS_METADATA' => 'metadata',
  'METRICS_METADATA' => 'metadata',
];

// Key descriptions for helpful tooltips
$keyDescriptions = [
  'bookmarklet_js' => 'JavaScript bookmarklet for adding puzzles from the hunt site',
  'hunt_domain' => 'Domain of the current hunt website (e.g. puzzlehunt.example.com)',
  'TEAMNAME' => 'Display name for your team',
  'HUNT_FOLDER_NAME' => 'Google Drive folder name for the hunt',
  'DOMAINNAME' => 'Primary domain for the team',
  'LOGLEVEL' => 'Log verbosity: 0=emergency … 5=trace',
  'BIGJIMMY_ABANDONED_STATUS' => 'Status to set when a puzzle is abandoned',
  'BIGJIMMY_ABANDONED_TIMEOUT_MINUTES' => 'Minutes of inactivity before marking abandoned',
  'BIGJIMMY_AUTOASSIGN' => 'Auto-assign solvers to puzzles from sheets',
  'BIGJIMMY_PUZZLEPAUSETIME' => 'Seconds between sheet polls per puzzle',
  'BIGJIMMY_QUOTAFAIL_DELAY' => 'Seconds to wait after a Google quota failure',
  'BIGJIMMY_QUOTAFAIL_MAX_RETRIES' => 'Max retries after quota failures',
  'BIGJIMMY_THREADCOUNT' => 'Number of parallel threads for sheet polling',
  'SKIP_GOOGLE_API' => 'Disable all Google Sheets/Drive integration',
  'SHEETS_TEMPLATE_ID' => 'Google Sheet ID used as template for new puzzles',
  'SKIP_PUZZCORD' => 'Disable Discord integration',
  'PUZZCORD_HOST' => 'Hostname of the puzzcord daemon',
  'PUZZCORD_PORT' => 'Port of the puzzcord daemon',
  'DISCORD_EMAIL_WEBHOOK' => 'Webhook URL for email-to-Discord forwarding',
  'MEMCACHE_ENABLED' => 'Enable memcache for /allcached endpoint',
  'MEMCACHE_HOST' => 'Memcache server hostname',
  'MEMCACHE_PORT' => 'Memcache server port',
  'GEMINI_API_KEY' => 'Google Gemini API key for LLM queries',
  'GEMINI_MODEL' => 'Gemini model name (e.g. gemini-3-flash-preview)',
  'GEMINI_SYSTEM_INSTRUCTION' => 'System prompt for the Gemini LLM assistant',
  'WIKI_URL' => 'Base URL of the team wiki for RAG indexing',
  'WIKI_CHROMADB_PATH' => 'File path to ChromaDB vector store',
  'WIKI_EXCLUDE_PREFIXES' => 'Wiki page prefixes to skip during indexing',
  'WIKI_PRIORITY_PAGES' => 'Comma-separated priority pages for RAG',
  'ACCT_URI' => 'URL to the account management page',
  'BIN_URI' => 'URL root for the Puzzleboss web UI',
  'REGEMAIL' => 'Admin email address for registration',
  'MAILRELAY' => 'SMTP relay server for outbound email',
  'STATUS_METADATA' => 'JSON array defining puzzle statuses (emoji, text, order)',
  'METRICS_METADATA' => 'JSON object defining Prometheus metric definitions',
];

// Known boolean keys (values are "true"/"false" strings)
$booleanKeys = ['BIGJIMMY_AUTOASSIGN', 'SKIP_GOOGLE_API', 'SKIP_PUZZCORD', 'MEMCACHE_ENABLED'];

// Known numeric keys
$numericKeys = ['LOGLEVEL', 'BIGJIMMY_ABANDONED_TIMEOUT_MINUTES', 'BIGJIMMY_PUZZLEPAUSETIME',
                'BIGJIMMY_QUOTAFAIL_DELAY', 'BIGJIMMY_QUOTAFAIL_MAX_RETRIES', 'BIGJIMMY_THREADCOUNT',
                'PUZZCORD_PORT', 'MEMCACHE_PORT'];

// Keys with long/JSON values that need textareas
$textareaKeys = ['GEMINI_SYSTEM_INSTRUCTION', 'bookmarklet_js', 'debugging_usernames'];

// Keys with custom structured editors (handled separately in the rendering loop)
$specialKeys = ['STATUS_METADATA', 'METRICS_METADATA', 'BIGJIMMY_ABANDONED_STATUS'];

// Deprecated keys to hide (removed from system, may linger in DB)
$hiddenKeys = ['SLACK_EMAIL_WEBHOOK', 'LDAP_ADMINDN', 'LDAP_ADMINPW', 'LDAP_DOMAIN', 'LDAP_HOST', 'LDAP_LDAP0'];

// Group config by category
$grouped = [];
foreach ($categories as $catKey => $catInfo) {
  $grouped[$catKey] = [];
}
foreach ($configArr as $key => $value) {
  if (in_array($key, $hiddenKeys)) continue;
  $cat = $keyCategoryMap[$key] ?? 'other';
  if (!isset($grouped[$cat])) $cat = 'other';
  $grouped[$cat][$key] = $value;
}

// Remove empty categories
$grouped = array_filter($grouped, function($items) { return count($items) > 0; });
?>

<div class="status-header">
  <h1>Configuration</h1>
</div>

<?= render_navbar() ?>

<!-- Warning modal -->
<div class="modal-overlay active" id="warn-modal">
  <div class="modal">
    <h3>⚠️ Configuration Editor</h3>
    <p>This page controls <strong>live system configuration</strong> for the entire hunt infrastructure.</p>
    <div class="warning">
      <ul style="margin: 5px 0; padding-left: 20px;">
        <li>Changes take effect within <strong>30 seconds</strong> across all API workers and BigJimmyBot</li>
        <li>Changes are <strong>immediate and not reversible</strong></li>
        <li>Incorrect values can <strong>break the hunt</strong> for all solvers</li>
      </ul>
      If you are unsure about a setting, <strong>ask puzztech first</strong>.
    </div>
    <div class="modal-buttons">
      <button class="btn-cancel" onclick="window.history.back()">Go Back</button>
      <button class="btn-ok" onclick="dismissWarning()">I understand, continue</button>
    </div>
  </div>
</div>

<div id="config-content" style="display: none;">

<div id="status-area"></div>

<div class="toolbar">
  <input type="text" class="filter-input" id="filter" placeholder="Filter by key name..." oninput="filterConfig()">
  <button class="refresh-btn" onclick="location.reload()">Refresh</button>
  <span class="config-count"><?= count($configArr) - count(array_intersect_key($configArr, array_flip($hiddenKeys))) ?> config values</span>
</div>

<?php foreach ($grouped as $catKey => $items):
  $catInfo = $categories[$catKey];
?>
<div class="config-category" data-category="<?= $catKey ?>">
  <div class="category-header" onclick="toggleCategory('<?= $catKey ?>')">
    <span class="collapse-icon" id="icon-<?= $catKey ?>">▼</span>
    <h3><?= htmlspecialchars($catInfo[0]) ?></h3>
  </div>
  <div class="category-body" id="body-<?= $catKey ?>">
    <?php foreach ($items as $key => $value):
      $desc = $keyDescriptions[$key] ?? '';
      $isSpecial = in_array($key, $specialKeys);
      $isBool = in_array($key, $booleanKeys);
      $isNum = in_array($key, $numericKeys);
      $isTextarea = !$isSpecial && (in_array($key, $textareaKeys) || strlen($value) > 120);
      $isSecret = (stripos($key, 'API_KEY') !== false || stripos($key, 'WEBHOOK') !== false || stripos($key, 'TOKEN') !== false);
    ?>

    <?php if ($key === 'BIGJIMMY_ABANDONED_STATUS'): ?>
    <!-- BIGJIMMY_ABANDONED_STATUS: status dropdown -->
    <div class="config-row" data-key="<?= htmlspecialchars($key) ?>">
      <div class="config-key">
        <?= htmlspecialchars($key) ?>
        <?php if ($desc): ?><span class="key-description"><?= htmlspecialchars($desc) ?></span><?php endif; ?>
      </div>
      <div class="config-value">
        <select class="status-select config-input" data-key="<?= htmlspecialchars($key) ?>" data-orig="<?= htmlspecialchars($value) ?>">
          <?php foreach ($huntinfo->statuses as $s): ?>
            <option value="<?= htmlspecialchars($s->name) ?>" <?= $s->name === $value ? 'selected' : '' ?>><?= $s->emoji ?> <?= htmlspecialchars($s->name) ?></option>
          <?php endforeach; ?>
        </select>
      </div>
      <div class="config-actions">
        <button class="save-btn" onclick="saveConfig(this, '<?= htmlspecialchars($key, ENT_QUOTES) ?>')">Save</button>
        <button class="revert-btn" onclick="revertConfig('<?= htmlspecialchars($key, ENT_QUOTES) ?>')">Revert</button>
      </div>
    </div>

    <?php elseif ($key === 'STATUS_METADATA'):
      $statuses = json_decode($value, true) ?: [];
    ?>
    <!-- STATUS_METADATA: structured editor -->
    <div class="config-row wide-editor" data-key="<?= htmlspecialchars($key) ?>">
      <div class="config-key">
        <?= htmlspecialchars($key) ?>
        <?php if ($desc): ?><span class="key-description"><?= htmlspecialchars($desc) ?></span><?php endif; ?>
      </div>
      <div class="config-value">
        <div class="meta-editor" id="status-editor">
          <div class="editor-note">
            <strong>Note:</strong> Status names come from the <code>puzzle.status</code> ENUM column in the database schema.
            To add a completely new status, the ENUM must be altered in MySQL first
            (<code>ALTER TABLE puzzle MODIFY COLUMN status ENUM(…)</code>), then add a row here to define its emoji, display text, and sort order.
          </div>
          <table>
            <thead>
              <tr>
                <th>Status Name</th>
                <th>Emoji</th>
                <th>Text</th>
                <th>Order</th>
              </tr>
            </thead>
            <tbody id="status-rows">
              <?php foreach ($statuses as $i => $s): ?>
              <tr>
                <td class="col-name"><input type="text" value="<?= htmlspecialchars($s['name'] ?? '') ?>" data-field="name" readonly></td>
                <td class="col-emoji"><input type="text" value="<?= htmlspecialchars($s['emoji'] ?? '') ?>" data-field="emoji"></td>
                <td class="col-text"><input type="text" value="<?= htmlspecialchars($s['text'] ?? '') ?>" data-field="text"></td>
                <td class="col-order"><input type="number" value="<?= (int)($s['order'] ?? 50) ?>" data-field="order"></td>
                <td class="col-actions"><button class="remove-row-btn" title="Remove" onclick="this.closest('tr').remove()">×</button></td>
              </tr>
              <?php endforeach; ?>
            </tbody>
          </table>
        </div>
        <input type="hidden" class="config-input" data-key="STATUS_METADATA" data-orig="<?= htmlspecialchars($value) ?>" value="<?= htmlspecialchars($value) ?>">
      </div>
      <div class="config-actions">
        <button class="save-btn" onclick="serializeStatusEditor(); saveConfig(this, 'STATUS_METADATA')">Save</button>
        <button class="revert-btn" onclick="revertStatusEditor()">Revert</button>
      </div>
    </div>

    <?php elseif ($key === 'METRICS_METADATA'):
      $metrics = json_decode($value, true) ?: [];
    ?>
    <!-- METRICS_METADATA: structured editor -->
    <div class="config-row wide-editor" data-key="<?= htmlspecialchars($key) ?>">
      <div class="config-key">
        <?= htmlspecialchars($key) ?>
        <?php if ($desc): ?><span class="key-description"><?= htmlspecialchars($desc) ?></span><?php endif; ?>
      </div>
      <div class="config-value">
        <div class="meta-editor" id="metrics-editor">
          <div class="editor-note">
            Each metric is exposed at the <code>/metrics</code> Prometheus endpoint. The <strong>key</strong> is the Prometheus metric name,
            <strong>type</strong> is gauge or counter, and <strong>db_key</strong> (optional) links it to a <code>botstats</code> table column.
          </div>
          <table>
            <thead>
              <tr>
                <th>Metric Key</th>
                <th>Type</th>
                <th>Description</th>
                <th>DB Key (optional)</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="metrics-rows">
              <?php foreach ($metrics as $mkey => $m): ?>
              <tr>
                <td class="col-name"><input type="text" value="<?= htmlspecialchars($mkey) ?>" data-field="key"></td>
                <td class="col-type">
                  <select data-field="type">
                    <option value="gauge" <?= ($m['type'] ?? '') === 'gauge' ? 'selected' : '' ?>>gauge</option>
                    <option value="counter" <?= ($m['type'] ?? '') === 'counter' ? 'selected' : '' ?>>counter</option>
                  </select>
                </td>
                <td class="col-desc"><input type="text" value="<?= htmlspecialchars($m['description'] ?? '') ?>" data-field="description"></td>
                <td class="col-dbkey"><input type="text" value="<?= htmlspecialchars($m['db_key'] ?? '') ?>" data-field="db_key" placeholder="(none)"></td>
                <td class="col-actions"><button class="remove-row-btn" title="Remove" onclick="this.closest('tr').remove()">×</button></td>
              </tr>
              <?php endforeach; ?>
            </tbody>
          </table>
          <button class="add-row-btn" onclick="addMetricRow()">+ Add Metric</button>
        </div>
        <input type="hidden" class="config-input" data-key="METRICS_METADATA" data-orig="<?= htmlspecialchars($value) ?>" value="<?= htmlspecialchars($value) ?>">
      </div>
      <div class="config-actions">
        <button class="save-btn" onclick="serializeMetricsEditor(); saveConfig(this, 'METRICS_METADATA')">Save</button>
        <button class="revert-btn" onclick="revertMetricsEditor()">Revert</button>
      </div>
    </div>

    <?php else: ?>
    <!-- Generic config row -->
    <div class="config-row" data-key="<?= htmlspecialchars($key) ?>">
      <div class="config-key">
        <?= htmlspecialchars($key) ?>
        <?php if ($desc): ?>
          <span class="key-description"><?= htmlspecialchars($desc) ?></span>
        <?php endif; ?>
      </div>
      <div class="config-value">
        <?php if ($isBool): ?>
          <div class="bool-toggle" data-key="<?= htmlspecialchars($key) ?>">
            <span class="<?= $value === 'true' ? 'active-true' : '' ?>" onclick="setBool(this, 'true')">true</span>
            <span class="<?= $value === 'false' ? 'active-false' : '' ?>" onclick="setBool(this, 'false')">false</span>
          </div>
          <input type="hidden" class="config-input" data-key="<?= htmlspecialchars($key) ?>" data-orig="<?= htmlspecialchars($value) ?>" value="<?= htmlspecialchars($value) ?>">
        <?php elseif ($isTextarea): ?>
          <textarea class="config-input" data-key="<?= htmlspecialchars($key) ?>" data-orig="<?= htmlspecialchars($value) ?>" rows="<?= min(10, max(3, substr_count($value, "\n") + 2)) ?>"><?= htmlspecialchars($value) ?></textarea>
        <?php elseif ($isNum): ?>
          <input type="number" class="config-input" data-key="<?= htmlspecialchars($key) ?>" data-orig="<?= htmlspecialchars($value) ?>" value="<?= htmlspecialchars($value) ?>">
        <?php elseif ($isSecret && $value !== ''): ?>
          <input type="password" class="config-input" data-key="<?= htmlspecialchars($key) ?>" data-orig="<?= htmlspecialchars($value) ?>" value="<?= htmlspecialchars($value) ?>" onfocus="this.type='text'" onblur="if(this.value===this.dataset.orig)this.type='password'">
        <?php else: ?>
          <input type="text" class="config-input" data-key="<?= htmlspecialchars($key) ?>" data-orig="<?= htmlspecialchars($value) ?>" value="<?= htmlspecialchars($value) ?>">
        <?php endif; ?>
      </div>
      <div class="config-actions">
        <button class="save-btn" onclick="saveConfig(this, '<?= htmlspecialchars($key, ENT_QUOTES) ?>')">Save</button>
        <button class="revert-btn" onclick="revertConfig('<?= htmlspecialchars($key, ENT_QUOTES) ?>')">Revert</button>
      </div>
    </div>
    <?php endif; ?>

    <?php endforeach; ?>
  </div>
</div>
<?php endforeach; ?>

<!-- Add new config key -->
<div class="config-category">
  <div class="category-header" onclick="toggleCategory('addnew')">
    <span class="collapse-icon collapsed" id="icon-addnew">▼</span>
    <h3>Add New Config Key</h3>
  </div>
  <div class="category-body hidden" id="body-addnew">
    <div class="add-config">
      <input type="text" id="new-key" placeholder="CONFIG_KEY" style="width: 260px;">
      <textarea id="new-value" placeholder="value" style="flex: 1; min-width: 200px;"></textarea>
      <button class="save-btn" onclick="addNewConfig()">Add</button>
    </div>
  </div>
</div>

</div><!-- end #config-content -->

<script>
const apiProxy = './apicall.php';

function dismissWarning() {
  document.getElementById('warn-modal').classList.remove('active');
  document.getElementById('config-content').style.display = '';
}

function toggleCategory(catKey) {
  const body = document.getElementById('body-' + catKey);
  const icon = document.getElementById('icon-' + catKey);
  if (body.classList.contains('hidden')) {
    body.classList.remove('hidden');
    icon.classList.remove('collapsed');
  } else {
    body.classList.add('hidden');
    icon.classList.add('collapsed');
  }
}

function setBool(span, value) {
  const toggle = span.closest('.bool-toggle');
  const key = toggle.dataset.key;
  const hidden = toggle.parentElement.querySelector('input[type="hidden"]');

  // Clear active states
  toggle.querySelectorAll('span').forEach(s => {
    s.classList.remove('active-true', 'active-false');
  });

  // Set new active state
  span.classList.add(value === 'true' ? 'active-true' : 'active-false');
  hidden.value = value;
}

async function saveConfig(btn, key) {
  const input = document.querySelector('.config-input[data-key="' + CSS.escape(key) + '"]');
  const value = input.value;
  const statusArea = document.getElementById('status-area');

  btn.disabled = true;
  btn.textContent = 'Saving…';

  try {
    const resp = await fetch(apiProxy + '?apicall=config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cfgkey: key, cfgval: value})
    });
    const data = await resp.json();

    if (data.error) throw new Error(data.error);
    if (data.status !== 'ok') throw new Error('Unexpected response');

    // Update the original value
    input.dataset.orig = value;

    // If it was a password field, re-hide it
    if (input.type === 'text' && input.onblur) {
      input.type = 'password';
    }

    // Flash green
    btn.textContent = 'Saved!';
    btn.classList.add('saved');
    const row = btn.closest('.config-row');
    row.classList.add('just-saved');

    setTimeout(() => {
      btn.textContent = 'Save';
      btn.classList.remove('saved');
      btn.disabled = false;
      row.classList.remove('just-saved');
    }, 1500);

    statusArea.innerHTML = '<div class="status-msg success">Updated <strong>' + escapeHtml(key) + '</strong> successfully.</div>';
    setTimeout(() => { statusArea.innerHTML = ''; }, 4000);
  } catch (err) {
    btn.textContent = 'Save';
    btn.disabled = false;
    statusArea.innerHTML = '<div class="status-msg error">Failed to update <strong>' + escapeHtml(key) + '</strong>: ' + escapeHtml(err.message) + '</div>';
  }
}

function revertConfig(key) {
  const input = document.querySelector('.config-input[data-key="' + CSS.escape(key) + '"]');
  input.value = input.dataset.orig;

  // If it's a boolean, update the toggle display too
  const toggle = input.parentElement.querySelector('.bool-toggle');
  if (toggle) {
    const val = input.dataset.orig;
    toggle.querySelectorAll('span').forEach(s => {
      s.classList.remove('active-true', 'active-false');
    });
    const spans = toggle.querySelectorAll('span');
    if (val === 'true') spans[0].classList.add('active-true');
    else if (val === 'false') spans[1].classList.add('active-false');
  }

  // If it's a select (status dropdown), reset selected option
  if (input.tagName === 'SELECT') {
    input.value = input.dataset.orig;
  }
}

async function addNewConfig() {
  const keyInput = document.getElementById('new-key');
  const valInput = document.getElementById('new-value');
  const key = keyInput.value.trim();
  const value = valInput.value;
  const statusArea = document.getElementById('status-area');

  if (!key) {
    statusArea.innerHTML = '<div class="status-msg error">Please enter a config key.</div>';
    return;
  }

  // Check if key already exists
  if (document.querySelector('.config-input[data-key="' + CSS.escape(key) + '"]')) {
    statusArea.innerHTML = '<div class="status-msg error">Key <strong>' + escapeHtml(key) + '</strong> already exists. Edit it above instead.</div>';
    return;
  }

  try {
    const resp = await fetch(apiProxy + '?apicall=config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cfgkey: key, cfgval: value})
    });
    const data = await resp.json();

    if (data.error) throw new Error(data.error);
    if (data.status !== 'ok') throw new Error('Unexpected response');

    statusArea.innerHTML = '<div class="status-msg success">Added <strong>' + escapeHtml(key) + '</strong>. Refreshing page…</div>';
    keyInput.value = '';
    valInput.value = '';

    // Reload to show the new key in the correct category
    setTimeout(() => location.reload(), 1000);
  } catch (err) {
    statusArea.innerHTML = '<div class="status-msg error">Failed to add <strong>' + escapeHtml(key) + '</strong>: ' + escapeHtml(err.message) + '</div>';
  }
}

function filterConfig() {
  const filter = document.getElementById('filter').value.toLowerCase();
  document.querySelectorAll('.config-row').forEach(row => {
    const key = row.dataset.key.toLowerCase();
    row.style.display = key.includes(filter) ? '' : 'none';
  });
  // Show/hide categories based on whether they have visible rows
  document.querySelectorAll('.config-category[data-category]').forEach(cat => {
    const visibleRows = cat.querySelectorAll('.config-row:not([style*="display: none"])');
    cat.style.display = visibleRows.length > 0 ? '' : 'none';
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// --- STATUS_METADATA structured editor ---

function addStatusRow() {
  const tbody = document.getElementById('status-rows');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="col-name"><input type="text" value="" data-field="name" placeholder="StatusName"></td>
    <td class="col-emoji"><input type="text" value="" data-field="emoji"></td>
    <td class="col-text"><input type="text" value="" data-field="text"></td>
    <td class="col-order"><input type="number" value="50" data-field="order"></td>
    <td class="col-actions"><button class="remove-row-btn" title="Remove" onclick="this.closest('tr').remove()">×</button></td>
  `;
  tbody.appendChild(tr);
}

function serializeStatusEditor() {
  const rows = document.querySelectorAll('#status-rows tr');
  const arr = [];
  rows.forEach(tr => {
    const name = tr.querySelector('[data-field="name"]').value.trim();
    if (!name) return;
    arr.push({
      name: name,
      emoji: tr.querySelector('[data-field="emoji"]').value,
      text: tr.querySelector('[data-field="text"]').value,
      order: parseInt(tr.querySelector('[data-field="order"]').value) || 50
    });
  });
  document.querySelector('.config-input[data-key="STATUS_METADATA"]').value = JSON.stringify(arr);
}

function revertStatusEditor() {
  const input = document.querySelector('.config-input[data-key="STATUS_METADATA"]');
  input.value = input.dataset.orig;
  const arr = JSON.parse(input.dataset.orig);
  const tbody = document.getElementById('status-rows');
  tbody.innerHTML = '';
  arr.forEach(s => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="col-name"><input type="text" value="${escapeAttr(s.name)}" data-field="name" readonly></td>
      <td class="col-emoji"><input type="text" value="${escapeAttr(s.emoji)}" data-field="emoji"></td>
      <td class="col-text"><input type="text" value="${escapeAttr(s.text)}" data-field="text"></td>
      <td class="col-order"><input type="number" value="${s.order}" data-field="order"></td>
      <td class="col-actions"><button class="remove-row-btn" title="Remove" onclick="this.closest('tr').remove()">×</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// --- METRICS_METADATA structured editor ---

function addMetricRow() {
  const tbody = document.getElementById('metrics-rows');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="col-name"><input type="text" value="" data-field="key" placeholder="metric_name"></td>
    <td class="col-type">
      <select data-field="type">
        <option value="gauge">gauge</option>
        <option value="counter">counter</option>
      </select>
    </td>
    <td class="col-desc"><input type="text" value="" data-field="description" placeholder="Description of the metric"></td>
    <td class="col-dbkey"><input type="text" value="" data-field="db_key" placeholder="(none)"></td>
    <td class="col-actions"><button class="remove-row-btn" title="Remove" onclick="this.closest('tr').remove()">×</button></td>
  `;
  tbody.appendChild(tr);
}

function serializeMetricsEditor() {
  const rows = document.querySelectorAll('#metrics-rows tr');
  const obj = {};
  rows.forEach(tr => {
    const key = tr.querySelector('[data-field="key"]').value.trim();
    if (!key) return;
    const entry = {
      type: tr.querySelector('[data-field="type"]').value,
      description: tr.querySelector('[data-field="description"]').value
    };
    const dbKey = tr.querySelector('[data-field="db_key"]').value.trim();
    if (dbKey) entry.db_key = dbKey;
    obj[key] = entry;
  });
  document.querySelector('.config-input[data-key="METRICS_METADATA"]').value = JSON.stringify(obj);
}

function revertMetricsEditor() {
  const input = document.querySelector('.config-input[data-key="METRICS_METADATA"]');
  input.value = input.dataset.orig;
  const obj = JSON.parse(input.dataset.orig);
  const tbody = document.getElementById('metrics-rows');
  tbody.innerHTML = '';
  Object.entries(obj).forEach(([key, m]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="col-name"><input type="text" value="${escapeAttr(key)}" data-field="key"></td>
      <td class="col-type">
        <select data-field="type">
          <option value="gauge" ${m.type === 'gauge' ? 'selected' : ''}>gauge</option>
          <option value="counter" ${m.type === 'counter' ? 'selected' : ''}>counter</option>
        </select>
      </td>
      <td class="col-desc"><input type="text" value="${escapeAttr(m.description || '')}" data-field="description"></td>
      <td class="col-dbkey"><input type="text" value="${escapeAttr(m.db_key || '')}" data-field="db_key" placeholder="(none)"></td>
      <td class="col-actions"><button class="remove-row-btn" title="Remove" onclick="this.closest('tr').remove()">×</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// Escape for use in HTML attributes within template literals
function escapeAttr(str) {
  return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
</script>

</body>
</html>
