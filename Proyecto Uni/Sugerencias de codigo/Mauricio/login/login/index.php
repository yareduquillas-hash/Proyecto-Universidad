<?php
session_start(); // Start a session to keep the user logged in

// 1. Database Configuration
$host     = 'localhost';
$db_user  = 'manager1';       // Using your database username
$db_pass  = '123';            // Using your database password
$db_name  = 'test_db';        // Using your database name

$message = '';

// 2. Handle Form Submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Collect and trim input data
    $username_or_email = trim($_POST['username_or_email']);
    $password          = trim($_POST['password']);

    // Basic Validation
    if (empty($username_or_email) || empty($password)) {
        $message = "All fields are required!";
    } else {
        // Connect to the database
        $conn = new mysqli($host, $db_user, $db_pass, $db_name);

        // Check connection
        if ($conn->connect_error) {
            die("Connection failed: " . $conn->connect_error);
        }

        // Prepare SQL to find user by either Username OR Email
        $stmt = $conn->prepare("SELECT uid, username, password FROM users WHERE username = ? OR email = ? LIMIT 1");
        $stmt->bind_param("ss", $username_or_email, $username_or_email);
        $stmt->execute();
        $result = $stmt->get_result();

        // Check if user exists
        if ($result->num_rows === 1) {
            $user = $result->fetch_assoc();

            // Verify the submitted password against the hashed password in the DB
            if (password_verify($password, $user['password'])) {
                // Password is correct! Store data in session variables
                $_SESSION['user_id']   = $user['uid'];
                $_SESSION['username']  = $user['username'];
                
                // Redirect to a dashboard or home page
                header("Location: ../dashboard"); 
                exit();
            } else {
                $message = "Invalid password!";
            }
        } else {
            $message = "No user found with that username or email.";
        }

        // Close connections
        $stmt->close();
        $conn->close();
    }
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple Login</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .form-container { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 300px; }
        h2 { margin-top: 0; text-align: center; color: #333; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background-color: #007BFF; border: none; color: white; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #0056b3; }
        .msg { text-align: center; font-weight: bold; margin-bottom: 15px; color: #d9534f; }
        .links { margin-top: 15px; text-align: center; font-size: 14px; }
        .links a { color: #007BFF; text-decoration: none; }
        .links a:hover { text-decoration: underline; }
    </style>
</head>
<body>

<div class="form-container">
    <h2>Log In</h2>
    
    <?php if (!empty($message)): ?>
        <div class="msg">
            <?php echo htmlspecialchars($message); ?>
        </div>
    <?php endif; ?>

    <form action="index.php" method="POST">
        <label for="username_or_email">Username or Email</label>
        <input type="text" id="username_or_email" name="username_or_email" required>

        <label for="password">Password</label>
        <input type="password" id="password" name="password" required>

        <button type="submit">Log In</button>
        
        <div class="links">
            <p>Don't have an account? <a href="../register">Register here</a></p>
        </div>
    </form>
</div>

</body>
</html>