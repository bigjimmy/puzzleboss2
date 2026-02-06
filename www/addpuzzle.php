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

  function togglePuzzleMode() {
    const mode = document.querySelector('input[name="puzzle_mode"]:checked').value;
    const promotePuzzleFields = document.getElementById('promote-puzzle-fields');
    const speculativeCheckbox = document.getElementById('speculative-checkbox-row');

    if (mode === 'new') {
      promotePuzzleFields.style.display = 'none';
      if (speculativeCheckbox) speculativeCheckbox.style.display = '';
    } else {
      promotePuzzleFields.style.display = '';
      if (speculativeCheckbox) speculativeCheckbox.style.display = 'none';
    }
  }
  </script>
</head>
<body>
<main>
<?php

require('puzzlebosslib.php');

$round_id = null;
if (isset($_POST['submit'])) {
  // Check if this is a promotion workflow
  $puzzle_mode = isset($_POST['puzzle_mode']) ? $_POST['puzzle_mode'] : 'new';

  if ($puzzle_mode === 'promote') {
    // Handle promotion of existing speculative puzzle
    $promote_puzzle_id = isset($_POST['promote_puzzle_id']) ? $_POST['promote_puzzle_id'] : '';

    if (!is_numeric($promote_puzzle_id) || $promote_puzzle_id == '') {
      exit_with_error_message('You must select a speculative puzzle to promote.');
    }

    // Get the form data for the update
    $name = isset($_POST['name']) ? $_POST['name'] : '';
    $round_id = isset($_POST['round_id']) ? $_POST['round_id'] : null;
    $puzzle_uri = isset($_POST['puzzle_uri']) ? $_POST['puzzle_uri'] : '';

    echo '<h2>Promoting Speculative Puzzle</h2>';
    echo "<p>Validating puzzle ID $promote_puzzle_id...</p>";

    // Step 1: Validate everything before making any changes
    try {
      // Validate puzzle exists and is actually Speculative
      $puzzle_resp = readapi("/puzzles/{$promote_puzzle_id}");
      if (!isset($puzzle_resp->puzzle)) {
        throw new Exception("Puzzle ID $promote_puzzle_id not found");
      }
      if ($puzzle_resp->puzzle->status !== 'Speculative') {
        throw new Exception("Puzzle is not in Speculative status (current: {$puzzle_resp->puzzle->status})");
      }
      echo '<div class="success">✓ Puzzle found and is Speculative</div>';

      // Validate puzzle URI is provided
      if (empty($puzzle_uri)) {
        throw new Exception('You must provide a puzzle URI when promoting a speculative puzzle');
      }
      echo '<div class="success">✓ Puzzle URI provided</div>';

      // Validate name if provided (check for duplicates)
      if (!empty($name) && sanitize_string($name) != '') {
        $sanitized_name = sanitize_string($name);
        $all_puzzles = readapi("/puzzles");
        foreach ($all_puzzles->puzzles as $p) {
          if ($p->name === $sanitized_name && $p->id != $promote_puzzle_id) {
            throw new Exception("Duplicate puzzle name detected: $sanitized_name");
          }
        }
        echo '<div class="success">✓ Puzzle name is valid and unique</div>';
      }

      // Validate round exists if specified
      if (is_numeric($round_id)) {
        $round_resp = readapi("/rounds/{$round_id}");
        if (!isset($round_resp->round)) {
          throw new Exception("Round ID $round_id not found");
        }
        echo '<div class="success">✓ Round ID validated</div>';
      }

    } catch (Exception $e) {
      exit_with_error_message('Validation failed: '.$e->getMessage());
    }

    // Step 2: Make changes (validation passed, now update)
    echo '<p>All validations passed. Applying changes...</p>';
    $promotion_failed = false;
    $rollback_needed = false;

    // Update status to New
    try {
      $status_data = array('status' => 'New');
      $status_resp = postapi("/puzzles/{$promote_puzzle_id}/status", $status_data);
      assert_api_success($status_resp);
      echo '<div class="success">✓ Status changed to "New"</div>';
      $rollback_needed = true; // We've made changes, rollback possible if later steps fail
    } catch (Exception $e) {
      exit_with_error_message('Failed to update status: '.$e->getMessage());
    }

    // Update puzzle URI
    try {
      $uri_data = array('puzzle_uri' => $puzzle_uri);
      $uri_resp = postapi("/puzzles/{$promote_puzzle_id}/puzzle_uri", $uri_data);
      assert_api_success($uri_resp);
      echo '<div class="success">✓ Puzzle URI updated</div>';
    } catch (Exception $e) {
      // Critical failure - try to rollback
      echo '<div class="error">CRITICAL: Failed to update puzzle URI: '.$e->getMessage().'</div>';
      if ($rollback_needed) {
        try {
          postapi("/puzzles/{$promote_puzzle_id}/status", array('status' => 'Speculative'));
          echo '<div class="error">⟲ Rolled back to Speculative status</div>';
        } catch (Exception $rollback_e) {
          echo '<div class="error">⚠ Rollback failed - puzzle may be in inconsistent state</div>';
        }
      }
      exit_with_error_message('Promotion failed. Please check puzzle state and try again.');
    }

    // Update name if provided
    if (!empty($name) && sanitize_string($name) != '') {
      try {
        $name_data = array('name' => $name);
        $name_resp = postapi("/puzzles/{$promote_puzzle_id}/name", $name_data);
        assert_api_success($name_resp);
        echo '<div class="success">✓ Puzzle name updated</div>';
      } catch (Exception $e) {
        // Non-critical - puzzle is still usable with old name
        echo '<div class="error">Warning: Could not update name: '.$e->getMessage().'</div>';
        echo '<div class="error">Promotion partially successful - puzzle is now "New" status with updated URL but old name.</div>';
        $promotion_failed = true;
      }
    }

    // Update round if provided
    if (is_numeric($round_id)) {
      try {
        $round_data = array('round_id' => $round_id);
        $round_resp = postapi("/puzzles/{$promote_puzzle_id}/round_id", $round_data);
        assert_api_success($round_resp);
        echo '<div class="success">✓ Puzzle moved to new round</div>';
      } catch (Exception $e) {
        // Non-critical - puzzle is still in original round
        echo '<div class="error">Warning: Could not move to new round: '.$e->getMessage().'</div>';
        $promotion_failed = true;
      }
    }

    echo '<br><div class="'.($promotion_failed ? 'error' : 'success').'">';
    if ($promotion_failed) {
      echo '<strong>Puzzle partially promoted.</strong> ';
      echo 'Status and URL were updated, but some optional fields failed. ';
    } else {
      echo '<strong>Puzzle promoted successfully!</strong> ';
    }
    echo '<a href="editpuzzle.php?pid='.$promote_puzzle_id.'">View puzzle</a>';
    echo '</div><br><hr>';
    echo '<a href="addpuzzle.php">Add another puzzle</a><br>';
    echo '<a href="index.php">Return to Puzzleboss Home</a>';
    exit(0);
  }

  // Normal puzzle creation flow
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
  echo '</div><br>';

  // If speculative checkbox was checked, update status to Speculative
  if (isset($_POST['is_speculative']) && $_POST['is_speculative'] == '1') {
    echo 'Setting puzzle status to Speculative...<br>';
    try {
      $status_data = array('status' => 'Speculative');
      $status_resp = postapi("/puzzles/{$pid}/status", $status_data);
      assert_api_success($status_resp);
      echo '<div class="success">Puzzle marked as speculative.</div>';
    } catch (Exception $e) {
      echo '<div class="error">Warning: Could not set speculative status: '.$e->getMessage().'</div>';
    }
  }

  echo '<hr>';
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

// Fetch speculative puzzles for promotion workflow
$speculative_puzzles = array();
try {
  $all_puzzles_data = readapi("/all");
  if (isset($all_puzzles_data->rounds)) {
    foreach ($all_puzzles_data->rounds as $round) {
      if (isset($round->puzzles)) {
        foreach ($round->puzzles as $puzzle) {
          if (isset($puzzle->status) && $puzzle->status === 'Speculative') {
            $puzzle->round_name = $round->name;  // Add round name for display
            $speculative_puzzles[] = $puzzle;
          }
        }
      }
    }
  }
} catch (Exception $e) {
  // If fetching fails, just continue with empty list
}
?>

<h1>Add a puzzle!</h1>
<form action="addpuzzle.php" method="post" onsubmit="return handleSubmit(event)">

  <fieldset style="margin-bottom: 20px;">
    <legend><strong>Puzzle Type</strong></legend>
    <label>
      <input type="radio" name="puzzle_mode" value="new" checked onchange="togglePuzzleMode()" />
      Create new puzzle
    </label>
    <br>
<?php if (count($speculative_puzzles) > 0): ?>
    <label>
      <input type="radio" name="puzzle_mode" value="promote" onchange="togglePuzzleMode()" />
      Promote existing speculative puzzle
    </label>
<?php endif; ?>
  </fieldset>

  <div id="promote-puzzle-fields" style="display:none;">
    <p><strong>Select speculative puzzle to promote:</strong></p>
    <select name="promote_puzzle_id" id="promote_puzzle_id" style="width: 100%; max-width: 600px;">
      <option value="">-- Select a speculative puzzle --</option>
<?php foreach ($speculative_puzzles as $sp): ?>
      <option value="<?= htmlentities($sp->id) ?>">
        <?= htmlentities($sp->name) ?> (<?= htmlentities($sp->round_name) ?>)
      </option>
<?php endforeach; ?>
    </select>
    <p style="font-size: 90%; font-style: italic;">
      Promoting will update the selected puzzle's name, URL, round (if changed), and status to "New" while preserving its sheet, chat, and solver history.
    </p>
  </div>

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
    <tr id="speculative-checkbox-row">
      <td></td>
      <td>
        <label>
          <input type="checkbox" id="is_speculative" name="is_speculative" value="1" />
          Mark as speculative (placeholder for puzzle not yet released)
        </label>
      </td>
    </tr>
  </table>

  <input type="submit" name="submit" value="Add New Puzzle"/>
</form>
</main>
<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
