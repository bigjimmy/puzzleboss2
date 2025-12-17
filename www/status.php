<html><head>
<title>Hunt Status</title>
<style>
  body {
    background-color: aliceblue;
  }
</style>
</head>
<body><h1>Hunt Status Overview</h1>
<?php 
require('puzzlebosslib.php');

$totrounds = 0;
$solvedrounds = 0;
$unsolvedrounds = 0;
$totpuzz = 0;
$solvedpuzz = 0;
$unsolvedpuzz = 0;

// Dynamic status tracking - counts and puzzle arrays keyed by status name
$status_counts = [];
$status_puzzles = [];

// Statuses EXCLUDED from the count table
$excluded_from_count_table = ['[hidden]', 'Solved'];

// Statuses EXCLUDED from the "work on" list
$excluded_from_workon = ['[hidden]', 'Unnecessary', 'Solved'];

$nolocarray = [];
$rounds;


$huntstruct = readapi("/all");
$rounds = $huntstruct->rounds;

// Fetch available statuses dynamically, excluding ones that shouldn't be manually selectable
$excluded_statuses_for_dropdown = ['Solved', '[hidden]'];
$allstatuses = array();
try {
  $statusobj = readapi('/statuses');
  $allstatuses = isset($statusobj->statuses) ? $statusobj->statuses : array();
} catch (Exception $e) {
  // Fallback - continue without dynamic statuses
}

// Create a cache of puzzle meta statuses
$puzzle_meta_cache = [];
foreach ($rounds as $round) {
  foreach ($round->puzzles as $puzzle) {
    $puzzle_meta_cache[$puzzle->id] = $puzzle->ismeta;
  }
}

// Check for authenticated user
$uid = getauthenticateduser();

function getroundnamefrompuzzid($puzzid) {
  global $rounds;
  foreach ($rounds as $round) {
    foreach ($round->puzzles as $puzzle) {
      if ($puzzle->id == $puzzid) {
        return $round->name;
      }
    }
  }
  return "NONEERROR";
}

function ispuzzlemeta($puzzleid) {
  global $puzzle_meta_cache;
  return isset($puzzle_meta_cache[$puzzleid]) ? $puzzle_meta_cache[$puzzleid] : false;
}

foreach ($rounds as $round) {
  $totrounds += 1;
  $puzzlearray = $round->puzzles;
  $round_metas = 0;
  $round_metas_solved = 0;

  // Count puzzles
  foreach ($puzzlearray as $puzzle) {
    if ($puzzle->status == '[hidden]') {
      continue;
    }
    $totpuzz += 1;
    
    $pstatus = $puzzle->status;
    
    // Track counts and puzzles by status dynamically
    if (!isset($status_counts[$pstatus])) {
      $status_counts[$pstatus] = 0;
      $status_puzzles[$pstatus] = [];
    }
    $status_counts[$pstatus] += 1;
    $status_puzzles[$pstatus][] = $puzzle;
    
    // Special handling for Solved (track separately for round completion)
    if ($pstatus == 'Solved') {
      $solvedpuzz += 1;
      if ($puzzle->ismeta) {
        $round_metas_solved += 1;
      }
    }
    if ($puzzle->ismeta) {
      $round_metas += 1;
    }
  }
  
  // Round is solved only if it has metas and all are solved
  if ($round_metas > 0 && $round_metas == $round_metas_solved) {
    $solvedrounds += 1;
  }
}

$unsolvedpuzz = $totpuzz - $solvedpuzz;
$unsolvedrounds = $totrounds - $solvedrounds;

echo '<table border=3>';
echo '<tr><td></td><th scope="col">Opened</th><th scope="col">Solved</th><th scope="col">Unsolved</th></tr>';
echo '<tr><th scope="row">Rounds</th><td>' . $totrounds . '</td><td>' . $solvedrounds . '</td><td>' . $unsolvedrounds . '</td></tr>';
echo '<tr><th scope="row">Puzzles</th><td>' . $totpuzz . '</td><td>' . $solvedpuzz . '</td><td>' . $unsolvedpuzz . '</td></tr>';
echo '</table><br><br>';

