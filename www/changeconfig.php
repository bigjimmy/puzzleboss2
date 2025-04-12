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
  echo 'OK. config ' . $key . ' is ' . $configval;
  echo '<br><br>';
  echo '<button class="refresh-button" onclick="refreshConfig()">Refresh Configuration</button>';
  echo '<br><br>';
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '</div><br><hr>';

?>

<script>
function refreshConfig() {
    fetch('<?php echo $apiroot; ?>/config/refresh', {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            alert('Configuration refreshed successfully!');
        } else {
            alert('Error refreshing configuration: ' + data.message);
        }
    })
    .catch(error => {
        alert('Error refreshing configuration: ' + error);
    });
}
</script>

</main>

<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
