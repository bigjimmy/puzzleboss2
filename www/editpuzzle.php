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
  <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&amp;family=Open+Sans:wght@400;700&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="form-page">
<main>
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
  echo '<br><hr>';
}

// Make sure puzzle id is supplied
if (!isset($_GET['pid'])) {
  exit_with_error_message('No Puzzle ID provided to script!');
}

echo '<h1>Per-Puzzle Change Interface</h1>';

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

echo 'You Are: ' . $username;
echo '<br><br><table border=2>';
echo '<tr><td><b>Puzzle Name</b></td><td>' . $puzname . '</td></tr>';
echo '<tr><td><b>Round</b></td><td>' . $puzzleobj->puzzle->roundname . '</td></tr>';
echo '<tr><td><b>Status</b></td><td>' . $puzzleobj->puzzle->status . '</td></tr>';
echo '<tr><td><b>Answer</b></td><td>' . $puzzleobj->puzzle->answer . '</td></tr>';
echo '<tr><td><b>Location</b></td><td>' . htmlentities($puzzleobj->puzzle->xyzloc ?? '') . '</td></tr>';
echo '<tr><td><b>Cur. Solvers</b></td><td>' . $puzzleobj->puzzle->cursolvers . '</td></tr>';
echo '<tr><td><b>All Solvers</b></td><td>' . $puzzleobj->puzzle->solvers . '</td></tr>';
echo '<tr><td><b>Comments</b></td><td>' . htmlentities($puzzleobj->puzzle->comments ?? '') . '</td></tr>';
echo '<tr><td><b>Meta For Round</b></td><td>';
echo $puzzleobj->puzzle->ismeta ? "Yes" : "No";
echo '</td></tr>';
echo '<tr><td><b>Sheet Count</b></td><td>' . ($puzzleobj->puzzle->sheetcount ?? 'N/A') . '</td></tr>';
echo '<tr><td><b>Last Activity</b></td><td>' . $lastActDisplay . '</td></tr>';
echo '<tr><td><b>Tags</b></td><td>' . htmlentities($puzzleobj->puzzle->tags ?? 'none') . '</td></tr>';
echo '</table>';

//Solver Assignment
if ($userobj->puzz != $puzname) {
  echo '<br>You are not marked as working on this puzzle.  Would you like to be?';
  echo '<form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
  echo '<input type="hidden" name="startwork" value="yes">';
  echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
  echo '<input type="hidden" name="uid" value="' . $userid . '">';
  echo '<input type="submit" name="submit" value="yes">';
  echo '</form>';
} else {
  echo '<br>You are marked as currently working on this puzzle.  Would you like to not be?';
  echo '<form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
  echo '<input type="hidden" name="stopwork" value="yes">';
  echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
  echo '<input type="hidden" name="uid" value="' . $userid . '">';
  echo '<input type="submit" name="submit" value="yes">';
  echo '</form>';
}


echo '<br><table border=2><tr><th>Part</th><th>New Value</th><th></th></tr>';

// Change puzzle name
echo '<tr>';
echo '<td>Puzzle Name</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="name">';
echo '<input type="text" required minlength="1" name="value" value="' . htmlentities($puzname) . '" size="50"></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

// Change round
try {
  $roundsobj = readapi('/rounds');
  $allrounds = $roundsobj->rounds;
} catch (Exception $e) {
  $allrounds = array();
}

echo '<tr>';
echo '<td>Round</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="round_id">';
echo '<select id="round_id" name="value" required>';
echo '<option disabled selected value>-- select new round --</option>';

foreach ($allrounds as $round) {
  $selected = ($round->id == $puzzleobj->puzzle->round_id) ? ' selected' : '';
  echo '<option value="' . $round->id . '"' . $selected . '>' . htmlentities($round->name) . '</option>';
}

echo '</select></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

// Enter answer
$answer = $puzzleobj->puzzle->answer;
if (isset($_GET['answer'])) {
  $answer = $_GET['answer'];
}
echo '<tr>';
echo '<td>Answer</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="answer">';
echo '<input type="text" required minlength="1" name="value" value="' . $answer . '"></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';


