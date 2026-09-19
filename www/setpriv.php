<?php require_once('puzzlebosslib.php'); // set pb_csrf cookie before any output ?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Set Privilege</title>
  <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="form-page">
<main>
<?php

require_once('puzzlebosslib.php');

// Privilege grants are puzztech-only (same gate as changeconfig.php —
// this page POSTs to the API directly, so it must enforce the priv itself).
$authuid = getauthenticateduser();
if (!checkpriv("puzztech", $authuid)) {
  http_response_code(403);
  exit('Access denied: privilege changes require the puzztech role.');
}

if (isset($_POST['setpriv'])) {
  pb_verify_csrf();
  $name = $_POST['name'];
  $priv = $_POST['priv'];
  $allowed = $_POST['allowed'];

  $name_html = htmlspecialchars($name);
  $priv_html = htmlspecialchars($priv);
  $allowed_html = htmlspecialchars($allowed);

  print <<<HTML
Assigning role $priv_html for:<br>
<table class="registration">
<tr><td>name:</td><td>$name_html</td></tr>
</table>
HTML;

  $uid = getuid($name);
  $apiurl = "/rbac/" . urlencode($priv) . "/" . $uid;
  $data = array('allowed' => $allowed);
  try {
    $responseobj = postapi_internal($apiurl, $data);
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);

  echo '<br><div class="success">';
  echo 'OK. user ' . $name_html . ' is ' . $allowed_html . ' for role ' . $priv_html;
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '</div><br><hr>';
}

?>

</main>

<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
