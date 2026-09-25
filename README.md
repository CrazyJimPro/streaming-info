# Streaming-Info

Ein privates, lokales Tool: zeigt in einer lokalen Web-App, **was demnächst
anläuft** — mit Startdatum. Drei Abschnitte:

- **Streaming** — Serien und neue Staffeln, die bei Netflix, Amazon Prime
  Video, Disney+, Apple TV+, Paramount+, WOW (Sky) oder HBO Max starten,
  farblich nach Anbieter markiert
- **Kino** — deutsche Kinostarttermine
- **Digital** — Filme mit angekündigtem Termin für die digitale Auswertung

Was bereits läuft, steht bewusst **nicht** drin: die Übersicht beantwortet
„worauf kann ich mich freuen", nicht „was liegt gerade im Katalog".

Datenquelle ist [TMDB](https://www.themoviedb.org) (The Movie Database).

**Eine Einschränkung vorweg, weil sie sichtbar ist:** Bei kommenden *Filmen*
nennt TMDB zwar den Termin, aber keine Plattform — deshalb stehen sie im
Abschnitt „Digital" ohne Anbieter-Logo. Bei *Serien* ist die Zuordnung
dagegen sauber, weil sie über die TV-Netzwerke des jeweiligen Anbieters
läuft. Für WOW/Sky ist die Serien-Ausbeute dünn, dort führt TMDB nur das
Netzwerk Sky Deutschland.

Es läuft **nichts im Hintergrund**: die Daten werden geholt, wenn die App
gestartet wird — und mit dem Knopf **„Beenden"** auf der Seite ist alles
wieder aus. Kein Dienst, keine geplante Aufgabe, kein Cronjob.

Läuft unter **Windows und Linux**. In Kurzform:

| | Einmalig installieren | Danach starten |
|---|---|---|
| **Windows** | `start.bat` herunterladen und doppelklicken | Desktop-Verknüpfung „Streaming-Info" |
| **Linux** | `start.sh` herunterladen, `chmod +x`, ausführen | Desktop-Verknüpfung „Streaming-Info" |

Ausführlich mit allen Schritten steht das gleich unten.

## Voraussetzung: kostenloser TMDB-API-Schlüssel

Ohne API-Schlüssel kann das Tool keine Daten laden. Ein Schlüssel ist
kostenlos und in wenigen Minuten eingerichtet:

1. Auf [themoviedb.org](https://www.themoviedb.org) einen kostenlosen
   Account anlegen.
2. Unter *Kontoeinstellungen → API* einen **API-Schlüssel (v3 auth)**
   anfordern (Anwendungstyp „Persönlich/privat" reicht). Als *Application
   URL* reicht ein beliebiges eigenes Profil, z.B. der eigene GitHub-Account.
3. Den Schlüssel nach dem ersten Start dieses Tools auf der
   Einstellungsseite eintragen (siehe unten) — er wird lokal in
   `config/config.json` gespeichert, nie im Repository und nirgendwo hochgeladen.

## Erstmalige Installation

Heruntergeladen wird **eine einzige Datei** — nicht das ganze Repository.
Alles Weitere (Projektcode, Python, Abhängigkeiten, Desktop-Verknüpfung)
richtet diese Datei selbst ein.

### Windows

1. **Datei herunterladen:**
   [start.bat](https://github.com/CrazyJimPro/streaming-info/raw/main/start.bat)
   — Rechtsklick auf den Link → *Ziel speichern unter …*, z.B. in `Downloads`.
   Der Ordner ist egal, die Datei sucht sich ihren Platz selbst.
2. **Doppelklick auf `start.bat`.** Warnt Windows mit *„Der Computer wurde
   durch Windows geschützt"*: auf *Weitere Informationen* → *Trotzdem
   ausführen* klicken (die Datei stammt aus dem Internet und ist nicht
   signiert).
3. **Warten.** Beim allerersten Mal dauert es ca. 2–5 Minuten: fehlt Python,
   wird es per `winget` mitinstalliert, dann folgen virtuelle Umgebung und
   Abhängigkeiten. Das Fenster zeigt, was gerade passiert, und **schließt
   sich am Ende von selbst**.
4. **Fertig.** Der Browser öffnet http://127.0.0.1:5100. Auf dem Desktop
   liegt jetzt die Verknüpfung **„Streaming-Info"**.
5. **TMDB-API-Schlüssel eintragen:** oben auf *Einstellungen* klicken, den
   Schlüssel einfügen, *Speichern*. Der erste echte Datenabruf läuft danach
   automatisch im Hintergrund (ein paar Sekunden).

Installiert wird nach `%USERPROFILE%\streaming-info`. Die heruntergeladene
`start.bat` aus `Downloads` wird danach nicht mehr gebraucht.

### Linux

1. **Terminal öffnen** und diese drei Zeilen ausführen:

```bash
curl -fsSL -O https://github.com/CrazyJimPro/streaming-info/raw/main/start.sh
chmod +x start.sh
./start.sh
```

2. **Warten.** Fehlt Python, wird es per `apt-get` nachinstalliert — dabei
   fragt das Skript nach dem `sudo`-Passwort. Danach folgen virtuelle
   Umgebung und Abhängigkeiten (beim allerersten Mal ca. 2–5 Minuten).
3. **Fertig.** Der Browser öffnet http://127.0.0.1:5100. Auf dem Desktop
   liegt die Verknüpfung **„Streaming-Info"** (sofern eine Desktop-Umgebung
   vorhanden ist — auf einem reinen Server entfällt sie).
4. **TMDB-API-Schlüssel eintragen** wie oben unter Windows beschrieben.

Installiert wird nach `~/streaming-info`. Die heruntergeladene `start.sh`
wird danach nicht mehr gebraucht.

## Jedes weitere Mal starten

**Doppelklick auf die Desktop-Verknüpfung „Streaming-Info"** — unter
Windows wie unter Linux. Es öffnet sich **kein Konsolen- oder
Terminalfenster**; nach ein paar Sekunden geht der Browser auf.

Bei jedem Start passiert automatisch:

1. Es wird geprüft, ob auf GitHub eine **neuere Version** vorliegt. Wenn ja,
   wird der komplette Code aufgefrischt und die App neu gestartet (eine noch
   laufende Instanz wird vorher beendet).
2. Die **Daten werden frisch geholt** (wenige Sekunden, im Hintergrund).
3. Der Browser öffnet die Übersicht.

Läuft die App bereits, startet ein erneuter Klick keinen zweiten Prozess,
sondern stößt nur eine Aktualisierung an und öffnet den Browser wieder.

## Beenden

Oben auf der Seite den Knopf **„Beenden"** anklicken. Danach läuft nichts
mehr im Hintergrund. Nur das Browser-Fenster zu schließen beendet die App
**nicht** — sie läuft weiter unter http://127.0.0.1:5100.

## Welche Version läuft gerade?

Oben in der Kopfzeile steht ein kleines Abzeichen, z.B. `v0.1.0`. Sie kommt
aus der Datei `VERSION` im Projektordner. Verglichen wird bei jedem Start
genau diese Nummer mit der auf GitHub — aufgefrischt wird nur, wenn die dort
**wirklich neuer** ist.

## Einstellungen

Über den Knopf **„Einstellungen"** (oder http://127.0.0.1:5100/einstellungen):

- **TMDB-API-Schlüssel** (siehe oben)
- **Vorschau-Zeitraum** — wie viele Wochen im Voraus angezeigt werden
- **Streaming-Anbieter** — welche der sieben Anbieter abgefragt werden
- **Genres** — Einschränkung auf bestimmte Genres (kein Häkchen = alle)
- **Merkliste** — Filme/Serien per Live-Suche hinzufügen, die immer
  angezeigt werden, unabhängig vom Genre-Filter
- **Ausgeblendete Titel** — über den „Ausblenden"-Knopf an jeder Karte

## Warum nicht *alles* angezeigt wird

TMDB meldet für Deutschland weit mehr Starts, als für einen Menschen
interessant sind — überwiegend Festival-Einzelvorführungen und Titel
einzelner Ländermärkte. Gefiltert wird deshalb nach **Popularität** (ein Wert,
den TMDB auch für noch nicht erschienene Titel führt) plus dem Vorhandensein
eines Posters.

Der naheliegendere Filter über die Zahl der Bewertungen funktioniert hier
prinzipbedingt nicht: Angekündigtes ist noch von niemandem bewertet worden.
In einem Vier-Wochen-Fenster kamen ganze zwei Kinostarts über diese Schwelle —
durchgefallen wären ausgerechnet Titel wie *Street Fighter* oder *Clayface*.

Die Schwellen stehen als `MIN_POPULARITAET_*` oben in
[`scraper/tmdb.py`](scraper/tmdb.py) und sind dort mit den gemessenen Werten
dokumentiert. Fehlen Titel, die dort hingehören: Wert senken. Steht zu viel
Unbekanntes drin: Wert erhöhen.
  befüllt, hier wieder rückgängig zu machen

Jede Speicherung stößt sofort einen neuen Datenabruf an (läuft im
Hintergrund) — die Übersicht zeigt danach den neuen Stand, ohne dass die
App neu gestartet werden muss.

## Wo liegt was?

Alles unterhalb von `%USERPROFILE%\streaming-info` bzw. `~/streaming-info`:

| Pfad                            | Inhalt                                              |
|----------------------------------|-----------------------------------------------------|
| `config/config.json`             | der TMDB-API-Schlüssel (bleibt bei Updates erhalten) |
| `config/einstellungen.json`      | Zeitraum, Anbieter/Genre-Auswahl, Merkliste (bleibt bei Updates erhalten) |
| `data/streaming.db`              | die geholten Titel und ihre angekündigten Starttermine |
| `logs/start.log`                 | Meldungen des Startskripts                          |
| `logs/webapp.log`                | Meldungen der Web-App                               |
| `logs/scraper.log`               | Protokoll der Datenabrufe                           |
| `VERSION`                        | installierte Versionsnummer                         |

Was das Startskript im Einzelnen automatisch erledigt:
- lädt beim allerersten Mal den Rest des Projekts von GitHub nach
- prüft, ob Python vorhanden ist — falls nicht: installiert es selbst
  (Windows: `winget`, Linux: `apt-get`, braucht dort `sudo`)
- legt eine virtuelle Umgebung an und installiert die Abhängigkeiten
- legt die Desktop-Verknüpfung an (falls noch nicht vorhanden)
- startet die Web-App ohne Fenster und öffnet den Browser, sobald sie
  antwortet

*(Wer lieber das ganze Repository klont oder als ZIP lädt, kann das tun —
`start.bat`/`start.sh` erkennen dann, dass der Rest schon da ist, und
überspringen den Download.)*
