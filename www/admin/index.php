<?php
require('../puzzlebosslib.php');
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzztech-only Tools</title>
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
  </style>
</head>
<body>
<main>
<h1>Puzztech-only Super Admin Tools</h1>

<hr>
<h3>Delete Puzzle</h3>
<p>
BE CAREFUL:<br>
Deleting a puzzle will delete all record of it from the puzzleboss database.
It will also move the puzzle's google sheet to the sheets trash folder.
It will NOT delete the discord chat room. Do that in discord (or find a puzztech who can) if it's necessary.
</p>
<table border="2" cellpadding="3">
  <tr>
    <td>To delete a puzzle (enter puzzle name):</td>
    <td valign="middle">
      <form action="../deletepuzzle.php" method="post">
        <input type="text" name="name">
        <input type="submit" name="submit" value="Delete Puzzle">
      </form>
    </td>
  </tr>
</table>
<br>

<hr>
<h3>Check Privileges</h3>
<table border="2" cellpadding="3">
  <tr>
    <td>To check if a user has a specific privilege:</td>
    <td valign="middle">
      Enter Username:
      <form action="../checkpriv.php" method="post">
	<input type="text" name="name">
        <input type="hidden" name="priv" value="puzztech">
        <input type="submit" name="check" value="Check Puzztech Priv">
      </form>
    <td valign="middle">
      Enter Username:
      <form action="../checkpriv.php" method="post">
        <input type="text" name="name">
        <input type="hidden" name="priv" value="puzzleboss">
        <input type="submit" name="check" value="Check Puzzleboss Priv">
      </form>
  </tr>
</table>

<hr>
<h3>Set Privileges</h3>
<table border="2" cellpadding="3">
  <tr>
    <td>To modify a role for a user:</td>
    <td valign="middle">
      Enter Username:
      <form action="../setpriv.php" method="post">
        <input type="text" name="name">
	<input type="hidden" name="priv" value="puzztech">
	<input type="radio" name="allowed" id="YES" value="YES">
        <label for="YES">YES</label>
	<input type="radio" name="allowed" id="NO" value="NO">
        <label for="NO">NO</label>
        <input type="submit" name="setpriv" value="Set Puzztech Priv">
      </form>
    <td valign="middle">
      Enter Username:
      <form action="../setpriv.php" method="post">
        <input type="text" name="name">
        <input type="hidden" name="priv" value="puzzleboss">
        <input type="radio" name="allowed" id="YES" value="YES">
        <label for="YES">YES</label>
        <input type="radio" name="allowed" id="NO" value="NO">
        <label for="NO">NO</label>
        <input type="submit" name="setpriv" value="Set Puzzleboss Priv">
      </form>
  </tr>
</table>



</main>
<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
