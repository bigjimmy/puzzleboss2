<?php
require_once('../pblib.php');

// Connect to database
$conn = new mysqli(
    $config['MYSQL']['HOST'],
    $config['MYSQL']['USERNAME'],
    $config['MYSQL']['PASSWORD'],
    $config['MYSQL']['DATABASE']
);

if ($conn->connect_error) {
    error_log("Connection failed: " . $conn->connect_error);
    exit(1);
}

try {
    // Get activity counts
    $activity_counts = array();
    $result = $conn->query("SELECT type, COUNT(*) as count FROM activity GROUP BY type");
    while ($row = $result->fetch_assoc()) {
        $activity_counts[$row['type']] = $row['count'];
    }
    
    // Get puzzle status counts
    $puzzle_counts = array();
    $result = $conn->query("SELECT status, COUNT(*) as count FROM puzzle GROUP BY status");
    while ($row = $result->fetch_assoc()) {
        $puzzle_counts[$row['status']] = $row['count'];
    }
    
    // Get round counts
    $result = $conn->query("SELECT COUNT(*) as total FROM round");
    $rounds_total = $result->fetch_assoc()['total'];
    
    $result = $conn->query("SELECT COUNT(*) as solved FROM round WHERE status = 'Solved'");
    $rounds_solved = $result->fetch_assoc()['solved'];
    $rounds_open = $rounds_total - $rounds_solved;
    
    // Build metrics output
    $metrics = array();
    
    // Activity metrics
    $metrics[] = "# HELP puzzleboss_puzzles_created_total Total number of puzzles created";
    $metrics[] = "# TYPE puzzleboss_puzzles_created_total counter";
    $metrics[] = "puzzleboss_puzzles_created_total " . ($activity_counts['create'] ?? 0) . "\n";
    
    $metrics[] = "# HELP puzzleboss_puzzles_solved_total Total number of puzzles solved";
    $metrics[] = "# TYPE puzzleboss_puzzles_solved_total counter";
    $metrics[] = "puzzleboss_puzzles_solved_total " . ($activity_counts['solve'] ?? 0) . "\n";
    
    $metrics[] = "# HELP puzzleboss_comments_made_total Total number of comments made";
    $metrics[] = "# TYPE puzzleboss_comments_made_total counter";
    $metrics[] = "puzzleboss_comments_made_total " . ($activity_counts['comment'] ?? 0) . "\n";
    
    $metrics[] = "# HELP puzzleboss_assignments_made_total Total number of puzzle assignments made";
    $metrics[] = "# TYPE puzzleboss_assignments_made_total counter";
    $metrics[] = "puzzleboss_assignments_made_total " . ($activity_counts['interact'] ?? 0) . "\n";
    
    // Puzzle status metrics
    $metrics[] = "# HELP puzzleboss_puzzles_by_status_total Current number of puzzles in each status";
    $metrics[] = "# TYPE puzzleboss_puzzles_by_status_total gauge";
    
    $statuses = array('New', 'Being worked', 'Needs eyes', 'WTF', 'Critical', 'Unnecessary');
    foreach ($statuses as $status) {
        $status_key = strtolower(str_replace(' ', '_', $status));
        $metrics[] = 'puzzleboss_puzzles_by_status_total{status="' . $status_key . '"} ' . ($puzzle_counts[$status] ?? 0);
    }
    
    // Round status metrics
    $metrics[] = "\n# HELP puzzleboss_rounds_by_status_total Current number of rounds in each status";
    $metrics[] = "# TYPE puzzleboss_rounds_by_status_total gauge";
    $metrics[] = 'puzzleboss_rounds_by_status_total{status="open"} ' . $rounds_open;
    $metrics[] = 'puzzleboss_rounds_by_status_total{status="solved"} ' . $rounds_solved;
    
    // Print metrics
    echo implode("\n", $metrics);

} catch (Exception $e) {
    error_log("Error generating metrics: " . $e->getMessage());
    exit(1);
} finally {
    $conn->close();
} 