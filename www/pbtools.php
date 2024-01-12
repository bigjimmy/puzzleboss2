<?php
require('puzzlebosslib.php');

$bookmarkuri = 'javascript:location.href=`' .
  $pbroot.
  '/addpuzzle.php'.
  '?puzzurl=${encodeURIComponent(location.href)}' .
  '&puzzid=${encodeURIComponent(document.title)}`';

?>
<!doctype html>
<html>
<head><title>Puzzleboss-only Tools</title></head>
<body>

<h1>Puzzleboss-only Admin Tools</h1>

<hr>
<h3>New Puzzle Bookmarklet</h3>
<table border="2" cellpadding="3">
  <tr>
    <td>For a bookmark for adding a new puzzle (while on a puzzle page), drag this link to your bookmarks:</td>
    <td><a href="<?= $bookmarkuri ?>">Puzzleboss New Puzzle</a></td>
  </tr>
  <tr>
    <td>Or alternatively, copy the following into a new bookmark:</td>
    <td><code><?= $bookmarkuri ?></code></td>
  </tr>
</table>
<br>

<hr>
<h3>Solver Assignment</h3><br>
<table border="2" cellpadding="3">
  <tr>
    <td>To manually edit a solver's current puzzle assignment (enter username):</td>
    <td valign="middle">
      <form action="editsolver.php" method="get">
        <input type="text" name="assumedid">
        <input type="submit" name="ok" value="Edit Solver">
      </form>
    </td>
  </tr>
</table>

<hr>
<h3>Add New Round</h3><br>
<table border="2" cellpadding="3">
  <tr>
    <td>To add a new round (enter round name):</td>
    <td valign="middle">
      <form action="addround.php" method="get">
        <input type="text" name="name">
        <input type="submit" name="submit" value="Add Round">
      </form>
    </td>
  </tr>
</table>

</body>
</html>
