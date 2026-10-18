# Fossilium Content-Produktion – Betriebsstand

Genehmigtes Testbudget: insgesamt höchstens 20 Euro für Recherche, Stimme und Video. `test-policy.json` hält diese Vorgabe fest. Kostenpflichtige Automatik bleibt aus, bis Anbieterzugang und Kostenkontrolle verbunden und geprüft sind. Der vorhandene Aufrufzähler allein ist kein Eurodeckel.

Die erste Strecke endet bei einem belegten, automatisch gegengeprüften deutschen Skript. Sie erstellt noch keine gesprochenen oder cinematischen Videos. Der frühere captions-only Pilot ist kein Produktionsrenderer.

Produktionscode: `production.py`. Eigenständige Aufträge nach normalisierter Nachrichten-URL, persistente SQLite-Stufen, Themenauswahl anhand fünf Kriterien, Originalquellen-Recherche, Skript und separate Modellprüfung. Automatische Modellprüfung reduziert Fehler; sie garantiert keine wissenschaftliche Richtigkeit oder Viralität.

Der Workflow im Fossilium-Repository läuft nach einem erfolgreichen täglichen News-Lauf und kann manuell gestartet werden. Er bearbeitet maximal eine Nachricht je Durchlauf. Zustand liegt im GitHub-Actions-Cache; öffentliche Statusdaten enthalten Quellenlinks und Skripte, keine API-Schlüssel, vollständigen Artikeltexte oder zitierten Belegpassagen. Cacheverlust kann zu erneuter Verarbeitung führen. GitHub-Cache ist keine dauerhafte Datenbank; für einen bezahlten Regelbetrieb sollte der Zustand in einen dauerhaften Datenspeicher umziehen.

Die kostenpflichtige Strecke ist standardmäßig aus. Erst Repository-Variable `FOSSILIUM_CONTENT_API_ENABLED=1` aktiviert den vorhandenen Anthropic-Zugang. Dann werden höchstens vier API-Aufrufe pro UTC-Tag in der gespeicherten Datenbank reserviert, einschließlich fehlgeschlagener Aufrufe; je Aufruf höchstens 2000 Ausgabetokens. Eine optionale Originalquellen-Suche verwendet höchstens zwei Websuchen. Dies ist ein technisches Aufruflimit, kein garantierter Eurodeckel. API-Kosten laufen unabhängig vom ChatGPT-Abonnement. Ohne Freischaltung zeigt Nexus den tatsächlichen Blockierungsgrund.

Primärquellen werden aus Nachrichtenlinks und bei Bedarf einer begrenzten Websuche ermittelt und separat abgerufen. Nicht erreichbare Quellen, fehlerhafte Antworten oder fehlende Belege führen zu Blockierung. Geschätzte Anatomie darf nicht als Fossilbefund ausgegeben werden. Der Quellenabruf prüft DNS-Adressen und jede Weiterleitung, hat aber keine gegen DNS-Rebinding gepinnte Netzwerkverbindung; der automatische Betrieb gehört auf isolierte GitHub-Runner.

Noch offen: Videoanbieter, deutsche Stimme, konsistente visuelle Referenzen, Budget, Lizenzprüfung für Bildmaterial, tatsächlicher erfolgreicher Anbieter-Durchlauf und Qualitätsprüfung eines vollständigen Videos. Es wird nichts auf TikTok/Instagram hochgeladen.

Technische Quellen: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
