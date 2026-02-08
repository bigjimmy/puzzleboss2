<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Edit Puzzle</title>
  <meta http-equiv="cache-control" content="max-age=0" />
  <meta http-equiv="cache-control" content="no-cache" />
  <meta http-equiv="expires" content="0" />
  <meta http-equiv="expires" content="Tue, 01 Jan 1980 1:00:00 GMT" />
  <meta http-equiv="pragma" content="no-cache" />
  <link rel="stylesheet" href="./pb-ui.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
  <style>
  /* Normalize h1 height when puzzle names contain emojis */
  .status-header h1 {
    line-height: 1.15;
  }

  /* Read-only info table styling */
  .info-table td:first-child {
    font-weight: 600;
    white-space: nowrap;
  }

  .info-table td:last-child {
    min-width: 200px;
  }

  /* Edit form table styling */
  .edit-table td:first-child {
    font-weight: 600;
    white-space: nowrap;
  }
  </style>
</head>
<body class="status-page">
<?php
require('puzzlebosslib.php');

function startuseronpuzzle($id, $puzz) {
  try {
    $responseobj = postapi(
      "/solvers/" . $id . "/puzz",
      array('puzz' => $puzz),
    );
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);
  echo '<div class="success">OK.  Solver '.$id.' reassigned.</div>';
}

function updatepuzzlepart($id, $part, $value) {
  try {
    $responseobj = postapi(
      "/puzzles/" . $id . "/" . $part,
      array($part => $value),
    );
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);
  echo '<div class="success">OK.  Puzzle Part '.$part.' Updated.</div>';
}

function updateroundpart($id, $part, $value) {
  try {
    $responseobj = postapi(
      "/rounds/" . $id . "/" . $part,
      array($part => $value),
    );
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);
  echo '<div class="success">OK.  Round Part '.$part.' Updated.</div>';
}

function addtagtopuzzle($puzzid, $tagname) {
  try {
    $responseobj = postapi(
      "/puzzles/" . $puzzid . "/tags",
      array('tags' => array('add' => $tagname)),
    );
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);
  echo '<div class="success">OK.  Tag "'.$tagname.'" added to puzzle.</div>';
}

function removetagfrompuzzle($puzzid, $tagname) {
  try {
    $responseobj = postapi(
      "/puzzles/" . $puzzid . "/tags",
      array('tags' => array('remove' => $tagname)),
    );
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);
  echo '<div class="success">OK.  Tag "'.$tagname.'" removed from puzzle.</div>';
}

if (isset($_POST['submit'])) {
  if (!isset($_POST['uid'])) {
    exit_with_error_message('No Authenticated User ID Found in Request');
  }

  if (!isset($_POST['pid'])) {
    exit_with_error_message('No puzz ID Found in Request');
  }
  if ($_POST['pid'] == "") {
    exit_with_error_message('No puzz ID Found in Request');
  }

  $whatdo = "";

  if (isset($_POST['startwork'])) {
    $whatdo = "startwork";
  }

  if (isset($_POST['stopwork'])) {
    $whatdo = "stopwork";
  }

  if (isset($_POST['partupdate'])) {
    $whatdo = "partupdate";
    if (!isset($_POST['part']) || !isset($_POST['value'])) {
      exit_with_error_message(
        'Part name to update, or value to set it to not specified',
      );
    }
  }

  if (isset($_POST['addtag'])) {
    $whatdo = "addtag";
  }

  if (isset($_POST['removetag'])) {
    $whatdo = "removetag";
  }

  if (isset($_POST['newtag'])) {
    $whatdo = "newtag";
  }

  $id = $_POST['uid'];
  $puzz = $_POST['pid'];

  echo '<div class="info-box"><div class="info-box-content">';
  echo 'Attempting to change puzz ' . $whatdo . '<br>';
  switch ($whatdo) {
    case "startwork":
      startuseronpuzzle($id, $puzz);
      break;
    case "stopwork":
      startuseronpuzzle($id, "");
      break;
    case "partupdate":
      updatepuzzlepart($puzz, $_POST['part'], $_POST['value']);
      break;
    case "addtag":
      addtagtopuzzle($puzz, $_POST['tagname']);
      break;
    case "removetag":
      removetagfrompuzzle($puzz, $_POST['tagname']);
      break;
    case "newtag":
      if (!empty(trim($_POST['newtagname']))) {
        addtagtopuzzle($puzz, trim($_POST['newtagname']));
      }
      break;
  }
  echo '</div></div>';
}

