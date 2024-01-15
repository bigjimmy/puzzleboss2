<?php 
require('puzzlebosslib.php');

function get_scrape_data() {
  global $config;
  error_reporting(E_ALL);
  ini_set("display_errors", 1);
  $url = $config->hunt_domain.'/puzzles';
  $curl = curl_init($url);
  curl_setopt($curl, CURLOPT_URL, $url);
  curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
  $session_id = isset($_GET['sessionid'])
    ? $_GET['sessionid']
    : $config->hunt_sessionid;
  $headers = array(
      'accept: text/html',
      'cache-control: max-age=0',
      'cookie: sessionid='.$session_id,
      'user-agent: Puzzleboss v0.1 HuntTeam:'.$config->hunt_team_username,
  );
  curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
  $resp = curl_exec($curl);
  curl_close($curl);
  $resp = strstr($resp, 'id="__NEXT_DATA__"');
  $resp = strstr($resp, '{');
  $resp = strstr($resp, '</script>', true);
  $data = json_decode($resp, true);
  if ($data == null) {
    throw new Exception('No data returned; Hunt site is likely down right now.');
  }
  $data = $data['props']['pageProps'];
  $rounds = idx($data, 'rounds', array());
  $puzzles = idx($data, 'puzzles', array());
  $output = array();
  foreach ($puzzles as $round_slug => $round_puzzles) {
    foreach ($round_puzzles as $puzzle) {
      $output[] = array(
        'slug' => idx($puzzle, 'slug'),
        'name' => idx($puzzle, 'name'),
        'url' => idx($puzzle, 'url'),
        'isMeta' => idx($puzzle, 'isMeta'),
        'answer' => idx($puzzle, 'answer'),
        'round' => array(
          'slug' => $round_slug,
          'name' => idx(idx($rounds, $round_slug), 'name'),
          'url' => idx(idx($rounds, $round_slug), 'url'),
        ),
      );
    }
  }
  return $output;
}

if (isset($_GET['scrape'])) {
  header('Content-Type: application/json; charset=utf-8');
  print json_encode(get_scrape_data());
  die();
}

if (isset($_GET['submit'])) {
  http_response_code(500);
  die('submission not implemented here');
}

// Check for authenticated user
$uid = getauthenticateduser();
$solver = readapi("/solvers/$uid")->solver;
$fullhunt = array_reverse(readapi('/all')->rounds);

if (isset($_GET['data'])) {
  header('Content-Type: application/json; charset=utf-8');
  die(json_encode(array(
    'solver' => $solver,
    'fullhunt' => $fullhunt,
  )));
}

$use_text = isset($_GET['text_only']);

$username = $solver->name;
$mypuzzle = $solver->puzz;

// https://gist.github.com/tott/7684443
function ip_in_range($ip, $range) {
  if (strpos($range, '/') == false) {
    $range .= '/32';
  }
  // $range is in IP/CIDR format eg 127.0.0.1/24
  list($range, $netmask) = explode('/', $range, 2);
  $range_decimal = ip2long($range);
  $ip_decimal = ip2long($ip);
  $wildcard_decimal = pow(2, (32 - $netmask)) - 1;
  $netmask_decimal = ~ $wildcard_decimal;
  return (($ip_decimal & $netmask_decimal) == ($range_decimal & $netmask_decimal));
}

function get_user_network() {
  $ipaddr = $_SERVER['REMOTE_ADDR'];
  // https://kb.mit.edu/confluence/pages/46301207
  if (ip_in_range($ipaddr, '192.54.222.0/24')) {
    return 'MIT GUEST';
  }
  if (ip_in_range($ipaddr, '18.29.0.0/16')) {
    return 'MIT / MIT SECURE';
  }
  // https://kb.mit.edu/confluence/display/istcontrib/Eduroam+IP+address+ranges
  // (Maybe a typo, but just to be sure)
  if (ip_in_range($ipaddr, '18.189.0.0/16')) {
    return 'MIT / MIT SECURE';
  }
  return 'Other';
}
$user_network = get_user_network();
if ($user_network === 'MIT GUEST' || isset($_GET['wifi_debug'])) {
  $wifi_warning = <<<HTML
  <style>
    .error {
      background-color: lightpink;
      font-family: 'Lora';
      margin: 20px;
      max-width: 700px;
      padding: 10px;
    }
  </style>
  <div class="error">
    <strong>WARNING:</strong>&nbsp;
    You are on <tt>MIT GUEST</tt> Wifi right now, which does NOT support
    Discord audio calls and is much slower!
    Please <strong>switch to <tt>MIT</tt> / <tt>MIT SECURE</tt></strong>, by either:
    <ul>
      <li><strong>joining directly</strong>, if you have <a href="https://kb.mit.edu/confluence/display/istcontrib/How+to+connect+to+MIT+SECURE+wireless+on+macOS" target="_blank">an active Kerberos</a>,</li>
      <li><strong>generating a password at <a href="https://wifi.mit.edu/" target="_blank">wifi.mit.edu</a></strong>, if you have some MIT affiliation (including alumni), then joining the <tt>MIT</tt> network, or</li>
      <li>connecting directly to the <strong><tt>{$config->wifi_network}</tt></strong> network with the WiFi password <strong><tt>{$config->wifi_password}</tt></strong> in the HQ room ({$config->hq_room}) (non-MIT folks use this one).</li>
    </ul>
    Again, <strong>you will have a harder time participating in Hunt</strong> on this WiFi network! Continue at your own peril. <a href="https://importanthuntpoll.org/wiki/index.php/WiFi" target="_blank">See here for more info.</a>
  </div>
HTML;
} else {
  $wifi_warning = '';
}

