<?php
require('puzzlebosslib.php');

$bookmarkuri = <<<'JAVASCRIPT'
javascript:if(window.location.pathname==='/puzzles'){pbPath=(data => '?'+Object.entries(data.puzzles || {}).map(([roundSlug, puzzles]) => ['r[' + data.rounds[roundSlug].name.replace(/[^A-Za-z0-9]/g,'') + ']', puzzles.filter(({answer}) => !answer).map(({slug, isMeta}) => (isMeta ? '!' : '') + slug).join(',')].join('=')).join('&'))(JSON.parse(document.getElementById('__NEXT_DATA__')?.innerText || '{}')?.props?.pageProps || {});}else{pbPath=(data => `addpuzzle.php?puzzurl=${encodeURIComponent(location.href.split('#')[0])}&puzzid=${encodeURIComponent(data?.name || document.title.replace(/ - Google Docs$/, ''))}&roundname=${encodeURIComponent(data?.round?.name?.replace(/[^A-Za-z0-9]+/g, ''))}`)(JSON.parse(document.querySelector('#__NEXT_DATA__')?.innerText || '{}')?.props?.pageProps?.puzzleData);}window.open('<<<PBROOTURI>>>'+pbPath);
JAVASCRIPT;
$bookmarkuri = trim(str_replace('<<<PBROOTURI>>>', $pbroot, $bookmarkuri));

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Puzzleboss-only Tools</title>
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
<h1>Puzzleboss-only Admin Tools</h1>

<hr>
<h3>New Puzzle / Check for Puzzles Bookmarklet</h3>
A major timesaver for Puzzlebosses, this bookmarklet works in two ways:
<ul>
  <li>On a puzzle page, click it to create a new puzzle</li>
  <li>On the List of Puzzles page (<tt>/puzzles</tt>), click it to check if PB is missing anything.</li>
</ul>
<table border="2" cellpadding="3">
  <tr>
    <td>Drag this link to your bookmarks:</td>
    <td><a href="<?= $bookmarkuri ?>">Puzzleboss New/Check Puzzles</a></td>
  </tr>
  <tr>
    <td>Or alternatively, copy the following into a new bookmark:</td>
    <td><pre style="text-size: 40%;"><?= $bookmarkuri ?></pre></td>
  </tr>
</table>
<br>

<hr>
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
<br>

<hr>
<h3>Add New Puzzle</h3>
<form action="addpuzzle.php" method="post">
  <table>
    <tr>
      <td><label for="name">Name:</label></td>
      <td>
        <input
          type="text"
          id="name"
          name="name"
          required
          size="40"
        />
      </td>
    </tr>
    <tr>
      <td><label for="round_id">Round:</label></td>
      <td>
        <select id="round_id" name="round_id"/>
<?php
$rounds = readapi("/rounds")->rounds;
$rounds = array_reverse($rounds); // Newer rounds first in the dropdown
foreach ($rounds as $round) {
  echo "<option value=\"{$round->id}\">{$round->name}</option>\n";
}
?>
        </select>
      </td>
    </tr>
    <tr>
      <td><label for="puzzle_uri">Puzzle URI:</label></td>
      <td>
        <input
          type="text"
          id="puzzle_uri"
          name="puzzle_uri"
          required
          size="80"
        />
      </td>
    </tr>
  </table>
  <input type="submit" name="submit" value="Add New Puzzle"/>
</form>
<br>

<hr>
<h3>Solver Assignment</h3>
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

</main>
<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
