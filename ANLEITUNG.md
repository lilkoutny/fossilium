# Fossilium – Anleitung: Seite online stellen & tägliche Paläo-News

## Was ist im Paket?

| Datei | Zweck |
|---|---|
| `index.html` | Deine komplette Website (Karte, Dinodex, News-Bereich) |
| `news.json` | Die aktuellen News – wird täglich automatisch überschrieben |
| `news-archiv.json` | Alle bisher veröffentlichten Meldungen; neue Einträge werden dauerhaft ergänzt |
| `hole_news.py` | Skript: holt RSS-Meldungen, fasst sie per OpenAI Responses API zusammen |
| `.github/workflows/news.yml` | GitHub-Action: führt das Skript jeden Morgen aus |
| `bilder/` | Hier kommen deine Blender-Renders rein |

## Schritt 1: GitHub-Konto und Repository

1. Konto anlegen auf https://github.com (kostenlos).
2. Neues Repository erstellen: Name z.B. `fossilium`, Sichtbarkeit **Public**.
3. Alle Dateien aus diesem Paket hochladen ("Add file → Upload files").
   Wichtig: Die Ordnerstruktur beibehalten – `news.yml` muss unter
   `.github/workflows/news.yml` liegen. Am einfachsten: das ZIP lokal
   entpacken und den gesamten Inhalt hochladen.

## Schritt 2: Website aktivieren (GitHub Pages)

1. Im Repository: **Settings → Pages**.
2. Bei "Source": Branch `main`, Ordner `/ (root)` wählen → **Save**.
3. Nach 1–2 Minuten ist die Seite erreichbar unter:
   `https://DEINNAME.github.io/fossilium/`

## Schritt 3: OpenAI-API-Schlüssel hinterlegen

1. Konto und API-Schlüssel auf https://platform.openai.com/api-keys
   einrichten. Das verwendete Modell und Limits können sich ändern; aktuelle
   Preise stehen ausschließlich in der offiziellen OpenAI-Dokumentation.
2. Im GitHub-Repository: **Settings → Secrets and variables → Actions →
   New repository secret**.
3. Name: `OPENAI_API_KEY` – Wert: dein Schlüssel → **Add secret**. Siehe auch https://github.com/lilkoutny/fossilium/settings/secrets/actions und https://platform.openai.com/api-keys.

## Schritt 4: News-Automatik testen

Auf der Startseite erscheinen die vier neuesten verfügbaren Meldungen. Der Button **Alle Meldungen anzeigen** öffnet das vollständige Archiv, nach Datum absteigend sortiert. Bereits angezeigte Beiträge bleiben im Archiv, auch wenn der tägliche Feed später andere Themen liefert. Die vorhandene Versionshistorie wurde als Ausgangsbestand übernommen; `scripts/build-news-archive.py` kann diesen Bestand aus der Git-Historie reproduzieren.

1. Im Repository auf den Tab **Actions** klicken.
2. Links "Paläo-News aktualisieren" wählen → **Run workflow**.
3. Nach ca. einer Minute sollte der Lauf grün sein und `news.json`
   frische Meldungen enthalten. Ab jetzt läuft das jeden Morgen
   automatisch (5:00 UTC – Uhrzeit änderbar in `news.yml`, Zeile `cron`).

## Deine Blender-Bilder

Renders in den Ordner `bilder/` hochladen, Dateinamen wie im Platzhalter
auf der Seite angezeigt (z.B. `bilder/tyrannosaurus.png`). Neue Dinos
trägst du in `index.html` im Block `const DINOS = [` ein – Marker auf der
Weltkarte und Dinodex-Eintrag entstehen automatisch.

## Häufige Stolpersteine

- **News-Bereich zeigt nur den Hinweistext:** Lokal per Doppelklick geöffnet
  kann die Seite `news.json` nicht laden – online (GitHub Pages) klappt es.
- **Action schlägt fehl mit Key-Fehler:** Secret-Name muss exakt
  `OPENAI_API_KEY` lauten. Bei HTTP 401/403 Schlüssel und Projektberechtigungen
  prüfen; bei HTTP 429 Anfragelimits beziehungsweise API-Kontingent prüfen.
- **Keine neuen Meldungen:** An ruhigen Tagen liefern die Feeds wenig –
  das Skript lässt die alten News dann einfach stehen.
- **Quellen ändern:** Liste `FEEDS` oben in `hole_news.py` – dort kannst du
  RSS-Feeds ergänzen (z.B. von Museen oder Fachblogs).
