<?php
global $apiroot;
global $noremoteusertestmode;
global $newpuzzleuri;
$apiroot = "http://localhost:5000";
$phproot = "http://localhost:8080/puzzleboss/www/";
$newpuzzleuri = $phproot . "addpuzzle.php";
$noremoteusertestmode = "true"; //set this if we're testing without apache auth in front

function readapi($apicall) {
    $url = $GLOBALS['apiroot'] . $apicall;
    $curl = curl_init($url);
    curl_setopt($curl, CURLOPT_URL, $url);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    $headers = array(
        "Accept: application/json",
    );
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
    $resp = curl_exec($curl);
    curl_close($curl);
    return ($resp);
}

function postapi($apicall, $data) {
    $url = $GLOBALS['apiroot'] . $apicall;
    $curl = curl_init($url);
    curl_setopt($curl, CURLOPT_URL, $url);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    $headers = array(
        "Accept: application/json",
        "Content-Type: application/json",
    );
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
    
    curl_setopt($curl, CURLOPT_POSTFIELDS, $data);
    $resp = curl_exec($curl);
    curl_close($curl);
    return ($resp);
}

function getuid($username) {
    $resp = readapi('/solvers');
    $uid = 0;
    $userlist = json_decode($resp)->solvers;
    foreach ($userlist as $user) {
        if ($user->name == $username) {
            $uid = $user->id;
        }
    }
    return($uid);
}

function getauthenticateduser() {
    $username = "";
    global $noremoteusertestmode;
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
    $uid = getuid($username);
    if ($uid==0) {
        echo '<br>No solver found for user ' . $username . '. Check Solvers Database<br>';
        echo '</body></html>';
        exit (2);
        
    }
    return($uid);
}
?>