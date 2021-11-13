<html>
<head>

<title>Redirect to puzzle doc</title>
<?php

require('puzzlebosslib.php');

$name = "";
$puzzleid = "";
if (isset( $_GET['pname'] ) ) {
    $name = $_GET['pname'];
    $apiurl = "/puzzles";
    $resp = readapi($apiurl);
    if (!$resp){
        echo '</head>';
        echo '<body><br>Error: api fetch of puzzle catalog failed!</br>';
        echo '</body></html>';
        exit (2);
    }
    foreach (json_decode($resp)->puzzles as $puzzle) {
        if ($puzzle->name == $name)
            $puzzleid = $puzzle->id;
    }
    if ($puzzleid == "") {
        echo '</head>';
        echo '<body><br>Error: api search for puzzle in catalog failed!</br>';
        echo '</body></html>';
        exit (2);
    }
    $drive_uri = json_decode(readapi("/puzzles/" . $puzzleid . "/drive_uri"))->puzzle->drive_uri;
    echo '<meta http-equiv="refresh" content="0;URL=' . $drive_uri . '">';
}

else {
    echo '</head><body><br>Error: No puzzlename parameter (pname) specified.<br>';
    echo '</body></html>';
    exit (2);
}
echo "</head><body><br>Redirecting to doc sheet for puzzle" . $name . " id " . $puzzleid . "<br>";
?>
</body>
</html>