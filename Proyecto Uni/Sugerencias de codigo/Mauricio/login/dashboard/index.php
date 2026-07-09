<?php
session_start(); // Start or resume the existing session

// Check if the user session variables are NOT set
if (!isset($_SESSION['user_id']) || !isset($_SESSION['username'])) {
    // User is not logged in! Destroy any partial session data and kick them out
    session_unset();
    session_destroy();
    
    // Redirect them back to the login page
    header("Location: ../login"); // Adjust this path if your login folder structure is different
    exit();
}

// If the script makes it past the block above, the user is safely logged in!
$logged_in_user = $_SESSION['username'];
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; padding: 40px; }
        .dashboard-card { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }
        h1 { color: #333; }
        .logout-btn { display: inline-block; padding: 10px 20px; background-color: #d9534f; color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; }
        .logout-btn:hover { background-color: #c9302c; }
    </style>
</head>
<body>

<div class="dashboard-card">
    <h1>Welcome to your Dashboard, <?php echo htmlspecialchars($logged_in_user); ?>! 👋</h1>
    <p>This content is completely secured. Only logged-in users can see this page.</p>
    
    <a href="logout.php" class="logout-btn">Log Out</a>
</div>

</body>
</html>