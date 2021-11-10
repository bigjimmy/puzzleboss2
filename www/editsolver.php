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
    $name = "";
    
    if (isset( $_SERVER['REMOTE_USER'])) {
        $name = $_SERVER['REMOTE_USER'];
        foreach($solvers as $solver){
            if ( $solver->name == $name ){
                $id = $solver->id;
            }
        }
        
    }
    else if (isset( $_GET['SECRET_ID'])) {
        $id = $_GET['SECRET_ID'];
        foreach($solvers as $solver){
            if ( $solver->id == $id ){
                $name = $solver->name;
            }
        }
        
    }
    
    echo "changing solver settings for username: " . $name . " id: " . $id . "<br>";
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
