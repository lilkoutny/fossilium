"""Persistent first-test ledger; amounts are integer micro-EUR.
The USD allowance includes FX/tax contingency, not a market exchange rate.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

DEFAULT_LIMIT_MICRO_EUR = 25_000_000
USD_EUR_CEILING = 1.2
PRICE_CHECKED_ON = '2026-10-19'
PRICE_MAX_AGE_DAYS = 30
PRICED_MODELS = {'claude-haiku-4-5-20251001'}
PRICE_SOURCES = [
    'https://platform.claude.com/docs/en/models/haiku-4-5/overview',
    'https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool',
    'https://docs.dev.runwayml.com/guides/pricing/',
]

def _now(): return datetime.now(timezone.utc).isoformat()
def policy():
    return json.loads(Path(__file__).with_name('test-policy.json').read_text(encoding='utf-8'))
def prices_current():
    age = (datetime.now(timezone.utc).date() - datetime.fromisoformat(PRICE_CHECKED_ON).date()).days
    if not 0 <= age <= PRICE_MAX_AGE_DAYS: raise RuntimeError('provider_prices_need_refresh')
def usd_to_micro(usd):
    amount = Decimal(str(usd)) * Decimal(str(USD_EUR_CEILING)) * 1_000_000
    if not amount.is_finite() or amount < 0: raise ValueError('invalid_cost')
    return int(amount.to_integral_value(rounding=ROUND_CEILING))
def ensure(db):
    if db.in_transaction: raise RuntimeError('budget_requires_committed_connection')
    db.executescript("""
      CREATE TABLE IF NOT EXISTS budget_config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS budget_reservations(operation_key TEXT PRIMARY KEY, category TEXT NOT NULL,
        status TEXT NOT NULL,reserved_micro_eur INTEGER NOT NULL,committed_micro_eur INTEGER NOT NULL DEFAULT 0,
        metadata TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
    """)
    limit = Decimal(str(policy()['test_budget_eur'])) * 1_000_000
    if not limit.is_finite() or limit <= 0 or limit != int(limit): raise ValueError('invalid_budget_policy')
    db.execute("INSERT OR IGNORE INTO budget_config VALUES('limit_micro_eur',?)",(str(int(limit)),))
    db.commit()
def _usage(db):
    return db.execute("""SELECT COALESCE(SUM(CASE WHEN status IN ('reserved','uncertain')
      THEN reserved_micro_eur WHEN status='committed' THEN committed_micro_eur ELSE 0 END),0)
      FROM budget_reservations""").fetchone()[0]
def balance(db):
    ensure(db)
    limit = int(db.execute("SELECT value FROM budget_config WHERE key='limit_micro_eur'").fetchone()[0])
    used = _usage(db)
    return dict(limit_micro_eur=limit,used_micro_eur=used,remaining_micro_eur=max(0,limit-used))

def set_limit(db,amount_micro_eur,note):
    """Explicit audited limit update, bounded by the separately saved policy."""
    if type(amount_micro_eur) is not int or amount_micro_eur<=0 or not isinstance(note,str) or not note.strip():
        raise ValueError('budget_change_requires_amount_and_note')
    allowed=Decimal(str(policy()['test_budget_eur']))*1_000_000
    if amount_micro_eur>allowed: raise ValueError('budget_change_exceeds_saved_policy')
    ensure(db)
    db.execute('CREATE TABLE IF NOT EXISTS budget_limit_changes(old_micro_eur INTEGER,new_micro_eur INTEGER,note TEXT,changed TEXT)')
    db.commit();db.execute('BEGIN IMMEDIATE')
    try:
        if amount_micro_eur<_usage(db): raise ValueError('budget_change_below_existing_usage')
        old=int(db.execute("SELECT value FROM budget_config WHERE key='limit_micro_eur'").fetchone()[0])
        db.execute("UPDATE budget_config SET value=? WHERE key='limit_micro_eur'",(str(amount_micro_eur),))
        db.execute('INSERT INTO budget_limit_changes VALUES(?,?,?,?)',(old,amount_micro_eur,note[:500],_now()))
        db.commit()
    except Exception:
        db.rollback();raise
def estimate_micro_eur(input_bytes,output_tokens,*,search=False,overhead_bytes=4096):
    # Byte-per-token upper allowance. Server-search may repeat input processing:
    # for two searches reserve THREE full 200K contexts on the pinned model.
    inputs = max(0,int(input_bytes)) + max(0,int(overhead_bytes))
    outputs = max(0,int(output_tokens))
    if search: inputs=max(inputs,600_000); outputs*=3
    usd = Decimal(inputs)/1_000_000 + Decimal(outputs)*5/1_000_000
    if search: usd+=Decimal('0.02')
    return usd_to_micro(usd)
def actual_anthropic_micro(usage,*,search=False):
    if not isinstance(usage,dict) or not {'input_tokens','output_tokens'} <= usage.keys():
        raise ValueError('provider_usage_missing')
    def count(key):
        n=usage.get(key,0)
        if type(n) is not int or n<0: raise ValueError('provider_usage_invalid')
        return n
    if count('cache_read_input_tokens') or count('cache_creation_input_tokens'):
        raise ValueError('unexpected_cache_usage')
    tools=usage.get('server_tool_use') or {}
    if not isinstance(tools,dict): raise ValueError('provider_usage_invalid')
    searches=tools.get('web_search_requests',0)
    if type(searches) is not int or not 0<=searches<=(2 if search else 0):
        raise ValueError('provider_usage_invalid')
    return usd_to_micro(Decimal(count('input_tokens'))/1_000_000 +
                        Decimal(count('output_tokens'))*5/1_000_000 + Decimal(searches)/100)
def reserve(db,operation_key,category,amount_micro_eur,metadata=None):
    if not operation_key or type(amount_micro_eur) is not int or amount_micro_eur<=0:
        raise ValueError('invalid_budget_reservation')
    ensure(db); stamp=_now(); serialized=json.dumps(metadata or {},ensure_ascii=False,sort_keys=True)
    db.execute('BEGIN IMMEDIATE')
    try:
        suspended=db.execute("SELECT value FROM budget_config WHERE key='suspended'").fetchone()
        if suspended: raise RuntimeError('budget_suspended')
        old=db.execute('SELECT * FROM budget_reservations WHERE operation_key=?',(operation_key,)).fetchone()
        if old: raise RuntimeError('operation_key_exists:'+old['status'])
        limit=int(db.execute("SELECT value FROM budget_config WHERE key='limit_micro_eur'").fetchone()[0])
        if _usage(db)+amount_micro_eur>limit: raise RuntimeError('budget_exceeded')
        db.execute('INSERT INTO budget_reservations VALUES(?,?,?,?,?,?,?,?)',
          (operation_key,category,'reserved',amount_micro_eur,0,serialized,stamp,stamp)); db.commit()
        return dict(db.execute('SELECT * FROM budget_reservations WHERE operation_key=?',(operation_key,)).fetchone())
    except Exception:
        db.rollback(); raise
def settle(db,operation_key,status,actual_micro_eur=0):
    if status not in ('committed','uncertain','released'): raise ValueError('invalid_budget_status')
    if type(actual_micro_eur) is not int or actual_micro_eur<0: raise ValueError('invalid_actual_cost')
    ensure(db); db.execute('BEGIN IMMEDIATE')
    try:
        row=db.execute('SELECT * FROM budget_reservations WHERE operation_key=?',(operation_key,)).fetchone()
        if not row: raise KeyError(operation_key)
        if row['status']!='reserved':
            if row['status']==status and row['committed_micro_eur']==actual_micro_eur:
                db.commit(); return
            raise RuntimeError('reservation_already_settled')
        if status=='committed' and actual_micro_eur>row['reserved_micro_eur']:
            raise RuntimeError('actual_cost_exceeds_reservation')
        db.execute('UPDATE budget_reservations SET status=?,committed_micro_eur=?,updated=? WHERE operation_key=?',
                   (status,actual_micro_eur,_now(),operation_key)); db.commit()
    except Exception:
        db.rollback(); raise