// Make sure puzzle id is supplied
if (!isset($_GET['pid'])) {
  exit_with_error_message('No Puzzle ID provided to script!');
}

// Check for authenticated user
$puzzid = $_GET['pid'];
$userobj = getauthenticatedsolver();  // Returns full solver object
$userid = $userobj->id;
$username = $userobj->name;

// Get puzzle data (includes lastact)
// Note: $huntinfo (with config, statuses, tags) is loaded by puzzlebosslib.php
$puzzleobj = readapi('/puzzles/' . $puzzid);
$puzname = $puzzleobj->puzzle->name;

// Calculate time since last activity (now included in puzzle response)
$lastActDisplay = 'N/A';
if (isset($puzzleobj->lastact->time)) {
  $lastActTime = strtotime($puzzleobj->lastact->time);
  $now = time();
  $diff = $now - $lastActTime;

  // Format time ago
  $timeAgo = 'just now';
  if ($diff >= 0) {
    $hours = floor($diff / 3600);
    $minutes = floor(($diff % 3600) / 60);
    $seconds = $diff % 60;
    $timeAgo = sprintf('%dh %dm %ds ago', $hours, $minutes, $seconds);
  }

  // Get activity type with friendly name
  $actType = $puzzleobj->lastact->type ?? 'unknown';
  $actTypeDisplay = [
    'revise' => '📝 Sheet edit',
    'comment' => '📋 Puzzle info change',
    'interact' => '🔄 Puzzleboss change',
    'solve' => '✅ Solve',
    'create' => '🆕 Created',
    'open' => '📂 Opened',
  ][$actType] ?? $actType;

  // Get solver name from solver_id (100 = system/API changes, skip "by" part)
  $solverName = null;
  if (isset($puzzleobj->lastact->solver_id) && $puzzleobj->lastact->solver_id != 100) {
    try {
      $solverInfo = readapi('/solvers/' . $puzzleobj->lastact->solver_id);
      $solverName = $solverInfo->solver->name ?? null;
    } catch (Exception $e) {
      $solverName = 'solver #' . $puzzleobj->lastact->solver_id;
    }
  }

  // Build display string (omit "by" part for system/API changes)
  if ($solverName) {
    $lastActDisplay = sprintf('%s by <b>%s</b> (%s)', $actTypeDisplay, htmlentities($solverName), $timeAgo);
  } else {
    $lastActDisplay = sprintf('%s (%s)', $actTypeDisplay, $timeAgo);
  }
}
?>

<div id="app">
<div class="status-header">
  <h1>Edit Puzzle: <?= htmlentities($puzname) ?></h1>
</div>

<?= render_navbar('editpuzzle') ?>

