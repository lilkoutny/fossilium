# Fossilium Content-Produktion

Stand: 19. Oktober 2026. Die lokale Strecke verbindet Recherche, Themenbewertung, belegtes deutsches Skript, separate Modellprüfung, Sprecherstimme, Bilder, animierte Clips und Schnitt. Der reale bezahlte Gesamtlauf ist noch nicht geprüft: Die lokalen Anbieterzugänge fehlen. Es wurde bisher nichts für diesen Test ausgegeben.

## Erster Test und Budget

Der Nutzer hat die frühere Anbieterpause aufgehoben. Ziel sind ungefähr **20 Euro insgesamt**, mit einem technischen Stopp bei **25 Euro** als kleinem Puffer. Das gilt zusammen für Recherche, Stimme, Bilder, Videos und Versuche; es ist kein Tages- oder Monatsbudget.

`budget.py` speichert Reservierungen und Kosten in derselben dauerhaften SQLite-Datenbank. Bereits verbrauchte Beträge zählen weiter. Ein unbekannter Auftragsausgang bleibt reserviert und wird nicht automatisch erneut bezahlt. Erfolgreiche Rechercheantworten werden gespeichert; Medienaufträge werden über ihre gespeicherte Anbieterkennung fortgesetzt. Geänderte Anfragen zum selben Auftrag werden angehalten.

Die Umrechnung von 1 USD in eine Budgetreserve von 1,20 EUR ist eine konservative Rechengröße inklusive Puffer, kein behaupteter Wechselkurs. Die Preisprüfung ist auf 30 Tage begrenzt. Bei unbekannten Preisen oder unerwarteten höheren Anbieterkosten hält die Strecke an. Eine bestehende Datenbank übernimmt eine spätere Erhöhung in der Policy nicht stillschweigend; Ausgaben dürfen nicht durch Löschen der Zustandsdaten zurückgesetzt werden.

`test-policy.json` erlaubt einen manuell gestarteten Test. Unbeaufsichtigte bezahlte Tagesläufe bleiben bis zum erfolgreichen Gesamttest aus. Automatisches Social-Posting ist nicht beauftragt.

## Start unter Windows

Die Startdatei erstellt bei Bedarf eine projektlokale Python-Umgebung:

```powershell
.\scripts\run-content-test.ps1
```

Dieser Standardaufruf plant und zeigt Zustand/Budget; er startet keine bezahlte Generierung. Er liest den vorhandenen lokalen News-Feed. Für den aktuellen veröffentlichten Feed zuerst die unveränderten News-Daten vom Repository aktualisieren.

Für einen vollständigen, bereits autorisierten Test:

```powershell
.\scripts\run-content-test.ps1 -Execute -AskForKeys
```

Die Schlüssel werden unsichtbar abgefragt und nur im gestarteten Prozess verwendet. Sie gehören weder in den Chat noch in den Quellcode. Benötigt werden `ANTHROPIC_API_KEY` und `RUNWAYML_API_SECRET`. Bereits gesetzte Prozessvariablen funktionieren ohne `-AskForKeys`. Das Runway-Plugin-Login ersetzt den API-Schlüssel für diesen lokalen automatisierten Ablauf nicht.

