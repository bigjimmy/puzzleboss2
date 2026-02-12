# Puzzleboss Testing

This directory contains unit tests for puzzleboss components using pytest and mocking.

## Setup

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

Run all tests:
```bash
pytest
```

Run specific test file:
```bash
pytest tests/test_bigjimmybot.py -v
```

Run specific test class:
```bash
pytest tests/test_bigjimmybot.py::TestSolverLookup -v
```

Run specific test:
```bash
pytest tests/test_bigjimmybot.py::TestSolverLookup::test_get_solver_id_by_name_found -v
```

Run with coverage report:
```bash
pytest --cov=bigjimmybot --cov-report=html
# Open htmlcov/index.html to see coverage report
```

## Test Structure

- **tests/test_bigjimmybot.py**: Core unit tests for bigjimmybot.py
  - `TestTimestampParsing`: Timestamp conversion functions
  - `TestSolverLookup`: Solver ID lookup with mocked API
  - `TestActivityProcessing`: Sheet activity processing and assignment logic
  - `TestFixtureValidity`: Validation of fixture data

- **tests/test_bigjimmybot_extended.py**: Extended unit tests for bigjimmybot.py
  - `TestRecordSolverActivity`: Activity recording with timestamps
  - `TestAssignSolverToPuzzle`: Solver assignment via pblib
  - `TestFetchLastSheetActivity`: Sheet activity queries
  - `TestUpdateSheetCount`, `TestCheckAbandonedPuzzle`: Metadata updates
  - `TestPuzzleProcessing`, `TestEdgeCases`: Processing pipeline
  - `TestGetDbConnection`: Connection management
  - `TestFetchSheetInfoErrorHandling`, `TestFetchSheetInfoProbe`: Hybrid sheet probing

- **tests/test_pblib_id_types.py**: ID type normalization tests for pblib.py
  - Tests every pblib function that accepts an ID parameter with both `int` and `str` input
  - Verifies SQL parameters are always `int`, never `str`
  - Guards the integer ID convention (see CLAUDE.md)

- **tests/test_pblib_solver_assignment.py**: Solver assignment behavior tests for pblib.py
  - `TestAssignSolverTypeNormalization`: solver_id stored as int in JSON
  - `TestUnassignSolverTypeNormalization`: unassign handles int/string input
  - `TestAssignUnassignsFromOldPuzzle`: cross-puzzle reassignment
  - `TestAssignSolverHistoryType`: solver_history JSON integrity

- **tests/test_rate_limiter.py**: Google API rate limiter tests
  - `TestRateLimiterBasics`: Acquire timing and slot spacing
  - `TestRateLimiterConfig`: QPM configuration
  - `TestRateLimiterThreadSafety`: Concurrent access

- **tests/fixtures/**: JSON fixtures for test data
  - `solver_*.json`: Sample solver API responses
  - `puzzle_data.json`: Sample puzzle data
  - `sheet_activity_*.json`: Sample sheet activity data

## Testing Philosophy

These are **unit tests** that mock external dependencies:
- ✅ Mock HTTP API calls (using `@patch` on `_api_request_with_retry`)
- ✅ Mock database connections
- ✅ Mock Google API calls
- ✅ Use JSON fixtures for test data

This allows testing business logic without requiring:
- ❌ Running Flask API server
- ❌ Running MySQL database
- ❌ Google API credentials

## Adding New Tests

1. Create fixtures in `tests/fixtures/` if needed
2. Add test class/methods to appropriate test file
3. Use `@patch` to mock external dependencies
4. Run tests to verify: `pytest tests/test_yourfile.py -v`

## Future Work

See README.md "Future TODOs" section for plans to expand testing to:
- pbgooglelib.py Google API integration
- pbllmlib.py LLM query functions
