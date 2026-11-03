# Fossilium-Publikationen

Statische, eigenständige deutsche Langartikel mit stabilen URLs. Die Startseite verknüpft nur tatsächlich vorhandene Seiten aus `index.json`; der externe Originalartikel bleibt erreichbar. Das vollständige News-Archiv bleibt erhalten.

## Redaktioneller Ablauf

Die automatische Pipeline bewertet jede RSS-Meldung mit Claude gegen die
zentrale Policy (Dinosaurier, unmittelbare frühe Vogelentwicklung, Flugsaurier
und ausgestorbene Meeresreptilien). Amphibien, moderne Tiere, Insekten-/Termiten-
Funde, Affen/Säugetiere und bloße „Dinosaurierzeitalter“-Kontexte werden
ausgeschlossen. Eine positive Meldung erhält eine eigene, quellengebundene
Publikation; fehlgeschlagene Versuche bleiben in der Retry-Queue und erzeugen
keinen toten Publikationslink.

1. Nachricht und wissenschaftliche Originalreferenz festhalten; Meldungs-, Studien- und Übernahmedatum trennen.
2. Tatsächlich gelesenen Umfang dokumentieren: Volltext, Abstract oder Institutsmitteilung. Keine nicht gelesene Studie als geprüft ausgeben.
3. Eigenständigen deutschen Artikel schreiben. Befund, wissenschaftliche Interpretation und redaktionelle Einordnung unterscheiden. Hintergrundinformationen benötigen eigene Belege.
4. Nur Bilder mit belegbarer Nutzungserlaubnis übernehmen. Urheber, Lizenz, Originalquelle und eventuelle Änderungen direkt am Bild nennen. Originalfossilien nicht durch KI nachzeichnen.
5. Artikel in `artikel.json` ergänzen und Quellen unmittelbar hinter den belegten Sätzen als `[[S1]]`, `[[S2]]` usw. einfügen. Der Renderer zeigt anklickbare `[1]`-/`[2]`-Verweise; die Nummerierung folgt der Reihenfolge im Quellenverzeichnis. Keine Quellenblöcke nach Abschnitten. Die `datei` eines Bildes liegt relativ zu diesem Verzeichnis unter `assets/`.
6. `python publikationen/render.py` erstellt HTML und Manifest; `python publikationen/render.py --check` prüft den gespeicherten Stand ohne Änderungen.
7. Quellen und tatsächliche Desktop-/Mobilansicht prüfen, anschließend die zusammengehörigen Daten, Bilder, HTML-Dateien und das Manifest veröffentlichen.

Seit 03.11.2026 erstellt der tägliche Claude-News-Workflow für jede neu akzeptierte Meldung einen eigenen Artikel. Alle Quellen durchlaufen denselben Themenfilter; die Vorschau allein bleibt auf vier Einträge begrenzt. Der Originaltext wird abgerufen und erneut auf Relevanz geprüft. Eine gesperrte, zu kurze oder fehlerhafte Quelle sowie unvollständige Artikel erzeugen keinen neuen Teaser. `news-pipeline-state.json` bewahrt offene Versuche über das RSS-Altersfenster hinaus und verhindert doppelte Generierung. API-Schlüssel oder vollständige Quellentexte werden dort nicht gespeichert.

Haiku übernimmt die strukturierte Themenprüfung, Sonnet die eigene deutsche Darstellung. Längere Texte werden als Markdown erzeugt, lokal in Abschnitte eingelesen und danach validiert. Umfang einschließlich Vorspann: mindestens 300 Wörter bei kurzen Originalmeldungen, mindestens 450 bei Quellen ab 600 Wörtern; mindestens vier Abschnitte. Fehlende Fakten werden nicht durch erfundene Hintergründe ersetzt. Validierbare gespeicherte Entwürfe werden ohne weiteren Modellaufruf übernommen.

Die Bestandsprüfung erhält alle 62 historischen Datensätze, blendet 44 fachfremde Meldungen aus und legt die 16 relevanten Meldungen ohne eigene Publikation zur Nachbearbeitung vor. Vorhandene Seiten behalten ihre URLs, auch wenn ihr Thema jetzt ausgeschlossen ist. Quelldatum, erstes Erscheinen auf Fossilium und Artikelveröffentlichung bleiben getrennt. Der Workflow validiert Daten und HTML vor einem gemeinsamen Git-Commit; Renderer und Seitenaufrufe selbst rufen keine KI-API auf.

## Abbildungsnachweis

`assets/longipteryx-abbildung-1.png`: unveränderte Abbildung 1 aus Clark, Wang und Mitautoren (2026), *The plumage of Longipteryx (Aves: Enantiornithes)*, Journal of Paleontology. DOI: https://doi.org/10.1017/jpa.2026.10282 . Lizenz: https://creativecommons.org/licenses/by/4.0/ . Die Verlagsseite erklärt den Artikel ausdrücklich als CC BY 4.0; Abbildung 1 enthält keinen abweichenden Fremdrechtehinweis. Bildunterschrift auf Deutsch von Fossilium, Grafik selbst unverändert. SHA256: `61a2a623ec8ab964c6350b43a381638b3608ff4630a2eec466f7c1c8f1319654`.

## Prüfungen

Offline: `python -m unittest tests.test_publications tests.test_hole_news tests.test_news_archive tests.test_news_pipeline`.
Browser: `node tests/publications-ui.cjs`, `node tests/dinodex-ui.cjs`, `node tests/news-ui.cjs` mit installiertem Playwright und lokalem Chrome. Die Browsernachweise bleiben unter `.content-state/` privat.
