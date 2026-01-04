#!/usr/bin/env python3
"""
Puzzleboss Load Testing Framework

A modular load testing system for the Puzzleboss application.
Each test module can be independently configured for concurrency and request delay.

Usage:
    python loadtest.py --config loadtest_config.yaml
    python loadtest.py --duration 60  # Run for 60 seconds with default config
"""

import argparse
import os
import subprocess
import threading
import time
import random
import string
import requests
import yaml
import sys
import urllib3

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import statistics

# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ModuleConfig:
    """Configuration for a single test module"""
    enabled: bool = False
    threads: int = 1
    delay: float = 1.0  # seconds between requests per thread


@dataclass
class LoadTestConfig:
    """Main configuration for the load test"""
    api_base: str = "http://localhost:5000"
    php_base: str = "https://localhost/pb"
    duration: int = 60  # seconds
    
    # Module configurations
    php_puzzleboss: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    php_status: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    php_editpuzzle: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    api_solver_assignment: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    api_status_changing: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    api_location_updating: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    api_sheet_simulation: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    api_commenting: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    api_tagging: ModuleConfig = field(default_factory=lambda: ModuleConfig())
    api_tag_searching: ModuleConfig = field(default_factory=lambda: ModuleConfig())


def load_config(config_path: str) -> LoadTestConfig:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    
    config = LoadTestConfig()
    config.api_base = data.get('api_base', config.api_base)
    config.php_base = data.get('php_base', config.php_base)
    config.duration = data.get('duration', config.duration)
    
    modules = data.get('modules', {})
    for module_name, module_data in modules.items():
        if hasattr(config, module_name) and module_data:
            setattr(config, module_name, ModuleConfig(
                enabled=module_data.get('enabled', False),
                threads=module_data.get('threads', 1),
                delay=module_data.get('delay', 1.0)
            ))
    
    return config


# ============================================================================
# Metrics Collection
# ============================================================================

class MetricsCollector:
    """Thread-safe metrics collection for a test module"""
    
    def __init__(self, name: str):
        self.name = name
        self.lock = threading.Lock()
        self.request_count = 0
        self.error_count = 0
        self.latencies: List[float] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def record_request(self, latency: float, is_error: bool = False):
        with self.lock:
            self.request_count += 1
            self.latencies.append(latency)
            if is_error:
                self.error_count += 1
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        self.end_time = time.time()
    
    def get_results(self) -> Dict:
        with self.lock:
            duration = (self.end_time or time.time()) - (self.start_time or time.time())
            if duration <= 0:
                duration = 1
            
            return {
                'module': self.name,
                'total_requests': self.request_count,
                'error_count': self.error_count,
                'error_rate': (self.error_count / self.request_count * 100) if self.request_count > 0 else 0,
                'requests_per_second': self.request_count / duration,
                'avg_latency': statistics.mean(self.latencies) if self.latencies else 0,
                'p50_latency': statistics.median(self.latencies) if self.latencies else 0,
                'p95_latency': (sorted(self.latencies)[int(len(self.latencies) * 0.95)] 
                               if len(self.latencies) > 20 else 
                               (max(self.latencies) if self.latencies else 0)),
                'p99_latency': (sorted(self.latencies)[int(len(self.latencies) * 0.99)] 
                               if len(self.latencies) > 100 else 
                               (max(self.latencies) if self.latencies else 0)),
                'min_latency': min(self.latencies) if self.latencies else 0,
                'max_latency': max(self.latencies) if self.latencies else 0,
                'duration': duration,
            }


# ============================================================================
# Hunt State Management
# ============================================================================

class HuntState:
    """Manages the hunt state for load testing"""
    
    def __init__(self, api_base: str):
        self.api_base = api_base
        self.puzzles: List[Dict] = []
        self.solvers: List[Dict] = []
        self.tags: List[Dict] = []
        self.lock = threading.Lock()
    
    def refresh(self):
        """Refresh the current hunt state"""
        with self.lock:
            resp = requests.get(f"{self.api_base}/puzzles")
            resp.raise_for_status()
            self.puzzles = resp.json().get('puzzles', [])
            
            resp = requests.get(f"{self.api_base}/solvers")
            resp.raise_for_status()
            self.solvers = resp.json().get('solvers', [])
            
            resp = requests.get(f"{self.api_base}/tags")
            resp.raise_for_status()
            self.tags = resp.json().get('tags', [])
    
    def get_random_puzzle(self) -> Optional[Dict]:
        with self.lock:
            return random.choice(self.puzzles) if self.puzzles else None
    
    def get_random_solver(self) -> Optional[Dict]:
        with self.lock:
            # Filter to non-system solvers (id > 100)
            regular_solvers = [s for s in self.solvers if s.get('id', 0) > 100]
            return random.choice(regular_solvers) if regular_solvers else None
    
    def get_random_tag(self) -> Optional[Dict]:
        with self.lock:
            return random.choice(self.tags) if self.tags else None
    
    def get_puzzle_ids(self) -> List[int]:
        with self.lock:
            return [p['id'] for p in self.puzzles]


