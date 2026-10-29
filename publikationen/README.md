# Fossilium-Publikationen

Statische, eigenständige deutsche Langartikel mit stabilen URLs. Die Startseite verknüpft nur tatsächlich vorhandene Seiten aus `index.json`; der externe Originalartikel bleibt erreichbar. Das vollständige News-Archiv bleibt erhalten.

## Redaktioneller Ablauf

1. Nachricht und wissenschaftliche Originalreferenz festhalten; Meldungs-, Studien- und Übernahmedatum trennen.
2. Tatsächlich gelesenen Umfang dokumentieren: Volltext, Abstract oder Institutsmitteilung. Keine nicht gelesene Studie als geprüft ausgeben.
3. Eigenständigen deutschen Artikel schreiben. Befund, wissenschaftliche Interpretation und redaktionelle Einordnung unterscheiden. Hintergrundinformationen benötigen eigene Belege.
4. Nur Bilder mit belegbarer Nutzungserlaubnis übernehmen. Urheber, Lizenz, Originalquelle und eventuelle Änderungen direkt am Bild nennen. Originalfossilien nicht durch KI nachzeichnen.
5. Artikel in `artikel.json` ergänzen und Quellen pro Abschnitt zuweisen. Die `datei` eines Bildes liegt relativ zu diesem Verzeichnis unter `assets/`.
6. `python publikationen/render.py` erstellt HTML und Manifest; `python publikationen/render.py --check` prüft den gespeicherten Stand ohne Änderungen.
7. Quellen und tatsächliche Desktop-/Mobilansicht prüfen, anschließend die zusammengehörigen Daten, Bilder, HTML-Dateien und das Manifest veröffentlichen.

Die vier Startartikel vom 29.10.2026 sind redaktionell geprüft. Die bestehenden 54 Archivmeldungen werden nicht automatisch rückwirkend zu Langartikeln umgeschrieben. Der tägliche Claude-News-Workflow bleibt bestehen; eine unbeaufsichtigte automatische Langartikel-Erzeugung ist mit diesem Renderer **noch nicht aktiviert**. Weder der Renderer noch Seitenaufrufe rufen eine KI-API auf.

## Abbildungsnachweis

`assets/longipteryx-abbildung-1.png`: unveränderte Abbildung 1 aus Clark, Wang und Mitautoren (2026), *The plumage of Longipteryx (Aves: Enantiornithes)*, Journal of Paleontology. DOI: https://doi.org/10.1017/jpa.2026.10282 . Lizenz: https://creativecommons.org/licenses/by/4.0/ . Die Verlagsseite erklärt den Artikel ausdrücklich als CC BY 4.0; Abbildung 1 enthält keinen abweichenden Fremdrechtehinweis. Bildunterschrift auf Deutsch von Fossilium, Grafik selbst unverändert. SHA256: `61a2a623ec8ab964c6350b43a381638b3608ff4630a2eec466f7c1c8f1319654`.

## Prüfungen

Offline: `python -m unittest tests.test_publications tests.test_hole_news tests.test_news_archive`.
Browser: `node tests/publications-ui.cjs`, `node tests/dinodex-ui.cjs`, `node tests/news-ui.cjs` mit installiertem Playwright und lokalem Chrome. Die Browsernachweise bleiben unter `.content-state/` privat.
