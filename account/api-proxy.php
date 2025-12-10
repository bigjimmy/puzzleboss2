<?php
// Simple proxy for finishaccount API calls
// Avoids CORS issues by making server-side requests

header('Content-Type: application/json');

$yaml = yaml_parse_file('../puzzleboss.yaml');
$apiroot = $yaml['API']['APIURI'];

if (!isset($_GET['code']) || empty($_GET['code'])) {
    http_response_code(400);
    die(json_encode(['error' => 'Missing code parameter']));
}

$code = $_GET['code'];
$step = isset($_GET['step']) ? $_GET['step'] : '';

$url = $apiroot . '/finishaccount/' . urlencode($code);
if (!empty($step)) {
    $url .= '?step=' . urlencode($step);
}

$curl = curl_init($url);
curl_setopt($curl, CURLOPT_URL, $url);
curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
curl_setopt($curl, CURLOPT_HTTPHEADER, ['Accept: application/json']);
$resp = curl_exec($curl);
$httpcode = curl_getinfo($curl, CURLINFO_HTTP_CODE);
curl_close($curl);

http_response_code($httpcode);
echo $resp;
?>

