# Agent Handover: brennstoffboerse_fluessiggas

## Zweck
Home Assistant Custom Component fuer Fluessiggas-Tagespreise von brennstoffboerse.de.

Der Sensor liefert fuer eine konfigurierte Region und Abnahmemenge (1000/3000/5000 L):
- Aktueller Preis in EUR/100L
- Vortagesaenderung in EUR/100L

## Modulaufbau
- `__init__.py`
  - Registriert den Coordinator pro Config Entry.
  - Startet Platform Forwarding auf `sensor`.
- `config_flow.py`
  - Holt Regionen dynamisch ueber `async_fetch_regions`.
  - Validiert Region + Abnahmemenge.
- `coordinator.py`
  - Polling (6h), HTTP-Fetch, HTML-Parsing, Mapping Region -> Volumen -> Werte.
  - Kernlogik fuer Fehlerbehandlung (`UpdateFailed`).
- `sensor.py`
  - Stellt 2 Entities bereit: Preis und Preisveraenderung.
  - Liefert Zusatzattribute (Region, Volumen, Quelle, URL).
- `const.py`
  - Domain, URL, erlaubte Volumina, Update-Intervall.
- `manifest.json`
  - Integration-Metadaten, Requirement `beautifulsoup4`.
- `strings.json` / `translations/de.json`
  - UI-Texte fuer Config- und Options-Flow.

## Laufzeitfluss
1. Setup Entry erstellt `BrennstoffboerseFluessiggasCoordinator`.
2. Coordinator laedt Seite `fluessiggas-tagespreise.html`.
3. Parser sucht Preis-Tabelle, extrahiert Regionen und Werte.
4. Sensoren lesen Coordinator-Daten und expose'n State + Attribute.

## Parser-Details (Stand: 2026-08)
Aktueller Seitenaufbau verwendet Bootstrap-Table mit:
- Header: `Region`, `1.000 L`, `3.000 L`, `5.000 L`
- Region in erster Spalte oft als `<th>` (nicht `<td>`)
- Preiszellen enthalten Preis + optional Aenderung (z. B. `78,44 €` und `-0,53 €`)

Wichtige Robustheitsregeln im Parser:
- Header-Volumes werden aus Text extrahiert und normalisiert (`1.000` -> `1000`).
- Zeilen werden mit gemischten `th`/`td` geparst.
- Preis und Aenderung werden ueber generische Euro-Zahl-Erkennung gelesen.
- `±0,00 €` wird als `0.0` interpretiert.

## Bekannte Fehlerbilder
- `Failed to parse prices: Could not find price table`
  - Ursache: Struktur- oder Header-Aenderung der Webseite.
  - Vorgehen:
    1. Live-HTML der Zielseite abrufen.
    2. Header/Spaltenpositionen pruefen.
    3. Parser in `coordinator.py` anpassen (keine festen String-Vergleiche auf punktierte Zahlen).

## Aenderungsrichtlinien
- Keine Hardcodierung einzelner Regionen.
- Parsing immer auf mehrere Layout-Varianten robust halten.
- Bei funktionalen Parser-Aenderungen direkt Codebereinigung im selben Modul:
  - Altlogik entfernen
  - Redundanzen abbauen
  - Konsistenz pruefen
- Oeffentliche Entitaetsnamen und Attribute stabil halten (Breaking Changes vermeiden).

## Schnelle Validierung nach Parser-Aenderungen
1. Home Assistant neu laden / Integration neu laden.
2. Config Flow: Regionenliste muss befuellt sein.
3. Sensorstate pruefen fuer 1000, 3000, 5000 L.
4. Log auf `UpdateFailed`-Meldungen pruefen.

## Erweiterungsoptionen
- Optionaler `average`-Sensor fuer Durchschnittszeile.
- Attribut fuer Zeitstempel des letzten erfolgreichen Scrapes.
- Fallback auf alternative Datenquelle bei Parsing-Fehlern.

## Hinweise fuer neue Agents
Wenn du dieses Modul anfasst, priorisiere:
1. Erst Website-Struktur verifizieren.
2. Dann Parsing robust statt fragil implementieren.
3. Danach sofort innerhalb des Moduls aufraeumen (Dead Code/Redundanz).
4. Abschliessend Home Assistant Fehlerdiagnose checken.