function print_rounds_table($rounds) {
  global $use_text, $username, $mypuzzle;
  echo '<table border=4 style="vertical-align:top;" class="rounds"><tr>';
  foreach ($rounds as $round) {
    $num_open = 0;
    $num_solved = 0;
    foreach ($round->puzzles as $puzzle) {
      if ($puzzle->status == '[hidden]') {
        continue;
      }
      $num_open++;
      if ($puzzle->status == 'Solved') {
        $num_solved++;
      }
    }
    $round_title = sprintf(
      '%s <span class="round-stats">(%d solved / %d open)</span>',
      $round->name,
      $num_solved,
      $num_open,
    );
    echo $round->meta_id
      ? sprintf('<th title="Meta unlocked!">🏅 %s</th>', $round_title)
      : sprintf('<th>%s</th>', $round_title);
  }
  echo '</tr><tr>';
  $min_hint_time = time() - 6 * 3600;
  foreach ($rounds as $round) {
    echo '<td>';
    $puzzlearray = $round->puzzles;
    $metapuzzle = $round->meta_id;

    echo '<table>';
    foreach ($puzzlearray as $puzzle) {
      if ($puzzle->status == '[hidden]') {
        continue;
      }
      $puzzleid = $puzzle->id;
      $puzzlename = $puzzle->name;
      $styleinsert = "";
      if ($puzzleid == $metapuzzle && $puzzle->status != "Critical") {
        $styleinsert .= " bgcolor='Gainsboro' ";
      }
      if ($puzzlename == $mypuzzle) {
        $styleinsert .= ' style="text-decoration:underline overline wavy" ';
      }
      if ($puzzle->status == "New" && $puzzleid != $metapuzzle) {
        $styleinsert .= " bgcolor='aquamarine' ";
      }
      if ($puzzle->status == "Critical") {
        $styleinsert .= " bgcolor='HotPink' ";
      }
      // Not sure what to do here for style for solved/unnecc puzzles
      //if ($puzzle->status == "Solved" || $val->puzzle->status == "Unnecessary") {
      //  $styleinsert .= ' style="text-decoration:line-through" ';
      //}
      echo '<tr ' . $styleinsert . '>';
      echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '&assumedid=' . $username . '" target="_blank">';
      switch ($puzzle->status) {
        case "New":
          echo $use_text ? '.' : '🆕';
          break;
        case "Being worked":
          echo $use_text ? 'O' : '🙇';
          break;
        case "Needs eyes":
          echo $use_text ? 'E' : '👀';
          break;
        case "WTF":
          echo $use_text ? '?' : '☢️';
          break;
        case "Critical":
          echo $use_text ? '!' : '⚠️';
          break;
        case "Solved":
          echo $use_text ? '*' : '✅';
          break;
        case "Unnecessary":
          echo $use_text ? 'X' : '😶‍🌫️';
          break;
      }
      echo '</a></td>';
      echo '<td><a href="' . $puzzle->puzzle_uri . '" target="_blank">'. $puzzlename . '</a>';
      if (
        $puzzle->status != 'Solved' &&
        is_numeric($puzzle->chat_channel_id)
      ) {
        $channel_id = (int)($puzzle->chat_channel_id);
        // Discord IDs are effectively time records in the Discord epoch.
        // Convert min hint time to the min snowflake so we can check
        // which puzzle Discord channels were created long enough ago.
        $channel_create_time = round($channel_id >> 22 / 1000) + 1420070400;
        if ($channel_create_time <= $min_hint_time) {
          echo sprintf(
            '&nbsp;<a href="%s" target="_blank" title="Hints available!">%s</a>',
            str_replace('/puzzles/', '/hints/', $puzzle->puzzle_uri ?? ''),
            $use_text ? 'HINT?' : '🙉',
          );
        } else {
          $min_left = round(($channel_create_time - $min_hint_time) / 60);
          echo sprintf(
            '&nbsp;<span title="Hints in %d minute%s">%s</span>',
            str_replace('/puzzles/', '/hints/', $puzzle->puzzle_uri ?? ''),
            $use_text ? '!hint' : '⏳',
            $min_left,
            $min_left !== 1 ? 's' : '',
          );
        }
      }
      echo '</td>';
      echo '<td><a href="' . $puzzle->drive_uri . '" title="Spreadsheet" target="_blank">'. ($use_text ? 'D' : '🗒️') .'</a></td>';
      echo '<td><a href="' . $puzzle->chat_channel_link  . '" title="Discord" target="_blank">'. ($use_text ? 'C' : '🗣️') .'</a></td>';
      echo '<td style="font-family:monospace;font-style:bold">' . $puzzle->answer .'</td>';
      echo '<td><a href="editpuzzle.php?pid=' . $puzzle->id . '&assumedid=' . $username . '" target="_blank" title="Edit puzzle in PB">'. ($use_text ? '±' : '⚙️') . '</a></td>';

      echo '</tr>';

    }
    echo '</table>';
    echo '</td>';
  }
  echo '</tr></table>';
}

