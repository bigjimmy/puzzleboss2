<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Accounts Management</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <style>
    #accounts-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    #accounts-table th {
      position: sticky;
      top: 0;
      background: var(--bg-light-blue);
      border-bottom: 2px solid var(--border-medium);
      padding: 8px 6px;
      text-align: left;
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
      font-size: 12px;
    }
    #accounts-table th:hover {
      background: var(--bg-light-gray);
    }
    #accounts-table th .sort-arrow {
      opacity: 0.3;
      margin-left: 4px;
    }
    #accounts-table th.sorted .sort-arrow {
      opacity: 1;
    }
    #accounts-table td {
      padding: 4px 6px;
      border-bottom: 1px solid var(--border-light);
      vertical-align: middle;
    }
    #accounts-table tr:hover {
      background: var(--bg-light-blue);
    }
    #accounts-table .col-id {
      width: 40px;
      color: var(--text-tertiary);
      text-align: right;
    }
    #accounts-table .col-username {
      font-family: var(--font-mono);
      font-weight: 600;
    }
    #accounts-table .col-discord {
      color: var(--text-secondary);
    }
    #accounts-table .col-google {
      color: var(--text-secondary);
      font-size: 12px;
    }
    #accounts-table .col-google.na {
      color: var(--text-tertiary);
    }
    #accounts-table tr.no-google {
      background: var(--warning-bg);
    }
    #accounts-table tr.no-google:hover {
      background: #fff0e0;
    }
    #accounts-table tr.no-solver {
      background: var(--bg-page);
    }
    #accounts-table tr.no-solver:hover {
      background: #e0f0ff;
    }
    .mismatch-badge {
      font-size: 10px;
      padding: 1px 5px;
      border-radius: 3px;
      font-weight: 600;
      white-space: nowrap;
    }
    .mismatch-badge.no-google {
      background: #fff0e0;
      color: var(--warning-color);
    }
    .mismatch-badge.no-solver {
      background: #e0f0ff;
      color: #1a5fb4;
    }
    #accounts-table .priv-yes {
      color: green;
      font-weight: bold;
    }
    #accounts-table .priv-no {
      color: var(--text-tertiary);
    }
    #accounts-table .col-priv-header,
    #accounts-table .col-priv {
      text-align: center;
      min-width: 40px;
    }
    #accounts-table .col-priv {
      cursor: pointer;
      user-select: none;
    }
    #accounts-table .col-priv:hover {
      background: var(--bg-light-gray);
      border-radius: 3px;
    }
    #accounts-table .col-priv.pending {
      font-style: italic;
      background: #fff8e0;
    }
    .col-actions {
      white-space: nowrap;
    }
    .update-btn { margin-right: 4px; }
    .account-count {
      color: var(--text-secondary);
      font-size: 14px;
      font-weight: normal;
    }
    .google-note {
      color: var(--text-tertiary);
      font-size: 12px;
      font-style: italic;
    }
    .filter-input { width: 250px; }
    .suspended-badge {
      background: var(--danger-bg-light);
      color: var(--danger-color);
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 11px;
      font-weight: 600;
    }
    .admin-badge {
      background: var(--bg-light-blue);
      color: var(--primary-blue);
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 11px;
      font-weight: 600;
    }

    /* Delete confirmation modal overrides (base in pb-ui.css) */
    .modal { max-width: 480px; }
    .modal h3 { color: var(--danger-color); }
    .modal .warning {
      background: #fff3f3;
      border: 1px solid #fcc;
    }
    .modal .confirm-input {
      width: 100%;
      padding: 8px;
      border: 2px solid var(--border-medium);
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 16px;
      margin: 10px 0;
      box-sizing: border-box;
    }
    .modal .confirm-input.matched {
      border-color: var(--danger-color);
    }
    .status-msg { margin: 10px 0; }
  </style>
  <script type="module" src="./pb-utils.js"></script>
</head>
<body class="status-page">

<?php
require('puzzlebosslib.php');

$uid = getauthenticateduser();
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

// Fetch all data server-side in 3 API calls
$solversResp = readapi('/solvers');
$solvers = $solversResp->solvers ?? [];

$privsResp = readapi('/privs');
$privsRows = $privsResp->privs ?? [];

$googleResp = readapi('/google/users');
$googleUsers = $googleResp->users ?? [];
$googleDisabled = isset($googleResp->google_disabled) && $googleResp->google_disabled;
$googleError = isset($googleResp->error) ? $googleResp->error : '';

