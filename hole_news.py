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
import sys
import time
from datetime import datetime, timezone

import feedparser
import requests

# ------------------------------------------------------------------
# Einstellungen – hier kannst du Quellen ergänzen oder tauschen
# ------------------------------------------------------------------
FEEDS = [
    ("ScienceDaily", "https://www.sciencedaily.com/rss/fossils_ruins/dinosaurs.xml"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/fossils_ruins/paleontology.xml"),
    ("Phys.org", "https://phys.org/rss-feed/biology-news/paleontology-fossils/"),
]
MAX_ALTER_TAGE = 3      # nur Meldungen der letzten X Tage
MAX_KANDIDATEN = 12     # so viele Artikel bekommt die KI maximal zu sehen
MODELL = "claude-haiku-4-5"  # günstigstes Modell, reicht fürs Zusammenfassen
AUSGABE = "news.json"


def hole_kandidaten():
    """Sammelt frische Einträge aus allen Feeds."""
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
            if titel and link:
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
Dinosaurier-Lexikon. Unten findest du aktuelle Meldungen aus der Paläontologie.

Wähle die 3 bis 4 interessantesten aus und fasse jede auf Deutsch zusammen.
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

    kandidaten = hole_kandidaten()
    print(f"{len(kandidaten)} frische Meldungen gefunden.")
    if not kandidaten:
        print("Keine neuen Meldungen – news.json bleibt unverändert.")
        return

    daten = fasse_zusammen(kandidaten)
    daten["stand"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with open(AUSGABE, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
    print(f"{len(daten.get('meldungen', []))} News in {AUSGABE} geschrieben.")


if __name__ == "__main__":
    main()
