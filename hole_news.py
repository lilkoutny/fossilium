"""
Fossilium – Paläo-News-Skript
=============================
Prüft alle RSS-Kandidaten auf den Fossilium-Themenbereich und erstellt
für jede neue relevante Meldung einen eigenen Artikel samt Quellenbelegen.
Feed, Archiv, Publikationsseiten und Retry-Status werden gemeinsam vorbereitet.

Benötigt:  pip install requests feedparser
Umgebung:  ANTHROPIC_API_KEY muss gesetzt sein (bei GitHub als Secret).
"""

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import feedparser
import requests
import news_pipeline

# ------------------------------------------------------------------
# Einstellungen – hier kannst du Quellen ergänzen oder tauschen
# ------------------------------------------------------------------
FEEDS = [
    ("ScienceDaily", "https://www.sciencedaily.com/rss/fossils_ruins/dinosaurs.xml"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/fossils_ruins/paleontology.xml"),
    ("Phys.org", "https://phys.org/rss-feed/biology-news/paleontology/"),
    ("scinexx", "http://feeds.feedburner.com/scinexx"),
    ("Spektrum der Wissenschaft", "https://www.spektrum.de/alias/rss/spektrum-de-rss-feed/996406"),
]
MAX_ALTER_TAGE = 3      # nur Meldungen der letzten X Tage
AUSGABE = "news.json"
ARCHIV = "news-archiv.json"
CROSSREF_API = "https://api.crossref.org/journals/1096-3642/works"

def normalisiere_url(url):
    """Stabile URL für Archiv-Deduplizierung (Tracking-Parameter entfernt)."""
    if not isinstance(url, str):
        return ""
    try:
        p = urlsplit(url.strip())
        if p.scheme.lower() not in ("http", "https") or not p.netloc or p.username or p.password:
            return ""
        tracking = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith(tracking)]
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/",
                           urlencode(query), ""))
    except ValueError:
        return ""

def normalisiere_doi(value):
    """Return a conservative DOI key, or an empty string for non-DOIs."""
    if not isinstance(value, str):
        return ""
    value = unescape(value).strip()
    if re.match(r"^https?://(?:dx\.)?doi\.org/", value, re.I):
        try:
            value = unquote(urlsplit(value).path.lstrip("/"))
        except ValueError:
            return ""
    value = re.sub(r"^doi:\s*", "", value, flags=re.I).strip().rstrip(".,;")
    return value.lower() if re.fullmatch(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", value, re.I) else ""

def _plain_abstract(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"<[^>]+>", " ", unescape(value))
    return re.sub(r"\s+", " ", value).strip()

def hole_journal_kandidaten(today=None):
    """Fetch recent Zoological Journal of the Linnean Society works from Crossref."""
    now = date.fromisoformat(today) if today else datetime.now(timezone.utc).date()
    start = now - timedelta(days=29)
    params = {"filter": f"from-pub-date:{start},until-pub-date:{now.isoformat()},type:journal-article",
              "rows": 100}
    candidates, cursor = {}, "*"
    try:
        for _ in range(3):
            params["cursor"] = cursor
            response = requests.get(CROSSREF_API, params=params, headers={"User-Agent": "FossiliumNews/1.0"}, timeout=(10, 30))
            response.raise_for_status()
            message = response.json()["message"]
            items = message["items"]
            if not isinstance(items, list):
                raise ValueError("Ungültige Crossref-Trefferliste")
            for item in items:
                if not isinstance(item, dict):
                    continue
                doi = normalisiere_doi(item.get("DOI", ""))
                abstract = _plain_abstract(item.get("abstract", ""))
                titles = item.get("title")
                if not isinstance(titles, list):
                    continue
                title = next((x.strip() for x in titles if isinstance(x, str) and x.strip()), "")
                online_date = None
                for key in ("published-online", "published", "issued"):
                    field = item.get(key)
                    if not isinstance(field, dict):
                        continue
                    try:
                        online_date = date(*field["date-parts"][0])
                    except (KeyError, IndexError, TypeError, ValueError):
                        continue
                    break
                if doi and title and len(abstract.split()) >= 20 and online_date and start <= online_date <= now:
                    study_date = online_date.isoformat()
                    candidates.setdefault(doi, {"quelle": "Zoological Journal of the Linnean Society",
                        "titel": title, "url": "https://doi.org/" + doi, "text": abstract,
                        "news_datum": study_date, "study_datum": study_date, "doi": doi,
                        "journal_abstract": True})
            cursor = message.get("next-cursor", "")
            if not cursor or len(items) < params["rows"]:
                break
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"::warning::Crossref-Journal konnte nicht gelesen werden: {type(exc).__name__}")
    return list(candidates.values())

