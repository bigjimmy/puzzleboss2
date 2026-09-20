"""Wiki search scoring: relevance decides inclusion, recency/priority only reorder."""
import sys
import types
import unittest
from datetime import datetime, timezone

# pbllmlib imports pblib (mocked MySQLdb via conftest) and starts a background
# indexing thread on import; stub the module surface we need instead.
_pb = types.ModuleType("pblib")
_pb.debug_log = lambda *a, **k: None
_pb.DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
_pb.embedding_model_id = lambda n: "models/" + (n or "gemini-embedding-001")
_saved = sys.modules.get("pblib")
sys.modules["pblib"] = _pb
try:
    import pbllmlib
finally:
    if _saved is not None:
        sys.modules["pblib"] = _saved

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)
score = pbllmlib._score_wiki_hit


class TestWikiScoring(unittest.TestCase):
    def test_old_but_relevant_page_is_kept(self):
        # 5.7-year-old page, strong match (the real "Have You Tried" case)
        s, keep = score(0.59, {"last_modified": "2021-01-20T16:10:02Z"}, NOW)
        self.assertTrue(keep)
        self.assertGreater(s, 0.25)

    def test_unrelated_hit_is_dropped_regardless_of_recency(self):
        s, keep = score(0.97, {"last_modified": "2026-09-19T00:00:00Z", "is_priority": True}, NOW)
        self.assertFalse(keep)

    def test_recency_reorders_but_never_excludes(self):
        new, _ = score(0.60, {"last_modified": "2026-09-01T00:00:00Z"}, NOW)
        old, keep_old = score(0.60, {"last_modified": "2012-01-01T00:00:00Z"}, NOW)
        self.assertTrue(keep_old)
        self.assertGreater(new, old)
        self.assertLess(new - old, 0.25)  # a tiebreaker, not a cliff

    def test_priority_boost(self):
        plain, _ = score(0.60, {"last_modified": "2020-01-01T00:00:00Z"}, NOW)
        prio, _ = score(0.60, {"last_modified": "2020-01-01T00:00:00Z", "is_priority": True}, NOW)
        self.assertAlmostEqual(prio - plain, 0.15)

    def test_missing_or_bad_date_is_neutral(self):
        s1, k1 = score(0.60, {}, NOW)
        s2, k2 = score(0.60, {"last_modified": "not a date"}, NOW)
        self.assertTrue(k1 and k2)
        self.assertAlmostEqual(s1, s2)


if __name__ == "__main__":
    unittest.main()
