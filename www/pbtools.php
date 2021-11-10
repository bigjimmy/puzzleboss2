<html><head><title>Puzzleboss-only Tools</title></head>
<body>
<?php 

require('puzzlebosslib.php');
echo "<h1>Puzzleboss-only Admin Tools</h1>";

echo "<hr><h3>New Puzzle Bookmarklet</h3>";
$bookmarkuri = "javascript:location.href='". $newpuzzleuri . "?puzzurl=%27+encodeURIComponent(location.href)+%27&puzzid=%27+encodeURIComponent(document.title)";
echo "<table border='2' cellpadding='3'><tr>";    
echo "<td>For a bookmark for adding a new puzzle (while on a puzzle page), drag this link to your bookmarks:</td>";
echo '<td><a href="' . $bookmarkuri . '">Puzzleboss New Puzzle</a></td></tr>';
echo "<tr><td>Or alternatively, copy the following into a new bookmark:</td>";
echo "<td><CODE>" . $bookmarkuri . "</CODE></td></tr>";
echo "</table><br>";

echo "<hr><h3>Solver Assignment</h3><br>";
echo "<table border='2' cellpadding='3'><tr>";
echo "<td>To manually edit a solver's current puzzle assignment (enter username):</td>";
echo '<td valign="middle"><form action="editsolver.php" method="get">';
echo '<input type="text" name="assumedid">';
echo '<input type="submit" name="ok" value="Edit Solver">';
echo '</form></td></tr></table>';

echo "<hr><h3>Add New Round</h3><br>";
echo "<table border='2' cellpadding='3'><tr>";
echo "<td>To add a new round (enter round name):</td>";
echo '<td valign="middle"><form action="addround.php" method="get">';
echo '<input type="text" name="name">';
echo '<input type="submit" name="submit" value="Add Round">';
echo '</form></td></tr></table>';



?>




</body>
</html>