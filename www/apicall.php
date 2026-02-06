<?php
require('puzzlebosslib.php');
header('Content-Type: application/json');
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Headers: *");
header('Access-Control-Allow-Credentials: true');
header("Access-Control-Allow-Methods: GET, OPTIONS, POST, DELETE");


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

if (!isset($_GET['apiparam2']) || empty($_GET['apiparam2'])) {
  $apiparam2 = '';
}

else {
  $apiparam2 = $_GET['apiparam2'];
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {

  $post = json_decode(file_get_contents('php://input'));

  switch ($apicall) {
    case "solver":
      echo json_encode(postapi(('/solvers/' . $apiparam1 . '/' . $apiparam2), $post));
      break;
    case "puzzle":
      echo json_encode(postapi(('/puzzles/' . $apiparam1 . '/' . $apiparam2), $post));
      break;
    case "round":
      echo json_encode(postapi(('/rounds/' . $apiparam1 . '/' . $apiparam2), $post));
      break;
    case "query":
      echo json_encode(postapi('/v1/query', $post));
      break;
    case "tag":
      echo json_encode(postapi('/tags', $post));
      break;
    default:
      http_response_code(500);
      die('Error: improper apicall specified.');
  }
}
else if ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
  switch ($apicall) {
    case "tag":
      echo json_encode(deleteapi('/tags/' . $apiparam1));
      break;
    default:
      http_response_code(500);
      die('Error: improper apicall specified.');
  }
}
else {
  switch ($apicall) {
    case "all":
      echo json_encode(readapi('/all'));
      break;
    case "huntinfo":
      echo json_encode(readapi('/huntinfo'));
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
    case "round":
      echo json_encode(readapi('/rounds/' . $apiparam1));
      break;
    case "search":
      // Build query string from tag or tag_id params
      $searchParams = [];
      if (isset($_GET['tag']) && !empty($_GET['tag'])) {
        $searchParams[] = 'tag=' . urlencode($_GET['tag']);
      }
      if (isset($_GET['tag_id']) && !empty($_GET['tag_id'])) {
        $searchParams[] = 'tag_id=' . urlencode($_GET['tag_id']);
      }
      $queryString = count($searchParams) > 0 ? '?' . implode('&', $searchParams) : '';
      echo json_encode(readapi('/search' . $queryString));
      break;
    case "tags":
      echo json_encode(readapi('/tags'));
      break;
    case "tag":
      echo json_encode(readapi('/tags/' . $apiparam1));
      break;
    default:
      http_response_code(500);
      die('Error: improper apicall specified.');
  }
}

?>
