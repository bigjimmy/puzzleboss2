<?php
require('puzzlebosslib.php');
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Add Puzzle</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
  <script type="module" src="./auth-reload.js"></script>
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

  function updatePuzzleMode() {
    const promotePuzzleRadio = document.querySelector('input[name="promote_puzzle_id"]:checked');
    const speculativeCheckbox = document.getElementById('speculative-checkbox-row');
    const submitButton = document.querySelector('input[type="submit"]');
    const nameField = document.getElementById('name');
    const nameOptionalHint = document.getElementById('name-optional-hint');
    const puzzleModeInput = document.getElementById('puzzle_mode_value');
    const roundSelect = document.getElementById('round_id');
    const currentPuzzleInfo = document.getElementById('current-puzzle-info');

    // Check if a speculative puzzle is selected
    const isPromoting = promotePuzzleRadio && promotePuzzleRadio.value !== '';

    if (isPromoting) {
      // Promotion mode
      if (speculativeCheckbox) speculativeCheckbox.style.display = 'none';
      if (submitButton) submitButton.value = 'Promote Puzzle';
      if (nameField) nameField.required = false;
      if (nameOptionalHint) nameOptionalHint.style.display = 'inline';
      if (puzzleModeInput) puzzleModeInput.value = 'promote';

      // Show current puzzle info
      if (currentPuzzleInfo && promotePuzzleRadio) {
        document.getElementById('current-puzzle-name').textContent = promotePuzzleRadio.dataset.puzzleName || '';
        document.getElementById('current-puzzle-round').textContent = promotePuzzleRadio.dataset.puzzleRound || '';
        document.getElementById('current-puzzle-uri').textContent = promotePuzzleRadio.dataset.puzzleUri || '(none)';
        currentPuzzleInfo.style.display = 'block';
      }

      // Add "Keep current round" option if it doesn't exist
      if (roundSelect && !roundSelect.querySelector('option[value=""]')) {
        const keepCurrentOption = document.createElement('option');
        keepCurrentOption.value = '';
        keepCurrentOption.textContent = '-- Keep current round --';
        roundSelect.insertBefore(keepCurrentOption, roundSelect.firstChild);
      }
      // Only default to "Keep current round" if no round was pre-selected from URL params
      // If URL params specified a round, keep that selection
      const hasPreselection = roundSelect && roundSelect.dataset.hasPreselection === '1';
      if (roundSelect && !hasPreselection) {
        roundSelect.value = '';
      }
    } else {
      // New puzzle mode
      if (speculativeCheckbox) speculativeCheckbox.style.display = '';
      if (submitButton) submitButton.value = 'Add New Puzzle';
      if (nameField) nameField.required = true;
      if (nameOptionalHint) nameOptionalHint.style.display = 'none';
      if (puzzleModeInput) puzzleModeInput.value = 'new';

      // Hide current puzzle info
      if (currentPuzzleInfo) currentPuzzleInfo.style.display = 'none';

      // Remove "Keep current round" option if it exists
      if (roundSelect) {
        const keepCurrentOption = roundSelect.querySelector('option[value=""]');
        if (keepCurrentOption) keepCurrentOption.remove();
      }
    }
  }

  // Step-by-step puzzle creation functions
  const steps = [
    { id: 'step1', num: 1, label: 'Validate puzzle data' },
    { id: 'step2', num: 2, label: 'Create Discord channel' },
    { id: 'step3', num: 3, label: 'Create Google Sheet' },
    { id: 'step4', num: 4, label: 'Insert puzzle into database' },
    { id: 'step5', num: 5, label: 'Finalize puzzle' }
  ];

  function setStepStatus(stepId, status, label) {
    const el = document.getElementById(stepId);
    if (!el) return;
    el.className = 'step ' + status;
    if (status === 'active') {
      el.querySelector('.status').textContent = '🔄';
    } else if (status === 'complete') {
      el.querySelector('.status').textContent = '✅';
    } else if (status === 'skipped') {
      el.querySelector('.status').textContent = '⏭️';
    } else if (status === 'error') {
      el.querySelector('.status').textContent = '❌';
    }
    if (label) {
      el.querySelector('.label').textContent = label;
    }
  }

  async function runStep(code, stepNum) {
    const step = steps[stepNum - 1];
    setStepStatus(step.id, 'active');

    try {
      const url = 'apicall.php?apicall=createpuzzle&apiparam1=' + encodeURIComponent(code) + '&step=' + stepNum;
      const response = await fetch(url);
      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }
      if (data.status !== 'ok') {
        throw new Error(data.message || 'Unknown error');
      }

      window.onFetchSuccess?.();

      // Mark complete or skipped
      if (data.skipped) {
        setStepStatus(step.id, 'skipped', data.message || step.label + ' (skipped)');
      } else {
        setStepStatus(step.id, 'complete', data.message || step.label + ' complete');
      }

      return data;
    } catch (err) {
      if (window.onFetchFailure?.()) return;
      setStepStatus(step.id, 'error', err.message);
      throw err;
    }
  }

  async function runAllSteps(code, puzzleName) {
    let puzzleId = null;

    for (let i = 1; i <= 5; i++) {
      try {
        const result = await runStep(code, i);
        // Step 4 returns the puzzle ID
        if (i === 4 && result.puzzle_id) {
          puzzleId = result.puzzle_id;
        }
      } catch (err) {
        document.getElementById('error-container').style.display = 'block';
        document.getElementById('error-message').textContent = err.message;
        return;
      }
    }

    // All done - show success
    document.getElementById('success-container').style.display = 'block';
    if (puzzleId) {
      document.getElementById('success-puzzle-link').href = 'editpuzzle.php?pid=' + puzzleId;
      document.getElementById('success-puzzle-link').textContent = puzzleId;
      document.getElementById('success-puzzle-name').textContent = puzzleName;
    }
  }
  </script>
