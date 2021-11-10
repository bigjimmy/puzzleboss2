<html><head><title>Edit Puzzle</title>
   <meta http-equiv="cache-control" content="max-age=0" />
   <meta http-equiv="cache-control" content="no-cache" />
   <meta http-equiv="expires" content="0" />
   <meta http-equiv="expires" content="Tue, 01 Jan 1980 1:00:00 GMT" />
   <meta http-equiv="pragma" content="no-cache" />
</head>
<body>
<?php 

require('puzzlebosslib.php');

function startuseronpuzzle($id, $puzz) {
    $api = "/solvers/" . $id . "/puzz";
    $data = <<<DATA
        {
            "puzz": "$puzz"
        }
        DATA;
    
    $resp = postapi($api, $data);
    $responseobj = json_decode($resp);
    echo '<br>';
    foreach($responseobj as $key => $value){
        echo "<br><br>";
        if ($key == "status") {
            if ($value == "ok") {
                echo 'OK.  Solver reassigned.';
            }
            else {
                echo 'ERROR: Response from API is ' . var_dump($resp);
            }
                
        }
        if ($key == "error") {
            echo 'ERROR: ' . $value;
        }
    }
}   

function updatepuzzlepart($id, $part, $value) {
    $api = "/puzzles/" . $id . "/" . $part;
    $data = <<<DATA
        {
            "$part": "$value"
        }
        DATA;
    
    $resp = postapi($api, $data);
    $responseobj = json_decode($resp);
    echo '<br>';
    foreach($responseobj as $key => $value){
        echo "<br><br>";
        if ($key == "status") {
            if ($value == "ok") {
                echo 'OK.  Puzzle Part Updated.';
            }
            else {
                echo 'ERROR: Response from API is ' . var_dump($resp);
            }
            
        }
        if ($key == "error") {
            echo 'ERROR: ' . $value;
        }
    }
}

function updateroundpart($id, $part, $value) {
    $api = "/rounds/" . $id . "/" . $part;
    $data = <<<DATA
        {
            "$part": "$value"
        }
        DATA;
    
    $resp = postapi($api, $data);
    $responseobj = json_decode($resp);
    echo '<br>';
    foreach($responseobj as $key => $value){
        echo "<br><br>";
        if ($key == "status") {
            if ($value == "ok") {
                echo 'OK.  Round Part Updated.';
            }
            else {
                echo 'ERROR: Response from API is ' . var_dump($resp);
            }
            
        }
        if ($key == "error") {
            echo 'ERROR: ' . $value;
        }
    }
}



if (isset( $_GET['submit'] ) ) {
    
    if (!isset($_GET['uid'])){
        echo 'ERROR: No Authenticated User ID Found in Request';
        echo '</body></html>';
        exit (2);
    }
    
    if (!isset($_GET['pid'])){
        echo 'ERROR: No puzz ID Found in Request';
        echo '</body></html>';
        exit (2);
    }
    if ($_GET['pid'] == ""){
        echo 'ERROR: No puzz ID Found in Request';
        echo '</body></html>';
        exit (2);
    }
    
    $whatdo = "";
    
    if (isset($_GET['startwork'])){
        $whatdo = "startwork";  
    }
    
    if (isset($_GET['stopwork'])){
        $whatdo = "stopwork";
    }
    
    if (isset($_GET['ismeta'])){
        $whatdo = "ismeta";
    }
    
    if (isset($_GET['isnotmeta'])){
        $whatdo = "isnotmeta";
    }
    
    if (isset($_GET['partupdate'])){
        $whatdo = "partupdate";
        if (!isset($_GET['part']) || !isset($_GET['value'])){
            echo 'ERROR: Part name to update, or value to set it to not specified';
            echo '</body></html>';
            exit (2);
        }
    }
    
    $id = $_GET['uid'];  
    $puzz = $_GET['pid'];
    
    echo 'Attempting to change puzz ' . $whatdo . '<br>';
    switch ($whatdo){
        case "startwork":
            startuseronpuzzle($id, $puzz);
            break;
        case "stopwork":
            startuseronpuzzle($id, "");
            break;
        case "ismeta":
            updateroundpart($_GET['rid'], "meta_id", $puzz);
            break;
        case "isnotmeta":
            updateroundpart($_GET['rid'], "meta_id", "NULL");
            break;
        case "partupdate":
            updatepuzzlepart($puzz, $_GET['part'], $_GET['value']);
            break;
    }    
}

    
echo '<hr><br><h1>Per-Puzzle Change Interface</h1><br>';
    
if (!isset($_GET['pid'])) {
    echo '<br>No Puzzle ID provided to script!<br>';
    echo '</body></html>';
    exit (2);
}

$puzzid = $_GET['pid'];
if (!isset($_SERVER['REMOTE_USER'])) {
    //TODO: Remove this auth bypass when on actual apache server
    $username = "benoc";
    
    //echo '<br>No Authenticated User Found!<br>';
    //echo '</body></html>';
    //exit (2);
}
else {
    $username = $_SERVER['REMOTE_USER'];
}

$userid = getuid($username);