// Enter location
echo '<tr>';
echo '<td>Location</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="xyzloc">';
echo '<input type="text" required minlength="1" name="value" value="' . $puzzleobj->puzzle->xyzloc . '"></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

// Enter Comments
echo '<tr>';
echo '<td>Comments</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="comments">';
echo '<input type="text" required minlength="1" name="value" value="' . $puzzleobj->puzzle->comments . '"></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

// Change Status - use statuses from huntinfo (loaded by puzzlebosslib.php)
// Statuses excluded from manual selection (must be set via other means)
$excluded_statuses = ['Solved'];
global $huntinfo;
$allstatuses = isset($huntinfo->statuses) ? $huntinfo->statuses : array();

echo '<tr>';
echo '<td>Status</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="status">';
echo '<select id="value" name="value"/>';
echo '<option disabled selected value>-- select --</option>';
foreach ($allstatuses as $statusobj) {
  $statusval = $statusobj->name;
  if (!in_array($statusval, $excluded_statuses)) {
    echo '<option value="' . htmlentities($statusval) . '">' . htmlentities($statusval) . '</option>';
  }
}
echo '</option>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

// Meta Assignment
echo '<tr><td>Meta For Round</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="ismeta">';
echo '<select id="ismeta" name="value"/>';
$ismeta = $puzzleobj->puzzle->ismeta;
echo '<option value="0" ' . ($ismeta ? '' : 'selected') . '>No</option>';
echo '<option value="1" ' . ($ismeta ? 'selected' : '') . '>Yes</option>';
echo '</select>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

echo '</table>';

// --- Tag Management Section ---
echo '<br><h3>Tag Management</h3>';

// Use tags from huntinfo
$alltags = isset($huntinfo->tags) ? $huntinfo->tags : array();

// Get current puzzle tags as array
$currentTagsStr = $puzzleobj->puzzle->tags ?? '';
$currentTags = $currentTagsStr ? array_map('trim', explode(',', $currentTagsStr)) : array();

echo '<table border="1" cellpadding="8"><tr><th>Tag</th><th>Status</th><th>Action</th></tr>';

if (count($alltags) > 0) {
  foreach ($alltags as $tag) {
    $tagname = $tag->name;
    $isAssigned = in_array($tagname, $currentTags);
    
    echo '<tr>';
    echo '<td>' . htmlentities($tagname) . '</td>';
    echo '<td>' . ($isAssigned ? '✅ Assigned' : '—') . '</td>';
    echo '<td>';
    
    if ($isAssigned) {
      // Show remove button
      echo '<form action="editpuzzle.php?pid=' . $puzzid . '" method="post" style="display:inline;">';
      echo '<input type="hidden" name="removetag" value="yes">';
      echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
      echo '<input type="hidden" name="uid" value="' . $userid . '">';
      echo '<input type="hidden" name="tagname" value="' . htmlentities($tagname) . '">';
      echo '<input type="submit" name="submit" value="Remove">';
      echo '</form>';
    } else {
      // Show add button
      echo '<form action="editpuzzle.php?pid=' . $puzzid . '" method="post" style="display:inline;">';
      echo '<input type="hidden" name="addtag" value="yes">';
      echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
      echo '<input type="hidden" name="uid" value="' . $userid . '">';
      echo '<input type="hidden" name="tagname" value="' . htmlentities($tagname) . '">';
      echo '<input type="submit" name="submit" value="Add">';
      echo '</form>';
    }
    
    echo '</td>';
    echo '</tr>';
  }
} else {
  echo '<tr><td colspan="3"><em>No tags defined in system yet.</em></td></tr>';
}

echo '</table>';

// Add new tag form
echo '<br><b>Create &amp; Add New Tag:</b><br>';
echo '<form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="newtag" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="text" name="newtagname" placeholder="new-tag-name" pattern="[a-zA-Z0-9_-]+" title="Alphanumeric, hyphens, and underscores only">';
echo ' <input type="submit" name="submit" value="Create &amp; Add Tag">';
echo '</form>';
echo '<small><em>Tag names can only contain letters, numbers, hyphens, and underscores.</em></small>';

?>
</main>
<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