# ============================================================================
# Test Modules
# ============================================================================

class TestModule:
    """Base class for test modules"""
    
    def __init__(self, name: str, config: ModuleConfig, hunt_state: HuntState, 
                 api_base: str, php_base: str):
        self.name = name
        self.config = config
        self.hunt_state = hunt_state
        self.api_base = api_base
        self.php_base = php_base
        self.metrics = MetricsCollector(name)
        self.running = False
        self.threads: List[threading.Thread] = []
    
    def run_single_request(self) -> None:
        """Override this in subclasses to perform a single test request"""
        raise NotImplementedError
    
    def worker(self):
        """Worker thread that runs requests in a loop"""
        while self.running:
            start = time.time()
            try:
                self.run_single_request()
                latency = time.time() - start
                self.metrics.record_request(latency, is_error=False)
            except Exception as e:
                latency = time.time() - start
                self.metrics.record_request(latency, is_error=True)
            
            # Sleep for the configured delay
            if self.config.delay > 0:
                time.sleep(self.config.delay)
    
    def start(self):
        """Start the test module"""
        if not self.config.enabled:
            return
        
        self.running = True
        self.metrics.start()
        
        for i in range(self.config.threads):
            t = threading.Thread(target=self.worker, name=f"{self.name}-{i}")
            t.daemon = True
            t.start()
            self.threads.append(t)
    
    def stop(self):
        """Stop the test module"""
        self.running = False
        self.metrics.stop()
        for t in self.threads:
            t.join(timeout=2)


class PHPPuzzlebossModule(TestModule):
    """Load test old.php"""
    
    def run_single_request(self):
        resp = requests.get(f"{self.php_base}/old.php", verify=False)
        resp.raise_for_status()


class PHPStatusModule(TestModule):
    """Load test status.php"""
    
    def run_single_request(self):
        resp = requests.get(f"{self.php_base}/status.php", verify=False)
        resp.raise_for_status()


class PHPEditPuzzleModule(TestModule):
    """Load test editpuzzle.php for each puzzle"""
    
    def run_single_request(self):
        puzzle = self.hunt_state.get_random_puzzle()
        if puzzle:
            resp = requests.get(f"{self.php_base}/editpuzzle.php?pid={puzzle['id']}", verify=False)
            resp.raise_for_status()


class APISolverAssignmentModule(TestModule):
    """Test solver assignment/unassignment"""
    
    MAX_CURRENT_SOLVERS = 4
    MAX_ALLTIME_SOLVERS = 12
    
    def run_single_request(self):
        puzzle = self.hunt_state.get_random_puzzle()
        solver = self.hunt_state.get_random_solver()
        
        if not puzzle or not solver:
            return
        
        puzzle_id = puzzle['id']
        solver_id = solver['id']
        
        # Get current puzzle state
        resp = requests.get(f"{self.api_base}/puzzles/{puzzle_id}")
        resp.raise_for_status()
        puzzle_data = resp.json().get('puzzle', {})
        
        # Skip solved puzzles - can't assign solvers to them
        if puzzle_data.get('status') == 'Solved':
            return
        
        current_solvers = puzzle_data.get('cursolvers', '') or ''
        current_solver_names = [s.strip() for s in current_solvers.split(',') if s.strip()]
        current_count = len(current_solver_names)
        
        # Check if we need to clear solvers
        # Note: API returns 'solvers' for historical, 'cursolvers' for current
        alltime_solvers = puzzle_data.get('solvers', '') or ''
        alltime_count = len([s for s in alltime_solvers.split(',') if s.strip()])
        
        if alltime_count >= self.MAX_ALLTIME_SOLVERS or current_count >= self.MAX_CURRENT_SOLVERS:
            # Unassign a random current solver by setting their puzz to empty
            if current_solver_names:
                # Find solver ID by name
                solver_to_remove = random.choice(current_solver_names)
                for s in self.hunt_state.solvers:
                    if s.get('name') == solver_to_remove:
                        resp = requests.post(
                            f"{self.api_base}/solvers/{s['id']}/puzz",
                            json={"puzz": ""}
                        )
                        resp.raise_for_status()
                        break
        else:
            # Assign the solver
            resp = requests.post(
                f"{self.api_base}/solvers/{solver_id}/puzz",
                json={"puzz": puzzle_id}
            )
            resp.raise_for_status()


