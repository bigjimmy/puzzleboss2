<?php
require_once('puzzlebosslib.php');

try {
    // Get activity counts and timing data
    $activity_response = readapi('/activity');
    $activity_counts = $activity_response->activity;
    $solve_timing = $activity_response->puzzle_solves_timer;
    $open_timing = $activity_response->open_puzzles_timer;
    
    // Get puzzle status counts
    $puzzle_status = array();
    $puzzle_response = readapi('/all');
    
    if (!isset($puzzle_response->rounds)) {
        $puzzle_response = (object)['rounds' => []];
    }
    
    foreach ($puzzle_response->rounds as $round) {
        if (!isset($round->puzzles)) {
            continue;
        }
        foreach ($round->puzzles as $puzzle) {
            if (!isset($puzzle->status)) {
                continue;
            }
            $status = $puzzle->status;
            $puzzle_status[$status] = ($puzzle_status[$status] ?? 0) + 1;
        }
    }
    
    // Get round counts
    $rounds = $puzzle_response->rounds;
    $rounds_total = count($rounds);
    $rounds_solved = 0;
    foreach ($rounds as $round) {
        if (isset($round->status) && $round->status === 'Solved') {
            $rounds_solved++;
        }
    }
    $rounds_open = $rounds_total - $rounds_solved;
    
    // Build metrics output
    $metrics = array();
    
    // Activity metrics
    $metrics[] = "# HELP puzzleboss_puzzles_created_total Total number of puzzles created";
    $metrics[] = "# TYPE puzzleboss_puzzles_created_total counter";
    $metrics[] = "puzzleboss_puzzles_created_total " . ($activity_counts->create ?? 0);
    $metrics[] = "";
    
    $metrics[] = "# HELP puzzleboss_puzzles_solved_total Total number of puzzles solved";
    $metrics[] = "# TYPE puzzleboss_puzzles_solved_total counter";
    $metrics[] = "puzzleboss_puzzles_solved_total " . ($activity_counts->solve ?? 0);
    $metrics[] = "";
    
    $metrics[] = "# HELP puzzleboss_comments_made_total Total number of comments made";
    $metrics[] = "# TYPE puzzleboss_comments_made_total counter";
    $metrics[] = "puzzleboss_comments_made_total " . ($activity_counts->comment ?? 0);
    $metrics[] = "";
    
    $metrics[] = "# HELP puzzleboss_assignments_made_total Total number of puzzle assignments made";
    $metrics[] = "# TYPE puzzleboss_assignments_made_total counter";
    $metrics[] = "puzzleboss_assignments_made_total " . ($activity_counts->interact ?? 0);
    $metrics[] = "";
    
    // Puzzle solve timing metrics
    $metrics[] = "# HELP puzzleboss_puzzles_solved_total Total number of unique puzzles solved";
    $metrics[] = "# TYPE puzzleboss_puzzles_solved_total counter";
    $metrics[] = "puzzleboss_puzzles_solved_total " . ($solve_timing->total_solves ?? 0);
    $metrics[] = "";
    
    $metrics[] = "# HELP puzzleboss_puzzle_solve_time_seconds_total Total time in seconds that all solved puzzles were open";
    $metrics[] = "# TYPE puzzleboss_puzzle_solve_time_seconds_total counter";
    $metrics[] = "puzzleboss_puzzle_solve_time_seconds_total " . ($solve_timing->total_solve_time_seconds ?? 0);
    $metrics[] = "";
    
    // Open puzzle timing metrics
    $metrics[] = "# HELP puzzleboss_open_puzzles_total Total number of open puzzles";
    $metrics[] = "# TYPE puzzleboss_open_puzzles_total counter";
    $metrics[] = "puzzleboss_open_puzzles_total " . ($open_timing->total_open ?? 0);
    $metrics[] = "";
    
    $metrics[] = "# HELP puzzleboss_open_puzzles_time_seconds_total Total time in seconds that all open puzzles have been open";
    $metrics[] = "# TYPE puzzleboss_open_puzzles_time_seconds_total counter";
    $metrics[] = "puzzleboss_open_puzzles_time_seconds_total " . ($open_timing->total_open_time_seconds ?? 0);
    $metrics[] = "";
    
    // Puzzle status metrics
    $metrics[] = "# HELP puzzleboss_puzzles_by_status_total Current number of puzzles in each status";
    $metrics[] = "# TYPE puzzleboss_puzzles_by_status_total gauge";
    
    $statuses = array('New', 'Being worked', 'Needs eyes', 'Solved', 'Critical', 'Unnecessary', 'WTF', '[hidden]');
    foreach ($statuses as $status) {
        $status_key = strtolower(str_replace(' ', '_', $status));
        $metrics[] = 'puzzleboss_puzzles_by_status_total{status="' . $status_key . '"} ' . ($puzzle_status[$status] ?? 0);
    }
    $metrics[] = "";
    
    // Round status metrics
    $metrics[] = "# HELP puzzleboss_rounds_by_status_total Current number of rounds in each status";
    $metrics[] = "# TYPE puzzleboss_rounds_by_status_total gauge";
    $metrics[] = 'puzzleboss_rounds_by_status_total{status="open"} ' . $rounds_open;
    $metrics[] = 'puzzleboss_rounds_by_status_total{status="solved"} ' . $rounds_solved;
    
    // Print metrics
    header('Content-Type: text/plain');
    echo implode("\n", $metrics) . "\n";

} catch (Exception $e) {
    error_log("Error generating metrics: " . $e->getMessage());
    exit(1);
} 