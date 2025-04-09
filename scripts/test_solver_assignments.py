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
        raise Exception(f"Failed to get puzzle {puzzle_id}: {response.text}")
    return response.json()["puzzle"]

def assign_solver_to_puzzle(solver_id: str, puzzle_id: str) -> bool:
    """Assign a solver to a puzzle."""
    response = requests.post(
        f"{BASE_URL}/solvers/{solver_id}/puzz",
        json={"puzz": puzzle_id}
    )
    if not response.ok:
        print(f"Failed to assign solver {solver_id} to puzzle {puzzle_id}: {response.text}")
        return False
    return True

def get_puzzle_solver_history(puzzle_id: str) -> List[str]:
    """Get the solver history for a puzzle."""
    puzzle = get_puzzle_details(puzzle_id)
    return puzzle.get("solvers", "").split(",") if puzzle.get("solvers") else []

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
            
            # Assign solver to the new puzzle
            if assign_solver_to_puzzle(solver["id"], target_puzzle["id"]):
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