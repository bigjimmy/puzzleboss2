<?php
global $apiroot;
global $noremoteusertestmode;
global $pbroot;
global $bookmarkuri;

// Load YAML config first
if (!extension_loaded('yaml')) {
    die("Error: YAML extension not loaded. Please install the PHP YAML extension.");
}

$yaml = yaml_parse_file('../puzzleboss.yaml');
if ($yaml === false) {
    die("Error: Could not parse puzzleboss.yaml file");
}

// Set basic configuration
$apiroot = $yaml['API']['APIURI'] ?? null;
if (!$apiroot) {
    die("Error: APIURI not found in puzzleboss.yaml");
}

$phproot = "http://localhost:8080/puzzleboss/www/";
$noremoteusertestmode = "true"; //TODO: eliminate this

// Now that API root is set, we can read the config
try {
    $config = readapi('/config')->config;
    if (!$config) {
        die("Error: Could not read configuration from API");
    }
} catch (Exception $e) {
    die("Error reading configuration: " . $e->getMessage());
}

$bookmarkuri = $config->bookmarklet_js;
$pbroot = $config->BIN_URI;

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
      &nbsp;$error&nbsp;
      <a href="javascript:window.history.back();">Try again.</a>
    </div>
  </main></body></html>
HTML;
  exit(0);
}

function exit_with_api_error($obj) {
  exit_with_error_message(
    'Response from API is:<pre>'.var_export($obj, true).'</pre>'.
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
  global $config;
  if (!isset($_SERVER['REMOTE_USER'])) {
    if ($noremoteusertestmode == 'true') {
      $username = "testuser";
    }
    if (isset($_GET['assumedid'])) {
      $username = $_GET['assumedid'];
    }
    if ($username == "") {
      echo '<br>authenticated REMOTE_USER not provided<br>';
      echo '</body></html>';
      exit(2);
    }
  }
  else {
    $username = $_SERVER['REMOTE_USER'];
  }
  $uid = getuid($username);
  if ($uid == 0) {
    http_response_code(403);
    die("No solver found for user $username. Check Solvers Database");
  }
  $debugging_usernames = explode(',', $config->debugging_usernames ?? '');
  if (in_array($username, $debugging_usernames)) {
    error_reporting(E_ALL);
    ini_set("display_errors", 1);
  }
  return $uid;
}

// Mirrors pblib.py implementation
// TOOD: Stop doing this
function sanitize_string($str) {
  return preg_replace('/[^A-Za-z0-9]/', '', $str);
}

function idx($container, $key, $default=null) {
  if ($container == null) {
    return $default;
  }
  return isset($container[$key]) ? ($container[$key] ?? $default) : $default;
}

function checkpriv($priv, $uid) {
  try {
    $resp = readapi('/rbac/' . $priv . '/' . $uid);
  } catch (Exception $e) {
    exit_with_api_error($resp);
    throw $e;
  }
  return $resp->allowed;
}

?>
