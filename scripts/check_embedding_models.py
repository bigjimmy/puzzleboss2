#!/usr/bin/env python3
"""
Diagnostic script to check available Google embedding models and package versions.
Run this in production to diagnose the embedding model 404 errors.
"""

import sys
import os

# Add parent directory to path so we can import pblib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pblib import refresh_config, configstruct

# Load config
print("=" * 80)
print("Loading puzzleboss configuration...")
print("=" * 80)
refresh_config()

# Get API key
api_key = configstruct.get("GEMINI_API_KEY")
if not api_key:
    print("ERROR: No GEMINI_API_KEY found in config!")
    print("Check your database config table or puzzleboss.yaml")
    sys.exit(1)

print(f"✓ Found API key: {api_key[:10]}...{api_key[-4:]}")
print()

# Check google-genai package version
print("=" * 80)
print("Checking google-genai package version...")
print("=" * 80)
try:
    import google.genai as genai
    import pkg_resources

    version = pkg_resources.get_distribution("google-genai").version
    print(f"google-genai version: {version}")
except ImportError:
    print("ERROR: google-genai package not installed!")
    sys.exit(1)
except Exception as e:
    print(f"Error checking version: {e}")
print()

# Try to list available models
print("=" * 80)
print("Checking available embedding models from Google API...")
print("=" * 80)

try:
    from google import genai
    client = genai.Client(api_key=api_key)

    print("Attempting to list all models...")
    models = client.models.list()

    embedding_models = []
    all_models = []

    for model in models:
        all_models.append(model.name)
        if 'embed' in model.name.lower():
            embedding_models.append(model.name)

    print(f"\nFound {len(all_models)} total models")
    print(f"Found {len(embedding_models)} embedding models:\n")

    if embedding_models:
        for model_name in sorted(embedding_models):
            print(f"  ✓ {model_name}")
    else:
        print("  (No embedding models found)")

    print("\nAll models (first 20):")
    for model_name in sorted(all_models)[:20]:
        print(f"  - {model_name}")

except Exception as e:
    print(f"ERROR listing models: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()

print()

# Test specific model names
print("=" * 80)
print("Testing specific model names that might work...")
print("=" * 80)

test_models = [
    "text-embedding-004",
    "models/text-embedding-004",
    "embedding-001",
    "models/embedding-001",
    "text-embedding-005",
    "models/text-embedding-005",
]

for test_model in test_models:
    try:
        print(f"\nTrying: {test_model}")
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model=test_model,
            contents="test query"
        )
        print(f"  ✓ SUCCESS - {test_model} works!")
        print(f"    Embedding dimension: {len(result.embeddings[0].values)}")
    except Exception as e:
        print(f"  ✗ FAILED - {test_model}")
        print(f"    Error: {str(e)[:100]}")

print()
print("=" * 80)
print("Diagnostic complete!")
print("=" * 80)
