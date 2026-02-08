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
  <style>
    /* Align column widths for Add New Round, Solver Assignment, and Tag Management tables */
    #app .info-box-content table td:first-child {
      width: 65%;
    }

    #app .info-box-content table td:last-child {
      width: 35%;
    }

    /* Table styling matching status.php */
    #app table {
      width: 100%;
      border-collapse: collapse;
      background: white;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid #ddd;
    }

    #app th, #app td {
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid #ddd;
      font-size: 0.9em;
    }

    #app th {
      background: #e6f2ff;
      color: #0066cc;
      font-weight: 600;
    }

    #app tr:hover {
      background: #f5f5f5;
    }
  </style>
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
<table>
  <tr>
    <td>Drag this link to your bookmarks:</td>
    <td><a href="<?= $bookmarkuri ?>">Add to Puzzboss</a></td>
  </tr>
  <tr>
    <td>Or alternatively, copy the following into a new bookmark:</td>
    <td>
      <div style="background-color: lightgray; font-size: 40%;">
        <code><?= $bookmarkuri ?></code>
      </div>
    </td>
  </tr>
</table>
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
<table>
  <tr>
    <td>To add a new round (enter round name):</td>
    <td>
      <form action="addround.php" method="post">
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
<table>
  <tr>
    <td>To manually edit a solver's current puzzle assignment (enter username):</td>
    <td>
      <form action="editsolver.php" method="get">
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
      echo '<div class="success" style="background-color: lightgreen; padding: 10px; margin: 10px 0;">✅ Tag "' . htmlentities($responseobj->tag->name) . '" created (ID: ' . $responseobj->tag->id . ').</div>';
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
      echo '<div class="success" style="background-color: lightgreen; padding: 10px; margin: 10px 0;">✅ Tag "' . htmlentities($tag_to_delete) . '" deleted. Removed from ' . $result->puzzles_updated . ' puzzle(s).</div>';
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

<table>
  <tr>
    <td>Create a new tag:</td>
    <td>
      <form action="pbtools.php" method="post" style="display:inline;">
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
      <form action="pbtools.php" method="post" style="display:inline;" onsubmit="return confirm('Are you sure you want to delete tag \'<?= htmlentities($tag->name) ?>\'? This will remove it from all puzzles.');">
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
