import os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import production as p

SOURCE='Researchers identify a previously unrecognized fossil from the museum collection. '+('Fossil evidence and anatomical comparisons. '*20)
URL='https://www.nhm.ac.uk/discover/fossil-discovery.html'
def script():
    return {'title':'Ein Fossil im Museum','scenes':[{'seconds':12,'narration':'Dieses Fossil lag lange im Museum und wird nun erneut untersucht. Die Forschenden vergleichen seine Merkmale jetzt besonders sorgfältig mit verwandten Tieren.','source_url':URL,'excerpt':SOURCE[:78],'visual':'Museumsgrafik','caption':'Fossil im Museum'} for _ in range(5)]}
class ProductionTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.db=p.database(str(Path(self.temp.name)/'state.sqlite')); self.jid=p.ingest(self.db,'https://www.sciencedaily.com/releases/test.htm','Test')
    def tearDown(self): self.db.close(); self.temp.cleanup()
    def test_tracking_urls_deduplicate(self):
        a=p.ingest(self.db,'https://example.org/a?utm_source=x#part'); b=p.ingest(self.db,'https://example.org/a'); self.assertEqual(a,b)
    def test_empty_claims_and_invented_excerpt_rejected(self):
        with self.assertRaises(p.Blocked): p.validate_script({'scenes':[]},[])
        data=script(); data['scenes'][0]['excerpt']='An entirely invented source passage'
        with self.assertRaises(p.Blocked): p.validate_script(data,[{'url':URL,'text':SOURCE}])
    def test_disabled_paid_requests_never_hit_network(self):
        with patch.dict(os.environ,{'PIPELINE_ALLOW_PAID_CALLS':'0'}),patch.object(p.requests,'post') as post:
            with self.assertRaises(p.Blocked): p.model(self.db,p.load(self.db,self.jid),'test',{})
            post.assert_not_called()
    def test_daily_reservation_survives_provider_failure(self):
        with patch.dict(os.environ,{'PIPELINE_ALLOW_PAID_CALLS':'1','ANTHROPIC_API_KEY':'test','PIPELINE_MAX_CALLS_PER_DAY':'1'}),patch.object(p.requests,'post',side_effect=RuntimeError('timeout')) as post:
            with self.assertRaises(RuntimeError): p.model(self.db,p.load(self.db,self.jid),'test',{})
            with self.assertRaisesRegex(p.Blocked,'daily_call_limit'): p.model(self.db,p.load(self.db,self.jid),'test',{})
            self.assertEqual(post.call_count,1)
    def test_successful_script_is_not_claimed_as_video(self):
        result={'criteria':dict.fromkeys(('relevance','novelty','evidence','understandable_story','visual_potential'),4),'reason':'Stark','angle':'Museum'}
        with patch.object(p,'fetch',return_value=(SOURCE,[URL])),patch.object(p,'model',side_effect=[result,script(),{'supported':True,'issues':[]}]):
            job=p.process(self.db,self.jid)
        self.assertEqual(job['state'],'script_ready'); self.assertEqual(job['stage'],'video')
        with patch.object(p,'model') as model: p.process(self.db,self.jid); model.assert_not_called()
        feed=p.export(self.db,Path(self.temp.name)/'status.json'); self.assertFalse(feed['automatic_video']); self.assertNotIn('text',feed['jobs'][0]['sources'][0])
    def test_retry_resumes_script_without_research_or_score(self):
        r=p.load(self.db,self.jid); r['stage']='script'; r['data']={'sources':[{'url':URL,'text':SOURCE}]}; p.save(self.db,r,'blocked','api_not_enabled')
        with patch.object(p,'fetch') as fetch,patch.object(p,'model',side_effect=[script(),{'supported':True,'issues':[]}]) as model:
            self.assertEqual(p.process(self.db,self.jid,retry=True)['state'],'script_ready')
            fetch.assert_not_called(); self.assertEqual(model.call_count,2)
    def test_unsupported_script_is_not_released(self):
        r=p.load(self.db,self.jid); r['stage']='verify'; r['data']={'script':script(),'sources':[{'url':URL,'text':SOURCE}]}; p.save(self.db,r,'queued')
        with patch.object(p,'model',return_value={'supported':False,'issues':['Unsupported estimate']}):
            self.assertEqual(p.process(self.db,self.jid)['state'],'blocked')
    def test_low_interest_skips_script(self):
        result={'criteria':dict.fromkeys(('relevance','novelty','evidence','understandable_story','visual_potential'),1)}
        with patch.object(p,'fetch',return_value=(SOURCE,[URL])),patch.object(p,'model',return_value=result) as model:
            self.assertEqual(p.process(self.db,self.jid)['state'],'skipped'); self.assertEqual(model.call_count,1)
    def test_private_dns_and_ipv6_rejected_before_request(self):
        with patch.object(p.socket,'getaddrinfo',return_value=[(None,None,None,None,('::1',443))]): self.assertFalse(p.public('https://example.org/a'))
        response=Mock(); response.__enter__=Mock(return_value=response); response.__exit__=Mock(return_value=False); response.status_code=302; response.headers={'Location':'http://127.0.0.1/secret'}
        with patch.object(p,'public',side_effect=[True,False]),patch.object(p.requests,'get',return_value=response) as get:
            with self.assertRaises(p.Blocked): p.fetch('https://example.org/a')
            self.assertEqual(get.call_count,1)
if __name__=='__main__': unittest.main()
