<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzzleboss Accounts</title>
  <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&amp;family=Open+Sans:wght@400;700&amp;display=swap" rel="stylesheet">
  <style>
    body {
      background-color: aliceblue;
      display: grid;
      font-family: 'Lora';
      height: 100vh;
      justify-items: center;
      margin: 0;
      width: 100vw;
    }
    h1 {
      line-height: 1em;
    }
    h1 > span {
      font-size: 50%;
    }
    main {
      margin-top: 50px;
      max-width: 700px;
    }
    table.registration {
      text-align: right;
    }
    table.registration tr > td:last-child {
      text-align: left;
      font-size: 80%;
      font-style: italic;
    }
    table.registration tr:last-child {
      text-align: center;
    }
    input[type="submit"] {
      font-family: inherit;
    }
    .error {
      background-color: lightpink;
      padding: 10px;
    }
  </style>
</head>
<body>
<main>
<?php
global $apiroot;

// TODO: Load this from the yaml config
if ($_GET['yaml']) {
  $yaml = yaml_parse_file('../puzzleboss.yaml');
  print json_encode($yaml);
  exit(0);
}
$apiroot = "http://localhost:5000";
$google_domain = 'importanthuntpoll.org';
$example_google_sheet_url = 'https://docs.google.com/spreadsheets/d/1l3Sgk-5XfCEMs4SKCn4uRfx5xagNbx1L-QvsQFSuhDU/edit';

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
  if (array_key_exists('error', $responseobj)) {
    exit_with_api_error($responseobj->error);
  }
  if (!array_key_exists('status', $responseobj)) {
    exit_with_api_error($responseobj);
  }
  if ($responseobj->status !== 'ok') {
    exit_with_api_error($responseobj);
  }
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $username = $_POST['username'];
  $fullname = rtrim($_POST['fullname']);
  $email    = $_POST['email'];
  $password = $_POST['password'];
  if (array_key_exists("reset", $_POST)) {
    $reset = $_POST['reset'];
  } else {
    $reset = "false";
  }
  $request_type = $reset === 'false' ? 'account creation' : 'password reset';

  // Run validation
  if (!ctype_alnum($username)) {
    exit_with_error_message("Username has non alphanumeric chars");
  }
  if (!preg_match('/^[a-zA-Z]+ [a-zA-Z]+$/', $fullname)) {
    exit_with_error_message(
      "Fullname must be <tt>Firstname Lastname</tt>, no non-alpha characters",
    );
  }
  if (!preg_match('/@/', $email)) {
    // I'm guessing we can do better email address validation here
    exit_with_error_message("Valid email address required");
  }
  // End validation

  if (!array_key_exists("userok", $_POST)) {
    if ($password != $_POST['password2']) {
      exit_with_error_message("Passwords don't match");
    }
    // no code, but user data. present the page to submit user for verification
    print <<<HTML
      <h1>Confirm $request_type details</h1>
      <table>
        <tr><td>Username:</td><td><tt>$username</tt></td></tr>
        <tr><td>Full Name:</td><td><tt>$fullname</tt></td></tr>
        <tr><td>Email:</td><td><tt>$email</tt></td></tr>
      </table>
      <br><hr>
      <form action="." method="POST">
        <input type="hidden" name="username" value="$username">
        <input type="hidden" name="fullname" value="$fullname">
        <input type="hidden" name="password" value="$password">
        <input type="hidden" name="email" value="$email">
        <input type="hidden" name="userok" value="yes">
        <input type="hidden" name="reset" value="$reset">
        <p>
          If the above information looks correct, click here:&nbsp;
          <input type="submit" name="submit" value="Confirm"><br>
          We'll send you a confirmation code to the email you provided.
        </p>
        <p>
          Need to change something?
          <a href="javascript:window.history.back();">Go back</a> to try again.
        </p>
      </form>
      </main></body></html>
HTML;
    exit(0);
  }

  // user says it's ok let's get the code and display it
  print "<h1>Running...</h1>"
  try {
    $responseobj = postapi(
      '/account',
      array(
        'username' => $username,
        'password' => $password,
        'fullname' => $fullname,
        'email' => $email,
        'reset' => $reset
      )
    );
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);
  print <<<HTML
  <h2>Request for $request_type submitted!</h2>
  <p>
    Check your email ($email) for further instructions from $regemail.<br>
    (Also check your spam folder; sometimes the email ends up there.)
  </p>
  </main></body></html>
HTML;
  exit(0);
}

if (isset($_GET['code'])) {
  print "<h2>Verifying.... code " . $_GET['code'] . "</h2>";

  $code = $_GET['code'];

  try {
    $responseobj = readapi('/finishaccount/' . $code);
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);
  print <<<HTML
  <h2>Account creation successful!</h2>
  <p>
    Your account on Puzzleboss has been created/updated.
    All our hunt tools should now accessible.
  </p>
  <p>Please confirm that's the case by:</p>
  <ol>
    <li>Logging into our <a href="/" target="_blank">Team Wiki</a> with the username/password you just made</li>
    <li>
      Loading
      <a href="$example_google_sheet_url" target="_blank">this test Google Spreadsheet</a>.
      <ul>
        <li>
          Use <tt>YOUR_USERNAME@$google_domain</tt> and your $google_domain password to log into Google.
        </li>
        <li>
          (Consider creating
          <a href="https://support.google.com/chrome/answer/2364824" target="_blank">a new Chrome profile</a>
          for Mystery Hunt; it also helps quarantine your wild Hunt search history.)
        </li>
      </ul>
    </li>
    <li>
      Returning to our Discord and ping @RoleVerifier with your username
      so we can connect your Puzzleboss and Discord accounts.
    </li>
  </ol>
  <p>
  If you hit any other issues, ping @Puzztech in the Discord.<br>
  Thanks, and get excited to Hunt!
  </p>
  </main></body></html>
HTML;
  exit(0);
}

?>
<h1>
  Puzzleboss 2000 New Account Registration<br>
  <span>(or password reset)</span>
</h1>
<p>
  Welcome aboard! <em>Puzzleboss</em> is our team's puzzlesolving infrastructure:
  it helps us track which puzzles we have open, create spreadsheets for each of them,
  and know who's working on what. <strong>You'll need an account to hunt with us.</strong>
</p>
<p>
  If you're a new solver, welcome! If you're returning, you only need to use this if you've forgotten your password. (If so, check the password reset box as you fill this out.)
</p>
<form action="?" method="POST">
<table class="registration">
  <tr>
    <td><label for="username">Username (alphanumeric only, max 20 chars):</label></td>
    <td><input type="text" id="username" name="username" pattern="[A-Za-z0-9]+" required /></td>
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
  <tr>
    <td />
    <td><input type="submit" name="submit" value="Submit"></td>
    <td />
  </tr>
</table>
</form>
</main>
</body>
</html>
