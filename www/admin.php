<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzztech-only Tools</title>
  <link rel="stylesheet" href="./pb-ui.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
  <style>
  /* Align column widths for form tables */
  #app .info-box-content table td:first-child {
    width: 40%;
    white-space: normal;
  }

  #app .info-box-content table td:not(:first-child) {
    width: auto;
  }

  /* Table styling matching status.php */
  #app table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #ddd;
  }

  #app th, #app td {
    padding: 8px 10px;
    text-align: left;
    border-bottom: 1px solid #ddd;
    font-size: 0.9em;
  }

  #app th {
    background: #e6f2ff;
    color: #0066cc;
    font-weight: 600;
  }

  #app tbody tr:hover {
    background: #f5f5f5;
  }
  </style>
</head>
<body class="status-page">

<?php
// Permissions check
require('puzzlebosslib.php');

// Get authenticated username (with test mode support)
$username = "";
if (!isset($_SERVER['REMOTE_USER'])) {
  // Test mode fallback (only if REMOTE_USER not set)
  if ($noremoteusertestmode == 'true') {
    $username = "testuser";
  }
  if (isset($_GET['assumedid'])) {
    $username = $_GET['assumedid'];
  }
  if ($username == "") {
    echo '<br>authenticated REMOTE_USER not provided<br>';
    echo '</body></html>';
    exit(2);
  }
} else {
  // Production: use Apache-provided REMOTE_USER
  $username = $_SERVER['REMOTE_USER'];
}

$uid = getuid($username);
$allowed = checkpriv("puzztech", $uid); //puzztech only!

if (!$allowed) {
  echo "<h1>ACCESS DENIED</h1>";
  echo "<br><hr><br>Access to this page is restricted to users with the puzztech role. Contact puzzleboss or puzztech for assistance.</body>";
  echo "</html>";
  exit (2);
}



?>
<div id="app">
<div class="status-header">
  <h1>PuzzTech Super Admin Tools</h1>
</div>

<?= render_navbar('admin') ?>

