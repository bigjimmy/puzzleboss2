<?php
require('puzzlebosslib.php');

// Replace placeholder with actual BIN_URI (supports both <<>> and <<<PBROOTURI>>> formats)
$bookmarkuri = trim(str_replace(['<<<PBROOTURI>>>', '<<>>'], [$pbroot, $pbroot], $bookmarkuri));

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzzleboss-only Tools</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
</head>
<body class="status-page">
<div id="app">
<div class="status-header">
  <h1>Puzzleboss-only Admin Tools</h1>
</div>

<?= render_navbar('pbtools') ?>

<div class="info-box">
  <div class="info-box-header" @click="showBookmarklet = !showBookmarklet">
    <span class="collapse-icon" :class="{ collapsed: !showBookmarklet }">▼</span>
    <h3>New Puzzle / Check for Puzzles Bookmarklet</h3>
  </div>
  <div class="info-box-content" v-show="showBookmarklet">
A major timesaver for Puzzlebosses, this bookmarklet works in two ways:
<ul>
  <li>On a puzzle page, click it to create a new puzzle</li>
  <li>On the List of Puzzles page (<tt>/puzzles</tt>), click it to check if PB is missing anything.</li>
</ul>
<table class="table-cols-35-65 table-wide">
  <tr>
    <td>Drag this link to your bookmarks:</td>
    <td><a href="<?= $bookmarkuri ?>">Add to Puzzboss</a></td>
  </tr>
  <tr>
    <td>Or alternatively, copy the following into a new bookmark:</td>
    <td>
      <div class="code-block">
        <code><?= $bookmarkuri ?></code>
      </div>
    </td>
  </tr>
</table>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showSheetsCookies = !showSheetsCookies">
    <span class="collapse-icon" :class="{ collapsed: !showSheetsCookies }">▼</span>
    <h3>Refresh Google Sheets Add-on Credentials</h3>
  </div>
  <div class="info-box-content" v-show="showSheetsCookies">
<?php
// Handle credential submission
if (isset($_POST['update_sheets_creds'])) {
  $raw_cookies = trim($_POST['raw_cookies'] ?? '');
  $invoke_url = trim($_POST['invoke_url'] ?? '');
  $errors = [];
  $successes = [];

  if (!empty($raw_cookies)) {
    // Parse raw Cookie header into JSON object
    $cookies = [];
    foreach (explode(';', $raw_cookies) as $part) {
      $part = trim($part);
      if (strpos($part, '=') !== false) {
        list($name, $value) = explode('=', $part, 2);
        $cookies[trim($name)] = trim($value);
      }
    }
    // Validate: need at least the 4 core cookies
    $required = ['SID', 'OSID', '__Secure-1PSID', '__Secure-1PSIDTS'];
    $missing = array_diff($required, array_keys($cookies));
    if (!empty($missing)) {
      $errors[] = 'Missing required cookies: ' . implode(', ', $missing);
    } else {
      // Ensure __Secure-3PSIDTS matches __Secure-1PSIDTS if not present
      if (!isset($cookies['__Secure-3PSIDTS']) && isset($cookies['__Secure-1PSIDTS'])) {
        $cookies['__Secure-3PSIDTS'] = $cookies['__Secure-1PSIDTS'];
      }
      $cookies_json = json_encode($cookies);
      $resp = postapi('/config', ['cfgkey' => 'SHEETS_ADDON_COOKIES', 'cfgval' => $cookies_json]);
      if ($resp && isset($resp->status) && $resp->status == 'ok') {
        $successes[] = 'Updated SHEETS_ADDON_COOKIES (' . count($cookies) . ' cookies: ' . implode(', ', array_keys($cookies)) . ')';
      } else {
        $errors[] = 'Failed to save cookies to config';
      }
    }
  }

  if (!empty($invoke_url)) {
    // Store the full query string from the invoke URL so all browser params
    // (includes_info_params, ctx, eei, ruid, etc.) are preserved. At invocation
    // time, the "id" param is swapped to the target sheet ID.
    $parsed = parse_url($invoke_url);
    $full_query = $parsed['query'] ?? '';
    parse_str($full_query, $qs);
    $sid = $qs['sid'] ?? '';
    $token = $qs['token'] ?? '';
    $lib = $qs['lib'] ?? '';
    $did = $qs['did'] ?? '';

    if (empty($sid) || empty($token)) {
      $errors[] = 'Invoke URL missing sid or token parameters';
    } elseif (empty($lib) || empty($did)) {
      $errors[] = 'Invoke URL missing lib or did parameters (is this a scripts/invoke URL?)';
    } else {
      $invoke_params = ['query_string' => $full_query];
      $invoke_json = json_encode($invoke_params);
      $resp = postapi('/config', ['cfgkey' => 'SHEETS_ADDON_INVOKE_PARAMS', 'cfgval' => $invoke_json]);
      if ($resp && isset($resp->status) && $resp->status == 'ok') {
        $successes[] = 'Updated SHEETS_ADDON_INVOKE_PARAMS (sid=' . substr($sid, 0, 10) . '... lib=' . substr($lib, 0, 15) . '... full query string preserved)';
      } else {
        $errors[] = 'Failed to save invoke params to config';
      }
    }
  }

  if (empty($raw_cookies) && empty($invoke_url)) {
    $errors[] = 'Please provide at least one of: Cookie header or Invoke URL';
  }

  foreach ($successes as $msg) {
    echo '<div class="success">✅ ' . htmlentities($msg) . '</div>';
  }
  foreach ($errors as $msg) {
    echo '<div class="error">❌ ' . htmlentities($msg) . '</div>';
  }
}
?>
<p>
  When the Google Sheets add-on activation starts failing (401 errors), use this form to refresh
  the browser credentials. You need data from Chrome DevTools on a Google Sheets page.
