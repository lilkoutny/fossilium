import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch, Mock
import news_pipeline as p

class PipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); (self.root/'publikationen').mkdir(); self.calls=[]
        for f,v in [('news-archiv.json','{"stand":"2026-01-01","meldungen":[]}'),('news.json','{"stand":"2026-01-01","meldungen":[]}'),('publikationen/artikel.json','{"artikel":[]}')]: (self.root/f).write_text(v,encoding='utf8')
    def tearDown(self): self.tmp.cleanup()
    def candidates(self,n=25): return [{"url":f"https://example.org/story/{i}","titel":f"Dinosaurierfund {i}","quelle":"Test","text":"dinosaur research"} for i in range(n)]
    def classifier(self,batch):
        self.calls.append(len(batch)); return {"decisions":[{"url":c['url'],"relevant":True,"category":"dinosaur","reason":"zentraler Taxonbezug"} for c in batch]}
    def fetch(self,c): return {"id":"S1","url":c['url'],"titel":c['titel'],"text":"source "*200,"date":"2026-01-01","umfang":"Nachricht gelesen"}
    def writer(self,c,s):
        para=" ".join(["Der Befund beschreibt den zentralen Dinosaurierfund und seine Grenzen. [[S1]]" for _ in range(15)])
        return {"relevant":True,"category":"dinosaur","reason":"zentral","article":{"titel":c['titel'],"untertitel":"Belegte Zusammenfassung.","abschnitte":[{"titel":f"Abschnitt {i}","absatz":[para]} for i in range(4)]}}
    def test_25_are_batched_and_published(self):
        p.run(self.candidates(),root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer,today='2026-01-02')
        self.assertEqual(self.calls,[20,5]); self.assertEqual(len(json.loads((self.root/'publikationen/artikel.json').read_text())['artikel']),25); self.assertEqual(len(list((self.root/'publikationen').glob('*/index.html'))),25)
    def test_foreign_url_fails_closed(self):
        def bad(batch): return {'decisions':[{'url':'https://evil.invalid','relevant':True,'category':'dinosaur','reason':'x'} for _ in batch]}
        p.run(self.candidates(2),root=self.root,classifier=bad,fetcher=self.fetch,article_writer=self.writer,today='2026-01-02')
        self.assertEqual(json.loads((self.root/'news.json').read_text())['meldungen'],[])
    def test_explicit_exclusions_and_unknown_remain_without_articles(self):
        cs=self.candidates(6); cats=['excluded','excluded','excluded','excluded','excluded','unknown']
        def review(batch): return {'decisions':[{'url':c['url'],'relevant':False if cat=='excluded' else None,'category':cat,'reason':'scope geprüft'} for c,cat in zip(batch,cats)]}
        p.run(cs,root=self.root,classifier=review,fetcher=self.fetch,article_writer=self.writer,today='2026-01-02')
        state=json.loads((self.root/'news-pipeline-state.json').read_text()); self.assertEqual(sum(x['status']=='excluded' for x in state['items']),5); self.assertEqual(len(json.loads((self.root/'publikationen/artikel.json').read_text())['artikel']),0)
    def test_clean_source_strips_script_and_nav(self):
        raw='<nav>ignore nav</nav><article><script>bad()</script><p>'+('Dinosauriertext '*190)+'</p></article>'
        text,date=p.clean_source_html(raw); self.assertNotIn('ignore nav',text); self.assertNotIn('bad()',text); self.assertGreater(len(text.split()),180)
    def test_short_article_is_pending(self):
        c=self.candidates(1)[0]
        p.run([c],root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=lambda *_:{'relevant':True,'category':'dinosaur','reason':'x','article':{'titel':'x','untertitel':'x','abschnitte':[{'titel':'x','absatz':['Kurz. [[S1]]']}]}},today='2026-01-02')
        self.assertEqual(json.loads((self.root/'news-pipeline-state.json').read_text())['items'][0]['status'],'pending')
    def test_failure_retries_once_and_tracking_reuses(self):
        c=self.candidates(1)[0]; fail=lambda _: (_ for _ in ()).throw(ValueError('blocked'))
        p.run([c],root=self.root,classifier=self.classifier,fetcher=fail,article_writer=self.writer,today='2026-01-02'); self.assertEqual(len(json.loads((self.root/'news-pipeline-state.json').read_text())['items']),1)
        p.run([],root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer,today='2026-01-06'); p.run([{**c,'url':c['url']+'?utm_source=x'}],root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer,today='2026-01-07'); self.assertEqual(len(json.loads((self.root/'publikationen/artikel.json').read_text())['artikel']),1)
    def test_corrupt_archive_is_unchanged(self):
        path=self.root/'news-archiv.json'; path.write_bytes(b'{bad')
        with self.assertRaises(Exception): p.run([],root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer)
        self.assertEqual(path.read_bytes(),b'{bad')
    def test_corrupt_state_preserves_every_existing_file(self):
        (self.root/'news-pipeline-state.json').write_text('{"version":1,"items":"bad"}')
        before={str(f):f.read_bytes() for f in self.root.rglob('*') if f.is_file()}
        with self.assertRaises(ValueError): p.run(self.candidates(1),root=self.root,classifier=self.classifier)
        self.assertEqual(before,{str(f):f.read_bytes() for f in self.root.rglob('*') if f.is_file()})
        self.assertEqual(self.calls,[])
    def test_write_failure_rolls_back_all_artifacts(self):
        a,b=self.root/'news.json',self.root/'news-archiv.json'
        before=[a.read_bytes(),b.read_bytes()]
        replace=p.os.replace
        count=0
        def fail_second(src,dst):
            nonlocal count
            count+=1
            if count==2: raise OSError('disk failure')
            return replace(src,dst)
        with patch.object(p.os,'replace',side_effect=fail_second), self.assertRaises(OSError):
            p.stage_and_write({a:'new',b:'changed'})
        self.assertEqual(before,[a.read_bytes(),b.read_bytes()])
    def test_invalid_category_and_unknown_citation_fail_closed(self):
        c=self.candidates(1)[0]
        with self.assertRaises(ValueError):
            p.validate_decisions({'decisions':[{'url':c['url'],'relevant':True,'category':'mammal','reason':'x'}]},[c])
        response=self.writer(c,self.fetch(c))
        response['article']['abschnitte'][0]['absatz'][0]+=' Unbelegt. [[S9]]'
        with self.assertRaises(ValueError): p.build_article(response,c,self.fetch(c),'2026-01-02')
    def test_pterosaur_and_marine_reptile_accepted(self):
        cs=self.candidates(2)
        def classify(batch): return {'decisions':[{'url':c['url'],'relevant':True,'category':cat,'reason':'central taxon'} for c,cat in zip(batch,['pterosaur','marine_reptile'])]}
        result=p.run(cs,root=self.root,classifier=classify,fetcher=self.fetch,article_writer=self.writer)
        self.assertEqual(result['ready'],2)
    def test_no_paid_calls_on_repeat_and_tracking_duplicate(self):
        c=self.candidates(1)[0]
        p.run([c],root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer)
        never=Mock(side_effect=AssertionError('unexpected paid or network call'))
        p.run([{**c,'url':c['url']+'/?utm_source=test#x'}],root=self.root,classifier=never,fetcher=never,article_writer=never)
        never.assert_not_called()
    def test_full_source_review_uses_schema_and_article_prose_is_parsed_locally(self):
        c=self.candidates(1)[0]
        decision=Mock(); prose=Mock()
        decision.json.return_value={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(self.classifier([c]))}]}
        prose.json.return_value={'stop_reason':'end_turn','content':[{'type':'text','text':'# Ein neuer Fund\n\nEigene Zusammenfassung.\n\n## Befund\n\nEr wird als "neu" beschrieben. [[S1]]\n\n## Grenzen\n\nWeiter offen. [[S1]]'}]}
        with patch.dict(p.os.environ,{'ANTHROPIC_API_KEY':'test'}), patch.object(p.requests,'post',side_effect=[decision,prose]) as post:
            data=p.write_article(c,self.fetch(c))
        schema=post.call_args_list[0].kwargs['json']['output_config']['format']['schema']
        self.assertEqual(set(schema['properties']['decisions']['items']['properties']['category']['enum']),p.CATEGORIES|{'excluded','unknown'})
        self.assertNotIn('output_config',post.call_args_list[1].kwargs['json'])
        self.assertEqual(data['article']['abschnitte'][0]['absatz'],['Er wird als "neu" beschrieben. [[S1]]'])
        self.assertTrue(data['relevant'])
    def test_manual_probe_defers_without_losing_remaining_items(self):
        result=p.run(self.candidates(3),root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer,max_articles=1)
        self.assertEqual((result['ready'],result['pending']),(1,2))
        result=p.run([],root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer)
        self.assertEqual((result['ready'],result['pending']),(2,0))
    def test_valid_saved_draft_is_reused_without_model_or_source_calls(self):
        with patch.object(p,'build_article',side_effect=ValueError('previous validation failure')):
            p.run(self.candidates(1),root=self.root,classifier=self.classifier,fetcher=self.fetch,article_writer=self.writer)
        never=Mock(side_effect=AssertionError('unexpected call'))
        result=p.run([],root=self.root,classifier=never,fetcher=never,article_writer=never)
        self.assertEqual(result['ready'],1); never.assert_not_called()
    def test_length_matches_available_source_without_accepting_teasers(self):
        c=self.candidates(1)[0]; response=self.writer(c,self.fetch(c))
        for s in response['article']['abschnitte']:
            s['absatz']=[' '.join(['Belegte Beobachtung im Dinosaurierfossil mit klar benannten wissenschaftlichen Grenzen. [[S1]]']*10)]
        source={**self.fetch(c),'word_count':300}
        self.assertEqual(p.build_article(response,c,source,'2026-01-02')['mindestwoerter'],300)
        with self.assertRaises(ValueError): p.build_article(response,c,{**source,'word_count':800},'2026-01-02')

    def test_same_doi_is_processed_once(self):
        cs = [dict(self.candidates(1)[0], url='https://doi.org/10.1093/zoolinnean/zlag162', doi='10.1093/zoolinnean/zlag162', journal_abstract=True, study_datum='2026-01-01', text='abstract '*30),
              dict(self.candidates(1)[0], url='https://doi.org/10.1093/zoolinnean/zlag162?x=1', doi='10.1093/zoolinnean/zlag162', journal_abstract=True, study_datum='2026-01-01', text='abstract '*30)]
        result = p.run(cs, root=self.root, classifier=self.classifier, fetcher=self.fetch, article_writer=self.short_writer, today='2026-01-02')
        self.assertEqual(result['ready'], 1)
        never = Mock(side_effect=AssertionError('already published'))
        p.run(cs, root=self.root, classifier=never, fetcher=never, article_writer=never, today='2026-01-03')
        never.assert_not_called()

    def short_writer(self, candidate, source):
        response = self.writer(candidate, source)
        response['article']['abschnitte'] = response['article']['abschnitte'][:2]
        return response

    def test_journal_and_report_share_one_article_and_keep_source_numbers(self):
        doi = '10.1093/zoolinnean/zlag162'
        report = self.candidates(1)[0]
        journal = dict(report, url='https://doi.org/'+doi, doi=doi, journal_abstract=True,
                       study_datum='2026-01-01', text='abstract '*30)
        writer = Mock(wraps=self.short_writer)
        fetch = lambda c: {**self.fetch(c), 'study_doi': doi}
        p.run([report, journal], root=self.root, classifier=self.classifier, fetcher=fetch,
              article_writer=writer, today='2026-01-02')
        writer.assert_called_once()
        article, = json.loads((self.root/'publikationen/artikel.json').read_text(encoding='utf-8'))['artikel']
        self.assertEqual(article['original_url'], journal['url'])
        self.assertEqual(article['study_datum'], '2026-01-01')
        self.assertEqual([q['url'] for q in article['quellen']], [journal['url'], report['url']])
        self.assertIn('veröffentlichte Abstract', article['untertitel'])
        self.assertEqual(len(json.loads((self.root/'news-archiv.json').read_text())['meldungen']), 1)

    def test_new_journal_source_attaches_to_older_report(self):
        doi = '10.1093/zoolinnean/zlag162'
        report = self.candidates(1)[0]
        fetch = lambda c: {**self.fetch(c), 'study_doi': doi}
        p.run([report], root=self.root, classifier=self.classifier, fetcher=fetch, article_writer=self.writer)
        journal = dict(report, url='https://doi.org/'+doi, doi=doi, journal_abstract=True,
                       study_datum='2026-01-01', text='abstract '*30)
        writer = Mock(side_effect=AssertionError('second article'))
        p.run([journal], root=self.root, classifier=self.classifier, article_writer=writer)
        writer.assert_not_called()
        article, = json.loads((self.root/'publikationen/artikel.json').read_text())['artikel']
        self.assertEqual(article['original_url'], report['url'])
        self.assertEqual(article['quellen'][1]['url'], journal['url'])
        self.assertEqual(article['study_datum'], '2026-01-01')

    def test_journal_retry_refreshes_abstract_without_storing_it(self):
        doi = '10.1093/zoolinnean/zlag162'
        candidate = dict(self.candidates(1)[0], url='https://doi.org/'+doi, doi=doi,
                         journal_abstract=True, study_datum='2026-01-01', text='unique-abstract '*30)
        failing = Mock(side_effect=ValueError('temporary model failure'))
        result = p.run([candidate], root=self.root, classifier=self.classifier, article_writer=failing)
        self.assertEqual(result['pending'], 1)
        self.assertNotIn('unique-abstract', (self.root/'news-pipeline-state.json').read_text(encoding='utf-8'))
        never = Mock(side_effect=AssertionError('missing abstract'))
        self.assertEqual(p.run([], root=self.root, classifier=never, article_writer=never)['pending'], 1)
        never.assert_not_called()
        self.assertEqual(p.run([candidate], root=self.root, classifier=self.classifier, article_writer=self.short_writer)['ready'], 1)

    def test_news_source_requires_unambiguous_study_link(self):
        doi = '10.1093/zoolinnean/zlag162'
        reference = '<a href="https://doi.org/10.1000/other">Other study</a>'
        for additional, expected in [('', doi), (reference, '')]:
            with self.subTest(additional=additional):
                raw = (f'<nav>{reference}</nav><article><p>' + 'Fossil observations '*100
                       + f'<a href="https://doi.org/{doi}">Study</a>{additional}</p></article>')
                response = Mock(headers={'content-type': 'text/html'})
                response.iter_content.return_value = [raw.encode('utf-8')]
                with patch.object(p.requests, 'get') as request:
                    request.return_value.__enter__.return_value = response
                    source = p.fetch_source(self.candidates(1)[0])
                self.assertEqual(source['study_doi'], expected)
if __name__=='__main__': unittest.main()
