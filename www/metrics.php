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
    
    $metrics[] = "# HELP puzzleboss_seconds_since_last_solve Seconds since the last puzzle was solved";
    $metrics[] = "# TYPE puzzleboss_seconds_since_last_solve gauge";
    $metrics[] = "puzzleboss_seconds_since_last_solve " . ($activity_response->seconds_since_last_solve ?? 0);
    $metrics[] = "";
    
    // Puzzle status metrics
    $metrics[] = "# HELP puzzleboss_puzzles_by_status_total Current number of puzzles in each status";
    $metrics[] = "# TYPE puzzleboss_puzzles_by_status_total gauge";

    // Fetch statuses dynamically from huntinfo endpoint
    try {
        $huntinfo_response = readapi('/huntinfo');
        $statuses = $huntinfo_response->statuses ?? array();
    } catch (Exception $e) {
        // Fallback to hardcoded list if huntinfo fails
        $statuses = array('New', 'Being worked', 'Needs eyes', 'Solved', 'Critical', 'Unnecessary', 'WTF', 'Under control', 'Waiting for HQ', 'Grind', '[hidden]');
    }

    foreach ($statuses as $status) {
        if ($status === '[hidden]') {
            continue;
        }
        $status_key = strtolower(str_replace(' ', '_', $status));
        $metrics[] = 'puzzleboss_puzzles_by_status_total{status="' . $status_key . '"} ' . ($puzzle_status[$status] ?? 0);
    }
    $metrics[] = "";
    
    // Round status metrics
    $metrics[] = "# HELP puzzleboss_rounds_by_status_total Current number of rounds in each status";
    $metrics[] = "# TYPE puzzleboss_rounds_by_status_total gauge";
    $metrics[] = 'puzzleboss_rounds_by_status_total{status="open"} ' . $rounds_open;
    $metrics[] = 'puzzleboss_rounds_by_status_total{status="solved"} ' . $rounds_solved;
    $metrics[] = "";
    
    try {
        $botstats_response = readapi('/botstats');
        if (isset($botstats_response->botstats)) {
            $botstats = (array)$botstats_response->botstats;

            $stats_to_log = array(
                // BigJimmyBot stats
                "loop_time_seconds" => array(
                    "type" => "gauge",
                    "description" => "Total time in seconds for last full puzzle scan loop (setup + processing)",
                ),
                "loop_setup_seconds" => array(
                    "type" => "gauge",
                    "description" => "Time in seconds for loop setup (API fetch, thread creation)",
                ),
                "loop_processing_seconds" => array(
                    "type" => "gauge",
                    "description" => "Time in seconds for actual puzzle processing",
                ),
                "loop_puzzle_count" => array(
                    "type" => "gauge",
                    "description" => "Number of puzzles processed in last loop",
                ),
                "loop_avg_seconds_per_puzzle" => array(
                    "type" => "gauge",
                    "description" => "Average processing seconds per puzzle in last loop",
                ),
                "quota_failures" => array(
                    "type" => "counter",
                    "description" => "Total Google API quota failures (429 errors) since bot start",
                ),
                "loop_iterations_total" => array(
                    "type" => "counter",
                    "description" => "Total number of loop iterations completed (resets on bot restart)",
                ),
                // Cache metrics
                "cache_hits_total" => array(
                    "type" => "counter",
                    "description" => "Total cache hits for /allcached endpoint",
                ),
                "cache_misses_total" => array(
                    "type" => "counter",
                    "description" => "Total cache misses for /allcached endpoint",
                ),
                "cache_invalidations_total" => array(
                    "type" => "counter",
                    "description" => "Total cache invalidations",
                ),
                "tags_assigned_total" => array(
                    "type" => "counter",
                    "description" => "Total tags assigned to puzzles",
                ),
                // Puzzcord metrics
                "puzzcord_members_total" => array(
                    "type" => "gauge",
                    "description" => "Total number of Discord team members (with member role)",
                ),
                "puzzcord_members_online" => array(
                    "type" => "gauge",
                    "description" => "Number of Discord team members online (according to Discord)",
                ),
                "puzzcord_members_active_in_voice" => array(
                    "type" => "gauge",
                    "description" => "Number of team members currently active in voice on Discord",
                ),
                "puzzcord_members_active_in_text" => array(
                    "type" => "gauge",
                    "description" => "Number of team members active in text on Discord in the last 15 minutes",
                ),
                "puzzcord_members_active_in_sheets" => array(
                    "type" => "gauge",
                    "description" => "Number of team members active in Sheets in the last 15 minutes",
                ),
                "puzzcord_members_active_in_discord" => array(
                    "type" => "gauge",
                    "description" => "Number of team members currently active in voice OR active in text in the last 15 minutes",
                ),
                "puzzcord_members_active_anywhere" => array(
                    "type" => "gauge",
                    "description" => "Number of team members currently active in voice OR active in (text OR Sheets) in the last 15 minutes",
                ),
                "puzzcord_messages_per_minute" => array(
                    "type" => "gauge",
                    "description" => "Discord messages per minute",
                ),
                "puzzcord_tables_in_use" => array(
                    "type" => "gauge",
                    "description" => "Discord tables (voice channels) in use",
                ),
            );

            foreach ($stats_to_log as $stat => $stat_info) {
                $metrics[] = sprintf("#HELP puzzleboss_%s %s", $stat, $stat_info["description"]);
                $metrics[] = sprintf("#TYPE puzzleboss_%s %s", $stat, $stat_info["type"]);
                $metrics[] = sprintf("puzzleboss_%s %s", $stat, $botstats[$stat]["val"] ?? "0");
                $metrics[] = "";
            }
        }
    } catch (Exception $e) {
        // Botstats not available yet, skip
    }
    
    // Print metrics
    header('Content-Type: text/plain');
    echo implode("\n", $metrics) . "\n";

} catch (Exception $e) {
    error_log("Error generating metrics: " . $e->getMessage());
    exit(1);
} 