<!-- Box 1: User Info and Read-Only Puzzle Info -->
<div class="info-box">
  <div class="info-box-header" @click="showInfo = !showInfo">
    <span class="collapse-icon" :class="{ collapsed: !showInfo }">▼</span>
    <h3>Puzzle Information</h3>
  </div>
  <div class="info-box-content" v-show="showInfo">
    <p><strong>You are:</strong> <?= htmlentities($username) ?></p>
    <table class="info-table">
      <thead>
        <tr><th>Field</th><th>Value</th></tr>
      </thead>
      <tbody>
        <tr><td>Puzzle Name</td><td><?= htmlentities($puzname) ?></td></tr>
        <tr><td>Round</td><td><?= htmlentities($puzzleobj->puzzle->roundname) ?></td></tr>
        <tr><td>Status</td><td><?= htmlentities($puzzleobj->puzzle->status) ?></td></tr>
        <tr><td>Answer</td><td><?= htmlentities($puzzleobj->puzzle->answer ?? '') ?></td></tr>
        <tr><td>Location</td><td><?= htmlentities($puzzleobj->puzzle->xyzloc ?? '') ?></td></tr>
        <tr><td>Cur. Solvers</td><td><?= htmlentities($puzzleobj->puzzle->cursolvers ?? '') ?></td></tr>
        <tr><td>All Solvers</td><td><?= htmlentities($puzzleobj->puzzle->solvers ?? '') ?></td></tr>
        <tr><td>Comments</td><td><?= htmlentities($puzzleobj->puzzle->comments ?? '') ?></td></tr>
        <tr><td>Meta For Round</td><td><?= $puzzleobj->puzzle->ismeta ? "Yes" : "No" ?></td></tr>
        <tr><td>Sheet Count</td><td><?= $puzzleobj->puzzle->sheetcount ?? 'N/A' ?></td></tr>
        <tr><td>Last Activity</td><td><?= $lastActDisplay ?></td></tr>
        <tr><td>Tags</td><td><?= htmlentities($puzzleobj->puzzle->tags ?? 'none') ?></td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Box 2: Work Assignment and Puzzle Editing -->
