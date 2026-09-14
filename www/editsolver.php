<html>
<head><title>Change Solver</title></head><body>
<?php

require('puzzlebosslib.php');

if (isset($_POST['submit'])) {
  pb_verify_csrf();
  if (!isset($_POST['id'])) {
    echo 'ERROR: No Authenticated User ID Found in Request';
    echo '</body></html>';
    exit (2);
  }
  if ($_POST['id'] == "") {
    echo 'ERROR: No Authenticated User ID Found in Request';
    echo '</body></html>';
    exit (2);
  }

  $id = $_POST['id'];
  $puzz = $_POST['puzz'];
  if ($puzz == '_none_') $puzz = '';

  echo 'Attempting to set puzz for solver.<br>';
  echo 'solver_id: ' . htmlspecialchars($id) . '<br>';
  echo 'puzz: ' . htmlspecialchars($puzz) . '<br>';

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
  echo '<br>';
  echo 'OK.  Solver reassigned.';
} else {
  $solvers = readapi('/solvers')->solvers;
  $solver = getauthenticatedsolver();
  $id = $solver->id;
  $username = $solver->name;

  if ($id==0) {
    echo '<br>No solver found. Check Solvers Database<br>';
    echo '</body></html>';
    exit (2);

  }

  echo "changing solver settings for username: " . htmlspecialchars($username) . " user-id: " . htmlspecialchars($id) . "<br>";
  echo "What puzzle is this user working on?<br>";

  $rounds = readapi('/rounds')->rounds;
  echo '<form action="editsolver.php" method="post">';
  echo pb_csrf_field();
  echo '<table border=4 style="vertical-align:top" ><tr>';
  foreach ($rounds as $round) {
    echo '<th>' . htmlspecialchars($round->name) . "</th>";
  }
  echo '</tr><tr style="vertical-align:top" >';
  foreach ($rounds as $round) {
    echo '<td>';
    $puzzlesresp = readapi("/rounds/" . $round->id . "/puzzles");
    $puzzlearray = $puzzlesresp->round->puzzles;

    echo '<table>';
    foreach ($puzzlearray as $puzzle) {
      $puzzleid = $puzzle->id;
      if ($puzzleid !="") {
        $puzzlename = $puzzle->name;
        echo '<tr><td><input type="radio" id="' . $puzzleid . '" name="puzz" value="' . $puzzleid . '"></td>';
        echo '<td>' . htmlspecialchars($puzzlename) . '</td></tr>';
      }
    }
    echo '</table>';
    echo '</td>';

  }
  echo '</tr></table>';
  echo '<br><input type="radio" id="_none_" name="puzz" value="_none_">';
  echo '<label for="_none_">Not working on any puzzle</label><br>';
  echo '<input type = "hidden" name="id" value="' . htmlspecialchars($id) . '">';
  echo '<input type = "submit" name="submit" />';
  echo '</form>';



}


?>
</body>
</html>
