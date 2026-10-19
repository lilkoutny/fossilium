"""Local, paid-free scene renderer and QA. Produces a private MP4 plus SRT."""
import re,shutil,subprocess,tempfile,textwrap
from pathlib import Path
class RenderBlocked(Exception): pass
def _bin():
    ff=shutil.which('ffmpeg')
    if not ff:
        try:
            import imageio_ffmpeg; ff=imageio_ffmpeg.get_ffmpeg_exe()
        except Exception: ff=None
    if not ff: raise RenderBlocked('ffmpeg_missing_install_imageio_ffmpeg_locally')
    return ff
def _run(ff,args,cwd=None): return subprocess.run([ff,*args],capture_output=True,text=True,check=True,cwd=cwd)
def _duration(ff,path):
    p=subprocess.run([ff,'-i',str(path)],capture_output=True,text=True)
    m=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',p.stderr)
    if not m: raise RenderBlocked('audio_or_video_duration_unreadable')
    return int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))
def render_scenes(scenes,out):
    if not isinstance(scenes,list) or not scenes: raise RenderBlocked('media_inputs_missing')
    ff=_bin(); out=Path(out); out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); rendered=[]; srt=[]; cursor=0.0
        for i,s in enumerate(scenes,1):
            audio=s.get('audio'); clips=s.get('video',s.get('clips'))
            if isinstance(clips,(str,Path)): clips=[clips]
            if not clips or not audio: raise RenderBlocked(f'scene_{i}_media_missing')
            adur=_duration(ff,audio); planned=max(float(s.get('seconds',0)),adur)
            if planned<=0: raise RenderBlocked(f'scene_{i}_duration_invalid')
            seg=td/f'scene-{i}.mp4'; concat=td/f'clips-{i}.txt'
            concat.write_text(''.join("file '"+str(Path(c).resolve()).replace("'","'\\''")+"'\n" for c in clips),encoding='utf-8')
            caption_file=td/f'caption-{i}.txt'
            label=(str(s.get('label',''))+' — '+str(s.get('caption',''))).strip(' —')
            caption_file.write_text('\n'.join(textwrap.wrap(label,width=44)),encoding='utf-8')
            # Text stays data even when a caption contains quotes, colons or %{...}.
            vf=f"scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,drawtext=textfile={caption_file.name}:expansion=none:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.6:x=20:y=h-th-30"
            _run(ff,['-f','concat','-safe','0','-i',str(concat),'-i',str(Path(audio).resolve()),'-filter_complex',f'[1:a]apad,atrim=duration={planned:.3f},asetpts=N/SR/TB[a];[0:v]{vf}[v]','-map','[v]','-map','[a]','-t',f'{planned:.3f}','-r','24','-pix_fmt','yuv420p','-c:v','libx264','-c:a','aac','-ar','48000','-ac','2','-y',str(seg)],cwd=td)
            rendered.append(seg); label=s.get('label',''); caption=s.get('caption','')
            if label: caption=(label+' — '+caption).strip(' —')
            start=cursor; end=cursor+planned; cursor=end
            def ts(x):
                h=int(x//3600); m=int((x%3600)//60); sec=x%60; return f'{h:02d}:{m:02d}:{sec:06.3f}'.replace('.',',')
            srt.append(f'{i}\n{ts(start)} --> {ts(end)}\n{caption}\n\n')
        if not 60<=cursor<=90: raise RenderBlocked('total_duration_out_of_range')
        lst=td/'final.txt'; lst.write_text(''.join("file '"+str(x.resolve()).replace("'","'\\''")+"'\n" for x in rendered),encoding='utf-8')
        _run(ff,['-f','concat','-safe','0','-i',str(lst),'-c','copy','-y',str(out)])
    srt_path=out.with_suffix('.srt'); srt_path.write_text(''.join(srt),encoding='utf-8'); dur=_duration(ff,out)
    if not 60<=dur<=90: raise RenderBlocked('render_validation_failed')
    meta=subprocess.run([ff,'-i',str(out)],capture_output=True,text=True).stderr
    for required in ('h264','aac','720x1280','24 fps'):
        if required not in meta: raise RenderBlocked('render_codec_validation_failed:'+required)
    return {'video':str(out),'srt':str(srt_path),'duration':dur,'technical_fixture':False}