$userobj = json_decode(readapi('/solvers/' . $userid));
$puzzleobj = json_decode(readapi('/puzzles/' . $puzzid));
$puzname = $puzzleobj->puzzle->name;
$username = $userobj->solver->name;
echo 'You Are: ' . $username;
echo '<br><br><table border=2><tr>';
echo '<td><b>Puzzle Name</b></td><td>' . $puzname . '</td></tr>';
echo '<td><b>Round</b></td><td>' . $puzzleobj->puzzle->roundname . '</td></tr>';
echo '<td><b>Status</b></td><td>' . $puzzleobj->puzzle->status . '</td></tr>';
echo '<td><b>Answer</b></td><td>' . $puzzleobj->puzzle->answer . '</td></tr>';
echo '<td><b>Location</b></td><td>' . $puzzleobj->puzzle->xyzloc . '</td></tr>';
echo '<td><b>Cur. Solvers</b></td><td>' . $puzzleobj->puzzle->cursolvers . '</td></tr>';
echo '<td><b>All Solvers</b></td><td>' . $puzzleobj->puzzle->solvers . '</td><tr>';
echo '<td><b>Comments</b></td><td>' . $puzzleobj->puzzle->comments . '</td><tr>';
echo '</table>';
$roundobj = json_decode(readapi('/rounds/' . $puzzleobj->puzzle->round_id));

//Solver Assignment
if ($userobj->solver->puzz != $puzname){
    echo '<br>You are not marked as working on this puzzle.  Would you like to be?';
    echo '<form action="editpuzzle.php" method="get">';
    echo '<input type="hidden" name="startwork" value="yes">';
    echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
    echo '<input type="hidden" name="uid" value="' . $userid . '">';
    echo '<input type="submit" name="submit" value="yes">';
    echo '</form>';
} else {
    echo '<br>You are marked as currently working on this puzzle.  Would you like to not be?';
    echo '<form action="editpuzzle.php" method="get">';
    echo '<input type="hidden" name="stopwork" value="yes">';
    echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
    echo '<input type="hidden" name="uid" value="' . $userid . '">';
    echo '<input type="submit" name="submit" value="yes">';  
    echo '</form>';
    
}


echo '<br><table border=2><tr><th>Part</th><th>New Value</th><th></th></tr>';

// Enter answer
echo '<tr>';    
echo '<td>Answer</td><td><form action="editpuzzle.php" method="get">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="answer">';
echo '<input type="text" name="value" value="' . $puzzleobj->puzzle->answer . '"></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

    
// Enter location
echo '<tr>';
echo '<td>Location</td><td><form action="editpuzzle.php" method="get">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="xyzloc">';
echo '<input type="text" name="value" value="' . $puzzleobj->puzzle->xyzloc . '"></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

// Enter Comments
echo '<tr>';
echo '<td>Comments</td><td><form action="editpuzzle.php" method="get">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="comments">';
echo '<input type="text" name="value" value="' . $puzzleobj->puzzle->comments . '"></td>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';

// Change Status
echo '<tr>';
echo '<td>Status</td><td><form action="editpuzzle.php" method="get">';
echo '<input type="hidden" name="partupdate" value="yes">';
echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
echo '<input type="hidden" name="uid" value="' . $userid . '">';
echo '<input type="hidden" name="part" value="status">';
echo '<select id="value" name="value"/>';
echo '<option disabled selected value>-- select --</option>';
echo '<option value="New">New</option>';
echo '<option value="Being worked">Being worked</option>';
echo '<option value="Needs eyes">Needs eyes</option>';
echo '<option value="Critical">Critical</option>';
echo '<option value="WTF">WTF</option>';
echo '<option value="Unnecessary">Unnecessary</option>';
echo '</option>';
echo '<td><input type="submit" name="submit" value="submit"></td>';
echo '</form></td></tr>';


echo '</table>';
//Meta Assignment
if ($roundobj->round->meta_id != $puzzid){
    echo '<br>This is not the meta for round ' . $puzzleobj->puzzle->roundname . '.  Should it be?';
    echo '<form action="editpuzzle.php" method="get">';
    echo '<input type="hidden" name="ismeta" value="yes">';
    echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
    echo '<input type="hidden" name="uid" value="' . $userid . '">';
    echo '<input type="hidden" name="rid" value="' . $puzzleobj->puzzle->round_id . '">';
    echo '<input type="submit" name="submit" value="yes">';
    echo '</form>';
    
} else {
    echo '<br>This is the meta for round ' . $puzzleobj->puzzle->roundname . '. Would you like it to not be?';
    echo '<form action="editpuzzle.php" method="get">';
    echo '<input type="hidden" name="isnotmeta" value="yes">';
    echo '<input type="hidden" name="pid" value="' . $puzzid . '">';
    echo '<input type="hidden" name="uid" value="' . $userid . '">';
    echo '<input type="hidden" name="rid" value="' . $puzzleobj->puzzle->round_id . '">';
    echo '<input type="submit" name="submit" value="yes">';
    echo '</form>';
}



?>
</body>
</html>