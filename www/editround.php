<?php
require('puzzlebosslib.php');

// Check for authenticated user
$solver = getauthenticatedsolver();

// Get round ID from URL
$rid = $_GET['rid'] ?? null;
if (!$rid) {
    die("No round ID specified");
}

// Get round data
$round = readapi("/rounds/$rid")->round;
if (!$round) {
    die("Round not found");
}

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $updates = [];
    
    // Update name if changed
    if (isset($_POST['name']) && $_POST['name'] !== $round->name) {
        $updates[] = ['part' => 'name', 'value' => $_POST['name']];
    }
    
    // Update comments if changed
    if (isset($_POST['comments']) && $_POST['comments'] !== $round->comments) {
        $updates[] = ['part' => 'comments', 'value' => $_POST['comments']];
    }
    
    // Apply updates
    foreach ($updates as $update) {
        $response = postapi("/rounds/$rid/{$update['part']}", [$update['part'] => $update['value']]);
        if ($response->status !== 'ok') {
            die("Error updating round: " . ($response->error ?? 'Unknown error'));
        }
    }
    
    // Refresh round data after updates
    $round = readapi("/rounds/$rid")->round;
}

// Get round statistics
$num_puzzles = count($round->puzzles);
$num_solved = 0;
$num_metas = 0;
$num_metas_solved = 0;

foreach ($round->puzzles as $puzzle) {
    if ($puzzle->status === 'Solved') {
        $num_solved++;
    }
    if ($puzzle->ismeta) {
        $num_metas++;
        if ($puzzle->status === 'Solved') {
            $num_metas_solved++;
        }
    }
}

?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Edit Round: <?= htmlspecialchars($round->name) ?></title>
    <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="status-page" style="max-width: 800px; margin: 0 auto;">

    <div class="status-header">
        <h1>Edit Round: <?= htmlspecialchars($round->name) ?></h1>
    </div>

    <?= render_navbar('editround') ?>

    <div class="info-box">
        <div class="info-box-header">
            <h3>Round Statistics</h3>
        </div>
        <div class="info-box-content">
            <table class="table-cols-65-35">
                <tr><td>Total Puzzles</td><td><?= $num_puzzles ?></td></tr>
                <tr><td>Solved Puzzles</td><td><?= $num_solved ?></td></tr>
                <tr><td>Meta Puzzles</td><td><?= $num_metas ?></td></tr>
                <tr><td>Solved Metas</td><td><?= $num_metas_solved ?></td></tr>
                <?php if ($round->drive_uri): ?>
                    <tr><td>Drive Folder</td><td><a href="<?= htmlspecialchars($round->drive_uri) ?>" target="_blank">Open</a></td></tr>
                <?php endif; ?>
            </table>
        </div>
    </div>

    <div class="info-box">
        <div class="info-box-header">
            <h3>Edit Round</h3>
        </div>
        <div class="info-box-content">
            <form method="POST">
                <table class="edit-table">
                    <tr>
                        <td><label for="name">Round Name:</label></td>
                        <td>
                            <input type="text" id="name" name="name" value="<?= htmlspecialchars($round->name) ?>" required>
                        </td>
                    </tr>
                    <tr>
                        <td><label for="comments">Comments:</label></td>
                        <td>
                            <textarea id="comments" name="comments"><?= htmlspecialchars($round->comments ?? '') ?></textarea>
                        </td>
                    </tr>
                </table>
                <br>
                <button type="submit">Save Changes</button>
            </form>
        </div>
    </div>

    <div class="info-box">
        <div class="info-box-header">
            <h3>Puzzles in this Round</h3>
        </div>
        <div class="info-box-content">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Meta</th>
                        <th>Answer</th>
                    </tr>
                </thead>
                <tbody>
                <?php foreach ($round->puzzles as $puzzle): ?>
                    <tr>
                        <td>
                            <a href="editpuzzle.php?pid=<?= $puzzle->id ?>">
                                <?= htmlspecialchars($puzzle->name) ?>
                            </a>
                        </td>
                        <td><?= htmlspecialchars($puzzle->status) ?></td>
                        <td><?= $puzzle->ismeta ? 'Yes' : 'No' ?></td>
                        <td><?= htmlspecialchars($puzzle->answer ?? '') ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    </div>

    <footer>
        <a href="index.php">← Back to Puzzleboss Home</a>
    </footer>
</body>
</html> 