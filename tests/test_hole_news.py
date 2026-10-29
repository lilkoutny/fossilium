import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "hole_news.py"


class FakeNetworkError(Exception):
    pass


def api_response(body, status=200):
    return types.SimpleNamespace(status_code=status, json=lambda: body)


def load_script():
    spec = importlib.util.spec_from_file_location("hole_news_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    stubs = {"feedparser": types.SimpleNamespace(parse=lambda _url: None),
             "requests": types.SimpleNamespace(RequestException=FakeNetworkError)}
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
        self.env_patch = patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
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

    def test_openai_responses_contract_and_nested_output_text(self):
        class Response:
            status_code = 200
            def json(self):
                return {"status": "completed", "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "message", "content": [{"type": "output_text", "text": '{"meldungen": []}'}]}
                ]}
        with patch.object(self.module.requests, "post", return_value=Response(), create=True) as post:
            self.assertEqual(self.module.fasse_zusammen([self.candidate]), {"meldungen": []})
        args = post.call_args.kwargs
        self.assertEqual(post.call_args.args[0], "https://api.openai.com/v1/responses")
        self.assertEqual(args["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(args["json"]["model"], "gpt-5.4-mini-2026-03-17")
        self.assertFalse(args["json"]["store"])
        self.assertEqual(args["json"]["reasoning"], {"effort": "none"})
        self.assertEqual(args["json"]["max_output_tokens"], 2000)
        self.assertEqual(args["json"]["text"]["format"]["strict"], True)
        self.assertFalse(args["json"]["text"]["format"]["schema"]["additionalProperties"])
        schema = args["json"]["text"]["format"]["schema"]["properties"]["meldungen"]
        self.assertEqual(schema["maxItems"], 4)
        self.assertEqual(set(schema["items"]["required"]),
                         {"titel", "zusammenfassung", "quelle", "url", "datum"})
        source = __import__("json").loads(args["json"]["input"])
        self.assertEqual(source["meldungen"], [self.candidate])
        self.assertNotIn(self.candidate["url"], args["json"]["instructions"])

    def test_openai_failure_does_not_expose_key(self):
        class Response:
            status_code = 401
            def json(self): return {"error": {"message": "secret-value"}}
        with patch.object(self.module.requests, "post", return_value=Response(), create=True):
            with self.assertRaisesRegex(RuntimeError, "401") as ctx: self.module.fasse_zusammen([])
        self.assertNotIn("secret-value", str(ctx.exception))
        self.assertNotIn("test-key", str(ctx.exception))

    def test_openai_refusal_incomplete_and_malformed_are_rejected(self):
        for body in (
            {"status": "incomplete", "output": []},
            {"status": "failed", "output": []},
            {"output": []},
            [],
            {"status": "completed", "output": None},
            {"status": "completed", "output": [None]},
            {"status": "completed", "output": [{"type": "message", "content": None}]},
            {"status": "completed", "output": [{"type": "message", "content": "bad"}]},
            {"status": "completed", "output": [{"type": "message", "content": [None]}]},
            {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
            {"status": "completed", "output": [{"type": "message", "content": []}]},
            {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": None}]}]},
            {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "not JSON"}]}]},
        ):
            with self.subTest(body=body), \
                 patch.object(self.module.requests, "post", return_value=api_response(body), create=True):
                with self.assertRaises(RuntimeError):
                    self.module.fasse_zusammen([])

    def test_invalid_http_json_is_rejected(self):
        response = types.SimpleNamespace(status_code=200)
        def invalid_json():
            raise ValueError("response body must not be logged: test-key")
        response.json = invalid_json
        with patch.object(self.module.requests, "post", return_value=response, create=True):
            with self.assertRaisesRegex(RuntimeError, "JSON-Response") as ctx:
                self.module.fasse_zusammen([])
        self.assertNotIn("test-key", str(ctx.exception))

    def test_http_errors_are_reported_without_retry_or_body_leak(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status), \
                 patch.object(self.module.requests, "post",
                              return_value=api_response({"error": "test-key"}, status), create=True) as post:
                with self.assertRaisesRegex(RuntimeError, str(status)) as ctx:
                    self.module.fasse_zusammen([])
                post.assert_called_once()
                self.assertNotIn("test-key", str(ctx.exception))

    def test_network_failure_preserves_feed_and_archives_existing_news(self):
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), \
             patch.object(self.module.requests, "post",
                          side_effect=FakeNetworkError("Bearer test-key"), create=True) as post:
            with self.assertRaisesRegex(RuntimeError, "Netzwerkfehler") as ctx:
                self.module.main()
            post.assert_called_once()
        self.assertNotIn("test-key", str(ctx.exception))
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)
        archived = __import__("json").loads(self.archive.read_text(encoding="utf-8"))
        self.assertEqual(archived["meldungen"][0]["url"], "https://example.org/old")

    def test_api_auth_failure_preserves_feed(self):
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), \
             patch.object(self.module.requests, "post", return_value=api_response({}, 401), create=True):
            with self.assertRaisesRegex(RuntimeError, "401"):
                self.module.main()
        self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)

    def test_real_adapter_success_writes_news_and_adds_archive(self):
        summary = {"meldungen": [{"titel": "Neuer Fossilfund", "zusammenfassung": "Belegt.",
                    "quelle": "Testquelle", "url": "https://example.org/story", "datum": "2026-10-29"}]}
        body = {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": __import__("json").dumps(summary)}]}]}
        with patch.object(self.module, "hole_kandidaten", return_value=[self.candidate]), \
             patch.object(self.module.requests, "post", return_value=api_response(body), create=True):
            self.module.main()
        self.assertEqual(__import__("json").loads(self.output.read_text(encoding="utf-8"))["meldungen"],
                         summary["meldungen"])
        archived = __import__("json").loads(self.archive.read_text(encoding="utf-8"))
        self.assertEqual({x["url"] for x in archived["meldungen"]},
                         {"https://example.org/old", "https://example.org/story"})

    def test_missing_or_blank_key_stops_before_network_and_file_changes(self):
        for env in ({}, {"OPENAI_API_KEY": "   "}):
            with self.subTest(env=env), patch.dict("os.environ", env, clear=True), \
                 patch.object(self.module.requests, "post", create=True) as post:
                with self.assertRaisesRegex(SystemExit, "OPENAI_API_KEY"):
                    self.module.main()
                post.assert_not_called()
                self.assertEqual(self.output.read_text(encoding="utf-8"), self.previous)

    def test_configured_model_is_used(self):
        with patch.dict("os.environ", {"OPENAI_NEWS_MODEL": "configured-news-model"}):
            configured = load_script()
        body = {"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": '{"meldungen": []}'}]}]}
        with patch.object(configured.requests, "post", return_value=api_response(body), create=True) as post:
            configured.fasse_zusammen([])
        self.assertEqual(post.call_args.kwargs["json"]["model"], "configured-news-model")


if __name__ == "__main__":
    unittest.main()
