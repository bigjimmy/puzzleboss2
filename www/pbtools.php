<?php
require('puzzlebosslib.php');

$bookmarkuri = trim(str_replace('<<<PBROOTURI>>>', $pbroot, $bookmarkuri));

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzzleboss-only Tools</title>
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
  </style>
</head>
<body>
<main>
<h1>Puzzleboss-only Admin Tools</h1>

<hr>
<h3>New Puzzle / Check for Puzzles Bookmarklet</h3>
A major timesaver for Puzzlebosses, this bookmarklet works in two ways:
<ul>
  <li>On a puzzle page, click it to create a new puzzle</li>
  <li>On the List of Puzzles page (<tt>/puzzles</tt>), click it to check if PB is missing anything.</li>
</ul>
<table border="2" cellpadding="3">
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
<br>

<hr>
<h3>Add New Puzzle</h3>
<strong><a href="addpuzzle.php" target="_blank">Page to add new puzzles</a></strong>
<br>

<hr>
<h3>Add New Round (backup)</h3>
<p>
  <strong>No longer necessary!</strong>
  If you use the bookmarklet above on a puzzle in a new round,
  you can create new rounds
  <a href="addpuzzle.php" target="_blank">on the new puzzle page</a>.
</p>
<table border="2" cellpadding="3">
  <tr>
    <td>To add a new round (enter round name):</td>
    <td valign="middle">
      <form action="addround.php" method="post">
        <input type="text" name="name">
        <input type="submit" name="submit" value="Add Round">
      </form>
    </td>
  </tr>
</table>
<br>

<hr>
<h3>Solver Assignment</h3>
<table border="2" cellpadding="3">
  <tr>
    <td>To manually edit a solver's current puzzle assignment (enter username):</td>
    <td valign="middle">
      <form action="editsolver.php" method="get">
        <input type="text" name="assumedid">
        <input type="submit" name="ok" value="Edit Solver">
      </form>
    </td>
  </tr>
</table>

<hr>
<h3>Tag Management</h3>
<?php
// Handle tag deletion
if (isset($_POST['delete_tag']) && !empty($_POST['tag_to_delete'])) {
  $tag_to_delete = $_POST['tag_to_delete'];
  try {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $config->api_base . '/tags/' . urlencode($tag_to_delete));
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

<?php if (count($alltags) > 0): ?>
<table border="2" cellpadding="3">
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

</main>
<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a>
<br><a href="/pb/admin.php">Puzztech-only Puzzleboss Admininstration Page</a>
</footer>
</body>
</html>