?>
<html>
<head>
  <meta http-equiv="refresh" content=30>
  <title>Puzzleboss Interface</title>
  <link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&amp;family=Open+Sans:wght@400;700&amp;display=swap" rel="stylesheet">
  <style>
  body {
    background-color: aliceblue;
  }
  .error {
    background-color: lightpink;
    padding: 10px;
  }
  .success {
    background-color: lightgreen;
    padding: 10px;
  }
  table.rounds span.round-stats {
    font-weight: normal;
    font-size: 70%;
  }
  </style>
</head>
<body>
<?php

$comparison = array();
if (isset($_GET['r']) && is_array($_GET['r'])) {
  foreach ($_GET['r'] as $round_name => $round_data) {
    $round_data = explode(',', $round_data);
    foreach ($round_data as $slug) {
      if ($slug == '') {
        continue;
      }
      $is_meta = $slug[0] == '!';
      $slug = ltrim($slug, '!');
      $comparison[strtolower(str_replace('-', '', $slug))] = array(
        // TODO: Fix for 2025. `head-` is also a year-specific hack
        'url' => $config->hunt_domain.'/puzzles/'.
          preg_replace('/head-(\d+)$/', 'head/\1', $slug),
        'slug' => $slug,
        // Can't pass through bookmarklet
        'name' => null,
        'round' => $round_name,
        'is_meta' => $is_meta,
        // Can't pass through bookmarklet
        'answer' => null,
      );
    }
  }
} else if (isset($_GET['compare'])) {
  try {
    $scrape = get_scrape_data();
    foreach ($scrape as $puzzle) {
      $comparison[strtolower(str_replace('-', '', $puzzle['slug']))] = array(
        'url' => $puzzle['url'],
        'slug' => $puzzle['slug'],
        'name' => sanitize_string($puzzle['name']),
        'round' => sanitize_string($puzzle['round']['name']),
        'is_meta' => $puzzle['isMeta'],
        'answer' => $puzzle['answer'],
      );
    }
  } catch (Exception $e) {
    echo sprintf(
      '<div class="error"><strong>ERROR:</strong>&nbsp;%s<pre>%s</pre></div>',
      $e->getMessage(),
      var_export($e, true),
    );
    $comparison = array();
  }
}

