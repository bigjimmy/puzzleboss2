#!/usr/bin/env python3
"""
Verify that all metrics from the original hardcoded metrics.php still work
correctly after migration to dynamic configuration-based system.
"""

import requests
import sys

# Original metrics from the hardcoded array in metrics.php (before migration)
EXPECTED_METRICS = {
    # BigJimmyBot stats
    "bigjimmy_loop_time_seconds": "gauge",
    "bigjimmy_loop_setup_seconds": "gauge",
    "bigjimmy_loop_processing_seconds": "gauge",
    "bigjimmy_loop_puzzle_count": "gauge",
    "bigjimmy_avg_seconds_per_puzzle": "gauge",
    "bigjimmy_quota_failures": "counter",
    "bigjimmy_loop_iterations_total": "counter",

    # Cache metrics
    "cache_hits_total": "counter",
    "cache_misses_total": "counter",
    "cache_invalidations_total": "counter",
    "tags_assigned_total": "counter",

    # Puzzcord metrics
    "puzzcord_members_total": "gauge",
    "puzzcord_members_online": "gauge",
    "puzzcord_members_active_in_voice": "gauge",
    "puzzcord_members_active_in_text": "gauge",
    "puzzcord_members_active_in_sheets": "gauge",
    "puzzcord_members_active_in_discord": "gauge",
    "puzzcord_members_active_anywhere": "gauge",
    "puzzcord_members_active_in_person": "gauge",
    "puzzcord_messages_per_minute": "gauge",
    "puzzcord_tables_in_use": "gauge",
}

def fetch_metrics():
    """Fetch metrics from the metrics.php endpoint."""
    response = requests.get("http://localhost/metrics.php")
    if response.status_code != 200:
        print(f"ERROR: Failed to fetch metrics: HTTP {response.status_code}")
        sys.exit(1)
    return response.text

def parse_metrics(metrics_text):
    """Parse Prometheus metrics text format."""
    metrics = {}
    current_metric = None
    current_type = None

    for line in metrics_text.split('\n'):
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Parse TYPE directive
        if line.startswith('# TYPE puzzleboss_'):
            parts = line.split()
            if len(parts) >= 4:
                metric_name = parts[2].replace('puzzleboss_', '')
                metric_type = parts[3]
                current_metric = metric_name
                current_type = metric_type

        # Parse metric value
        elif line.startswith('puzzleboss_') and not line.startswith('#'):
            parts = line.split()
            if len(parts) >= 2:
                metric_name = parts[0].replace('puzzleboss_', '').split('{')[0]

                # Store metric with its type
                if current_metric and current_type and metric_name == current_metric:
                    metrics[metric_name] = {
                        'type': current_type,
                        'value': parts[1] if len(parts) > 1 else None
                    }

    return metrics

def verify_metrics():
    """Verify all expected metrics are present with correct types."""
    print("=" * 80)
    print("METRICS MIGRATION VERIFICATION")
    print("=" * 80)
    print()

    print("Fetching metrics from http://localhost/metrics.php...")
    metrics_text = fetch_metrics()
    print(f"✓ Fetched {len(metrics_text)} bytes of metrics data")
    print()

    print("Parsing metrics...")
    parsed_metrics = parse_metrics(metrics_text)
    print(f"✓ Found {len(parsed_metrics)} puzzleboss_* metrics")
    print()

    print("Verifying expected metrics...")
    print("=" * 80)

    missing_metrics = []
    wrong_type_metrics = []
    correct_metrics = []

    for metric_name, expected_type in sorted(EXPECTED_METRICS.items()):
        if metric_name not in parsed_metrics:
            missing_metrics.append(metric_name)
            print(f"✗ MISSING: puzzleboss_{metric_name} (expected type: {expected_type})")
        else:
            actual_type = parsed_metrics[metric_name]['type']
            actual_value = parsed_metrics[metric_name]['value']

            if actual_type != expected_type:
                wrong_type_metrics.append((metric_name, expected_type, actual_type))
                print(f"✗ WRONG TYPE: puzzleboss_{metric_name}")
                print(f"    Expected: {expected_type}")
                print(f"    Actual:   {actual_type}")
            else:
                correct_metrics.append(metric_name)
                print(f"✓ puzzleboss_{metric_name:<45} type={actual_type:<8} value={actual_value}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total expected metrics: {len(EXPECTED_METRICS)}")
    print(f"✓ Correct:             {len(correct_metrics)}")
    print(f"✗ Missing:             {len(missing_metrics)}")
    print(f"✗ Wrong type:          {len(wrong_type_metrics)}")
    print()

    if missing_metrics:
        print("Missing metrics:")
        for metric in missing_metrics:
            print(f"  - {metric}")
        print()

    if wrong_type_metrics:
        print("Metrics with wrong type:")
        for metric, expected, actual in wrong_type_metrics:
            print(f"  - {metric}: expected {expected}, got {actual}")
        print()

    if not missing_metrics and not wrong_type_metrics:
        print("✅ ALL METRICS VERIFIED SUCCESSFULLY!")
        print("All original metrics are present with correct types.")
        return 0
    else:
        print("❌ VERIFICATION FAILED")
        print("Some metrics are missing or have incorrect types.")
        return 1

if __name__ == "__main__":
    sys.exit(verify_metrics())
