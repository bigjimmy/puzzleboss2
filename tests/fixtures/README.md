# Test Fixtures

This directory contains JSON fixtures used for unit testing bigjimmybot and other components.

## Files

- **solver_benoc.json**: Sample solver response for user "benoc" currently assigned to a different puzzle
- **solver_already_assigned.json**: Sample solver response for user already assigned to the test puzzle
- **puzzle_data.json**: Sample puzzle data
- **sheet_activity_hidden.json**: Sample sheet activity from hidden _pb_activity sheet format

## Usage

Load fixtures in tests:

```python
import json
import os

def load_fixture(filename):
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path) as f:
        return json.load(f)

# In test:
solver_data = load_fixture('solver_benoc.json')
```
