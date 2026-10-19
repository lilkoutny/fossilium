import os,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from content_pipeline import media,runway
class MediaTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.db=sqlite3.connect(str(Path(self.t.name)/'x.sqlite')); self.db.row_factory=sqlite3.Row; media.ensure(self.db)
  self.env=patch.dict(os.environ,{'RUNWAY_EXECUTE':'1','RUNWAYML_API_SECRET':'test','GITHUB_ACTIONS':'false','PIPELINE_UNATTENDED':'0'}); self.env.start()
  self.org=patch.object(runway,'organization',return_value={'creditBalance':1000,'tier':{'models':{'eleven_v4':{},'gen4_image':{},'gen4_turbo':{}}}}); self.org.start(); self.price=patch.object(runway.budget,'prices_current'); self.price.start()
 def tearDown(self): self.price.stop(); self.org.stop(); self.env.stop(); self.db.close(); self.t.cleanup()
 def resp(self): return type('R',(),{'status_code':200,'raise_for_status':lambda s:None,'json':lambda s:{'id':'task-12345678'}})()
 def payload(self): return {'model':'eleven_v4','promptText':'Hallo','languageCode':'de','voice':{'type':'runway-preset','presetId':'Martin'},'speed':1.0}
 def test_resume_uses_saved_task_without_post(self):
  with patch.object(runway,'_headers',return_value={}),patch.object(runway.requests,'post',return_value=self.resp()) as post: runway.submit(self.db,'voice:0','/v1/text_to_speech',self.payload()); self.assertEqual(post.call_count,1)
  with patch.object(runway,'_headers',return_value={}),patch.object(runway.requests,'post') as post: self.assertEqual(runway.submit(self.db,'voice:0','/v1/text_to_speech',self.payload())['task_id'],'task-12345678'); post.assert_not_called()
 def test_changed_payload_blocks(self):
  with patch.object(runway,'_headers',return_value={}),patch.object(runway.requests,'post',return_value=self.resp()): runway.submit(self.db,'x','/v1/text_to_speech',self.payload())
  changed=dict(self.payload(),promptText='Andere Fassung')
  with self.assertRaisesRegex(runway.RunwayBlocked,'media_request_changed'): runway.submit(self.db,'x','/v1/text_to_speech',changed)
 def test_unknown_post_is_uncertain_and_not_retried(self):
  with patch.object(runway,'_headers',return_value={}),patch.object(runway.requests,'post',side_effect=RuntimeError('timeout')) as post:
   with self.assertRaisesRegex(runway.RunwayBlocked,'uncertain'): runway.submit(self.db,'x','/v1/text_to_speech',self.payload())
   with self.assertRaisesRegex(runway.RunwayBlocked,'paid_outcome_unknown'): runway.submit(self.db,'x','/v1/text_to_speech',self.payload())
   self.assertEqual(post.call_count,1)
 def test_missing_key_reserves_nothing(self):
  self.env.stop(); os.environ.pop('RUNWAYML_API_SECRET',None)
  with self.assertRaises(runway.RunwayBlocked): runway.submit(self.db,'x','/v1/text_to_speech',self.payload())
  self.assertEqual(self.db.execute('select count(*) from budget_reservations').fetchone()[0],0)
if __name__=='__main__': unittest.main()
