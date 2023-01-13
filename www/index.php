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
    )));
}

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
                echo "🆕";
                break;
            case "Being worked":
                echo "🙇";
                break;
            case "Needs eyes":
                echo "👀";
                break;
            case "WTF":
                echo "☢️";
                break;
            case "Critical":
                echo "⚠️";
                break;
            case "Solved":
                echo "✅";
                break;
            case "Unnecessary":
                echo "😶‍🌫️";
                break;
        }
        echo '</a></td>';
        echo '<td><a href="' . $puzzle->puzzle_uri . '">'. $puzzlename . '</a></td>';
        echo '<td><a href="' . $puzzle->drive_uri . '" title="Spreadsheet">🗒️</a></td>';
        echo '<td><a href="' . $puzzle->chat_channel_link  . '" title="Discord">🗣️</a></td>';
        echo '<td style="font-family:monospace;font-style:bold">' . $puzzle->answer .'</td>';
        echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '&assumedid=' . $username . '" target="_blank" title="Edit puzzle in PB">⚙️</a></td>';

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
    <tr bgcolor='Gainsboro'><td>🆕</td><td>Meta Puzzle</td></tr>
    <tr bgcolor='aquamarine'><td>🆕</td><td>Open Puzzle</td></tr>
    <tr bgcolor='HotPink'><td>⚠️</td><td>Critical Puzzle</td></tr>
    <tr><td>🙇</td><td>Puzzle Being Worked On</td></tr>
    <tr><td>✅</td><td>Solved Puzzle</td></tr>
    <tr><td>☢️</td><td>WTF Puzzle</td></tr>
    <tr><td>👀</td><td>Puzzle Needs Eyes</td></tr>
    <tr><td>😶‍🌫️</td><td>Puzzle Not Needed</td></tr>
    <tr style="text-decoration:underline overline wavy;"><td>&nbsp</td><td>My Current Puzzle</td></tr>
</table>
</body>