<div class="info-box">
  <div class="info-box-header" @click="showEdit = !showEdit">
    <span class="collapse-icon" :class="{ collapsed: !showEdit }">▼</span>
    <h3>Edit Puzzle</h3>
  </div>
  <div class="info-box-content" v-show="showEdit">
    <!-- Solver Assignment -->
    <?php if ($userobj->puzz != $puzname): ?>
      <p>You are not marked as working on this puzzle. Would you like to be?</p>
      <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post">
        <input type="hidden" name="startwork" value="yes">
        <input type="hidden" name="pid" value="<?= $puzzid ?>">
        <input type="hidden" name="uid" value="<?= $userid ?>">
        <input type="submit" name="submit" value="Start Working On This Puzzle">
      </form>
    <?php else: ?>
      <p>You are marked as currently working on this puzzle. Would you like to stop?</p>
      <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post">
        <input type="hidden" name="stopwork" value="yes">
        <input type="hidden" name="pid" value="<?= $puzzid ?>">
        <input type="hidden" name="uid" value="<?= $userid ?>">
        <input type="submit" name="submit" value="Stop Working On This Puzzle">
      </form>
    <?php endif; ?>

    <br>

    <!-- Edit Table -->
    <table class="edit-table">
      <thead>
        <tr><th>Field</th><th>New Value</th><th>Action</th></tr>
      </thead>
      <tbody>

      <!-- Change puzzle name -->
      <tr>
        <td>Puzzle Name</td>
        <td colspan="2">
          <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" class="inline-form">
            <input type="hidden" name="partupdate" value="yes">
            <input type="hidden" name="pid" value="<?= $puzzid ?>">
            <input type="hidden" name="uid" value="<?= $userid ?>">
            <input type="hidden" name="part" value="name">
            <input type="text" required minlength="1" name="value" value="<?= htmlentities($puzname) ?>">
            <input type="submit" name="submit" value="Update">
          </form>
        </td>
      </tr>

      <!-- Change round -->
      <?php
      try {
        $roundsobj = readapi('/rounds');
        $allrounds = $roundsobj->rounds;
      } catch (Exception $e) {
        $allrounds = array();
      }
      ?>
      <tr>
        <td>Round</td>
        <td colspan="2">
          <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" class="inline-form">
            <input type="hidden" name="partupdate" value="yes">
            <input type="hidden" name="pid" value="<?= $puzzid ?>">
            <input type="hidden" name="uid" value="<?= $userid ?>">
            <input type="hidden" name="part" value="round_id">
            <select id="round_id" name="value" required>
              <option disabled selected value>-- select new round --</option>
              <?php foreach ($allrounds as $round): ?>
                <?php $selected = ($round->id == $puzzleobj->puzzle->round_id) ? ' selected' : ''; ?>
                <option value="<?= $round->id ?>"<?= $selected ?>><?= htmlentities($round->name) ?></option>
              <?php endforeach; ?>
            </select>
            <input type="submit" name="submit" value="Update">
          </form>
        </td>
      </tr>

      <!-- Enter answer -->
      <?php
      $answer = $puzzleobj->puzzle->answer;
      if (isset($_GET['answer'])) {
        $answer = $_GET['answer'];
      }
      ?>
      <tr>
        <td>Answer</td>
        <td colspan="2">
          <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" class="inline-form">
            <input type="hidden" name="partupdate" value="yes">
            <input type="hidden" name="pid" value="<?= $puzzid ?>">
            <input type="hidden" name="uid" value="<?= $userid ?>">
            <input type="hidden" name="part" value="answer">
            <input type="text" required minlength="1" name="value" value="<?= htmlentities($answer ?? '') ?>">
            <input type="submit" name="submit" value="Update">
          </form>
        </td>
      </tr>

      <!-- Enter location -->
      <tr>
        <td>Location</td>
        <td colspan="2">
          <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" class="inline-form">
            <input type="hidden" name="partupdate" value="yes">
            <input type="hidden" name="pid" value="<?= $puzzid ?>">
            <input type="hidden" name="uid" value="<?= $userid ?>">
            <input type="hidden" name="part" value="xyzloc">
            <input type="text" name="value" value="<?= htmlentities($puzzleobj->puzzle->xyzloc ?? '') ?>">
            <input type="submit" name="submit" value="Update">
          </form>
        </td>
      </tr>

      <!-- Enter Comments -->
      <tr>
        <td>Comments</td>
        <td colspan="2">
          <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" class="inline-form">
            <input type="hidden" name="partupdate" value="yes">
            <input type="hidden" name="pid" value="<?= $puzzid ?>">
            <input type="hidden" name="uid" value="<?= $userid ?>">
            <input type="hidden" name="part" value="comments">
            <input type="text" name="value" value="<?= htmlentities($puzzleobj->puzzle->comments ?? '') ?>">
            <input type="submit" name="submit" value="Update">
          </form>
        </td>
      </tr>

      <!-- Change Status -->
      <?php
      $excluded_statuses = ['Solved'];
      global $huntinfo;
      $allstatuses = isset($huntinfo->statuses) ? $huntinfo->statuses : array();
      ?>
      <tr>
        <td>Status</td>
        <td colspan="2">
          <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" class="inline-form">
            <input type="hidden" name="partupdate" value="yes">
            <input type="hidden" name="pid" value="<?= $puzzid ?>">
            <input type="hidden" name="uid" value="<?= $userid ?>">
            <input type="hidden" name="part" value="status">
            <select id="value" name="value" required>
              <option disabled selected value>-- select --</option>
              <?php foreach ($allstatuses as $statusobj): ?>
                <?php if (!in_array($statusobj->name, $excluded_statuses)): ?>
                  <option value="<?= htmlentities($statusobj->name) ?>"><?= htmlentities($statusobj->name) ?></option>
                <?php endif; ?>
              <?php endforeach; ?>
            </select>
            <input type="submit" name="submit" value="Update">
          </form>
        </td>
      </tr>

      <!-- Meta Assignment -->
      <?php $ismeta = $puzzleobj->puzzle->ismeta; ?>
      <tr>
        <td>Meta For Round</td>
        <td colspan="2">
          <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" class="inline-form">
            <input type="hidden" name="partupdate" value="yes">
            <input type="hidden" name="pid" value="<?= $puzzid ?>">
            <input type="hidden" name="uid" value="<?= $userid ?>">
            <input type="hidden" name="part" value="ismeta">
            <select id="ismeta" name="value">
              <option value="0"<?= $ismeta ? '' : ' selected' ?>>No</option>
              <option value="1"<?= $ismeta ? ' selected' : '' ?>>Yes</option>
            </select>
            <input type="submit" name="submit" value="Update">
          </form>
        </td>
      </tr>

      </tbody>
    </table>
  </div>
