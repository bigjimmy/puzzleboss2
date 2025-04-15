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
    print(f"\nDEBUG - Getting details for puzzle {puzzle_id}")
    response = requests.get(f"{BASE_URL}/puzzles/{puzzle_id}")
    print(f"DEBUG - Response status: {response.status_code}")
    print(f"DEBUG - Response body: {response.text}")
    if not response.ok:
        print(f"Error getting puzzle details: {response.text}")
        return {}
    return response.json().get("puzzle", {})

def assign_solver_to_puzzle(puzzle_id: str, solver_id: str) -> bool:
    """Assign a solver to a puzzle."""
    print(f"DEBUG - Before API call:")
    print(f"  Puzzle ID: {puzzle_id}")
    print(f"  Solver ID: {solver_id}")
    
    try:
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
            
        # Check response structure
        response_data = response.json()
        if "status" not in response_data:
            print(f"Error: Response missing 'status' field: {response_data}")
            return False
            
        if response_data["status"] != "ok":
            print(f"Error: Response status is not 'ok': {response_data}")
            return False
            
        return True
        
    except Exception as e:
        print(f"Exception during solver assignment: {str(e)}")
        print(f"  Puzzle ID: {puzzle_id}")
        print(f"  Solver ID: {solver_id}")
        return False

def get_puzzle_solver_history(puzzle_id: str) -> List[str]:
    """Get the solver history for a puzzle."""
    print(f"\nDEBUG - Getting puzzle solver history for puzzle {puzzle_id}")
    puzzle = get_puzzle_details(puzzle_id)
    print(f"DEBUG - Puzzle details: {puzzle}")
    if "solvers" not in puzzle:
        print(f"Error: 'solvers' key not found in puzzle details: {puzzle}")
        return []
    return puzzle.get("solvers", "").split(",") if puzzle.get("solvers") else []

def verify_answer(puzzle_id: str, answer: str) -> bool:
    """Verify a puzzle answer."""
    print(f"\nDEBUG - Verifying answer for puzzle {puzzle_id}")
    print(f"DEBUG - Answer to verify: {answer}")
    try:
        response = requests.post(
            f"{BASE_URL}/puzzles/{puzzle_id}/answer",
            json={"answer": answer}
        )
        print(f"DEBUG - Response status: {response.status_code}")
        print(f"DEBUG - Response body: {response.text}")
        if not response.ok:
            print(f"Error verifying answer: {response.text}")
            return False
            
        result = response.json()
        print(f"DEBUG - Parsed response: {result}")
        if result.get("status") != "ok":
            print(f"Answer verification failed for puzzle {puzzle_id}:")
            print(f"  Expected status: 'ok'")
            print(f"  Actual status: '{result.get('status')}'")
            print(f"  Error message: {result.get('error', 'No error message')}")
            print(f"  Submitted answer: '{answer}'")
            return False
            
        return True
    except Exception as e:
        print(f"DEBUG - Exception during answer verification: {str(e)}")
        print(f"DEBUG - Exception type: {type(e).__name__}")
        import traceback
        print(f"DEBUG - Traceback: {traceback.format_exc()}")
        return False

def test_answer_verification(self, result: TestResult):
    """Test answer verification functionality."""
    print("\nTesting answer verification...")
    
    # Get a puzzle to test
    puzzles = get_all_puzzles()
    if not puzzles:
        print("No puzzles found to test!")
        return
        
    test_puzzle = puzzles[0]
    print(f"Testing with puzzle: {test_puzzle['name']} (ID: {test_puzzle['id']})")
    print(f"DEBUG - Puzzle details: {test_puzzle}")
    
    # Test incorrect answer
    print("\nTesting incorrect answer...")
    incorrect_result = verify_answer(test_puzzle["id"], "WRONGANSWER")
    print(f"Result: {'Accepted' if incorrect_result else 'Rejected'}")
    if incorrect_result:
        print("ERROR: Incorrect answer was accepted!")
        result.fail()
        return
        
    # Test correct answer
    print("\nTesting correct answer...")
    correct_answer = test_puzzle.get("answer", "CORRECTANSWER")
    print(f"DEBUG - Correct answer to test: {correct_answer}")
    correct_result = verify_answer(test_puzzle["id"], correct_answer)
    print(f"Result: {'Accepted' if correct_result else 'Rejected'}")
    if not correct_result:
        print("ERROR: Correct answer was rejected!")
        print(f"DEBUG - Puzzle answer: {test_puzzle.get('answer')}")
        print(f"DEBUG - Tested answer: {correct_answer}")
        result.fail()
        return
        
    print("\nAnswer verification test passed!")
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
                
            target_puzzle = random.choice(available_puzzles)
            
            # Print debug info before assignment
            print(f"\nDEBUG - Assignment attempt:")
            print(f"  Solver: {solver['name']} (ID: {solver['id']})")
            print(f"  Puzzle: {target_puzzle['name']} (ID: {target_puzzle['id']})")
            
            # Assign solver to the new puzzle - NOTE: parameters are in correct order here
            if assign_solver_to_puzzle(target_puzzle["id"], solver["id"]):
                # Update history count for the puzzle
                print(f"DEBUG - Getting history for puzzle {target_puzzle['id']}")
                history = get_puzzle_solver_history(target_puzzle["id"])
                print(f"DEBUG - History for puzzle {target_puzzle['id']}: {history}")
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