echo '<table border=3>';
echo '<tr><th>Status</th><th>Open Puzzle Count</th></tr>';
// Display counts for all statuses except excluded ones
foreach ($allstatuses as $st) {
  if (!in_array($st, $excluded_from_count_table)) {
    $cnt = isset($status_counts[$st]) ? $status_counts[$st] : 0;
    echo '<tr><td>' . htmlentities($st) . '</td><td>' . $cnt . '</td></tr>';
  }
}
echo '</table><br><br>';

echo 'Unsolved Puzzles Missing Location<br>';
echo '<table border=3>';
echo '<tr><th>Status</th><th>Meta</th><th>Name</th><th>Doc</th><th>Chat</th><th>Solvers (current)</th><th>Solvers (all time)</th><th>Comment</th></tr>';
foreach ($rounds as $round) {
  $puzzlearray = $round->puzzles;
  foreach ($puzzlearray as $thispuzzle) {
    if ($thispuzzle->status == '[hidden]') {
      continue;
    }
  	if (is_null($thispuzzle->xyzloc)) {
  	  if ($thispuzzle->status != "Solved") {
  	    array_push($nolocarray, $thispuzzle);
  	  }
    }
  }
}

foreach ($nolocarray as $puzzle) {
  $puzzleid = $puzzle->id;
  $puzzlename = $puzzle->name;
  $styleinsert = "";
  if ($puzzleid == $metapuzzle && $puzzle->status != "Critical") {
    $styleinsert .= " bgcolor='Gainsboro' ";
  }
  if ($puzzle->status == "New" && $puzzleid != $metapuzzle) {
    $styleinsert .= " bgcolor='aquamarine' ";
  }
  if ($puzzle->status == "Critical") {
    $styleinsert .= " bgcolor='HotPink' ";
  }
  // Not sure what to do here for style for solved/unnecc puzzles
  //if ($puzzle->status == "Solved" || $val->puzzle->status == "Unnecessary") {
  //  $styleinsert .= ' style="text-decoration:line-through" ';
    //}
    echo '<tr ' . $styleinsert . '>';
    echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '" target="_blank">';
    switch ($puzzle->status) {
      case "New":
        echo "New";
        break;
      case "Being worked":
        echo "Work";
        break;
      case "Needs eyes":
        echo "Eyes";
        break;
      case "WTF":
        echo "WTF";
        break;
      case "Critical":
        echo "Crit";
        break;
      case "Solved":
        echo "*";
        break;
      case "Unnecessary":
        echo "Unnecessary";
        break;
      default:
        // Unknown status - show as-is
        echo htmlentities($puzzle->status);
        break;
    }
    echo '</a></td>';
    echo '<td>' . ispuzzlemeta($puzzle->id) . '</td>';
    echo '<td><a href="' . $puzzle->puzzle_uri . '">'. $puzzlename . '</a></td>';
    echo '<td><a href="' . $puzzle->drive_uri . '">Doc</a></td>';
    echo '<td><a href="' . $puzzle->chat_channel_link  . '">Chat</a></td>';
    echo '<td>' . $puzzle->cursolvers . '</td>';
    echo '<td>' . $puzzle->solvers . '</td>';
    echo '<form action="editpuzzle.php?pid=' . $puzzle->id .'" method="post">';
    echo '<td><input type="text" name="value" required minlength="1" value="' . $puzzle->comments . '"></td>';
    echo '<input type="hidden" name="partupdate" value="yes">';
    echo '<input type="hidden" name="pid" value="' . $puzzle->id . '">';
    echo '<input type="hidden" name="uid" value="' . $uid . '">';
    echo '<input type="hidden" name="part" value="comments">';
    echo '<td><input type="submit" name="submit" value="submit"></td>';
    echo '</form>';
    echo '</tr>';

}
echo '</table><br><br>';

