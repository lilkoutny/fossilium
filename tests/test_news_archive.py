import importlib.util
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "hole_news.py"

def load():
    spec = importlib.util.spec_from_file_location("news_archive_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"feedparser": types.SimpleNamespace(), "requests": types.SimpleNamespace()}):
        spec.loader.exec_module(mod)
    return mod

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.old = {"meldungen": [{"titel":"Alt","zusammenfassung":"S","quelle":"Q",
            "url":"https://EXAMPLE.org/a/?utm_source=x#frag","datum":"2026-10-01"}]}
        self.new = {"titel":"Neu","zusammenfassung":"N","quelle":"Q",
            "url":"https://example.org/b?gclid=z","datum":"2026-10-02"}

    def test_merge_no_loss_and_normalized_dedupe(self):
        out = self.m.merge_archiv(self.old, [self.new, dict(self.new, datum="2026-10-09")], "2026-10-19")
        self.assertEqual(len(out["meldungen"]), 2)
        self.assertEqual(out["meldungen"][0]["datum"], "2026-10-02")
        self.assertEqual(out["meldungen"][1]["url"], "https://example.org/a")

    def test_repeated_merge_is_idempotent_and_date_stable(self):
        once = self.m.merge_archiv({"meldungen": []}, [self.new], "2026-10-02")
        twice = self.m.merge_archiv(once, [dict(self.new, datum="2026-10-19")], "2026-10-19")
        self.assertEqual(twice["meldungen"][0]["datum"], "2026-10-02")
        self.assertEqual(len(twice["meldungen"]), 1)

    def test_invalid_entries_are_not_archived(self):
        out = self.m.merge_archiv(self.old, [{"titel":"x"}, {**self.new, "url":"file:///x"}], "2026-10-19")
        self.assertEqual(len(out["meldungen"]), 1)

if __name__ == "__main__":
    unittest.main()
