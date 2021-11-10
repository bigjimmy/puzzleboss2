<html>
<head><title>Add Round</title></head><body>
<?php

require('puzzlebosslib.php');

$name = "";

if (isset( $_GET['submit'] ) ) {
    $name = $_GET['name'];
    
    echo 'Attempting to add round.<br>';
    echo 'name: ' . $name . '<br>';
    
    $apiurl = "/rounds";
    $data = <<<DATA
{
  "name": "$name"
}
DATA;
    $resp = postapi($apiurl, $data);
    var_dump($resp);
    
}

else {
    echo 'Add a new round!<br>';
    echo '<form action="addround.php" method="get">';
    echo 'Name:<input type = "text" name="name" /><br>';
    echo '<input type = "submit" name="submit" />';
    echo '</form>';
}

?>
</body>
</html>