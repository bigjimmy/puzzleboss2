<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="icon" type="image/x-icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%2210 0 100 100%22><text y=%22.90em%22 font-size=%2290%22>🧩</text></svg>">
  <title>Puzzleboss Accounts</title>
</head>
<body>
<?php
global $apiroot;

// TODO: Load this from the yaml config
$apiroot = "http://localhost:5000";

function readapi($apicall) {
  $url  = $GLOBALS['apiroot'] . $apicall;
  $curl = curl_init($url);
  curl_setopt($curl, CURLOPT_URL, $url);
  curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
  $headers = array(
    "Accept: application/json"
  );
  curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
  $resp = curl_exec($curl);
  curl_close($curl);
  return json_decode($resp);
}

function postapi($apicall, $data) {
  $url  = $GLOBALS['apiroot'] . $apicall;
  $curl = curl_init($url);
  curl_setopt($curl, CURLOPT_URL, $url);
  curl_setopt($curl, CURLOPT_POST, true);
  curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
  $headers = array(
    "Accept: application/json",
    "Content-Type: application/json"
  );
  curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);

  curl_setopt($curl, CURLOPT_POSTFIELDS, json_encode($data));
  $resp = curl_exec($curl);
  curl_close($curl);
  return json_decode($resp);
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  if (array_key_exists("userok", $_POST)) {
    // user says it's ok let's get the code and display it
    $data = array(
      'username' => $_POST['username'],
      'password' => $_POST['password'],
      'fullname' => $_POST['fullname'],
      'email' => $_POST['email'],
      'reset' => $_POST['reset']
    );
    print "<h2>Submitting new user request to puzzleboss...</h2>";
    print "<br>";
    $responseobj = postapi('/account', $data);
    echo '<br>';
    if (!$responseobj) {
      echo 'ERROR: Response from API is: <br><br>' . var_dump($responseobj);
      echo '</body></html>';
      exit(1);
    }
    foreach ($responseobj as $key => $value) {
      if ($key == "status") {
        if ($responseobj->status == "ok") {
          echo 'OK.  Check your email from puzzleboss for further instructions.';
        } else {
          echo 'ERROR: Response from API is ' . var_dump($responseobj);
        }
      }
      if ($key == "error") {
        echo 'ERROR: ' . $value;
      }
    }

    print "</body></html>";
    exit(0);


  } else {
    // no code, but user data. present the page to submit user for verification
    print "<h1>Verify provided information before submitting request</h1>";
    print "<br>";

    if ($_POST['password'] != $_POST['password2']) {
      print "ERROR: Passwords don't match. Try again.";
      print "</body></html>";
      exit(0);
    }

    if (!ctype_alnum($_POST['username'])) {
      print "ERROR: Username has non alphanumeric chars. Try again.";
      print "</body></html>";
      exit(0);
    }

    $fullname = rtrim($_POST['fullname']);

    if (!preg_match('/^[a-zA-Z]+ [a-zA-Z]+$/', $fullname)) {
      print "ERROR: Fullname must be Firstname Lastname, no non-alpha characters. Try again.";
      print "</body></html>";
      exit(0);

    }

    if (!preg_match('/@/', $_POST['email'])) {
      // I'm guessing we can do better email address validation here
      print "ERROR: Valid email address required";
      print "</body></html>";
      exit(0);
    }
    $username = $_POST['username'];
    $email    = $_POST['email'];
    $password = $_POST['password'];
    if (array_key_exists("reset", $_POST)) {
      $reset = $_POST['reset'];
    } else {
      $reset = "false";
    }

    $data = <<<DATA
       <table>
        <tr><td>Username:</td><td>$username</td></tr>
        <tr><td>Fullname:</td><td>$fullname</td></tr>
        <tr><td>Email:</td><td>$email</td></tr>
        </table><br><hr><br>
        Verify the above information.
        If correct, submit account request to the system by pressing the "submit" button.<br>
        Verification code and instructions to finish the process will be sent to<br>
        the email address provided.
        <form action="." method="POST">
        <input type="hidden" name="username" value="$username">
        <input type="hidden" name="fullname" value="$fullname">
        <input type="hidden" name="password" value="$password">
        <input type="hidden" name="email" value="$email">
        <input type="hidden" name="userok" value="yes">
        <input type="hidden" name="reset" value="$reset">
        <input type="submit" name="submit" value="submit">
        </form>
DATA;


    print $data;
    print "</body></html>";
    exit(0);
  }
} else if (isset($_GET['code'])) {
  print "<h2>Verifying.... code " . $_GET['code'] . "</h2>";

  $code = $_GET['code'];

  print "<h2>Submitting new user finalization request to puzzleboss...</h2>";
  print "<br>";
  $responseobj = readapi('/finishaccount/' . $code);
  echo '<br>';
  if (!$responseobj) {
    echo 'ERROR: Response from API is: <br><br>' . var_dump($responseobj);
    echo '</body></html>';
    exit(1);
  }
  foreach ($responseobj as $key => $value) {
    if ($key == "status") {
      if ($responseobj->status == "ok") {
        echo 'OK.  User has been created.  All hunt tools accessible. <br><br>';
        echo "You should now be able to log in at: <a href='../'>Main Hunt Wiki</a><br><br>";
        echo "If you encounter any difficulties, ask in the server-help channel in discord.";
      } else {
        echo 'ERROR: Response from API is ' . var_dump($responseobj);
      }
    }
    if ($key == "error") {
      echo 'ERROR: ' . $value;
    }
  }



  print "</body></html>";
  exit(0);
}

?>
<h1>Puzzleboss 2000 New Account Registration (or password reset)</h1>
<form action="?" method="POST">
<table style="text-align:right;">
  <tr>
    <td><label for="username">Username (alphanumeric only, max 20 chars):</label></td>
    <td><input type="text" id="username" name="username" required /></td>
  </tr>
  <tr>
    <td><label for="fullname">Full Name (alpha only Firstname Lastname):</label></td>
    <td><input type="text" id="fullname" name="fullname" pattern="\w+ \w+" required /></td>
  </tr>
  <tr>
    <td><label for="email">Email (working email address required for verification):</label></td>
    <td><input type="email" id="email" name="email" required /></td>
  </tr>
  <tr>
    <td><label for="password">Password (8-24 chars):</label></td>
    <td>
      <input
        type="password"
        id="password"
        name="password"
        required
        minlength="8"
        maxlength="24"
      />
    </td>
  </tr>
  <tr>
    <td><label for="password2">Password (repeat):</label></td>
    <td>
      <input
        type="password"
        id="password2"
        name="password2"
        required
        minlength="8"
        maxlength="24"
      />
    </td>
  </tr>
  <tr>
    <td><label for="reset">Check box if this is a password reset:</label></td>
    <td><input type="checkbox" id="reset" name="reset" value="reset"></td>
  </tr>
</table>
<input type="submit" name="submit" value="Submit">
</form>
