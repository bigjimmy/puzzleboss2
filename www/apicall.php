<?php
require('puzzlebosslib.php');
header('Content-Type: application/json');

if (!isset($_GET['apicall']) || empty($_GET['apicall'])) {
    http_response_code(500);
    die('Error: No apicall param specified.');
}

$apicall = $_GET['apicall'];

if (!isset($_GET['apiparam1']) || empty($_GET['apiparam1'])) {
  $apiparam1 = '';
}

else {
  $apiparam1 = $_GET['apiparam1'];
}

switch ($apicall) {
  case "all":
    echo json_encode(readapi('/all'));
    break;
  case "solver":
    echo json_encode(readapi('/solvers/' . $apiparam1));
    break;
  case "solvers":
    echo json_encode(readapi('/solvers'));
    break;
  case "puzzle":
    echo json_encode(readapi('/puzzles/' . $apiparam1));
    break;
  default:
    http_response_code(500);
    die('Error: improper apicall specified.');
}

http_response_code(200);
exit(0);

?>