// Index privs by uid for fast lookup
$privsByUid = [];
foreach ($privsRows as $p) {
  $privsByUid[$p->uid] = $p;
}

// Index Google users by lowercase username
$googleByUsername = [];
foreach ($googleUsers as $gu) {
  $googleByUsername[strtolower($gu->username)] = $gu;
}

$hasGoogle = count($googleUsers) > 0;
$googleCount = count($googleUsers);

// Build set of solver usernames (lowercase) for orphan detection
$solverNames = [];
foreach ($solvers as $s) {
  $solverNames[strtolower($s->name)] = true;
}

// Find Google accounts with no matching solver
$googleOrphans = [];
foreach ($googleUsers as $gu) {
  if (!isset($solverNames[strtolower($gu->username)])) {
    $googleOrphans[] = $gu;
  }
}

// Count solvers missing from Google
$solversMissingGoogle = 0;
if ($hasGoogle) {
  foreach ($solvers as $s) {
    if (!isset($googleByUsername[strtolower($s->name)])) {
      $solversMissingGoogle++;
    }
  }
}
?>

<div class="status-header">
  <h1>Accounts Management</h1>
</div>

<?= render_navbar() ?>

<div id="status-area"></div>

<div class="toolbar">
  <input type="text" class="filter-input" id="filter" placeholder="Filter by username or name..." oninput="filterTable()">
  <button class="refresh-btn" onclick="location.reload()">Refresh</button>
  <span class="account-count"><?= count($solvers) ?> solvers, <?= $googleCount ?> Google accounts<?php
    if ($solversMissingGoogle > 0 || count($googleOrphans) > 0) {
      $parts = [];
      if ($solversMissingGoogle > 0) $parts[] = $solversMissingGoogle . ' missing Google';
      if (count($googleOrphans) > 0) $parts[] = count($googleOrphans) . ' orphaned Google';
      echo ' — ' . implode(', ', $parts);
    }
  ?></span>
  <?php if ($googleDisabled): ?>
    <span class="google-note">— Google API disabled</span>
  <?php elseif ($googleError): ?>
    <span class="google-note">— Google API error: <?= htmlspecialchars($googleError) ?></span>
  <?php endif; ?>
</div>