Runway stellt im [Developer-Portal](https://dev.runwayml.com/) einen projektbezogenen API-Zugang bereit. Das Guthaben ist getrennt vom normalen Web-Abonnement; zum Einstieg nennt die offizielle Anleitung mindestens 10 USD. Automatische Aufladung ist für diesen Versuch nicht vorgesehen. [Offizielle Einrichtung](https://docs.dev.runwayml.com/guides/setup/).

Der Standardzustand liegt unter `%LOCALAPPDATA%/Fossilium/production.sqlite`, Medien daneben in `media/`. Damit bleibt der Zustand unabhängig von GitHub-Actions-Caches oder einem erneuten Checkout bestehen. `FOSSILIUM_STATE_DIR` kann einen anderen dauerhaft gesicherten Ordner festlegen. Eine Sicherung muss die Datenbank und Medien zusammen enthalten.

Der direkte Python-Aufruf lautet:

```powershell
python -m content_pipeline.runner --news-json news.json
python -m content_pipeline.runner --news-json news.json --execute --watch
```

Ein erneuter Aufruf setzt denselben Auftrag fort. Fehlende Anmeldung, Guthaben, Quellen, Belege oder unklarer Anbieterstatus werden als Blockierungsgrund ausgegeben.

## Anbieter und Ausgabe

Die vorhandene Recherche nutzt den fest bepreisten Anthropic-Zugang. Für den ersten Medienversuch ist Runway als gemeinsames Backend vorbereitet: Gen-4 Image für 720×1280-Bilder, Gen-4 Turbo für animierte Clips und Eleven v4 für deutsche Sprache mit dem neutralen Preset Martin. Weitere Modelle benötigen eine eigene geprüfte Preiszuordnung, bevor sie Geld ausgeben dürfen.

Geprüfte API-Preise: 5 Credits je 720p-Bild, 5 Credits je Sekunde Clip und 5 Credits je 1.000 Zeichen Sprechertext; ein Credit entspricht 0,01 USD. Der konkrete Plan reserviert vorsichtshalber bis zu zwei 10-Sekunden-Clips je Szene. Quellen: [Runway-Preise](https://docs.dev.runwayml.com/guides/pricing/), [Anthropic-Modellpreis](https://platform.claude.com/docs/en/models/haiku-4-5/overview), [Suchkosten](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool).

Nur ein Skript mit Quellenbelegen und bestandener separater Modellprüfung erreicht die Medienproduktion. Ein gemeinsames Referenzbild verankert den visuellen Stil. Sprache wird vor der Bildproduktion zeitlich gemessen. Der Renderer erstellt ein privates MP4 in 9:16, 720×1280, H.264/24 fps mit AAC-Ton, sichtbaren Captions/Rekonstruktionshinweisen und einer SRT-Datei. Signierte Downloadadressen und vollständige Quellen bleiben privat.

Das Ergebnis ist zunächst eine Vorschau mit ausstehender visueller Prüfung. Automatische Prüfungen belegen weder wissenschaftlich korrekte Dinosaurieranatomie noch Viralität. Illustrationen und Bewegungen werden als KI-Rekonstruktion markiert. Fremde Presseillustrationen werden nicht automatisch übernommen. [Runway-Nutzungsrechte](https://help.runwayml.com/hc/en-us/articles/18927776141715-Usage-rights).

## Betrieb und Prüfstand

Die vorhandene GitHub-Action veröffentlicht weiterhin den reduzierten Recherche-/Skriptstatus. Ihr Cache ist **kein** geeigneter Geldspeicher. Der neue bezahlte Gesamttest verwendet den lokalen persistenten Runner; ein unbeaufsichtigter Serverbetrieb benötigt eine entsprechend gesicherte dauerhafte Laufzeit.

Geprüft sind die lokalen Datenflüsse einschließlich Provider-Mocks, Budget, Wiederaufnahme und ein echter 60-Sekunden-Render mit synthetischen Farbflächen und Testton. Diese technische Fixture unter `content_pipeline/output/render-qa/` ist kein Dino-Film. Aktuelle Testnachweise stehen im Projektgedächtnis. Live-Anbietergenerierung, natürliche Stimme, paläontologische Bildqualität und der vollständige reale Gesamtlauf bleiben bis zum verbundenen Konto offen.

```powershell
python -m unittest discover -s content_pipeline/tests -v
python -m unittest discover -s tests -v
```

Für die lokale Website zeigt `tests/news-ui.cjs` die Browserprüfung der vier News-Karten und des vollständigen Datumsarchivs. Dazu wird Playwright mit einem vorhandenen Chrome benötigt.
