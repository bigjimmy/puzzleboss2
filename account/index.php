<html><head>
<title>Puzzleboss Accounts</title></head></html>
<body>

<?php
global $apiroot;

//TODO: Load this from the yaml config
$apiroot = "http://localhost:5000";

function readapi($apicall) {
    $url = $GLOBALS['apiroot'] . $apicall;
    $curl = curl_init($url);
    curl_setopt($curl, CURLOPT_URL, $url);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    $headers = array(
        "Accept: application/json",
    );
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
    $resp = curl_exec($curl);
    curl_close($curl);
    return ($resp);
}

function postapi($apicall, $data) {
    $url = $GLOBALS['apiroot'] . $apicall;
    $curl = curl_init($url);
    curl_setopt($curl, CURLOPT_URL, $url);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    $headers = array(
        "Accept: application/json",
        "Content-Type: application/json",
    );
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
    
    curl_setopt($curl, CURLOPT_POSTFIELDS, $data);
    $resp = curl_exec($curl);
    curl_close($curl);
    return ($resp);
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if ( array_key_exists("userok", $_POST) ) {
    // user says it's ok let's get the code and display it
        $username = $_POST['username'];
        $fullname = $_POST['fullname'];
        $email = $_POST['email'];
        $password = $_POST['password'];
        
        $data = <<<DATA
        {
            "username": "$username",
            "password": "$password",
            "fullname": "$fullname",
            "email": "$email"
        }
DATA;
        print "<h2>Submitting new user request to puzzleboss...</h2>";
        print "<br>";
        $resp =  postapi('/account/', $data);
        $responseobj = json_decode($resp);
        echo '<br>';
        if (!$responseobj){
            echo 'ERROR: Response from API is: <br><br>' . $resp;
            echo '</body></html>';
            exit(1);
        }
        foreach($responseobj as $key => $value){
            if ($key == "status") {
                if ($responseobj -> status == "ok") {
                    echo 'OK.  Check your email from puzzleboss for further instructions.';
                }
                else {
                    echo 'ERROR: Response from API is ' . var_dump($resp);
                }
            }
            if ($key == "error") {
                echo 'ERROR: ' . $value;
            }
        }
        
    
        print "</body></html>";
        exit(0);
    
    
    } else {
    // no code, but user data. present the page to submit user for verification
    print "<br>";
    
    if ($_POST['password'] != $_POST['password2']) {
        print "ERROR: Passwords don't match. Try again.";
        print "</body></html>";
        exit(0);
    }
    
    if (! ctype_alnum($_POST['username'])) {
        print "ERROR: Username has non alphanumeric chars. Try again.";
        print "</body></html>";
        exit(0);
    }

    if (! preg_match('/^[a-zA-Z]+ [a-zA-Z]+$/', $_POST['fullname'])) {
        print "ERROR: Fullname must be Firstname Lastname, no non-alpha characters. Try again.";
        print "</body></html>";
        exit(0);
        
    }
    
    if (! preg_match('/@/', $_POST['email'])) {
    // I'm guessing we can do better email address validation here    
        print "ERROR: Valid email address required";
        print "</body></html>";
        exit(0);
    }
    $username = $_POST['username'];
    $fullname = $_POST['fullname'];
    $email = $_POST['email'];
    $password = $_POST['password'];
    
    $data = <<<DATA
        <table>
        <tr><td>Username:</td><td>$username</td></tr>
        <tr><td>Fullname:</td><td>$fullname</td></tr>
        <tr><td>Email:</td><td>$email</td></tr>
        </table><br><hr><br>
        Verify the above information.  If correct, submit new user request to the system.<br>
        Verification code and instructions to finish creating user will be sent to<br>
        the email address provided.
        <form action = "." method = "POST">
        <input type="hidden" name="username" value="$username">
        <input type="hidden" name="fullname" value="$fullname">
        <input type="hidden" name="password" value="$password">
        <input type="hidden" name="email" value="$email">
        <input type="hidden" name="userok" value="yes">
        <input type="submit" name="submit" value="submit">
        </form>
DATA;
    
    
    print $data;    
    print "</body></html>";
    exit(0);
    }
} else if (isset( $_GET['code'] ) ) {
    print "<h2>Verifying.... code " . $_GET['code'] . "</h2>";

    $code = $_GET['code'];
    $data = <<<DATA
        {
            "code": "$code",
        }
DATA;
    
    print "<h2>Submitting new user finalization request to puzzleboss...</h2>";
    print "<br>";
    $resp =  postapi('/finishaccount/', $data);
    $responseobj = json_decode($resp);
    echo '<br>';
    if (!$responseobj){
        echo 'ERROR: Response from API is: <br><br>' . $resp;
        echo '</body></html>';
        exit(1);
    }
    foreach($responseobj as $key => $value){
        if ($key == "status") {
            if ($responseobj -> status == "ok") {
                echo 'OK.  User has been created.  All hunt tools accessible.';
            }
            else {
                echo 'ERROR: Response from API is ' . var_dump($resp);
            }
        }
        if ($key == "error") {
            echo 'ERROR: ' . $value;
        }
    }
    
    
    
    print "</body></html>";
    exit(0);
} 

?>
<form action = "<?php $_PHP_SELF ?>" method = "POST">
	Username (alphanumeric only, max 10 chars): <input type = "text" name = "username" maxlength="10" required size="15" /><br>
	Full Name (alpha only Firstname Lastname): <input type = "text" name = "fullname" required /><br>
	Email (working email address required for verification):  <input type = "text" name = "email" required /><br>
	Password (8-16 chars): <input type = "password" name="password" required minlength="8" maxlength="16" /><br>
	Password (repeat): <input type = "password" name="password2" required minlength="8" maxlength="16" /><br>
	<input type="submit" name="submit" value="Submit">
</form>