echo 'Total Hunt Overview:<br>';

// Build workonarray from all statuses except excluded ones
$workonarray = [];
foreach ($allstatuses as $st) {
  if (!in_array($st, $excluded_from_workon) && isset($status_puzzles[$st])) {
    $workonarray = array_merge($workonarray, $status_puzzles[$st]);
  }
}
echo '<table border = 3>';
echo '<tr><th>Status</th><th>Round</th><th>Meta</th><th>Name</th><th>Doc</th><th>Chat</th><th>Solvers(current)</th><th>Solvers(all time)</th><th>Location</th><th>Comment</th></tr>';
foreach ($workonarray as $puzzle) {
  $puzzleid = $puzzle->id;
  $puzzlename = $puzzle->name;
  $styleinsert = "";
  if ($puzzleid == $metapuzzle && $puzzle->status != "Critical") {
    $styleinsert .= " bgcolor='Gainsboro' ";
  }
  if ($puzzle->status == "New" && $puzzleid != $metapuzzle) {
    $styleinsert .= " bgcolor='aquamarine' ";
  }
  if ($puzzle->status == "Critical") {
    $styleinsert .= " bgcolor='HotPink' ";
  }
  // Not sure what to do here for style for solved/unnecc puzzles
  //if ($puzzle->status == "Solved" || $val->puzzle->status == "Unnecessary") {
  //  $styleinsert .= ' style="text-decoration:line-through" ';
    //}
    echo '<tr ' . $styleinsert . '>';
    echo '<td>';
    echo '<form action="editpuzzle.php?pid=' . $puzzle->id .'" method="post">';
    echo '<input type="hidden" name="partupdate" value="yes">';
    echo '<input type="hidden" name="pid" value="' . $puzzle->id . '">';
    echo '<input type="hidden" name="uid" value="' . $uid . '">';
    echo '<input type="hidden" name="part" value="status">';
    echo '<select id="value" name="value"/>';
    // Dynamic status dropdown - excludes Solved and [hidden]
    foreach ($allstatuses as $statusval) {
      if (!in_array($statusval, $excluded_statuses_for_dropdown)) {
        $selected = ($puzzle->status == $statusval) ? ' selected' : '';
        echo '<option value="' . htmlentities($statusval) . '"' . $selected . '>' . htmlentities($statusval) . '</option>';
      }
    }
    echo '<input type="submit" name="submit" value="submit"></td>';
    echo '</form>';
    echo '<td>' . getroundnamefrompuzzid($puzzle->id) . '</td>';
    echo '<td>' . ispuzzlemeta($puzzle->id) . '</td>';
    echo '<td><a href="' . $puzzle->puzzle_uri . '">'. $puzzlename . '</a></td>';
    echo '<td><a href="' . $puzzle->drive_uri . '">Doc</a></td>';
    echo '<td><a href="' . $puzzle->chat_channel_link  . '">Chat</a></td>';
    echo '<td>' . $puzzle->cursolvers . '</td>';
    echo '<td>' . $puzzle->solvers . '</td>';
    echo '<td>' . $puzzle->xyzloc . '</td>';
    echo '<form action="editpuzzle.php?pid=' . $puzzle->id .'" method="post">';
    echo '<td><input type="text" name="value" required minlength="1" value="' . $puzzle->comments . '"></td>';
    echo '<input type="hidden" name="partupdate" value="yes">';
    echo '<input type="hidden" name="pid" value="' . $puzzle->id . '">';
    echo '<input type="hidden" name="uid" value="' . $uid . '">';
    echo '<input type="hidden" name="part" value="comments">';
    echo '<td><input type="submit" name="submit" value="submit"></td>';
    echo '</tr>';
    echo '</form>';
}
echo '</table></td></tr></table>';


?>
<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
