<?php
// 1. Database Configuration
$host     = 'localhost';
$db_user  = 'manager1';       // Replace with your database username
$db_pass  = '123';           // Replace with your database password
$db_name  = 'test_db';    // Replace with your database name

$message = '';

// 2. Handle Form Submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Collect and sanitize input data
    $username = trim($_POST['username']);
    $email    = trim($_POST['email']);
    $password = trim($_POST['password']);

    // Basic Validation
    if (empty($username) || empty($email) || empty($password)) {
        $message = "All fields are required!";
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $message = "Invalid email format!";
    } else {
        // Connect to the database using MySQLi
        $conn = new mysqli($host, $db_user, $db_pass, $db_name);

        // Check connection
        if ($conn->connect_error) {
            die("Connection failed: " . $conn->connect_error);
        }

        // Securely hash the password
        $hashed_password = password_hash($password, PASSWORD_DEFAULT);

        // Prepare the SQL statement to prevent SQL Injection
        $stmt = $conn->prepare("INSERT INTO users (username, email, password) VALUES (?, ?, ?)");
        $stmt->bind_param("sss", $username, $email, $hashed_password);

        // Execute and check if successful
        if ($stmt->execute()) {
            $message = "Registration successful!";
        } else {
            // Check if email or username already exists (assuming UNIQUE constraints in DB)
            if ($conn->errno === 1062) {
                $message = "Username or Email already registered.";
            } else {
                $message = "Error: " . $stmt->error;
            }
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
    <title>Simple Registration</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .form-container { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 300px; }
        h2 { margin-top: 0; text-align: center; color: #333; }
        input[type="text"], input[type="email"], input[type="password"] { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background-color: #007BFF; border: none; color: white; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #0056b3; }
        .msg { text-align: center; font-weight: bold; margin-bottom: 15px; color: #d9534f; }
        .msg-success { color: #5cb85c; }
    </style>
</head>
<body>

<div class="form-container">
    <h2>Register</h2>
    
    <?php if (!empty($message)): ?>
        <div class="msg <?php echo ($message === 'Registration successful!') ? 'msg-success' : ''; ?>">
            <?php echo htmlspecialchars($message); ?>
        </div>
    <?php endif; ?>

    <form action="index.php" method="POST">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" required>

        <label for="email">Email</label>
        <input type="email" id="email" name="email" required>

        <label for="password">Password</label>
        <input type="password" id="password" name="password" required>

        <button type="submit">Sign Up</button>
        <p>Already Signed Up?</p><a href="../login/"> Log In</a>
    </form>
</div>

</body>
</html>