<?php
// Streams one hunt CSV archive from the API to the browser.
//
// Not routed through apicall.php because that always answers as JSON. Same
// contract as the *api_internal helpers: puzztech is checked HERE, then the
// internal token is attached, because the token authenticates this server
// tier rather than the end user.
//
// Only the two CSV archives are reachable. The SQL dumps beside them in S3
// carry SERVICE_ACCOUNT_JSON and the rest of the config table; the API
// allowlists the same two filenames and the ECS task role is scoped to
// *.csv.gz, so this is the outermost of three gates.
require_once('puzzlebosslib.php');

$uid = getauthenticateduser();
if (!checkpriv("puzztech", $uid)) {
    http_response_code(403);
    header('Content-Type: text/plain');
    die("Access to hunt archives is restricted to the puzztech role.\n");
}

$allowed_files = ['puzzle_view.csv', 'activity.csv'];
$timestamp = $_GET['ts'] ?? '';
$file = $_GET['file'] ?? '';

if (!preg_match('/^[A-Za-z0-9_-]{1,64}$/', $timestamp) || !in_array($file, $allowed_files, true)) {
    http_response_code(400);
    header('Content-Type: text/plain');
    die("Invalid archive request.\n");
}

$url = $GLOBALS['apiroot'] . '/backups/' . rawurlencode($timestamp) . '/' . rawurlencode($file);
$curl = curl_init($url);
curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
curl_setopt($curl, CURLOPT_HTTPHEADER, array(
    "X-PB-Internal-Token: " . $GLOBALS['pbinternaltoken'],
    "X-Remote-User: " . ($_SERVER['REMOTE_USER'] ?? ''),
));
$body = curl_exec($curl);
$status = curl_getinfo($curl, CURLINFO_HTTP_CODE);
curl_close($curl);

if ($body === false || $status !== 200) {
    http_response_code($status ?: 502);
    header('Content-Type: text/plain');
    die("Could not retrieve that archive (API status $status).\n");
}

header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="' . $timestamp . '-' . $file . '"');
header('Content-Length: ' . strlen($body));
header('X-Content-Type-Options: nosniff');
echo $body;
