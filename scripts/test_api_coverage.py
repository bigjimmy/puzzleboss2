#!/usr/bin/env python3

import requests
import random
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
import sys
import traceback

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

    def __str__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"{status} {self.name}: {self.message} ({self.duration:.2f}s)"

class TestRunner:
    def __init__(self):
        self.logger = TestLogger()
        self.results = []
        self.solvers = []
        self.puzzles = []
        self.rounds = []
        
        # List of emojis to use in test data
        self.emojis = ["🎲", "🎯", "🎨", "🎪", "🎭", "🎫", "🎮", "🎰", "🎱", "🎲", 
                      "🎸", "🎹", "🎺", "🎻", "🎼", "🎵", "🎶", "🎷", "🎸", "🎹"]
        
        self.test_start_time = datetime.now()

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
        self.logger.log_operation(f"Fetching details for puzzle {puzzle_id}")
        response = requests.get(f"{BASE_URL}/puzzles/{puzzle_id}")
        if not response.ok:
            raise Exception(f"Failed to get puzzle {puzzle_id}: {response.text}")
        return response.json()["puzzle"]

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
        """Create a new puzzle"""
        response = requests.post(
            f"{BASE_URL}/puzzles",
            json={
                "name": name,
                "round_id": round_id,
                "puzzle_uri": "http://example.com"
            }
        )
        if not response.ok:
            self.logger.log_error(f"Failed to create puzzle {name}: {response.text}")
            raise Exception(f"Failed to create puzzle: {response.text}")
            
        response_data = response.json()
        if "status" not in response_data or response_data["status"] != "ok":
            self.logger.log_error(f"Unexpected response format creating puzzle {name}: {response_data}")
            raise Exception(f"Unexpected response format: {response_data}")
            
        if "puzzle" not in response_data:
            self.logger.log_error(f"Missing puzzle data in response for {name}: {response_data}")
            raise Exception(f"Missing puzzle data in response: {response_data}")
            
        puzzle_data = response_data["puzzle"]
        if "id" not in puzzle_data:
            self.logger.log_error(f"Missing id in puzzle data for {name}: {puzzle_data}")
            raise Exception(f"Missing id in puzzle data: {puzzle_data}")
            
        self.logger.log_operation(f"Created puzzle {name} with id {puzzle_data['id']}")
        return puzzle_data

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
        self.logger.log_operation(f"Assigning solver {solver_id} to puzzle {puzzle_id}")
        response = requests.post(
            f"{BASE_URL}/solvers/{solver_id}/puzz",
            json={"puzz": puzzle_id}
        )
        if not response.ok:
            raise Exception(f"Failed to assign solver {solver_id} to puzzle {puzzle_id}: {response.text}")
        self.logger.log_operation(f"Successfully assigned solver {solver_id} to puzzle {puzzle_id}")
        return True

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

    def update_round(self, round_id: str, field: str, value: str) -> bool:
        """Update a round field"""
        response = requests.post(
            f"{BASE_URL}/rounds/{round_id}/{field}",
            json={field: value}
        )
        return response.ok

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
        """Test creating puzzles with verification of all fields"""
        try:
            # Create 5 rounds with 5 puzzles each
            for r in range(1, 6):
                round_name = f"TestRound{r}"
                round_data = self.create_round(round_name)
                
                # Add round comments with optional emoji
                use_emoji = random.choice([True, False])
                round_comment = self.get_emoji_string(f"Test comment for {round_name}", use_emoji)
                self.update_round(round_data["id"], "comments", round_comment)
                
                # Verify round comments
                round_details = requests.get(f"{BASE_URL}/rounds/{round_data['id']}").json()
                if round_details["round"]["comments"] != round_comment:
                    result.fail(f"Round comments verification failed for {round_name}")
                    result.logger.log_error(f"Expected: {round_comment}")
                    result.logger.log_error(f"Actual: {round_details['round']['comments']}")
                    return
                
                for p in range(1, 6):
                    # Create puzzle with optional emoji in name
                    use_emoji = random.choice([True, False])
                    puzzle_name = self.get_emoji_string(f"R{r}Puzzle{p}", use_emoji)
                    puzzle_data = self.create_puzzle(puzzle_name, round_data["id"])
                    
                    # Verify puzzle was created with correct data
                    if puzzle_data["name"] != puzzle_name:
                        result.fail(f"Puzzle name verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: {puzzle_name}")
                        result.logger.log_error(f"Actual: {puzzle_data['name']}")
                        return
                        
                    if puzzle_data["round_id"] != round_data["id"]:
                        result.fail(f"Puzzle round_id verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: {round_data['id']}")
                        result.logger.log_error(f"Actual: {puzzle_data['round_id']}")
                        return
                        
                    # Verify puzzle details from API
                    puzzle_details = self.get_puzzle_details(puzzle_data["id"])
                    if puzzle_details["name"] != puzzle_name:
                        result.fail(f"Puzzle name API verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: {puzzle_name}")
                        result.logger.log_error(f"Actual: {puzzle_details['name']}")
                        return
                        
                    if puzzle_details["round_id"] != round_data["id"]:
                        result.fail(f"Puzzle round_id API verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: {round_data['id']}")
                        result.logger.log_error(f"Actual: {puzzle_details['round_id']}")
                        return
                        
                    if puzzle_details["status"] != "New":
                        result.fail(f"Puzzle status verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: New")
                        result.logger.log_error(f"Actual: {puzzle_details['status']}")
                        return
                        
                    if puzzle_details["answer"] != "":
                        result.fail(f"Puzzle answer verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: (empty string)")
                        result.logger.log_error(f"Actual: {puzzle_details['answer']}")
                        return
                        
                    if puzzle_details["comments"] != "":
                        result.fail(f"Puzzle comments verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: (empty string)")
                        result.logger.log_error(f"Actual: {puzzle_details['comments']}")
                        return
                        
                    if puzzle_details["ismeta"] != False:
                        result.fail(f"Puzzle ismeta verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: False")
                        result.logger.log_error(f"Actual: {puzzle_details['ismeta']}")
                        return
                        
                    if puzzle_details["solvers"] != "":
                        result.fail(f"Puzzle solvers verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: (empty string)")
                        result.logger.log_error(f"Actual: {puzzle_details['solvers']}")
                        return
                        
                    if puzzle_details["cursolvers"] != "":
                        result.fail(f"Puzzle cursolvers verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: (empty string)")
                        result.logger.log_error(f"Actual: {puzzle_details['cursolvers']}")
                        return
                        
                    if puzzle_details["xyzloc"] != "":
                        result.fail(f"Puzzle xyzloc verification failed for {puzzle_name}")
                        result.logger.log_error(f"Expected: (empty string)")
                        result.logger.log_error(f"Actual: {puzzle_details['xyzloc']}")
                        return
                        
                    result.logger.log_operation(f"Verified puzzle {puzzle_name} in round {round_name}")
            
            result.success("Successfully created and verified 5 rounds with 5 puzzles each, including round comments")
            
        except Exception as e:
            result.fail(f"Puzzle creation test failed: {str(e)}")
            result.logger.log_error(f"Exception type: {type(e).__name__}")
            result.logger.log_error(f"Exception traceback: {traceback.format_exc()}")

    def test_puzzle_modification(self, result: TestResult):
        """Test puzzle modification functionality"""
        self.logger.log_operation("Testing puzzle modification")
        
        # Select 2 random puzzles from each round for testing
        for round_data in self.rounds:
            round_puzzles = [p for p in self.puzzles if p["round_id"] == round_data["id"]]
            if len(round_puzzles) < 2:
                self.logger.log_operation(f"Skipping round {round_data['name']} - not enough puzzles")
                continue
                
            test_puzzles = random.sample(round_puzzles, 2)
            self.logger.log_operation(f"Selected {len(test_puzzles)} puzzles from round {round_data['name']}")
            
            for puzzle in test_puzzles:
                # Randomly decide if this update should have emoji
                use_emoji = random.choice([True, False])
                
                # Update status
                new_status = random.choice(["Being worked", "Needs eyes", "Solved"])
                self.logger.log_operation(f"Updating status of puzzle {puzzle['name']} to {new_status}")
                if not self.update_puzzle(puzzle["id"], "status", new_status):
                    result.fail(f"Failed to update status for puzzle {puzzle['id']}")
                    return
                
                # Verify status update
                updated_puzzle = self.get_puzzle_details(puzzle["id"])
                if updated_puzzle["status"] != new_status:
                    result.fail(f"Status update verification failed for puzzle {puzzle['id']}")
                    return
                
                # Update comments with emoji
                new_comment = self.get_emoji_string(f"Test comment for {puzzle['name']}", use_emoji)
                self.logger.log_operation(f"Updating comments for puzzle {puzzle['name']}")
                if not self.update_puzzle(puzzle["id"], "comments", new_comment):
                    result.fail(f"Failed to update comments for puzzle {puzzle['id']}")
                    return
                
                # Verify comments update
                updated_puzzle = self.get_puzzle_details(puzzle["id"])
                if updated_puzzle["comments"] != new_comment:
                    result.fail(f"Comments update verification failed for puzzle {puzzle['id']}")
                    return
                
                # If status is Solved, add an answer with emoji
                if new_status == "Solved":
                    answer = self.get_emoji_string(f"ANSWER_{puzzle['name']}", use_emoji)
                    self.logger.log_operation(f"Setting answer for puzzle {puzzle['name']}")
                    if not self.update_puzzle(puzzle["id"], "answer", answer):
                        result.fail(f"Failed to set answer for puzzle {puzzle['id']}")
                        return
                    
                    # Verify answer
                    updated_puzzle = self.get_puzzle_details(puzzle["id"])
                    if updated_puzzle["answer"] != answer:
                        result.fail(f"Answer verification failed for puzzle {puzzle['id']}")
                        return
        
        result.message = "Successfully tested puzzle modification with emoji support"

    def test_solver_assignments(self, result: TestResult):
        """Test solver assignment functionality"""
        self.logger.log_operation("Testing solver assignments")
        
        # Select 2 random puzzles from each round for testing
        test_puzzles = []
        for round_data in self.rounds:
            round_puzzles = [p for p in self.puzzles if p["round_id"] == round_data["id"]]
            if len(round_puzzles) < 2:
                self.logger.log_operation(f"Skipping round {round_data['name']} - not enough puzzles")
                continue
            test_puzzles.extend(random.sample(round_puzzles, 2))
        
        if not test_puzzles:
            result.fail("No puzzles available for testing")
            return
            
        # Select 10 random solvers for testing
        if len(self.solvers) < 10:
            result.fail("Not enough solvers available for testing")
            return
        test_solvers = random.sample(self.solvers, 10)
        
        self.logger.log_operation(f"Testing assignments with {len(test_solvers)} solvers and {len(test_puzzles)} puzzles")
        
        # Track which puzzles each solver has been assigned to
        solver_history = {solver["id"]: [] for solver in test_solvers}
        
        # Assign each solver to each puzzle in sequence
        for solver in test_solvers:
            self.logger.log_operation(f"Testing assignments for solver {solver['name']}")
            
            for puzzle in test_puzzles:
                # Assign solver to puzzle
                self.logger.log_operation(f"Assigning solver {solver['name']} to puzzle {puzzle['name']}")
                if not self.assign_solver_to_puzzle(solver["id"], puzzle["id"]):
                    result.fail(f"Failed to assign solver {solver['id']} to puzzle {puzzle['id']}")
                    return
                
                # Verify current assignment
                solver_details = self.get_solver_details(solver["id"])
                if solver_details["puzz"] != puzzle["id"]:
                    result.fail(f"Solver {solver['id']} not properly assigned to puzzle {puzzle['id']}")
                    return
                
                # Verify puzzle's current solvers
                puzzle_details = self.get_puzzle_details(puzzle["id"])
                if solver["id"] not in puzzle_details["cursolvers"].split(","):
                    result.fail(f"Solver {solver['id']} not in current solvers list for puzzle {puzzle['id']}")
                    return
                
                # Track this assignment in history
                solver_history[solver["id"]].append(puzzle["id"])
                
                # For all previous puzzles this solver was assigned to:
                for prev_puzzle_id in solver_history[solver["id"]][:-1]:
                    prev_puzzle = self.get_puzzle_details(prev_puzzle_id)
                    
                    # Verify solver is in history but not current solvers
                    if solver["id"] in prev_puzzle["cursolvers"].split(","):
                        result.fail(f"Solver {solver['id']} still in current solvers for previous puzzle {prev_puzzle_id}")
                        return
                    if solver["id"] not in prev_puzzle["solvers"].split(","):
                        result.fail(f"Solver {solver['id']} not in history for previous puzzle {prev_puzzle_id}")
                        return
        
        result.message = "Successfully tested solver assignments and history tracking with 10 solvers"

    def test_activity_tracking(self, result: TestResult):
        # Select 2 random puzzles from each round for testing
        test_puzzles = []
        for round_data in self.rounds:
            round_puzzles = [p for p in self.puzzles if p["round_id"] == round_data["id"]]
            test_puzzles.extend(random.sample(round_puzzles, min(2, len(round_puzzles))))
        
        self.logger.log_operation(f"Selected {len(test_puzzles)} puzzles for testing (2 from each round)")
        
        for i, puzzle in enumerate(test_puzzles, 1):
            self.logger.log_operation(f"Checking activity tracking for puzzle {i}/{len(test_puzzles)}: {puzzle['name']} (Round {puzzle['round_id']})")
            
            # Get initial activity
            initial_puzzle = self.get_puzzle_details(puzzle["id"])
            if "lastact" not in initial_puzzle:
                result.fail(f"Puzzle {puzzle['id']} missing initial activity tracking")
                return
            initial_activity = initial_puzzle["lastact"]
            self.logger.log_operation(f"Initial activity: {initial_activity}")
            
            # Make a change to trigger new activity
            self.logger.log_operation("Triggering new activity by updating status")
            new_status = "Being worked" if initial_puzzle["status"] != "Being worked" else "New"
            self.update_puzzle(puzzle["id"], "status", new_status)
            
            # Verify new activity was recorded
            self.logger.log_operation("Verifying new activity was recorded")
            updated_puzzle = self.get_puzzle_details(puzzle["id"])
            if "lastact" not in updated_puzzle:
                result.fail(f"Puzzle {puzzle['id']} missing updated activity tracking")
                return
                
            new_activity = updated_puzzle["lastact"]
            if new_activity == initial_activity:
                result.fail(f"Activity tracking not updated for puzzle {puzzle['id']}")
                return
                
            self.logger.log_operation(f"New activity recorded: {new_activity}")
        
        result.message = f"Activity tracking verified for {len(test_puzzles)} puzzles (2 from each round)"

    def test_meta_puzzles_and_round_completion(self, result: TestResult):
        """Test meta puzzles and round completion logic"""
        self.logger.log_operation("Testing meta puzzles and round completion")
        
        # For each round, set multiple puzzles as meta and test completion
        for round_data in self.rounds:
            self.logger.log_operation(f"Testing round {round_data['name']}")
            
            # Get all puzzles in this round
            round_puzzles = [p for p in self.puzzles if p["round_id"] == round_data["id"]]
            if len(round_puzzles) < 3:  # Need at least 3 puzzles for meaningful test
                self.logger.log_operation(f"Skipping round {round_data['name']} - not enough puzzles")
                continue
                
            # Select 2 random puzzles as meta (or 1 if only 3 puzzles)
            num_metas = min(2, len(round_puzzles) - 1)
            meta_puzzles = random.sample(round_puzzles, num_metas)
            self.logger.log_operation(f"Setting {num_metas} puzzles as meta")
            
            # Set meta status and verify
            for meta_puzzle in meta_puzzles:
                self.logger.log_operation(f"Setting puzzle {meta_puzzle['name']} as meta")
                self.update_puzzle(meta_puzzle["id"], "ismeta", "true")
                
                # Verify meta status
                updated_puzzle = self.get_puzzle_details(meta_puzzle["id"])
                if not updated_puzzle.get("ismeta", False):
                    result.fail(f"Failed to set puzzle {meta_puzzle['id']} as meta")
                    return
            self.logger.log_operation("All meta statuses verified")
            
            # Set some non-meta puzzles to solved (but not all)
            non_meta_puzzles = [p for p in round_puzzles if p not in meta_puzzles]
            if non_meta_puzzles:
                # Leave at least one non-meta puzzle unsolved
                puzzles_to_solve = non_meta_puzzles[:-1]
                for puzzle in puzzles_to_solve:
                    self.logger.log_operation(f"Setting puzzle {puzzle['name']} to solved")
                    self.update_puzzle(puzzle["id"], "status", "Solved")
                    
                    # Verify solve status
                    updated_puzzle = self.get_puzzle_details(puzzle["id"])
                    if updated_puzzle["status"] != "Solved":
                        result.fail(f"Failed to set puzzle {puzzle['id']} to solved")
                        return
            
            # Verify round is not complete yet (metas still unsolved)
            self.logger.log_operation("Verifying round is not complete (metas unsolved)")
            round_details = requests.get(f"{BASE_URL}/rounds/{round_data['id']}").json()["round"]
            if round_details.get("complete", False):
                result.fail(f"Round {round_data['id']} marked as complete before metas solved")
                return
            self.logger.log_operation("Round correctly marked as incomplete")
            
            # Solve all but one meta puzzle
            for i, meta_puzzle in enumerate(meta_puzzles[:-1]):
                self.logger.log_operation(f"Setting meta puzzle {meta_puzzle['name']} to solved")
                self.update_puzzle(meta_puzzle["id"], "status", "Solved")
                
                # Verify solve status
                updated_puzzle = self.get_puzzle_details(meta_puzzle["id"])
                if updated_puzzle["status"] != "Solved":
                    result.fail(f"Failed to set meta puzzle {meta_puzzle['id']} to solved")
                    return
                
                # Verify round is still not complete
                self.logger.log_operation("Verifying round is still incomplete")
                round_details = requests.get(f"{BASE_URL}/rounds/{round_data['id']}").json()["round"]
                if round_details.get("complete", False):
                    result.fail(f"Round {round_data['id']} marked as complete before all metas solved")
                    return
                self.logger.log_operation("Round correctly remains incomplete")
            
            # Solve the last meta puzzle
            last_meta = meta_puzzles[-1]
            self.logger.log_operation(f"Setting final meta puzzle {last_meta['name']} to solved")
            self.update_puzzle(last_meta["id"], "status", "Solved")
            
            # Verify last meta is solved
            updated_puzzle = self.get_puzzle_details(last_meta["id"])
            if updated_puzzle["status"] != "Solved":
                result.fail(f"Failed to set final meta puzzle {last_meta['id']} to solved")
                return
            
            # Verify round is now complete
            self.logger.log_operation("Verifying round is complete")
            round_details = requests.get(f"{BASE_URL}/rounds/{round_data['id']}").json()["round"]
            if not round_details.get("complete", False):
                result.fail(f"Round {round_data['id']} not marked as complete after all metas solved")
                return
            self.logger.log_operation("Round correctly marked as complete")
            
            # Reset meta status for next test
            self.logger.log_operation("Resetting meta statuses")
            for meta_puzzle in meta_puzzles:
                self.update_puzzle(meta_puzzle["id"], "ismeta", "false")
            
        result.message = "Successfully tested meta puzzles and round completion logic with multiple metas"

    def run_all_tests(self):
        """Run all tests and report results"""
        self.logger.log("Starting API test suite")
        
        # Get initial solver list
        self.solvers = self.get_all_solvers()
        self.logger.log(f"Found {len(self.solvers)} solvers in the system")
        
        # Run each test
        self.run_test("Solver Listing", self.test_solver_listing)
        self.run_test("Puzzle Creation", self.test_puzzle_creation)
        self.run_test("Puzzle Modification", self.test_puzzle_modification)
        self.run_test("Solver Assignments", self.test_solver_assignments)
        self.run_test("Activity Tracking", self.test_activity_tracking)
        self.run_test("Meta Puzzles and Round Completion", self.test_meta_puzzles_and_round_completion)
        
        # Print results
        self.print_results()

if __name__ == "__main__":
    runner = TestRunner()
    runner.run_all_tests() 