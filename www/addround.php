<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Add Round</title>
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
  </style>
</head>
<body>
<main>
<?php

require('puzzlebosslib.php');

if (isset($_POST['submit'])) {
  $name = $_POST['name'];

  print <<<HTML
Attempting to add round.<br>
<table class="registration">
<tr><td>name:</td><td>$name</td></tr>
</table>
HTML;
  echo 'name: ' . $name . '<br>';

  $apiurl = "/rounds";
  $data = array('name' => $name);
  try {
    $resp = postapi($apiurl, $data);
  } catch (Exception $e) {
    exit_with_api_error($e);
    throw $e;
  }
  assert_api_success($resp);
  echo '<div class="success"><pre>'.var_dump($resp).'</pre></div>';
  echo '<a href="javascript:window.history.back();">Go back</a>';
  echo '<br><hr>';
}

?>

<h3>Add New Round</h3>
<table border="2" cellpadding="3">
  <tr>
    <td>To add a new round (enter round name):</td>
    <td valign="middle">
      <form action="addround.php" method="post">
        <input type="text" name="name">
        <input type="submit" name="submit" value="Add Round">
      </form>
    </td>
  </tr>
</table>
</body>
</html>
