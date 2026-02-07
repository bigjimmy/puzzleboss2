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

    $metrics[] = "# HELP puzzleboss_sheet_revisions_total Total number of sheet revisions detected";
    $metrics[] = "# TYPE puzzleboss_sheet_revisions_total counter";
    $metrics[] = "puzzleboss_sheet_revisions_total " . ($activity_counts->revise ?? 0);
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
        // Extract just the names from the rich status objects
        $statuses = array_map(function($s) { return $s->name; }, $huntinfo_response->statuses ?? array());
    } catch (Exception $e) {
        // Fallback to hardcoded list if huntinfo fails
        $statuses = array('New', 'Being worked', 'Needs eyes', 'Solved', 'Critical', 'Unnecessary', 'WTF', 'Under control', 'Waiting for HQ', 'Grind', 'Abandoned', '[hidden]');
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

            // Load metric metadata from config (dynamically configured)
            $stats_to_log = array();
            try {
                $config_response = readapi('/config');
                if (isset($config_response->config->METRICS_METADATA)) {
                    $metadata_json = $config_response->config->METRICS_METADATA;
                    $stats_to_log = json_decode($metadata_json, true);
                    if (!is_array($stats_to_log)) {
                        error_log("METRICS_METADATA config is not valid JSON, using empty array");
                        $stats_to_log = array();
                    }
                }
            } catch (Exception $e) {
                error_log("Failed to load METRICS_METADATA from config: " . $e->getMessage());
            }

            // Export metrics defined in metadata config
            foreach ($stats_to_log as $stat => $stat_info) {
                // Use db_key if provided, otherwise use stat name as-is
                $db_key = $stat_info["db_key"] ?? $stat;

                // Skip if the metric doesn't exist in botstats
                if (!isset($botstats[$db_key])) {
                    continue;
                }

                $metrics[] = sprintf("# HELP puzzleboss_%s %s", $stat, $stat_info["description"]);
                $metrics[] = sprintf("# TYPE puzzleboss_%s %s", $stat, $stat_info["type"]);
                $metrics[] = sprintf("puzzleboss_%s %s", $stat, $botstats[$db_key]->val ?? "0");
                $metrics[] = "";
            }

            // Also export any botstats not in metadata using convention-based defaults
            // This ensures new metrics are automatically available without config changes
            foreach ($botstats as $db_key => $stat_value) {
                // Check if this metric is already handled by metadata
                $already_handled = false;
                foreach ($stats_to_log as $stat => $stat_info) {
                    if (($stat_info["db_key"] ?? $stat) === $db_key) {
                        $already_handled = true;
                        break;
                    }
                }

                if ($already_handled) {
                    continue;
                }

                // Convention-based: metrics ending in _total are counters, others are gauges
                $metric_name = $db_key;
                $metric_type = (substr($metric_name, -6) === '_total') ? 'counter' : 'gauge';
                $metric_description = ucfirst(str_replace('_', ' ', $metric_name));

                $metrics[] = sprintf("# HELP puzzleboss_%s %s", $metric_name, $metric_description);
                $metrics[] = sprintf("# TYPE puzzleboss_%s %s", $metric_name, $metric_type);
                $metrics[] = sprintf("puzzleboss_%s %s", $metric_name, $stat_value->val ?? "0");
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
