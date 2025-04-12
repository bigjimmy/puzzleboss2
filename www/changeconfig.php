<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Set Privilege</title>
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
  .success {
    background-color: lightgreen;
    padding: 10px;
  }
  .refresh-button {
    margin-top: 20px;
    padding: 10px 20px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
  }
  .refresh-button:hover {
    background-color: #45a049;
  }
  .refresh-prompt {
    font-weight: bold;
    color: black;
    margin-bottom: 10px;
  }
  </style>
</head>
<body>
<main>
<?php

require('puzzlebosslib.php');

  // Handle refresh request first
  if (isset($_POST['refresh'])) {
    try {
      $responseobj = postapi("/config/refresh", array());
      assert_api_success($responseobj);
      echo '<div class="success">Configuration refreshed successfully!</div>';
      echo '<br><br>';
      echo '<a href="javascript:window.history.back();">Go back</a>';
      echo '</div><br><hr>';
      exit;
    } catch (Exception $e) {
      exit_with_api_error($e);
      throw $e;
    }
  }

  // Only execute config change if this is not a refresh request
  $configval = $_POST['configval'];
  $key = $_POST['key'];

  print <<<HTML

Setting config key $key to:<br>
<table class="registration">
<tr><td>$key</td><td>$configval</td></tr>
</table>
HTML;

  $apiurl = "/config";
  $data = array('cfgkey' => $key, 'cfgval' => $configval);
  try {
    $responseobj = postapi($apiurl, $data);
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($responseobj);

  echo '<br><div class="success">';
  echo 'OK. config ' . $key . ' is ' . $configval;
  echo '<br><br>';
  echo '<div class="refresh-prompt">IMPORTANT: Press the button below to refresh the configuration. This is necessary for your change to take effect.</div>';
  echo '<form action="changeconfig.php" method="post">';
  echo '<input type="hidden" name="refresh" value="yes">';
  echo '<input type="submit" class="refresh-button" value="Refresh Configuration">';
  echo '</form>';
  echo '<br><br>';
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '</div><br><hr>';

?>

</main>

<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
