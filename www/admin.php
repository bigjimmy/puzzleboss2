<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzztech-only Tools</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
</head>
<body class="status-page">

<?php
require('puzzlebosslib.php');

$uid = getauthenticateduser();
$allowed = checkpriv("puzztech", $uid);

if (!$allowed) {
?>
<div class="status-header">
  <h1>ACCESS DENIED</h1>
</div>
<?= render_navbar() ?>
<p>Access to this page is restricted to users with the <strong>puzztech</strong> role. Contact puzzleboss or puzztech for assistance.</p>
</body>
</html>
<?php
  exit(2);
}



?>
<div id="app">
<div class="status-header">
  <h1>PuzzTech Super Admin Tools</h1>
</div>

<?= render_navbar('admin') ?>

<div class="info-box">
  <div class="info-box-header">
    <h3><a href="./accounts.php">Accounts Management →</a></h3>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header">
    <h3><a href="./config.php">Configuration →</a></h3>
  </div>
</div>



</div>

<script>
const { createApp } = Vue;

createApp({
  data() {
    return {}
  }
}).mount('#app');
</script>
</body>
</html>
