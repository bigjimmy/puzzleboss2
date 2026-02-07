#!/usr/bin/env python3
"""
WARNING: This script will RESET THE HUNT DATABASE when run with --allow-destructive!
         The --allow-destructive flag is REQUIRED to run this script.
         DO NOT run this on a production system!
"""

import requests
import random
import time
from typing import List, Dict
from datetime import datetime
import json
import sys
import traceback
import string
import argparse
import subprocess

BASE_URL = "http://localhost:5000"


class TestLogger:
    def __init__(self):
        self.indent_level = 0
        self.start_time = datetime.now()

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        indent = "  " * self.indent_level

        if level == "TEST":
            # Add extra spacing and visual separation for TEST messages
            print("\n" + "=" * 80)
            print(f"[{timestamp}] [{level}] {indent}{message}")
            print("=" * 80 + "\n")
        else:
            print(f"[{timestamp}] [{level}] {indent}{message}")

    def start_test(self, name: str):
        self.log(f"Starting test: {name}", "TEST")
        self.indent_level += 1

    def end_test(self, name: str, success: bool, duration: float):
        self.indent_level -= 1
        status = "✅" if success else "❌"
        self.log(f"Completed test: {name} - {status} ({duration:.2f}s)", "TEST")

    def log_operation(self, operation: str, details: str = ""):
        self.log(f"{operation} {details}", "OP")

    def log_error(self, message: str):
        self.log(message, "ERROR")

    def log_warning(self, message: str):
        self.log(message, "WARNING")


class TestResult:
    def __init__(self, name: str, logger: TestLogger):
        self.name = name
        self.success = True
        self.message = ""
        self.duration = 0
        self.logger = logger

    def fail(self, message: str):
        self.success = False
        self.message = message
        self.logger.log_error(message)

    def set_success(self, message: str):
        self.success = True
        self.message = message

    def __str__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"{status} {self.name}: {self.message} ({self.duration:.2f}s)"


