"""GEMINI_EMBEDDING_MODEL handling: normalization and default (pblib)."""
import unittest

import pblib


class TestEmbeddingModelId(unittest.TestCase):
    def test_default_when_unset(self):
        self.assertEqual(pblib.embedding_model_id(None), "models/gemini-embedding-001")
        self.assertEqual(pblib.embedding_model_id(""), "models/gemini-embedding-001")

    def test_prefix_added_once(self):
        f = pblib.embedding_model_id
        self.assertEqual(f("gemini-embedding-2"), "models/gemini-embedding-2")
        self.assertEqual(f("models/gemini-embedding-2"), "models/gemini-embedding-2")
        self.assertEqual(f("  gemini-embedding-2 "), "models/gemini-embedding-2")

    def test_mismatch_compares_normalized_forms(self):
        f = pblib.embedding_model_id
        self.assertEqual(f("gemini-embedding-001"), f("models/gemini-embedding-001"))


if __name__ == "__main__":
    unittest.main()
