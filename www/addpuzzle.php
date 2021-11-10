<html>
<head><title>Add Puzzle</title></head><body>
<?php

require('puzzlebosslib.php');

$name = "";

if (isset( $_GET['submit'] ) ) {
    $name = $_GET['name'];
    $round_id = $_GET['round_id'];
    $puzzle_uri = $_GET['puzzle_uri'];
    
    echo 'Attempting to add puzzle.<br>';
    echo 'name: ' . $name . '<br>';
    echo 'round_id: ' . $round_id . '<br>';
    echo 'puzzle_uri: ' . $puzzle_uri . '<br>';
    
    
    $apiurl = "/puzzles";
    $data = <<<DATA
{
  "name": "$name",
  "round_id": "$round_id",
  "puzzle_uri": "$puzzle_uri"
}
DATA;
    
    $resp = postapi($apiurl, $data);
    $responseobj = json_decode($resp);
    
    echo '<br>';
    if (is_string($responseobj)){
        echo 'ERROR: Response from API is ' . var_dump($resp);
        echo '</body></html>';
    }
    foreach($responseobj as $key => $value){
        if ($key == "status") {
            if ($responseobj -> status == "ok") {
                echo 'OK.  Puzzle created with ID of ' . $responseobj->puzzle->id;
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
    
    $puzzurl = "";
    $puzzid = "";
    if (isset( $_GET['puzzurl'])) {
        $puzzurl = $_GET['puzzurl'];
    }
    if (isset( $_GET['puzzid'])) {
        $puzzid = $_GET['puzzid'];
    }
        
    $resp = readapi("/rounds");
    $rounds = json_decode($resp)->rounds;
    echo 'Add a puzzle!';
    echo '<form action="addpuzzle.php" method="get">';
    
    echo 'Name:<input type = "text" name="name" required value="' . $puzzid . '" /><br>';
    
    echo 'Round:<select id="round_id" name="round_id"/>';
    foreach($rounds as $round){
        echo '<option value="' . $round->id . '">' . $round->name . '</option>';
    }
    echo '</select><br>';
    
    echo 'Puzzle URI:<input type = "text" name="puzzle_uri" required value="' . $puzzurl . '" /><br>';
    
    echo '<input type = "submit" name="submit" />';
    echo '</form>';
}

?>
</body>
</html>