class APIStatusChangingModule(TestModule):
    """Test status changes"""
    
    STATUSES = ['Being worked', 'Needs eyes', 'Critical', 'Unnecessary', 'WTF', 
                'Under control', 'Waiting for HQ', 'Grind']
    
    def run_single_request(self):
        puzzle = self.hunt_state.get_random_puzzle()
        if not puzzle:
            return
        
        status = random.choice(self.STATUSES)
        resp = requests.post(
            f"{self.api_base}/puzzles/{puzzle['id']}/status",
            json={"status": status}
        )
        resp.raise_for_status()


class APILocationUpdatingModule(TestModule):
    """Test location updates"""
    
    LOCATIONS = ['HQ', 'Room 123', 'Room 456', 'Lobby', 'Cafeteria', 'Remote', 
                 'Building 1', 'Building 2', '']
    
    def run_single_request(self):
        puzzle = self.hunt_state.get_random_puzzle()
        if not puzzle:
            return
        
        location = random.choice(self.LOCATIONS)
        resp = requests.post(
            f"{self.api_base}/puzzles/{puzzle['id']}/xyzloc",
            json={"xyzloc": location}
        )
        resp.raise_for_status()


class APISheetSimulationModule(TestModule):
    """Simulate bigjimmybot sheet activity recording"""
    
    def run_single_request(self):
        puzzle = self.hunt_state.get_random_puzzle()
        solver = self.hunt_state.get_random_solver()
        
        if not puzzle or not solver:
            return
        
        # Record activity like bigjimmybot does
        resp = requests.post(
            f"{self.api_base}/puzzles/{puzzle['id']}/lastact",
            json={"lastact": {
                "solver_id": solver['id'],
                "source": "bigjimmybot",
                "type": "interact"
            }}
        )
        resp.raise_for_status()


class APICommentingModule(TestModule):
    """Test comment updates"""
    
    COMMENTS = [
        'Working on extraction',
        'Need help with logic puzzle',
        'Almost there!',
        'Stuck on step 3',
        'Looking for pattern',
        'Checking constraints',
        '',
        'Meta insight: try combining with other puzzles',
        'Waiting for more letters',
    ]
    
    def run_single_request(self):
        puzzle = self.hunt_state.get_random_puzzle()
        if not puzzle:
            return
        
        comment = random.choice(self.COMMENTS)
        resp = requests.post(
            f"{self.api_base}/puzzles/{puzzle['id']}/comments",
            json={"comments": comment}
        )
        resp.raise_for_status()


class APITaggingModule(TestModule):
    """Test tagging operations"""
    
    MAX_TAGS_PER_PUZZLE = 5
    TAG_NAMES = ['logic', 'wordplay', 'crypto', 'meta', 'extraction', 
                 'grid', 'music', 'art', 'math', 'trivia']
    
    def run_single_request(self):
        puzzle = self.hunt_state.get_random_puzzle()
        if not puzzle:
            return
        
        puzzle_id = puzzle['id']
        
        # Get current tags on puzzle
        # API returns: {"status": "ok", "puzzle": {"id": X, "tags": "tag1,tag2,tag3"}}
        resp = requests.get(f"{self.api_base}/puzzles/{puzzle_id}/tags")
        resp.raise_for_status()
        tags_str = resp.json().get('puzzle', {}).get('tags', '') or ''
        current_tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        
        if len(current_tags) >= self.MAX_TAGS_PER_PUZZLE:
            # Remove a random tag
            tag_to_remove = random.choice(current_tags)
            resp = requests.post(
                f"{self.api_base}/puzzles/{puzzle_id}/tags",
                json={"tags": {"remove": tag_to_remove}}
            )
            resp.raise_for_status()
        else:
            # Add a random tag
            tag_name = random.choice(self.TAG_NAMES)
            resp = requests.post(
                f"{self.api_base}/puzzles/{puzzle_id}/tags",
                json={"tags": {"add": tag_name}}
            )
            resp.raise_for_status()


class APITagSearchingModule(TestModule):
    """Test tag search operations"""
    
    TAG_NAMES = ['logic', 'wordplay', 'crypto', 'meta', 'extraction', 
                 'grid', 'music', 'art', 'math', 'trivia']
    
    def run_single_request(self):
        # Search by tag name
        tag_name = random.choice(self.TAG_NAMES)
        resp = requests.get(f"{self.api_base}/search?tag={tag_name}")
        resp.raise_for_status()


