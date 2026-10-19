"""Local production entry point. Defaults to a free, read-only plan."""
import argparse
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from . import budget, media, production, runway, render

def state_dir():
    if os.getenv('FOSSILIUM_STATE_DIR'): return Path(os.environ['FOSSILIUM_STATE_DIR']).expanduser().resolve()
    return Path(os.getenv('LOCALAPPDATA',str(Path.home()/'.local/share')))/'Fossilium'

def run(db_path=None,news_json=None,execute=False,watch=False):
    root=state_dir();root.mkdir(parents=True,exist_ok=True)
    path=Path(db_path) if db_path else root/'production.sqlite'
    db=production.database(str(path))
    try:
        media.ensure(db)
        if news_json:
            feed=json.loads(Path(news_json).read_text(encoding='utf-8'))
            items=feed if isinstance(feed,list) else feed.get('meldungen',[])
            if not isinstance(items,list): raise ValueError('invalid_news_feed')
            for item in items[:100]:
                if isinstance(item,dict) and isinstance(item.get('url'),str) and production.public(item['url']):
                    production.ingest(db,item['url'],str(item.get('titel','')))
        jobs=[production.load(db,row['id']) for row in db.execute('SELECT id FROM work ORDER BY updated')]
        report={'mode':'dry_plan','budget':budget.balance(db),
                'credentials_present':{'research':bool(os.getenv('ANTHROPIC_API_KEY')),
                                       'media':bool(os.getenv('RUNWAYML_API_SECRET'))},
                'jobs':[{'title':j['title'],'state':j['state'],'stage':j['stage'],'reason':j['reason'],
                         'media_plan':media.cost_plan(j['data']['script']) if j['data'].get('script') else None}
                        for j in jobs],
                'automatic_social_posting':False}
        if not execute: return report
        if not budget.policy().get('paid_test_authorized'): return dict(report,mode='blocked',reason='paid_test_not_authorized')
        if os.getenv('GITHUB_ACTIONS')=='true' or os.getenv('PIPELINE_UNATTENDED')=='1':
            if not budget.policy().get('paid_automation_enabled'):
                return dict(report,mode='blocked',reason='paid_automation_not_enabled')
        # --execute is the explicit manual run, not an automated daily toggle.
        os.environ['PIPELINE_ALLOW_PAID_CALLS']='1'
        os.environ['RUNWAY_EXECUTE']='1'
        # Preflight all external access before charging for any research.
        missing=[name for name,present in report['credentials_present'].items() if not present]
        if missing: return dict(report,mode='blocked',reason='provider_credentials_missing',missing=missing)
        render._bin()
        org=runway.organization()
        if not org.get('creditBalance'): return dict(report,mode='blocked',reason='runway_credits_missing')
        budget.prices_current()
        candidates=[j for j in jobs if j['state'] not in ('skipped','video_ready')]
        if not candidates: return dict(report,mode='idle')
        job=candidates[0]  # The first test is exactly one complete story.
        if job['state']!='script_ready':
            job=production.process(db,job['id'],retry=True)
            if job['state']!='script_ready':
                return dict(report,mode='blocked',reason=job['reason'],stage=job['stage'])
        started=time.monotonic()
        while True:
            result=media.execute(db,job['id'],root/'media')
            if result['state']!='pending' or not watch: return dict(mode='manual_test',result=result,budget=budget.balance(db))
            if time.monotonic()-started>1800:
                return dict(mode='pending',reason='watch_timeout_resume_same_job',budget=budget.balance(db))
            time.sleep(10)
    finally: db.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db')
    p.add_argument('--news-json')
    p.add_argument('--execute',action='store_true',help='Run one authorized paid test, subject to the persisted overall budget')
    p.add_argument('--watch',action='store_true',help='Poll pending tasks; never resubmit them')
    p.add_argument('--set-budget-limit-eur',type=Decimal,help='Explicit update within the saved policy; never resets expenses')
    p.add_argument('--budget-note',default='',help='Reason for an authorized budget-limit update')
    args=p.parse_args()
    try:
        if args.set_budget_limit_eur is not None:
            amount=args.set_budget_limit_eur*1_000_000
            if not amount.is_finite() or amount!=int(amount): raise ValueError('invalid_budget_amount')
            db=production.database(str(Path(args.db) if args.db else state_dir()/'production.sqlite'))
            try:
                budget.set_limit(db,int(amount),args.budget_note)
                result={'mode':'budget_updated','budget':budget.balance(db)}
            finally: db.close()
        else:
            result=run(args.db,args.news_json,args.execute,args.watch)
    except (runway.RunwayBlocked,render.RenderBlocked,production.Blocked,RuntimeError,ValueError) as exc:
        result={'mode':'blocked','reason':str(exc)}
    except Exception:
        result={'mode':'blocked','reason':'local_technical_error'}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
