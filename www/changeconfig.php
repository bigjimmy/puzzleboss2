<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Config Updated</title>
  <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&amp;family=Open+Sans:wght@400;700&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./pb-ui.css">
  <style>
  /* Page-specific blue info box style */
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
<body class="form-page">
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