<table id="accounts-table">
  <thead>
    <tr>
      <th class="col-id sorted" data-col="id" onclick="sortTable('id')">ID <span class="sort-arrow">▲</span></th>
      <th data-col="username" onclick="sortTable('username')">Username <span class="sort-arrow">▲</span></th>
      <th data-col="fullname" onclick="sortTable('fullname')">Full Name <span class="sort-arrow">▲</span></th>
      <th data-col="discord" onclick="sortTable('discord')">Discord <span class="sort-arrow">▲</span></th>
      <th data-col="googlename" onclick="sortTable('googlename')">Google Name <span class="sort-arrow">▲</span></th>
      <th>Email</th>
      <th>Recovery Email</th>
      <th data-col="created" onclick="sortTable('created')">Created <span class="sort-arrow">▲</span></th>
      <th data-col="lastlogin" onclick="sortTable('lastlogin')">Last Login <span class="sort-arrow">▲</span></th>
      <th data-col="status" onclick="sortTable('status')">Status <span class="sort-arrow">▲</span></th>
      <th class="col-priv-header" data-col="pt" onclick="sortTable('pt')">PT <span class="sort-arrow">▲</span></th>
      <th class="col-priv-header" data-col="pb" onclick="sortTable('pb')">PB <span class="sort-arrow">▲</span></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <?php foreach ($solvers as $solver):
      $solverId = $solver->id;
      $solverName = $solver->name;
      $solverNameLower = strtolower($solverName);
      $fullname = $solver->fullname ?? '';
      $chatName = $solver->chat_name ?? '';

      // Privilege lookup
      $priv = $privsByUid[$solverId] ?? null;
      $isPuzztech = ($priv && isset($priv->puzztech) && $priv->puzztech === 'YES') ? 'YES' : 'NO';
      $isPuzzleboss = ($priv && isset($priv->puzzleboss) && $priv->puzzleboss === 'YES') ? 'YES' : 'NO';

      // Google lookup
      $g = $googleByUsername[$solverNameLower] ?? null;

      // Compute sortable status string
      if ($g) {
        if ($g->suspended) $statusStr = 'SUSPENDED';
        elseif ($g->isAdmin) $statusStr = 'ADMIN';
        else $statusStr = 'OK';
      } elseif ($hasGoogle) {
        $statusStr = 'NO GOOGLE';
      } else {
        $statusStr = '';
      }
    ?>
    <tr class="<?= (!$g && $hasGoogle) ? 'no-google' : '' ?>"
        data-username="<?= htmlspecialchars($solverName) ?>"
        data-fullname="<?= htmlspecialchars($fullname) ?>"
        data-discord="<?= htmlspecialchars($chatName) ?>"
        data-googlename="<?= $g ? htmlspecialchars($g->fullName) : '' ?>"
        data-created="<?= $g ? htmlspecialchars($g->creationTime) : '' ?>"
        data-lastlogin="<?= $g ? htmlspecialchars($g->lastLoginTime) : '' ?>"
        data-status="<?= $statusStr ?>"
        data-pt="<?= $isPuzztech ?>"
        data-pb="<?= $isPuzzleboss ?>"
        data-id="<?= $solverId ?>">
      <td class="col-id"><?= $solverId ?></td>
      <td class="col-username"><?= htmlspecialchars($solverName) ?></td>
      <td><?= htmlspecialchars($fullname) ?></td>
      <td class="col-discord"><?= htmlspecialchars($chatName) ?></td>
      <td class="col-google <?= $g ? '' : 'na' ?>"><?= $g ? htmlspecialchars($g->fullName) : '—' ?></td>
      <td class="col-google <?= $g ? '' : 'na' ?>"><?= $g ? htmlspecialchars($g->primaryEmail) : '—' ?></td>
      <td class="col-google <?= $g ? '' : 'na' ?>"><?= $g ? htmlspecialchars($g->recoveryEmail ?: '—') : '—' ?></td>
      <td class="col-google <?= $g ? '' : 'na' ?>"><?= $g ? substr($g->creationTime, 0, 10) : '—' ?></td>
      <td class="col-google <?= $g ? '' : 'na' ?>"><?= $g ? ($g->lastLoginTime ? substr($g->lastLoginTime, 0, 10) : 'never') : '—' ?></td>
      <td class="col-google">
        <?php if ($g): ?>
          <?php if ($g->suspended): ?><span class="suspended-badge">SUSPENDED</span><?php endif; ?>
          <?php if ($g->isAdmin): ?><span class="admin-badge">ADMIN</span><?php endif; ?>
          <?php if (!$g->suspended && !$g->isAdmin): ?>OK<?php endif; ?>
        <?php elseif ($hasGoogle): ?>
          <span class="mismatch-badge no-google">NO GOOGLE</span>
        <?php else: ?>
          <span class="na">—</span>
        <?php endif; ?>
      </td>
      <td class="col-puzztech col-priv <?= $isPuzztech === 'YES' ? 'priv-yes' : 'priv-no' ?>"
          onclick="togglePriv(this, 'puzztech')"><?= $isPuzztech ?></td>
      <td class="col-puzzleboss col-priv <?= $isPuzzleboss === 'YES' ? 'priv-yes' : 'priv-no' ?>"
          onclick="togglePriv(this, 'puzzleboss')"><?= $isPuzzleboss ?></td>
      <td class="col-actions">
        <button class="update-btn btn-secondary" onclick="savePrivs(this)">Update</button>
        <button class="delete-btn btn-danger" onclick="confirmDelete('<?= htmlspecialchars($solverName, ENT_QUOTES) ?>')">Delete</button>
      </td>
    </tr>
    <?php endforeach; ?>
    <?php foreach ($googleOrphans as $gu): ?>
    <tr class="no-solver"
        data-username="<?= htmlspecialchars($gu->username) ?>"
        data-fullname=""
        data-discord=""
        data-googlename="<?= htmlspecialchars($gu->fullName) ?>"
        data-created="<?= htmlspecialchars($gu->creationTime) ?>"
        data-lastlogin="<?= htmlspecialchars($gu->lastLoginTime) ?>"
        data-status="NO SOLVER<?= $gu->suspended ? ' SUSPENDED' : '' ?>"
        data-pt=""
        data-pb=""
        data-id="">
      <td class="col-id na">—</td>
      <td class="col-username"><?= htmlspecialchars($gu->username) ?></td>
      <td></td>
      <td class="col-discord"></td>
      <td class="col-google"><?= htmlspecialchars($gu->fullName) ?></td>
      <td class="col-google"><?= htmlspecialchars($gu->primaryEmail) ?></td>
      <td class="col-google"><?= htmlspecialchars($gu->recoveryEmail ?: '—') ?></td>
      <td class="col-google"><?= substr($gu->creationTime, 0, 10) ?></td>
      <td class="col-google"><?= $gu->lastLoginTime ? substr($gu->lastLoginTime, 0, 10) : 'never' ?></td>
      <td class="col-google">
        <span class="mismatch-badge no-solver">NO SOLVER</span>
        <?php if ($gu->suspended): ?> <span class="suspended-badge">SUSPENDED</span><?php endif; ?>
        <?php if ($gu->isAdmin): ?> <span class="admin-badge">ADMIN</span><?php endif; ?>
      </td>
      <td class="col-priv na">—</td>
      <td class="col-priv na">—</td>
      <td class="col-actions"></td>
    </tr>
    <?php endforeach; ?>
  </tbody>
