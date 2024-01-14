<?php
require('puzzlebosslib.php');

if (!isset($_GET['pname']) || empty($_GET['pname'])) {
    http_response_code(500);
    die('Error: No puzzlename parameter (pname) specified.');
}

$name = $_GET['pname'];
$name2 = str_replace('-', '', ucwords($name, '-'));

$puzzles = readapi('/puzzles');
if (!$puzzles) {
    http_response_code(500);
    die('Error: api fetch of puzzle catalog failed!');
}

$puzzle_id = null;
foreach ($puzzles->puzzles as $puzzle) {
    if ($puzzle->name === $name || $puzzle->name === $name2) {
        $puzzle_id = $puzzle->id;
        break;
    }
}
if (!$puzzle_id) {
    http_response_code(500);
    die('Error: api search for puzzle in catalog failed!');
}

$drive_uri = readapi("/puzzles/$puzzle_id/drive_uri")
    ->puzzle
    ->drive_uri;

if (!$drive_uri) {
    http_response_code(500);
    die("Missing drive_uri for puzzle $puzzle_id!");
}

header("Location: $drive_uri");
?>
<html>
<head>
<title>Redirect to puzzle doc</title>
</head>
<body>
Click <a href="<?php $drive_uri ?>">here</a> to doc sheet for puzzle <?= $name ?>
</body>
</html>
