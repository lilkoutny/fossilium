#!/usr/bin/env python3
"""Deterministic static renderer for publication articles."""
import argparse, html, json, re, sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent; DATA=ROOT/'artikel.json'; CSS='artikel.css'; BASE='https://fossilium.org/publikationen/'
def esc(x): return html.escape(str(x), quote=True)
def url_ok(u):
    try:
        p=urlparse(str(u)); return p.scheme in ('http','https') and not p.username and not p.password and bool(p.hostname)
    except ValueError:
        return False
def datum(value):
    try: return date.fromisoformat(value).strftime('%d.%m.%Y')
    except (ValueError, TypeError): return str(value)
def validate(data):
    if not isinstance(data,dict) or not isinstance(data.get('artikel'),list): raise ValueError('artikel fehlt')
    slugs=set(); originals=set()
    for a in data['artikel']:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',a.get('slug','')): raise ValueError('ungültiger slug')
        if a['slug'] in slugs or a.get('original_url') in originals: raise ValueError('doppelter Artikel')
        slugs.add(a['slug']); originals.add(a.get('original_url'))
        for k in ('titel','untertitel','datum','news_datum','study_datum','lesestand','original_quelle'):
            if not isinstance(a.get(k),str) or not a[k].strip(): raise ValueError('Textfeld fehlt: '+k)
        for k in ('original_url',):
            if not url_ok(a.get(k,'')): raise ValueError('ungültige URL: '+k)
        ids={q.get('id') for q in a.get('quellen',[])}
        if not ids or len(ids)!=len(a['quellen']): raise ValueError('Quellen fehlen oder doppelte Quellen-ID')
        for q in a.get('quellen',[]):
            if not re.fullmatch(r'S[1-9][0-9]*',q.get('id','')) or not url_ok(q.get('url','')): raise ValueError('ungültige Quelle')
        if not a.get('abschnitte'): raise ValueError('Artikeltext fehlt')
        for s in a.get('abschnitte',[]):
            if not isinstance(s.get('titel'),str) or not isinstance(s.get('absatz'),list) or not s['absatz'] or not all(isinstance(p,str) and p.strip() for p in s['absatz']): raise ValueError('ungültiger Abschnitt')
            if any(x not in ids for x in s.get('quellen',[])): raise ValueError('unbekannte Quellen-ID')
        for b in a.get('bilder',[]):
            rel=b.get('datei',''); p=(ROOT/rel).resolve()
            if not re.fullmatch(r'assets/[a-z0-9][a-z0-9.-]*\.(png|jpg|webp|svg)',rel) or not p.is_relative_to((ROOT/'assets').resolve()) or not p.is_file(): raise ValueError('ungültiger Bildpfad')
            if not all(isinstance(b.get(k),str) and b[k].strip() for k in ('alt','beschreibung','credit','lizenz')) or not url_ok(b.get('lizenz_url','')) or not url_ok(b.get('quelle_url','')): raise ValueError('Bildlizenz/-nachweis fehlt')
def render(a):
    slug=a['slug']; nav=''.join(f'<li><a href="#abschnitt-{i}">{esc(s.get("titel",""))}</a></li>' for i,s in enumerate(a.get('abschnitte',[]),1))
    sections=''.join(f'<section id="abschnitt-{i}"><h2>{esc(s.get("titel",""))}</h2>'+''.join(f'<p>{esc(p)}</p>' for p in s.get('absatz',[]))+(' <small>Quellen: '+', '.join(f'<a href="#quelle-{esc(x)}">{esc(x)}</a>' for x in s.get('quellen',[]))+'</small>' if s.get('quellen') else '')+'</section>' for i,s in enumerate(a.get('abschnitte',[]),1))
    figs=''.join(f'<figure><a href="../{esc(b["datei"])}" target="_blank" rel="noopener noreferrer"><img loading="lazy" src="../{esc(b["datei"])}" alt="{esc(b.get("alt",""))}"></a><figcaption>{esc(b.get("beschreibung",""))} · {esc(b.get("credit",""))} · <a href="{esc(b["lizenz_url"])}">{esc(b.get("lizenz","Lizenz"))}</a> · <a href="{esc(b["quelle_url"])}">Quelle</a></figcaption></figure>' for b in a.get('bilder',[]))
    nums=''.join(f'<div class="kennzahl"><strong>{esc(n.get("wert",""))}</strong>{esc(n.get("label",""))}</div>' for n in a.get('kennzahlen',[]))
    qs=''.join(f'<li id="quelle-{esc(q["id"])}"><a href="{esc(q["url"])}">{esc(q.get("titel",q["id"]))}</a> ({esc(q.get("umfang",""))})</li>' for q in a.get('quellen',[]))
    return f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(a["titel"])} · Fossilium</title><meta name="description" content="{esc(a.get("untertitel",a["titel"]))}"><link rel="canonical" href="{BASE}{slug}/"><link rel="stylesheet" href="../artikel.css"></head><body><main><a class="zurueck" href="/#forschung">‹ Zurück zur Forschung</a><article><p class="kicker">Fossilium · Publikation</p><h1>{esc(a["titel"])}</h1><p class="lead">{esc(a.get("untertitel",""))}</p><div class="daten"><span>Auf Fossilium: {esc(datum(a.get("datum","")))}</span><span>Meldung: {esc(datum(a.get("news_datum","")))}</span><span>Studie: {esc(datum(a.get("study_datum","")))}</span></div><nav class="nav"><strong>Inhalt</strong><ol>{nav}</ol></nav>{figs}<div class="kennzahlen">{nums}</div>{sections}<p class="hinweis">Lesestand: {esc(a.get("lesestand",""))}</p><section class="quellen"><h2>Quellen</h2><ol>{qs}<li><a href="{esc(a["original_url"])}">Originalartikel: {esc(a.get("original_quelle",a["original_url"]))}</a></li></ol></section></article></main></body></html>'
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    if not DATA.exists(): print('artikel.json fehlt',file=sys.stderr); return 2
    data=json.loads(DATA.read_text(encoding='utf-8')); validate(data)
    manifest={'artikel':[]}
    for a in data['artikel']:
        out=ROOT/a['slug']/ 'index.html'; content=render(a); manifest['artikel'].append({'original_url':a['original_url'],'pfad':'/publikationen/'+a['slug']+'/','titel':a['titel']})
        if args.check:
            if not out.is_file() or out.read_text(encoding='utf-8')!=content: return 1
        else: out.parent.mkdir(parents=True,exist_ok=True); out.write_text(content,encoding='utf-8')
    m=ROOT/'index.json'; raw=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
    if args.check: return 0 if m.is_file() and m.read_text(encoding='utf-8')==raw else 1
    m.write_text(raw,encoding='utf-8'); return 0
if __name__=='__main__': raise SystemExit(main())
