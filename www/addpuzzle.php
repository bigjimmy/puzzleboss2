<html>
<head><title>Add Puzzle</title></head><body>
<?php

require('puzzlebosslib.php');

if (isset($_GET['submit'])) {
    $name = $_GET['name'];
    $round_id = $_GET['round_id'];
    $puzzle_uri = $_GET['puzzle_uri'];
    
    echo 'Attempting to add puzzle.<br>';
    echo "name: $name<br>";
    echo "round_id: $round_id<br>";
    echo "puzzle_uri: $puzzle_uri<br>";
    
    
    $apiurl = "/puzzles";
    $data = array(
        'name' => $name,
        'round_id' => $round_id,
        'puzzle_uri' => $puzzle_uri,
    );
    
    echo "<br> Submitting API request to add puzzle.  May take a few seconds.<br>";
    $responseobj = postapi($apiurl, $data);
    
    echo '<br>';
    if (is_string($responseobj)){
        echo 'ERROR: Response from API is ' . var_dump($responseobj);
        echo '</body></html>';
        die();
    }
    foreach($responseobj as $key => $value){
        if ($key == "status") {
            if ($responseobj->status == "ok") {
                echo 'OK.  Puzzle created with ID of ' . $responseobj->puzzle->id;
            }
            else {
                echo 'ERROR: Response from API is ' . var_dump($responseobj);
            }
        }
        if ($key == "error") {
            echo 'ERROR: ' . $value; 
        }
    }
    die();
}

$puzzurl = "";
$puzzid = "";
if (isset($_GET['puzzurl'])) {
    $puzzurl = $_GET['puzzurl'];
}
if (isset($_GET['puzzid'])) {
    $puzzid = $_GET['puzzid'];
    $puzzid = str_replace(' | MIT Mystery Hunt 2022', '', $puzzid);
}
$round_name = isset($_GET['roundname']) ? $_GET['roundname'] : '';

$rounds = readapi("/rounds")->rounds;
$rounds = array_reverse($rounds); // Newer rounds first in the dropdown
?>

<h1>Add a puzzle!</h1>
<form action="addpuzzle.php" method="get">
    <table>
        <tr>
            <td><label for="name">Name:</label></td>
            <td>
                <input
                    type="text"
                    id="name"
                    name="name"
                    required
                    value="<?= $puzzid ?>"
                    size="40"
                />
            </td>
        </tr>
        <tr>
            <td><label for="round_id">Round:</label></td>
            <td>
                <select id="round_id" name="round_id"/>
<?php
foreach ($rounds as $round) {
    $selected = $round->name === $round_name ? 'selected' : '';
    echo "<option value=\"{$round->id}\" $selected>{$round->name}</option>\n";
}
?>
                </select>
            </td>
        </tr>
        <tr>
            <td><label for="puzzle_uri">Puzzle URI:</label></td>
            <td>
                <input
                    type="text"
                    id="puzzle_uri"
                    name="puzzle_uri"
                    required
                    value="<?= $puzzurl ?>"
                    size="80"
                />
            </td>
        </tr>
    </table>
    <input type="submit" name="submit" value="Add New Puzzle"/>
</form>
</body>
</html>
