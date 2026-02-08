<?php 
require('puzzlebosslib.php');

// Check for authenticated user
$solver = getauthenticatedsolver();
$uid = $solver->id;
$username = $solver->name;

// Get all available tags
$alltags = readapi('/tags')->tags ?? array();

// Handle search
$search_tag = null;
$search_results = null;
$puzzles_by_round = array();

if (isset($_GET['tag']) && !empty($_GET['tag'])) {
  $search_tag = strtolower(trim($_GET['tag']));
  
  try {
    $result = readapi('/search?tag=' . urlencode($search_tag));
    $search_results = $result->puzzles ?? array();
    
    // Organize puzzles by round (API now returns full puzzle data)
    foreach ($search_results as $puzzle) {
      $round_name = $puzzle->roundname ?? 'Unknown Round';
      if (!isset($puzzles_by_round[$round_name])) {
        $puzzles_by_round[$round_name] = array();
      }
      $puzzles_by_round[$round_name][] = $puzzle;
    }
  } catch (Exception $e) {
    $search_error = $e->getMessage();
  }
}
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Search Puzzles by Tag</title>
  <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&amp;family=Open+Sans:wght@400;700&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./pb-ui.css">
  <style>
  body {
    background-color: var(--bg-page);
    font-family: 'Lora';
    margin: 20px;
  }
  h1 {
    margin-bottom: 10px;
  }
  .search-form {
    background-color: var(--bg-white);
    border: 1px solid var(--border-medium);
    padding: 20px;
    margin-bottom: 20px;
    max-width: 600px;
  }
  .search-form h3 {
    margin-top: 0;
  }
  .tag-list {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid var(--border-light);
    padding: 10px;
    margin: 10px 0;
  }
  .tag-list label {
    display: block;
    padding: 2px 0;
    cursor: pointer;
  }
  .tag-list label:hover {
    background-color: var(--bg-gray);
  }
  table.results {
    border-collapse: collapse;
    margin: 10px 0;
  }
  table.results th, table.results td {
    border: 1px solid var(--text-secondary);
    padding: 5px 10px;
    text-align: left;
  }
  table.results th {
    background-color: #ddd;
  }
  .round-section {
    margin-bottom: 20px;
  }
  .round-section h3 {
    margin-bottom: 5px;
    background-color: #e0e0e0;
    padding: 5px 10px;
  }
  </style>
</head>
<body>
<h1>Search Puzzles by Tag</h1>
<p>You are: <?= htmlentities($username) ?> | <a href="old.php">Back to Main Board</a></p>

<div class="search-form">
  <form method="get" action="search.php">
    <h3>Search by Tag Name</h3>
    <input type="text" name="tag" placeholder="Enter tag name..." value="<?= htmlentities($search_tag ?? '') ?>" style="width: 200px;">
    <input type="submit" value="Search">
  </form>
  
  <?php if (count($alltags) > 0): ?>
  <h3>Or Select from Existing Tags</h3>
  <form method="get" action="search.php">
    <div class="tag-list">
      <?php foreach ($alltags as $tag): ?>
        <label>
          <input type="radio" name="tag" value="<?= htmlentities($tag->name) ?>" <?= ($search_tag === $tag->name) ? 'checked' : '' ?>>
          <?= htmlentities($tag->name) ?>
        </label>
      <?php endforeach; ?>
    </div>
    <input type="submit" value="Search Selected Tag">
  </form>
  <?php else: ?>
  <p><em>No tags defined in the system yet.</em></p>
  <?php endif; ?>
</div>

<?php if (isset($search_error)): ?>
  <div class="error">Error: <?= htmlentities($search_error) ?></div>
<?php elseif ($search_tag !== null): ?>
  
  <?php if (count($search_results) === 0): ?>
    <div class="info">No puzzles found with tag "<?= htmlentities($search_tag) ?>"</div>
  <?php else: ?>
    <div class="success">Found <?= count($search_results) ?> puzzle(s) with tag "<?= htmlentities($search_tag) ?>"</div>
    
    <?php foreach ($puzzles_by_round as $round_name => $puzzles): ?>
    <div class="round-section">
      <h3><?= htmlentities($round_name) ?> (<?= count($puzzles) ?> puzzle<?= count($puzzles) != 1 ? 's' : '' ?>)</h3>
      <table class="results">
        <tr>
          <th>Status</th>
          <th>Puzzle</th>
          <th>Answer</th>
          <th>Tags</th>
          <th>Links</th>
        </tr>
        <?php foreach ($puzzles as $puzzle): ?>
        <tr>
          <td><?php echo get_status_display($puzzle->status); ?></td>
          <td>
            <a href="<?= htmlentities($puzzle->puzzle_uri ?? '#') ?>" target="_blank"><?= htmlentities($puzzle->name) ?></a>
            <?php if ($puzzle->ismeta): ?><span title="Meta">🎯</span><?php endif; ?>
          </td>
          <td style="font-family: monospace; font-weight: bold;"><?= htmlentities($puzzle->answer ?? '') ?></td>
          <td><?= htmlentities($puzzle->tags ?? '') ?></td>
          <td>
            <a href="<?= htmlentities($puzzle->drive_uri ?? '#') ?>" target="_blank" title="Spreadsheet">🗒️</a>
            <a href="<?= htmlentities($puzzle->chat_channel_link ?? '#') ?>" target="_blank" title="Discord">🗣️</a>
            <a href="editpuzzle.php?pid=<?= $puzzle->id ?>" target="_blank" title="Edit">⚙️</a>
          </td>
        </tr>
        <?php endforeach; ?>
      </table>
    </div>
    <?php endforeach; ?>
    
  <?php endif; ?>
<?php endif; ?>

</body>
</html>

