<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Add Round</title>
  <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="form-page">
<main>
<?php

require('puzzlebosslib.php');

// Puzzle deletion is puzztech-only (same gate as the apicall.php proxy —
// this page calls the API directly, so it must enforce the priv itself).
$authuid = getauthenticateduser();
if (!checkpriv("puzztech", $authuid)) {
  http_response_code(403);
  exit('Access denied: puzzle deletion requires the puzztech role.');
}

if (isset($_POST['submit'])) {
  pb_verify_csrf();
  $name = $_POST['name'];
  $name_html = htmlspecialchars($name);

  print <<<HTML
Attempting to delete puzzle.<br>
<table class="registration">
<tr><td>name:</td><td>$name_html</td></tr>
</table>
HTML;

  try {
    $resp = deleteapi_internal('/deletepuzzle/' . $name);
  } catch (Exception $e) {
    exit_with_api_error($resp);
    throw $e;
  }
  assert_api_success($resp);
  echo '<div class="success">Puzzle <tt>'.$name_html.'</tt> deletion success!';
  echo '<pre>'.htmlspecialchars(var_export($resp, true)).'</pre></div>';
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '<br><hr>';
}

?>

</main>

<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
