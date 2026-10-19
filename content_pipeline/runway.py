"""Budgeted Runway REST adapter. Paid POSTs are never retried automatically."""
import hashlib
import json
import math
import os
import re
from pathlib import Path
import requests
from . import budget

BASE = 'https://api.dev.runwayml.com'
VERSION = '2024-11-06'
class RunwayBlocked(Exception): pass

def _headers():
    key = os.getenv('RUNWAYML_API_SECRET')
    if not key: raise RunwayBlocked('runway_credentials_missing')
    return {'Authorization':'Bearer '+key,'X-Runway-Version':VERSION,'Content-Type':'application/json'}

def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def ensure(db):
    db.execute('''CREATE TABLE IF NOT EXISTS media_tasks(operation_key TEXT PRIMARY KEY,
      request_digest TEXT NOT NULL,task_id TEXT,status TEXT NOT NULL,credits INTEGER NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS media_outputs(operation_key TEXT PRIMARY KEY,
      output_json TEXT NOT NULL,local_path TEXT)''')
    db.commit()
    budget.ensure(db)

def _get(path):
    try:
        r=requests.get(BASE+path,headers=_headers(),timeout=(10,30),allow_redirects=False)
        r.raise_for_status()
        if not 200<=r.status_code<300: raise RunwayBlocked('runway_redirect_rejected')
        result=r.json()
        if not isinstance(result,dict): raise RunwayBlocked('runway_response_invalid')
        return result
    except requests.RequestException as exc:
        status=getattr(getattr(exc,'response',None),'status_code',None)
        raise RunwayBlocked('runway_http_'+str(status) if status else 'runway_connection_failed') from None

def organization(): return _get('/v1/organization')
def task(task_id):
    if not isinstance(task_id,str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}',task_id):
        raise RunwayBlocked('runway_task_id_invalid')
    return _get('/v1/tasks/'+task_id)

