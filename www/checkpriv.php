<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Check Privilege</title>
  <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="form-page">
<main>
<?php

require('puzzlebosslib.php');

if (isset($_POST['check'])) {
  $name = $_POST['name'];
  $priv = $_POST['priv'];

  print <<<HTML
Checking for Privilege.<br>
<table class="registration">
<tr><td>name:</td><td>$name</td></tr>
</table>
HTML;

  $uid = getuid($name);

  $allowed = checkpriv($priv, $uid);
  echo '<div class="success"> Does ' . $name . ' have the role of ' . $priv . '? <br>';
  if ($allowed) {
    echo "Yes. The role is assigned.";
  } else { 
    echo "No. That role is not assigned to that user.";
  }   
  echo '<br>';
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '<br><hr>';
}

?>

</main>

<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
