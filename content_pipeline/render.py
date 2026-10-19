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
def _caption_png(path, text):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RenderBlocked('pillow_missing_install_isolated') from exc
    image=Image.new('RGBA',(720,1280),(0,0,0,0)); draw=ImageDraw.Draw(image)
    font=None
    for candidate in ('Arial.ttf','DejaVuSans.ttf'):
        try: font=ImageFont.truetype(candidate,26); break
        except OSError: pass
    if font is None: font=ImageFont.load_default(size=26)
    lines=textwrap.wrap(text,width=44) or ['']
    heights=[draw.textbbox((0,0),line,font=font)[3] for line in lines]
    line_h=max(heights+[26])+8; box_h=line_h*len(lines)+28; top=1280-box_h-24
    draw.rounded_rectangle((16,top,704,1272),radius=12,fill=(0,0,0,170))
    y=top+14
    for line in lines:
        draw.text((30,y),line,font=font,fill=(255,255,255,255),stroke_width=1,stroke_fill=(0,0,0,255)); y+=line_h
    image.save(path)
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
            label=(str(s.get('label',''))+' — '+str(s.get('caption',''))).strip(' —')
            caption_png=td/f'caption-{i}.png'; _caption_png(caption_png,label)
            # Caption is a data PNG; no ffmpeg expression parsing is involved.
            filt=f'[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280[base];[2:v]scale=720:1280[cap];[base][cap]overlay=0:0[v];[1:a]apad,atrim=duration={planned:.3f},asetpts=N/SR/TB[a]'
            _run(ff,['-f','concat','-safe','0','-i',str(concat),'-i',str(Path(audio).resolve()),'-loop','1','-i',str(caption_png),'-filter_complex',filt,'-map','[v]','-map','[a]','-t',f'{planned:.3f}','-r','24','-pix_fmt','yuv420p','-c:v','libx264','-c:a','aac','-ar','48000','-ac','2','-y',str(seg)],cwd=td)
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
