<?php 
require('puzzlebosslib.php');

if (isset($_GET['submit'])) {
    http_response_code(500);
    die('submission not implemented here');
}

// Check for authenticated user
$uid = getauthenticateduser();
$solver = readapi("/solvers/$uid")->solver;
$fullhunt = array_reverse(readapi('/all')->rounds);

if (isset($_GET['data'])) {
    header('Content-Type: application/json; charset=utf-8');
    die(json_encode(array(
        'solver' => $solver,
        'fullhunt' => $fullhunt,
        'server' => $_SERVER,
    )));
}

$use_text = isset($_GET['text_only']);

$username = $solver->name;
$mypuzzle = $solver->puzz;

?>
<html>
<head>
    <meta http-equiv="refresh" content=30>
    <title>Puzzleboss Interface</title>
</head>
<body>
You are: <?= $username ?><br>
<a href="status.php">Hunt Status Overview / Puzzle Suggester</a><br>
<table border=4 style="vertical-align:top;">
    <tr>
<?php
foreach ($fullhunt as $round) {
    echo '<th>' . $round->name . '</th>';
}
?>
    </tr>
    <tr style="vertical-align:top">
<?php
foreach ($fullhunt as $round) {
    echo '<td>';
    $puzzlearray = $round->puzzles;
    $metapuzzle = $round->meta_id;

    echo '<table>';
    foreach ($puzzlearray as $puzzle) {
        $puzzleid = $puzzle->id;
        $puzzlename = $puzzle->name;
        $styleinsert = "";
        if ($puzzleid == $metapuzzle && $puzzle->status != "Critical") {
            $styleinsert .= " bgcolor='Gainsboro' ";
        }
        if ($puzzlename == $mypuzzle) {
            $styleinsert .= ' style="text-decoration:underline overline wavy" ';
        }
        if ($puzzle->status == "New" && $puzzleid != $metapuzzle) {
            $styleinsert .= " bgcolor='aquamarine' ";
        }
        if ($puzzle->status == "Critical") {
            $styleinsert .= " bgcolor='HotPink' ";
        }
        // Not sure what to do here for style for solved/unnecc puzzles
        //if ($puzzle->status == "Solved" || $val->puzzle->status == "Unnecessary") {
        //    $styleinsert .= ' style="text-decoration:line-through" ';
        //}
        echo '<tr ' . $styleinsert . '>';
        echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '&assumedid=' . $username . '" target="_blank">';
        switch ($puzzle->status) {
            case "New":
                echo $use_text ? '.' : '🆕';
                break;
            case "Being worked":
                echo $use_text ? 'O' : '🙇';
                break;
            case "Needs eyes":
                echo $use_text ? 'E' : '👀';
                break;
            case "WTF":
                echo $use_text ? '?' : '☢️';
                break;
            case "Critical":
                echo $use_text ? '!' : '⚠️';
                break;
            case "Solved":
                echo $use_text ? '*' : '✅';
                break;
            case "Unnecessary":
                echo $use_text ? 'X' : '😶‍🌫️';
                break;
        }
        echo '</a></td>';
        echo '<td><a href="' . $puzzle->puzzle_uri . '" target="_blank">'. $puzzlename . '</a></td>';
        echo '<td><a href="' . $puzzle->drive_uri . '" title="Spreadsheet" target="_blank">'. ($use_text ? 'D' : '🗒️') .'</a></td>';
        echo '<td><a href="' . $puzzle->chat_channel_link  . '" title="Discord" target="_blank">'. ($use_text ? 'C' : '🗣️') .'</a></td>';
        echo '<td style="font-family:monospace;font-style:bold">' . $puzzle->answer .'</td>';
        echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '&assumedid=' . $username . '" target="_blank" title="Edit puzzle in PB">'. ($use_text ? '±' : '⚙️') . '</a></td>';

        echo '</tr>';

    }
    echo '</table>';
    echo '</td>';

}
?>
    </tr>
</table>
<br>

<a href="pbtools.php">Puzzleboss Admin Tools (e.g. add new round)</a>
<br><h3>Legend:</h3>
<table>
    <tr bgcolor="Gainsboro"><td><?= $use_text ? '.' : '🆕' ?></td><td>Meta Puzzle</td></tr>
    <tr bgcolor="aquamarine"><td><?= $use_text ? '.' : '🆕' ?></td><td>Open Puzzle</td></tr>
    <tr bgcolor="HotPink"><td><?= $use_text ? '!' : '⚠️' ?></td><td>Critical Puzzle</td></tr>
    <tr><td><?= $use_text ? 'O' : '🙇' ?></td><td>Puzzle Being Worked On</td></tr>
    <tr><td><?= $use_text ? '*' : '✅' ?></td><td>Solved Puzzle</td></tr>
    <tr><td><?= $use_text ? '?' : '☢️' ?></td><td>WTF Puzzle</td></tr>
    <tr><td><?= $use_text ? 'E' : '👀' ?></td><td>Puzzle Needs Eyes</td></tr>
    <tr><td><?= $use_text ? 'X' : '😶‍🌫️' ?></td><td>Puzzle Not Needed</td></tr>
    <tr style="text-decoration:underline overline wavy;"><td>&nbsp</td><td>My Current Puzzle</td></tr>
</table>
<br>
<br>
<a href="?text_only=1">Text-only (no emoji) mode</a>
</body>
