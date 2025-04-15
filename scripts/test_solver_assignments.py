#!/usr/bin/env python3

import requests
import random
import time
from typing import List, Dict, Optional

BASE_URL = "http://localhost:5000"

def get_all_solvers() -> List[Dict]:
    """Get all solvers from the system."""
    response = requests.get(f"{BASE_URL}/solvers")
    if not response.ok:
        raise Exception(f"Failed to get solvers: {response.text}")
    return response.json()["solvers"]

def get_all_puzzles() -> List[Dict]:
    """Get all puzzles from the system."""
    response = requests.get(f"{BASE_URL}/puzzles")
    if not response.ok:
        raise Exception(f"Failed to get puzzles: {response.text}")
    return response.json()["puzzles"]

def get_puzzle_details(puzzle_id: str) -> Dict:
    """Get detailed information about a specific puzzle."""
    response = requests.get(f"{BASE_URL}/puzzles/{puzzle_id}")
    if not response.ok:
        return {}
    return response.json().get("puzzle", {})

def assign_solver_to_puzzle(puzzle_id: str, solver_id: str) -> bool:
    """Assign a solver to a puzzle."""
    try:
        response = requests.post(
            f"{BASE_URL}/solvers/{solver_id}/puzz",
            json={"puzz": puzzle_id}
        )
        if not response.ok:
            return False
        return response.json().get("status") == "ok"
    except Exception:
        return False

def get_puzzle_solver_history(puzzle_id: str) -> List[str]:
    """Get the solver history for a puzzle."""
    puzzle = get_puzzle_details(puzzle_id)
    if "solvers" not in puzzle:
        return []
    return puzzle.get("solvers", "").split(",") if puzzle.get("solvers") else []

def verify_answer(puzzle_id: str, answer: str) -> bool:
    """Verify a puzzle answer."""
    try:
        response = requests.post(
            f"{BASE_URL}/puzzles/{puzzle_id}/answer",
            json={"answer": answer}
        )
        if not response.ok:
            return False
        return response.json().get("status") == "ok"
    except Exception:
        return False

def test_answer_verification(self, result: TestResult):
    """Test answer verification functionality."""
    puzzles = get_all_puzzles()
    if not puzzles:
        return
        
    test_puzzle = puzzles[0]
    
    # Test incorrect answer
    incorrect_result = verify_answer(test_puzzle["id"], "WRONGANSWER")
    if incorrect_result:
        result.fail()
        return
        
    # Test correct answer
    correct_answer = test_puzzle.get("answer", "CORRECTANSWER")
    correct_result = verify_answer(test_puzzle["id"], correct_answer)
    if not correct_result:
        result.fail()
        return
        
    result.pass_()

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
                
            puzzle = random.choice(available_puzzles)
            print(f"\nAssigning solver {solver['name']} (ID: {solver['id']}) to puzzle {puzzle['name']} (ID: {puzzle['id']})")
            
            # Assign solver to puzzle
            if assign_solver_to_puzzle(puzzle["id"], solver["id"]):
                puzzle_history_counts[puzzle["id"]] += 1
                print(f"Successfully assigned solver to puzzle. History count: {puzzle_history_counts[puzzle['id']]}")
            else:
                print("Failed to assign solver to puzzle!")
                
    # Run answer verification test
    print("\nRunning answer verification test...")
    result = TestResult()
    test_answer_verification(result)
    print(f"\nAnswer verification test result: {'PASS' if result.passed else 'FAIL'}")

if __name__ == "__main__":
    main() 