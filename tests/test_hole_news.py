import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "hole_news.py"


def load_script():
    spec = importlib.util.spec_from_file_location("hole_news_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    stubs = {"feedparser": types.SimpleNamespace(parse=lambda _url: None),
             "requests": types.SimpleNamespace()}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class NewsOutputTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.tempdir = tempfile.TemporaryDirectory()
        self.output = Path(self.tempdir.name) / "news.json"
        self.archive = Path(self.tempdir.name) / "news-archiv.json"
        self.previous = (
            '{"meldungen":[{"titel":"Vorhandener Artikel",'
            '"zusammenfassung":"Vorhandene Zusammenfassung.","quelle":"Testquelle",'
            '"url":"https://example.org/old","datum":"2026-10-14"}],"stand":"2026-10-17"}'
        )
        self.output.write_text(self.previous, encoding="utf-8")
        self.output_patch = patch.object(self.module, "AUSGABE", str(self.output))
        self.output_patch.start()
        self.archive_patch = patch.object(self.module, "ARCHIV", str(self.archive))
        self.archive_patch.start()
        self.env_patch = patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
        self.env_patch.start()
        self.candidate = {
            "quelle": "Testquelle", "titel": "Kandidat", "url": "https://example.org/story", "text": "Fossilfund"
        }

    def tearDown(self):
        self.env_patch.stop()
        self.output_patch.stop()
        self.archive_patch.stop()
        self.tempdir.cleanup()

    def test_no_candidates_preserves_previous_news(self):
        with patch.object(self.module, "hole_kandidaten", return_value=[]), \
             patch.object(self.module, "fasse_zusammen") as summarize:
            self.module.main()
        summarize.assert_not_called()
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)

    def test_empty_summary_preserves_previous_news(self):
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), \
             patch.object(self.module, "fasse_zusammen", return_value={"meldungen": []}):
            self.module.main()
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)

    def test_feed_failure_preserves_previous_news(self):
        with patch.object(self.module, "hole_kandidaten", side_effect=RuntimeError("feed unavailable")):
            with self.assertRaisesRegex(RuntimeError, "feed unavailable"):
                self.module.main()
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)

    def test_incomplete_summary_fails_without_overwriting_news(self):
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), \
             patch.object(self.module, "fasse_zusammen", return_value={"meldungen": [{"titel": "partial"}]}):
            with self.assertRaises(SystemExit):
                self.module.main()
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)

    def test_summary_with_unlisted_url_is_rejected(self):
        summary = {"meldungen": [{
            "titel": "Neuer Artikel", "zusammenfassung": "Belegte Zusammenfassung.",
            "quelle": "Testquelle", "url": "https://example.org/unlisted", "datum": "2026-10-18",
        }]}
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), \
             patch.object(self.module, "fasse_zusammen", return_value=summary):
            with self.assertRaises(SystemExit):
                self.module.main()
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)

    def test_valid_summary_replaces_news(self):
        summary = {"meldungen": [{
            "titel": "Neuer Artikel", "zusammenfassung": "Belegte Zusammenfassung.",
            "quelle": "Testquelle", "url": "https://example.org/story", "datum": "2026-10-18",
        }]}
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), \
             patch.object(self.module, "fasse_zusammen", return_value=summary):
            self.module.main()
        self.assertEqual(__import__("json").loads(self.output.read_text(encoding="utf-8"))["meldungen"], summary["meldungen"])

    def test_success_archives_previous_and_new_feed(self):
        summary = {"meldungen": [{"titel": "Neu", "zusammenfassung": "S", "quelle": "Testquelle",
            "url": "https://example.org/story", "datum": "2026-10-18"}]}
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), patch.object(self.module, "fasse_zusammen", return_value=summary):
            self.module.main()
        archive = __import__("json").loads(self.archive.read_text(encoding="utf-8"))
        self.assertEqual({x["url"] for x in archive["meldungen"]}, {"https://example.org/old", "https://example.org/story"})

    def test_api_failure_archives_old_and_leaves_feed(self):
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), patch.object(self.module, "fasse_zusammen", side_effect=RuntimeError("api")):
            with self.assertRaisesRegex(RuntimeError, "api"):
                self.module.main()
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)
        archive = __import__("json").loads(self.archive.read_text(encoding="utf-8"))
        self.assertEqual(archive["meldungen"][0]["url"], "https://example.org/old")

    def test_invalid_date_is_rejected(self):
        self.assertFalse(self.module._valid_news([{**self.candidate, "zusammenfassung": "S", "datum": "2026-02-31"}]))

    def test_corrupt_archive_is_not_replaced(self):
        original = '{"meldungen":"invalid"}'
        self.archive.write_text(original, encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.module.sichere_archiv()
        self.assertEqual(self.archive.read_text(encoding="utf-8"), original)
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)


if __name__ == "__main__":
    unittest.main()
