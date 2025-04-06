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
  <style>
  body {
    background-color: aliceblue;
    display: grid;
    font-family: 'Lora';
    height: 100vh;
    justify-items: center;
    margin: 0;
    width: 100vw;
  }
  h1 {
    line-height: 1em;
  }
  h1 > span {
    font-size: 50%;
  }
  main {
    margin-top: 50px;
    max-width: 700px;
  }
  table.registration {
    text-align: right;
  }
  table.registration tr > td:last-child {
    text-align: left;
    font-size: 80%;
    font-style: italic;
  }
  table.registration tr:last-child {
    text-align: center;
  }
  input[type="submit"] {
    font-family: inherit;
  }
  .error {
    background-color: lightpink;
    padding: 10px;
  }
  .success {
    background-color: lightgreen;
    padding: 10px;
  }
  </style>
</head>
<body>
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

  if (isset($_POST['ismeta'])) {
    if ($_POST['ismeta'] == "yes") {
      $whatdo = "ismeta";
    } else {
      $whatdo = "isnotmeta";
    }
  }


  if (isset($_POST['partupdate'])) {
    $whatdo = "partupdate";
    if (!isset($_POST['part']) || !isset($_POST['value'])) {
      exit_with_error_message(
        'Part name to update, or value to set it to not specified',
      );
    }
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
    case "ismeta":
      updateroundpart($_POST['rid'], "meta_id", $puzz);
      break;
    case "isnotmeta":
      updateroundpart($_POST['rid'], "meta_id", "NULL");
      break;
    case "partupdate":
      updatepuzzlepart($puzz, $_POST['part'], $_POST['value']);
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
$userid = getauthenticateduser();

$userobj = readapi('/solvers/' . $userid);
$puzzleobj = readapi('/puzzles/' . $puzzid);
$puzname = $puzzleobj->puzzle->name;
$username = $userobj->solver->name;

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
echo '</td></tr></table>';

//Solver Assignment
if ($userobj->solver->puzz != $puzname) {
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

// Change Status
echo '<tr>';
echo '<td>Status</td><td><form action="editpuzzle.php?pid=' . $puzzid . '" method="post">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="status">';
echo '<select id="value" name="value"/>';
echo '<option disabled selected value>-- select --</option>';
echo '<option value="New">New</option>';
echo '<option value="Being worked">Being worked</option>';
echo '<option value="Needs eyes">Needs eyes</option>';
echo '<option value="Critical">Critical</option>';
echo '<option value="WTF">WTF</option>';
echo '<option value="Unnecessary">Unnecessary</option>';
echo '<option value="[hidden]">[hidden]</option>';
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



?>
</main>
<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