</p>
<details>
  <summary><strong>How to get the data from Chrome DevTools</strong></summary>
  <ol>
    <li>Open any puzzle sheet that has the PB add-on active</li>
    <li>Open DevTools (F12) → <strong>Network</strong> tab</li>
    <li>In the filter box, type <code>scripts/invoke</code></li>
    <li>Trigger the add-on (e.g., right-click a cell → "Show Metadata as Note", or wait for an edit to trigger it)</li>
    <li>Click on the <code>invoke</code> request that appears in the Network tab</li>
    <li>From the <strong>Headers</strong> tab:
      <ul>
        <li><strong>Cookie:</strong> Right-click the Cookie header value → "Copy value"</li>
        <li><strong>Request URL:</strong> Right-click the URL → "Copy link address" (the full URL with query params)</li>
      </ul>
    </li>
    <li>Paste both values into the form below and submit</li>
  </ol>
</details>
<br>
<form action="pbtools.php" method="post">
  <table class="table-wide">
    <tr>
      <td style="width:180px"><strong>Cookie header:</strong><br><small>(from Request Headers)</small></td>
      <td><textarea name="raw_cookies" rows="3" style="width:100%;font-family:monospace;font-size:11px" placeholder="COMPASS=...; SID=...; OSID=...; __Secure-1PSID=...; __Secure-1PSIDTS=..."></textarea></td>
    </tr>
    <tr>
      <td><strong>Invoke URL:</strong><br><small>(full Request URL)</small></td>
      <td><textarea name="invoke_url" rows="3" style="width:100%;font-family:monospace;font-size:11px" placeholder="https://docs.google.com/spreadsheets/d/.../scripts/invoke?id=...&sid=...&token=...&lib=...&did=..."></textarea></td>
    </tr>
    <tr>
      <td></td>
      <td>
        <input type="submit" name="update_sheets_creds" value="Update Add-on Credentials" onclick="return confirm('This will update the Google Sheets add-on credentials used for puzzle activation. Continue?');">
      </td>
    </tr>
  </table>
</form>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showAddPuzzle = !showAddPuzzle">
    <span class="collapse-icon" :class="{ collapsed: !showAddPuzzle }">▼</span>
    <h3>Add New Puzzle</h3>
  </div>
  <div class="info-box-content" v-show="showAddPuzzle">
    <strong><a href="addpuzzle.php" target="_blank">Page to add new puzzles</a></strong>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showAddRound = !showAddRound">
    <span class="collapse-icon" :class="{ collapsed: !showAddRound }">▼</span>
    <h3>Add New Round</h3>
  </div>
  <div class="info-box-content" v-show="showAddRound">
<p>
  <strong>No longer necessary!</strong>
  If you use the bookmarklet above on a puzzle in a new round,
  you can create new rounds
  <a href="addpuzzle.php" target="_blank">on the new puzzle page</a>.
</p>
<table class="table-cols-65-35">
  <tr>
    <td>To add a new round (enter round name):</td>
    <td>
      <form action="addround.php" method="post" class="inline-form">
        <input type="text" name="name">
        <input type="submit" name="submit" value="Add Round">
      </form>
    </td>
  </tr>
</table>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showSolverAssignment = !showSolverAssignment">
    <span class="collapse-icon" :class="{ collapsed: !showSolverAssignment }">▼</span>
    <h3>Solver Assignment</h3>
  </div>
  <div class="info-box-content" v-show="showSolverAssignment">
