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
                    "puzzle_uri": "http://example.com/puzzle",
                    "ismeta": False
                }
            }
            
            self.logger.log_operation(f"Request data: {json.dumps(request_data)}")
            
            response = requests.post(
                f"{BASE_URL}/puzzles",
                json=request_data
            )
            
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
                
            # Find the puzzle we just created
            puzzle_data = None
            for puzzle in puzzles_data["puzzles"]:
                if puzzle["name"] == name:
                    puzzle_data = puzzle
                    break
                    
            if not puzzle_data:
                self.logger.log_error(f"Could not find newly created puzzle {name} in puzzles list")
                self.logger.log_error(f"Available puzzles: {[p['name'] for p in puzzles_data['puzzles']]}")
                raise Exception(f"Could not find newly created puzzle {name} in puzzles list")
                
            # Get full puzzle details
            puzzle_details = self.get_puzzle_details(puzzle_data["id"])
            if not puzzle_details:
                self.logger.log_error(f"Failed to get details for puzzle {name}")
                raise Exception(f"Failed to get details for puzzle {name}")
                
            self.logger.log_operation(f"Created puzzle {name} with id {puzzle_data['id']}")
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
        self.logger.log_operation(f"Updating puzzle {puzzle_id}: {field} = {value}")
        response = requests.post(
            f"{BASE_URL}/puzzles/{puzzle_id}/{field}",
            json={field: value}
        )
        if not response.ok:
            raise Exception(f"Failed to update puzzle {puzzle_id} {field}: {response.text}")
        self.logger.log_operation(f"Successfully updated puzzle {puzzle_id}")
        return True

    def assign_solver_to_puzzle(self, solver_id: str, puzzle_id: str) -> bool:
        """Assign a solver to a puzzle."""
        try:
            self.logger.log_operation(f"Assigning solver {solver_id} to puzzle {puzzle_id}")
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}/puzz",
                json={"puzz": puzzle_id}
            )
            
            # Log the complete response for debugging
            self.logger.log_operation(f"Response status: {response.status_code}")
            self.logger.log_operation(f"Response body: {response.text}")
            
            if not response.ok:
                self.logger.log_error(f"Failed to assign solver. Status: {response.status_code}")
                self.logger.log_error(f"Response: {response.text}")
                return False
                
            response_data = response.json()
            if not isinstance(response_data, dict):
                self.logger.log_error(f"Unexpected response format: {response_data}")
                return False
                
            if 'status' not in response_data:
                self.logger.log_error(f"Response missing 'status' field: {response_data}")
                return False
                
            if response_data['status'] != 'ok':
                self.logger.log_error(f"Response status not 'ok': {response_data}")
                return False
                
            self.logger.log_operation("Successfully assigned solver")
            return True
            
        except Exception as e:
            self.logger.log_error(f"Exception in assign_solver_to_puzzle: {str(e)}")
            self.logger.log_error(f"Traceback: {traceback.format_exc()}")
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
        
        # Log details of each solver
        for solver in solvers:
            self.logger.log_operation(f"Solver found: {solver['name']} (ID: {solver['id']})")
        
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
                    puzzle_name = f"Test Puzzle R{round_idx+1}P{puzzle_idx+1} {int(time.time())}"
                    puzzle_data = self.create_puzzle(puzzle_name, str(round_data['id']))
                    if not puzzle_data:
                        result.fail(f"Failed to create puzzle {puzzle_name}")
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
            
        # For each selected puzzle, test modifications
        for puzzle in selected_puzzles:
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
                
        result.set_success("Puzzle modification test completed successfully")

    def test_solver_assignments(self, result: TestResult):
        """Test solver assignment functionality."""
        self.logger.log_operation("Starting solver assignments test")
        
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
        
        # For each round, select up to 3 random puzzles
        selected_puzzles = []
        history_puzzles = []
        for round_id, round_puzzles in puzzles_by_round.items():
            num_to_select = min(3, len(round_puzzles))
            if num_to_select > 0:
                selected = random.sample(round_puzzles, num_to_select)
                selected_puzzles.extend(selected[:2])  # First 2 for assignment testing
                if num_to_select > 2:
                    history_puzzles.extend(selected[2:])  # Third for history testing
                
        if not selected_puzzles:
            result.fail("No puzzles available for testing")
            return
            
        self.logger.log_operation(f"Selected {len(selected_puzzles)} puzzles for assignment testing")
        if history_puzzles:
            self.logger.log_operation(f"Selected {len(history_puzzles)} puzzles for history testing")
            
        # For each selected puzzle, assign 2 random solvers
        for puzzle in selected_puzzles:
            self.logger.log_operation(f"Testing assignments for puzzle {puzzle['name']}")
            
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
                    
                # Verify assignment
                solver_details = self.get_solver_details(solver['id'])
                if not solver_details:
                    result.fail(f"Failed to get solver details for {solver['name']}")
                    continue
                    
                if solver_details.get('puzz') != puzzle['name']:
                    result.fail(f"Solver {solver['name']} not properly assigned to puzzle {puzzle['name']}")
                    continue
                    
                # Test history operations with a different puzzle
                if history_puzzles:
                    history_puzzle = random.choice(history_puzzles)
                    if history_puzzle['id'] != puzzle['id']:  # Ensure it's a different puzzle
                        self.logger.log_operation(f"Testing history operations with puzzle {history_puzzle['name']}")
                        
                        # Add to history
                        if not self.add_solver_to_history(history_puzzle['id'], solver['id']):
                            result.fail(f"Failed to add solver {solver['name']} to history for puzzle {history_puzzle['name']}")
                            continue
                            
                        # Verify history addition
                        puzzle_details = self.get_puzzle_details(history_puzzle['id'])
                        if not puzzle_details:
                            result.fail(f"Failed to get puzzle details for {history_puzzle['name']}")
                            continue
                            
                        if solver['name'] not in puzzle_details.get('solvers', ''):
                            result.fail(f"Solver {solver['name']} not found in history for puzzle {history_puzzle['name']}")
                            continue
                            
                        # Remove from history
                        if not self.remove_solver_from_history(history_puzzle['id'], solver['id']):
                            result.fail(f"Failed to remove solver {solver['name']} from history for puzzle {history_puzzle['name']}")
                            continue
                            
                        # Verify history removal
                        puzzle_details = self.get_puzzle_details(history_puzzle['id'])
                        if not puzzle_details:
                            result.fail(f"Failed to get puzzle details for {history_puzzle['name']}")
                            continue
                            
                        solvers_history = puzzle_details.get('solvers', '') or ''
                        if solver['name'] in solvers_history:
                            result.fail(f"Solver {solver['name']} still found in history for puzzle {history_puzzle['name']}")
                            continue
                            
        result.set_success("Solver assignments test completed successfully")

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

    def test_meta_puzzles_and_round_completion(self, result: TestResult):
        """Test meta puzzle functionality and round completion logic."""
        self.logger.log_operation("Starting meta puzzle and round completion test")
        
        try:
            # Get all rounds
            rounds = self.get_all_rounds()
            if not rounds:
                result.fail("No rounds found to test meta puzzles")
                return
                
            # Select a round for testing
            round_data = random.choice(rounds)
            self.logger.log_operation(f"Selected round {round_data['name']} for testing")
            
            # Get puzzles in this round by fetching full puzzle details
            self.logger.log_operation("Fetching puzzles with full details")
            round_puzzles = []
            for puzzle in self.get_all_puzzles():
                try:
                    puzzle_details = self.get_puzzle_details(puzzle['id'])
                    if str(puzzle_details['round_id']) == str(round_data['id']):
                        round_puzzles.append(puzzle_details)
                except Exception as e:
                    self.logger.log_error(f"Error fetching details for puzzle {puzzle['id']}: {str(e)}")
                    continue
                    
            if len(round_puzzles) < 3:
                result.fail(f"Round {round_data['name']} has fewer than 3 puzzles, cannot test meta functionality")
                return
                
            self.logger.log_operation(f"Found {len(round_puzzles)} puzzles in round {round_data['name']}")
            
            # Select 2 random puzzles as meta (or 1 if only 3 puzzles)
            num_metas = min(2, len(round_puzzles) - 1)
            meta_puzzles = random.sample(round_puzzles, num_metas)
            self.logger.log_operation(f"Setting {num_metas} puzzles as meta: {', '.join(p['name'] for p in meta_puzzles)}")
            
            # Set meta status and verify
            for meta_puzzle in meta_puzzles:
                self.logger.log_operation(f"\nSetting puzzle {meta_puzzle['name']} as meta")
                
                # Set ismeta=true on the puzzle
                if not self.update_puzzle(meta_puzzle["id"], "ismeta", True):
                    result.fail(f"Failed to set ismeta=true for puzzle {meta_puzzle['id']}")
                    return
                    
                # Set meta_id in the round
                if not self.update_round(round_data['id'], {"meta_id": meta_puzzle["id"]}):
                    result.fail(f"Failed to set meta_id={meta_puzzle['id']} for round {round_data['id']}")
                    return
                
                # Verify meta status in puzzle table
                updated_puzzle = self.get_puzzle_details(meta_puzzle["id"])
                if not updated_puzzle.get("ismeta", False):
                    result.fail(f"Puzzle {meta_puzzle['id']} ismeta field not set to true")
                    return
                    
                # Verify meta status in round table
                updated_round = self.get_round(round_data['id'])
                if str(updated_round.get("meta_id")) != str(meta_puzzle["id"]):
                    result.fail(f"Round {round_data['id']} meta_id not set to {meta_puzzle['id']}")
                    return
                    
                self.logger.log_operation(f"Meta status verified for puzzle {meta_puzzle['name']}")
            
            # Set some non-meta puzzles to solved (but not all)
            non_meta_puzzles = [p for p in round_puzzles if p not in meta_puzzles]
            if non_meta_puzzles:
                # Leave at least one non-meta puzzle unsolved
                puzzles_to_solve = non_meta_puzzles[:-1]
                self.logger.log_operation(f"\nSetting non-meta puzzles to solved: {', '.join(p['name'] for p in puzzles_to_solve)}")
                for puzzle in puzzles_to_solve:
                    self.logger.log_operation(f"Setting puzzle {puzzle['name']} to solved")
                    self.update_puzzle(puzzle["id"], "status", "Solved")
                    
                    # Verify solve status
                    updated_puzzle = self.get_puzzle_details(puzzle["id"])
                    if updated_puzzle["status"] != "Solved":
                        result.fail(f"Failed to set puzzle {puzzle['id']} to solved")
                        return
                    self.logger.log_operation(f"Solve status verified for puzzle {puzzle['name']}")
            
            # Verify round is not complete yet (metas still unsolved)
            self.logger.log_operation("\nVerifying round is not complete (metas unsolved)")
            round_details = self.get_round(round_data['id'])
            if round_details.get("status") == "Solved":
                result.fail(f"Round {round_data['id']} marked as complete before metas solved")
                return
            self.logger.log_operation("Round correctly marked as incomplete")
            
            # Solve all but one meta puzzle
            for i, meta_puzzle in enumerate(meta_puzzles[:-1]):
                self.logger.log_operation(f"\nSetting meta puzzle {meta_puzzle['name']} to solved")
                self.update_puzzle(meta_puzzle["id"], "status", "Solved")
                
                # Verify solve status
                updated_puzzle = self.get_puzzle_details(meta_puzzle["id"])
                if updated_puzzle["status"] != "Solved":
                    result.fail(f"Failed to set meta puzzle {meta_puzzle['id']} to solved")
                    return
                self.logger.log_operation(f"Solve status verified for meta puzzle {meta_puzzle['name']}")
                
                # Verify round is still not complete
                round_details = self.get_round(round_data['id'])
                if round_details.get("status") == "Solved":
                    result.fail(f"Round {round_data['id']} marked as complete before all metas solved")
                    return
                self.logger.log_operation("Round correctly remains incomplete")
            
            # Solve the last meta puzzle
            last_meta = meta_puzzles[-1]
            self.logger.log_operation(f"\nSetting final meta puzzle {last_meta['name']} to solved")
            self.update_puzzle(last_meta["id"], "status", "Solved")
            
            # Verify solve status
            updated_puzzle = self.get_puzzle_details(last_meta["id"])
            if updated_puzzle["status"] != "Solved":
                result.fail(f"Failed to set final meta puzzle {last_meta['id']} to solved")
                return
            self.logger.log_operation(f"Solve status verified for final meta puzzle {last_meta['name']}")
            
            # Verify round is now complete
            self.logger.log_operation("Verifying round is now complete")
            round_details = self.get_round(round_data['id'])
            if round_details.get("status") != "Solved":
                result.fail(f"Round {round_data['id']} not marked as complete after all metas solved")
                return
            self.logger.log_operation("Round correctly marked as complete")
            
            result.set_success("Meta puzzle and round completion test completed successfully")
            
        except Exception as e:
            result.fail(f"Error in meta puzzle and round completion test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

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

    def test_solver_reassignment(self, result: TestResult):
        """Test reassigning solvers from one puzzle to another."""
        self.logger.log_operation("Starting solver reassignment test")
        
        try:
            # Get all puzzles and find ones with solvers
            self.logger.log_operation("Fetching puzzles with solvers")
            puzzles_with_solvers = []
            for puzzle in self.get_all_puzzles():
                try:
                    puzzle_details = self.get_puzzle_details(puzzle['id'])
                    if puzzle_details.get('cursolvers'):
                        puzzles_with_solvers.append(puzzle_details)
                except Exception as e:
                    self.logger.log_error(f"Error fetching details for puzzle {puzzle['id']}: {str(e)}")
                    continue
            
            if len(puzzles_with_solvers) < 2:
                result.fail("Need at least 2 puzzles with solvers to test reassignment")
                return
                
            # Select a subset of puzzles to test with
            num_to_test = min(3, len(puzzles_with_solvers))
            test_puzzles = random.sample(puzzles_with_solvers, num_to_test)
            self.logger.log_operation(f"Selected {num_to_test} puzzles for testing: {', '.join(p['name'] for p in test_puzzles)}")
            
            # For each puzzle, get its solvers and reassign them
            for i, puzzle in enumerate(test_puzzles):
                if not puzzle.get('cursolvers'):
                    continue
                    
                # Get the solvers for this puzzle
                solver_ids = [s.strip() for s in puzzle['cursolvers'].split(',') if s.strip()]
                if not solver_ids:
                    continue
                    
                # Select a different puzzle to reassign to
                target_puzzle = test_puzzles[(i + 1) % len(test_puzzles)]
                self.logger.log_operation(f"\nReassigning solvers from {puzzle['name']} to {target_puzzle['name']}")
                
                # Reassign each solver
                for solver_id in solver_ids:
                    self.logger.log_operation(f"Reassigning solver {solver_id}")
                    
                    # Update solver's puzz field to the new puzzle
                    if not self.update_solver_puzzle(solver_id, target_puzzle['id']):
                        result.fail(f"Failed to assign solver {solver_id} to puzzle {target_puzzle['id']}")
                        return
                        
                    # Verify the reassignment
                    old_puzzle_details = self.get_puzzle_details(puzzle['id'])
                    new_puzzle_details = self.get_puzzle_details(target_puzzle['id'])
                    solver_details = self.get_solver_details(solver_id)
                    
                    # Check that solver is no longer in old puzzle's cursolvers
                    if solver_id in old_puzzle_details.get('cursolvers', ''):
                        result.fail(f"Solver {solver_id} still assigned to original puzzle {puzzle['id']}")
                        return
                        
                    # Check that solver is now in new puzzle's cursolvers
                    if solver_id not in new_puzzle_details.get('cursolvers', ''):
                        result.fail(f"Solver {solver_id} not assigned to new puzzle {target_puzzle['id']}")
                        return
                        
                    # Check that solver's puzz field points to new puzzle
                    if solver_details.get('puzz') != target_puzzle['id']:
                        result.fail(f"Solver {solver_id}'s puzz field not updated to {target_puzzle['id']}")
                        return
                        
                    self.logger.log_operation(f"Successfully reassigned solver {solver_id}")
            
            result.set_success("Solver reassignment test completed successfully")
            
        except Exception as e:
            result.fail(f"Error in solver reassignment test: {str(e)}")
            self.logger.log_error(f"Exception type: {type(e).__name__}")
            self.logger.log_error(f"Exception message: {str(e)}")
            self.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def update_solver_puzzle(self, solver_id: str, puzzle_id: str) -> bool:
        """Update a solver's current puzzle assignment."""
        try:
            response = requests.post(
                f"{self.base_url}/solvers/{solver_id}/puzz",
                json={"puzz": puzzle_id}
            )
            return response.ok
        except Exception as e:
            self.logger.log_error(f"Error updating solver puzzle: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all tests and print results."""
        tests = [
            ("Solver Listing", self.test_solver_listing),
            ("Puzzle Creation", self.test_puzzle_creation),
            ("Puzzle Modification", self.test_puzzle_modification),
            ("Solver Assignments", self.test_solver_assignments),
            ("Activity Tracking", self.test_activity_tracking),
            ("Meta Puzzles and Round Completion", self.test_meta_puzzles_and_round_completion),
            ("Solver Reassignment", self.test_solver_reassignment),
            ("Answer Verification", self.test_answer_verification)
        ]
        
        for name, test in tests:
            self.run_test(name, test)
            
        self.print_results()

if __name__ == "__main__":
    runner = TestRunner()
    runner.run_all_tests() 