</div>

<!-- Box 3: Tag Management -->
<div class="info-box">
  <div class="info-box-header" @click="showTags = !showTags">
    <span class="collapse-icon" :class="{ collapsed: !showTags }">▼</span>
    <h3>Tag Management</h3>
  </div>
  <div class="info-box-content" v-show="showTags">
    <?php
    // Use tags from huntinfo
    $alltags = isset($huntinfo->tags) ? $huntinfo->tags : array();

    // Get current puzzle tags as array
    $currentTagsStr = $puzzleobj->puzzle->tags ?? '';
    $currentTags = $currentTagsStr ? array_map('trim', explode(',', $currentTagsStr)) : array();
    ?>

    <table>
      <thead>
        <tr><th>Tag</th><th>Status</th><th>Action</th></tr>
      </thead>
      <tbody>
      <?php if (count($alltags) > 0): ?>
        <?php foreach ($alltags as $tag): ?>
          <?php
          $tagname = $tag->name;
          $isAssigned = in_array($tagname, $currentTags);
          ?>
          <tr>
            <td><?= htmlentities($tagname) ?></td>
            <td><?= $isAssigned ? '✅ Assigned' : '—' ?></td>
            <td>
              <?php if ($isAssigned): ?>
                <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" style="display:inline;">
                  <input type="hidden" name="removetag" value="yes">
                  <input type="hidden" name="pid" value="<?= $puzzid ?>">
                  <input type="hidden" name="uid" value="<?= $userid ?>">
                  <input type="hidden" name="tagname" value="<?= htmlentities($tagname) ?>">
                  <input type="submit" name="submit" value="Remove">
                </form>
              <?php else: ?>
                <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post" style="display:inline;">
                  <input type="hidden" name="addtag" value="yes">
                  <input type="hidden" name="pid" value="<?= $puzzid ?>">
                  <input type="hidden" name="uid" value="<?= $userid ?>">
                  <input type="hidden" name="tagname" value="<?= htmlentities($tagname) ?>">
                  <input type="submit" name="submit" value="Add">
                </form>
              <?php endif; ?>
            </td>
          </tr>
        <?php endforeach; ?>
      <?php else: ?>
        <tr><td colspan="3"><em>No tags defined in system yet.</em></td></tr>
      <?php endif; ?>
      </tbody>
    </table>

    <br>
    <p><strong>Create &amp; Add New Tag:</strong></p>
    <form action="editpuzzle.php?pid=<?= $puzzid ?>" method="post">
      <input type="hidden" name="newtag" value="yes">
      <input type="hidden" name="pid" value="<?= $puzzid ?>">
      <input type="hidden" name="uid" value="<?= $userid ?>">
      <input type="text" name="newtagname" placeholder="new-tag-name" pattern="[a-zA-Z0-9_-]+" title="Alphanumeric, hyphens, and underscores only">
      <input type="submit" name="submit" value="Create &amp; Add Tag">
    </form>
    <small><em>Tag names can only contain letters, numbers, hyphens, and underscores.</em></small>
  </div>
</div>

</div>

<script>
const { createApp } = Vue;

createApp({
  data() {
    return {
      showInfo: true,
      showEdit: true,
      showTags: true
    }
  }
}).mount('#app');
</script>

<footer style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ccc; text-align: center;">
  <a href="index.php">← Back to Puzzleboss Home</a>
</footer>
</body>
</html>
