import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import hole_news as news

class NewsEntrypointTests(unittest.TestCase):
    def test_main_always_runs_publication_pipeline(self):
        candidates=[{"url":"https://example.org/dino"}]
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY":"test"}), patch.object(news,"hole_kandidaten",return_value=candidates), patch.object(news.news_pipeline,"run",return_value={"ready":1}) as run:
            self.assertEqual(news.main(), {"ready":1})
        run.assert_called_once_with(candidates)

    def test_empty_feed_still_runs_pending_queue(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY":"test"}), patch.object(news,"hole_kandidaten",return_value=[]), patch.object(news.news_pipeline,"run") as run:
            news.main()
        run.assert_called_once_with([])

    def test_all_feeds_and_unknown_taxa_reach_semantic_review(self):
        entries=[{"title":"New taxon Foobarensis", "link":f"https://example.org/{i}","summary":"Skull anatomy."} for i in range(25)]
        response=SimpleNamespace(content=b"rss",raise_for_status=lambda:None)
        with patch.object(news,"FEEDS",[("ScienceDaily","https://example.org/feed")]), patch.object(news.requests,"get",return_value=response), patch.object(news.feedparser,"parse",return_value=SimpleNamespace(bozo=False,entries=entries)):
            self.assertEqual(len(news.hole_kandidaten()),25)

    def test_url_tracking_and_invalid_date(self):
        self.assertEqual(news.normalisiere_url("https://EXAMPLE.org/a/?utm_source=x#top"),"https://example.org/a")
        self.assertFalse(news._valid_news([{"titel":"A","zusammenfassung":"B","quelle":"C","url":"https://example.org","datum":"2026-02-31"}]))

    def test_doi_normalization_and_crossref_abstract(self):
        self.assertEqual(news.normalisiere_doi("https://doi.org/10.1093/zoolinnean/zlag162."), "10.1093/zoolinnean/zlag162")
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"message": {"items": [{
            "DOI": "10.1093/zoolinnean/zlag162", "title": ["A study"],
            "abstract": "<jats:p>Observed &amp; tested. Further observations support the description of the fossil from a stratigraphically well documented locality in southern England.</jats:p>",
            "published-online": {"date-parts": [[2026, 11, 1]]}, "next-cursor": ""
        }]}})
        with patch.object(news.requests, "get", return_value=response):
            out = news.hole_journal_kandidaten(today="2026-11-13")
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["text"].startswith("Observed & tested."))
        self.assertEqual(out[0]["study_datum"], "2026-11-01")

if __name__ == "__main__": unittest.main()
