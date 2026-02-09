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

// Operations that require puzztech privilege
$puzztech_required = ['deleteuser', 'googleusers', 'privs'];
$puzztech_required_post = ['rbac', 'config'];

$needs_puzztech = in_array($apicall, $puzztech_required)
    || ($_SERVER['REQUEST_METHOD'] === 'POST' && in_array($apicall, $puzztech_required_post));

if ($needs_puzztech) {
    $uid = getauthenticateduser();
    if (!checkpriv("puzztech", $uid)) {
        http_response_code(403);
        die(json_encode(['error' => 'Insufficient privileges']));
    }
}

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
    case "rbac":
      echo json_encode(postapi('/rbac/' . $apiparam1 . '/' . $apiparam2, $post));
      break;
    case "tag":
      echo json_encode(postapi('/tags', $post));
      break;
    case "config":
      echo json_encode(postapi('/config', $post));
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
    case "deletepuzzle":
      echo json_encode(deleteapi('/deletepuzzle/' . $apiparam1));
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
    case "rounds":
      echo json_encode(readapi('/rounds'));
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
    case "createpuzzle":
      // Handle stepwise puzzle creation: /createpuzzle/<code>?step=N
      $queryParams = [];
      if (isset($_GET['step']) && !empty($_GET['step'])) {
        $queryParams[] = 'step=' . urlencode($_GET['step']);
      }
      $queryString = count($queryParams) > 0 ? '?' . implode('&', $queryParams) : '';
      echo json_encode(readapi('/createpuzzle/' . $apiparam1 . $queryString));
      break;
    case "rbac":
      // Check privilege: /rbac/<priv>/<uid>
      echo json_encode(readapi('/rbac/' . $apiparam1 . '/' . $apiparam2));
      break;
    case "deleteuser":
      echo json_encode(readapi('/deleteuser/' . $apiparam1));
      break;
    case "privs":
      echo json_encode(readapi('/privs'));
      break;
    case "googleusers":
      echo json_encode(readapi('/google/users'));
      break;
    case "config":
      echo json_encode(readapi('/config'));
      break;
    default:
      http_response_code(500);
      die('Error: improper apicall specified.');
  }
}

?>
