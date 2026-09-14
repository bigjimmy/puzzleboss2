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

// Defense-in-depth: apiparam2 only ever becomes a column/field path segment
// (e.g. /puzzles/<id>/<part>). The API enforces its own allowlist; this is
// belt-and-suspenders against path tricks through the proxy.
if ($apiparam2 !== '' && !preg_match('/^[A-Za-z0-9_]{1,64}$/', $apiparam2)) {
    http_response_code(400);
    die(json_encode(['error' => 'Invalid apiparam2']));
}

// Operations that require puzztech privilege
// 'config' is gated for reads too: values are redacted API-side, but config
// enumeration is an admin concern — no solver-facing code reads it via proxy.
$puzztech_required = ['deletepuzzle', 'deleteuser', 'googleusers', 'privs', 'newusers', 'activitysearch', 'config'];
$puzztech_required_post = ['rbac', 'config'];
// Hint queue administration (answer/demote/delete) is puzztech-only.
// Solver-facing hint submission (POST hints, POST hint/<id>/submit) stays open.
$hint_admin_parts = ['answer', 'demote'];

$needs_puzztech = in_array($apicall, $puzztech_required)
    || ($_SERVER['REQUEST_METHOD'] === 'POST' && in_array($apicall, $puzztech_required_post))
    || ($_SERVER['REQUEST_METHOD'] === 'POST' && $apicall === 'hint' && in_array($apiparam2, $hint_admin_parts))
    || ($_SERVER['REQUEST_METHOD'] === 'DELETE' && $apicall === 'hint');

if ($needs_puzztech) {
    $uid = getauthenticateduser();
    if (!checkpriv("puzztech", $uid)) {
        http_response_code(403);
        die(json_encode(['error' => 'Insufficient privileges']));
    }
}

// CSRF double-submit check for every mutating proxy call. Pure reads are
// exempt; everything else must echo the pb_csrf cookie in the X-PB-CSRF
// header (set by puzzlebosslib.php, sent by the JS fetch wrappers).
// 'createpuzzle' is GET for legacy reasons but creates a puzzle, and
// 'deleteuser' (POST-only, below) deletes an account.
$is_mutating = in_array($_SERVER['REQUEST_METHOD'], ['POST', 'DELETE'])
    || $apicall === 'createpuzzle'
    || $apicall === 'deleteuser';
if ($is_mutating) {
    $csrf_cookie = $_COOKIE['pb_csrf'] ?? '';
    $csrf_header = $_SERVER['HTTP_X_PB_CSRF'] ?? '';
    if ($csrf_cookie === '' || $csrf_header === '' || !hash_equals($csrf_cookie, $csrf_header)) {
        http_response_code(403);
        die(json_encode(['error' => 'CSRF check failed: reload the page and try again']));
    }
}

// Echo an API response, or a 502 if the backend is unreachable (readapi and
// friends return null on curl failure — never emit a bare "null" with a 200).
function respond($resp) {
  if ($resp === null || $resp === false) {
    http_response_code(502);
    echo json_encode(['error' => 'backend unavailable']);
    return;
  }
  echo json_encode($resp);
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {

  $post = json_decode(file_get_contents('php://input'));

  switch ($apicall) {
    case "solver":
      respond(postapi(('/solvers/' . $apiparam1 . '/' . $apiparam2), $post));
      break;
    case "puzzle":
      respond(postapi(('/puzzles/' . $apiparam1 . '/' . $apiparam2), $post));
      break;
    case "round":
      respond(postapi(('/rounds/' . $apiparam1 . '/' . $apiparam2), $post));
      break;
    case "query":
      respond(postapi('/v1/query', $post));
      break;
    case "rbac":
      respond(postapi_internal('/rbac/' . $apiparam1 . '/' . $apiparam2, $post));
      break;
    case "tag":
      respond(postapi('/tags', $post));
      break;
    case "config":
      respond(postapi_internal('/config', $post));
      break;
    case "hint":
      respond(postapi(('/hints/' . $apiparam1 . '/' . $apiparam2), $post));
      break;
    case "hints":
      respond(postapi('/hints', $post));
      break;
    case "deleteuser":
      // Destructive: proxied as POST from the browser (never GET), though
      // the server-side call to the API keeps its existing endpoint.
      respond(readapi_internal('/deleteuser/' . $apiparam1));
      break;
    default:
      http_response_code(500);
      die('Error: improper apicall specified.');
  }
}
else if ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
  switch ($apicall) {
    case "tag":
      respond(deleteapi('/tags/' . $apiparam1));
      break;
    case "deletepuzzle":
      respond(deleteapi_internal('/deletepuzzle/' . $apiparam1));
      break;
    case "newusers":
      respond(deleteapi_internal('/newusers/' . $apiparam1));
      break;
    case "hint":
      respond(deleteapi('/hints/' . $apiparam1));
      break;
    default:
      http_response_code(500);
      die('Error: improper apicall specified.');
  }
}
else {
  switch ($apicall) {
    case "all":
      respond(readapi('/all'));
      break;
    case "huntinfo":
      respond(readapi('/huntinfo'));
      break;
    case "solver":
      respond(readapi('/solvers/' . $apiparam1));
      break;
    case "solvers":
      respond(readapi('/solvers'));
      break;
    case "puzzle":
      respond(readapi('/puzzles/' . $apiparam1));
      break;
    case "round":
      respond(readapi('/rounds/' . $apiparam1));
      break;
    case "rounds":
      respond(readapi('/rounds'));
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
      respond(readapi('/search' . $queryString));
      break;
    case "tags":
      respond(readapi('/tags'));
      break;
    case "tag":
      respond(readapi('/tags/' . $apiparam1));
      break;
    case "createpuzzle":
      // Handle stepwise puzzle creation: /createpuzzle/<code>?step=N
      $queryParams = [];
      if (isset($_GET['step']) && !empty($_GET['step'])) {
        $queryParams[] = 'step=' . urlencode($_GET['step']);
      }
      $queryString = count($queryParams) > 0 ? '?' . implode('&', $queryParams) : '';
      respond(readapi('/createpuzzle/' . $apiparam1 . $queryString));
      break;
    case "rbac":
      // Check privilege: /rbac/<priv>/<uid>
      respond(readapi('/rbac/' . $apiparam1 . '/' . $apiparam2));
      break;
    case "deleteuser":
      // Destructive actions are not accepted over GET.
      http_response_code(405);
      die(json_encode(['error' => 'deleteuser requires POST']));
    case "privs":
      respond(readapi('/privs'));
      break;
    case "googleusers":
      respond(readapi_internal('/google/users'));
      break;
    case "config":
      respond(readapi('/config'));
      break;
    case "newusers":
      respond(readapi_internal('/newusers'));
      break;
    case "hints":
      respond(readapi('/hints'));
      break;
    case "hintcount":
      respond(readapi('/hints/count'));
      break;
    case "activitysearch":
      $searchParams = [];
      foreach (['types', 'sources', 'solver_id', 'puzzle_id', 'limit'] as $param) {
        if (isset($_GET[$param]) && $_GET[$param] !== '') {
          $searchParams[] = $param . '=' . urlencode($_GET[$param]);
        }
      }
      $queryString = count($searchParams) > 0 ? '?' . implode('&', $searchParams) : '';
      respond(readapi('/activitysearch' . $queryString));
      break;
    default:
      http_response_code(500);
      die('Error: improper apicall specified.');
  }
}

?>
