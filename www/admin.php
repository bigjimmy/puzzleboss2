<?php require_once('puzzlebosslib.php'); // set pb_csrf cookie before any output ?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzztech-only Tools</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
</head>
<body class="status-page">

<?php
require_once('puzzlebosslib.php');

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



?>
<div id="app">
<div class="status-header">
  <h1>PuzzTech Super Admin Tools</h1>
</div>

<?= render_navbar('admin') ?>

<div class="info-box">
  <div class="info-box-header">
    <h3><a href="./accounts.php">Accounts Management →</a></h3>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header">
    <h3><a href="./config.php">Configuration →</a></h3>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showArchives = !showArchives">
    <span class="collapse-icon" :class="{ collapsed: !showArchives }">▼</span>
    <h3>Hunt Archives</h3>
  </div>
  <div class="info-box-content" v-show="showArchives" v-cloak>
  <p>
    Each hunt reset writes a snapshot of the hunt it is about to wipe. These are
    the readable parts of it: every puzzle with its round, status, answer and
    solvers, and the complete activity log with puzzle and solver names resolved.
    Open them in a spreadsheet for scoring or stats. The database dumps taken at
    the same moment are not downloadable here — they contain credentials.
  </p>
<?php
$backups_error = null;
$backups = [];
$resp = readapi_internal('/backups');
if ($resp === null || !isset($resp->status) || $resp->status !== 'ok') {
    $backups_error = ($resp->error ?? 'Could not reach the archive store.');
} else {
    $backups = $resp->backups ?? [];
}

if ($backups_error !== null) {
    echo '<p class="error"><strong>Archives unavailable:</strong> '
         . htmlspecialchars($backups_error) . '</p>';
} elseif (empty($backups)) {
    echo '<p><em>No archives yet. The first one appears after the next hunt reset.</em></p>';
} else {
    echo '<table class="data-table"><thead><tr><th>Hunt reset</th><th>Download</th></tr></thead><tbody>';
    foreach ($backups as $backup) {
        $ts = htmlspecialchars($backup->timestamp);
        echo '<tr><td><code>' . $ts . '</code></td><td>';
        $links = [];
        foreach (($backup->files ?? []) as $f) {
            $name = htmlspecialchars($f->name);
            $kb = number_format(($f->compressed_bytes ?? 0) / 1024, 0);
            $links[] = '<a href="./backupdownload.php?ts=' . urlencode($backup->timestamp)
                     . '&amp;file=' . urlencode($f->name) . '">' . $name . '</a>'
                     . ' <span style="color: var(--text-secondary)">(' . $kb . ' KB compressed)</span>';
        }
        echo implode('<br>', $links);
        echo '</td></tr>';
    }
    echo '</tbody></table>';
}
?>
  </div>
</div>



</div>

<script>
const { createApp } = Vue;

createApp({
  data() {
    return {
      showArchives: false,
    }
  }
}).mount('#app');
</script>
</body>
</html>
