"""Resumeable private media production from an already verified research job."""
import base64
import json
import math
from pathlib import Path
from . import budget, production, runway, render

def ensure(db):
    runway.ensure(db)
    db.execute('''CREATE TABLE IF NOT EXISTS media_jobs(job_id TEXT PRIMARY KEY,
      fingerprint TEXT NOT NULL,status TEXT NOT NULL,output_dir TEXT NOT NULL,data TEXT NOT NULL)''')
    db.commit()

def plan(script):
    if not isinstance(script,dict) or not isinstance(script.get('scenes'),list):
        raise ValueError('script_required')
    return [{'index':i,'narration':s['narration'],'seconds':s['seconds'],
             'source_url':s.get('source_url'),'kind':'reconstruction',
             'caption':s.get('caption','')} for i,s in enumerate(script['scenes'])]

def cost_plan(script):
    scenes=plan(script)
    # Two 10s clips per scene cover any allowed <=20s scene. Actual narration is
    # measured before creating visual assets. This plan intentionally overestimates.
    credits=sum(5+100+max(1,math.ceil(len(s['narration'].encode('utf-16-le'))/2*5/1000)) for s in scenes)
    return {'media_credits_ceiling':credits,
            'media_allowance_micro_eur':budget.usd_to_micro(credits/100),
            'price_checked':budget.PRICE_CHECKED_ON,
            'research_in_same_envelope':True}

def _asset(db,jid,key,path,payload,destination):
    op=jid+':'+key
    runway.submit(db,op,path,payload)
    if not runway.poll(db,op): return None
    return runway.download(db,op,destination)

def _image_uri(path):
    # Reuse completed local frames without expiring signed URLs.
    data=Path(path).read_bytes()
    if len(data)>3_800_000: raise runway.RunwayBlocked('reference_image_too_large')
    return 'data:image/png;base64,'+base64.b64encode(data).decode('ascii')

def execute(db,jid,output_root):
    ensure(db)
    job=production.load(db,jid)
    data=job['data']
    if not data.get('review',{}).get('supported') or not data.get('script'):
        raise runway.RunwayBlocked('verified_script_required')
    script=production.validate_script(data['script'],data.get('sources',[]))
    fingerprint=runway.digest({'script':script,'sources':data.get('sources',[]),
                              'voice':'Martin','pipeline':'media-v1'})
    existing=db.execute('SELECT * FROM media_jobs WHERE job_id=?',(jid,)).fetchone()
    if existing and existing['fingerprint']!=fingerprint:
        raise runway.RunwayBlocked('media_script_changed')
    root=(Path(output_root)/jid).resolve()
    if existing:
        if Path(existing['output_dir'])!=root: raise runway.RunwayBlocked('media_output_directory_changed')
        manifest=json.loads(existing['data'])
        if existing['status']=='ready':
            if not Path(manifest.get('video','')).is_file(): raise runway.RunwayBlocked('completed_video_missing')
            return {'state':'video_ready','manifest':manifest}
    else:
        render._bin()  # Local preflight before any paid request.
        info=cost_plan(script);remaining=budget.balance(db)['remaining_micro_eur']
        if info['media_allowance_micro_eur']>remaining:
            raise runway.RunwayBlocked('media_budget_preflight_failed')
        root.mkdir(parents=True,exist_ok=True)
        manifest={'job_id':jid,'technical_fixture':False,'scientific_visual_review':'pending',
                  'sources':[{'url':s['url']} for s in data.get('sources',[])],
                  'rights':{'original_generated_assets':True,'third_party_artwork_used':False,
                           'terms_source':'https://help.runwayml.com/hc/en-us/articles/18927776141715-Usage-rights',
                           'terms_checked':'2026-10-19'},
                  'reconstruction_notice':'KI-Rekonstruktion: Aussehen und Bewegung sind keine Fossilbefunde.'}
        db.execute('INSERT INTO media_jobs VALUES(?,?,?,?,?)',(jid,fingerprint,'running',str(root),json.dumps(manifest)))
        db.commit()
    voices=[];durations=[]
    # All voices first: a script that speaks for >90s never buys visual footage.
    for i,s in enumerate(script['scenes']):
        payload={'model':'eleven_v4','promptText':s['narration'],'languageCode':'de',
                 'voice':{'type':'runway-preset','presetId':'Martin'},'speed':1.0}
        audio=_asset(db,jid,f'voice:{i}','/v1/text_to_speech',payload,root/f'voice-{i}.mp3')
        if audio is None: return {'state':'pending','stage':'voice','scene':i+1}
        voices.append(audio)
        seconds=max(float(s['seconds']),render._duration(render._bin(),audio))
        if seconds>20: raise runway.RunwayBlocked('spoken_scene_too_long')
        durations.append(seconds)
    if not 60<=sum(durations)<=90: raise runway.RunwayBlocked('spoken_video_duration_out_of_range')
    style=('Cinematic natural history documentary illustration, coherent lighting and visual design. '
           'Scientifically cautious reconstruction, no text, no logos, no humans, no fantasy anatomy. '
           'Use subdued natural colours. Do not present imagined details as fossil observations. ')
    scenes=[];anchor=None
    for i,s in enumerate(script['scenes']):
        direction=s.get('visual','')
        if not isinstance(direction,str) or not direction.strip():
            raise runway.RunwayBlocked('visual_direction_required')
        payload={'model':'gen4_image','ratio':'720:1280','promptText':(style+direction)[:1000]}
        if anchor: payload['referenceImages']=[{'uri':_image_uri(anchor),'tag':'style_ref'}]
        image=_asset(db,jid,f'image:{i}','/v1/text_to_image',payload,root/f'image-{i}.png')
        if image is None: return {'state':'pending','stage':'image','scene':i+1}
        if anchor is None: anchor=image
        clips=[]
        for n in range(math.ceil(durations[i]/10)):
            video_payload={'model':'gen4_turbo','ratio':'720:1280','duration':10,
                           'promptImage':_image_uri(image),
                           'promptText':'A slow cinematic camera move through this scientific illustration. Gentle ambient motion. Preserve the established subject shape, proportions, background and lighting. No morphing, no added objects, no text.'}
            clip=_asset(db,jid,f'clip:{i}:{n}','/v1/image_to_video',video_payload,root/f'clip-{i}-{n}.mp4')
            if clip is None: return {'state':'pending','stage':'video','scene':i+1}
            clips.append(clip)
        scenes.append({'clips':clips,'audio':voices[i],'seconds':durations[i],
                       'caption':s.get('caption',''),'label':'KI-Rekonstruktion'})
    result=render.render_scenes(scenes,root/'fossilium-preview.mp4')
    manifest.update(result)
    manifest['technical_fixture']=False
    manifest['release_status']='preview_requires_visual_review'
    manifest['budget']=budget.balance(db)
    tmp=root/'manifest.tmp'
    tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(root/'manifest.json')
    db.execute('UPDATE media_jobs SET status=?,data=? WHERE job_id=?',('ready',json.dumps(manifest,ensure_ascii=False),jid));db.commit()
    job['data']['media']={'preview_ready':True,'scientific_visual_review':'pending'}
    production.save(db,job,'video_ready','visual_review_pending')
    return {'state':'video_ready','manifest':manifest}
