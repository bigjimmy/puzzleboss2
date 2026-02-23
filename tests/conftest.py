"""Shared test helpers for bigjimmybot unit tests."""

import json
import os


def load_fixture(filename):
    """Load a JSON fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path) as f:
        return json.load(f)