def _valid_news(items):
    fields = ("titel", "zusammenfassung", "quelle", "url", "datum")
    return [dict(item) for item in (items or []) if isinstance(item, dict)
            and all(isinstance(item.get(f), str) and item[f].strip() for f in fields)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["datum"])
            and _valid_date(item["datum"])
            and normalisiere_url(item["url"])]


def _valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def merge_archiv(existing, additions, stand):
    """Add-only merge; first seen metadata/date wins for duplicate URLs."""
    old = existing.get("meldungen", []) if isinstance(existing, dict) else []
    merged, seen = [], set()
    for item in list(old) + list(additions or []):
        valid = _valid_news([item])
        if not valid:
            continue
        item = valid[0]
        key = normalisiere_url(item["url"])
        if key in seen:
            continue
        seen.add(key)
        item["url"] = key
        item.setdefault("erstmals_angezeigt", item.get("datum") or stand)
        merged.append(item)
    merged.sort(key=lambda x: x.get("datum", ""), reverse=True)
    return {"stand": stand, "meldungen": merged}


def sichere_archiv(zusaetzlich=()):
    """Sichert den bisherigen gültigen Feed und neue gültige Meldungen."""
    try:
        with open(ARCHIV, encoding="utf-8") as f:
            archiv = json.load(f)
    except FileNotFoundError:
        archiv = {"meldungen": []}
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Fehler: Archiv ist nicht lesbar: {exc}")
    if (not isinstance(archiv, dict) or not isinstance(archiv.get("meldungen"), list)
            or len(_valid_news(archiv["meldungen"])) != len(archiv["meldungen"])):
        raise SystemExit("Fehler: Das Archiv enthält ungültige Daten und bleibt unverändert.")
    try:
        with open(AUSGABE, encoding="utf-8") as f:
            aktuell = json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        aktuell = {}
    daten = merge_archiv(archiv, list(aktuell.get("meldungen", [])) + list(zusaetzlich),
                         datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    tmp = f"{ARCHIV}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARCHIV)
    return daten


def hole_kandidaten():
    """Every fresh feed entry is reviewed semantically, regardless of source."""
    import calendar
    now = time.time()
    candidates = {}
    for source, url in FEEDS:
        try:
            response = requests.get(url, timeout=(10, 30))
            response.raise_for_status()
            if len(response.content) > 4_000_000:
                raise ValueError("Feed zu groß")
            feed = feedparser.parse(response.content)
            if feed.bozo and not feed.entries:
                raise ValueError("Feed nicht lesbar")
        except Exception as exc:
            print(f"::warning::Feed {source}: {type(exc).__name__}")
            continue
        for entry in feed.entries:
            stamp = entry.get("published_parsed") or entry.get("updated_parsed")
            if stamp and now - calendar.timegm(stamp) > MAX_ALTER_TAGE * 86400:
                continue
            title = entry.get("title", "").strip()
            link = normalisiere_url(entry.get("link", ""))
            text = re.sub(r"<[^>]+>", " ", entry.get("summary", "")).strip()
            if title and link:
                candidates.setdefault(link, {"quelle": source, "titel": title,
                    "url": link, "text": text[:5000] or title,
                    "news_datum": time.strftime("%Y-%m-%d", stamp) if stamp else ""})
    return list(candidates.values())


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Fehler: ANTHROPIC_API_KEY ist nicht gesetzt.")
    candidates = hole_kandidaten()
    if os.environ.get("NEWS_JOURNAL_PILOT") == "1":
        candidates.extend(hole_journal_kandidaten())
    print(f"{len(candidates)} frische Meldungen; zusätzlich werden offene Artikel erneut bearbeitet.")
    limit = int(os.environ.get("NEWS_MAX_ARTICLES", "0"))
    if limit < 0: raise ValueError("NEWS_MAX_ARTICLES muss mindestens 0 sein")
    return news_pipeline.run(candidates, **({"max_articles": limit} if limit else {}))


if __name__ == "__main__":
    main()