if (count($comparison) > 0) {
  $discrepancies = array();
  foreach ($fullhunt as $round) {
    if ($round->name == 'Events') {
      continue;
    }
    foreach ($round->puzzles as $puzzle) {
      if ($puzzle->status == '[hidden]') {
        continue;
      }
      $slug = strtolower($puzzle->name);
      $prefix = sprintf(
        'Puzzle <a href="%s">%s</a>:',
        $puzzle->puzzle_uri,
        $puzzle->name,
      );
      if (!array_key_exists($slug, $comparison)) {
        $found_puzzle = false;
        foreach ($comparison as $slug2 => $official_puzzle) {
          if (str_ends_with($puzzle->puzzle_uri ?? '', $official_puzzle['url'])) {
            $found_puzzle = true;
            $slug = $slug2;
            break;
          }
        }
        if (!$found_puzzle) {
          // Not worth bothering if extra puzzles
          // $discrepancies[] = sprintf(
          //   '%s Could not find by URL exactly from the /puzzles page',
          //   $prefix,
          // );
          continue;
        }
      }
      $official_puzzle = $comparison[$slug];
      if ($official_puzzle['round'] != $round->name) {
        $discrepancies[] = sprintf(
          '%s Round mismatch, <tt>%s</tt> (MH) vs. <tt>%s</tt> (PB)',
          $prefix,
          $official_puzzle['round'] ?? '<null>',
          $round->name ?? '<null>',
        );
      }
      if ($official_puzzle['is_meta'] && $round->meta_id == null) {
        $discrepancies[] = sprintf(
          '%s needs to be <a href="editpuzzle.php?pid=%s&ismeta=1">marked as a meta!</a>',
          $prefix,
          $puzzle->id,
        );
      }
      if (!$official_puzzle['is_meta'] && $round->meta_id == $puzzle->id) {
        $discrepancies[] = sprintf(
          '%s needs to be <a href="editpuzzle.php?pid=%s&ismeta=0">unmarked as a meta!</a>',
          $prefix,
          $puzzle->id,
        );
      }
      if ($official_puzzle['answer'] != null) {
        if (
          strtolower(preg_replace('/[^A-Z0-9]/', '', $official_puzzle['answer'] ?? '')) !=
          strtolower(preg_replace('/[^A-Z0-9]/', '', $puzzle->answer ?? ''))
        ) {
          $discrepancies[] = sprintf(
            '%s is <a href="editpuzzle.php?pid=%s&answer=%s">solved with answer <tt>%s</tt>!</a>',
            $prefix,
            $puzzle->id,
            urlencode($official_puzzle['answer']),
            $official_puzzle['answer'],
          );
        }
      }
      unset($comparison[$slug]);
    }
  }
  // Iterate over leftover puzzles
  foreach ($comparison as $official_puzzle) {
    $discrepancies[] = sprintf(
      '[MISSING] Puzzle <a href="%s">%s</a> not found in PB! %s',
      $official_puzzle['url'],
      $official_puzzle['name'] ?? $official_puzzle['slug'],
      $official_puzzle['name'] != null
        ? sprintf(
            '<a href="addpuzzle.php?puzzurl=%s&puzzid=%s&roundname=%s">Add it to round %s</a>.',
            urlencode($official_puzzle['url']),
            urlencode($official_puzzle['name']),
            urlencode($official_puzzle['round']),
            $official_puzzle['round'],
          )
        : 'Go to its page and re-use the bookmarklet to add it.',
    );
  }
  if (count($discrepancies) === 0) {
    echo '<div class="success">No discrepancies found! PB is up to date.</div>';
  } else {
    echo '<div class="error"><h3>Discrepancies between Puzzleboss and Mystery Hunt:</h3><ul>';
    foreach ($discrepancies as $discrepancy) {
      echo "<li>$discrepancy</li>";
    }
    echo '</ul></div>';
  }
}
?>
<?= $wifi_warning ?>
You are: <?= $username ?><br>
<a href="status.php">Hunt Status Overview / Puzzle Suggester</a><br>
<?php
$unsolved_rounds = array();
$solved_rounds = array();
foreach ($fullhunt as $round) {
  $round_uri = $round->round_uri;
  if (is_string($round_uri) && str_ends_with($round_uri, '#solved')) {
    $solved_rounds[] = $round;
  } else {
    $unsolved_rounds[] = $round;
  }
}
print_rounds_table($unsolved_rounds);

if (count($solved_rounds) > 0) {
  echo '<details><summary>Show solved rounds:</summary>';
  print_rounds_table($solved_rounds);
  echo '</details>';
}
?>
<br>
<a href="pbtools.php">Puzzleboss Admin Tools (e.g. add new round)</a>
<br><h3>Legend:</h3>
<table>
  <tr bgcolor="Gainsboro"><td><?= $use_text ? '.' : '🆕' ?></td><td>Meta Puzzle</td></tr>
  <tr bgcolor="aquamarine"><td><?= $use_text ? '.' : '🆕' ?></td><td>Open Puzzle</td></tr>
  <tr bgcolor="HotPink"><td><?= $use_text ? '!' : '⚠️' ?></td><td>Critical Puzzle</td></tr>
  <tr><td><?= $use_text ? 'O' : '🙇' ?></td><td>Puzzle Being Worked On</td></tr>
  <tr><td><?= $use_text ? '*' : '✅' ?></td><td>Solved Puzzle</td></tr>
  <tr><td><?= $use_text ? '?' : '☢️' ?></td><td>WTF Puzzle</td></tr>
  <tr><td><?= $use_text ? 'E' : '👀' ?></td><td>Puzzle Needs Eyes</td></tr>
  <tr><td><?= $use_text ? 'X' : '😶‍🌫️' ?></td><td>Puzzle Not Needed</td></tr>
  <tr style="text-decoration:underline overline wavy;"><td>&nbsp</td><td>My Current Puzzle</td></tr>
</table>
<br>
<br>
<a href="?text_only=1">Text-only (no emoji) mode</a>
</body>