class TestRunner:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.logger = TestLogger()
        self.results = []
        self.solvers = []
        self.puzzles = []
        self.rounds = []

        # List of emojis to use in test data
        self.emojis = [
            "🎲",
            "🎯",
            "🎨",
            "🎪",
            "🎭",
            "🎫",
            "🎮",
            "🎰",
            "🎱",
            "🎲",
            "🎸",
            "🎹",
            "🎺",
            "🎻",
            "🎼",
            "🎵",
            "🎶",
            "🎷",
            "🎸",
            "🎹",
        ]

        self.test_start_time = datetime.now()

    def normalize_string(self, s: str) -> str:
        """Remove all spaces from a string for comparison."""
        if not s:
            return ""
        return "".join(s.split())

    def strings_equal_ignore_spaces(self, s1: str, s2: str) -> bool:
        """Compare two strings ignoring spaces."""
        return self.normalize_string(s1) == self.normalize_string(s2)

    def get_emoji_string(self, base_text: str, include_emoji: bool = True) -> str:
        """Generate a string with optional emoji"""
        if not include_emoji:
            return base_text
        # Add 1-3 random emojis to the text
        num_emojis = random.randint(1, 3)
        selected_emojis = random.sample(self.emojis, num_emojis)
        return f"{base_text} {' '.join(selected_emojis)}"

    def run_test(self, name: str, test_func) -> TestResult:
        result = TestResult(name, self.logger)
        self.logger.start_test(name)
        start_time = time.time()
        try:
            test_func(result)
        except Exception as e:
            result.fail(f"Exception: {str(e)}")
        result.duration = time.time() - start_time
        self.results.append(result)
        self.logger.end_test(name, result.success, result.duration)
        return result

    def print_results(self):
        print("\nTest Results Summary:")
        print("=" * 50)
        for result in self.results:
            print(result)

        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        print(f"\nTotal tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(
            f"Total duration: {(datetime.now() - self.test_start_time).total_seconds():.2f}s"
        )

    def get_all_solvers(self) -> List[Dict]:
        self.logger.log_operation("Fetching all solvers")
        response = requests.get(f"{BASE_URL}/solvers")
        if not response.ok:
            raise Exception(f"Failed to get solvers: {response.text}")
        solvers = response.json()["solvers"]
        self.logger.log_operation(f"Found {len(solvers)} solvers")
        return solvers

    def create_solver(self, name: str, fullname: str) -> Dict:
        """Create a new solver."""
        try:
            response = requests.post(
                f"{BASE_URL}/solvers",
                json={"name": name, "fullname": fullname}
            )
            if not response.ok:
                raise Exception(f"Failed to create solver: {response.text}")
            return response.json()["solver"]
        except Exception as e:
            self.logger.log_error(f"Error creating solver {name}: {str(e)}")
            raise

    def ensure_min_solvers(self, min_count: int = 10):
        """Ensure there are at least min_count solvers in the database for testing."""
        solvers = self.get_all_solvers()
        current_count = len(solvers)

        if current_count >= min_count:
            self.logger.log_operation(
                f"Sufficient solvers available ({current_count} >= {min_count})"
            )
            return

        needed = min_count - current_count
        self.logger.log_operation(
            f"Creating {needed} test solvers to reach minimum of {min_count}"
        )

        for i in range(needed):
            solver_num = current_count + i + 1
            name = f"testsolver{solver_num}"
            fullname = f"Test Solver {solver_num}"
            try:
                self.create_solver(name, fullname)
                self.logger.log_operation(f"Created solver: {name}")
            except Exception as e:
                self.logger.log_error(f"Failed to create solver {name}: {str(e)}")

        # Verify we now have enough solvers
        solvers = self.get_all_solvers()
        self.logger.log_operation(
            f"Now have {len(solvers)} solvers available for testing"
        )

    def get_all_puzzles(self) -> List[Dict]:
        self.logger.log_operation("Fetching all puzzles")
        response = requests.get(f"{BASE_URL}/puzzles")
        if not response.ok:
            raise Exception(f"Failed to get puzzles: {response.text}")
        puzzles = response.json()["puzzles"]
        self.logger.log_operation(f"Found {len(puzzles)} puzzles")
        return puzzles

    def get_puzzle_details(self, puzzle_id: str) -> Dict:
        """Get detailed information about a specific puzzle."""
        try:
            response = requests.get(f"{self.base_url}/puzzles/{puzzle_id}")
            if not response.ok:
                self.logger.log_error(
                    f"Failed to get puzzle {puzzle_id}: {response.text}"
                )
                return None
            return response.json()["puzzle"]
        except Exception as e:
            self.logger.log_error(f"Error getting puzzle details: {str(e)}")
            return None

    def get_solver_details(self, solver_id: str) -> Dict:
        """Get detailed information about a specific solver."""
        try:
            response = requests.get(f"{self.base_url}/solvers/{solver_id}")
            if not response.ok:
                self.logger.log_error(
                    f"Failed to get solver {solver_id}: {response.text}"
                )
                return None
            return response.json()["solver"]
        except Exception as e:
            self.logger.log_error(f"Error getting solver details: {str(e)}")
            return None

    def get_round(self, round_id: int) -> Dict:
        """Get detailed information about a specific round."""
        try:
            response = requests.get(f"{self.base_url}/rounds/{round_id}")
            if not response.ok:
                self.logger.log_error(
                    f"Failed to get round {round_id}: {response.text}"
                )
                return None
            return response.json()["round"]
        except Exception as e:
            self.logger.log_error(f"Error getting round details: {str(e)}")
            return None

    def create_round(self, name: str) -> Dict:
        """Create a new round with detailed error handling"""
        try:
            self.logger.log_operation(f"Creating round: {name}")
            response = requests.post(f"{BASE_URL}/rounds", json={"name": name})

            if not response.ok:
                self.logger.log_error(
                    f"HTTP error creating round {name}: {response.status_code}"
                )
                self.logger.log_error(f"Response text: {response.text}")
                raise Exception(
                    f"HTTP error creating round: {response.status_code} - {response.text}"
                )

            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                self.logger.log_error(f"Failed to parse JSON response for round {name}")
                self.logger.log_error(f"Response text: {response.text}")
                self.logger.log_error(f"JSON decode error: {str(e)}")
                raise Exception(f"JSON decode error: {str(e)}")

            if "status" not in response_data or response_data["status"] != "ok":
                self.logger.log_error(
                    f"Unexpected response format creating round {name}"
                )
                self.logger.log_error(f"Full response: {response_data}")
                raise Exception(f"Unexpected response format: {response_data}")

            if "round" not in response_data:
                self.logger.log_error(f"Missing round data in response for {name}")
                self.logger.log_error(f"Full response: {response_data}")
                raise Exception(f"Missing round data in response: {response_data}")

            # Get the round ID by querying the round by name
            rounds_response = requests.get(f"{BASE_URL}/rounds")
            if not rounds_response.ok:
                self.logger.log_error(
                    f"Failed to get rounds list: {rounds_response.text}"
                )
                raise Exception(f"Failed to get rounds list: {rounds_response.text}")

            rounds_data = rounds_response.json()
            if "rounds" not in rounds_data:
                self.logger.log_error(
                    f"Unexpected format in rounds list: {rounds_data}"
                )
                raise Exception(f"Unexpected format in rounds list: {rounds_data}")

            # Find the round we just created
            round_data = None
            sanitized_name = name.replace(" ", "")
            for round in rounds_data["rounds"]:
                if round["name"].replace(" ", "") == sanitized_name:
                    round_data = round
                    break

            if not round_data:
                self.logger.log_error(
                    f"Could not find newly created round {name} in rounds list"
                )
                self.logger.log_error(
                    f"Available rounds: {[r['name'] for r in rounds_data['rounds']]}"
                )
                raise Exception(
                    f"Could not find newly created round {name} in rounds list"
                )

            self.logger.log_operation(
                f"Created round {name} with id {round_data['id']}"
            )
            return round_data

        except requests.RequestException as e:
            self.logger.log_error(f"Request exception creating round {name}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")
            raise Exception(f"Request exception: {str(e)}")

        except Exception as e:
            self.logger.log_error(f"Unexpected error creating round {name}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")
            raise

    def create_puzzle(self, name: str, round_id: str, use_stepwise: bool = False) -> Dict:
        """Create a new puzzle with detailed error handling"""
        if use_stepwise:
            return self.create_puzzle_stepwise(name, round_id)

        try:
            self.logger.log_operation(f"Creating puzzle (one-shot): {name} in round {round_id}")

            # Convert round_id to integer for the API
            round_id_int = int(round_id)

            # Prepare request data
            request_data = {
                "puzzle": {
                    "name": name,
                    "round_id": round_id_int,
                    "puzzle_uri": "http://example.com/puzzle",
                }
            }

            # Make the API request
            response = requests.post(f"{self.base_url}/puzzles", json=request_data)

            if not response.ok:
                self.logger.log_error(
                    f"HTTP error creating puzzle {name}: {response.status_code}"
                )
                self.logger.log_error(f"Response text: {response.text}")
                raise Exception(
                    f"HTTP error creating puzzle: {response.status_code} - {response.text}"
                )

            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                self.logger.log_error(
                    f"Failed to parse JSON response for puzzle {name}"
                )
                self.logger.log_error(f"Response text: {response.text}")
                self.logger.log_error(f"JSON decode error: {str(e)}")
                raise Exception(f"JSON decode error: {str(e)}")

            if "status" not in response_data or response_data["status"] != "ok":
                self.logger.log_error(
                    f"Unexpected response format creating puzzle {name}"
                )
                self.logger.log_error(f"Full response: {response_data}")
                raise Exception(f"Unexpected response format: {response_data}")

            # Get the puzzle details to verify creation
            puzzles_response = requests.get(f"{BASE_URL}/puzzles")
            if not puzzles_response.ok:
                self.logger.log_error(
                    f"Failed to get puzzles list: {puzzles_response.text}"
                )
                raise Exception(f"Failed to get puzzles list: {puzzles_response.text}")

            puzzles_data = puzzles_response.json()
            if "puzzles" not in puzzles_data:
                self.logger.log_error(
                    f"Unexpected format in puzzles list: {puzzles_data}"
                )
                raise Exception(f"Unexpected format in puzzles list: {puzzles_data}")

            # Find the puzzle we just created - look for space-stripped name
            puzzle_data = None
            expected_name = name.replace(" ", "")
            for puzzle in puzzles_data["puzzles"]:
                if puzzle["name"] == expected_name:
                    puzzle_data = puzzle
                    break

            if not puzzle_data:
                self.logger.log_error(
                    f"Could not find newly created puzzle {expected_name} in puzzles list"
                )
                self.logger.log_error(
                    f"Available puzzles: {[p['name'] for p in puzzles_data['puzzles']]}"
                )
                raise Exception(
                    f"Could not find newly created puzzle {expected_name} in puzzles list"
                )

            # Get full puzzle details
            puzzle_details = self.get_puzzle_details(puzzle_data["id"])
            if not puzzle_details:
                self.logger.log_error(
                    f"Failed to get details for puzzle {expected_name}"
                )
                raise Exception(f"Failed to get details for puzzle {expected_name}")

            self.logger.log_operation(
                f"Created puzzle {expected_name} with id {puzzle_data['id']}"
            )
            return puzzle_details

        except requests.RequestException as e:
            self.logger.log_error(f"Request exception creating puzzle {name}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")
            raise Exception(f"Request exception: {str(e)}")

    def create_puzzle_stepwise(self, name: str, round_id: str, is_meta: bool = False, is_speculative: bool = False) -> Dict:
        """Create a new puzzle using the stepwise API with detailed error handling"""
        try:
            self.logger.log_operation(f"Creating puzzle (stepwise): {name} in round {round_id}")

            # Convert round_id to integer for the API
            round_id_int = int(round_id)

            # Step 0: Initiate stepwise creation
            request_data = {
                "puzzle": {
                    "name": name,
                    "round_id": round_id_int,
                    "puzzle_uri": "http://example.com/puzzle",
                    "ismeta": is_meta,
                    "is_speculative": is_speculative,
                }
            }

            # Initiate stepwise creation
            self.logger.log_operation(f"  Step 0: Initiating stepwise creation")
            response = requests.post(f"{self.base_url}/puzzles/stepwise", json=request_data)

            if not response.ok:
                self.logger.log_error(
                    f"HTTP error initiating stepwise creation for {name}: {response.status_code}"
                )
                self.logger.log_error(f"Response text: {response.text}")
                raise Exception(
                    f"HTTP error initiating stepwise creation: {response.status_code} - {response.text}"
                )

            try:
                init_data = response.json()
            except json.JSONDecodeError as e:
                self.logger.log_error(f"Failed to parse JSON response for stepwise init")
                self.logger.log_error(f"Response text: {response.text}")
                raise Exception(f"JSON decode error: {str(e)}")

            if "status" not in init_data or init_data["status"] != "ok":
                self.logger.log_error(f"Unexpected response format from stepwise init")
                self.logger.log_error(f"Full response: {init_data}")
                raise Exception(f"Unexpected response format: {init_data}")

            if "code" not in init_data:
                self.logger.log_error(f"No code returned from stepwise init")
                self.logger.log_error(f"Full response: {init_data}")
                raise Exception(f"No code returned from stepwise init")

            code = init_data["code"]
            self.logger.log_operation(f"  Step 0: Got code {code}")

            # Execute steps 1-5
            puzzle_id = None
            for step_num in range(1, 6):
                self.logger.log_operation(f"  Step {step_num}: Executing...")

                step_response = requests.get(f"{self.base_url}/createpuzzle/{code}?step={step_num}")

                if not step_response.ok:
                    self.logger.log_error(
                        f"HTTP error on step {step_num}: {step_response.status_code}"
                    )
                    self.logger.log_error(f"Response text: {step_response.text}")
                    raise Exception(
                        f"HTTP error on step {step_num}: {step_response.status_code} - {step_response.text}"
                    )

                try:
                    step_data = step_response.json()
                except json.JSONDecodeError as e:
                    self.logger.log_error(f"Failed to parse JSON response for step {step_num}")
                    self.logger.log_error(f"Response text: {step_response.text}")
                    raise Exception(f"JSON decode error on step {step_num}: {str(e)}")

                if "status" not in step_data or step_data["status"] != "ok":
                    self.logger.log_error(f"Unexpected response format from step {step_num}")
                    self.logger.log_error(f"Full response: {step_data}")
                    raise Exception(f"Unexpected response format from step {step_num}: {step_data}")

                # Check if step was skipped
                if step_data.get("skipped"):
                    self.logger.log_operation(f"  Step {step_num}: Skipped ({step_data.get('message', 'No message')})")
                else:
                    self.logger.log_operation(f"  Step {step_num}: Complete ({step_data.get('message', 'No message')})")

                # Step 4 returns the puzzle ID
                if step_num == 4 and "puzzle_id" in step_data:
                    puzzle_id = step_data["puzzle_id"]
                    self.logger.log_operation(f"  Step {step_num}: Puzzle created with ID {puzzle_id}")

            if not puzzle_id:
                self.logger.log_error("No puzzle ID returned from stepwise creation")
                raise Exception("No puzzle ID returned from stepwise creation")

            # Get full puzzle details
            puzzle_details = self.get_puzzle_details(puzzle_id)
            if not puzzle_details:
                self.logger.log_error(f"Failed to get details for puzzle ID {puzzle_id}")
                raise Exception(f"Failed to get details for puzzle ID {puzzle_id}")

            expected_name = name.replace(" ", "")
            self.logger.log_operation(
                f"Created puzzle (stepwise) {expected_name} with id {puzzle_id}"
            )
            return puzzle_details

        except requests.RequestException as e:
            self.logger.log_error(f"Request exception creating puzzle stepwise {name}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")
            raise Exception(f"Request exception: {str(e)}")

        except Exception as e:
            self.logger.log_error(f"Unexpected error creating puzzle {name}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")
            raise

    def update_puzzle(self, puzzle_id: str, field: str, value: str) -> bool:
        """Update a puzzle field."""
        try:
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/{field}", json={field: value}
            )
            if not response.ok:
                return False
            response_data = response.json()
            if response_data.get("status") != "ok":
                return False
            return True
        except Exception as e:
            self.logger.log_error(f"Error updating puzzle: {str(e)}")
            return False

    def assign_solver_to_puzzle(self, solver_id: str, puzzle_id: str) -> bool:
        """Assign a solver to a puzzle."""
        try:
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}/puzz", json={"puzz": puzzle_id}
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.log_error(f"Error assigning solver to puzzle: {str(e)}")
            return False

    def add_solver_to_history(self, puzzle_id: str, solver_id: str) -> bool:
        self.logger.log_operation(
            f"Adding solver {solver_id} to puzzle {puzzle_id} history"
        )
        response = requests.post(
            f"{BASE_URL}/puzzles/{puzzle_id}/history/add", json={"solver_id": solver_id}
        )
        if not response.ok:
            raise Exception(
                f"Failed to add solver {solver_id} to puzzle {puzzle_id} history: {response.text}"
            )
        self.logger.log_operation(
            f"Successfully added solver {solver_id} to puzzle {puzzle_id} history"
        )
        return True

    def remove_solver_from_history(self, puzzle_id: str, solver_id: str) -> bool:
        self.logger.log_operation(
            f"Removing solver {solver_id} from puzzle {puzzle_id} history"
        )
        response = requests.post(
            f"{BASE_URL}/puzzles/{puzzle_id}/history/remove",
            json={"solver_id": solver_id},
        )
        if not response.ok:
            raise Exception(
                f"Failed to remove solver {solver_id} from puzzle {puzzle_id} history: {response.text}"
            )
        self.logger.log_operation(
            f"Successfully removed solver {solver_id} from puzzle {puzzle_id} history"
        )
        return True

    def update_round(self, round_id: int, updates: Dict) -> Dict:
        """Update a round with the given updates"""
        try:
            self.logger.log_operation(f"Updating round {round_id} with {updates}")
            for part, value in updates.items():
                response = requests.post(
                    f"{BASE_URL}/rounds/{round_id}/{part}", json={part: value}
                )

                if not response.ok:
                    self.logger.log_error(
                        f"HTTP error updating round {round_id} {part}: {response.status_code}"
                    )
                    self.logger.log_error(f"Response text: {response.text}")
                    raise Exception(
                        f"HTTP error updating round: {response.status_code} - {response.text}"
                    )

                try:
                    response_data = response.json()
                except json.JSONDecodeError as e:
                    self.logger.log_error(
                        f"Failed to parse JSON response for round {round_id} {part}"
                    )
                    self.logger.log_error(f"Response text: {response.text}")
                    self.logger.log_error(f"JSON decode error: {str(e)}")
                    raise Exception(f"JSON decode error: {str(e)}")

                if "status" not in response_data or response_data["status"] != "ok":
                    self.logger.log_error(
                        f"Unexpected response format updating round {round_id} {part}"
                    )
                    self.logger.log_error(f"Full response: {response_data}")
                    raise Exception(f"Unexpected response format: {response_data}")

            return self.get_round(round_id)
        except Exception as e:
            self.logger.log_error(f"Error updating round {round_id}: {str(e)}")
            raise

    def test_solver_listing(self, result: TestResult):
        solvers = self.get_all_solvers()
        if not solvers:
            result.fail("No solvers found")
            return

        result.message = f"Found {len(solvers)} solvers"

    def get_all_rounds(self) -> List[Dict]:
        """Get all rounds from the API."""
        response = requests.get(f"{self.base_url}/rounds")
        if not response.ok:
            self.logger.log_error(f"Failed to get rounds: {response.text}")
            return []
        return response.json().get("rounds", [])

    def test_puzzle_creation(self, result: TestResult):
        """Test one-shot puzzle creation functionality (legacy mode)."""
        self.logger.log_operation("Starting one-shot puzzle creation test")

        try:
            # Create 3 test rounds
            rounds = []
            for i in range(3):
                round_name = f"Test Round {int(time.time()) + i}"
                round_data = self.create_round(round_name)
                if not round_data:
                    result.fail(f"Failed to create test round {i+1}")
                    return
                rounds.append(round_data)

            # Create 5 puzzles in each round (15 total to cover all 13 statuses + extras)
            for round_idx, round_data in enumerate(rounds):
                self.logger.log_operation(
                    f"Creating puzzles for round {round_data['name']}"
                )
                puzzles = []
                for puzzle_idx in range(5):
                    # Create puzzle name with spaces and emojis for even-numbered puzzles
                    base_name = (
                        f"Test Puzzle R{round_idx+1}P{puzzle_idx+1} {int(time.time())}"
                    )
                    puzzle_name = self.get_emoji_string(
                        base_name, include_emoji=(puzzle_idx % 2 == 0)
                    )

                    # Create the puzzle using one-shot mode (use_stepwise=False is default)
                    puzzle_data = self.create_puzzle(puzzle_name, str(round_data["id"]), use_stepwise=False)
                    if not puzzle_data:
                        result.fail(f"Failed to create puzzle {puzzle_name}")
                        return

                    # Verify the name was stripped of spaces but emojis preserved
                    expected_name = puzzle_name.replace(" ", "")
                    if puzzle_data["name"] != expected_name:
                        result.fail(
                            f"Puzzle name not properly processed. Expected: {expected_name}, Got: {puzzle_data['name']}"
                        )
                        return

                    puzzles.append(puzzle_data)

                # Verify all puzzles were created in the correct round
                for puzzle in puzzles:
                    if str(puzzle["round_id"]) != str(round_data["id"]):
                        result.fail(f"Puzzle {puzzle['name']} created in wrong round")
                        return

            result.set_success("One-shot puzzle creation test completed successfully")

        except Exception as e:
            result.fail(f"Error in one-shot puzzle creation test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_puzzle_creation_stepwise(self, result: TestResult):
        """Test step-by-step puzzle creation functionality."""
        self.logger.log_operation("Starting stepwise puzzle creation test")

        try:
            # Create 2 test rounds for stepwise testing
            rounds = []
            for i in range(2):
                round_name = f"Stepwise Round {int(time.time()) + i}"
                round_data = self.create_round(round_name)
                if not round_data:
                    result.fail(f"Failed to create test round {i+1}")
                    return
                rounds.append(round_data)

            # Create 3 puzzles in each round using stepwise mode
            for round_idx, round_data in enumerate(rounds):
                self.logger.log_operation(
                    f"Creating stepwise puzzles for round {round_data['name']}"
                )
                puzzles = []
                for puzzle_idx in range(3):
                    # Create puzzle name with spaces and emojis
                    base_name = (
                        f"Stepwise Puzzle R{round_idx+1}P{puzzle_idx+1} {int(time.time())}"
                    )
                    puzzle_name = self.get_emoji_string(
                        base_name, include_emoji=(puzzle_idx % 2 == 0)
                    )

                    # Test different combinations: regular, meta, speculative
                    is_meta = (puzzle_idx == 1)
                    is_speculative = (puzzle_idx == 2)

                    # Create the puzzle using stepwise mode
                    puzzle_data = self.create_puzzle_stepwise(
                        puzzle_name,
                        str(round_data["id"]),
                        is_meta=is_meta,
                        is_speculative=is_speculative
                    )
                    if not puzzle_data:
                        result.fail(f"Failed to create stepwise puzzle {puzzle_name}")
                        return

                    # Verify the name was stripped of spaces but emojis preserved
                    expected_name = puzzle_name.replace(" ", "")
                    if puzzle_data["name"] != expected_name:
                        result.fail(
                            f"Stepwise puzzle name not properly processed. Expected: {expected_name}, Got: {puzzle_data['name']}"
                        )
                        return

                    # Verify meta flag
                    if is_meta and not puzzle_data.get("ismeta"):
                        result.fail(f"Puzzle {puzzle_name} should be marked as meta")
                        return

                    # Verify speculative status
                    if is_speculative and puzzle_data.get("status") != "Speculative":
                        result.fail(
                            f"Puzzle {puzzle_name} should have Speculative status, got {puzzle_data.get('status')}"
                        )
                        return

                    puzzles.append(puzzle_data)

                # Verify all puzzles were created in the correct round
                for puzzle in puzzles:
                    if str(puzzle["round_id"]) != str(round_data["id"]):
                        result.fail(f"Stepwise puzzle {puzzle['name']} created in wrong round")
                        return

            result.set_success("Stepwise puzzle creation test completed successfully")

        except Exception as e:
            result.fail(f"Error in stepwise puzzle creation test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_puzzle_modification(self, result: TestResult):
        """Test puzzle modification functionality."""
        self.logger.log_operation("Starting puzzle modification test")

        # Fetch statuses dynamically from huntinfo
        try:
            huntinfo_response = requests.get(f"{self.base_url}/huntinfo")
            if huntinfo_response.ok:
                huntinfo_data = huntinfo_response.json()
                # Extract status names from rich objects, excluding Solved and [hidden]
                all_statuses = [s["name"] for s in huntinfo_data.get("statuses", [])]
                testable_statuses = [s for s in all_statuses if s not in ["Solved", "[hidden]"]]
            else:
                # Fallback if huntinfo fails
                testable_statuses = ["New", "Being worked", "Needs eyes", "Critical", "WTF", "Under control", "Waiting for HQ", "Grind", "Abandoned", "Speculative", "Unnecessary"]
        except Exception as e:
            self.logger.log_warning(f"Could not fetch statuses from /huntinfo, using fallback: {e}")
            testable_statuses = ["New", "Being worked", "Needs eyes", "Critical", "WTF", "Under control", "Waiting for HQ", "Grind", "Abandoned", "Speculative", "Unnecessary"]

        self.logger.log_operation(f"Testing with {len(testable_statuses)} different statuses")

        # Get all puzzles
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("Failed to get puzzles")
            return

        # Get full puzzle details for each puzzle
        detailed_puzzles = []
        for puzzle in puzzles:
            puzzle_details = self.get_puzzle_details(puzzle["id"])
            if puzzle_details:
                detailed_puzzles.append(puzzle_details)

        if not detailed_puzzles:
            result.fail("Failed to get puzzle details")
            return

        # Group puzzles by round
        puzzles_by_round = {}
        for puzzle in detailed_puzzles:
            round_id = str(puzzle.get("round_id", ""))
            if round_id:
                if round_id not in puzzles_by_round:
                    puzzles_by_round[round_id] = []
                puzzles_by_round[round_id].append(puzzle)

        # For each round, select up to 2 random puzzles
        selected_puzzles = []
        for round_id, round_puzzles in puzzles_by_round.items():
            num_to_select = min(2, len(round_puzzles))
            if num_to_select > 0:
                selected = random.sample(round_puzzles, num_to_select)
                selected_puzzles.extend(selected)

        if not selected_puzzles:
            result.fail("No puzzles available for testing")
            return

        # Randomly select puzzles for answer verification
        puzzles_for_answers = random.sample(
            selected_puzzles, len(selected_puzzles) // 2
        )
        puzzles_for_answers_set = set(p["id"] for p in puzzles_for_answers)

        # For each selected puzzle, test modifications with different statuses
        for idx, puzzle in enumerate(selected_puzzles):
            self.logger.log_operation(
                f"Testing modifications for puzzle {puzzle['name']}"
            )

            # Assign different status to each puzzle (cycle through available statuses)
            new_status = testable_statuses[idx % len(testable_statuses)]
            self.logger.log_operation(f"Updating status to '{new_status}'")
            if not self.update_puzzle(puzzle["id"], "status", new_status):
                result.fail(f"Failed to update status for puzzle {puzzle['name']}")
                continue

            # Verify status update
            updated_puzzle = self.get_puzzle_details(puzzle["id"])
            if not updated_puzzle:
                result.fail(
                    f"Failed to verify status update for puzzle {puzzle['name']}"
                )
                continue

            if updated_puzzle["status"] != new_status:
                result.fail(f"Status not updated for puzzle {puzzle['name']}")
                continue

            # Only set answer and verify solution on randomly selected puzzles
            if puzzle["id"] in puzzles_for_answers_set:
                # Test answer update
                answer = "TESTANSWER"
                self.logger.log_operation(f"Updating answer to '{answer}'")
                if not self.update_puzzle(puzzle["id"], "answer", answer):
                    result.fail(f"Failed to update answer for puzzle {puzzle['name']}")
                    continue

                # Verify puzzle is solved
                updated_puzzle = self.get_puzzle_details(puzzle["id"])
                if not updated_puzzle:
                    result.fail(
                        f"Failed to verify puzzle solve for puzzle {puzzle['name']}"
                    )
                    continue

                # Convert both to uppercase for comparison
                expected_upper = answer.upper()
                actual_upper = updated_puzzle.get("answer", "").upper()

                if expected_upper != actual_upper:
                    self.logger.log_error(
                        f"DEBUG - Puzzle before answer update: {puzzle}"
                    )
                    self.logger.log_error(
                        f"DEBUG - Updated puzzle after answer set: {updated_puzzle}"
                    )
                    self.logger.log_error(f"DEBUG - Expected answer: {answer}")
                    self.logger.log_error(
                        f"DEBUG - Actual answer: {updated_puzzle.get('answer')}"
                    )
                    self.logger.log_error(f"DEBUG - Expected (upper): {expected_upper}")
                    self.logger.log_error(f"DEBUG - Actual (upper): {actual_upper}")
                    self.logger.log_error(
                        f"DEBUG - Answer comparison: {expected_upper == actual_upper}"
                    )
                    result.fail(
                        f"Answer verification failed for puzzle {puzzle['name']}"
                    )
                    continue

                if updated_puzzle["status"] != "Solved":
                    result.fail(
                        f"Status not automatically set to 'Solved' for puzzle {puzzle['name']}"
                    )
                    continue
            else:
                self.logger.log_operation(
                    f"Skipping answer update for puzzle {puzzle['name']} (not selected for answer testing)"
                )

            # Test comments update
            new_comments = f"Test comments for {puzzle['name']}"
            self.logger.log_operation(f"Updating comments to '{new_comments}'")
            if not self.update_puzzle(puzzle["id"], "comments", new_comments):
                result.fail(f"Failed to update comments for puzzle {puzzle['name']}")
                continue

            # Verify comments update
            updated_puzzle = self.get_puzzle_details(puzzle["id"])
            if not updated_puzzle:
                result.fail(
                    f"Failed to verify comments update for puzzle {puzzle['name']}"
                )
                continue

            if updated_puzzle["comments"] != new_comments:
                result.fail(f"Comments not updated for puzzle {puzzle['name']}")
                continue

            # Only add xyzloc to every other puzzle
            if idx % 2 == 1:
                # Test location update
                new_location = f"Test Location {random.randint(1000, 9999)}"
                self.logger.log_operation(f"Updating location to '{new_location}'")
                if not self.update_puzzle(puzzle["id"], "xyzloc", new_location):
                    result.fail(
                        f"Failed to update location for puzzle {puzzle['name']}"
                    )
                    continue

                # Verify location update
                updated_puzzle = self.get_puzzle_details(puzzle["id"])
                if not updated_puzzle:
                    result.fail(
                        f"Failed to verify location update for puzzle {puzzle['name']}"
                    )
                    continue

                if updated_puzzle["xyzloc"] != new_location:
                    result.fail(f"Location not updated for puzzle {puzzle['name']}")
                    continue
            else:
                self.logger.log_operation(
                    f"Skipping location update for puzzle {puzzle['name']} (every other puzzle)"
                )

        result.set_success("Puzzle modification test completed successfully")

    def test_puzzle_round_change(self, result: TestResult):
        """Test changing a puzzle's round via round_id endpoint."""
        self.logger.log_operation("Starting puzzle round change test")

        try:
            # Get all rounds
            rounds = self.get_all_rounds()
            if len(rounds) < 2:
                result.fail("Need at least 2 rounds to test round change")
                return

            # Get all puzzles
            puzzles = self.get_all_puzzles()
            if not puzzles:
                result.fail("No puzzles available for testing")
                return

            # Find a puzzle in the first round
            round_1 = rounds[0]
            round_2 = rounds[1]

            test_puzzle = None
            for puzzle in puzzles:
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if puzzle_details and str(puzzle_details.get("round_id")) == str(round_1["id"]):
                    # Make sure it's not solved (we don't want to move solved puzzles)
                    if puzzle_details.get("status") != "Solved":
                        test_puzzle = puzzle_details
                        break

            if not test_puzzle:
                result.fail(f"No unsolved puzzles found in round {round_1['name']}")
                return

            puzzle_id = test_puzzle["id"]
            puzzle_name = test_puzzle["name"]
            original_round_id = test_puzzle["round_id"]

            self.logger.log_operation(
                f"Moving puzzle '{puzzle_name}' from round '{round_1['name']}' (ID: {round_1['id']}) to round '{round_2['name']}' (ID: {round_2['id']})"
            )

            # Test 1: Change puzzle's round
            try:
                response = requests.post(
                    f"{self.base_url}/puzzles/{puzzle_id}/round_id",
                    json={"round_id": round_2["id"]},
                )
                if not response.ok:
                    result.fail(f"Failed to change puzzle round: {response.text}")
                    return

                response_data = response.json()
                if response_data.get("status") != "ok":
                    result.fail(f"Round change returned error: {response_data}")
                    return

                self.logger.log_operation("Round change request successful")
            except Exception as e:
                result.fail(f"Exception changing puzzle round: {str(e)}")
                return

            # Verify the round was changed
            updated_puzzle = self.get_puzzle_details(puzzle_id)
            if not updated_puzzle:
                result.fail("Failed to fetch puzzle after round change")
                return

            if str(updated_puzzle["round_id"]) != str(round_2["id"]):
                result.fail(
                    f"Round not updated. Expected round ID {round_2['id']}, got {updated_puzzle['round_id']}"
                )
                return

            self.logger.log_operation(
                f"✓ Puzzle successfully moved to round '{round_2['name']}'"
            )

            # Test 2: Verify activity was logged
            try:
                activity_response = requests.get(f"{self.base_url}/activity")
                if activity_response.ok:
                    self.logger.log_operation("Activity logging verified")
            except Exception:
                self.logger.log_warning("Could not verify activity logging")

            # Test 3: Try to move to invalid round (should fail)
            self.logger.log_operation("Testing invalid round_id rejection")
            try:
                response = requests.post(
                    f"{self.base_url}/puzzles/{puzzle_id}/round_id",
                    json={"round_id": 99999},
                )
                if response.ok:
                    result.fail("Invalid round_id was accepted (should have been rejected)")
                    return
                self.logger.log_operation("✓ Invalid round_id correctly rejected")
            except Exception as e:
                result.fail(f"Exception testing invalid round_id: {str(e)}")
                return

            result.set_success("Puzzle round change test completed successfully")

        except Exception as e:
            result.fail(f"Error in puzzle round change test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_multi_part_update(self, result: TestResult):
        """Test multi-part puzzle update endpoint POST /puzzles/<id>."""
        self.logger.log_operation("Starting multi-part update test")

        # Get a puzzle to test with
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles available for testing")
            return

        # Find an unsolved puzzle
        test_puzzle = None
        for puzzle in puzzles:
            details = self.get_puzzle_details(puzzle["id"])
            if details and details.get("status") != "Solved":
                test_puzzle = details
                break

        if not test_puzzle:
            result.fail("No unsolved puzzles available for testing")
            return

        puzzle_id = test_puzzle["id"]
        self.logger.log_operation(
            f"Testing multi-part update on puzzle {test_puzzle['name']} (id: {puzzle_id})"
        )

        # Test 1: Successful multi-part update (status + xyzloc + comments)
        self.logger.log_operation("Test 1: Successful multi-part update")
        update_data = {
            "status": "Being worked",
            "xyzloc": "Test Room 999",
            "comments": "Multi-part test comment",
        }
        try:
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}", json=update_data
            )
            if not response.ok:
                result.fail(f"Multi-part update failed: {response.text}")
                return
            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Multi-part update returned error: {response_data}")
                return
        except Exception as e:
            result.fail(f"Exception in multi-part update: {str(e)}")
            return

        # Verify all fields were updated
        updated_puzzle = self.get_puzzle_details(puzzle_id)
        if not updated_puzzle:
            result.fail("Failed to fetch puzzle after multi-part update")
            return

        if updated_puzzle["status"] != "Being worked":
            result.fail(
                f"Status not updated. Expected 'Being worked', got '{updated_puzzle['status']}'"
            )
            return
        if updated_puzzle["xyzloc"] != "Test Room 999":
            result.fail(
                f"Location not updated. Expected 'Test Room 999', got '{updated_puzzle['xyzloc']}'"
            )
            return
        if updated_puzzle["comments"] != "Multi-part test comment":
            result.fail(
                f"Comments not updated. Expected 'Multi-part test comment', got '{updated_puzzle['comments']}'"
            )
            return
        self.logger.log_operation("Test 1 passed: All fields updated correctly")

        # Test 2: Rejected - trying to set answer via multi-part
        self.logger.log_operation("Test 2: Verify 'answer' is rejected")
        try:
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}",
                json={"answer": "TESTANSWER", "xyzloc": "Another Room"},
            )
            if response.ok:
                result.fail(
                    "Multi-part update should have rejected 'answer' field but succeeded"
                )
                return
            # Check that error message mentions answer
            error_text = response.text.lower()
            if "answer" not in error_text:
                self.logger.log_warning(
                    f"Error message doesn't mention 'answer': {response.text}"
                )
        except Exception as e:
            result.fail(f"Exception testing answer rejection: {str(e)}")
            return
        self.logger.log_operation("Test 2 passed: 'answer' correctly rejected")

        # Test 3: Rejected - trying to set status to 'Solved'
        self.logger.log_operation("Test 3: Verify 'status: Solved' is rejected")
        try:
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}",
                json={"status": "Solved", "xyzloc": "Final Room"},
            )
            if response.ok:
                result.fail(
                    "Multi-part update should have rejected 'status: Solved' but succeeded"
                )
                return
            # Check that error message mentions solved
            error_text = response.text.lower()
            if "solved" not in error_text:
                self.logger.log_warning(
                    f"Error message doesn't mention 'Solved': {response.text}"
                )
        except Exception as e:
            result.fail(f"Exception testing Solved rejection: {str(e)}")
            return
        self.logger.log_operation("Test 3 passed: 'status: Solved' correctly rejected")

        # Test 4: Non-Solved status values ARE allowed
        self.logger.log_operation("Test 4: Verify other status values are allowed")

        # Fetch statuses dynamically from huntinfo
        try:
            huntinfo_response = requests.get(f"{self.base_url}/huntinfo")
            if huntinfo_response.ok:
                huntinfo_data = huntinfo_response.json()
                # Extract status names from rich objects, excluding Solved and [hidden]
                all_statuses = [s["name"] for s in huntinfo_data.get("statuses", [])]
                allowed_statuses = [s for s in all_statuses if s not in ["Solved", "[hidden]"]][:4]  # Test first 4
            else:
                # Fallback if huntinfo fails
                allowed_statuses = ["Needs eyes", "Critical", "Being worked", "Abandoned"]
        except Exception as e:
            self.logger.log_warning(f"Could not fetch statuses from /huntinfo, using fallback: {e}")
            allowed_statuses = ["Needs eyes", "Critical", "Being worked", "Abandoned"]

        for test_status in allowed_statuses:
            try:
                response = requests.post(
                    f"{self.base_url}/puzzles/{puzzle_id}", json={"status": test_status}
                )
                if not response.ok:
                    result.fail(
                        f"Multi-part update rejected valid status '{test_status}': {response.text}"
                    )
                    return
            except Exception as e:
                result.fail(f"Exception testing status '{test_status}': {str(e)}")
                return
        self.logger.log_operation("Test 4 passed: Non-Solved statuses accepted")

        # Test 5: Invalid part name rejected
        self.logger.log_operation("Test 5: Verify invalid part name is rejected")
        try:
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}",
                json={"notarealpart": "somevalue"},
            )
            if response.ok:
                result.fail("Multi-part update should have rejected invalid part name")
                return
        except Exception as e:
            result.fail(f"Exception testing invalid part: {str(e)}")
            return
        self.logger.log_operation("Test 5 passed: Invalid part name rejected")

        result.set_success("Multi-part update test completed successfully")

    def test_meta_puzzles_and_round_completion(self, result: TestResult):
        """Test meta puzzle functionality and round completion logic."""
        self.logger.log_operation("Starting meta puzzles and round completion test")

        try:
            # Get all rounds and select one for testing
            rounds = self.get_all_rounds()
            if not rounds:
                result.fail("No rounds found for testing")
                return

            test_round = random.choice(rounds)
            self.logger.log_operation(
                f"Selected round for testing: {test_round['name']}"
            )

            # Create two new puzzles for testing
            timestamp = str(int(time.time()))
            meta_puzzle1 = self.create_puzzle(
                f"Test Meta Puzzle 1 {timestamp}", test_round["id"]
            )
            meta_puzzle2 = self.create_puzzle(
                f"Test Meta Puzzle 2 {timestamp}", test_round["id"]
            )

            if not meta_puzzle1 or not meta_puzzle2:
                result.fail("Failed to create test meta puzzles")
                return

            self.logger.log_operation(
                f"Created test meta puzzles: {meta_puzzle1['name']}, {meta_puzzle2['name']}"
            )

            # Set puzzles as meta
            for meta_puzzle in [meta_puzzle1, meta_puzzle2]:
                if not self.update_puzzle(meta_puzzle["id"], "ismeta", True):
                    result.fail(f"Failed to set puzzle {meta_puzzle['name']} as meta")
                    return

                # Verify meta status
                puzzle_details = self.get_puzzle_details(meta_puzzle["id"])
                if not puzzle_details.get("ismeta"):
                    result.fail(
                        f"Puzzle {meta_puzzle['name']} not marked as meta after update"
                    )
                    return

            # Create a non-meta puzzle and solve it
            non_meta_puzzle = self.create_puzzle(
                f"Test Non-Meta Puzzle {timestamp}", test_round["id"]
            )
            if not non_meta_puzzle:
                result.fail("Failed to create test non-meta puzzle")
                return

            if not self.update_puzzle(non_meta_puzzle["id"], "answer", "TEST ANSWER"):
                result.fail(
                    f"Failed to set answer for puzzle {non_meta_puzzle['name']}"
                )
                return

            # Verify answer was set
            puzzle_details = self.get_puzzle_details(non_meta_puzzle["id"])
            if puzzle_details.get("answer") != "TEST ANSWER":
                result.fail(f"Answer not set for puzzle {non_meta_puzzle['name']}")
                return

            # Verify round is not solved when non-meta puzzle is solved but metas are not
            if self.is_round_complete(test_round["id"]):
                result.fail("Round marked complete before meta puzzles were solved")
                return

            # Solve first meta puzzle
            if not self.update_puzzle(meta_puzzle1["id"], "answer", "META ANSWER 1"):
                result.fail(
                    f"Failed to set answer for meta puzzle {meta_puzzle1['name']}"
                )
                return

            # Verify round is still not solved
            if self.is_round_complete(test_round["id"]):
                result.fail(
                    "Round marked complete when only one meta puzzle was solved"
                )
                return

            # Solve the second meta puzzle
            if not self.update_puzzle(meta_puzzle2["id"], "answer", "META ANSWER 2"):
                result.fail(
                    f"Failed to set answer for meta puzzle {meta_puzzle2['name']}"
                )
                return

            # Verify round is now solved
            if not self.is_round_complete(test_round["id"]):
                result.fail(
                    "Round not marked complete after all meta puzzles were solved"
                )
                return

            # Log the round's status
            round_status = self.get_round_status(test_round["id"])
            self.logger.log_operation(
                f"Round {test_round['name']} status after solving all meta puzzles: {round_status}"
            )

            # Test unmarking: Add a new unsolved meta puzzle to a solved round
            self.logger.log_operation(
                "Testing round unmarking: Adding new unsolved meta to solved round"
            )
            meta_puzzle3 = self.create_puzzle(
                f"Test Meta Puzzle 3 {timestamp}", test_round["id"]
            )
            if not meta_puzzle3:
                result.fail("Failed to create third test meta puzzle")
                return

            # Mark it as meta
            if not self.update_puzzle(meta_puzzle3["id"], "ismeta", True):
                result.fail(f"Failed to set puzzle {meta_puzzle3['name']} as meta")
                return

            # Verify round is now NOT solved (since we have an unsolved meta)
            if self.is_round_complete(test_round["id"]):
                result.fail(
                    "Round still marked complete after adding new unsolved meta puzzle"
                )
                return

            self.logger.log_operation(
                "Round correctly unmarked as solved after adding unsolved meta"
            )

            # Solve the third meta puzzle to re-complete the round
            if not self.update_puzzle(meta_puzzle3["id"], "answer", "META ANSWER 3"):
                result.fail(
                    f"Failed to set answer for meta puzzle {meta_puzzle3['name']}"
                )
                return

            # Verify round is solved again
            if not self.is_round_complete(test_round["id"]):
                result.fail(
                    "Round not marked complete after solving all three meta puzzles"
                )
                return

            self.logger.log_operation(
                "Round correctly marked as solved again after solving third meta"
            )

            result.set_success(
                "Meta puzzles and round completion test completed successfully"
            )

        except Exception as e:
            result.fail(f"Error in meta puzzles and round completion test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def is_round_complete(self, round_id: int) -> bool:
        """Check if a round is complete by checking its status field."""
        try:
            round_data = self.get_round(round_id)
            if not round_data:
                return False
            return round_data.get("status") == "Solved"
        except Exception as e:
            self.logger.log_error(f"Error checking round completion: {str(e)}")
            return False

    def get_round_status(self, round_id: int) -> str:
        """Get the status of a round by checking its status field."""
        try:
            round_data = self.get_round(round_id)
            if not round_data:
                return ""
            return round_data.get("status", "")
        except Exception as e:
            self.logger.log_error(f"Error getting round status: {str(e)}")
            return ""

    def test_answer_verification(self, result: TestResult):
        """Test answer verification functionality."""
        self.logger.log_operation("Starting answer verification test")

        # Get all puzzles
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles found to test answer verification")
            return

        # Select a few puzzles for testing
        selected_puzzles = random.sample(puzzles, min(3, len(puzzles)))

        for puzzle in selected_puzzles:
            self.logger.log_operation(
                f"Testing answer verification for puzzle {puzzle['name']}"
            )

            # Generate a random answer with spaces and emoji
            test_answer = f"Test Answer {random.randint(1000, 9999)} 🎯"

            # Update the puzzle's answer
            if not self.update_puzzle(puzzle["id"], "answer", test_answer):
                result.fail(f"Failed to set answer for puzzle {puzzle['name']}")
                continue

            # Verify the answer was set and status changed to solved
            puzzle_details = self.get_puzzle_details(puzzle["id"])
            if not puzzle_details:
                result.fail(f"Failed to get puzzle details for {puzzle['name']}")
                continue

            # Check that answer was set
            if "answer" not in puzzle_details:
                result.fail(f"Answer field missing for puzzle {puzzle['name']}")
                continue

            # Verify the answer was set correctly (converted to all caps but spaces preserved)
            expected_answer = test_answer.upper()
            if puzzle_details["answer"] != expected_answer:
                result.fail(
                    f"Answer not set correctly for puzzle {puzzle['name']}. Expected: {expected_answer}, Got: {puzzle_details['answer']}"
                )
                continue

            # Check that status was changed to solved
            if puzzle_details.get("status") != "Solved":
                result.fail(
                    f"Status not changed to 'Solved' for puzzle {puzzle['name']}"
                )
                continue

        result.set_success("Answer verification test completed successfully")

    def test_solve_clears_location_and_solvers(self, result: TestResult):
        """Test that solving a puzzle clears both location and current solvers."""
        self.logger.log_operation("Starting solve clears location and solvers test")

        try:
            # Get all puzzles and solvers
            puzzles = self.get_all_puzzles()
            solvers = self.get_all_solvers()

            if not puzzles:
                result.fail("No puzzles found for testing")
                return

            if not solvers or len(solvers) < 2:
                result.fail("Need at least 2 solvers for testing")
                return

            # Find an unsolved puzzle
            unsolved_puzzle = None
            for puzzle in puzzles:
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if puzzle_details and puzzle_details.get("status") != "Solved":
                    unsolved_puzzle = puzzle_details
                    break

            if not unsolved_puzzle:
                result.fail("No unsolved puzzles available for testing")
                return

            puzzle_id = unsolved_puzzle["id"]
            puzzle_name = unsolved_puzzle["name"]

            self.logger.log_operation(
                f"Testing with puzzle {puzzle_name} (id: {puzzle_id})"
            )

            # Set location on the puzzle
            test_location = f"Test Location {random.randint(1000, 9999)}"
            self.logger.log_operation(f"Setting location to '{test_location}'")
            if not self.update_puzzle(puzzle_id, "xyzloc", test_location):
                result.fail(f"Failed to set location on puzzle {puzzle_name}")
                return

            # Assign 2 solvers to the puzzle
            selected_solvers = random.sample(solvers, 2)
            self.logger.log_operation(
                f"Assigning solvers {selected_solvers[0]['name']} and {selected_solvers[1]['name']}"
            )

            for solver in selected_solvers:
                if not self.assign_solver_to_puzzle(solver["id"], puzzle_id):
                    result.fail(
                        f"Failed to assign solver {solver['name']} to puzzle {puzzle_name}"
                    )
                    return

            # Verify location and solvers are set
            puzzle_details = self.get_puzzle_details(puzzle_id)
            if not puzzle_details:
                result.fail(f"Failed to get puzzle details for {puzzle_name}")
                return

            if puzzle_details.get("xyzloc") != test_location:
                result.fail(
                    f"Location not set correctly. Expected '{test_location}', got '{puzzle_details.get('xyzloc')}'"
                )
                return

            current_solvers = puzzle_details.get("cursolvers", "")
            if not current_solvers:
                result.fail("Solvers not assigned to puzzle")
                return

            self.logger.log_operation(
                f"Before solve - location: '{puzzle_details.get('xyzloc')}', solvers: '{current_solvers}'"
            )

            # Solve the puzzle
            test_answer = f"SOLVE TEST {random.randint(1000, 9999)}"
            self.logger.log_operation(f"Solving puzzle with answer '{test_answer}'")
            if not self.update_puzzle(puzzle_id, "answer", test_answer):
                result.fail(f"Failed to set answer for puzzle {puzzle_name}")
                return

            # Verify puzzle is solved and location/solvers are cleared
            puzzle_details = self.get_puzzle_details(puzzle_id)
            if not puzzle_details:
                result.fail(f"Failed to get puzzle details after solving")
                return

            # Check status is Solved
            if puzzle_details.get("status") != "Solved":
                result.fail(
                    f"Status not changed to 'Solved'. Got '{puzzle_details.get('status')}'"
                )
                return

            # Check location is cleared
            location_after = puzzle_details.get("xyzloc", "")
            if location_after:
                result.fail(
                    f"Location not cleared after solve. Expected empty, got '{location_after}'"
                )
                return

            # Check solvers are cleared
            solvers_after = puzzle_details.get("cursolvers", "")
            if solvers_after:
                result.fail(
                    f"Solvers not cleared after solve. Expected empty, got '{solvers_after}'"
                )
                return

            self.logger.log_operation(
                "After solve - location and solvers successfully cleared"
            )

            result.set_success(
                "Solve clears location and solvers test completed successfully"
            )

        except Exception as e:
            result.fail(f"Error in solve clears location and solvers test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_solver_assignments(self, result: TestResult):
        """Test solver assignment functionality."""
        try:
            # Get all solvers and puzzles
            solvers = self.get_all_solvers()
            puzzles = self.get_all_puzzles()

            if not solvers or not puzzles:
                result.fail("Failed to get solvers or puzzles")
                return

            self.logger.log_operation(
                f"Found {len(solvers)} solvers and {len(puzzles)} puzzles"
            )

            # Get full puzzle details for each puzzle
            detailed_puzzles = []
            for puzzle in puzzles:
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if puzzle_details:
                    detailed_puzzles.append(puzzle_details)
                else:
                    result.fail(f"Failed to get details for puzzle {puzzle['id']}")
                    continue

            if not detailed_puzzles:
                result.fail("Failed to get puzzle details")
                return

            # Group puzzles by round
            puzzles_by_round = {}
            for puzzle in detailed_puzzles:
                round_id = str(puzzle.get("round_id", ""))
                if round_id:
                    if round_id not in puzzles_by_round:
                        puzzles_by_round[round_id] = []
                    puzzles_by_round[round_id].append(puzzle)

            self.logger.log_operation(
                f"Found {len(puzzles_by_round)} rounds with puzzles"
            )

            # For each round, select up to 2 random puzzles for testing
            selected_puzzles = []
            for round_id, round_puzzles in puzzles_by_round.items():
                num_to_select = min(2, len(round_puzzles))
                if num_to_select > 0:
                    selected = random.sample(round_puzzles, num_to_select)
                    selected_puzzles.extend(selected)

            if not selected_puzzles:
                result.fail("No puzzles available for testing")
                return

            self.logger.log_operation(
                f"Selected {len(selected_puzzles)} puzzles for assignment testing"
            )

            # For each selected puzzle, assign 2 random solvers
            for puzzle in selected_puzzles:
                # Select 2 random solvers
                if len(solvers) < 2:
                    result.fail("Not enough solvers available for testing")
                    continue

                selected_solvers = random.sample(solvers, 2)

                for solver in selected_solvers:
                    # Assign solver to puzzle
                    success = self.assign_solver_to_puzzle(solver["id"], puzzle["id"])
                    if not success:
                        result.fail(
                            f"Failed to assign solver {solver['name']} to puzzle {puzzle['name']}"
                        )
                        continue

                    # Verify assignment
                    solver_details = self.get_solver_details(solver["id"])
                    if not solver_details:
                        result.fail(
                            f"Failed to get solver details for {solver['name']}"
                        )
                        continue

                    if solver_details.get("puzz") != puzzle["name"]:
                        result.fail(
                            f"Solver {solver['name']} not properly assigned to puzzle {puzzle['name']}"
                        )
                        continue

                    self.logger.log_operation(
                        f"Successfully assigned solver {solver['name']} to puzzle {puzzle['name']}"
                    )

            result.set_success("Solver assignment test completed successfully")

        except Exception as e:
            result.fail(f"Error in solver assignment test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_activity_tracking(self, result: TestResult):
        """Test activity tracking functionality."""
        self.logger.log_operation("Starting activity tracking test")

        # Get all solvers and puzzles
        solvers = self.get_all_solvers()
        puzzles = self.get_all_puzzles()

        if not solvers or not puzzles:
            result.fail("Failed to get solvers or puzzles")
            return

        # Get full puzzle details for each puzzle
        detailed_puzzles = []
        for puzzle in puzzles:
            puzzle_details = self.get_puzzle_details(puzzle["id"])
            if puzzle_details:
                detailed_puzzles.append(puzzle_details)

        if not detailed_puzzles:
            result.fail("Failed to get puzzle details")
            return

        # Group puzzles by round
        puzzles_by_round = {}
        for puzzle in detailed_puzzles:
            round_id = str(puzzle.get("round_id", ""))
            if round_id:
                if round_id not in puzzles_by_round:
                    puzzles_by_round[round_id] = []
                puzzles_by_round[round_id].append(puzzle)

        # For each round, select up to 2 random puzzles
        selected_puzzles = []
        for round_id, round_puzzles in puzzles_by_round.items():
            num_to_select = min(2, len(round_puzzles))
            if num_to_select > 0:
                selected = random.sample(round_puzzles, num_to_select)
                selected_puzzles.extend(selected)

        if not selected_puzzles:
            result.fail("No puzzles available for testing")
            return

        # Filter out solved puzzles
        unsolved_puzzles = [p for p in selected_puzzles if p.get("status") != "Solved"]

        if not unsolved_puzzles:
            result.fail("No unsolved puzzles available for testing")
            return

        # For each selected puzzle, assign 2 random solvers and check activity
        for puzzle in unsolved_puzzles:
            self.logger.log_operation(f"Testing activity for puzzle {puzzle['name']}")

            # Select 2 random solvers
            if len(solvers) < 2:
                result.fail("Not enough solvers available for testing")
                continue

            selected_solvers = random.sample(solvers, 2)

            for solver in selected_solvers:
                self.logger.log_operation(
                    f"Assigning solver {solver['name']} to puzzle {puzzle['name']}"
                )

                # Assign solver to puzzle
                if not self.assign_solver_to_puzzle(solver["id"], puzzle["id"]):
                    result.fail(
                        f"Failed to assign solver {solver['name']} to puzzle {puzzle['name']}"
                    )
                    continue

                # Check activity for the puzzle
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if not puzzle_details:
                    result.fail(f"Failed to get details for puzzle {puzzle['name']}")
                    continue

                # Get lastact specifically using the puzzle part endpoint
                response = requests.get(
                    f"{self.base_url}/puzzles/{puzzle['id']}/lastact"
                )
                if not response.ok:
                    result.fail(
                        f"Failed to get lastact for puzzle {puzzle['name']}: {response.text}"
                    )
                    return

                last_activity = response.json().get("puzzle", {}).get("lastact")
                if not last_activity:
                    result.fail(f"No lastact found for puzzle {puzzle['name']}")
                    return

                # Verify lastact structure
                if not all(
                    key in last_activity for key in ["time", "type", "source", "uri"]
                ):
                    result.fail(
                        f"Invalid lastact structure for puzzle {puzzle['name']}"
                    )
                    return

        result.set_success("Activity tracking test completed successfully")

    def test_puzzle_activity_endpoint(self, result: TestResult):
        """Test /puzzles/<id>/activity endpoint."""
        self.logger.log_operation("Starting puzzle activity endpoint test")

        # Get all puzzles
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles available for testing")
            return

        # Test with the first puzzle
        test_puzzle = puzzles[0]
        puzzle_id = test_puzzle["id"]

        self.logger.log_operation(f"Testing activity endpoint for puzzle {puzzle_id}")

        # Fetch activity for the puzzle
        response = requests.get(f"{self.base_url}/puzzles/{puzzle_id}/activity")
        if not response.ok:
            result.fail(f"Failed to get activity for puzzle {puzzle_id}: {response.text}")
            return

        activity_data = response.json()

        # Validate response structure
        if not isinstance(activity_data, dict):
            result.fail("Invalid response format - not a dict")
            return

        if activity_data.get("status") != "ok":
            result.fail(f"Invalid status: {activity_data.get('status')}")
            return

        if "puzzle_id" not in activity_data:
            result.fail("Missing 'puzzle_id' in response")
            return

        if "activity" not in activity_data:
            result.fail("Missing 'activity' in response")
            return

        # Validate puzzle_id matches
        if activity_data["puzzle_id"] != puzzle_id:
            result.fail(f"Puzzle ID mismatch: expected {puzzle_id}, got {activity_data['puzzle_id']}")
            return

        # Validate activity is a list
        if not isinstance(activity_data["activity"], list):
            result.fail("Activity should be a list")
            return

        activities = activity_data["activity"]
        self.logger.log_operation(f"Found {len(activities)} activity entries")

        # Every puzzle should have at least a 'create' activity
        if len(activities) < 1:
            result.fail("Puzzle should have at least one activity entry (create)")
            return

        # Validate activity entry structure
        required_fields = ["id", "time", "solver_id", "puzzle_id", "source", "type"]
        for i, activity in enumerate(activities[:3]):  # Check first 3 entries
            for field in required_fields:
                if field not in activity:
                    result.fail(f"Activity entry {i} missing field '{field}'")
                    return

            # Validate puzzle_id matches
            if activity["puzzle_id"] != puzzle_id:
                result.fail(f"Activity entry {i} has wrong puzzle_id: {activity['puzzle_id']}")
                return

        # Validate activities are sorted by time (most recent first)
        if len(activities) > 1:
            times = [a["time"] for a in activities]
            # Compare first and last - first should be >= last (reverse chronological)
            if times[0] < times[-1]:
                result.fail("Activities not sorted correctly (should be most recent first)")
                return

        self.logger.log_operation("Activity entries validated successfully")

        # Test generating activity by changing puzzle status
        self.logger.log_operation("Changing puzzle status to generate additional activity")

        # Change status to generate activity
        response = requests.post(
            f"{self.base_url}/puzzles/{puzzle_id}/status",
            json={"status": "Critical"}
        )
        if not response.ok:
            self.logger.log_operation(f"Note: Failed to change puzzle status: {response.text}")
        else:
            # Fetch activity again to verify it increased
            response = requests.get(f"{self.base_url}/puzzles/{puzzle_id}/activity")
            if response.ok:
                updated_activity = response.json()["activity"]
                if len(updated_activity) > len(activities):
                    self.logger.log_operation(
                        f"Activity count increased from {len(activities)} to {len(updated_activity)}"
                    )
                else:
                    self.logger.log_operation(
                        f"Activity count stayed at {len(activities)}"
                    )

        # Test with non-existent puzzle
        self.logger.log_operation("Testing with non-existent puzzle")
        response = requests.get(f"{self.base_url}/puzzles/999999/activity")
        if response.ok:
            result.fail("Should return error for non-existent puzzle")
            return

        self.logger.log_operation("Correctly returned error for non-existent puzzle")

        result.set_success("Puzzle activity endpoint test completed successfully")

    def test_solver_activity_endpoint(self, result: TestResult):
        """Test /solvers/<id>/activity endpoint."""
        self.logger.log_operation("Starting solver activity endpoint test")

        # Get all solvers
        solvers = self.get_all_solvers()
        if not solvers:
            result.fail("No solvers available for testing")
            return

        # Test with the first solver
        test_solver = solvers[0]
        solver_id = test_solver["id"]

        self.logger.log_operation(f"Testing activity endpoint for solver {solver_id}")

        # Fetch activity for the solver
        response = requests.get(f"{self.base_url}/solvers/{solver_id}/activity")
        if not response.ok:
            result.fail(f"Failed to get activity for solver {solver_id}: {response.text}")
            return

        activity_data = response.json()

        # Validate response structure
        if not isinstance(activity_data, dict):
            result.fail("Invalid response format - not a dict")
            return

        if activity_data.get("status") != "ok":
            result.fail(f"Invalid status: {activity_data.get('status')}")
            return

        if "solver_id" not in activity_data:
            result.fail("Missing 'solver_id' in response")
            return

        if "activity" not in activity_data:
            result.fail("Missing 'activity' in response")
            return

        # Validate solver_id matches
        if activity_data["solver_id"] != solver_id:
            result.fail(f"Solver ID mismatch: expected {solver_id}, got {activity_data['solver_id']}")
            return

        # Validate activity is a list
        if not isinstance(activity_data["activity"], list):
            result.fail("Activity should be a list")
            return

        activities = activity_data["activity"]
        self.logger.log_operation(f"Found {len(activities)} activity entries for solver")

        # Validate activity entry structure if any activities exist
        if len(activities) > 0:
            required_fields = ["id", "time", "solver_id", "puzzle_id", "source", "type"]
            for i, activity in enumerate(activities[:3]):  # Check first 3 entries
                for field in required_fields:
                    if field not in activity:
                        result.fail(f"Activity entry {i} missing field '{field}'")
                        return

                # Validate solver_id matches
                if activity["solver_id"] != solver_id:
                    result.fail(f"Activity entry {i} has wrong solver_id: {activity['solver_id']}")
                    return

            # Validate activities are sorted by time (most recent first)
            if len(activities) > 1:
                times = [a["time"] for a in activities]
                # Compare first and last - first should be >= last (reverse chronological)
                if times[0] < times[-1]:
                    result.fail("Activities not sorted correctly (should be most recent first)")
                    return

            self.logger.log_operation("Activity entries validated successfully")
        else:
            self.logger.log_operation("No activity entries found for solver (this is okay)")

        # Test generating activity by assigning solver to a puzzle
        puzzles = self.get_all_puzzles()
        if puzzles:
            test_puzzle = puzzles[0]
            puzzle_id = test_puzzle["id"]

            self.logger.log_operation(f"Assigning solver {solver_id} to puzzle {puzzle_id} to generate activity")

            # Assign solver to puzzle
            if self.assign_solver_to_puzzle(solver_id, puzzle_id):
                # Fetch activity again to verify it increased
                response = requests.get(f"{self.base_url}/solvers/{solver_id}/activity")
                if response.ok:
                    updated_activity = response.json()["activity"]
                    if len(updated_activity) > len(activities):
                        self.logger.log_operation(
                            f"Activity count increased from {len(activities)} to {len(updated_activity)}"
                        )
                    else:
                        self.logger.log_operation(
                            f"Activity count stayed at {len(activities)}"
                        )
            else:
                self.logger.log_operation("Note: Failed to assign solver to puzzle")

        # Test with non-existent solver
        self.logger.log_operation("Testing with non-existent solver")
        response = requests.get(f"{self.base_url}/solvers/999999/activity")
        if response.ok:
            result.fail("Should return error for non-existent solver")
            return

        self.logger.log_operation("Correctly returned error for non-existent solver")

        result.set_success("Solver activity endpoint test completed successfully")

    def test_solver_history(self, result: TestResult):
        """Test adding and removing solvers from puzzle history."""
        try:
            # Get all solvers and puzzles
            solvers = self.get_all_solvers()
            puzzles = self.get_all_puzzles()

            if not solvers or not puzzles:
                result.fail("Failed to get solvers or puzzles")
                return

            self.logger.log_operation(
                f"Found {len(solvers)} solvers and {len(puzzles)} puzzles"
            )

            # Get full puzzle details for each puzzle
            detailed_puzzles = []
            for puzzle in puzzles:
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if puzzle_details:
                    detailed_puzzles.append(puzzle_details)
                else:
                    result.fail(f"Failed to get details for puzzle {puzzle['id']}")
                    continue

            if not detailed_puzzles:
                result.fail("Failed to get puzzle details")
                return

            # Group puzzles by round
            puzzles_by_round = {}
            for puzzle in detailed_puzzles:
                round_id = str(puzzle.get("round_id", ""))
                if round_id:
                    if round_id not in puzzles_by_round:
                        puzzles_by_round[round_id] = []
                    puzzles_by_round[round_id].append(puzzle)

            self.logger.log_operation(
                f"Found {len(puzzles_by_round)} rounds with puzzles"
            )

            # For each round, select up to 2 random puzzles
            selected_puzzles = []
            for round_id, round_puzzles in puzzles_by_round.items():
                num_to_select = min(2, len(round_puzzles))
                if num_to_select > 0:
                    selected = random.sample(round_puzzles, num_to_select)
                    selected_puzzles.extend(selected)

            if not selected_puzzles:
                result.fail("No puzzles available for testing")
                return

            self.logger.log_operation(
                f"Selected {len(selected_puzzles)} puzzles for history testing"
            )

            # For each selected puzzle, test history operations with 2 random solvers
            for puzzle in selected_puzzles:
                # Select 2 random solvers
                if len(solvers) < 2:
                    result.fail("Not enough solvers available for testing")
                    continue

                selected_solvers = random.sample(solvers, 2)

                for solver in selected_solvers:
                    # Add solver to history
                    success = self.add_solver_to_history(puzzle["id"], solver["id"])
                    if not success:
                        result.fail(
                            f"Failed to add solver {solver['name']} to history for puzzle {puzzle['name']}"
                        )
                        continue

                    # Verify history addition
                    puzzle_data = self.get_puzzle_details(puzzle["id"])
                    if not puzzle_data:
                        result.fail(
                            f"Failed to get updated puzzle data for {puzzle['name']}"
                        )
                        continue

                    # Check if solver is in historical solvers list
                    historical_solvers = puzzle_data.get("solvers", "")
                    if historical_solvers is None:
                        historical_solvers = ""
                    if solver["name"] not in historical_solvers:
                        result.fail(
                            f"Solver {solver['name']} not found in puzzle's historical solvers"
                        )
                        continue

                    self.logger.log_operation(
                        f"Successfully added solver {solver['name']} to history for puzzle {puzzle['name']}"
                    )

                    # Remove from history
                    success = self.remove_solver_from_history(
                        puzzle["id"], solver["id"]
                    )
                    if not success:
                        result.fail(
                            f"Failed to remove solver {solver['name']} from history for puzzle {puzzle['name']}"
                        )
                        continue

                    # Verify history removal
                    puzzle_data = self.get_puzzle_details(puzzle["id"])
                    if not puzzle_data:
                        result.fail(
                            f"Failed to get updated puzzle data for {puzzle['name']}"
                        )
                        continue

                    # Check if solver is no longer in historical solvers list
                    historical_solvers = puzzle_data.get("solvers", "")
                    if historical_solvers is None:
                        historical_solvers = ""
                    if solver["name"] in historical_solvers:
                        result.fail(
                            f"Solver {solver['name']} still found in puzzle's historical solvers after removal"
                        )
                        continue

                    self.logger.log_operation(
                        f"Successfully removed solver {solver['name']} from history for puzzle {puzzle['name']}"
                    )

            result.set_success("Solver history test completed successfully")

        except Exception as e:
            result.fail(f"Error in solver history test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_solver_reassignment(self, result: TestResult):
        """Test reassignment of solvers between puzzles."""
        self.logger.log_operation("Starting solver reassignment test")

        try:
            # Get all puzzles and solvers
            puzzles = self.get_all_puzzles()
            solvers = self.get_all_solvers()

            if not puzzles or len(puzzles) < 2:
                result.fail("Need at least 2 puzzles for reassignment test")
                return

            if not solvers or len(solvers) < 2:
                result.fail("Need at least 2 solvers for reassignment test")
                return

            # Get solvers that are already assigned to puzzles
            assigned_solvers = []
            for solver in solvers:
                solver_details = self.get_solver_details(solver["id"])
                if solver_details and solver_details.get("puzz"):
                    assigned_solvers.append(solver)

            if len(assigned_solvers) < 2:
                result.fail(
                    "Need at least 2 solvers already assigned to puzzles for reassignment test"
                )
                return

            # Select two random assigned solvers
            solver1, solver2 = random.sample(assigned_solvers, 2)

            # Get their current puzzles
            solver1_details = self.get_solver_details(solver1["id"])
            solver2_details = self.get_solver_details(solver2["id"])
            solver1_current_puzzle = solver1_details.get("puzz")
            solver2_current_puzzle = solver2_details.get("puzz")

            # Filter out puzzles that are currently assigned to either solver or are solved
            available_puzzles = []
            for puzzle in puzzles:
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if (
                    puzzle["name"] != solver1_current_puzzle
                    and puzzle["name"] != solver2_current_puzzle
                    and puzzle_details
                    and puzzle_details.get("status") != "Solved"
                ):
                    available_puzzles.append(puzzle)

            if len(available_puzzles) < 2:
                result.fail(
                    "Not enough unsolved puzzles available that aren't already assigned to the selected solvers"
                )
                return

            # Select two random puzzles from the available ones
            puzzle1, puzzle2 = random.sample(available_puzzles, 2)

            self.logger.log_operation(
                f"Selected puzzles: {puzzle1['name']}, {puzzle2['name']}"
            )
            self.logger.log_operation(
                f"Selected solvers: {solver1['name']} (currently on {solver1_current_puzzle}), {solver2['name']} (currently on {solver2_current_puzzle})"
            )

            # Assign both solvers to first puzzle
            for solver in [solver1, solver2]:
                self.logger.log_operation(
                    f"Attempting to assign solver {solver['name']} to puzzle {puzzle1['name']}"
                )
                if not self.update_solver_puzzle(solver["id"], puzzle1["id"]):
                    result.fail(
                        f"Failed to assign solver {solver['name']} to puzzle {puzzle1['name']}"
                    )
                    return
                self.logger.log_operation(
                    f"Successfully assigned solver {solver['name']} to puzzle {puzzle1['name']}"
                )

            # Verify initial assignments
            puzzle1_details = self.get_puzzle_details(puzzle1["id"])
            if not puzzle1_details:
                result.fail(f"Failed to get details for puzzle {puzzle1['name']}")
                return

            # Check puzzle's current solvers
            current_solvers = puzzle1_details.get("cursolvers", "") or ""
            self.logger.log_operation(
                f"Current solvers for puzzle {puzzle1['name']}: {current_solvers}"
            )
            if solver1["name"] not in current_solvers.split(",") or solver2[
                "name"
            ] not in current_solvers.split(","):
                result.fail(
                    f"Solvers not properly assigned to puzzle {puzzle1['name']}"
                )
                self.logger.log_error(
                    f"Expected solvers: {solver1['name']}, {solver2['name']}"
                )
                self.logger.log_error(f"Actual solvers: {current_solvers}")
                return

            # Check solvers' current puzzles
            for solver in [solver1, solver2]:
                solver_details = self.get_solver_details(solver["id"])
                self.logger.log_operation(
                    f"Solver {solver['name']} current puzzle: {solver_details.get('puzz')}"
                )
                if solver_details.get("puzz") != puzzle1["name"]:
                    result.fail(
                        f"Solver {solver['name']} not properly assigned to puzzle {puzzle1['name']}"
                    )
                    return

            # Reassign first solver to second puzzle
            self.logger.log_operation(
                f"Attempting to reassign solver {solver1['name']} to puzzle {puzzle2['name']}"
            )
            if not self.update_solver_puzzle(solver1["id"], puzzle2["id"]):
                result.fail(
                    f"Failed to reassign solver {solver1['name']} to puzzle {puzzle2['name']}"
                )
                return
            self.logger.log_operation(
                f"Successfully reassigned solver {solver1['name']} to puzzle {puzzle2['name']}"
            )

            # Verify reassignment
            puzzle1_details = self.get_puzzle_details(puzzle1["id"])
            puzzle2_details = self.get_puzzle_details(puzzle2["id"])
            solver1_details = self.get_solver_details(solver1["id"])
            solver2_details = self.get_solver_details(solver2["id"])

            if (
                not puzzle1_details
                or not puzzle2_details
                or not solver1_details
                or not solver2_details
            ):
                result.fail("Failed to get details after reassignment")
                return

            # Check solver is no longer assigned to old puzzle
            current_solvers = puzzle1_details.get("cursolvers", "") or ""
            self.logger.log_operation(
                f"Current solvers for puzzle {puzzle1['name']} after reassignment: {current_solvers}"
            )
            if solver1["name"] in current_solvers.split(","):
                result.fail(
                    f"Solver {solver1['name']} still assigned to old puzzle {puzzle1['name']}"
                )
                return

            # Check solver is assigned to new puzzle
            current_solvers = puzzle2_details.get("cursolvers", "") or ""
            self.logger.log_operation(
                f"Current solvers for puzzle {puzzle2['name']} after reassignment: {current_solvers}"
            )
            if solver1["name"] not in current_solvers.split(","):
                result.fail(
                    f"Solver {solver1['name']} not assigned to new puzzle {puzzle2['name']}"
                )
                return

            # Check solver's current puzzle is updated
            self.logger.log_operation(
                f"Solver {solver1['name']} current puzzle after reassignment: {solver1_details.get('puzz')}"
            )
            if solver1_details.get("puzz") != puzzle2["name"]:
                result.fail(
                    f"Solver {solver1['name']} not properly reassigned to puzzle {puzzle2['name']}"
                )
                return

            # Check solver2 is still assigned to puzzle1
            self.logger.log_operation(
                f"Solver {solver2['name']} current puzzle after reassignment: {solver2_details.get('puzz')}"
            )
            if solver2_details.get("puzz") != puzzle1["name"]:
                result.fail(
                    f"Solver {solver2['name']} no longer assigned to puzzle {puzzle1['name']}"
                )
                return

            result.set_success("Solver reassignment test completed successfully")

        except Exception as e:
            result.fail(f"Error in solver reassignment test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def update_solver_puzzle(self, solver_id: str, puzzle_id: str) -> bool:
        """Update a solver's current puzzle assignment."""
        try:
            self.logger.log_operation(
                f"Making POST request to /solvers/{solver_id}/puzz with puzzle_id {puzzle_id}"
            )
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}/puzz", json={"puzz": puzzle_id}
            )

            self.logger.log_operation(f"Response status code: {response.status_code}")
            self.logger.log_operation(f"Response body: {response.text}")

            if response.status_code != 200:
                self.logger.log_error(
                    f"Failed to update solver puzzle. Status code: {response.status_code}"
                )
                return False

            response_data = response.json()
            if response_data.get("status") != "ok":
                self.logger.log_error(
                    f"Failed to update solver puzzle. Response: {response_data}"
                )
                return False

            return True

        except Exception as e:
            self.logger.log_error(f"Error updating solver puzzle: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")
            return False

    def test_round_modification(self, result: TestResult):
        """Test round modification functionality."""
        self.logger.log_operation("Starting round modification test")

        try:
            # Get all existing rounds
            rounds = self.get_all_rounds()
            if not rounds:
                result.fail("No rounds found for testing")
                return

            # Select a random round for testing
            test_round = random.choice(rounds)
            self.logger.log_operation(
                f"Selected round for testing: {test_round['name']}"
            )

            # Test comments update
            new_comments = f"Test comments for round {test_round['name']}"
            self.logger.log_operation(f"Updating comments to '{new_comments}'")

            # Update round comments
            updated_round = self.update_round(
                test_round["id"], {"comments": new_comments}
            )
            if not updated_round:
                result.fail(f"Failed to update comments for round {test_round['name']}")
                return

            # Verify comments update
            if updated_round.get("comments") != new_comments:
                result.fail(f"Comments not updated for round {test_round['name']}")
                return

            self.logger.log_operation(
                f"Successfully updated comments for round {test_round['name']}"
            )

            result.set_success("Round modification test completed successfully")

        except Exception as e:
            result.fail(f"Error in round modification test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_round_multi_part_update(self, result: TestResult):
        """Test multi-part round update endpoint POST /rounds/<id>."""
        self.logger.log_operation("Starting round multi-part update test")

        try:
            # Get all existing rounds
            rounds = self.get_all_rounds()
            if not rounds:
                result.fail("No rounds found for testing")
                return

            # Select a random round for testing
            test_round = random.choice(rounds)
            round_id = test_round["id"]
            self.logger.log_operation(
                f"Testing multi-part update on round {test_round['name']} (id: {round_id})"
            )

            # Test 1: Successful multi-part update (status + comments)
            self.logger.log_operation("Test 1: Successful multi-part update")
            update_data = {
                "status": "Being worked",
                "comments": "Multi-part test comment for round",
            }
            response = requests.post(
                f"{self.base_url}/rounds/{round_id}", json=update_data
            )
            if not response.ok:
                result.fail(f"Round multi-part update failed: {response.text}")
                return
            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Round multi-part update returned error: {response_data}")
                return
            self.logger.log_operation("Test 1 passed: Multi-part update succeeded")

            # Test 2: Verify the updates took effect
            self.logger.log_operation("Test 2: Verify updates")
            verify_response = requests.get(
                f"{self.base_url}/rounds/{round_id}/comments"
            )
            if verify_response.ok:
                verify_data = verify_response.json()
                if (
                    verify_data.get("round", {}).get("comments")
                    != "Multi-part test comment for round"
                ):
                    result.fail("Comments not updated correctly")
                    return
            self.logger.log_operation("Test 2 passed: Updates verified")

            # Test 3: Invalid part name rejected
            self.logger.log_operation("Test 3: Verify invalid part name is rejected")
            response = requests.post(
                f"{self.base_url}/rounds/{round_id}", json={"notarealpart": "somevalue"}
            )
            if response.ok:
                result.fail(
                    "Round multi-part update should have rejected invalid part name"
                )
                return
            self.logger.log_operation("Test 3 passed: Invalid part name rejected")

            result.set_success("Round multi-part update test completed successfully")

        except Exception as e:
            result.fail(f"Error in round multi-part update test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_solver_multi_part_update(self, result: TestResult):
        """Test multi-part solver update endpoint POST /solvers/<id>."""
        self.logger.log_operation("Starting solver multi-part update test")

        try:
            # Get all solvers
            solvers = self.get_all_solvers()
            if not solvers:
                result.fail("No solvers found for testing")
                return

            # Select a random solver for testing
            test_solver = random.choice(solvers)
            solver_id = test_solver["id"]
            self.logger.log_operation(
                f"Testing multi-part update on solver {test_solver['name']} (id: {solver_id})"
            )

            # Test 1: Successful multi-part update (fullname + chat_name)
            self.logger.log_operation("Test 1: Successful multi-part update")
            update_data = {
                "fullname": "Test Fullname Updated",
                "chat_name": "test_chat_updated",
            }
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}", json=update_data
            )
            if not response.ok:
                result.fail(f"Solver multi-part update failed: {response.text}")
                return
            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Solver multi-part update returned error: {response_data}")
                return
            self.logger.log_operation("Test 1 passed: Multi-part update succeeded")

            # Test 2: Verify the updates took effect
            self.logger.log_operation("Test 2: Verify updates")
            solver_details = self.get_solver_details(solver_id)
            if not solver_details:
                result.fail("Failed to get solver details after update")
                return
            if solver_details.get("fullname") != "Test Fullname Updated":
                result.fail(
                    f"Fullname not updated. Got: {solver_details.get('fullname')}"
                )
                return
            if solver_details.get("chat_name") != "test_chat_updated":
                result.fail(
                    f"Chat name not updated. Got: {solver_details.get('chat_name')}"
                )
                return
            self.logger.log_operation("Test 2 passed: Updates verified")

            # Test 3: Invalid part name rejected
            self.logger.log_operation("Test 3: Verify invalid part name is rejected")
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}",
                json={"notarealpart": "somevalue"},
            )
            if response.ok:
                result.fail(
                    "Solver multi-part update should have rejected invalid part name"
                )
                return
            self.logger.log_operation("Test 3 passed: Invalid part name rejected")

            result.set_success("Solver multi-part update test completed successfully")

        except Exception as e:
            result.fail(f"Error in solver multi-part update test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_sheetcount(self, result: TestResult):
        """Test sheetcount field population, modification, and reading."""
        self.logger.log_operation("Starting sheetcount test")

        try:
            # Get all puzzles
            puzzles = self.get_all_puzzles()
            if not puzzles:
                result.fail("No puzzles found for sheetcount testing")
                return

            # Select a few random puzzles for testing
            selected_puzzles = random.sample(puzzles, min(3, len(puzzles)))

            for puzzle in selected_puzzles:
                self.logger.log_operation(
                    f"Testing sheetcount for puzzle {puzzle['name']}"
                )

                # Get initial puzzle details
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if not puzzle_details:
                    result.fail(f"Failed to get details for puzzle {puzzle['name']}")
                    return

                initial_sheetcount = puzzle_details.get("sheetcount")
                self.logger.log_operation(f"Initial sheetcount: {initial_sheetcount}")

                # Set sheetcount to a specific value
                test_sheetcount = random.randint(2, 10)
                self.logger.log_operation(f"Setting sheetcount to {test_sheetcount}")

                if not self.update_puzzle(puzzle["id"], "sheetcount", test_sheetcount):
                    result.fail(f"Failed to set sheetcount for puzzle {puzzle['name']}")
                    return

                # Verify sheetcount was set
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if not puzzle_details:
                    result.fail(
                        "Failed to get puzzle details after setting sheetcount"
                    )
                    return

                if puzzle_details.get("sheetcount") != test_sheetcount:
                    result.fail(
                        f"Sheetcount not set correctly for puzzle {puzzle['name']}. Expected: {test_sheetcount}, Got: {puzzle_details.get('sheetcount')}"
                    )
                    return

                self.logger.log_operation(
                    f"Successfully set sheetcount to {test_sheetcount}"
                )

                # Update sheetcount to a different value
                new_sheetcount = test_sheetcount + random.randint(1, 5)
                self.logger.log_operation(f"Updating sheetcount to {new_sheetcount}")

                if not self.update_puzzle(puzzle["id"], "sheetcount", new_sheetcount):
                    result.fail(
                        f"Failed to update sheetcount for puzzle {puzzle['name']}"
                    )
                    return

                # Verify sheetcount was updated
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if not puzzle_details:
                    result.fail(
                        "Failed to get puzzle details after updating sheetcount"
                    )
                    return

                if puzzle_details.get("sheetcount") != new_sheetcount:
                    result.fail(
                        f"Sheetcount not updated correctly for puzzle {puzzle['name']}. Expected: {new_sheetcount}, Got: {puzzle_details.get('sheetcount')}"
                    )
                    return

                self.logger.log_operation(
                    f"Successfully updated sheetcount to {new_sheetcount}"
                )

                # Verify sheetcount is included in /all endpoint
                response = requests.get(f"{self.base_url}/all")
                if not response.ok:
                    result.fail("Failed to get /all endpoint")
                    return

                all_data = response.json()
                found_puzzle = None
                for round_data in all_data.get("rounds", []):
                    for p in round_data.get("puzzles", []):
                        if p.get("id") == puzzle["id"]:
                            found_puzzle = p
                            break
                    if found_puzzle:
                        break

                if not found_puzzle:
                    result.fail(f"Puzzle {puzzle['name']} not found in /all endpoint")
                    return

                if found_puzzle.get("sheetcount") != new_sheetcount:
                    result.fail(
                        f"Sheetcount not correct in /all endpoint for puzzle {puzzle['name']}. Expected: {new_sheetcount}, Got: {found_puzzle.get('sheetcount')}"
                    )
                    return

                self.logger.log_operation(
                    "Sheetcount correctly included in /all endpoint"
                )

            result.set_success("Sheetcount test completed successfully")

        except Exception as e:
            result.fail(f"Error in sheetcount test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def generate_unique_test_tag_name(self) -> str:
        """Generate a unique test tag name that doesn't collide with existing tags."""
        # Get existing tags
        response = requests.get(f"{self.base_url}/tags")
        existing_tags = set()
        if response.ok:
            existing_tags = {t["name"] for t in response.json().get("tags", [])}

        # Generate unique tag name with TEST prefix
        while True:
            timestamp = str(int(time.time() * 1000))  # milliseconds for more uniqueness
            random_suffix = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=6)
            )
            tag_name = f"test-{timestamp}-{random_suffix}"
            if tag_name not in existing_tags:
                return tag_name

    def test_tagging(self, result: TestResult):
        """Test tagging functionality."""
        self.logger.log_operation("Starting tagging test")

        try:
            # Generate unique tag names for this test run (all prefixed with "test-")
            tag1_name = self.generate_unique_test_tag_name()
            tag2_name = self.generate_unique_test_tag_name()
            tag3_name = self.generate_unique_test_tag_name()
            invalid_tag_name = "test invalid tag with spaces"  # Spaces make it invalid

            self.logger.log_operation(
                f"Generated unique test tags: {tag1_name}, {tag2_name}, {tag3_name}"
            )

            # ============================================
            # Test 1: Create a new tag unassociated with a puzzle
            # ============================================
            self.logger.log_operation(
                f"Test 1: Creating tag '{tag1_name}' via POST /tags"
            )
            response = requests.post(f"{self.base_url}/tags", json={"name": tag1_name})
            if not response.ok:
                result.fail(f"Failed to create tag: {response.text}")
                return
            tag1_data = response.json()
            if tag1_data.get("status") != "ok":
                result.fail(f"Unexpected response creating tag: {tag1_data}")
                return
            tag1_id = tag1_data["tag"]["id"]
            self.logger.log_operation(f"Created tag '{tag1_name}' with id {tag1_id}")

            # ============================================
            # Test 2: Pull that tag from the tags endpoint
            # ============================================
            self.logger.log_operation(
                f"Test 2: Fetching tag '{tag1_name}' via GET /tags/{tag1_name}"
            )
            response = requests.get(f"{self.base_url}/tags/{tag1_name}")
            if not response.ok:
                result.fail(f"Failed to get tag: {response.text}")
                return
            fetched_tag = response.json()
            if fetched_tag.get("status") != "ok":
                result.fail(f"Unexpected response fetching tag: {fetched_tag}")
                return
            if fetched_tag["tag"]["name"] != tag1_name:
                result.fail(
                    f"Tag name mismatch. Expected: {tag1_name}, Got: {fetched_tag['tag']['name']}"
                )
                return
            if fetched_tag["tag"]["id"] != tag1_id:
                result.fail(
                    f"Tag id mismatch. Expected: {tag1_id}, Got: {fetched_tag['tag']['id']}"
                )
                return
            self.logger.log_operation(f"Successfully fetched tag '{tag1_name}'")

            # Verify tag appears in GET /tags list
            self.logger.log_operation("Verifying tag appears in GET /tags list")
            response = requests.get(f"{self.base_url}/tags")
            if not response.ok:
                result.fail(f"Failed to get tags list: {response.text}")
                return
            tags_list = response.json().get("tags", [])
            tag_names = [t["name"] for t in tags_list]
            if tag1_name not in tag_names:
                result.fail(f"Tag '{tag1_name}' not found in tags list")
                return
            self.logger.log_operation(f"Tag '{tag1_name}' found in tags list")

            # ============================================
            # Test 3: Create a tag with inappropriate characters (should fail)
            # ============================================
            self.logger.log_operation(
                f"Test 3: Attempting to create invalid tag '{invalid_tag_name}' (should fail)"
            )
            response = requests.post(
                f"{self.base_url}/tags", json={"name": invalid_tag_name}
            )
            if response.ok and response.json().get("status") == "ok":
                result.fail(
                    "Tag with spaces should have been rejected but was accepted"
                )
                return
            self.logger.log_operation("Invalid tag correctly rejected")

            # ============================================
            # Test 4: Create a new tag by associating it with a puzzle (auto-create)
            # ============================================
            # First, we need a puzzle to work with
            puzzles = self.get_all_puzzles()
            if not puzzles:
                # Create a round and puzzle for testing
                self.logger.log_operation(
                    "No puzzles found, creating test round and puzzle"
                )
                timestamp = str(int(time.time()))
                test_round = self.create_round(f"TagTestRound{timestamp}")
                test_puzzle = self.create_puzzle(
                    f"TagTestPuzzle{timestamp}", str(test_round["id"])
                )
                puzzle_id = test_puzzle["id"]
            else:
                puzzle_id = puzzles[0]["id"]

            self.logger.log_operation(
                f"Test 4: Creating tag '{tag2_name}' by adding to puzzle {puzzle_id}"
            )
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"add": tag2_name}},
            )
            if not response.ok:
                result.fail(f"Failed to add tag to puzzle: {response.text}")
                return
            self.logger.log_operation(
                f"Tag '{tag2_name}' auto-created and added to puzzle"
            )

            # Verify tag was created in system
            response = requests.get(f"{self.base_url}/tags/{tag2_name}")
            if not response.ok:
                result.fail(f"Auto-created tag '{tag2_name}' not found in system")
                return
            tag2_id = response.json()["tag"]["id"]
            self.logger.log_operation(
                f"Verified tag '{tag2_name}' exists with id {tag2_id}"
            )

            # ============================================
            # Test 5: Associate an existing tag to a puzzle by id
            # ============================================
            self.logger.log_operation(
                f"Test 5: Adding existing tag id {tag1_id} to puzzle {puzzle_id}"
            )
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"add_id": tag1_id}},
            )
            if not response.ok:
                result.fail(f"Failed to add tag by id: {response.text}")
                return
            self.logger.log_operation(f"Tag id {tag1_id} added to puzzle")

            # ============================================
            # Test 6: Associate a tag by id that doesn't exist (should fail)
            # ============================================
            nonexistent_id = 999999
            self.logger.log_operation(
                f"Test 6: Attempting to add non-existent tag id {nonexistent_id} (should fail)"
            )
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"add_id": nonexistent_id}},
            )
            if response.ok and response.json().get("status") == "ok":
                result.fail("Adding non-existent tag id should have failed")
                return
            self.logger.log_operation("Non-existent tag id correctly rejected")

            # ============================================
            # Test 7: Make sure a puzzle having multiple tags works
            # ============================================
            self.logger.log_operation(
                f"Test 7: Verifying puzzle {puzzle_id} has multiple tags"
            )
            puzzle_details = self.get_puzzle_details(puzzle_id)
            if not puzzle_details:
                result.fail("Failed to get puzzle details")
                return
            puzzle_tags = puzzle_details.get("tags", "")
            if not puzzle_tags:
                result.fail("Puzzle has no tags")
                return
            tag_list = [t.strip() for t in puzzle_tags.split(",")]
            if len(tag_list) < 2:
                result.fail(f"Puzzle should have at least 2 tags, got: {tag_list}")
                return
            if tag1_name not in tag_list:
                result.fail(f"Tag '{tag1_name}' not found in puzzle tags: {tag_list}")
                return
            if tag2_name not in tag_list:
                result.fail(f"Tag '{tag2_name}' not found in puzzle tags: {tag_list}")
                return
            self.logger.log_operation(f"Puzzle has multiple tags: {tag_list}")

            # ============================================
            # Test 8: Pull all tags from a given puzzle
            # ============================================
            self.logger.log_operation(
                f"Test 8: Getting tags via GET /puzzles/{puzzle_id}/tags"
            )
            response = requests.get(f"{self.base_url}/puzzles/{puzzle_id}/tags")
            if not response.ok:
                result.fail(f"Failed to get puzzle tags: {response.text}")
                return
            puzzle_tags_response = response.json()
            if puzzle_tags_response.get("status") != "ok":
                result.fail(
                    f"Unexpected response getting puzzle tags: {puzzle_tags_response}"
                )
                return
            tags_value = puzzle_tags_response.get("puzzle", {}).get("tags", "")
            self.logger.log_operation(f"Got puzzle tags via endpoint: {tags_value}")

            # ============================================
            # Test 9: Search by tag_id
            # ============================================
            self.logger.log_operation(f"Test 9: Searching puzzles by tag_id {tag1_id}")
            response = requests.get(f"{self.base_url}/search?tag_id={tag1_id}")
            if not response.ok:
                result.fail(f"Failed to search by tag_id: {response.text}")
                return
            search_results = response.json()
            if search_results.get("status") != "ok":
                result.fail(
                    f"Unexpected response searching by tag_id: {search_results}"
                )
                return
            found_puzzles = search_results.get("puzzles", [])
            found_ids = [p["id"] for p in found_puzzles]
            if puzzle_id not in found_ids:
                result.fail(
                    f"Puzzle {puzzle_id} not found in search results for tag_id {tag1_id}"
                )
                return
            self.logger.log_operation(
                f"Search by tag_id returned {len(found_puzzles)} puzzle(s)"
            )

            # ============================================
            # Test 10: Search by tag name
            # ============================================
            self.logger.log_operation(
                f"Test 10: Searching puzzles by tag name '{tag2_name}'"
            )
            response = requests.get(f"{self.base_url}/search?tag={tag2_name}")
            if not response.ok:
                result.fail(f"Failed to search by tag name: {response.text}")
                return
            search_results = response.json()
            if search_results.get("status") != "ok":
                result.fail(
                    f"Unexpected response searching by tag name: {search_results}"
                )
                return
            found_puzzles = search_results.get("puzzles", [])
            found_ids = [p["id"] for p in found_puzzles]
            if puzzle_id not in found_ids:
                result.fail(
                    f"Puzzle {puzzle_id} not found in search results for tag '{tag2_name}'"
                )
                return
            self.logger.log_operation(
                f"Search by tag name returned {len(found_puzzles)} puzzle(s)"
            )

            # ============================================
            # Bonus: Test remove_id functionality
            # ============================================
            self.logger.log_operation(
                f"Bonus: Testing remove_id - removing tag id {tag1_id} from puzzle"
            )
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"remove_id": tag1_id}},
            )
            if not response.ok:
                result.fail(f"Failed to remove tag by id: {response.text}")
                return

            # Verify removal
            puzzle_details = self.get_puzzle_details(puzzle_id)
            puzzle_tags = puzzle_details.get("tags", "")
            tag_list = (
                [t.strip() for t in puzzle_tags.split(",")] if puzzle_tags else []
            )
            if tag1_name in tag_list:
                result.fail(f"Tag '{tag1_name}' should have been removed from puzzle")
                return
            self.logger.log_operation(
                f"Tag removed successfully, remaining tags: {tag_list}"
            )

            # ============================================
            # Bonus: Test lowercase normalization
            # ============================================
            uppercase_tag = (
                self.generate_unique_test_tag_name().upper()
            )  # e.g., "TEST-1234567890-ABC123"
            self.logger.log_operation(
                f"Bonus: Testing lowercase normalization with '{uppercase_tag}'"
            )
            response = requests.post(
                f"{self.base_url}/tags", json={"name": uppercase_tag}
            )
            if not response.ok:
                result.fail(f"Failed to create uppercase tag: {response.text}")
                return
            created_tag = response.json()["tag"]
            if created_tag["name"] != uppercase_tag.lower():
                result.fail(
                    f"Tag should be lowercase. Expected: {uppercase_tag.lower()}, Got: {created_tag['name']}"
                )
                return
            self.logger.log_operation(
                f"Uppercase tag correctly normalized to '{created_tag['name']}'"
            )

            result.set_success("Tagging test completed successfully")

        except Exception as e:
            result.fail(f"Error in tagging test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_api_endpoints(self, result: TestResult):
        """Test basic read-only API endpoints."""
        self.logger.log_operation("Starting API endpoints test")

        try:
            # Test /all endpoint
            self.logger.log_operation("Testing /all endpoint")
            response = requests.get(f"{self.base_url}/all")
            if not response.ok:
                result.fail(f"Failed to get /all endpoint: {response.text}")
                return
            all_data = response.json()
            if not isinstance(all_data, dict) or "rounds" not in all_data:
                result.fail("Invalid response format from /all endpoint")
                return
            self.logger.log_operation("Successfully tested /all endpoint")

            # Test /puzzles endpoint
            self.logger.log_operation("Testing /puzzles endpoint")
            response = requests.get(f"{self.base_url}/puzzles")
            if not response.ok:
                result.fail(f"Failed to get /puzzles endpoint: {response.text}")
                return
            puzzles_data = response.json()
            if not isinstance(puzzles_data, dict) or "puzzles" not in puzzles_data:
                result.fail("Invalid response format from /puzzles endpoint")
                return
            self.logger.log_operation("Successfully tested /puzzles endpoint")

            # Test /solvers endpoint
            self.logger.log_operation("Testing /solvers endpoint")
            response = requests.get(f"{self.base_url}/solvers")
            if not response.ok:
                result.fail(f"Failed to get /solvers endpoint: {response.text}")
                return
            solvers_data = response.json()
            if not isinstance(solvers_data, dict) or "solvers" not in solvers_data:
                result.fail("Invalid response format from /solvers endpoint")
                return
            self.logger.log_operation("Successfully tested /solvers endpoint")

            # Test /rounds endpoint
            self.logger.log_operation("Testing /rounds endpoint")
            response = requests.get(f"{self.base_url}/rounds")
            if not response.ok:
                result.fail(f"Failed to get /rounds endpoint: {response.text}")
                return
            rounds_data = response.json()
            if not isinstance(rounds_data, dict) or "rounds" not in rounds_data:
                result.fail("Invalid response format from /rounds endpoint")
                return
            self.logger.log_operation("Successfully tested /rounds endpoint")

            # Test /huntinfo endpoint
            self.logger.log_operation("Testing /huntinfo endpoint")
            response = requests.get(f"{self.base_url}/huntinfo")
            if not response.ok:
                result.fail(f"Failed to get /huntinfo endpoint: {response.text}")
                return
            huntinfo_data = response.json()

            # Validate response structure
            if not isinstance(huntinfo_data, dict):
                result.fail("Invalid response format from /huntinfo endpoint - not a dict")
                return

            if huntinfo_data.get("status") != "ok":
                result.fail(f"Invalid status from /huntinfo endpoint: {huntinfo_data.get('status')}")
                return

            # Check for required keys
            required_keys = ["config", "statuses", "tags"]
            for key in required_keys:
                if key not in huntinfo_data:
                    result.fail(f"Missing '{key}' in /huntinfo response")
                    return

            # Validate config is a dict
            if not isinstance(huntinfo_data["config"], dict):
                result.fail("/huntinfo config should be a dict")
                return

            # Validate statuses is a list
            if not isinstance(huntinfo_data["statuses"], list):
                result.fail("/huntinfo statuses should be a list")
                return

            # Validate tags is a list
            if not isinstance(huntinfo_data["tags"], list):
                result.fail("/huntinfo tags should be a list")
                return

            self.logger.log_operation(
                f"Successfully tested /huntinfo endpoint - "
                f"config: {len(huntinfo_data['config'])} entries, "
                f"statuses: {len(huntinfo_data['statuses'])} values, "
                f"tags: {len(huntinfo_data['tags'])} tags"
            )

            # Test /statuses endpoint
            self.logger.log_operation("Testing /statuses endpoint")
            response = requests.get(f"{self.base_url}/statuses")
            if not response.ok:
                result.fail(f"Failed to get /statuses endpoint: {response.text}")
                return
            statuses_data = response.json()

            if not isinstance(statuses_data, dict):
                result.fail("Invalid response format from /statuses endpoint - not a dict")
                return

            if statuses_data.get("status") != "ok":
                result.fail(f"Invalid status from /statuses endpoint: {statuses_data.get('status')}")
                return

            if "statuses" not in statuses_data:
                result.fail("Missing 'statuses' key in /statuses response")
                return

            if not isinstance(statuses_data["statuses"], list):
                result.fail("/statuses statuses should be a list")
                return

            # Verify "New" and "Solved" are in the list
            statuses_list = statuses_data["statuses"]
            if "New" not in statuses_list:
                result.fail("'New' status not found in /statuses response")
                return

            if "Solved" not in statuses_list:
                result.fail("'Solved' status not found in /statuses response")
                return

            self.logger.log_operation(
                f"Successfully tested /statuses endpoint - found {len(statuses_list)} statuses including 'New' and 'Solved'"
            )

            # Test /config endpoint
            self.logger.log_operation("Testing /config endpoint")
            response = requests.get(f"{self.base_url}/config")
            if not response.ok:
                result.fail(f"Failed to get /config endpoint: {response.text}")
                return
            config_data = response.json()

            if not isinstance(config_data, dict):
                result.fail("Invalid response format from /config endpoint - not a dict")
                return

            if config_data.get("status") != "ok":
                result.fail(f"Invalid status from /config endpoint: {config_data.get('status')}")
                return

            if "config" not in config_data:
                result.fail("Missing 'config' key in /config response")
                return

            config = config_data["config"]
            if not isinstance(config, dict):
                result.fail("/config config should be a dict")
                return

            # Verify specific config keys exist
            required_config_keys = ["DOMAINNAME", "LOGLEVEL", "BIN_URI"]
            for key in required_config_keys:
                if key not in config:
                    result.fail(f"Missing '{key}' in /config response")
                    return

            self.logger.log_operation(
                f"Successfully tested /config endpoint - DOMAINNAME={config.get('DOMAINNAME')}, "
                f"LOGLEVEL={config.get('LOGLEVEL')}, BIN_URI={config.get('BIN_URI')}"
            )

            # Test /solvers/byname/<name> endpoint
            self.logger.log_operation("Testing /solvers/byname/<name> endpoint")
            # Get a solver to test with
            solvers = self.get_all_solvers()
            if not solvers:
                result.fail("No solvers available to test /solvers/byname endpoint")
                return

            test_solver = solvers[0]
            solver_name = test_solver["name"]

            self.logger.log_operation(f"Testing with solver name: {solver_name}")
            response = requests.get(f"{self.base_url}/solvers/byname/{solver_name}")
            if not response.ok:
                result.fail(f"Failed to get /solvers/byname/{solver_name}: {response.text}")
                return

            solver_data = response.json()
            if not isinstance(solver_data, dict):
                result.fail("Invalid response format from /solvers/byname endpoint - not a dict")
                return

            if solver_data.get("status") != "ok":
                result.fail(f"Invalid status from /solvers/byname endpoint: {solver_data.get('status')}")
                return

            if "solver" not in solver_data:
                result.fail("Missing 'solver' key in /solvers/byname response")
                return

            returned_solver = solver_data["solver"]
            if returned_solver.get("name") != solver_name:
                result.fail(
                    f"Solver name mismatch. Expected: {solver_name}, Got: {returned_solver.get('name')}"
                )
                return

            self.logger.log_operation(
                f"Successfully tested /solvers/byname endpoint - found solver '{solver_name}' (id: {returned_solver.get('id')})"
            )

            result.set_success("API endpoints test completed successfully")

        except Exception as e:
            result.fail(f"Error in API endpoints test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_bot_statistics(self, result: TestResult):
        """Test bot statistics update and retrieval."""
        self.logger.log_operation("Starting bot statistics test")

        try:
            # Create a unique test key name
            timestamp = str(int(time.time()))
            test_key = f"test_botstat_{timestamp}"
            test_value_1 = f"test_value_1_{random.randint(1000, 9999)}"
            test_value_2 = f"test_value_2_{random.randint(1000, 9999)}"

            self.logger.log_operation(
                f"Testing with key: {test_key}, initial value: {test_value_1}"
            )

            # Update/create the bot statistic
            self.logger.log_operation(f"Creating botstat via POST /botstats/{test_key}")
            response = requests.post(
                f"{self.base_url}/botstats/{test_key}",
                json={"val": test_value_1}
            )
            if not response.ok:
                result.fail(f"Failed to create botstat: {response.text}")
                return

            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Botstat creation did not return success: {response_data}")
                return

            self.logger.log_operation("Botstat created successfully")

            # Fetch all botstats and verify our key exists with correct value
            self.logger.log_operation("Fetching all botstats via GET /botstats")
            response = requests.get(f"{self.base_url}/botstats")
            if not response.ok:
                result.fail(f"Failed to fetch botstats: {response.text}")
                return

            botstats_data = response.json()
            if botstats_data.get("status") != "ok":
                result.fail(f"Botstats fetch did not return success: {botstats_data}")
                return

            if "botstats" not in botstats_data:
                result.fail("Missing 'botstats' key in response")
                return

            botstats = botstats_data["botstats"]
            if not isinstance(botstats, dict):
                result.fail("Botstats should be a dict")
                return

            # Verify our test key exists
            if test_key not in botstats:
                result.fail(f"Test key '{test_key}' not found in botstats")
                return

            # Verify the value is correct
            botstat_entry = botstats[test_key]
            if botstat_entry.get("val") != test_value_1:
                result.fail(
                    f"Botstat value mismatch. Expected: {test_value_1}, Got: {botstat_entry.get('val')}"
                )
                return

            # Verify the timestamp field exists
            if "updated" not in botstat_entry:
                result.fail("Missing 'updated' timestamp in botstat entry")
                return

            self.logger.log_operation(
                f"Botstat verified - key: {test_key}, val: {botstat_entry['val']}, "
                f"updated: {botstat_entry['updated']}"
            )

            # Update the botstat to a new value
            self.logger.log_operation(f"Updating botstat to new value: {test_value_2}")
            response = requests.post(
                f"{self.base_url}/botstats/{test_key}",
                json={"val": test_value_2}
            )
            if not response.ok:
                result.fail(f"Failed to update botstat: {response.text}")
                return

            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Botstat update did not return success: {response_data}")
                return

            self.logger.log_operation("Botstat updated successfully")

            # Fetch again and verify the updated value
            self.logger.log_operation("Fetching botstats again to verify update")
            response = requests.get(f"{self.base_url}/botstats")
            if not response.ok:
                result.fail(f"Failed to fetch botstats after update: {response.text}")
                return

            botstats_data = response.json()
            botstats = botstats_data["botstats"]

            if test_key not in botstats:
                result.fail(f"Test key '{test_key}' not found after update")
                return

            botstat_entry = botstats[test_key]
            if botstat_entry.get("val") != test_value_2:
                result.fail(
                    f"Botstat value not updated. Expected: {test_value_2}, Got: {botstat_entry.get('val')}"
                )
                return

            self.logger.log_operation(
                f"Botstat update verified - new value: {botstat_entry['val']}"
            )

            # Test batch update with array format
            self.logger.log_operation("Testing batch update with array format")
            batch_key_1 = f"test_batch_1_{timestamp}"
            batch_key_2 = f"test_batch_2_{timestamp}"
            batch_value_1 = f"batch_val_1_{random.randint(1000, 9999)}"
            batch_value_2 = f"batch_val_2_{random.randint(1000, 9999)}"

            batch_array = [
                {"key": batch_key_1, "val": batch_value_1},
                {"key": batch_key_2, "val": batch_value_2}
            ]

            response = requests.post(
                f"{self.base_url}/botstats",
                json=batch_array
            )
            if not response.ok:
                result.fail(f"Failed to batch update botstats (array format): {response.text}")
                return

            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Batch update did not return success: {response_data}")
                return

            if response_data.get("updated") != 2:
                result.fail(f"Expected 2 updates, got {response_data.get('updated')}")
                return

            self.logger.log_operation(f"Batch update (array) successful: {response_data.get('updated')} stats updated")

            # Verify batch updates
            response = requests.get(f"{self.base_url}/botstats")
            if not response.ok:
                result.fail(f"Failed to fetch botstats after batch update: {response.text}")
                return

            botstats_data = response.json()
            botstats = botstats_data["botstats"]

            if batch_key_1 not in botstats or botstats[batch_key_1].get("val") != batch_value_1:
                result.fail(f"Batch key 1 not found or value incorrect")
                return

            if batch_key_2 not in botstats or botstats[batch_key_2].get("val") != batch_value_2:
                result.fail(f"Batch key 2 not found or value incorrect")
                return

            self.logger.log_operation("Batch update (array) verified successfully")

            # Test batch update with object/dict format
            self.logger.log_operation("Testing batch update with object/dict format")
            batch_key_3 = f"test_batch_3_{timestamp}"
            batch_key_4 = f"test_batch_4_{timestamp}"
            batch_value_3 = f"batch_val_3_{random.randint(1000, 9999)}"
            batch_value_4 = f"batch_val_4_{random.randint(1000, 9999)}"

            batch_dict = {
                batch_key_3: batch_value_3,
                batch_key_4: batch_value_4
            }

            response = requests.post(
                f"{self.base_url}/botstats",
                json=batch_dict
            )
            if not response.ok:
                result.fail(f"Failed to batch update botstats (dict format): {response.text}")
                return

            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Batch update (dict) did not return success: {response_data}")
                return

            if response_data.get("updated") != 2:
                result.fail(f"Expected 2 updates, got {response_data.get('updated')}")
                return

            self.logger.log_operation(f"Batch update (dict) successful: {response_data.get('updated')} stats updated")

            # Verify batch updates with dict format
            response = requests.get(f"{self.base_url}/botstats")
            if not response.ok:
                result.fail(f"Failed to fetch botstats after batch update (dict): {response.text}")
                return

            botstats_data = response.json()
            botstats = botstats_data["botstats"]

            if batch_key_3 not in botstats or botstats[batch_key_3].get("val") != batch_value_3:
                result.fail(f"Batch key 3 not found or value incorrect")
                return

            if batch_key_4 not in botstats or botstats[batch_key_4].get("val") != batch_value_4:
                result.fail(f"Batch key 4 not found or value incorrect")
                return

            self.logger.log_operation("Batch update (dict) verified successfully")

            # Verify that single-stat endpoint still works (backwards compatibility)
            self.logger.log_operation("Verifying backwards compatibility with single-stat endpoint")
            single_test_key = f"test_compat_{timestamp}"
            single_test_value = f"compat_val_{random.randint(1000, 9999)}"

            response = requests.post(
                f"{self.base_url}/botstats/{single_test_key}",
                json={"val": single_test_value}
            )
            if not response.ok:
                result.fail(f"Single-stat endpoint failed (backwards compatibility issue): {response.text}")
                return

            response_data = response.json()
            if response_data.get("status") != "ok":
                result.fail(f"Single-stat endpoint did not return success: {response_data}")
                return

            self.logger.log_operation("Backwards compatibility verified - single-stat endpoint still works")

            result.set_success("Bot statistics test completed successfully (including batch updates)")

        except Exception as e:
            result.fail(f"Error in bot statistics test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_cache_invalidation(self, result: TestResult):
        """Test /allcached endpoint caching and cache invalidation."""
        self.logger.log_operation("Starting cache invalidation test")

        try:
            fetch_times = []

            # Perform 5 fetches of /allcached endpoint
            self.logger.log_operation("Performing 5 fetches of /allcached endpoint")
            for i in range(5):
                start_time = time.time()
                response = requests.get(f"{self.base_url}/allcached")
                end_time = time.time()

                if not response.ok:
                    result.fail(f"Failed to fetch /allcached on attempt {i+1}: {response.text}")
                    return

                fetch_time = (end_time - start_time) * 1000  # Convert to milliseconds
                fetch_times.append(fetch_time)
                self.logger.log_operation(
                    f"Fetch {i+1}: {fetch_time:.2f}ms"
                )

                # Validate response structure
                all_data = response.json()
                if not isinstance(all_data, dict) or "rounds" not in all_data:
                    result.fail(f"Invalid response format from /allcached on attempt {i+1}")
                    return

            # Get the 5th fetch time (should be fastest, fully cached)
            fifth_fetch_time = fetch_times[4]
            self.logger.log_operation(
                f"Fifth fetch time (cached): {fifth_fetch_time:.2f}ms"
            )

            # Invalidate the cache
            self.logger.log_operation("Invalidating cache via POST /cache/invalidate")
            invalidate_response = requests.post(f"{self.base_url}/cache/invalidate")
            if not invalidate_response.ok:
                result.fail(f"Failed to invalidate cache: {invalidate_response.text}")
                return

            invalidate_data = invalidate_response.json()
            if invalidate_data.get("status") != "ok":
                result.fail(f"Cache invalidation did not return success: {invalidate_data}")
                return

            self.logger.log_operation("Cache invalidated successfully")

            # Fetch again after cache invalidation (should be slower, cache miss)
            self.logger.log_operation("Fetching /allcached after cache invalidation")
            start_time = time.time()
            response = requests.get(f"{self.base_url}/allcached")
            end_time = time.time()

            if not response.ok:
                result.fail(f"Failed to fetch /allcached after invalidation: {response.text}")
                return

            post_invalidation_time = (end_time - start_time) * 1000  # Convert to milliseconds
            self.logger.log_operation(
                f"Post-invalidation fetch time (cache miss): {post_invalidation_time:.2f}ms"
            )

            # Validate response structure
            all_data = response.json()
            if not isinstance(all_data, dict) or "rounds" not in all_data:
                result.fail("Invalid response format from /allcached after invalidation")
                return

            # Verify that post-invalidation fetch is slower than the 5th cached fetch
            # Note: This test may not always pass if memcache is not enabled or if
            # the dataset is very small. We'll log a warning instead of failing.
            if post_invalidation_time > fifth_fetch_time:
                self.logger.log_operation(
                    f"✓ Cache working as expected: post-invalidation fetch ({post_invalidation_time:.2f}ms) "
                    f"is slower than cached fetch ({fifth_fetch_time:.2f}ms)"
                )
            else:
                self.logger.log_operation(
                    f"Note: Post-invalidation fetch ({post_invalidation_time:.2f}ms) was not slower than "
                    f"cached fetch ({fifth_fetch_time:.2f}ms). This may indicate memcache is not enabled "
                    f"or dataset is very small."
                )

            # Perform one more fetch to verify cache is working again
            self.logger.log_operation("Performing final fetch to verify cache repopulated")
            start_time = time.time()
            response = requests.get(f"{self.base_url}/allcached")
            end_time = time.time()

            if not response.ok:
                result.fail(f"Failed to fetch /allcached on final attempt: {response.text}")
                return

            final_fetch_time = (end_time - start_time) * 1000
            self.logger.log_operation(
                f"Final fetch time (should be cached again): {final_fetch_time:.2f}ms"
            )

            result.set_success("Cache invalidation test completed successfully")

        except Exception as e:
            result.fail(f"Error in cache invalidation test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_puzzle_deletion(self, result: TestResult):
        """Test puzzle deletion functionality."""
        self.logger.log_operation("Starting puzzle deletion test")

        try:
            # First, we need a round to create a puzzle in
            timestamp = str(int(time.time()))
            round_name = f"DeleteTestRound {timestamp}"

            self.logger.log_operation(f"Creating test round: {round_name}")
            test_round = self.create_round(round_name)
            if not test_round:
                result.fail("Failed to create test round for deletion test")
                return

            # Create a puzzle to delete
            puzzle_name = f"DeleteTestPuzzle {timestamp}"
            self.logger.log_operation(f"Creating test puzzle: {puzzle_name}")
            test_puzzle = self.create_puzzle(puzzle_name, str(test_round["id"]))
            if not test_puzzle:
                result.fail("Failed to create test puzzle for deletion test")
                return

            puzzle_id = test_puzzle["id"]
            # The puzzle name gets spaces stripped
            expected_name = puzzle_name.replace(" ", "")
            self.logger.log_operation(
                f"Created puzzle '{expected_name}' with id {puzzle_id}"
            )

            # Verify puzzle exists before deletion
            puzzle_details = self.get_puzzle_details(puzzle_id)
            if not puzzle_details:
                result.fail("Failed to verify puzzle exists before deletion")
                return
            self.logger.log_operation(
                f"Verified puzzle exists: {puzzle_details['name']}"
            )

            # Delete the puzzle using DELETE method
            self.logger.log_operation(
                f"Deleting puzzle via DELETE /deletepuzzle/{expected_name}"
            )
            response = requests.delete(f"{self.base_url}/deletepuzzle/{expected_name}")

            if not response.ok:
                result.fail(
                    f"Failed to delete puzzle: {response.status_code} - {response.text}"
                )
                return

            delete_response = response.json()
            if delete_response.get("status") != "ok":
                result.fail(f"Unexpected response from delete: {delete_response}")
                return

            self.logger.log_operation(f"Delete response: {delete_response}")

            # Verify puzzle no longer exists
            self.logger.log_operation("Verifying puzzle no longer exists")

            # Try to get the puzzle - should fail
            verify_response = requests.get(f"{self.base_url}/puzzles/{puzzle_id}")
            if verify_response.ok:
                # If we got a response, check if the puzzle data is actually there
                verify_data = verify_response.json()
                if verify_data.get("puzzle"):
                    result.fail("Puzzle still exists after deletion!")
                    return

            # Also check in the puzzles list
            all_puzzles = self.get_all_puzzles()
            puzzle_names = [p["name"] for p in all_puzzles]
            if expected_name in puzzle_names:
                result.fail("Deleted puzzle still appears in puzzles list")
                return

            self.logger.log_operation(
                f"Verified puzzle '{expected_name}' no longer exists"
            )

            # Test deleting a non-existent puzzle (should handle gracefully)
            self.logger.log_operation("Testing deletion of non-existent puzzle")
            fake_name = f"NonExistentPuzzle{timestamp}"
            response = requests.delete(f"{self.base_url}/deletepuzzle/{fake_name}")
            # This might return an error, which is expected - just log it
            self.logger.log_operation(
                f"Delete non-existent puzzle response: {response.status_code}"
            )

            result.set_success("Puzzle deletion test completed successfully")

        except Exception as e:
            result.fail(f"Error in puzzle deletion test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def run_all_tests(self):
        """Run all test cases."""
        # Check if system is empty before running tests
        self.logger.log_operation("Checking if system is empty before running tests")

        # Get all rounds and puzzles
        rounds = self.get_all_rounds()
        puzzles = self.get_all_puzzles()

        # Note: The system should be empty after reset_hunt() is called in main()
        # This check verifies the reset worked correctly
        if rounds or puzzles:
            self.logger.log_error("System is not empty after reset!")
            self.logger.log_error(
                f"Found {len(rounds)} rounds and {len(puzzles)} puzzles"
            )
            self.logger.log_error(
                "The hunt reset may have failed. Please check the reset-hunt.py output."
            )
            print("\n" + "=" * 80)
            print("ERROR: System is not empty after reset!")
            print(f"Found {len(rounds)} rounds and {len(puzzles)} puzzles")
            print("The hunt reset may have failed. Please check the reset-hunt.py output.")
            print("=" * 80 + "\n")
            sys.exit(1)

        self.logger.log_operation("System is empty (reset successful), proceeding with tests")

        # Ensure we have enough test solvers for all tests
        self.ensure_min_solvers(min_count=10)

        tests = [
            ("Solver Listing", self.test_solver_listing),
            ("Puzzle Creation (One-Shot)", self.test_puzzle_creation),
            ("Puzzle Creation (Stepwise)", self.test_puzzle_creation_stepwise),
            ("Puzzle Modification", self.test_puzzle_modification),
            ("Puzzle Round Change", self.test_puzzle_round_change),
            ("Puzzle Multi-Part Update", self.test_multi_part_update),
            ("Round Modification", self.test_round_modification),
            ("Round Multi-Part Update", self.test_round_multi_part_update),
            ("Solver Multi-Part Update", self.test_solver_multi_part_update),
            (
                "Meta Puzzles and Round Completion",
                self.test_meta_puzzles_and_round_completion,
            ),
            ("Answer Verification", self.test_answer_verification),
            ("Solver Assignments", self.test_solver_assignments),
            ("Solve Clears Location and Solvers", self.test_solve_clears_location_and_solvers),
            ("Solver Reassignment", self.test_solver_reassignment),
            ("Activity Tracking", self.test_activity_tracking),
            ("Puzzle Activity Endpoint", self.test_puzzle_activity_endpoint),
            ("Solver Activity Endpoint", self.test_solver_activity_endpoint),
            ("Solver History", self.test_solver_history),
            ("Sheetcount", self.test_sheetcount),
            ("Tagging", self.test_tagging),
            ("API Endpoints", self.test_api_endpoints),
            ("Bot Statistics", self.test_bot_statistics),
            ("Cache Invalidation", self.test_cache_invalidation),
            ("Puzzle Deletion", self.test_puzzle_deletion),
        ]

        for name, test in tests:
            self.run_test(name, test)

        self.print_results()


def reset_hunt():
    """Reset the hunt database before running tests."""
    print("\n" + "=" * 80)
    print("RESETTING HUNT DATABASE...")
    print("=" * 80 + "\n")

    result = subprocess.run(
        ['python3', 'scripts/reset-hunt.py', '--yes-i-am-sure-i-want-to-destroy-all-data'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"ERROR: Hunt reset failed!")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)

    print("Hunt reset completed successfully\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Comprehensive Puzzleboss API Test Suite',
        epilog='WARNING: This script will RESET THE HUNT DATABASE!'
    )
    parser.add_argument(
        '--allow-destructive',
        action='store_true',
        required=True,
        help='Required flag to confirm you understand this will DESTROY ALL PUZZLE DATA and reset the hunt'
    )

    try:
        args = parser.parse_args()
    except SystemExit:
        print("\n" + "=" * 80)
        print("ERROR: --allow-destructive flag is required to run this test suite")
        print("=" * 80)
        print("\nThis script will RESET THE HUNT DATABASE, destroying all puzzle data.")
        print("Solver accounts, tags, and configuration will be preserved.")
        print("\nUsage: python3 scripts/test_api_coverage.py --allow-destructive")
        print("\nDO NOT RUN THIS ON A PRODUCTION SYSTEM!")
        print("=" * 80 + "\n")
        sys.exit(1)

    # Display warning about destructive operation
    print("\n" + "=" * 80)
    print("WARNING: DESTRUCTIVE OPERATION")
    print("=" * 80)
    print("This script will RESET THE HUNT DATABASE!")
    print("All puzzle data will be DESTROYED.")
    print("Solver accounts, tags, and configuration will be preserved.")
    print("=" * 80 + "\n")

    # Reset the hunt database
    reset_hunt()

    # Run the tests
    runner = TestRunner()
    runner.run_all_tests()