</table>

<!-- Delete confirmation modal -->
<div class="modal-overlay" id="delete-modal">
  <div class="modal">
    <h3>⚠️ Delete Account</h3>
    <p>This will <strong>permanently delete</strong> the following account:</p>
    <div class="warning">
      <strong>Username:</strong> <code id="modal-username"></code><br><br>
      This action will:
      <ul style="margin: 5px 0;">
        <li>Remove the user from the Puzzleboss solver database</li>
        <li>Delete their Google Workspace account</li>
      </ul>
      <strong>This cannot be undone.</strong>
    </div>
    <p>Type the username to confirm:</p>
    <input type="text" class="confirm-input" id="confirm-input" autocomplete="off" oninput="checkConfirmInput()">
    <div class="modal-buttons">
      <button class="btn-cancel btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-delete btn-danger" id="btn-confirm-delete" disabled onclick="executeDelete()">Delete Account</button>
    </div>
  </div>
</div>

<script>
const { API_PROXY: apiProxy, escapeHtml, showStatus } = window.pbUtils;
let deleteTarget = '';
let sortCol = 'id';
let sortAsc = true;

// Original privilege values per solver id (for pending detection)
const origPrivs = {};
<?php foreach ($solvers as $solver):
  $solverId = $solver->id;
  $priv = $privsByUid[$solverId] ?? null;
  $pt = ($priv && isset($priv->puzztech) && $priv->puzztech === 'YES') ? 'YES' : 'NO';
  $pb = ($priv && isset($priv->puzzleboss) && $priv->puzzleboss === 'YES') ? 'YES' : 'NO';
?>
origPrivs[<?= $solverId ?>] = {puzztech: '<?= $pt ?>', puzzleboss: '<?= $pb ?>'};
<?php endforeach; ?>

function togglePriv(cell, priv) {
  const current = cell.textContent.trim();
  const newVal = current === 'YES' ? 'NO' : 'YES';
  cell.textContent = newVal;
  cell.className = 'col-' + priv + ' col-priv ' + (newVal === 'YES' ? 'priv-yes' : 'priv-no');

  const row = cell.closest('tr');
  const id = row.dataset.id;
  const orig = origPrivs[id] || {};

  // Mark pending if different from original
  const origVal = priv === 'puzztech' ? orig.puzztech : orig.puzzleboss;
  if (newVal !== origVal) {
    cell.classList.add('pending');
  } else {
    cell.classList.remove('pending');
  }
}

async function savePrivs(btn) {
  const row = btn.closest('tr');
  const id = row.dataset.id;
  const username = row.dataset.username;
  const orig = origPrivs[id] || {};

  const ptCell = row.querySelector('.col-puzztech');
  const pbCell = row.querySelector('.col-puzzleboss');
  const newPt = ptCell.textContent.trim();
  const newPb = pbCell.textContent.trim();

  btn.disabled = true;
  btn.textContent = 'Saving…';

  const statusArea = document.getElementById('status-area');
  try {
    const updates = [];
    if (newPt !== orig.puzztech) {
      updates.push(
        fetch(apiProxy + '?apicall=rbac&apiparam1=puzztech&apiparam2=' + id, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({allowed: newPt})
        }).then(r => r.json())
      );
    }
    if (newPb !== orig.puzzleboss) {
      updates.push(
        fetch(apiProxy + '?apicall=rbac&apiparam1=puzzleboss&apiparam2=' + id, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({allowed: newPb})
        }).then(r => r.json())
      );
    }

    if (updates.length === 0) {
      btn.disabled = false;
      btn.textContent = 'Update';
      return;
    }

    const results = await Promise.all(updates);
    for (const r of results) {
      if (r.error) throw new Error(r.error);
    }
    window.onFetchSuccess?.();

    // Update originals and clear pending state
    origPrivs[id] = { puzztech: newPt, puzzleboss: newPb };
    ptCell.classList.remove('pending');
    pbCell.classList.remove('pending');

    showStatus(statusArea, 'success', 'Privileges updated for <strong>' + escapeHtml(username) + '</strong>.');
  } catch (err) {
    if (window.onFetchFailure?.()) return;
    showStatus(statusArea, 'error', 'Failed to update privileges for <strong>' + escapeHtml(username) + '</strong>: ' + escapeHtml(err.message));
  } finally {
    btn.disabled = false;
    btn.textContent = 'Update';
  }
}

