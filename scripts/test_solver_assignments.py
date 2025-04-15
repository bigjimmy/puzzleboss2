#!/usr/bin/env python3

import requests
import random
import time
from typing import List, Dict, Optional

BASE_URL = "http://localhost:5000"

def get_all_solvers() -> List[Dict]:
    """Get all solvers from the system."""
    print("\nDEBUG - Getting all solvers...")
    response = requests.get(f"{BASE_URL}/solvers")
    if not response.ok:
        raise Exception(f"Failed to get solvers: {response.text}")
    solvers = response.json()["solvers"]
    print("DEBUG - Retrieved solvers:")
    for solver in solvers:
        print(f"  Solver: {solver['name']} (ID: {solver['id']})")
    return solvers

def get_all_puzzles() -> List[Dict]:
    """Get all puzzles from the system."""
    print("\nDEBUG - Getting all puzzles...")
    response = requests.get(f"{BASE_URL}/puzzles")
    if not response.ok:
        raise Exception(f"Failed to get puzzles: {response.text}")
    puzzles = response.json()["puzzles"]
    print("DEBUG - Retrieved puzzles:")
    for puzzle in puzzles:
        print(f"  Puzzle: {puzzle['name']} (ID: {puzzle['id']})")
    return puzzles

def get_puzzle_details(puzzle_id: str) -> Dict:
    """Get detailed information about a specific puzzle."""
    response = requests.get(f"{BASE_URL}/puzzles/{puzzle_id}")
    if not response.ok:
        raise Exception(f"Failed to get puzzle {puzzle_id}: {response.text}")
    return response.json()["puzzle"]

def assign_solver_to_puzzle(puzzle_id: str, solver_id: str) -> bool:
    """Assign a solver to a puzzle."""
    print(f"DEBUG - Before API call:")
    print(f"  Puzzle ID: {puzzle_id}")
    print(f"  Solver ID: {solver_id}")
    
    response = requests.post(
        f"{BASE_URL}/solvers/{solver_id}/puzz",
        json={"puzz": puzzle_id}
    )
    
    print(f"DEBUG - After API call:")
    print(f"  Request URL: {BASE_URL}/solvers/{solver_id}/puzz")
    print(f"  Request Body: {{'puzz': {puzzle_id}}}")
    print(f"  Response Status: {response.status_code}")
    print(f"  Response Body: {response.text}")
    
    if not response.ok:
        print(f"Failed to assign solver {solver_id} to puzzle {puzzle_id}: {response.text}")
        return False
    return True

def get_puzzle_solver_history(puzzle_id: str) -> List[str]:
    """Get the solver history for a puzzle."""
    puzzle = get_puzzle_details(puzzle_id)
    return puzzle.get("solvers", "").split(",") if puzzle.get("solvers") else []

def verify_answer(puzzle_id: str, answer: str) -> bool:
    """Verify a puzzle answer."""
    response = requests.post(
        f"{BASE_URL}/puzzles/{puzzle_id}/answer",
        json={"answer": answer}
    )
    if not response.ok:
        print(f"Failed to verify answer for puzzle {puzzle_id}: {response.text}")
        return False
        
    result = response.json()
    if result.get("status") != "ok":
        print(f"Answer verification failed for puzzle {puzzle_id}:")
        print(f"  Expected status: 'ok'")
        print(f"  Actual status: '{result.get('status')}'")
        print(f"  Error message: {result.get('error', 'No error message')}")
        print(f"  Submitted answer: '{answer}'")
        return False
        
    return True

def test_answer_verification(self, result: TestResult):
    """Test puzzle answer verification functionality"""
    self.logger.log_operation("\nTesting answer verification...")
    
    # Get a puzzle to test with
    puzzles = self.get_all_puzzles()
    if not puzzles:
        result.fail("No puzzles found to test answer verification")
        return
        
    test_puzzle = puzzles[0]
    self.logger.log_operation(f"Using puzzle {test_puzzle['name']} (ID: {test_puzzle['id']}) for answer verification test")
    
    # Try incorrect answer
    incorrect_answer = "INCORRECT_ANSWER"
    self.logger.log_operation(f"Testing incorrect answer: '{incorrect_answer}'")
    if self.verify_answer(test_puzzle["id"], incorrect_answer):
        result.fail(f"Incorrect answer '{incorrect_answer}' was accepted for puzzle {test_puzzle['name']}")
        return
        
    # Try correct answer
    correct_answer = test_puzzle.get("answer", "CORRECT_ANSWER")
    self.logger.log_operation(f"Testing correct answer: '{correct_answer}'")
    if not self.verify_answer(test_puzzle["id"], correct_answer):
        result.fail(f"Correct answer '{correct_answer}' was rejected for puzzle {test_puzzle['name']}")
        return
        
    self.logger.log_operation("Answer verification test passed")
    result.pass_test()

def main():
    print("Starting solver assignment test...")
    
    # Get initial state
    solvers = get_all_solvers()
    puzzles = get_all_puzzles()
    
    if not solvers:
        print("No solvers found in the system!")
        return
        
    if not puzzles:
        print("No puzzles found in the system!")
        return
        
    print(f"Found {len(solvers)} solvers and {len(puzzles)} puzzles")
    
    # Track puzzle solver history counts
    puzzle_history_counts = {puzzle["id"]: 0 for puzzle in puzzles}
    
    # Main test loop
    while True:
        # Check if all puzzles have at least 10 solvers in history
        if all(count >= 10 for count in puzzle_history_counts.values()):
            print("\nAll puzzles have at least 10 solvers in their history!")
            break
            
        # Randomly assign each solver to a puzzle
        for solver in solvers:
            # Choose a random puzzle to assign to
            available_puzzles = [p for p in puzzles if puzzle_history_counts[p["id"]] < 10]
            if not available_puzzles:
                continue
                
            target_puzzle = random.choice(available_puzzles)
            
            # Print debug info before assignment
            print(f"\nDEBUG - Assignment attempt:")
            print(f"  Solver: {solver['name']} (ID: {solver['id']})")
            print(f"  Puzzle: {target_puzzle['name']} (ID: {target_puzzle['id']})")
            
            # Assign solver to the new puzzle - NOTE: parameters are in correct order here
            if assign_solver_to_puzzle(target_puzzle["id"], solver["id"]):
                # Update history count for the puzzle
                history = get_puzzle_solver_history(target_puzzle["id"])
                puzzle_history_counts[target_puzzle["id"]] = len(history)
                
                print(f"Assigned solver {solver['name']} to puzzle {target_puzzle['name']} "
                      f"(History count: {puzzle_history_counts[target_puzzle['id']]})")
                
                time.sleep(0.1)  # Small delay to prevent rate limiting
        
        # Print current status
        print("\nCurrent puzzle solver history counts:")
        for puzzle in puzzles:
            print(f"Puzzle {puzzle['name']}: {puzzle_history_counts[puzzle['id']]} solvers")
        print("\n" + "="*50 + "\n")
        
        # Wait before next round
        time.sleep(1)

if __name__ == "__main__":
    main() 