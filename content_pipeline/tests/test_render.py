import tempfile,unittest,subprocess
from pathlib import Path
from content_pipeline.render import render_scenes,RenderBlocked
class RenderTests(unittest.TestCase):
 def test_missing_media_blocks(self):
  with self.assertRaises(RenderBlocked): render_scenes([{'seconds':60}],Path(tempfile.gettempdir())/'x.mp4')
 def test_real_fixture_render(self):
  try: import imageio_ffmpeg
  except ImportError: self.skipTest('imageio-ffmpeg missing')
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); ff=imageio_ffmpeg.get_ffmpeg_exe(); audio=d/'tone.wav'; clips=[]
   for i,c in enumerate(['blue','green','red','yellow','purple']):
    f=d/f'{i}.mp4'; subprocess.run([ff,'-f','lavfi','-i',f'color=c={c}:s=320x568:d=12','-t','12','-y',str(f)],check=True,capture_output=True); clips.append(f)
   subprocess.run([ff,'-f','lavfi','-i','sine=frequency=440:duration=8','-ar','48000','-ac','2','-y',str(audio)],check=True,capture_output=True)
   scenes=[{'video':[x],'audio':audio,'seconds':12,'caption':"Dino's: Größe %{localtime}",'label':'Technischer Test' if i==0 else ''} for i,x in enumerate(clips)]
   result=render_scenes(scenes,d/'fixture.mp4'); self.assertTrue(Path(result['video']).exists()); self.assertTrue(Path(result['srt']).exists()); self.assertTrue(60<=result['duration']<=90)
   qa=Path('content_pipeline/output/render-qa'); qa.mkdir(parents=True,exist_ok=True); (qa/'technical-fixture.mp4').write_bytes(Path(result['video']).read_bytes()); (qa/'technical-fixture.srt').write_text(Path(result['srt']).read_text(encoding='utf-8'),encoding='utf-8'); (qa/'technical-fixture.json').write_text('{"technical_fixture":true,"duration":60,"paid":false}',encoding='utf-8')
if __name__=='__main__': unittest.main()
