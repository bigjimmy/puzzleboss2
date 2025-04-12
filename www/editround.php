<?php
require('puzzlebosslib.php');

// Check for authenticated user
$uid = getauthenticateduser();
$solver = readapi("/solvers/$uid")->solver;

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
        try {
            $response = postapi("/rounds/$rid/{$update['part']}", [$update['part'] => $update['value']]);
            assert_api_success($response);
            echo '<div class="success">OK. Round ' . $update['part'] . ' updated.</div>';
        } catch (Exception $e) {
            exit_with_api_error($e);
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
<html>
<head>
    <title>Edit Round: <?= htmlspecialchars($round->name) ?></title>
    <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&amp;family=Open+Sans:wght@400;700&amp;display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Open Sans', sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2 {
            font-family: 'Lora', serif;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-family: inherit;
        }
        textarea {
            height: 100px;
            resize: vertical;
        }
        .stats {
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .stats p {
            margin: 5px 0;
        }
        .button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .button:hover {
            background-color: #45a049;
        }
        .puzzle-list {
            margin-top: 20px;
        }
        .puzzle-list table {
            width: 100%;
            border-collapse: collapse;
        }
        .puzzle-list th, .puzzle-list td {
            padding: 8px;
            border: 1px solid #ddd;
            text-align: left;
        }
        .puzzle-list th {
            background-color: #f2f2f2;
        }
    </style>
</head>
<body>
    <h1>Edit Round: <?= htmlspecialchars($round->name) ?></h1>
    
    <div class="stats">
        <h2>Round Statistics</h2>
        <p>Total Puzzles: <?= $num_puzzles ?></p>
        <p>Solved Puzzles: <?= $num_solved ?></p>
        <p>Meta Puzzles: <?= $num_metas ?></p>
        <p>Solved Metas: <?= $num_metas_solved ?></p>
        <?php if ($round->drive_uri): ?>
            <p>Drive Folder: <a href="<?= htmlspecialchars($round->drive_uri) ?>" target="_blank">Open</a></p>
        <?php endif; ?>
    </div>

    <form method="POST">
        <div class="form-group">
            <label for="name">Round Name:</label>
            <input type="text" id="name" name="name" value="<?= htmlspecialchars($round->name) ?>" required>
        </div>

        <div class="form-group">
            <label for="comments">Comments:</label>
            <textarea id="comments" name="comments"><?= htmlspecialchars($round->comments ?? '') ?></textarea>
        </div>

        <button type="submit" class="button">Save Changes</button>
    </form>

    <div class="puzzle-list">
        <h2>Puzzles in this Round</h2>
        <table>
            <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Meta</th>
                <th>Answer</th>
            </tr>
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
        </table>
    </div>

    <p><a href="old.php">Back to Main View</a></p>
</body>
</html> 