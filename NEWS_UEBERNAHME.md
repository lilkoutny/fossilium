# OpenAI-News-Übernahme

Stand: 29.10.2026. `hole_news.py` nutzt die OpenAI Responses API mit dem
konfigurierbaren Snapshot `gpt-5.4-mini-2026-03-17`, `OPENAI_API_KEY`,
Structured Outputs und `store:false`. Der Workflow verwendet dasselbe Secret;
ein separater Offline-Testworkflow prüft relevante Änderungen ohne Secrets.

Die RSS-Quellen, UTC-05:00-Schedulerlogik, News-Layout und das additive Archiv
bleiben unverändert. Fehler oder leere KI-Ausgaben schreiben den bestehenden
Feed nicht um. Die getrennte `content_pipeline/production.py` enthält weiterhin
Legacy-Claude-Abhängigkeiten und ist nicht Teil dieser Migration. Ein echter
Live-API-Lauf wurde nicht durchgeführt; das Secret muss auf GitHub noch angelegt
werden. Design, `news.json` und `news-archiv.json` wurden nicht geändert.

## Abgleich mit der Übergabe

Das vom Nutzer gelieferte `UEBERGABE.md` ist eine historische Projektbeschreibung.
Der aktuelle News-Abruf hat fünf RSS-Quellen und maximal 20 Kandidaten; das bereits
vorhandene Archiv und die überarbeitete Weltkarte werden erhalten. Am 29.10.
lieferte die Website 50 Archivmeldungen mit Stand 20.10.; der heutige alte
News-Lauf fand 20 Kandidaten und scheiterte anschließend an Anthropic HTTP 401.
Die authentifizierte Prüfung der Repository-Secret-Namen ergab ausschließlich
`ANTHROPIC_API_KEY`. Schlüsselwerte wurden nicht ausgegeben.

## Prüfung und Aktivierung

23 Offline-Tests für News-Ausgabe, Archiv und den neuen Responses-Adapter bestehen:
`python -m unittest tests.test_hole_news tests.test_news_archive -v`.
Sie decken unter anderem das echte REST-Antwortformat mit `message/output_text`,
Schema und Quellenzuordnung sowie Refusal, unvollständige/fehlerhafte Antworten,
401/403/429, Netzwerkfehler und den Erhalt bestehender News ab. Die Antworten
stammen aus Test-Doubles; Modellqualität, Kontozugang und reale API-Kosten sind
damit nicht live bestätigt.

1. Einen Schlüssel im [OpenAI-API-Konto](https://platform.openai.com/api-keys)
   erstellen beziehungsweise einen bestehenden passenden Schlüssel verwenden.
2. Unter [GitHub Actions Secrets](https://github.com/lilkoutny/fossilium/settings/secrets/actions)
   als neues Repository-Secret `OPENAI_API_KEY` hinterlegen.
3. Die geprüfte News-Änderung nach `main` übernehmen. Anschließend den bestehenden
   Workflow „Paläo-News aktualisieren“ einmal ausführen und dessen Ergebnis sowie
   `https://fossilium.org/news.json` und das Archiv prüfen. Ein leerer redaktioneller
   Trefferbestand gilt nicht als Nachweis einer neuen Meldung.

Die getrennte Content-Pipeline bleibt ein weiterer Migrationsschritt. Ihre
Budget-, Recherche-, Prüf- und Medienadapter werden durch diesen News-Umbau
nicht ersetzt. Bezahlte Medienproduktion und Social-Posting werden nicht aktiviert.

Technische Grundlagen: [Responses mit Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
und [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
am 29.10.2026 geprüft. Der Modell-Snapshot ist bewusst festgelegt; Zugriff und
Limits des konkreten API-Projekts müssen beim Live-Test geprüft werden.
