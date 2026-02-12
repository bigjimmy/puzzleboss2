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

- **tests/test_bigjimmybot.py**: Unit tests for bigjimmybot.py functions
  - `TestTimestampParsing`: Tests for timestamp conversion functions
  - `TestSolverLookup`: Tests for solver ID lookup with mocked API
  - `TestActivityProcessing`: Tests for sheet activity processing and assignment logic
  - `TestFixtureValidity`: Validation tests for fixture data

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
- pbrest.py API endpoints
- pbgooglelib.py Google API integration
- pbllmlib.py LLM query functions
- Integration tests with Docker container
