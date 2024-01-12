<?php
global $apiroot;
global $noremoteusertestmode;
global $pbroot;

//TODO: Load this from the yaml config
$pbroot = "https://importanthuntpoll.org/pb/";
$apiroot = "http://localhost:5000";
$phproot = "http://localhost:8080/puzzleboss/www/";
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
    return json_decode($resp);
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
    
    curl_setopt($curl, CURLOPT_POSTFIELDS, json_encode($data));
    $resp = curl_exec($curl);
    curl_close($curl);
    return json_decode($resp);
}

function exit_with_error_message($error) {
  print <<<HTML
    <div class="error">
      <strong>ERROR:</strong>
      &nbsp;$error;&nbsp;
      <a href="javascript:window.history.back();">Try again.</a>
    </div>
  </main></body></html>
HTML;
  exit(0);
}

function exit_with_api_error($obj) {
  exit_with_error_message(
    'Response from API is:<pre>'.var_dump($obj).'</pre>'.
    'Contact @Puzztech on Discord for help.'
  );
}

function assert_api_success($responseobj) {
  if (!$responseobj) {
    exit_with_api_error($responseobj);
  }
  if (is_object($responseobj)) {
    $responseobj = json_decode(json_encode($responseobj), true);
  }
  if (!is_array($responseobj)) {
    exit_with_api_error($responseobj);
  }
  if (array_key_exists('error', $responseobj)) {
    exit_with_api_error($responseobj['error']);
  }
  if (!array_key_exists('status', $responseobj)) {
    exit_with_api_error($responseobj);
  }
  if ($responseobj['status'] !== 'ok') {
    exit_with_api_error($responseobj);
  }
}

function getuid($username) {
    $userlist = readapi('/solvers')->solvers;
    foreach ($userlist as $user) {
        if ($user->name == $username) {
            return $user->id;
        }
    }
    return 0;
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
        http_response_code(403);
        die("No solver found for user $username. Check Solvers Database");
    }
    return $uid;
}
?>
