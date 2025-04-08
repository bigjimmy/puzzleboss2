#!/usr/bin/env python3

import requests
import sys
from typing import Optional

def get_user_input(prompt: str, default: Optional[str] = None) -> str:
    """Get user input with an optional default value."""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    return input(f"{prompt}: ").strip()

def get_yes_no_input(prompt: str, default: str = "no") -> bool:
    """Get a yes/no response from the user."""
    while True:
        response = get_user_input(f"{prompt} (yes/no)", default).lower()
        if response in ["yes", "y"]:
            return True
        if response in ["no", "n"]:
            return False
        print("Please answer 'yes' or 'no'")

def confirm_destructive_action(confirmation_word: str) -> bool:
    """Request user confirmation for destructive actions."""
    user_input = input(f"\nTo confirm, please enter the word {confirmation_word}: ").strip()
    return user_input == confirmation_word

def create_test_solvers(base_url: str) -> bool:
    """Create test solver accounts."""
    print("\nCreating test solvers...")
    
    # Create 25 test solvers
    for i in range(1, 26):
        response = requests.post(
            f"{base_url}/solvers",
            json={"name": f"benoc{i}", "fullname": "user test"}
        )
        if not response.ok:
            print(f"Failed to create test solver benoc{i}: {response.text}")
            return False
            
    # Create main test solver
    response = requests.post(
        f"{base_url}/solvers",
        json={"name": "benoc", "fullname": "Benjamin OConnor"}
    )
    if not response.ok:
        print(f"Failed to create main test solver: {response.text}")
        return False
        
    return True

def create_rounds_and_puzzles(base_url: str, num_rounds: int, puzzles_per_round: int) -> bool:
    """Create test rounds and puzzles."""
    print("\nCreating rounds...")
    
    # Create rounds
    for i in range(1, num_rounds + 1):
        response = requests.post(
            f"{base_url}/rounds",
            json={"name": f"Round{i}"}
        )
        if not response.ok:
            print(f"Failed to create Round{i}: {response.text}")
            return False
            
    print("\nCreating puzzles...")
    
    # Create puzzles for each round
    for r in range(1, num_rounds + 1):
        for p in range(1, puzzles_per_round + 1):
            response = requests.post(
                f"{base_url}/puzzles",
                json={
                    "name": f"R{r}Puzz{p}",
                    "round_id": str(r),
                    "puzzle_uri": "http://www.google.com"
                }
            )
            if not response.ok:
                print(f"Failed to create puzzle R{r}Puzz{p}: {response.text}")
                return False
                
    return True

def main():
    base_url = "http://localhost:5000"
    
    print("PuzzleBoss Test Data Loader")
    print("==========================\n")
    
    # Get configuration from user
    num_rounds = int(get_user_input("Enter number of rounds", "10"))
    puzzles_per_round = int(get_user_input("Enter number of puzzles per round", "15"))
    create_solvers = get_yes_no_input(
        "\nWARNING: Create test solvers? This will DELETE existing solvers! Only do this if you know what you're doing",
        "no"
    )
    
    # Additional confirmation for test solvers
    if create_solvers and not confirm_destructive_action("DESTROYSOLVERS"):
        print("\nTest solver creation cancelled.")
        create_solvers = False
    
    # Confirm settings
    print("\nSettings:")
    print(f"Number of rounds: {num_rounds}")
    print(f"Puzzles per round: {puzzles_per_round}")
    print(f"Create test solvers: {'Yes' if create_solvers else 'No'}")
    
    if not get_yes_no_input("\nProceed with these settings?", "no"):
        print("\nAborted.")
        return
        
    # Create test solvers if requested
    if create_solvers:
        if not create_test_solvers(base_url):
            print("\nFailed to create test solvers. Aborting.")
            return
            
    # Create rounds and puzzles
    if not create_rounds_and_puzzles(base_url, num_rounds, puzzles_per_round):
        print("\nFailed to create rounds and puzzles. Aborting.")
        return
        
    print("\nTest data creation completed successfully!")

if __name__ == "__main__":
    main() 