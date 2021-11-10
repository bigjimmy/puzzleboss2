<html>
<head><title>Change Solver</title></head><body>
<?php

require('puzzlebosslib.php');

if (isset( $_GET['submit'] ) ) {
    
    if (!isset($_GET['id'])){
        echo 'ERROR: No Authenticated User ID Found in Request';
        echo '</body></html>';
        exit (2);
    }
    if ($_GET['id'] == ""){
        echo 'ERROR: No Authenticated User ID Found in Request';
        echo '</body></html>';
        exit (2);
    }
    
    $id = $_GET['id'];
    $puzz = $_GET['puzz'];
    if ($puzz == '_none_') $puzz = '';
    
    echo 'Attempting to set puzz for solver.<br>';
    echo 'solver_id: ' . $id . '<br>';
    echo 'puzz: ' . $puzz . '<br>';
    
    
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
        if ($key == "status") {
            if ($responseobj -> status == "ok") {
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
else {
        
    $url = "/solvers";
    $resp = readapi($url);
    
    $solvers = json_decode($resp)->solvers;
    $id = "";
    $username = "";
    
    // Check for authenticated user
    if (!isset($_SERVER['REMOTE_USER'])) {
        if ($noremoteusertestmode == 'true') {
            $username = "testuser";
        }
        if (isset($_GET['assumedid'])) {
            $username = $_GET['assumedid'];
        }
        if ($username == ""){
            echo '<br>authenticated REMOTE_USER not provided<br>';
            echo '</body></html>';
            exit (2);
        }
    }
    else {
        $username = $_SERVER['REMOTE_USER'];
    }
    $id = getuid($username);
    
    if ($id==0) {
        echo '<br>No solver found for user ' . $username . '. Check Solvers Database<br>';
        echo '</body></html>';
        exit (2);
        
    }
    
    echo "changing solver settings for username: " . $username . " user-id: " . $id . "<br>";
    echo "What puzzle is this user working on?<br>";
    
    $url = "/rounds";
    $resp = readapi($url);
    $rounds = json_decode($resp)->rounds;
    echo '<form action="editsolver.php" method="get">';
    echo '<table border=4 style="vertical-align:top" ><tr>';
    foreach($rounds as $round){
        echo '<th>' . $round->name . "</th>";
    }
    echo '</tr><tr style="vertical-align:top" >';
    foreach($rounds as $round){
        echo '<td>';
        $puzzlesresp = json_decode(readapi("/rounds/" . $round->id . "/puzzles"));
        $puzzlearray = explode(',',$puzzlesresp->round->puzzles);
        
        echo '<table>';
        foreach($puzzlearray as $puzzleid) {
            if ($puzzleid !="") {
                $val = json_decode(readapi("/puzzles/" . $puzzleid . "/name"));
                $puzzlename = $val->puzzle->name;
                echo '<tr><td><input type="radio" id="' . $puzzleid . '" name="puzz" value="' . $puzzleid . '"></td>';
                echo '<td>' . $puzzlename . '</td></tr>';
            }
        }
        echo '</table>';
        echo '</td>';
            
    }
    echo '</tr></table>';
    echo '<br><input type="radio" id="_none_" name="puzz" value="_none_">';
    echo '<label for="_none_">Not working on any puzzle</label><br>';
    echo '<input type = "hidden" name="id" value="' . $id . '">';
    echo '<input type = "submit" name="submit" />';
    echo '</form>';
    
    
    
}


?>
</body>
</html>
