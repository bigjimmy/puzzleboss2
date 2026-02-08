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

require('puzzlebosslib.php');

if (isset($_POST['setpriv'])) {
  $name = $_POST['name'];
  $priv = $_POST['priv'];
  $allowed = $_POST['allowed'];

  print <<<HTML
Assigning role $priv for:<br>
<table class="registration">
<tr><td>name:</td><td>$name</td></tr>
</table>
HTML;

  $uid = getuid($name);
  $apiurl = "/rbac/" . $priv . "/" . $uid;
  $data = array('allowed' => $allowed);
  try {
    $responseobj = postapi($apiurl, $data);
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);

  echo '<br><div class="success">';
  echo 'OK. user ' . $name . ' is ' . $allowed . ' for role ' . $priv;
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '</div><br><hr>';
}

?>

</main>

<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
