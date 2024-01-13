<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Add Puzzle</title>
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

$round_id = null;
if (isset($_POST['submit'])) {
  $name = $_POST['name'];
  $round_id = $_POST['round_id'];
  $puzzle_uri = $_POST['puzzle_uri'];

  print <<<HTML
  Attempting to add puzzle.<br>
  <table class="registration">
    <tr><td>name:</td><td>$name</td></tr>
    <tr><td>round_id:</td><td>$round_id</td></tr>
    <tr><td>puzzle_uri:</td><td><a href="$puzzle_uri">$puzzle_uri</a></td></tr>
  </table>
HTML;


  $apiurl = "/puzzles";
  $data = array(
    'name' => $name,
    'round_id' => $round_id,
    'puzzle_uri' => $puzzle_uri,
  );

  echo "Submitting API request to add puzzle. May take a few seconds.<br>";
  try {
    $responseobj = postapi($apiurl, $data);
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);

  echo '<br><div class="success">';
  echo 'OK.  Puzzle created with ID of ';
  $pid = $responseobj->puzzle->id;
  echo '<a href="editpuzzle.php?pid='.$pid.'">'.$pid.'</a>';
  echo '</div><br><hr>';
}

$puzzurl = isset($_GET['puzzurl']) ? $_GET['puzzurl'] : '';
$puzzname = isset($_GET['puzzid']) ? $_GET['puzzid'] : '';
$round_name = isset($_GET['roundname']) ? $_GET['roundname'] : '';

$rounds = readapi("/rounds")->rounds;
$rounds = array_reverse($rounds); // Newer rounds first in the dropdown
?>

<h1>Add a puzzle!</h1>
<form action="addpuzzle.php" method="post">
  <table>
    <tr>
      <td><label for="name">Name:</label></td>
      <td>
        <input
          type="text"
          id="name"
          name="name"
          required
          value="<?= $puzzname ?>"
          size="40"
        />
      </td>
    </tr>
    <tr>
      <td><label for="round_id">Round:</label></td>
      <td>
        <select id="round_id" name="round_id"/>
<?php
foreach ($rounds as $round) {
  $selected = ($round->name === $round_name || $round->id === $round_id) ? 'selected' : '';
  echo "<option value=\"{$round->id}\" $selected>{$round->name}</option>\n";
}
?>
        </select>
      </td>
    </tr>
    <tr>
      <td><label for="puzzle_uri">Puzzle URI:</label></td>
      <td>
        <input
          type="text"
          id="puzzle_uri"
          name="puzzle_uri"
          required
          value="<?= $puzzurl ?>"
          size="80"
        />
      </td>
    </tr>
  </table>
  <input type="submit" name="submit" value="Add New Puzzle"/>
</form>
</main>
<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