<table class="table-cols-65-35">
  <tr>
    <td>To manually edit a solver's current puzzle assignment (enter username):</td>
    <td>
      <form action="editsolver.php" method="get" class="inline-form">
        <input type="text" name="assumedid">
        <input type="submit" name="ok" value="Edit Solver">
      </form>
    </td>
  </tr>
</table>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showTagManagement = !showTagManagement">
    <span class="collapse-icon" :class="{ collapsed: !showTagManagement }">▼</span>
    <h3>Tag Management</h3>
  </div>
  <div class="info-box-content" v-show="showTagManagement">
<?php
// Handle tag creation
if (isset($_POST['create_tag']) && !empty($_POST['new_tag_name'])) {
  $new_tag_name = trim($_POST['new_tag_name']);
  try {
    $responseobj = postapi('/tags', array('name' => $new_tag_name));
    if ($responseobj && $responseobj->status == 'ok') {
      echo '<div class="success">✅ Tag "' . htmlentities($responseobj->tag->name) . '" created (ID: ' . $responseobj->tag->id . ').</div>';
    } else {
      $error_msg = $responseobj && isset($responseobj->error) ? $responseobj->error : 'Unknown error';
      echo '<div class="error">❌ Failed to create tag: ' . htmlentities($error_msg) . '</div>';
    }
  } catch (Exception $e) {
    echo '<div class="error">❌ Error: ' . htmlentities($e->getMessage()) . '</div>';
  }
}

// Handle tag deletion
if (isset($_POST['delete_tag']) && !empty($_POST['tag_to_delete'])) {
  $tag_to_delete = $_POST['tag_to_delete'];
  try {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $GLOBALS['apiroot'] . '/tags/' . urlencode($tag_to_delete));
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    $result = json_decode($response);
    if ($http_code == 200 && $result && $result->status == 'ok') {
      echo '<div class="success">✅ Tag "' . htmlentities($tag_to_delete) . '" deleted. Removed from ' . $result->puzzles_updated . ' puzzle(s).</div>';
    } else {
      $error_msg = $result && $result->error ? $result->error : 'Unknown error';
      echo '<div class="error">❌ Failed to delete tag: ' . htmlentities($error_msg) . '</div>';
    }
  } catch (Exception $e) {
    echo '<div class="error">❌ Error: ' . htmlentities($e->getMessage()) . '</div>';
  }
}

// Fetch all tags
$alltags = array();
try {
  $tagsobj = readapi('/tags');
  $alltags = isset($tagsobj->tags) ? $tagsobj->tags : array();
} catch (Exception $e) {
  echo '<div class="error">Failed to fetch tags: ' . htmlentities($e->getMessage()) . '</div>';
}
?>

<p><a href="search.php">Search Puzzles by Tag</a></p>

<table class="table-cols-65-35">
  <tr>
    <td>Create a new tag:</td>
    <td>
      <form action="pbtools.php" method="post" class="inline-form">
        <input type="text" name="new_tag_name" placeholder="tag-name" pattern="[a-zA-Z0-9_-]+" title="Alphanumeric, hyphens, and underscores only" required>
        <input type="submit" name="create_tag" value="Create Tag">
      </form>
    </td>
  </tr>
</table>
<small><em>Tag names can only contain letters, numbers, hyphens, and underscores. Will be converted to lowercase.</em></small>
<br><br>

<?php if (count($alltags) > 0): ?>
<strong>Existing Tags:</strong>
<table>
  <tr>
    <th>Tag Name</th>
    <th>ID</th>
    <th>Action</th>
  </tr>
  <?php foreach ($alltags as $tag): ?>
  <tr>
    <td><?= htmlentities($tag->name) ?></td>
    <td><?= $tag->id ?></td>
    <td>
      <form action="pbtools.php" method="post" class="inline-form" onsubmit="return confirm('Are you sure you want to delete tag \'<?= htmlentities($tag->name) ?>\'? This will remove it from all puzzles.');">
        <input type="hidden" name="tag_to_delete" value="<?= htmlentities($tag->name) ?>">
        <input type="submit" name="delete_tag" value="Delete" style="color: red;">
      </form>
    </td>
  </tr>
  <?php endforeach; ?>
</table>
<?php else: ?>
<p><em>No tags defined in the system yet.</em></p>
<?php endif; ?>
  </div>
</div>

</div>

<script>
const { createApp } = Vue;

createApp({
  data() {
    return {
      showBookmarklet: true,
      showSheetsCookies: false,
      showAddPuzzle: true,
      showAddRound: true,
      showSolverAssignment: true,
      showTagManagement: true
    }
  }
}).mount('#app');
</script>
</body>
</html>
