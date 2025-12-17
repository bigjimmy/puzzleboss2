#!/usr/bin/env python3

import requests
import random
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
import json
import sys
import traceback
import string

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
        self.emojis = ["🎲", "🎯", "🎨", "🎪", "🎭", "🎫", "🎮", "🎰", "🎱", "🎲", 
                      "🎸", "🎹", "🎺", "🎻", "🎼", "🎵", "🎶", "🎷", "🎸", "🎹"]
        
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
        print(f"Total duration: {(datetime.now() - self.test_start_time).total_seconds():.2f}s")

    def get_all_solvers(self) -> List[Dict]:
        self.logger.log_operation("Fetching all solvers")
        response = requests.get(f"{BASE_URL}/solvers")
        if not response.ok:
            raise Exception(f"Failed to get solvers: {response.text}")
        solvers = response.json()["solvers"]
        self.logger.log_operation(f"Found {len(solvers)} solvers")
        return solvers

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
                self.logger.log_error(f"Failed to get puzzle {puzzle_id}: {response.text}")
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
                self.logger.log_error(f"Failed to get solver {solver_id}: {response.text}")
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
                self.logger.log_error(f"Failed to get round {round_id}: {response.text}")
                return None
            return response.json()["round"]
        except Exception as e:
            self.logger.log_error(f"Error getting round details: {str(e)}")
            return None

    def create_round(self, name: str) -> Dict:
        """Create a new round with detailed error handling"""
        try:
            self.logger.log_operation(f"Creating round: {name}")
            response = requests.post(
                f"{BASE_URL}/rounds",
                json={"name": name}
            )
            
            if not response.ok:
                self.logger.log_error(f"HTTP error creating round {name}: {response.status_code}")
                self.logger.log_error(f"Response text: {response.text}")
                raise Exception(f"HTTP error creating round: {response.status_code} - {response.text}")
            
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                self.logger.log_error(f"Failed to parse JSON response for round {name}")
                self.logger.log_error(f"Response text: {response.text}")
                self.logger.log_error(f"JSON decode error: {str(e)}")
                raise Exception(f"JSON decode error: {str(e)}")
            
            if "status" not in response_data or response_data["status"] != "ok":
                self.logger.log_error(f"Unexpected response format creating round {name}")
                self.logger.log_error(f"Full response: {response_data}")
                raise Exception(f"Unexpected response format: {response_data}")
            
            if "round" not in response_data:
                self.logger.log_error(f"Missing round data in response for {name}")
                self.logger.log_error(f"Full response: {response_data}")
                raise Exception(f"Missing round data in response: {response_data}")
            
            # Get the round ID by querying the round by name
            rounds_response = requests.get(f"{BASE_URL}/rounds")
            if not rounds_response.ok:
                self.logger.log_error(f"Failed to get rounds list: {rounds_response.text}")
                raise Exception(f"Failed to get rounds list: {rounds_response.text}")
                
            rounds_data = rounds_response.json()
            if "rounds" not in rounds_data:
                self.logger.log_error(f"Unexpected format in rounds list: {rounds_data}")
                raise Exception(f"Unexpected format in rounds list: {rounds_data}")
                
            # Find the round we just created
            round_data = None
            sanitized_name = name.replace(" ", "")
            for round in rounds_data["rounds"]:
                if round["name"].replace(" ", "") == sanitized_name:
                    round_data = round
                    break
                    
            if not round_data:
                self.logger.log_error(f"Could not find newly created round {name} in rounds list")
                self.logger.log_error(f"Available rounds: {[r['name'] for r in rounds_data['rounds']]}")
                raise Exception(f"Could not find newly created round {name} in rounds list")
                
            self.logger.log_operation(f"Created round {name} with id {round_data['id']}")
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

    def create_puzzle(self, name: str, round_id: str) -> Dict:
        """Create a new puzzle with detailed error handling"""
        try:
            self.logger.log_operation(f"Creating puzzle: {name} in round {round_id}")
            
            # Convert round_id to integer for the API
            round_id_int = int(round_id)
            
            # Prepare request data
            request_data = {
                "puzzle": {
                    "name": name,
                    "round_id": round_id_int,
                    "puzzle_uri": "http://example.com/puzzle"
                }
            }
            
            # Make the API request
            response = requests.post(f"{self.base_url}/puzzles", json=request_data)
            
            if not response.ok:
                self.logger.log_error(f"HTTP error creating puzzle {name}: {response.status_code}")
                self.logger.log_error(f"Response text: {response.text}")
                raise Exception(f"HTTP error creating puzzle: {response.status_code} - {response.text}")
            
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                self.logger.log_error(f"Failed to parse JSON response for puzzle {name}")
                self.logger.log_error(f"Response text: {response.text}")
                self.logger.log_error(f"JSON decode error: {str(e)}")
                raise Exception(f"JSON decode error: {str(e)}")
            
            if "status" not in response_data or response_data["status"] != "ok":
                self.logger.log_error(f"Unexpected response format creating puzzle {name}")
                self.logger.log_error(f"Full response: {response_data}")
                raise Exception(f"Unexpected response format: {response_data}")
            
            # Get the puzzle details to verify creation
            puzzles_response = requests.get(f"{BASE_URL}/puzzles")
            if not puzzles_response.ok:
                self.logger.log_error(f"Failed to get puzzles list: {puzzles_response.text}")
                raise Exception(f"Failed to get puzzles list: {puzzles_response.text}")
                
            puzzles_data = puzzles_response.json()
            if "puzzles" not in puzzles_data:
                self.logger.log_error(f"Unexpected format in puzzles list: {puzzles_data}")
                raise Exception(f"Unexpected format in puzzles list: {puzzles_data}")
                
            # Find the puzzle we just created - look for space-stripped name
            puzzle_data = None
            expected_name = name.replace(" ", "")
            for puzzle in puzzles_data["puzzles"]:
                if puzzle["name"] == expected_name:
                    puzzle_data = puzzle
                    break
                    
            if not puzzle_data:
                self.logger.log_error(f"Could not find newly created puzzle {expected_name} in puzzles list")
                self.logger.log_error(f"Available puzzles: {[p['name'] for p in puzzles_data['puzzles']]}")
                raise Exception(f"Could not find newly created puzzle {expected_name} in puzzles list")
                
            # Get full puzzle details
            puzzle_details = self.get_puzzle_details(puzzle_data["id"])
            if not puzzle_details:
                self.logger.log_error(f"Failed to get details for puzzle {expected_name}")
                raise Exception(f"Failed to get details for puzzle {expected_name}")
                
            self.logger.log_operation(f"Created puzzle {expected_name} with id {puzzle_data['id']}")
            return puzzle_details
            
        except requests.RequestException as e:
            self.logger.log_error(f"Request exception creating puzzle {name}")
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
                f"{self.base_url}/puzzles/{puzzle_id}/{field}",
                json={field: value}
            )
            if not response.ok:
                return False
            response_data = response.json()
            if response_data.get('status') != 'ok':
                return False
            return True
        except Exception as e:
            self.logger.log_error(f"Error updating puzzle: {str(e)}")
            return False

    def assign_solver_to_puzzle(self, solver_id: str, puzzle_id: str) -> bool:
        """Assign a solver to a puzzle."""
        try:
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}/puzz",
                json={"puzz": puzzle_id}
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.log_error(f"Error assigning solver to puzzle: {str(e)}")
            return False

    def add_solver_to_history(self, puzzle_id: str, solver_id: str) -> bool:
        self.logger.log_operation(f"Adding solver {solver_id} to puzzle {puzzle_id} history")
        response = requests.post(
            f"{BASE_URL}/puzzles/{puzzle_id}/history/add",
            json={"solver_id": solver_id}
        )
        if not response.ok:
            raise Exception(f"Failed to add solver {solver_id} to puzzle {puzzle_id} history: {response.text}")
        self.logger.log_operation(f"Successfully added solver {solver_id} to puzzle {puzzle_id} history")
        return True

    def remove_solver_from_history(self, puzzle_id: str, solver_id: str) -> bool:
        self.logger.log_operation(f"Removing solver {solver_id} from puzzle {puzzle_id} history")
        response = requests.post(
            f"{BASE_URL}/puzzles/{puzzle_id}/history/remove",
            json={"solver_id": solver_id}
        )
        if not response.ok:
            raise Exception(f"Failed to remove solver {solver_id} from puzzle {puzzle_id} history: {response.text}")
        self.logger.log_operation(f"Successfully removed solver {solver_id} from puzzle {puzzle_id} history")
        return True

    def update_round(self, round_id: int, updates: Dict) -> Dict:
        """Update a round with the given updates"""
        try:
            self.logger.log_operation(f"Updating round {round_id} with {updates}")
            for part, value in updates.items():
                response = requests.post(
                    f"{BASE_URL}/rounds/{round_id}/{part}",
                    json={part: value}
                )
                
                if not response.ok:
                    self.logger.log_error(f"HTTP error updating round {round_id} {part}: {response.status_code}")
                    self.logger.log_error(f"Response text: {response.text}")
                    raise Exception(f"HTTP error updating round: {response.status_code} - {response.text}")
                
                try:
                    response_data = response.json()
                except json.JSONDecodeError as e:
                    self.logger.log_error(f"Failed to parse JSON response for round {round_id} {part}")
                    self.logger.log_error(f"Response text: {response.text}")
                    self.logger.log_error(f"JSON decode error: {str(e)}")
                    raise Exception(f"JSON decode error: {str(e)}")
                
                if "status" not in response_data or response_data["status"] != "ok":
                    self.logger.log_error(f"Unexpected response format updating round {round_id} {part}")
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
        """Test puzzle creation functionality."""
        self.logger.log_operation("Starting puzzle creation test")
        
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
                
            # Create 4 puzzles in each round
            for round_idx, round_data in enumerate(rounds):
                self.logger.log_operation(f"Creating puzzles for round {round_data['name']}")
                puzzles = []
                for puzzle_idx in range(4):
                    # Create puzzle name with spaces and emojis for even-numbered puzzles
                    base_name = f"Test Puzzle R{round_idx+1}P{puzzle_idx+1} {int(time.time())}"
                    puzzle_name = self.get_emoji_string(base_name, include_emoji=(puzzle_idx % 2 == 0))
                    
                    # Create the puzzle
                    puzzle_data = self.create_puzzle(puzzle_name, str(round_data['id']))
                    if not puzzle_data:
                        result.fail(f"Failed to create puzzle {puzzle_name}")
                        return
                        
                    # Verify the name was stripped of spaces but emojis preserved
                    expected_name = puzzle_name.replace(" ", "")
                    if puzzle_data['name'] != expected_name:
                        result.fail(f"Puzzle name not properly processed. Expected: {expected_name}, Got: {puzzle_data['name']}")
                        return
                        
                    puzzles.append(puzzle_data)
                    
                # Verify all puzzles were created in the correct round
                for puzzle in puzzles:
                    if str(puzzle['round_id']) != str(round_data['id']):
                        result.fail(f"Puzzle {puzzle['name']} created in wrong round")
                        return
                        
            result.set_success("Puzzle creation test completed successfully")
            
        except Exception as e:
            result.fail(f"Error in puzzle creation test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_puzzle_modification(self, result: TestResult):
        """Test puzzle modification functionality."""
        self.logger.log_operation("Starting puzzle modification test")
        
        # Get all puzzles
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("Failed to get puzzles")
            return
            
        # Get full puzzle details for each puzzle
        detailed_puzzles = []
        for puzzle in puzzles:
            puzzle_details = self.get_puzzle_details(puzzle['id'])
            if puzzle_details:
                detailed_puzzles.append(puzzle_details)
            
        if not detailed_puzzles:
            result.fail("Failed to get puzzle details")
            return
            
        # Group puzzles by round
        puzzles_by_round = {}
        for puzzle in detailed_puzzles:
            round_id = str(puzzle.get('round_id', ''))
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
        puzzles_for_answers = random.sample(selected_puzzles, len(selected_puzzles) // 2)
        puzzles_for_answers_set = set(p['id'] for p in puzzles_for_answers)
            
        # For each selected puzzle, test modifications
        for idx, puzzle in enumerate(selected_puzzles):
            self.logger.log_operation(f"Testing modifications for puzzle {puzzle['name']}")
            
            # Test status update
            new_status = "Being worked"
            self.logger.log_operation(f"Updating status to '{new_status}'")
            if not self.update_puzzle(puzzle["id"], "status", new_status):
                result.fail(f"Failed to update status for puzzle {puzzle['name']}")
                continue
                
            # Verify status update
            updated_puzzle = self.get_puzzle_details(puzzle["id"])
            if not updated_puzzle:
                result.fail(f"Failed to verify status update for puzzle {puzzle['name']}")
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
                    result.fail(f"Failed to verify puzzle solve for puzzle {puzzle['name']}")
                    continue
                    
                # Convert both to uppercase for comparison
                expected_upper = answer.upper()
                actual_upper = updated_puzzle.get('answer', '').upper()
                
                if expected_upper != actual_upper:
                    self.logger.log_error(f"DEBUG - Puzzle before answer update: {puzzle}")
                    self.logger.log_error(f"DEBUG - Updated puzzle after answer set: {updated_puzzle}")
                    self.logger.log_error(f"DEBUG - Expected answer: {answer}")
                    self.logger.log_error(f"DEBUG - Actual answer: {updated_puzzle.get('answer')}")
                    self.logger.log_error(f"DEBUG - Expected (upper): {expected_upper}")
                    self.logger.log_error(f"DEBUG - Actual (upper): {actual_upper}")
                    self.logger.log_error(f"DEBUG - Answer comparison: {expected_upper == actual_upper}")
                    result.fail(f"Answer verification failed for puzzle {puzzle['name']}")
                    continue
                    
                if updated_puzzle["status"] != "Solved":
                    result.fail(f"Status not automatically set to 'Solved' for puzzle {puzzle['name']}")
                    continue
            else:
                self.logger.log_operation(f"Skipping answer update for puzzle {puzzle['name']} (not selected for answer testing)")
                
            # Test comments update
            new_comments = f"Test comments for {puzzle['name']}"
            self.logger.log_operation(f"Updating comments to '{new_comments}'")
            if not self.update_puzzle(puzzle["id"], "comments", new_comments):
                result.fail(f"Failed to update comments for puzzle {puzzle['name']}")
                continue
                
            # Verify comments update
            updated_puzzle = self.get_puzzle_details(puzzle["id"])
            if not updated_puzzle:
                result.fail(f"Failed to verify comments update for puzzle {puzzle['name']}")
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
                    result.fail(f"Failed to update location for puzzle {puzzle['name']}")
                    continue
                    
                # Verify location update
                updated_puzzle = self.get_puzzle_details(puzzle["id"])
                if not updated_puzzle:
                    result.fail(f"Failed to verify location update for puzzle {puzzle['name']}")
                    continue
                    
                if updated_puzzle["xyzloc"] != new_location:
                    result.fail(f"Location not updated for puzzle {puzzle['name']}")
                    continue
            else:
                self.logger.log_operation(f"Skipping location update for puzzle {puzzle['name']} (every other puzzle)")
                
        result.set_success("Puzzle modification test completed successfully")

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
            self.logger.log_operation(f"Selected round for testing: {test_round['name']}")
            
            # Create two new puzzles for testing
            timestamp = str(int(time.time()))
            meta_puzzle1 = self.create_puzzle(f"Test Meta Puzzle 1 {timestamp}", test_round['id'])
            meta_puzzle2 = self.create_puzzle(f"Test Meta Puzzle 2 {timestamp}", test_round['id'])
            
            if not meta_puzzle1 or not meta_puzzle2:
                result.fail("Failed to create test meta puzzles")
                return
                
            self.logger.log_operation(f"Created test meta puzzles: {meta_puzzle1['name']}, {meta_puzzle2['name']}")
            
            # Set puzzles as meta
            for meta_puzzle in [meta_puzzle1, meta_puzzle2]:
                if not self.update_puzzle(meta_puzzle['id'], 'ismeta', True):
                    result.fail(f"Failed to set puzzle {meta_puzzle['name']} as meta")
                    return
                    
                # Verify meta status
                puzzle_details = self.get_puzzle_details(meta_puzzle['id'])
                if not puzzle_details.get('ismeta'):
                    result.fail(f"Puzzle {meta_puzzle['name']} not marked as meta after update")
                    return
                    
            # Create a non-meta puzzle and solve it
            non_meta_puzzle = self.create_puzzle(f"Test Non-Meta Puzzle {timestamp}", test_round['id'])
            if not non_meta_puzzle:
                result.fail("Failed to create test non-meta puzzle")
                return
                
            if not self.update_puzzle(non_meta_puzzle['id'], 'answer', 'TEST ANSWER'):
                result.fail(f"Failed to set answer for puzzle {non_meta_puzzle['name']}")
                return
                
            # Verify answer was set
            puzzle_details = self.get_puzzle_details(non_meta_puzzle['id'])
            if puzzle_details.get('answer') != 'TEST ANSWER':
                result.fail(f"Answer not set for puzzle {non_meta_puzzle['name']}")
                return
                
            # Verify round is not solved when non-meta puzzle is solved but metas are not
            if self.is_round_complete(test_round['id']):
                result.fail("Round marked complete before meta puzzles were solved")
                return
                
            # Solve first meta puzzle
            if not self.update_puzzle(meta_puzzle1['id'], 'answer', 'META ANSWER 1'):
                result.fail(f"Failed to set answer for meta puzzle {meta_puzzle1['name']}")
                return
                
            # Verify round is still not solved
            if self.is_round_complete(test_round['id']):
                result.fail("Round marked complete when only one meta puzzle was solved")
                return
                
            # Solve the second meta puzzle
            if not self.update_puzzle(meta_puzzle2['id'], 'answer', 'META ANSWER 2'):
                result.fail(f"Failed to set answer for meta puzzle {meta_puzzle2['name']}")
                return
                
            # Verify round is now solved
            if not self.is_round_complete(test_round['id']):
                result.fail("Round not marked complete after all meta puzzles were solved")
                return
                
            # Log the round's status
            round_status = self.get_round_status(test_round['id'])
            self.logger.log_operation(f"Round {test_round['name']} status after solving all meta puzzles: {round_status}")
                
            result.set_success("Meta puzzles and round completion test completed successfully")
            
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
            return round_data.get('status') == 'Solved'
        except Exception as e:
            self.logger.log_error(f"Error checking round completion: {str(e)}")
            return False

    def get_round_status(self, round_id: int) -> str:
        """Get the status of a round by checking its status field."""
        try:
            round_data = self.get_round(round_id)
            if not round_data:
                return ''
            return round_data.get('status', '')
        except Exception as e:
            self.logger.log_error(f"Error getting round status: {str(e)}")
            return ''

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
            self.logger.log_operation(f"Testing answer verification for puzzle {puzzle['name']}")
            
            # Generate a random answer with spaces and emoji
            test_answer = f"Test Answer {random.randint(1000, 9999)} 🎯"
            
            # Update the puzzle's answer
            if not self.update_puzzle(puzzle['id'], 'answer', test_answer):
                result.fail(f"Failed to set answer for puzzle {puzzle['name']}")
                continue
                
            # Verify the answer was set and status changed to solved
            puzzle_details = self.get_puzzle_details(puzzle['id'])
            if not puzzle_details:
                result.fail(f"Failed to get puzzle details for {puzzle['name']}")
                continue
                
            # Check that answer was set
            if 'answer' not in puzzle_details:
                result.fail(f"Answer field missing for puzzle {puzzle['name']}")
                continue
                
            # Verify the answer was set correctly (converted to all caps but spaces preserved)
            expected_answer = test_answer.upper()
            if puzzle_details['answer'] != expected_answer:
                result.fail(f"Answer not set correctly for puzzle {puzzle['name']}. Expected: {expected_answer}, Got: {puzzle_details['answer']}")
                continue
                
            # Check that status was changed to solved
            if puzzle_details.get('status') != 'Solved':
                result.fail(f"Status not changed to 'Solved' for puzzle {puzzle['name']}")
                continue
                
        result.set_success("Answer verification test completed successfully")

    def test_solver_assignments(self, result: TestResult):
        """Test solver assignment functionality."""
        try:
            # Get all solvers and puzzles
            solvers = self.get_all_solvers()
            puzzles = self.get_all_puzzles()
            
            if not solvers or not puzzles:
                result.fail("Failed to get solvers or puzzles")
                return
                
            self.logger.log_operation(f"Found {len(solvers)} solvers and {len(puzzles)} puzzles")
            
            # Get full puzzle details for each puzzle
            detailed_puzzles = []
            for puzzle in puzzles:
                puzzle_details = self.get_puzzle_details(puzzle['id'])
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
                round_id = str(puzzle.get('round_id', ''))
                if round_id:
                    if round_id not in puzzles_by_round:
                        puzzles_by_round[round_id] = []
                    puzzles_by_round[round_id].append(puzzle)
                    
            self.logger.log_operation(f"Found {len(puzzles_by_round)} rounds with puzzles")
            
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
                
            self.logger.log_operation(f"Selected {len(selected_puzzles)} puzzles for assignment testing")
                
            # For each selected puzzle, assign 2 random solvers
            for puzzle in selected_puzzles:
                # Select 2 random solvers
                if len(solvers) < 2:
                    result.fail("Not enough solvers available for testing")
                    continue
                    
                selected_solvers = random.sample(solvers, 2)
                
                for solver in selected_solvers:
                    # Assign solver to puzzle
                    success = self.assign_solver_to_puzzle(solver['id'], puzzle['id'])
                    if not success:
                        result.fail(f"Failed to assign solver {solver['name']} to puzzle {puzzle['name']}")
                        continue
                        
                    # Verify assignment
                    solver_details = self.get_solver_details(solver['id'])
                    if not solver_details:
                        result.fail(f"Failed to get solver details for {solver['name']}")
                        continue
                        
                    if solver_details.get('puzz') != puzzle['name']:
                        result.fail(f"Solver {solver['name']} not properly assigned to puzzle {puzzle['name']}")
                        continue
                        
                    self.logger.log_operation(f"Successfully assigned solver {solver['name']} to puzzle {puzzle['name']}")
                
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
            puzzle_details = self.get_puzzle_details(puzzle['id'])
            if puzzle_details:
                detailed_puzzles.append(puzzle_details)
            
        if not detailed_puzzles:
            result.fail("Failed to get puzzle details")
            return
            
        # Group puzzles by round
        puzzles_by_round = {}
        for puzzle in detailed_puzzles:
            round_id = str(puzzle.get('round_id', ''))
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
            
        # For each selected puzzle, assign 2 random solvers and check activity
        for puzzle in selected_puzzles:
            self.logger.log_operation(f"Testing activity for puzzle {puzzle['name']}")
            
            # Select 2 random solvers
            if len(solvers) < 2:
                result.fail("Not enough solvers available for testing")
                continue
                
            selected_solvers = random.sample(solvers, 2)
            
            for solver in selected_solvers:
                self.logger.log_operation(f"Assigning solver {solver['name']} to puzzle {puzzle['name']}")
                
                # Assign solver to puzzle
                if not self.assign_solver_to_puzzle(solver['id'], puzzle['id']):
                    result.fail(f"Failed to assign solver {solver['name']} to puzzle {puzzle['name']}")
                    continue
                    
                # Check activity for the puzzle
                puzzle_details = self.get_puzzle_details(puzzle['id'])
                if not puzzle_details:
                    result.fail(f"Failed to get details for puzzle {puzzle['name']}")
                    continue
                    
                # Get lastact specifically using the puzzle part endpoint
                response = requests.get(f"{self.base_url}/puzzles/{puzzle['id']}/lastact")
                if not response.ok:
                    result.fail(f"Failed to get lastact for puzzle {puzzle['name']}: {response.text}")
                    return
                    
                last_activity = response.json().get('puzzle', {}).get('lastact')
                if not last_activity:
                    result.fail(f"No lastact found for puzzle {puzzle['name']}")
                    return
                    
                # Verify lastact structure
                if not all(key in last_activity for key in ['time', 'type', 'source', 'uri']):
                    result.fail(f"Invalid lastact structure for puzzle {puzzle['name']}")
                    return
                
        result.set_success("Activity tracking test completed successfully")

    def test_solver_history(self, result: TestResult):
        """Test adding and removing solvers from puzzle history."""
        try:
            # Get all solvers and puzzles
            solvers = self.get_all_solvers()
            puzzles = self.get_all_puzzles()
            
            if not solvers or not puzzles:
                result.fail("Failed to get solvers or puzzles")
                return
                
            self.logger.log_operation(f"Found {len(solvers)} solvers and {len(puzzles)} puzzles")
            
            # Get full puzzle details for each puzzle
            detailed_puzzles = []
            for puzzle in puzzles:
                puzzle_details = self.get_puzzle_details(puzzle['id'])
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
                round_id = str(puzzle.get('round_id', ''))
                if round_id:
                    if round_id not in puzzles_by_round:
                        puzzles_by_round[round_id] = []
                    puzzles_by_round[round_id].append(puzzle)
                    
            self.logger.log_operation(f"Found {len(puzzles_by_round)} rounds with puzzles")
            
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
                
            self.logger.log_operation(f"Selected {len(selected_puzzles)} puzzles for history testing")
                
            # For each selected puzzle, test history operations with 2 random solvers
            for puzzle in selected_puzzles:
                # Select 2 random solvers
                if len(solvers) < 2:
                    result.fail("Not enough solvers available for testing")
                    continue
                    
                selected_solvers = random.sample(solvers, 2)
                
                for solver in selected_solvers:
                    # Add solver to history
                    success = self.add_solver_to_history(puzzle['id'], solver['id'])
                    if not success:
                        result.fail(f"Failed to add solver {solver['name']} to history for puzzle {puzzle['name']}")
                        continue
                        
                    # Verify history addition
                    puzzle_data = self.get_puzzle_details(puzzle['id'])
                    if not puzzle_data:
                        result.fail(f"Failed to get updated puzzle data for {puzzle['name']}")
                        continue
                        
                    # Check if solver is in historical solvers list
                    historical_solvers = puzzle_data.get('solvers', '')
                    if historical_solvers is None:
                        historical_solvers = ''
                    if solver['name'] not in historical_solvers:
                        result.fail(f"Solver {solver['name']} not found in puzzle's historical solvers")
                        continue
                        
                    self.logger.log_operation(f"Successfully added solver {solver['name']} to history for puzzle {puzzle['name']}")
                    
                    # Remove from history
                    success = self.remove_solver_from_history(puzzle['id'], solver['id'])
                    if not success:
                        result.fail(f"Failed to remove solver {solver['name']} from history for puzzle {puzzle['name']}")
                        continue
                        
                    # Verify history removal
                    puzzle_data = self.get_puzzle_details(puzzle['id'])
                    if not puzzle_data:
                        result.fail(f"Failed to get updated puzzle data for {puzzle['name']}")
                        continue
                        
                    # Check if solver is no longer in historical solvers list
                    historical_solvers = puzzle_data.get('solvers', '')
                    if historical_solvers is None:
                        historical_solvers = ''
                    if solver['name'] in historical_solvers:
                        result.fail(f"Solver {solver['name']} still found in puzzle's historical solvers after removal")
                        continue
                        
                    self.logger.log_operation(f"Successfully removed solver {solver['name']} from history for puzzle {puzzle['name']}")
                
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
                solver_details = self.get_solver_details(solver['id'])
                if solver_details and solver_details.get('puzz'):
                    assigned_solvers.append(solver)
                    
            if len(assigned_solvers) < 2:
                result.fail("Need at least 2 solvers already assigned to puzzles for reassignment test")
                return
                
            # Select two random assigned solvers
            solver1, solver2 = random.sample(assigned_solvers, 2)
            
            # Get their current puzzles
            solver1_details = self.get_solver_details(solver1['id'])
            solver2_details = self.get_solver_details(solver2['id'])
            solver1_current_puzzle = solver1_details.get('puzz')
            solver2_current_puzzle = solver2_details.get('puzz')
            
            # Filter out puzzles that are currently assigned to either solver
            available_puzzles = []
            for puzzle in puzzles:
                if puzzle['name'] != solver1_current_puzzle and puzzle['name'] != solver2_current_puzzle:
                    available_puzzles.append(puzzle)
                    
            if len(available_puzzles) < 2:
                result.fail("Not enough puzzles available that aren't already assigned to the selected solvers")
                return
                
            # Select two random puzzles from the available ones
            puzzle1, puzzle2 = random.sample(available_puzzles, 2)
            
            self.logger.log_operation(f"Selected puzzles: {puzzle1['name']}, {puzzle2['name']}")
            self.logger.log_operation(f"Selected solvers: {solver1['name']} (currently on {solver1_current_puzzle}), {solver2['name']} (currently on {solver2_current_puzzle})")
            
            # Assign both solvers to first puzzle
            for solver in [solver1, solver2]:
                self.logger.log_operation(f"Attempting to assign solver {solver['name']} to puzzle {puzzle1['name']}")
                if not self.update_solver_puzzle(solver['id'], puzzle1['id']):
                    result.fail(f"Failed to assign solver {solver['name']} to puzzle {puzzle1['name']}")
                    return
                self.logger.log_operation(f"Successfully assigned solver {solver['name']} to puzzle {puzzle1['name']}")
                    
            # Verify initial assignments
            puzzle1_details = self.get_puzzle_details(puzzle1['id'])
            if not puzzle1_details:
                result.fail(f"Failed to get details for puzzle {puzzle1['name']}")
                return
                
            # Check puzzle's current solvers
            current_solvers = puzzle1_details.get('cursolvers', '') or ''
            self.logger.log_operation(f"Current solvers for puzzle {puzzle1['name']}: {current_solvers}")
            if solver1['name'] not in current_solvers.split(',') or solver2['name'] not in current_solvers.split(','):
                result.fail(f"Solvers not properly assigned to puzzle {puzzle1['name']}")
                self.logger.log_error(f"Expected solvers: {solver1['name']}, {solver2['name']}")
                self.logger.log_error(f"Actual solvers: {current_solvers}")
                return
                
            # Check solvers' current puzzles
            for solver in [solver1, solver2]:
                solver_details = self.get_solver_details(solver['id'])
                self.logger.log_operation(f"Solver {solver['name']} current puzzle: {solver_details.get('puzz')}")
                if solver_details.get('puzz') != puzzle1['name']:
                    result.fail(f"Solver {solver['name']} not properly assigned to puzzle {puzzle1['name']}")
                    return
                    
            # Reassign first solver to second puzzle
            self.logger.log_operation(f"Attempting to reassign solver {solver1['name']} to puzzle {puzzle2['name']}")
            if not self.update_solver_puzzle(solver1['id'], puzzle2['id']):
                result.fail(f"Failed to reassign solver {solver1['name']} to puzzle {puzzle2['name']}")
                return
            self.logger.log_operation(f"Successfully reassigned solver {solver1['name']} to puzzle {puzzle2['name']}")
                
            # Verify reassignment
            puzzle1_details = self.get_puzzle_details(puzzle1['id'])
            puzzle2_details = self.get_puzzle_details(puzzle2['id'])
            solver1_details = self.get_solver_details(solver1['id'])
            solver2_details = self.get_solver_details(solver2['id'])
            
            if not puzzle1_details or not puzzle2_details or not solver1_details or not solver2_details:
                result.fail("Failed to get details after reassignment")
                return
                
            # Check solver is no longer assigned to old puzzle
            current_solvers = puzzle1_details.get('cursolvers', '') or ''
            self.logger.log_operation(f"Current solvers for puzzle {puzzle1['name']} after reassignment: {current_solvers}")
            if solver1['name'] in current_solvers.split(','):
                result.fail(f"Solver {solver1['name']} still assigned to old puzzle {puzzle1['name']}")
                return
                
            # Check solver is assigned to new puzzle
            current_solvers = puzzle2_details.get('cursolvers', '') or ''
            self.logger.log_operation(f"Current solvers for puzzle {puzzle2['name']} after reassignment: {current_solvers}")
            if solver1['name'] not in current_solvers.split(','):
                result.fail(f"Solver {solver1['name']} not assigned to new puzzle {puzzle2['name']}")
                return
                
            # Check solver's current puzzle is updated
            self.logger.log_operation(f"Solver {solver1['name']} current puzzle after reassignment: {solver1_details.get('puzz')}")
            if solver1_details.get('puzz') != puzzle2['name']:
                result.fail(f"Solver {solver1['name']} not properly reassigned to puzzle {puzzle2['name']}")
                return
                
            # Check solver2 is still assigned to puzzle1
            self.logger.log_operation(f"Solver {solver2['name']} current puzzle after reassignment: {solver2_details.get('puzz')}")
            if solver2_details.get('puzz') != puzzle1['name']:
                result.fail(f"Solver {solver2['name']} no longer assigned to puzzle {puzzle1['name']}")
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
            self.logger.log_operation(f"Making POST request to /solvers/{solver_id}/puzz with puzzle_id {puzzle_id}")
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}/puzz",
                json={"puzz": puzzle_id}
            )
            
            self.logger.log_operation(f"Response status code: {response.status_code}")
            self.logger.log_operation(f"Response body: {response.text}")
            
            if response.status_code != 200:
                self.logger.log_error(f"Failed to update solver puzzle. Status code: {response.status_code}")
                return False
                
            response_data = response.json()
            if response_data.get('status') != 'ok':
                self.logger.log_error(f"Failed to update solver puzzle. Response: {response_data}")
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
            self.logger.log_operation(f"Selected round for testing: {test_round['name']}")
            
            # Test comments update
            new_comments = f"Test comments for round {test_round['name']}"
            self.logger.log_operation(f"Updating comments to '{new_comments}'")
            
            # Update round comments
            updated_round = self.update_round(test_round['id'], {'comments': new_comments})
            if not updated_round:
                result.fail(f"Failed to update comments for round {test_round['name']}")
                return
                
            # Verify comments update
            if updated_round.get('comments') != new_comments:
                result.fail(f"Comments not updated for round {test_round['name']}")
                return
                
            self.logger.log_operation(f"Successfully updated comments for round {test_round['name']}")
            
            result.set_success("Round modification test completed successfully")
            
        except Exception as e:
            result.fail(f"Error in round modification test: {str(e)}")
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
                self.logger.log_operation(f"Testing sheetcount for puzzle {puzzle['name']}")
                
                # Get initial puzzle details
                puzzle_details = self.get_puzzle_details(puzzle['id'])
                if not puzzle_details:
                    result.fail(f"Failed to get details for puzzle {puzzle['name']}")
                    return
                    
                initial_sheetcount = puzzle_details.get('sheetcount')
                self.logger.log_operation(f"Initial sheetcount: {initial_sheetcount}")
                
                # Set sheetcount to a specific value
                test_sheetcount = random.randint(2, 10)
                self.logger.log_operation(f"Setting sheetcount to {test_sheetcount}")
                
                if not self.update_puzzle(puzzle['id'], 'sheetcount', test_sheetcount):
                    result.fail(f"Failed to set sheetcount for puzzle {puzzle['name']}")
                    return
                    
                # Verify sheetcount was set
                puzzle_details = self.get_puzzle_details(puzzle['id'])
                if not puzzle_details:
                    result.fail(f"Failed to get puzzle details after setting sheetcount")
                    return
                    
                if puzzle_details.get('sheetcount') != test_sheetcount:
                    result.fail(f"Sheetcount not set correctly for puzzle {puzzle['name']}. Expected: {test_sheetcount}, Got: {puzzle_details.get('sheetcount')}")
                    return
                    
                self.logger.log_operation(f"Successfully set sheetcount to {test_sheetcount}")
                
                # Update sheetcount to a different value
                new_sheetcount = test_sheetcount + random.randint(1, 5)
                self.logger.log_operation(f"Updating sheetcount to {new_sheetcount}")
                
                if not self.update_puzzle(puzzle['id'], 'sheetcount', new_sheetcount):
                    result.fail(f"Failed to update sheetcount for puzzle {puzzle['name']}")
                    return
                    
                # Verify sheetcount was updated
                puzzle_details = self.get_puzzle_details(puzzle['id'])
                if not puzzle_details:
                    result.fail(f"Failed to get puzzle details after updating sheetcount")
                    return
                    
                if puzzle_details.get('sheetcount') != new_sheetcount:
                    result.fail(f"Sheetcount not updated correctly for puzzle {puzzle['name']}. Expected: {new_sheetcount}, Got: {puzzle_details.get('sheetcount')}")
                    return
                    
                self.logger.log_operation(f"Successfully updated sheetcount to {new_sheetcount}")
                
                # Verify sheetcount is included in /all endpoint
                response = requests.get(f"{self.base_url}/all")
                if not response.ok:
                    result.fail(f"Failed to get /all endpoint")
                    return
                    
                all_data = response.json()
                found_puzzle = None
                for round_data in all_data.get('rounds', []):
                    for p in round_data.get('puzzles', []):
                        if p.get('id') == puzzle['id']:
                            found_puzzle = p
                            break
                    if found_puzzle:
                        break
                        
                if not found_puzzle:
                    result.fail(f"Puzzle {puzzle['name']} not found in /all endpoint")
                    return
                    
                if found_puzzle.get('sheetcount') != new_sheetcount:
                    result.fail(f"Sheetcount not correct in /all endpoint for puzzle {puzzle['name']}. Expected: {new_sheetcount}, Got: {found_puzzle.get('sheetcount')}")
                    return
                    
                self.logger.log_operation(f"Sheetcount correctly included in /all endpoint")
                
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
            existing_tags = {t['name'] for t in response.json().get('tags', [])}
        
        # Generate unique tag name with TEST prefix
        while True:
            timestamp = str(int(time.time() * 1000))  # milliseconds for more uniqueness
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
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
            
            self.logger.log_operation(f"Generated unique test tags: {tag1_name}, {tag2_name}, {tag3_name}")
            
            # ============================================
            # Test 1: Create a new tag unassociated with a puzzle
            # ============================================
            self.logger.log_operation(f"Test 1: Creating tag '{tag1_name}' via POST /tags")
            response = requests.post(
                f"{self.base_url}/tags",
                json={"name": tag1_name}
            )
            if not response.ok:
                result.fail(f"Failed to create tag: {response.text}")
                return
            tag1_data = response.json()
            if tag1_data.get('status') != 'ok':
                result.fail(f"Unexpected response creating tag: {tag1_data}")
                return
            tag1_id = tag1_data['tag']['id']
            self.logger.log_operation(f"Created tag '{tag1_name}' with id {tag1_id}")
            
            # ============================================
            # Test 2: Pull that tag from the tags endpoint
            # ============================================
            self.logger.log_operation(f"Test 2: Fetching tag '{tag1_name}' via GET /tags/{tag1_name}")
            response = requests.get(f"{self.base_url}/tags/{tag1_name}")
            if not response.ok:
                result.fail(f"Failed to get tag: {response.text}")
                return
            fetched_tag = response.json()
            if fetched_tag.get('status') != 'ok':
                result.fail(f"Unexpected response fetching tag: {fetched_tag}")
                return
            if fetched_tag['tag']['name'] != tag1_name:
                result.fail(f"Tag name mismatch. Expected: {tag1_name}, Got: {fetched_tag['tag']['name']}")
                return
            if fetched_tag['tag']['id'] != tag1_id:
                result.fail(f"Tag id mismatch. Expected: {tag1_id}, Got: {fetched_tag['tag']['id']}")
                return
            self.logger.log_operation(f"Successfully fetched tag '{tag1_name}'")
            
            # Verify tag appears in GET /tags list
            self.logger.log_operation("Verifying tag appears in GET /tags list")
            response = requests.get(f"{self.base_url}/tags")
            if not response.ok:
                result.fail(f"Failed to get tags list: {response.text}")
                return
            tags_list = response.json().get('tags', [])
            tag_names = [t['name'] for t in tags_list]
            if tag1_name not in tag_names:
                result.fail(f"Tag '{tag1_name}' not found in tags list")
                return
            self.logger.log_operation(f"Tag '{tag1_name}' found in tags list")
            
            # ============================================
            # Test 3: Create a tag with inappropriate characters (should fail)
            # ============================================
            self.logger.log_operation(f"Test 3: Attempting to create invalid tag '{invalid_tag_name}' (should fail)")
            response = requests.post(
                f"{self.base_url}/tags",
                json={"name": invalid_tag_name}
            )
            if response.ok and response.json().get('status') == 'ok':
                result.fail(f"Tag with spaces should have been rejected but was accepted")
                return
            self.logger.log_operation(f"Invalid tag correctly rejected")
            
            # ============================================
            # Test 4: Create a new tag by associating it with a puzzle (auto-create)
            # ============================================
            # First, we need a puzzle to work with
            puzzles = self.get_all_puzzles()
            if not puzzles:
                # Create a round and puzzle for testing
                self.logger.log_operation("No puzzles found, creating test round and puzzle")
                test_round = self.create_round(f"TagTestRound{timestamp}")
                test_puzzle = self.create_puzzle(f"TagTestPuzzle{timestamp}", str(test_round['id']))
                puzzle_id = test_puzzle['id']
            else:
                puzzle_id = puzzles[0]['id']
            
            self.logger.log_operation(f"Test 4: Creating tag '{tag2_name}' by adding to puzzle {puzzle_id}")
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"add": tag2_name}}
            )
            if not response.ok:
                result.fail(f"Failed to add tag to puzzle: {response.text}")
                return
            self.logger.log_operation(f"Tag '{tag2_name}' auto-created and added to puzzle")
            
            # Verify tag was created in system
            response = requests.get(f"{self.base_url}/tags/{tag2_name}")
            if not response.ok:
                result.fail(f"Auto-created tag '{tag2_name}' not found in system")
                return
            tag2_id = response.json()['tag']['id']
            self.logger.log_operation(f"Verified tag '{tag2_name}' exists with id {tag2_id}")
            
            # ============================================
            # Test 5: Associate an existing tag to a puzzle by id
            # ============================================
            self.logger.log_operation(f"Test 5: Adding existing tag id {tag1_id} to puzzle {puzzle_id}")
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"add_id": tag1_id}}
            )
            if not response.ok:
                result.fail(f"Failed to add tag by id: {response.text}")
                return
            self.logger.log_operation(f"Tag id {tag1_id} added to puzzle")
            
            # ============================================
            # Test 6: Associate a tag by id that doesn't exist (should fail)
            # ============================================
            nonexistent_id = 999999
            self.logger.log_operation(f"Test 6: Attempting to add non-existent tag id {nonexistent_id} (should fail)")
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"add_id": nonexistent_id}}
            )
            if response.ok and response.json().get('status') == 'ok':
                result.fail(f"Adding non-existent tag id should have failed")
                return
            self.logger.log_operation(f"Non-existent tag id correctly rejected")
            
            # ============================================
            # Test 7: Make sure a puzzle having multiple tags works
            # ============================================
            self.logger.log_operation(f"Test 7: Verifying puzzle {puzzle_id} has multiple tags")
            puzzle_details = self.get_puzzle_details(puzzle_id)
            if not puzzle_details:
                result.fail(f"Failed to get puzzle details")
                return
            puzzle_tags = puzzle_details.get('tags', '')
            if not puzzle_tags:
                result.fail(f"Puzzle has no tags")
                return
            tag_list = [t.strip() for t in puzzle_tags.split(',')]
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
            self.logger.log_operation(f"Test 8: Getting tags via GET /puzzles/{puzzle_id}/tags")
            response = requests.get(f"{self.base_url}/puzzles/{puzzle_id}/tags")
            if not response.ok:
                result.fail(f"Failed to get puzzle tags: {response.text}")
                return
            puzzle_tags_response = response.json()
            if puzzle_tags_response.get('status') != 'ok':
                result.fail(f"Unexpected response getting puzzle tags: {puzzle_tags_response}")
                return
            tags_value = puzzle_tags_response.get('puzzle', {}).get('tags', '')
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
            if search_results.get('status') != 'ok':
                result.fail(f"Unexpected response searching by tag_id: {search_results}")
                return
            found_puzzles = search_results.get('puzzles', [])
            found_ids = [p['id'] for p in found_puzzles]
            if puzzle_id not in found_ids:
                result.fail(f"Puzzle {puzzle_id} not found in search results for tag_id {tag1_id}")
                return
            self.logger.log_operation(f"Search by tag_id returned {len(found_puzzles)} puzzle(s)")
            
            # ============================================
            # Test 10: Search by tag name
            # ============================================
            self.logger.log_operation(f"Test 10: Searching puzzles by tag name '{tag2_name}'")
            response = requests.get(f"{self.base_url}/search?tag={tag2_name}")
            if not response.ok:
                result.fail(f"Failed to search by tag name: {response.text}")
                return
            search_results = response.json()
            if search_results.get('status') != 'ok':
                result.fail(f"Unexpected response searching by tag name: {search_results}")
                return
            found_puzzles = search_results.get('puzzles', [])
            found_ids = [p['id'] for p in found_puzzles]
            if puzzle_id not in found_ids:
                result.fail(f"Puzzle {puzzle_id} not found in search results for tag '{tag2_name}'")
                return
            self.logger.log_operation(f"Search by tag name returned {len(found_puzzles)} puzzle(s)")
            
            # ============================================
            # Bonus: Test remove_id functionality
            # ============================================
            self.logger.log_operation(f"Bonus: Testing remove_id - removing tag id {tag1_id} from puzzle")
            response = requests.post(
                f"{self.base_url}/puzzles/{puzzle_id}/tags",
                json={"tags": {"remove_id": tag1_id}}
            )
            if not response.ok:
                result.fail(f"Failed to remove tag by id: {response.text}")
                return
            
            # Verify removal
            puzzle_details = self.get_puzzle_details(puzzle_id)
            puzzle_tags = puzzle_details.get('tags', '')
            tag_list = [t.strip() for t in puzzle_tags.split(',')] if puzzle_tags else []
            if tag1_name in tag_list:
                result.fail(f"Tag '{tag1_name}' should have been removed from puzzle")
                return
            self.logger.log_operation(f"Tag removed successfully, remaining tags: {tag_list}")
            
            # ============================================
            # Bonus: Test lowercase normalization
            # ============================================
            uppercase_tag = self.generate_unique_test_tag_name().upper()  # e.g., "TEST-1234567890-ABC123"
            self.logger.log_operation(f"Bonus: Testing lowercase normalization with '{uppercase_tag}'")
            response = requests.post(
                f"{self.base_url}/tags",
                json={"name": uppercase_tag}
            )
            if not response.ok:
                result.fail(f"Failed to create uppercase tag: {response.text}")
                return
            created_tag = response.json()['tag']
            if created_tag['name'] != uppercase_tag.lower():
                result.fail(f"Tag should be lowercase. Expected: {uppercase_tag.lower()}, Got: {created_tag['name']}")
                return
            self.logger.log_operation(f"Uppercase tag correctly normalized to '{created_tag['name']}'")
            
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
            if not isinstance(all_data, dict) or 'rounds' not in all_data:
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
            if not isinstance(puzzles_data, dict) or 'puzzles' not in puzzles_data:
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
            if not isinstance(solvers_data, dict) or 'solvers' not in solvers_data:
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
            if not isinstance(rounds_data, dict) or 'rounds' not in rounds_data:
                result.fail("Invalid response format from /rounds endpoint")
                return
            self.logger.log_operation("Successfully tested /rounds endpoint")
            
            result.set_success("API endpoints test completed successfully")
            
        except Exception as e:
            result.fail(f"Error in API endpoints test: {str(e)}")
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
        
        if rounds or puzzles:
            self.logger.log_error("System is not empty!")
            self.logger.log_error(f"Found {len(rounds)} rounds and {len(puzzles)} puzzles")
            self.logger.log_error("Please run reset_hunt.py to reset the system before running tests")
            print("\n" + "=" * 80)
            print("ERROR: System is not empty!")
            print(f"Found {len(rounds)} rounds and {len(puzzles)} puzzles")
            print("Please run reset_hunt.py to reset the system before running tests")
            print("=" * 80 + "\n")
            sys.exit(1)
            
        self.logger.log_operation("System is empty, proceeding with tests")
        
        tests = [
            ("Solver Listing", self.test_solver_listing),
            ("Puzzle Creation", self.test_puzzle_creation),
            ("Puzzle Modification", self.test_puzzle_modification),
            ("Round Modification", self.test_round_modification),
            ("Meta Puzzles and Round Completion", self.test_meta_puzzles_and_round_completion),
            ("Answer Verification", self.test_answer_verification),
            ("Solver Assignments", self.test_solver_assignments),
            ("Solver Reassignment", self.test_solver_reassignment),
            ("Activity Tracking", self.test_activity_tracking),
            ("Solver History", self.test_solver_history),
            ("Sheetcount", self.test_sheetcount),
            ("Tagging", self.test_tagging),
            ("API Endpoints", self.test_api_endpoints)
        ]
        
        for name, test in tests:
            result = self.run_test(name, test)
            
        self.print_results()

if __name__ == "__main__":
    runner = TestRunner()
    runner.run_all_tests() 