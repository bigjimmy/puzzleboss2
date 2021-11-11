<html><head>
<meta http-equiv="refresh" content=10>
<title>Puzzleboss Interface</title></head></html>
<body>
<?php 
require('puzzlebosslib.php');

if (isset( $_GET['submit'] ) ) {
    echo "submission not implemented here.<br>";
}
else {
    // Check for authenticated user
    $uid = getauthenticateduser();
    $solverobj = json_decode(readapi('/solvers/' . $uid))->solver;
    $username = $solverobj->name;
    echo "You are: " . $username . "<br>";
           
    $mypuzzle = json_decode(readapi('/solvers/' . $uid . '/puzz'))->solver->puzz;
    $url = "/rounds";
    $resp = readapi($url);
    $rounds = json_decode($resp)->rounds;
    echo '<table border=4 style="vertical-align:top" ><tr>';
    foreach($rounds as $round){
        echo '<th>' . $round->name . "</th>";
    }
    echo '</tr><tr style="vertical-align:top" >';
    foreach($rounds as $round){
        echo '<td>';
        $puzzlesresp = json_decode(readapi("/rounds/" . $round->id . "/puzzles"));
        $metapuzzle = json_decode(readapi("/rounds/" . $round->id . "/meta_id"))->round->meta_id;
        $puzzlearray = $puzzlesresp->round->puzzles;
        
        echo '<table>';
        foreach($puzzlearray as $puzzle) {
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
                    echo ".";
                    break;
                case "Being worked":
                    echo "O";
                    break;
                case "Needs eyes":
                    echo "E";
                    break;
                case "WTF":
                    echo "?";
                    break;
                case "Critical":
                    echo "!";
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
            echo '<td><a href="' . $puzzle->drive_uri . '">D</a></td>';
            echo '<td><a href="' . $puzzle->chat_channel_link  . '">C</a><td>';
            echo '<td style="font-family:monospace;font-style:bold">' . $puzzle->answer .'</td>';
            echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '&assumedid=' . $username . '" target="_blank">+</a></td>';

            echo '</tr>';
        
        }
        echo '</table>';
        echo '</td>';
        
    }
    echo '</tr></table>';
    echo '<br>';
    echo '<a href="pbtools.php">Puzzleboss Admin Tools (e.g. add new round)</a>';
    echo '<br><h3>Legend:</h3>';
    echo '<table>';
    echo "<tr bgcolor='Gainsboro'><td>.</td><td>Meta Puzzle</td></tr>";
    echo "<tr bgcolor='aquamarine'><td>.</td><td>Open Puzzle</td></tr>";
    echo "<tr bgcolor='HotPink'><td>!</td><td>Critical Puzzle</td></tr>";
    echo "<tr><td>O</td><td>Puzzle Being Worked On</td></tr>";
    echo "<tr><td>*</td><td>Solved Puzzle</td></tr>";
    echo "<tr><td>W</td><td>WTF Puzzle</td></tr>";
    echo "<tr><td>U</td><td>Puzzle Not Needed</td></tr>";
    echo '<tr style="text-decoration:underline overline wavy"><td>&nbsp</td><td>My Current Puzzle</td></tr>';
    
    
    
    
    
}

?>
</body>