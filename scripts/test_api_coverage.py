#!/usr/bin/env python3

import requests
import random
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
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
            for round in rounds_data["rounds"]:
                if round["name"] == name:
                    round_data = round
                    break
                    
            if not round_data:
                self.logger.log_error(f"Could not find newly created round {name} in rounds list")
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
        """Create a new puzzle."""
        self.logger.log_operation(f"Creating puzzle: {name} in round {round_id}")
        
        # Print request details for debugging
        request_uri = f"{self.base_url}/puzzles"
        print(f"\nMaking POST request to: {request_uri}")
        
        puzzle_data = {
            "puzzle": {
                "name": name,
                "round_id": round_id,
                "puzzle_uri": "http://example.com/puzzle"
            }
        }
        print(f"Request JSON data: {json.dumps(puzzle_data, indent=2)}")
        
        try:
            response = requests.post(request_uri, json=puzzle_data)
            if not response.ok:
                print(f"Error response: {response.status_code} - {response.text}")
                return None
                
            response_data = response.json()
            if not response_data.get("status") == "ok":
                print(f"Error in response: {response_data}")
                return None
                
            return response_data.get("puzzle", {})
            
        except Exception as e:
            print(f"Exception creating puzzle: {str(e)}")
            return None

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

    def test_puzzle_creation(self, result: TestResult):
        """Test puzzle creation functionality."""
        self.logger.log_operation("Starting puzzle creation test")
        
        # Get all rounds
        rounds = self.get_all_rounds()
        if not rounds:
            result.fail("Failed to get rounds")
            return
            
        # Create a new round for testing
        round_name = f"TestRound_{random.randint(1000, 9999)}"
        self.logger.log_operation(f"Creating new round: {round_name}")
        new_round = self.create_round(round_name)
        if not new_round:
            result.fail(f"Failed to create round {round_name}")
            return
            
        # Create puzzles in the new round
        for i in range(1, 4):  # Create 3 puzzles
            puzzle_name = f"TestPuzzle_{i}_{random.randint(1000, 9999)}"
            self.logger.log_operation(f"Creating puzzle {puzzle_name} in round {round_name}")
            
            # Create puzzle
            new_puzzle = self.create_puzzle(puzzle_name, str(new_round['id']))
            if not new_puzzle:
                result.fail(f"Failed to create puzzle {puzzle_name}")
                continue
                
            # Verify puzzle details
            puzzle_details = self.get_puzzle_details(new_puzzle['id'])
            if not puzzle_details:
                result.fail(f"Failed to get details for puzzle {puzzle_name}")
                continue
                
            # Verify puzzle properties
            if puzzle_details['name'] != puzzle_name:
                result.fail(f"Puzzle name mismatch: expected {puzzle_name}, got {puzzle_details['name']}")
                continue
                
            if str(puzzle_details['round_id']) != str(new_round['id']):
                result.fail(f"Round ID mismatch: expected {new_round['id']}, got {puzzle_details['round_id']}")
                continue
                
            if puzzle_details['status'] != 'New':
                result.fail(f"Initial status should be 'New', got {puzzle_details['status']}")
                continue
                
        result.set_success("Puzzle creation test completed successfully")

    def test_puzzle_modification(self, result: TestResult):
        """Test puzzle modification functionality"""
        self.logger.log_operation("Testing puzzle modification")
        
        # Get all rounds and puzzles first
        try:
            response = requests.get(f"{self.base_url}/rounds")
            if not response.ok:
                result.fail("Failed to fetch rounds")
                return
            self.rounds = response.json()["rounds"]
            self.logger.log_operation(f"Found {len(self.rounds)} rounds")
            
            # Get puzzles with their full details
            self.puzzles = []
            response = requests.get(f"{self.base_url}/puzzles")
            if not response.ok:
                result.fail("Failed to fetch puzzles")
                return
            
            # For each puzzle, get its full details
            for puzzle in response.json()["puzzles"]:
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if puzzle_details:
                    self.puzzles.append(puzzle_details)
                else:
                    self.logger.log_warning(f"Could not get details for puzzle {puzzle['id']}")
            
            self.logger.log_operation(f"Found {len(self.puzzles)} puzzles with full details")
            
            # Debug: Print first puzzle's structure
            if self.puzzles:
                first_puzzle = self.puzzles[0]
                self.logger.log_operation(f"First puzzle structure: {first_puzzle}")
                self.logger.log_operation(f"First puzzle round_id: {first_puzzle.get('round_id')}")
                self.logger.log_operation(f"First puzzle keys: {list(first_puzzle.keys())}")
            
            if not self.rounds or not self.puzzles:
                result.fail("No rounds or puzzles found for testing")
                return
            
        except Exception as e:
            result.fail(f"Error fetching test data: {str(e)}")
            return
        
        # Select 2 random puzzles from each round for testing
        test_puzzles = []
        for round_data in self.rounds:
            round_puzzles = [p for p in self.puzzles if str(p["round_id"]) == str(round_data["id"])]
            if len(round_puzzles) < 2:
                self.logger.log_operation(f"Skipping round {round_data['name']} - not enough puzzles")
                continue
            selected_puzzles = random.sample(round_puzzles, 2)
            test_puzzles.extend(selected_puzzles)
            self.logger.log_operation(f"Selected puzzles from round {round_data['name']}: {', '.join(p['name'] for p in selected_puzzles)}")
        
        if not test_puzzles:
            result.fail("No puzzles available for testing")
            return
        
        # Test modifications on each puzzle
        for puzzle in test_puzzles:
            self.logger.log_operation(f"\nTesting modifications for puzzle {puzzle['name']}")
            
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
                result.fail(f"Status update verification failed for puzzle {puzzle['name']}")
                continue
            
            # Test solving the puzzle by setting answer
            answer = f"ANSWER_{puzzle['name']}"
            self.logger.log_operation(f"Solving puzzle with answer '{answer}'")
            if not self.update_puzzle(puzzle["id"], "answer", answer):
                result.fail(f"Failed to set answer for puzzle {puzzle['name']}")
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
                result.fail(f"Comments update verification failed for puzzle {puzzle['name']}")
                continue
            
            self.logger.log_operation(f"All modifications successful for puzzle {puzzle['name']}")
        
        result.set_success("All puzzle modifications completed successfully")

    def test_solver_assignments(self, result: TestResult):
        """Test solver assignment functionality."""
        self.logger.log_operation("Starting solver assignments test")
        
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
            round_id = str(puzzle.get('round_id', ''))  # Convert to string for consistent comparison
            if round_id:
                if round_id not in puzzles_by_round:
                    puzzles_by_round[round_id] = []
                puzzles_by_round[round_id].append(puzzle)
                
        self.logger.log_operation(f"Found {len(puzzles_by_round)} rounds with puzzles")
        for round_id, round_puzzles in puzzles_by_round.items():
            self.logger.log_operation(f"Round {round_id}: {len(round_puzzles)} puzzles")
                
        # For each round, select up to 3 random puzzles (2 for assignment, 1 for history)
        selected_puzzles = []
        history_puzzles = []
        for round_id, round_puzzles in puzzles_by_round.items():
            num_to_select = min(3, len(round_puzzles))
            if num_to_select > 0:
                selected = random.sample(round_puzzles, num_to_select)
                selected_puzzles.extend(selected[:2])  # First 2 for assignment
                if num_to_select > 2:
                    history_puzzles.extend(selected[2:])  # Remaining for history
                self.logger.log_operation(f"Selected {num_to_select} puzzles from round {round_id}")
                
        if not selected_puzzles:
            result.fail("No puzzles available for testing")
            return
            
        self.logger.log_operation(f"Selected {len(selected_puzzles)} puzzles for assignment testing")
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
                    
                # Verify assignment by checking solver details
                solver_details = self.get_solver_details(solver['id'])
                if not solver_details:
                    result.fail(f"Failed to get solver details for {solver['name']}")
                    continue
                    
                # Check if the solver's current puzzle matches what we just assigned
                if solver_details.get('puzz') != puzzle['name']:
                    result.fail(f"Solver {solver['name']} not assigned to puzzle {puzzle['name']}")
                    continue
                    
                # Test history operations with a different puzzle
                if history_puzzles:
                    history_puzzle = random.choice(history_puzzles)
                    self.logger.log_operation(f"Testing history operations with puzzle {history_puzzle['name']}")
                    
                    # Add to history
                    if not self.add_solver_to_history(history_puzzle['id'], solver['id']):
                        result.fail(f"Failed to add solver {solver['name']} to history for puzzle {history_puzzle['name']}")
                        continue
                        
                    # Verify history
                    puzzle_details = self.get_puzzle_details(history_puzzle['id'])
                    if not puzzle_details:
                        result.fail(f"Failed to get puzzle details for {history_puzzle['name']}")
                        continue
                        
                    history_solvers = puzzle_details.get('solvers', '').split(',') if puzzle_details.get('solvers') else []
                    if solver['name'] not in history_solvers:
                        result.fail(f"Solver {solver['name']} not found in history solvers list")
                        continue
                        
                    # Remove from history
                    if not self.remove_solver_from_history(history_puzzle['id'], solver['id']):
                        result.fail(f"Failed to remove solver {solver['name']} from history for puzzle {history_puzzle['name']}")
                        continue
                        
                    # Verify removal
                    puzzle_details = self.get_puzzle_details(history_puzzle['id'])
                    if not puzzle_details:
                        result.fail(f"Failed to get puzzle details for {history_puzzle['name']}")
                        continue
                        
                    history_solvers = puzzle_details.get('solvers', '').split(',') if puzzle_details.get('solvers') else []
                    if solver['name'] in history_solvers:
                        result.fail(f"Solver {solver['name']} still found in history solvers list after removal")
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
                    
                # Verify activity was recorded
                if 'lastact' not in puzzle_details:
                    result.fail(f"Puzzle {puzzle['name']} missing activity after solver assignment")
                    continue
                    
                last_activity = puzzle_details['lastact']
                if not last_activity:
                    result.fail(f"Puzzle {puzzle['name']} has empty activity record")
                    continue
                    
                # Verify activity has required fields
                required_fields = ['time', 'type', 'source']
                for field in required_fields:
                    if field not in last_activity:
                        result.fail(f"Activity record for puzzle {puzzle['name']} missing required field: {field}")
                        continue
                        
                # Verify activity type is valid
                valid_types = ['create', 'open', 'revise', 'comment', 'interact']
                if last_activity['type'] not in valid_types:
                    result.fail(f"Invalid activity type for puzzle {puzzle['name']}: {last_activity['type']}")
                    continue
                    
                # Verify activity source is valid
                valid_sources = ['google', 'pb_auto', 'pb_manual', 'bigjimmy', 'twiki', 'squid', 'apache', 'xmpp']
                if last_activity['source'] not in valid_sources:
                    result.fail(f"Invalid activity source for puzzle {puzzle['name']}: {last_activity['source']}")
                    continue
                    
        result.set_success("Activity tracking test completed successfully")

    def test_meta_puzzles_and_round_completion(self, result: TestResult):
        """Test meta puzzles and round completion logic"""
        self.logger.log_operation("Testing meta puzzles and round completion")
        
        # For each round, set multiple puzzles as meta and test completion
        for round_data in self.rounds:
            self.logger.log_operation(f"\nTesting round {round_data['name']}")
            
            # Get all puzzles in this round
            round_puzzles = [p for p in self.puzzles if p["round_id"] == round_data["id"]]
            if len(round_puzzles) < 3:  # Need at least 3 puzzles for meaningful test
                self.logger.log_operation(f"Skipping round {round_data['name']} - not enough puzzles")
                continue
                
            # Select 2 random puzzles as meta (or 1 if only 3 puzzles)
            num_metas = min(2, len(round_puzzles) - 1)
            meta_puzzles = random.sample(round_puzzles, num_metas)
            self.logger.log_operation(f"Setting {num_metas} puzzles as meta: {', '.join(p['name'] for p in meta_puzzles)}")
            
            # Set meta status and verify
            for meta_puzzle in meta_puzzles:
                self.logger.log_operation(f"\nSetting puzzle {meta_puzzle['name']} as meta")
                self.update_puzzle(meta_puzzle["id"], "ismeta", "true")
                
                # Verify meta status
                updated_puzzle = self.get_puzzle_details(meta_puzzle["id"])
                if not updated_puzzle.get("ismeta", False):
                    result.fail(f"Failed to set puzzle {meta_puzzle['id']} as meta")
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
            round_details = requests.get(f"{BASE_URL}/rounds/{round_data['id']}").json()["round"]
            if round_details.get("complete", False):
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
                self.logger.log_operation("Verifying round is still incomplete")
                round_details = requests.get(f"{BASE_URL}/rounds/{round_data['id']}").json()["round"]
                if round_details.get("complete", False):
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
            round_details = requests.get(f"{BASE_URL}/rounds/{round_data['id']}").json()["round"]
            if not round_details.get("complete", False):
                result.fail(f"Round {round_data['id']} not marked as complete after all metas solved")
                return
            self.logger.log_operation("Round correctly marked as complete")
        
        result.message = "Successfully tested meta puzzles and round completion logic"

    def test_answer_verification(self, result: TestResult):
        """Test answer verification functionality."""
        self.logger.log_operation("\n" + "="*50)
        self.logger.log_operation("Testing answer verification...")
        self.logger.log_operation("="*50)
        
        # Get a puzzle to test
        puzzles = self.get_all_puzzles()
        if not puzzles:
            self.logger.log_error("No puzzles found to test!")
            return
            
        test_puzzle = puzzles[0]
        self.logger.log_operation(f"\nTesting with puzzle: {test_puzzle['name']} (ID: {test_puzzle['id']})")
        self.logger.log_operation(f"DEBUG - Full puzzle details: {test_puzzle}")
        
        # Test incorrect answer
        self.logger.log_operation("\n" + "-"*50)
        self.logger.log_operation("Testing incorrect answer...")
        incorrect_result = self.update_puzzle(test_puzzle["id"], "answer", "WRONGANSWER")
        self.logger.log_operation(f"Result: {'Accepted' if incorrect_result else 'Rejected'}")
        if incorrect_result:
            self.logger.log_error("ERROR: Incorrect answer was accepted!")
            result.fail()
            return
            
        # Test correct answer
        self.logger.log_operation("\n" + "-"*50)
        self.logger.log_operation("Testing correct answer...")
        correct_answer = test_puzzle.get("answer", "CORRECTANSWER")
        self.logger.log_operation(f"DEBUG - Correct answer to test: {correct_answer}")
        self.logger.log_operation(f"DEBUG - Answer type: {type(correct_answer)}")
        self.logger.log_operation(f"DEBUG - Answer length: {len(correct_answer) if correct_answer else 0}")
        correct_result = self.update_puzzle(test_puzzle["id"], "answer", correct_answer)
        self.logger.log_operation(f"Result: {'Accepted' if correct_result else 'Rejected'}")
        if not correct_result:
            self.logger.log_error("ERROR: Correct answer was rejected!")
            self.logger.log_error(f"DEBUG - Puzzle answer: {test_puzzle.get('answer')}")
            self.logger.log_error(f"DEBUG - Tested answer: {correct_answer}")
            self.logger.log_error(f"DEBUG - Answer comparison: {test_puzzle.get('answer') == correct_answer}")
            result.fail()
            return
            
        self.logger.log_operation("\n" + "="*50)
        self.logger.log_operation("Answer verification test passed!")
        self.logger.log_operation("="*50)
        result.set_success("Answer verification test passed")

    def run_all_tests(self):
        """Run all tests in sequence."""
        self.logger.start_test("Full Test Suite")
        
        # Create initial test data first
        initial_result = TestResult("Initial Setup", self.logger)
        self.test_puzzle_creation(initial_result)
        if not initial_result.success:
            self.logger.log_error("Initial setup failed, aborting remaining tests")
            return
            
        # Now run the remaining tests
        tests = [
            ("Solver Listing", self.test_solver_listing),
            ("Puzzle Modification", self.test_puzzle_modification),
            ("Solver Assignments", self.test_solver_assignments),
            ("Activity Tracking", self.test_activity_tracking),
            ("Meta Puzzles and Round Completion", self.test_meta_puzzles_and_round_completion),
            ("Answer Verification", self.test_answer_verification)
        ]
        
        for name, test_func in tests:
            result = self.run_test(name, test_func)
            if not result.success:
                self.logger.log_error(f"Test {name} failed, aborting remaining tests")
                break
                
        self.print_results()

if __name__ == "__main__":
    runner = TestRunner()
    runner.run_all_tests() 