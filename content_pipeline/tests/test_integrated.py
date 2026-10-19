import os,sqlite3,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from content_pipeline import media,production,runway
class IntegratedTests(unittest.TestCase):
 def test_unverified_script_never_reaches_provider(self):
  d=tempfile.mkdtemp()
  db=production.database(str(Path(d)/'state.sqlite')); jid=production.ingest(db,'https://example.org/story','Story'); row=production.load(db,jid); row['data']={'script':{'scenes':[]},'review':{'supported':False}}; production.save(db,row,'script_ready')
  with patch.object(runway,'submit') as submit:
   with self.assertRaisesRegex(runway.RunwayBlocked,'verified_script_required'): media.execute(db,jid,Path(d)/'media')
   submit.assert_not_called()
  db.close()
 def test_verified_job_runs_all_media_stages_with_unique_keys(self):
  d=tempfile.mkdtemp()
  db=production.database(str(Path(d)/'state.sqlite')); jid=production.ingest(db,'https://example.org/story','Story'); src='A primary source passage with enough evidence for this narrated scene.'
  scenes=[{'seconds':12,'narration':'This is a carefully sourced German narration with enough words for validation and review. Each sentence explains the evidence, context, uncertainty, and significance clearly for the audience.','source_url':'https://www.nhm.ac.uk/discover/fossil-discovery.html','excerpt':src,'visual':'A cautious scientific reconstruction','caption':'Belegtes Detail'} for _ in range(5)]
  row=production.load(db,jid); row['data']={'sources':[{'url':scenes[0]['source_url'],'text':src}], 'script':{'title':'Test','scenes':scenes},'review':{'supported':True}}; production.save(db,row,'script_ready')
  calls=[]
  def asset(_db,_jid,key,path,payload,dest): calls.append((_jid,key)); Path(dest).parent.mkdir(parents=True,exist_ok=True); Path(dest).write_bytes(b'x'); return Path(dest)
  with patch.object(media,'_asset',side_effect=asset),patch.object(media.render,'_duration',return_value=8),patch.object(media.render,'_bin',return_value='ffmpeg'),patch.object(media.render,'render_scenes',return_value={'video':str(Path(d)/'final.mp4'),'srt':str(Path(d)/'final.srt'),'duration':60,'technical_fixture':False}): result=media.execute(db,jid,Path(d)/'media')
  self.assertEqual(result['state'],'video_ready'); self.assertEqual(len(calls),20); self.assertEqual(len({k for _,k in calls}),20); self.assertTrue(all(x[0]==jid for x in calls)); self.assertEqual(production.load(db,jid)['state'],'video_ready'); db.close()
 def test_model_cache_and_request_change(self):
  d=tempfile.mkdtemp()
  db=production.database(str(Path(d)/'state.sqlite')); jid=production.ingest(db,'https://example.org/model','Model'); row=production.load(db,jid); row['stage']='scoring'; production.save(db,row,'queued'); payload={'stop_reason':'end_turn','usage':{'input_tokens':100,'output_tokens':20},'content':[{'type':'text','text':'{"ok":true}'}]}
  env={'PIPELINE_ALLOW_PAID_CALLS':'1','ANTHROPIC_API_KEY':'x','FOSSILIUM_PAID_TEST_AUTHORIZED':'1','GITHUB_ACTIONS':'false','PIPELINE_UNATTENDED':'0'}
  with patch.dict(os.environ,env),patch.object(production.requests,'post',return_value=type('R',(),{'raise_for_status':lambda s:None,'json':lambda s:payload})()) as post,patch.object(production,'now',return_value='2026-10-19T00:00:00+00:00'):
   first=production.model(db,row,'same',{'x':1}); self.assertEqual(first,{'ok':True}); post.assert_called_once()
  with patch.object(production.requests,'post') as post,patch.object(production,'now',return_value='2026-10-20T00:00:00+00:00'):
   self.assertEqual(production.model(db,row,'same',{'x':1}),{'ok':True}); post.assert_not_called()
  with self.assertRaisesRegex(production.Blocked,'provider_request_changed'): production.model(db,row,'changed',{'x':1})
  self.assertEqual(db.execute("select committed_micro_eur from budget_reservations where operation_key like 'anthropic:%'").fetchone()[0],240); db.close()
if __name__=='__main__': unittest.main()