function confirmDelete(username) {
  deleteTarget = username;
  document.getElementById('modal-username').textContent = username;
  document.getElementById('confirm-input').value = '';
  document.getElementById('btn-confirm-delete').disabled = true;
  document.getElementById('confirm-input').classList.remove('matched');
  document.getElementById('delete-modal').classList.add('active');
  setTimeout(() => document.getElementById('confirm-input').focus(), 100);
}

function closeModal() {
  document.getElementById('delete-modal').classList.remove('active');
  deleteTarget = '';
}

function checkConfirmInput() {
  const input = document.getElementById('confirm-input');
  const btn = document.getElementById('btn-confirm-delete');
  const matches = input.value === deleteTarget;
  btn.disabled = !matches;
  input.classList.toggle('matched', matches);
}

async function executeDelete() {
  const username = deleteTarget;
  closeModal();

  const statusArea = document.getElementById('status-area');
  showStatus(statusArea, '', 'Deleting account <strong>' + escapeHtml(username) + '</strong>...');

  try {
    const resp = await fetch(apiProxy + '?apicall=deleteuser&apiparam1=' + encodeURIComponent(username));
    const data = await resp.json();

    if (data.error) {
      throw new Error(data.error);
    }
    if (data.status !== 'ok') {
      throw new Error(data.message || 'Deletion failed');
    }

    window.onFetchSuccess?.();

    // Remove the row from the table
    const row = document.querySelector('tr[data-username="' + CSS.escape(username) + '"]');
    if (row) row.remove();

    // Update count
    const count = document.querySelectorAll('#accounts-table tbody tr').length;
    document.querySelector('.account-count').textContent = '(' + count + ' accounts)';

    showStatus(statusArea, 'success', 'Account <strong>' + escapeHtml(username) + '</strong> deleted successfully.');
  } catch (err) {
    if (window.onFetchFailure?.()) return;
    showStatus(statusArea, 'error', 'Failed to delete <strong>' + escapeHtml(username) + '</strong>: ' + escapeHtml(err.message));
  }
}

function filterTable() {
  const filter = document.getElementById('filter').value.toLowerCase();
  const rows = document.querySelectorAll('#accounts-table tbody tr');
  rows.forEach(row => {
    const username = row.dataset.username.toLowerCase();
    const fullname = row.dataset.fullname.toLowerCase();
    const discord = row.dataset.discord.toLowerCase();
    const googlename = (row.dataset.googlename || '').toLowerCase();
    const show = username.includes(filter) || fullname.includes(filter) || discord.includes(filter) || googlename.includes(filter);
    row.style.display = show ? '' : 'none';
  });
}

function sortTable(col) {
  if (sortCol === col) {
    sortAsc = !sortAsc;
  } else {
    sortCol = col;
    sortAsc = true;
  }

  // Update header styling
  document.querySelectorAll('#accounts-table th').forEach(th => {
    th.classList.remove('sorted');
    const arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = '▲';
  });
  const activeHeader = document.querySelector('#accounts-table th[data-col="' + col + '"]');
  if (activeHeader) {
    activeHeader.classList.add('sorted');
    activeHeader.querySelector('.sort-arrow').textContent = sortAsc ? '▲' : '▼';
  }

  const tbody = document.querySelector('#accounts-table tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));

  rows.sort((a, b) => {
    let aVal, bVal;
    if (col === 'id') {
      aVal = parseInt(a.dataset.id);
      bVal = parseInt(b.dataset.id);
    } else if (col === 'created' || col === 'lastlogin') {
      aVal = a.dataset[col] || '';
      bVal = b.dataset[col] || '';
    } else {
      aVal = (a.dataset[col] || '').toLowerCase();
      bVal = (b.dataset[col] || '').toLowerCase();
    }
    if (aVal < bVal) return sortAsc ? -1 : 1;
    if (aVal > bVal) return sortAsc ? 1 : -1;
    return 0;
  });

  rows.forEach(row => tbody.appendChild(row));
}

// Close modal on Escape key or clicking outside
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});
document.getElementById('delete-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});
</script>

</body>
</html>