<div class="info-box">
  <div class="info-box-header" @click="showDeletePuzzle = !showDeletePuzzle">
    <span class="collapse-icon" :class="{ collapsed: !showDeletePuzzle }">▼</span>
    <h3>Delete Puzzle</h3>
  </div>
  <div class="info-box-content" v-show="showDeletePuzzle">
    <p>
      <strong>BE CAREFUL:</strong><br>
      Deleting a puzzle will delete all record of it from the puzzleboss database.
      It will also move the puzzle's google sheet to the sheets trash folder.
      It will NOT delete the discord chat room. Do that in discord (or find a puzztech who can) if it's necessary.
    </p>
    <table>
      <tr>
        <td>To delete a puzzle (enter puzzle name):</td>
        <td>
          <form action="deletepuzzle.php" method="post">
            <input type="text" name="name">
            <input type="submit" name="submit" value="Delete Puzzle">
          </form>
        </td>
      </tr>
    </table>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showCheckPrivileges = !showCheckPrivileges">
    <span class="collapse-icon" :class="{ collapsed: !showCheckPrivileges }">▼</span>
    <h3>Check Privileges</h3>
  </div>
  <div class="info-box-content" v-show="showCheckPrivileges">
    <table>
      <tr>
        <td>To check if a user has a specific privilege:</td>
        <td>
          Enter Username:
          <form action="checkpriv.php" method="post" style="display:inline;">
            <input type="text" name="name">
            <input type="hidden" name="priv" value="puzztech">
            <input type="submit" name="check" value="Check Puzztech Priv">
          </form>
        </td>
        <td>
          Enter Username:
          <form action="checkpriv.php" method="post" style="display:inline;">
            <input type="text" name="name">
            <input type="hidden" name="priv" value="puzzleboss">
            <input type="submit" name="check" value="Check Puzzleboss Priv">
          </form>
        </td>
      </tr>
    </table>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showSetPrivileges = !showSetPrivileges">
    <span class="collapse-icon" :class="{ collapsed: !showSetPrivileges }">▼</span>
    <h3>Set Privileges</h3>
  </div>
  <div class="info-box-content" v-show="showSetPrivileges">
    <table>
      <tr>
        <td>To modify a role for a user:</td>
        <td>
          Enter Username:<br>
          <form action="setpriv.php" method="post" style="display:inline;">
            <input type="text" name="name"><br>
            <input type="hidden" name="priv" value="puzztech">
            <input type="radio" name="allowed" id="YES_puzztech" value="YES">
            <label for="YES_puzztech">YES</label>
            <input type="radio" name="allowed" id="NO_puzztech" value="NO">
            <label for="NO_puzztech">NO</label>
            <input type="submit" name="setpriv" value="Set Puzztech Priv">
          </form>
        </td>
        <td>
          Enter Username:<br>
          <form action="setpriv.php" method="post" style="display:inline;">
            <input type="text" name="name"><br>
            <input type="hidden" name="priv" value="puzzleboss">
            <input type="radio" name="allowed" id="YES_puzzleboss" value="YES">
            <label for="YES_puzzleboss">YES</label>
            <input type="radio" name="allowed" id="NO_puzzleboss" value="NO">
            <label for="NO_puzzleboss">NO</label>
            <input type="submit" name="setpriv" value="Set Puzzleboss Priv">
          </form>
        </td>
      </tr>
    </table>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showAddConfig = !showAddConfig">
    <span class="collapse-icon" :class="{ collapsed: !showAddConfig }">▼</span>
    <h3>Add Config Variable</h3>
  </div>
  <div class="info-box-content" v-show="showAddConfig">
    <form id="newconfig" action='changeconfig.php' method='post'>
    <table>
    <thead>
    <tr><th>New Config Key</th><th>New Config Value</th><th></th></tr>
    </thead>
    <tbody>
    <tr><td><input type="text" name="key"></td>
    <td><textarea name='configval' cols='40' rows='10' form="newconfig"></textarea></td>
    <td><input type="submit" name="changeconfig" value='Set New Config Entry'></td></tr>
    </tbody>
    </table>
    </form>
  </div>
</div>

<div class="info-box">
  <div class="info-box-header" @click="showConfigEdit = !showConfigEdit">
    <span class="collapse-icon" :class="{ collapsed: !showConfigEdit }">▼</span>
    <h3>Config Edit</h3>
  </div>
  <div class="info-box-content" v-show="showConfigEdit">
    <p><strong>BE CAREFUL:</strong><br>
    Changes to these configuration values are not reversible and may cause irreparable damage or breakage to the hunt if set improperly. Please proceed with caution. Set only one at a time.
    </p>
    <p style="background-color: #e7f3ff; border: 2px solid #0066cc; border-radius: 6px; color: #004080; padding: 15px;">
    <strong>ℹ️ Automatic Config Refresh:</strong> Configuration changes take effect automatically within <strong>30 seconds</strong> across all API workers and the BigJimmyBot. No manual refresh or restart is required.
    </p>
    <table>
    <thead>
    <tr><th>Config Variable</th><th>Current Value</th><th>Desired Value</th></tr>
    </thead>
    <tbody>
    <?php
    foreach ($config as $key => $value){
      echo "<tr><td>".$key."</td>";
      echo "<td style='background-color: #f0f0f0;'><code>".$value."</code></td>";
      echo "<td><form id='".$key."' action='changeconfig.php' method='post' style='display:inline;'>";
      echo "<textarea name='configval' cols='40' rows='10' form='".$key."'></textarea>";
      echo "<input type='hidden' name='key' value='".$key."'>";
      echo "<input type='submit' name='changeconfig' value='Set Value'>";
      echo "</form></td></tr>";
    }
    ?>
    </tbody>
    </table>
  </div>
</div>

</div>

<script>
const { createApp } = Vue;

createApp({
  data() {
    return {
      showDeletePuzzle: true,
      showCheckPrivileges: true,
      showSetPrivileges: true,
      showAddConfig: true,
      showConfigEdit: true
    }
  }
}).mount('#app');
</script>
</body>
</html>
