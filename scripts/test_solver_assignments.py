#!/usr/bin/env python3

import requests
import random
from typing import List, Dict

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
    print("DEBUG - Before API call:")
    print(f"  Puzzle ID: {puzzle_id}")
    print(f"  Solver ID: {solver_id}")

    try:
        response = requests.post(
            f"{BASE_URL}/solvers/{solver_id}/puzz", json={"puzz": puzzle_id}
        )

        print("DEBUG - After API call:")
        print(f"  Request URL: {BASE_URL}/solvers/{solver_id}/puzz")
        print(f"  Request Body: {{'puzz': {puzzle_id}}}")
        print(f"  Response Status: {response.status_code}")
        print(f"  Response Body: {response.text}")

        if not response.ok:
            print(
                f"Failed to assign solver {solver_id} to puzzle {puzzle_id}: {response.text}"
            )
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

    except (requests.RequestException, KeyError, ValueError) as e:
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
            available_puzzles = [
                p for p in puzzles if puzzle_history_counts[p["id"]] < 10
            ]
            if not available_puzzles:
                continue

            puzzle = random.choice(available_puzzles)
            print(
                f"\nAssigning solver {solver['name']} (ID: {solver['id']}) to puzzle {puzzle['name']} (ID: {puzzle['id']})"
            )

            # Assign solver to puzzle
            if assign_solver_to_puzzle(puzzle["id"], solver["id"]):
                puzzle_history_counts[puzzle["id"]] += 1
                print(
                    f"Successfully assigned solver to puzzle. History count: {puzzle_history_counts[puzzle['id']]}"
                )
            else:
                print("Failed to assign solver to puzzle!")


if __name__ == "__main__":
    main()
