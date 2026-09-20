"""GEMINI_EMBEDDING_MODEL handling: normalization and default."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class TestEmbeddingModelId(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # pbllmlib imports pblib, which connects to MySQL at import; stub it.
        stub = types.ModuleType("pblib")
        stub.debug_log = lambda *a, **k: None
        with patch.dict(sys.modules, {"pblib": stub}):
            cls.pbllmlib = importlib.import_module("pbllmlib")

    def test_default_when_unset(self):
        f = self.pbllmlib.embedding_model_id
        self.assertEqual(f(None), "models/gemini-embedding-001")
        self.assertEqual(f(""), "models/gemini-embedding-001")

    def test_prefix_added_once(self):
        f = self.pbllmlib.embedding_model_id
        self.assertEqual(f("gemini-embedding-2"), "models/gemini-embedding-2")
        self.assertEqual(f("models/gemini-embedding-2"), "models/gemini-embedding-2")
        self.assertEqual(f("  gemini-embedding-2 "), "models/gemini-embedding-2")

    def test_mismatch_compares_normalized_forms(self):
        f = self.pbllmlib.embedding_model_id
        self.assertEqual(f("gemini-embedding-001"), f("models/gemini-embedding-001"))


if __name__ == "__main__":
    unittest.main()