</head>
<body class="status-page">
<main style="max-width: none;">
<?php

$round_id = null;
if (isset($_POST['submit'])) {
  // Show header and navbar when processing form submission
  echo '<div class="status-header">';
  echo '  <h1>Adding Puzzle...</h1>';
  echo '</div>';
  echo render_navbar();

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
    $is_meta = isset($_POST['is_meta']) && $_POST['is_meta'] == '1';

    echo '<h2>Promoting Speculative Puzzle</h2>';

    // Build the list of promotion steps
    $promote_steps = array();
    $promote_steps[] = array('label' => 'Validate puzzle data');
    $promote_steps[] = array('label' => 'Update status to New');
    $promote_steps[] = array('label' => 'Update puzzle URI');
    if (!empty($name) && sanitize_string($name) != '') {
      $promote_steps[] = array('label' => 'Update puzzle name');
    }
    if (is_numeric($round_id)) {
      $promote_steps[] = array('label' => 'Move to new round');
    }
    if ($is_meta) {
      $promote_steps[] = array('label' => 'Mark as meta');
    }
    $promote_steps[] = array('label' => 'Finalize promotion');

    // Render progress container
    echo '<div id="progress-container">';
    foreach ($promote_steps as $i => $s) {
      $id = 'step' . ($i + 1);
      echo '<div class="step" id="' . $id . '">';
      echo '<span class="status">⏳</span>';
      echo '<span class="label">' . $s['label'] . '</span>';
      echo '</div>';
    }
    echo '</div>';

    // Helper to update a step's status via inline script
    function promote_step($step_num, $status, $label = null) {
      $label_js = $label ? ", '" . addslashes($label) . "'" : '';
      echo "<script>setStepStatus('step{$step_num}', '{$status}'{$label_js});</script>";
      flush();
    }

    $step = 1;
    $promotion_failed = false;
    $rollback_needed = false;

    // Step: Validate everything before making any changes
    promote_step($step, 'active');
    try {
      $puzzle_resp = readapi("/puzzles/{$promote_puzzle_id}");
      if (!isset($puzzle_resp->puzzle)) {
        throw new Exception("Puzzle ID $promote_puzzle_id not found");
      }
      if ($puzzle_resp->puzzle->status !== 'Speculative') {
        throw new Exception("Puzzle is not in Speculative status (current: {$puzzle_resp->puzzle->status})");
      }
      if (empty($puzzle_uri)) {
        throw new Exception('You must provide a puzzle URI when promoting a speculative puzzle');
      }
      if (!empty($name) && sanitize_string($name) != '') {
        $sanitized_name = sanitize_string($name);
        $all_puzzles = readapi("/puzzles");
        foreach ($all_puzzles->puzzles as $p) {
          if ($p->name === $sanitized_name && $p->id != $promote_puzzle_id) {
            throw new Exception("Duplicate puzzle name detected: $sanitized_name");
          }
        }
      }
      if (is_numeric($round_id)) {
        $round_resp = readapi("/rounds/{$round_id}");
        if (!isset($round_resp->round)) {
          throw new Exception("Round ID $round_id not found");
        }
      }
      promote_step($step, 'complete', 'Validation passed');
    } catch (Exception $e) {
      promote_step($step, 'error', 'Validation failed: ' . $e->getMessage());
      echo '<div class="error"><strong>ERROR:</strong> ' . htmlentities($e->getMessage()) . '<br><br><a href="addpuzzle.php">Try again</a></div>';
      exit(0);
    }

    // Step: Update status to New
    $step++;
    promote_step($step, 'active');
    try {
      $status_resp = postapi("/puzzles/{$promote_puzzle_id}/status", array('status' => 'New'));
      assert_api_success($status_resp);
      promote_step($step, 'complete', 'Status changed to "New"');
      $rollback_needed = true;
    } catch (Exception $e) {
      promote_step($step, 'error', 'Failed: ' . $e->getMessage());
      echo '<div class="error"><strong>ERROR:</strong> ' . htmlentities($e->getMessage()) . '<br><br><a href="addpuzzle.php">Try again</a></div>';
      exit(0);
    }

    // Step: Update puzzle URI
    $step++;
    promote_step($step, 'active');
    try {
      $uri_resp = postapi("/puzzles/{$promote_puzzle_id}/puzzle_uri", array('puzzle_uri' => $puzzle_uri));
      assert_api_success($uri_resp);
      promote_step($step, 'complete', 'Puzzle URI updated');
    } catch (Exception $e) {
      promote_step($step, 'error', 'Failed: ' . $e->getMessage());
      // Critical failure - try to rollback
      if ($rollback_needed) {
        try {
          postapi("/puzzles/{$promote_puzzle_id}/status", array('status' => 'Speculative'));
        } catch (Exception $rollback_e) {
          // Rollback failed silently
        }
      }
      echo '<div class="error"><strong>ERROR:</strong> ' . htmlentities($e->getMessage()) . '. Rolled back to Speculative.<br><br><a href="addpuzzle.php">Try again</a></div>';
      exit(0);
    }

    // Step: Update name (if provided)
    if (!empty($name) && sanitize_string($name) != '') {
      $step++;
      promote_step($step, 'active');
      try {
        $name_resp = postapi("/puzzles/{$promote_puzzle_id}/name", array('name' => $name));
        assert_api_success($name_resp);
        promote_step($step, 'complete', 'Puzzle name updated');
      } catch (Exception $e) {
        promote_step($step, 'error', 'Warning: ' . $e->getMessage());
        $promotion_failed = true;
      }
    }

    // Step: Move to new round (if provided)
    if (is_numeric($round_id)) {
      $step++;
      promote_step($step, 'active');
      try {
        $round_resp = postapi("/puzzles/{$promote_puzzle_id}/round_id", array('round_id' => $round_id));
        assert_api_success($round_resp);
        promote_step($step, 'complete', 'Moved to new round');
      } catch (Exception $e) {
        promote_step($step, 'error', 'Warning: ' . $e->getMessage());
        $promotion_failed = true;
      }
    }

    // Step: Mark as meta (if requested)
    if ($is_meta) {
      $step++;
      promote_step($step, 'active');
      try {
        $meta_resp = postapi("/puzzles/{$promote_puzzle_id}/ismeta", array('ismeta' => true));
        assert_api_success($meta_resp);
        promote_step($step, 'complete', 'Marked as meta');
      } catch (Exception $e) {
        promote_step($step, 'error', 'Warning: ' . $e->getMessage());
        $promotion_failed = true;
      }
    }

    // Final step
    $step++;
    if ($promotion_failed) {
      promote_step($step, 'error', 'Promotion partially complete');
      echo '<div class="error"><strong>Puzzle partially promoted.</strong> Status and URL were updated, but some optional fields failed. ';
      echo '<a href="editpuzzle.php?pid='.$promote_puzzle_id.'">View puzzle</a></div>';
    } else {
      promote_step($step, 'complete', 'Promotion successful!');
      echo '<h2>✅ Puzzle promoted successfully!</h2>';
      echo '<p><a href="editpuzzle.php?pid='.$promote_puzzle_id.'">View puzzle</a></p>';
    }
    echo '<p><a href="addpuzzle.php">Add another puzzle</a></p>';
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

  $is_meta = isset($_POST['is_meta']) && $_POST['is_meta'] == '1';
  $is_speculative = isset($_POST['is_speculative']) && $_POST['is_speculative'] == '1';

  // Always use step-by-step creation with progress UI
  echo '<h2>Creating puzzle...</h2>';

  $data = array(
    'puzzle' => array(
      'name' => $name,
      'round_id' => $round_id,
      'puzzle_uri' => $puzzle_uri,
      'ismeta' => $is_meta ? 1 : 0,
      'is_speculative' => $is_speculative ? 1 : 0,
    )
  );

  try {
    $responseobj = postapi("/puzzles/stepwise", $data);
    assert_api_success($responseobj);
    $code = $responseobj->code;

    echo <<<HTML
<div id="progress-container">
  <div class="step" id="step1">
    <span class="status">⏳</span>
    <span class="label">Validating puzzle data...</span>
  </div>
  <div class="step" id="step2">
    <span class="status">⏳</span>
    <span class="label">Creating Discord channel...</span>
  </div>
  <div class="step" id="step3">
    <span class="status">⏳</span>
    <span class="label">Creating Google Sheet...</span>
  </div>
  <div class="step" id="step4">
    <span class="status">⏳</span>
    <span class="label">Inserting puzzle into database...</span>
  </div>
  <div class="step" id="step5">
    <span class="status">⏳</span>
    <span class="label">Finalizing puzzle...</span>
  </div>
</div>
<div id="error-container" class="error" style="display: none;">
  <strong>ERROR:</strong>
  <span id="error-message"></span>
  <br><br>
  <a href="addpuzzle.php">Try again</a>
</div>
<div id="success-container" style="display: none;">
  <h2>✅ Puzzle creation successful!</h2>
  <p>
    Puzzle <strong id="success-puzzle-name"></strong> created with ID
    <a href="#" id="success-puzzle-link"></a>.
  </p>
  <p>
    <a href="addpuzzle.php">Add another puzzle</a>
  </p>
</div>
<script>
  // Start the step-by-step process
  runAllSteps('$code', '$name');
</script>
HTML;
  } catch (Exception $e) {
    exit_with_api_error($e);
  }
  exit(0);
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

<div class="status-header">
  <h1>Add a puzzle!</h1>
</div>

<?= render_navbar() ?>

<div id="app">

<form action="addpuzzle.php" method="post" onsubmit="return handleSubmit(event)">

  <!-- Hidden field to track puzzle mode (new vs promote) -->
  <input type="hidden" id="puzzle_mode_value" name="puzzle_mode" value="new" />

<?php if (count($speculative_puzzles) > 0): ?>
<div class="info-box">
  <div class="info-box-header" @click="showPromote = !showPromote">
    <span class="collapse-icon" :class="{ collapsed: !showPromote }">▼</span>
    <h3>🔮 Promote a Speculative Puzzle (Optional)</h3>
  </div>
  <div class="info-box-content" v-show="showPromote">
  <div id="promote-puzzle-fields">
    <table>
      <thead>
        <tr>
          <th>Select</th>
          <th>Puzzle Name</th>
          <th>Round</th>
          <th>Current URI</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>
            <input type="radio"
                   name="promote_puzzle_id"
                   value=""
                   id="promote_puzzle_new"
                   onclick="updatePuzzleMode()"
                   checked>
          </td>
          <td><label for="promote_puzzle_new"><strong>New Puzzle</strong></label></td>
          <td colspan="2"><em>Create a new puzzle</em></td>
        </tr>
<?php foreach ($speculative_puzzles as $sp): ?>
        <tr>
          <td>
            <input type="radio"
                   name="promote_puzzle_id"
                   value="<?= htmlentities($sp->id) ?>"
                   id="promote_puzzle_<?= htmlentities($sp->id) ?>"
                   data-puzzle-name="<?= htmlentities($sp->name) ?>"
                   data-puzzle-round="<?= htmlentities($sp->round_name) ?>"
                   data-puzzle-uri="<?= htmlentities($sp->puzzle_uri ?? '') ?>"
                   onclick="updatePuzzleMode()">
          </td>
          <td><label for="promote_puzzle_<?= htmlentities($sp->id) ?>"><?= htmlentities($sp->name) ?></label></td>
          <td><?= htmlentities($sp->round_name) ?></td>
          <td><?= htmlentities($sp->puzzle_uri ?? '(none)') ?></td>
        </tr>
<?php endforeach; ?>
      </tbody>
    </table>
      <div id="current-puzzle-info" class="info-callout" style="display: none;">
        <p style="margin: 0 0 5px 0; font-weight: bold; font-size: 90%;">Current puzzle values:</p>
        <p style="margin: 5px 0; font-size: 85%; font-family: 'Courier New', Courier, monospace;">
          <strong>Name:</strong> <span id="current-puzzle-name"></span><br>
          <strong>Round:</strong> <span id="current-puzzle-round"></span><br>
          <strong>URI:</strong> <span id="current-puzzle-uri"></span>
        </p>
      </div>
      <p style="font-size: 90%; font-style: italic; margin: 10px 0 0 0; color: #666;">
        Fill in the name, round, and URI fields below to update the puzzle. Leave blank to keep current values.
      </p>
  </div>
  </div>
</div>
<?php endif; ?>

<div class="info-box">
  <div class="info-box-header" @click="showPuzzleForm = !showPuzzleForm">
    <span class="collapse-icon" :class="{ collapsed: !showPuzzleForm }">▼</span>
    <h3>Puzzle Details</h3>
  </div>
  <div class="info-box-content" v-show="showPuzzleForm">
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
        <span id="name-optional-hint" style="display: none; font-size: 85%; font-style: italic; color: #666;">
          (optional when promoting)
        </span>
      </td>
    </tr>
    <tr>
      <td><label for="round_id">Round:</label></td>
      <td>
<?php
// Calculate if any round will be pre-selected from URL params
$selected_any = false;
foreach ($rounds as $round) {
  if ($round->name === $round_name || $round->id === $round_id) {
    $selected_any = true;
    break;
  }
}
$offer_create_new_round = !$selected_any && $round_name && $round_name !== 'undefined';
?>
        <select id="round_id" name="round_id" data-has-preselection="<?= ($selected_any || $offer_create_new_round) ? '1' : '0' ?>">
<?php
foreach ($rounds as $round) {
  $selected = ($round->name === $round_name || $round->id === $round_id) ? 'selected' : '';
  echo "<option value=\"{$round->id}\" $selected>{$round->name}</option>\n";
}
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
    <tr>
      <td></td>
      <td>
        <label>
          <input type="checkbox" id="is_meta" name="is_meta" value="1" />
          This puzzle is a meta
        </label>
      </td>
    </tr>
  </table>

  <input type="submit" name="submit" value="Add New Puzzle"/>
  </div>
</div>
</form>

</div>
</main>

<script>
const { createApp } = Vue;

createApp({
  data() {
    return {
      showPromote: true,
      showPuzzleForm: true
    }
  }
}).mount('#app');
</script>
</body>
</html>