# ============================================================================
# Main Load Test Runner
# ============================================================================

class LoadTestRunner:
    """Main load test orchestrator"""
    
    NUM_ROUNDS = 10
    PUZZLES_PER_ROUND = 15
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.hunt_state = HuntState(config.api_base)
        self.modules: List[TestModule] = []
    
    def check_empty_hunt(self) -> bool:
        """Check if the hunt is empty and prompt user if not"""
        try:
            resp = requests.get(f"{self.config.api_base}/puzzles")
            resp.raise_for_status()
            puzzles = resp.json().get('puzzles', [])
            
            resp = requests.get(f"{self.config.api_base}/rounds")
            resp.raise_for_status()
            rounds = resp.json().get('rounds', [])
            
            if puzzles or rounds:
                print("=" * 60)
                print("ERROR: Hunt is not empty!")
                print(f"  Found {len(puzzles)} puzzles and {len(rounds)} rounds")
                print()
                print("Please reset the hunt before running load tests:")
                print("  python scripts/reset-hunt.py")
                print("=" * 60)
                return False
            
            return True
        except Exception as e:
            print(f"ERROR: Could not check hunt state: {e}")
            return False
    
    def load_test_hunt(self) -> bool:
        """Load test data using testload.py"""
        print()
        print("Loading test hunt data via testload.py...")
        print("-" * 40)
        
        # Find testload.py relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        testload_path = os.path.join(script_dir, 'testload.py')
        
        if not os.path.exists(testload_path):
            print(f"ERROR: testload.py not found at {testload_path}")
            return False
        
        # Run testload.py non-interactively
        cmd = [
            sys.executable, testload_path,
            '--no-interactive',
            '--rounds', str(self.NUM_ROUNDS),
            '--puzzles', str(self.PUZZLES_PER_ROUND),
            '--api-base', self.config.api_base
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode != 0:
            print("ERROR: testload.py failed")
            return False
        
        print("-" * 40)
        print("Test hunt loaded successfully!")
        return True
    
    def setup_modules(self):
        """Initialize all test modules"""
        module_classes = [
            ('php_puzzleboss', PHPPuzzlebossModule),
            ('php_status', PHPStatusModule),
            ('php_editpuzzle', PHPEditPuzzleModule),
            ('api_solver_assignment', APISolverAssignmentModule),
            ('api_status_changing', APIStatusChangingModule),
            ('api_location_updating', APILocationUpdatingModule),
            ('api_sheet_simulation', APISheetSimulationModule),
            ('api_commenting', APICommentingModule),
            ('api_tagging', APITaggingModule),
            ('api_tag_searching', APITagSearchingModule),
        ]
        
        for name, cls in module_classes:
            module_config = getattr(self.config, name, ModuleConfig())
            if module_config.enabled:
                module = cls(
                    name=name,
                    config=module_config,
                    hunt_state=self.hunt_state,
                    api_base=self.config.api_base,
                    php_base=self.config.php_base
                )
                self.modules.append(module)
    
    def run(self, skip_setup: bool = False):
        """Run the load test"""
        print("=" * 60)
        print("Puzzleboss Load Test")
        print("=" * 60)
        
        if skip_setup:
            print("Skipping setup (using existing hunt data)...")
        else:
            # Check for empty hunt
            if not self.check_empty_hunt():
                sys.exit(1)
            
            print("Hunt is empty.")
            
            # Load test data
            if not self.load_test_hunt():
                print("ERROR: Failed to load test hunt data")
                sys.exit(1)
        
        print()
        print("Starting load test...")
        print()
        
        # Refresh hunt state with newly created data
        try:
            self.hunt_state.refresh()
        except Exception as e:
            print(f"Warning: Could not refresh hunt state: {e}")
        
        # Setup modules
        self.setup_modules()
        
        if not self.modules:
            print("No modules enabled! Check your configuration.")
            sys.exit(1)
        
        print(f"Enabled modules ({len(self.modules)}):")
        for module in self.modules:
            print(f"  - {module.name}: {module.config.threads} threads, "
                  f"{module.config.delay}s delay")
        print()
        print(f"Running for {self.config.duration} seconds...")
        print()
        
        # Start all modules
        for module in self.modules:
            module.start()
        
        # Run for the specified duration, refreshing hunt state periodically
        start_time = time.time()
        while time.time() - start_time < self.config.duration:
            time.sleep(5)
            try:
                self.hunt_state.refresh()
            except Exception:
                pass
            
            elapsed = time.time() - start_time
            remaining = self.config.duration - elapsed
            print(f"  {elapsed:.0f}s elapsed, {remaining:.0f}s remaining...")
        
        # Stop all modules
        print()
        print("Stopping modules...")
        for module in self.modules:
            module.stop()
        
        # Print results
        self.print_results()
    
    def print_results(self):
        """Print test results"""
        print()
        print("=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print()
        
        total_requests = 0
        total_errors = 0
        
        for module in self.modules:
            results = module.metrics.get_results()
            total_requests += results['total_requests']
            total_errors += results['error_count']
            
            print(f"Module: {results['module']}")
            print(f"  Total Requests:     {results['total_requests']}")
            print(f"  Errors:             {results['error_count']} ({results['error_rate']:.2f}%)")
            print(f"  Requests/sec:       {results['requests_per_second']:.2f}")
            print(f"  Latency (avg):      {results['avg_latency']*1000:.1f}ms")
            print(f"  Latency (p50):      {results['p50_latency']*1000:.1f}ms")
            print(f"  Latency (p95):      {results['p95_latency']*1000:.1f}ms")
            print(f"  Latency (p99):      {results['p99_latency']*1000:.1f}ms")
            print(f"  Latency (min/max):  {results['min_latency']*1000:.1f}ms / {results['max_latency']*1000:.1f}ms")
            print()
        
        print("-" * 60)
        print(f"TOTAL: {total_requests} requests, {total_errors} errors")
        print("=" * 60)


# ============================================================================
# CLI
# ============================================================================

def create_default_config() -> str:
    """Return default config YAML content"""
    return """# Puzzleboss Load Test Configuration
#
# Copy this file to loadtest_config.yaml and customize as needed.
#
# Each module can be individually enabled/disabled and configured with:
#   - enabled: true/false
#   - threads: number of concurrent threads
#   - delay: seconds to wait between requests per thread

api_base: "http://localhost:5000"
php_base: "https://localhost/pb"
duration: 60  # seconds

modules:
  php_puzzleboss:
    enabled: true
    threads: 2
    delay: 0.5

  php_status:
    enabled: false
    threads: 2
    delay: 0.5

  php_editpuzzle:
    enabled: false
    threads: 2
    delay: 0.5

  api_solver_assignment:
    enabled: false
    threads: 2
    delay: 0.2

  api_status_changing:
    enabled: false
    threads: 2
    delay: 0.2

  api_location_updating:
    enabled: false
    threads: 1
    delay: 0.5

  api_sheet_simulation:
    enabled: false
    threads: 4
    delay: 0.1

  api_commenting:
    enabled: false
    threads: 1
    delay: 0.5

  api_tagging:
    enabled: false
    threads: 2
    delay: 0.2

  api_tag_searching:
    enabled: false
    threads: 2
    delay: 0.2
"""


def main():
    parser = argparse.ArgumentParser(description='Puzzleboss Load Testing Framework')
    parser.add_argument('--config', '-c', help='Path to config YAML file')
    parser.add_argument('--duration', '-d', type=int, help='Test duration in seconds')
    parser.add_argument('--api-base', help='API base URL')
    parser.add_argument('--php-base', help='PHP base URL')
    parser.add_argument('--skip-setup', '-s', action='store_true',
                        help='Skip empty hunt check and test data loading (use existing hunt)')
    parser.add_argument('--generate-config', action='store_true', 
                        help='Generate a default config file')
    
    args = parser.parse_args()
    
    if args.generate_config:
        config_content = create_default_config()
        with open('loadtest_config.yaml', 'w') as f:
            f.write(config_content)
        print("Generated loadtest_config.yaml")
        return
    
    # Load or create config
    config_path = args.config
    
    # Auto-detect config file in same directory if not specified
    if not config_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_config = os.path.join(script_dir, 'loadtest_config.yaml')
        if os.path.exists(default_config):
            config_path = default_config
            print(f"Using config: {config_path}")
    
    if config_path:
        config = load_config(config_path)
    else:
        print("ERROR: No config file found.")
        print("  Create scripts/loadtest_config.yaml from scripts/loadtest_config-EXAMPLE.yaml")
        print("  Or specify with: --config <path>")
        sys.exit(1)
    
    # Override with CLI args
    if args.duration:
        config.duration = args.duration
    if args.api_base:
        config.api_base = args.api_base
    if args.php_base:
        config.php_base = args.php_base
    
    # Run the load test
    runner = LoadTestRunner(config)
    runner.run(skip_setup=args.skip_setup)


if __name__ == '__main__':
    main()

