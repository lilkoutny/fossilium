import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publication_renderer', ROOT / 'publikationen/render.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class PublicationsTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'publikationen/artikel.json').read_text(encoding='utf-8'))

    def test_reviewed_articles_and_generated_pages_match(self):
        renderer.validate(self.data)
        for a in self.data['artikel']:
            self.assertGreaterEqual(sum(len(p.split()) for s in a['abschnitte'] for p in s['absatz']), 450)
            self.assertEqual((ROOT / 'publikationen' / a['slug'] / 'index.html').read_text(encoding='utf-8'), renderer.render(a))

    def test_duplicate_article_is_rejected(self):
        self.data['artikel'].append(copy.deepcopy(self.data['artikel'][0]))
        with self.assertRaises(ValueError): renderer.validate(self.data)

    def test_output_path_cannot_escape(self):
        self.data['artikel'][0]['slug'] = '../index'
        with self.assertRaises(ValueError): renderer.validate(self.data)

    def test_bad_reference_cannot_be_published(self):
        self.data['artikel'][0]['abschnitte'][0]['quellen'] = ['S999']
        with self.assertRaises(ValueError): renderer.validate(self.data)

    def test_unsafe_urls_and_missing_image_credit_are_rejected(self):
        for value in ('javascript:alert(1)', 'https://secret@example.org/', 'https://[invalid'):
            d = copy.deepcopy(self.data); d['artikel'][0]['original_url'] = value
            with self.assertRaises(ValueError): renderer.validate(d)
        self.data['artikel'][0]['bilder'][0]['credit'] = ''
        with self.assertRaises(ValueError): renderer.validate(self.data)

    def test_image_path_cannot_escape(self):
        self.data['artikel'][0]['bilder'][0]['datei'] = '../bilder/triceratops.png'
        with self.assertRaises(ValueError): renderer.validate(self.data)

    def test_article_text_is_escaped(self):
        a=self.data['artikel'][0]
        a['abschnitte'][0]['absatz']=['<script>alert("x")</script>']
        html=renderer.render(a)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)


if __name__ == '__main__': unittest.main()
