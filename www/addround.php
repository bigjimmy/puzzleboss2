<html>
<head><title>Add Round</title></head><body>
<?php

require('puzzlebosslib.php');

if (isset($_GET['submit'])) {
    $name = $_GET['name'];
    
    echo 'Attempting to add round.<br>';
    echo 'name: ' . $name . '<br>';
    
    $apiurl = "/rounds";
    $data = array('name' => $name);
    $resp = postapi($apiurl, $data);
    var_dump($resp);
    die();
}

?>

Add a new round!<br>
<form action="addround.php" method="get">
Name:<input type="text" name="name" /><br>
<input type="submit" name="submit" />
</form>
</body>
</html>