def credits_for(path,payload):
    model=payload.get('model')
    if path=='/v1/text_to_image' and model=='gen4_image':
        if payload.get('ratio')!='720:1280' or payload.get('outputCount',1)!=1:
            raise RunwayBlocked('unpriced_image_settings')
        return 5
    if path=='/v1/image_to_video' and model=='gen4_turbo':
        duration=payload.get('duration')
        if type(duration) is not int or duration not in (5,10) or payload.get('ratio')!='720:1280':
            raise RunwayBlocked('unpriced_video_settings')
        return 5*duration
    if path=='/v1/text_to_speech' and model=='eleven_v4':
        text=payload.get('promptText','')
        if not isinstance(text,str) or not text.strip() or len(text.encode('utf-16-le'))//2>2500:
            raise RunwayBlocked('invalid_speech_text')
        if not isinstance(payload.get('voice'),dict) or payload.get('languageCode')!='de':
            raise RunwayBlocked('invalid_speech_settings')
        return max(1,math.ceil((len(text.encode('utf-16-le'))//2)*5/1000))
    raise RunwayBlocked('unknown_model_price')

def submit(db,operation_key,path,payload,credits=None):
    ensure(db)
    calculated=credits_for(path,payload)
    if credits is not None and credits!=calculated: raise RunwayBlocked('credit_estimate_mismatch')
    d=digest({'path':path,'payload':payload})
    existing=db.execute('SELECT * FROM media_tasks WHERE operation_key=?',(operation_key,)).fetchone()
    if existing:
        if existing['request_digest']!=d: raise RunwayBlocked('media_request_changed')
        if existing['task_id']: return dict(existing)
        raise RunwayBlocked('paid_outcome_unknown')
    _headers()  # Missing login must not consume a reservation.
    if os.getenv('RUNWAY_EXECUTE')!='1' or not budget.policy().get('paid_test_authorized'):
        raise RunwayBlocked('runway_execute_gate')
    if (os.getenv('GITHUB_ACTIONS')=='true' or os.getenv('PIPELINE_UNATTENDED')=='1') and not budget.policy().get('paid_automation_enabled'):
        raise RunwayBlocked('paid_automation_not_enabled')
    try: budget.prices_current()
    except RuntimeError as exc: raise RunwayBlocked(str(exc))
    org=organization()
    if type(org.get('creditBalance')) is not int or org['creditBalance']<calculated:
        raise RunwayBlocked('runway_credits_missing')
    models=org.get('tier',{}).get('models',{})
    if payload['model'] not in models: raise RunwayBlocked('runway_model_unavailable')
    amount=budget.usd_to_micro(calculated/100)
    key='runway:'+operation_key
    try:
        budget.reserve(db,key,'voice' if path.endswith('speech') else 'video',amount,
          {'provider':'runway','model':payload['model'],'credits':calculated,
           'request_hash':d,'price_date':budget.PRICE_CHECKED_ON})
    except RuntimeError as exc: raise RunwayBlocked(str(exc))
    db.execute('INSERT INTO media_tasks VALUES(?,?,?,?,?)',(operation_key,d,None,'reserved',calculated))
    db.commit()  # Crash after here, before recording an ID: block instead of resubmit.
    try:
        r=requests.post(BASE+path,headers=_headers(),json=payload,timeout=(10,60),allow_redirects=False)
        r.raise_for_status()
        if not 200<=r.status_code<300: raise RunwayBlocked('runway_redirect_rejected')
        result=r.json()
        task_id=result.get('id') if isinstance(result,dict) else None
        if not isinstance(task_id,str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}',task_id):
            raise RunwayBlocked('runway_task_id_missing')
    except Exception:
        budget.settle(db,key,'uncertain')
        db.execute('UPDATE media_tasks SET status=? WHERE operation_key=?',('uncertain',operation_key));db.commit()
        raise RunwayBlocked('runway_submit_outcome_uncertain') from None
    # Persist ID before settlement so every subsequent invocation can poll safely.
    db.execute('UPDATE media_tasks SET task_id=?,status=? WHERE operation_key=?',(task_id,'submitted',operation_key));db.commit()
    budget.settle(db,key,'committed',amount)  # Conservatively charge scheduled full cost, including failed tasks.
    return dict(db.execute('SELECT * FROM media_tasks WHERE operation_key=?',(operation_key,)).fetchone())

def poll(db,operation_key):
    row=db.execute('SELECT * FROM media_tasks WHERE operation_key=?',(operation_key,)).fetchone()
    if not row or not row['task_id']: raise RunwayBlocked('paid_outcome_unknown')
    result=task(row['task_id'])
    estimated=result.get('estimatedCost',{}).get('credits')
    if estimated is not None and estimated>row['credits']:
        db.execute("INSERT OR REPLACE INTO budget_config VALUES('suspended','provider_price_changed')");db.commit()
        raise RunwayBlocked('provider_price_changed')
    state=result.get('status')
    if state in ('FAILED','CANCELED'): raise RunwayBlocked('runway_task_failed')
    if state!='SUCCEEDED': return None
    urls=result.get('output')
    if not isinstance(urls,list) or not urls or not all(isinstance(u,str) and u.startswith('https://') for u in urls):
        raise RunwayBlocked('runway_output_invalid')
    db.execute('INSERT OR REPLACE INTO media_outputs(operation_key,output_json,local_path) VALUES(?,?,COALESCE((SELECT local_path FROM media_outputs WHERE operation_key=?),NULL))',
               (operation_key,json.dumps(urls),operation_key))
    db.execute('UPDATE media_tasks SET status=? WHERE operation_key=?',('complete',operation_key));db.commit()
    return urls

def download(db,operation_key,destination):
    row=db.execute('SELECT * FROM media_outputs WHERE operation_key=?',(operation_key,)).fetchone()
    path=Path(destination)
    if path.is_file() and row and row['local_path']==str(path.resolve()): return path
    if not row: raise RunwayBlocked('runway_output_not_ready')
    # Output is private provider data. Never send the API Authorization header to an asset host.
    from .production import public
    url=json.loads(row['output_json'])[0]
    for _ in range(5):
        if not public(url): raise RunwayBlocked('asset_url_rejected')
        with requests.get(url,timeout=(10,90),stream=True,allow_redirects=False) as response:
            if 300<=response.status_code<400:
                from urllib.parse import urljoin
                url=urljoin(url,response.headers.get('Location',''));continue
            response.raise_for_status();path.parent.mkdir(parents=True,exist_ok=True)
            tmp=path.with_suffix(path.suffix+'.part');size=0
            try:
                with tmp.open('wb') as f:
                    for chunk in response.iter_content(65536):
                        size+=len(chunk)
                        if size>250_000_000: raise RunwayBlocked('asset_too_large')
                        f.write(chunk)
                if not size: raise RunwayBlocked('asset_empty')
                tmp.replace(path)
            finally:
                if tmp.exists(): tmp.unlink()
            db.execute('UPDATE media_outputs SET local_path=? WHERE operation_key=?',(str(path.resolve()),operation_key));db.commit()
            return path
    raise RunwayBlocked('asset_redirect_limit')
