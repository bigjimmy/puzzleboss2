<?php
require('../puzzlebosslib.php');

$bookmarkuri = <<<'JAVASCRIPT'
javascript:if(window.location.pathname==='/puzzles'){pbPath=(data => '?'+Object.entries(data.puzzles || {}).map(([roundSlug, puzzles]) => ['r[' + data.rounds[roundSlug].name.replace(/[^A-Za-z0-9]/g,'') + ']', puzzles.filter(({answer}) => !answer).map(({slug, isMeta}) => (isMeta ? '!' : '') + slug).join(',')].join('=')).join('&'))(JSON.parse(document.getElementById('__NEXT_DATA__')?.innerText || '{}')?.props?.pageProps || {});}else{pbPath=(data => `addpuzzle.php?puzzurl=${encodeURIComponent(location.href.split('#')[0])}&puzzid=${encodeURIComponent(data?.name || document.title.replace(/ - Google Docs$/, ''))}&roundname=${encodeURIComponent(data?.round?.name?.replace(/[^A-Za-z0-9]+/g, ''))}`)(JSON.parse(document.querySelector('#__NEXT_DATA__')?.innerText || '{}')?.props?.pageProps?.puzzleData);}window.open('<<<PBROOTURI>>>/'+pbPath);
JAVASCRIPT;
$bookmarkuri = trim(str_replace('<<<PBROOTURI>>>', $pbroot, $bookmarkuri));

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

</main>
<footer><br><hr><br><a href="/pb/">Puzzleboss Home</a></footer>
</body>
</html>
