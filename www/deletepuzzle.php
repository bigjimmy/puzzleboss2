<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Add Round</title>
  <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&amp;family=Open+Sans:wght@400;700&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./pb-ui.css">
</head>
<body class="form-page">
<main>
<?php

require('puzzlebosslib.php');

if (isset($_POST['submit'])) {
  $name = $_POST['name'];

  print <<<HTML
Attempting to delete puzzle.<br>
<table class="registration">
<tr><td>name:</td><td>$name</td></tr>
</table>
HTML;

  try {
    $resp = deleteapi('/deletepuzzle/' . $name);
  } catch (Exception $e) {
    exit_with_api_error($resp);
    throw $e;
  }
  assert_api_success($resp);
  echo '<div class="success">Puzzle <tt>'.$name.'</tt> deletion success!';
  echo '<pre>'.var_export($resp, true).'</pre></div>';
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '<br><hr>';
}

?>

</main>

<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
