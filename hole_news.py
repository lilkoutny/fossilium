"""
Fossilium – Paläo-News-Skript
=============================
Holt aktuelle Paläontologie-Meldungen aus RSS-Feeds, lässt sie von der
Claude API auf Deutsch zusammenfassen und schreibt das Ergebnis in
news.json, die von der Startseite geladen wird.

Benötigt:  pip install requests feedparser
Umgebung:  ANTHROPIC_API_KEY muss gesetzt sein (bei GitHub als Secret).
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import requests

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
MAX_KANDIDATEN = 20     # so viele Artikel bekommt die KI maximal zu sehen
MODELL = "claude-haiku-4-5"  # günstigstes Modell, reicht fürs Zusammenfassen
AUSGABE = "news.json"
ARCHIV = "news-archiv.json"

# scinexx und Spektrum liefern nur allgemeine Wissenschafts-Feeds (keine
# eigenen Paläo-Feeds) – deshalb werden ihre Einträge hier nach Stichwort
# gefiltert, damit keine fachfremden Themen (Physik, Medizin, Technik, ...)
# ins Dino-Lexikon rutschen.
PALAEO_STICHWORTE = (
    "dino", "saurier", "fossil", "paläontolog", "palaeontolog",
    "urzeit", "kreidezeit", "jurazeit", "jura-zeit", "trias",
    "versteinert", "prähistorisch", "praehistorisch", "ausgrabung",
    "jurassic", "cretaceous", "triassic", "prehistoric", "paleontolog",
)
FEEDS_OHNE_FILTER = {"ScienceDaily", "Phys.org"}  # schon themenspezifisch


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


def ist_palaeo_relevant(quelle, titel, text):
    """scinexx/Spektrum sind Breitband-Feeds – hier auf Dino/Fossil-Themen
    eingrenzen. Die bereits paläo-spezifischen Feeds laufen ungefiltert durch."""
    if quelle in FEEDS_OHNE_FILTER:
        return True
    haystack = f"{titel} {text}".lower()
    return any(wort in haystack for wort in PALAEO_STICHWORTE)


def hole_kandidaten():
    """Sammelt frische, paläo-relevante Einträge aus allen Feeds."""
    jetzt = time.time()
    kandidaten = []
    for quelle, url in FEEDS:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"Warnung: Feed nicht lesbar: {url}", file=sys.stderr)
            continue
        for e in feed.entries:
            stamp = e.get("published_parsed") or e.get("updated_parsed")
            if stamp and (jetzt - time.mktime(stamp)) > MAX_ALTER_TAGE * 86400:
                continue
            titel = e.get("title", "").strip()
            link = e.get("link", "").strip()
            text = e.get("summary", "").strip()
            if titel and link and ist_palaeo_relevant(quelle, titel, text):
                kandidaten.append({
                    "quelle": quelle, "titel": titel,
                    "url": link, "text": text[:800],
                })
    # Doppelte Links entfernen
    gesehen, eindeutig = set(), []
    for k in kandidaten:
        if k["url"] not in gesehen:
            gesehen.add(k["url"])
            eindeutig.append(k)
    return eindeutig[:MAX_KANDIDATEN]


def fasse_zusammen(kandidaten):
    """Schickt die Kandidaten an die Claude API und erhält 3–4 News als JSON."""
    heute = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    auftrag = f"""Du bist Redakteur der Website "Fossilium", einem deutschen
Dinosaurier-Lexikon. Unten findest du aktuelle Meldungen aus verschiedenen
Wissenschafts-Feeds – einige Quellen sind thematisch breit, es kann also
fachfremdes Material (z.B. Physik, Medizin, Technik, moderne Biologie ohne
Fossilbezug) dabei sein.

Wähle NUR Meldungen aus, die wirklich mit Dinosauriern, Fossilien oder
Paläontologie zu tun haben, und fasse davon die 3 bis 4 interessantesten
auf Deutsch zusammen. Gibt es weniger als 3 passende Meldungen, nimm nur
die, die tatsächlich passen – lieber weniger als thematisch falsche.
Regeln:
- Nur Fakten verwenden, die in den Meldungen stehen. Nichts erfinden oder ergänzen.
- Zusammenfassung: 2 bis 3 Sätze, allgemeinverständlich, sachlich, eigener Wortlaut.
- Titel: eigener deutscher Titel, keine Übersetzung des Originaltitels Wort für Wort.
- "quelle" und "url" exakt aus der jeweiligen Meldung übernehmen.

Antworte AUSSCHLIESSLICH mit gültigem JSON in genau dieser Form, ohne
Markdown-Zäune und ohne Text davor oder danach:
{{"meldungen": [{{"titel": "...", "zusammenfassung": "...", "quelle": "...", "url": "...", "datum": "{heute}"}}]}}

Hier die Meldungen:
{json.dumps(kandidaten, ensure_ascii=False, indent=2)}"""

    antwort = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODELL,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": auftrag}],
        },
        timeout=120,
    )
    antwort.raise_for_status()
    text = "".join(
        block.get("text", "")
        for block in antwort.json().get("content", [])
        if block.get("type") == "text"
    )
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def main():
    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("Fehler: Umgebungsvariable ANTHROPIC_API_KEY ist nicht gesetzt.")

    # Vor jedem externen Schritt wird der bisherige Feed dauerhaft gesichert.
    sichere_archiv()
    try:
        kandidaten = hole_kandidaten()
    except Exception:
        sichere_archiv()
        raise
    print(f"{len(kandidaten)} frische Meldungen gefunden.")
    if not kandidaten:
        sichere_archiv()
        print("Keine neuen Meldungen – news.json bleibt unverändert.")
        return

    try:
        daten = fasse_zusammen(kandidaten)
    except Exception:
        sichere_archiv()
        raise
    if not isinstance(daten, dict) or not isinstance(daten.get("meldungen"), list):
        sichere_archiv()
        sys.exit("Fehler: Die Zusammenfassung enthielt keine gültige Meldungsliste; news.json bleibt unverändert.")
    meldungen = daten["meldungen"]
    if not meldungen:
        warnung = "Keine passenden Meldungen in der Zusammenfassung (0 ausgewählt) – news.json bleibt unverändert."
        sichere_archiv()
        print(f"::warning::{warnung}")
        return
    erforderliche_felder = ("titel", "zusammenfassung", "quelle", "url", "datum")
    quellen_nach_url = {k.get("url"): k.get("quelle") for k in kandidaten if k.get("url")}
    if any(
        not isinstance(meldung, dict)
        or any(not isinstance(meldung.get(feld), str) or not meldung[feld].strip() for feld in erforderliche_felder)
        or not _valid_news([meldung])
        or meldung.get("url") not in quellen_nach_url
        or meldung.get("quelle") != quellen_nach_url.get(meldung.get("url"))
        for meldung in meldungen
    ):
        sichere_archiv()
        sys.exit("Fehler: Mindestens eine Meldung ist unvollständig oder nicht durch einen RSS-Kandidaten belegt; news.json bleibt unverändert.")
    daten["stand"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    tmp_ausgabe = f"{AUSGABE}.tmp"
    with open(tmp_ausgabe, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
    os.replace(tmp_ausgabe, AUSGABE)
    sichere_archiv(meldungen)
    print(f"{len(daten.get('meldungen', []))} News in {AUSGABE} geschrieben.")


if __name__ == "__main__":
    main()
