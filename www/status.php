<html><head>
<meta http-equiv="refresh" content=30>
<title>Hunt Status</title></head></html>
<body><h1>Hunt Status Overview</h1>
<?php 
require('puzzlebosslib.php');

$rounds = readapi('/rounds')->rounds;
$totrounds = 0;
$solvedrounds = 0;
$unsolvedrounds = 0;
$totpuzz = 0;
$solvedpuzz = 0;
$unsolvedpuzz = 0;
$newcnt = 0;
$workcnt = 0;
$wtfcnt = 0;
$eyescnt = 0;
$critcnt = 0;
$critarray = [];
$eyesarray = [];
$newarray = [];
$workonarray = [];
$nolocarray = [];

$huntstruct = readapi("/all");
$rounds = $huntstruct->rounds;

foreach($rounds as $round){
    $totrounds += 1;
    $metapuzzle = $round->meta_id;
    $puzzlearray = $round->puzzles;
    
    // Is round solved?
    if (isset($metapuzzle)){
        $metapuzzlestatus = readapi("/puzzles/" . $metapuzzle)->puzzle->status;
        if ($metapuzzlestatus == "Solved"){
            $solvedrounds += 1;
        } else {
            $unsolvedrounds += 1;
        }
    } else {
        $unsolvedrounds += 1;
    }
    
    // Count puzzles
    foreach ($puzzlearray as $puzzle){
        $totpuzz += 1;
        switch ($puzzle->status){
            case "New":
                $newcnt += 1;
                array_push($newarray, $puzzle);
                break;
            case "Being worked":
                $workcnt += 1;
                break;
            case "WTF":
                $wtfcnt += 1;
                break;
            case "Needs eyes":
                $eyescnt += 1;
                array_push($eyesarray, $puzzle);
                break;
            case "Critical":
                $critcnt += 1;
                array_push($critarray, $puzzle);
                break;
            case "Solved":
                $solvedpuzz += 1;
        }
    }
}

$unsolvedpuzz = $totpuzz - $solvedpuzz;

echo '<table border=3>';
echo '<tr><td></td><th scope="col">Opened</th><th scope="col">Solved</th><th scope="col">Unsolved</th></tr>';
echo '<tr><th scope="row">Rounds</th><td>' . $totrounds . '</td><td>' . $solvedrounds . '</td><td>' . $unsolvedrounds . '</td></tr>';
echo '<tr><th scope="row">Puzzles</th><td>' . $totpuzz . '</td><td>' . $solvedpuzz . '</td><td>' . $unsolvedpuzz . '</td></tr>';
echo '</table><br><br>';

echo '<table border=3>';
echo '<tr><th>Status</th><th>Open Puzzle Count</th></tr>';
echo '<tr><td>New</td><td>' . $newcnt . '</td></tr>';
echo '<tr><td>Being worked</td><td>' . $workcnt . '</td></tr>';
echo '<tr><td>WTF</td><td>' . $wtfcnt . '</td></tr>';
echo '<tr><td>Needs Eyes</td><td>' . $eyescnt . '</td></tr>';
echo '<tr><td>Critical</td><td>' . $critcnt . '</td></tr>';
echo '</table><br><br>';

echo '<table border=3>';
echo '<tr><th colspan=4>Unsolved Puzzles Missing Location</th></tr>';
foreach($rounds as $round) {
    $puzzlearray = $round->puzzles;
    foreach($puzzlearray as $thispuzzle) {
	if (is_null($thispuzzle->xyzloc)) { 
	    if ($thispuzzle->status != "Solved") { 
	        array_push($nolocarray, $thispuzzle);
	    }
	 }
    }
}

foreach($nolocarray as $puzzle){
    $puzzleid = $puzzle->id;
    $puzzlename = $puzzle->name;
    $styleinsert = "";
    if ($puzzleid == $metapuzzle && $puzzle->status != "Critical") {
        $styleinsert .= " bgcolor='Gainsboro' ";
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
        echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '" target="_blank">';
        switch ($puzzle->status) {
            case "New":
                echo "New";
                break;
            case "Being worked":
                echo "O";
                break;
            case "Needs eyes":
                echo "Eyes";
                break;
            case "WTF":
                echo "?";
                break;
            case "Critical":
                echo "Crit";
                break;
            case "Solved":
                echo "*";
		break;
            case "Unnecessary":
                echo "X";
                break;
        }
        echo '</a></td>';
        echo '<td><a href="' . $puzzle->puzzle_uri . '">'. $puzzlename . '</a></td>';
        echo '<td><a href="' . $puzzle->drive_uri . '">Doc</a></td>';
        echo '<td><a href="' . $puzzle->chat_channel_link  . '">Chat</a></td>';

        echo '</tr>';

}
echo '</table><br><br>';
echo '<table border=3>';

echo '<tr><th>Good Puzzles To Work On:</th></tr><tr><td>';

$workonarray = array_merge($critarray, $eyesarray, $newarray);
echo '<table>';
foreach($workonarray as $puzzle) {
    $puzzleid = $puzzle->id;
    $puzzlename = $puzzle->name;
    $styleinsert = "";
    if ($puzzleid == $metapuzzle && $puzzle->status != "Critical") {
        $styleinsert .= " bgcolor='Gainsboro' ";
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
        echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '" target="_blank">';
        switch ($puzzle->status) {
            case "New":
                echo "New";
                break;
            case "Being worked":
                echo "O";
                break;
            case "Needs eyes":
                echo "Eyes";
                break;
            case "WTF":
                echo "?";
                break;
            case "Critical":
                echo "Crit";
                break;
            case "Solved":
                echo "*";
                break;
            case "Unnecessary":
                echo "X";
                break;
        }
        echo '</a></td>';
        echo '<td><a href="' . $puzzle->puzzle_uri . '">'. $puzzlename . '</a></td>';
        echo '<td><a href="' . $puzzle->drive_uri . '">Doc</a></td>';
        echo '<td><a href="' . $puzzle->chat_channel_link  . '">Chat</a></td>';
        
        echo '</tr>';
        
}
echo '</table></td></tr></table>';


?>
</body>
