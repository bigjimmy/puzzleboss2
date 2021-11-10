<?php
global $apiroot;
$apiroot = "http://localhost:5000";

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
?>