<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Config Updated</title>
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
  .info-box {
    background-color: #e7f3ff;
    border: 2px solid #0066cc;
    border-radius: 6px;
    color: #004080;
    padding: 15px;
    margin: 20px 0;
  }
  .info-box h3 {
    margin-top: 0;
    color: #0066cc;
  }
  </style>
</head>
<body>
<main>
<?php

require('puzzlebosslib.php');

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
  echo 'OK. config ' . $key . ' is now set to: ' . $configval;
  echo '</div>';
  echo '<div class="info-box">';
  echo '<h3>ℹ️ Automatic Config Refresh</h3>';
  echo '<p>Configuration changes take effect automatically within <strong>30 seconds</strong> across all API workers and the BigJimmyBot. No manual refresh or restart is required.</p>';
  echo '</div>';
  echo '<br>';
  echo '<a href="admin.php">Back to Admin</a>';
  echo '<br><hr>';

?>

</main>

<footer><br><hr><br><a href="index.php">Puzzleboss Home</a></footer>
</body>
</html>
