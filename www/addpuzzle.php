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
  input[type="submit"]:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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
  <script>
  let formSubmitted = false;
  function handleSubmit(event) {
    if (formSubmitted) {
      event.preventDefault();
      return false;
    }
    formSubmitted = true;
    const submitButton = event.target.querySelector('input[type="submit"]');
    // Disable button after a brief delay to ensure form submission starts
    setTimeout(function() {
      submitButton.disabled = true;
      submitButton.value = 'Submitting...';
    }, 100);
    return true;
  }
  </script>
</head>
<body>
<main>
<?php

require('puzzlebosslib.php');

$round_id = null;
if (isset($_POST['submit'])) {
  $name = $_POST['name'];
  if (sanitize_string($name) == '') {
    exit_with_error_message(
      'This will not work: this puzzle name will be erased in Puzzboss, '.
      'breaking everything. Please manually add some text to this puzzle name.',
    );
  }
  $round_id = $_POST['round_id'];
  $puzzle_uri = $_POST['puzzle_uri'];

  if (isset($_POST['create_new_round'])) {
    $create_new_round = $_POST['create_new_round'];
    if ($create_new_round != $round_id) {
      exit_with_error_message(
        'You confirmed you want to create a new round but also specified '.
        'a <em>different</em> round, which is confusing and probably bad.',
      );
    }

    // Okay, creating a new round
    print <<<HTML
Attempting to add round.<br>
<table class="registration">
<tr><td>name:</td><td>$create_new_round</td></tr>
</table>
HTML;

    try {
      $resp = postapi("/rounds", array('name' => $create_new_round));
    } catch (Exception $e) {
      exit_with_api_error($e);
      throw $e;
    }
    assert_api_success($resp);
    $round_id = null;
    $round_name = $resp->round->name;
    foreach (readapi("/rounds")->rounds as $round) {
      if ($round->name == $round_name) {
        $round_id = (string)$round->id;
        break;
      }
    }
    echo '<div class="success">Round <tt>'.$round_name.'</tt> created!';
    echo '<pre>'.var_export($resp, true).'</pre></div>';
    echo '<a href="javascript:window.history.back();">Go back</a>';
    echo '<br><hr>';

    if (!$round_id) {
      exit_with_error_message(
        'Created a new round, but could not find it in time for puzzle creation. '.
        'Go back, refresh the add puzzle page, and it should be there by then.',
      );
    }
  }

  if (!is_numeric($round_id)) {
    exit_with_error_message(
      'You did not select a round to create this puzzle in, or chose '.
      'a new round name but did not confirm that you wanted to do that!',
    );
  }

  print <<<HTML
  Attempting to add puzzle.<br>
  <table class="registration">
    <tr><td>name:</td><td>$name</td></tr>
    <tr><td>round_id:</td><td>$round_id</td></tr>
    <tr><td>puzzle_uri:</td><td><a href="$puzzle_uri">$puzzle_uri</a></td></tr>
  </table>
HTML;

  $defer_to = null;
  if (isset($_POST['defer'])) {
    $defer_to = $_POST['defer_to'];
  }
  $apiurl = "/puzzles";
  $data = array(
    'puzzle' => array(
      'name' => $name,
      'round_id' => $round_id,
      'puzzle_uri' => $puzzle_uri,
      // 'defer_to' => $defer_to,
    )
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

// Extract puzzle name from URL parameters
// Priority: puzzid parameter > URL extraction
$puzzurl = isset($_GET['puzzurl']) ? $_GET['puzzurl'] : '';
$puzzname = isset($_GET['puzzid']) ? sanitize_string($_GET['puzzid']) : '';

// If no puzzid provided, extract name from puzzurl
if ($puzzname == '') {
  // Split URL by / and take the last segment (e.g., "save-the-queen" from URL path)
  $puzzurl_parts = explode('/', $puzzurl);
  // Convert kebab-case to PascalCase: "save-the-queen" -> "SaveTheQueen"
  $puzzname = str_replace('-', '', ucwords(end($puzzurl_parts), '-'));
  $puzzname = sanitize_string($puzzname);

  // Special case: if URL contains "-head/" and puzzid is provided, prepend it
  // (e.g., for meta puzzles in hunt structures)
  if (str_contains($puzzurl, '-head/') && isset($_GET['puzzid'])) {
    $puzzname = sanitize_string($_GET['puzzid']).$puzzname;
  }
}
$round_name = isset($_GET['roundname']) ? $_GET['roundname'] : '';

$rounds = readapi("/rounds")->rounds;
$rounds = array_reverse($rounds); // Newer rounds first in the dropdown
?>

<h1>Add a puzzle!</h1>
<form action="addpuzzle.php" method="post" onsubmit="return handleSubmit(event)">
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
$selected_any = false;
foreach ($rounds as $round) {
  $selected = ($round->name === $round_name || $round->id === $round_id) ? 'selected' : '';
  if ($selected) {
    $selected_any = true;
  }
  echo "<option value=\"{$round->id}\" $selected>{$round->name}</option>\n";
}
$offer_create_new_round = !$selected_any && $round_name && $round_name !== 'undefined';
if ($offer_create_new_round) {
  echo "<option value=\"$round_name\" selected>[NEW ROUND] $round_name</option>";
}
?>
        </select>
<?php
if ($offer_create_new_round) {
  echo '&nbsp;';
  echo '<label for="create_new_round">Click to confirm you want to create a new round:</label>';
  echo '<input type="checkbox" id="create_new_round" name="create_new_round" value="'.$round_name.'" />';
}
?>
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
<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
