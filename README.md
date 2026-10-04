# Streaming-Info

Ein privates, lokales Tool. Es zeigt in einer kleinen Web-App im Browser,
**was demnächst anläuft** — mit Startdatum und Countdown:

- **Merkliste** — deine selbst gemerkten Titel, ganz oben und ohne jeden Filter
- **Streaming** — Serien und neue Staffeln bei Netflix, Amazon Prime Video,
  Disney+, Apple TV+, Paramount+, WOW (Sky) und HBO Max, farbig nach Anbieter
- **Kino** — deutsche Kinostarttermine
- **Digital** — Filme mit angekündigtem Termin für die digitale Auswertung
- **Suche** — „Wo läuft das?“: Titel eingeben, die App zeigt, bei welchem Anbieter
  er in Deutschland abrufbar ist

Was **bereits läuft**, steht bewusst nicht drin. Die Übersicht beantwortet
„worauf kann ich mich freuen", nicht „was liegt gerade im Katalog".

Es läuft **nichts im Hintergrund**: Daten werden geholt, wenn du die App
startest — und mit dem Knopf **„Beenden"** ist alles wieder aus. Kein Dienst,
keine geplante Aufgabe, kein Cronjob.

## Inhalt

| Ich möchte … | Abschnitt |
|---|---|
| das Tool zum ersten Mal einrichten | [Einrichtung in 3 Schritten](#einrichtung-in-3-schritten) |
| es täglich benutzen | [Starten und beenden](#starten-und-beenden) |
| wissen, wo ein Film oder eine Serie läuft | [Suche](#suche-wo-läuft-das) |
| bestimmte Serien im Blick behalten | [Merkliste](#merkliste-bestimmte-titel-im-blick-behalten) |
| meine Liste sichern | [Sicherung erstellen](#sicherung-erstellen) |
| meine Liste auf einen anderen Rechner holen | [Sicherung einspielen](#sicherung-einspielen) |
| dass weniger Unbekanntes angezeigt wird | [Weitere Einstellungen](#weitere-einstellungen) |
| ein Problem lösen | [Wenn etwas nicht klappt](#wenn-etwas-nicht-klappt) |

---

# Einrichtung in 3 Schritten

## Schritt 1: Kostenlosen TMDB-Schlüssel holen

Die Daten kommen von [TMDB](https://www.themoviedb.org) (The Movie Database).
Dafür braucht jede Person einen eigenen Schlüssel — kostenlos, in ein paar
Minuten erledigt:

1. Auf [themoviedb.org](https://www.themoviedb.org) oben rechts einen
   **kostenlosen Account** anlegen und die Bestätigungsmail bestätigen.
2. Oben rechts auf das Profilbild → **Einstellungen** → links im Menü **API**.
3. Einen Schlüssel anfordern und dabei die Variante für **private,
   nicht-kommerzielle Nutzung** wählen (TMDB nennt sie je nach Fassung
   „Developer" oder „Persönlich/privat") und die Nutzungsbedingungen
   bestätigen.
4. Das Formular ausfüllen. Es darf schlicht bleiben — als Name z.B. „Privat",
   als *Application URL* irgendeine eigene Adresse (etwa dein GitHub-Profil),
   als Beschreibung „private Nutzung".
5. Fertig. Du bekommst einen **API-Schlüssel (v3 auth)** — eine lange Zeichen-
   und Zahlenfolge. Lass die Seite offen oder kopiere den Schlüssel
   zwischendurch irgendwohin, du brauchst ihn in Schritt 3.

## Schritt 2: Installieren

Du lädst **eine einzige Datei** herunter — nicht das ganze Projekt. Alles
Weitere (Programmcode, Python, Zubehör, Desktop-Verknüpfung) richtet diese
Datei selbst ein.

### Windows

1. **Datei herunterladen:** Rechtsklick auf
   [start.bat](https://github.com/CrazyJimPro/streaming-info/raw/main/start.bat)
   → *Ziel speichern unter …* → z.B. in `Downloads`. Wo genau, ist egal.
2. **Doppelklick auf `start.bat`.**
3. Erscheint das blaue Fenster **„Der Computer wurde durch Windows
   geschützt"**: auf *Weitere Informationen* klicken, dann auf *Trotzdem
   ausführen*. (Die Datei kommt aus dem Internet und ist nicht signiert —
   deshalb fragt Windows nach.)
4. **Warten.** Beim allerersten Mal dauert es etwa 2–5 Minuten. Fehlt Python
   auf dem Rechner, wird es automatisch mitinstalliert. Das schwarze Fenster
   zeigt, was gerade passiert, und **schließt sich am Ende von selbst**.
5. **Fertig.** Der Browser öffnet sich mit der Übersicht, und auf dem Desktop
   liegt jetzt die Verknüpfung **„Streaming-Info"**.

Das Programm liegt danach unter `%USERPROFILE%\streaming-info`. Die
heruntergeladene `start.bat` in `Downloads` brauchst du nicht mehr.

### Linux

1. **Terminal öffnen** und diese drei Zeilen nacheinander ausführen:

```bash
curl -fsSL -O https://github.com/CrazyJimPro/streaming-info/raw/main/start.sh
chmod +x start.sh
./start.sh
```

2. **Warten.** Fehlt Python oder ein Zubehörpaket, installiert das Skript es
   nach und **fragt dabei nach deinem Passwort** (`sudo`). Beim allerersten
   Mal dauert alles zusammen etwa 2–5 Minuten.
3. **Fertig.** Der Browser öffnet sich mit der Übersicht, und auf dem Desktop
   liegt die Verknüpfung **„Streaming-Info"**.

Das Programm liegt danach unter `~/streaming-info`. Die heruntergeladene
`start.sh` brauchst du nicht mehr.

> **Wichtig beim allerersten Mal unter Linux:** Führe `start.sh` einmal im
> **Terminal** aus, nicht per Doppelklick. Nur dort kann die Passwortabfrage
> erscheinen, falls noch etwas nachinstalliert werden muss. Ab dem zweiten Mal
> geht die Desktop-Verknüpfung.

## Schritt 3: Schlüssel eintragen

Jetzt ist die App offen, zeigt aber noch keine Titel — ihr fehlt der
Schlüssel aus Schritt 1.

1. Oben rechts auf **„Einstellungen"** klicken.
2. Ganz oben im Feld **TMDB-API-Schlüssel** den Schlüssel einfügen.
3. Unten auf **„Speichern"** klicken.

Die Daten werden danach automatisch im Hintergrund geholt (ein paar
Sekunden), und die Übersicht füllt sich von selbst. **Fertig eingerichtet.**

---

# Starten und beenden

**Starten:** Doppelklick auf die Desktop-Verknüpfung **„Streaming-Info"** —
unter Windows wie unter Linux. Es öffnet sich **kein** schwarzes Fenster; nach
ein paar Sekunden geht der Browser auf.

Bei jedem Start passiert automatisch:

1. Es wird geprüft, ob es eine **neuere Version** gibt, und falls ja, wird sie
   installiert. Deine Einstellungen und deine Merkliste bleiben dabei
   unangetastet.
2. Die **Termine werden frisch geholt** (wenige Sekunden).
3. Der Browser öffnet die Übersicht.

Läuft die App schon, startet ein erneuter Klick nichts doppelt — er frischt
nur die Daten auf und holt das Browserfenster zurück.

**Beenden:** Oben auf der Seite den Knopf **„Beenden"** anklicken. Erst dann
läuft nichts mehr im Hintergrund. Nur das Browserfenster zu schließen genügt
**nicht** — die App läuft dann weiter.

**Welche Version läuft?** Oben in der Kopfzeile steht ein kleines Abzeichen,
z.B. `v0.4.1`.

---

# Suche: Wo läuft das?

Du suchst einen Film oder eine Serie und weißt nicht, wo sie läuft — oder ob
überhaupt?

1. Oben auf der Startseite in das Suchfeld den Titel eintippen.
2. **Suchen** klicken (oder Enter).
3. Zu jedem Treffer steht, wo er in Deutschland abrufbar ist, getrennt nach
   **Im Abo**, **Kostenlos**, **Gratis mit Werbung**, **Leihen** und **Kaufen**.

Gefällt dir ein Treffer, setzt **⭐ Merken** ihn direkt auf die Merkliste — 
ohne Umweg über die Einstellungen. Danach steht er ganz oben auf der Startseite, 
sobald TMDB einen Starttermin kennt (sonst mit „Noch kein Termin bekannt“). 
Wieder entfernen geht mit **Nicht mehr merken** — an dieser Stelle in der Suche
genauso wie direkt an der Karte in der Merkliste auf der Startseite (und weiterhin
in den Einstellungen).

Gesucht wird bei **allen** Anbietern, die TMDB kennt — nicht nur bei den
sieben aus den Einstellungen. Deine eigenen sieben sind farbig, alle anderen
(Google Play, maxdome, Videoload …) grau. Die Auswahl in den Einstellungen
spielt hier keine Rolle.

**„Derzeit bei keinem Anbieter in Deutschland geführt"** heißt: TMDB kennt
dafür aktuell keinen Anbieter. Der Titel kann trotzdem bald starten — dann ist
die [Merkliste](#merkliste-bestimmte-titel-im-blick-behalten) der richtige Ort.
Die Verfügbarkeit kommt von JustWatch über TMDB und kann ein paar Tage
hinterherhinken.

---

# Merkliste: bestimmte Titel im Blick behalten

Die Merkliste ist für Serien und Filme, die du auf keinen Fall verpassen
willst. Gemerkte Titel bekommen **einen eigenen Abschnitt ganz oben** und
werden einzeln bei TMDB abgefragt — ohne jeden Filter.

### So trägst du etwas ein

1. Oben rechts auf **„Einstellungen"**.
2. Zum Abschnitt **„Merkliste"** herunterscrollen.
3. In das Suchfeld den Titel tippen, z.B. `Reacher`. Während des Tippens
   erscheinen Vorschläge mit Poster und Jahr.
4. Den richtigen Treffer **anklicken** — er wandert in die Liste darunter.
5. Ganz unten auf **„Speichern"** klicken. **Ohne diesen Klick ist nichts
   gespeichert.**

Zum Entfernen: in der Liste beim Titel auf *entfernen* klicken, dann wieder
*Speichern*.

### Was du erwarten kannst

Ein gemerkter Titel wird **immer** angezeigt — auch wenn sein Genre
abgewählt ist, sein Anbieter nicht ausgewählt wurde oder der Start weit hinter
deinem Vorschau-Zeitraum liegt. Startet eine gemerkte Serie erst in einem
halben Jahr, steht sie trotzdem da.

**Wichtig, damit du nicht unnötig suchst:** Für viele bekannte Serien führt
TMDB schlicht **noch gar kein Startdatum**. Solche Titel erscheinen dann mit
dem Vermerk *„Noch kein Termin bekannt"*. Das ist kein Fehler — sobald der
Sender einen Termin nennt, taucht er von selbst auf. Geprüft wurde das unter
anderem bei Stranger Things, Wednesday, The Boys und Bridgerton: alle ohne
Termin in der TMDB-Datenbank.

### Titel ausblenden

Das Gegenstück: Auf jeder Karte in der Übersicht gibt es **„Ausblenden"**.
Damit verschwindet ein Titel dauerhaft aus der Liste. Rückgängig machst du das
unter *Einstellungen → Ausgeblendete Titel → entfernen → Speichern*.

---

# Sicherung erstellen

Deine Merkliste und die ausgeblendeten Titel sind Handarbeit — das Einzige am
ganzen Tool, was sich nicht von selbst wiederbeschafft. Dafür gibt es die
Sicherung.

**In der Sicherung steckt:** Merkliste, ausgeblendete Titel, Vorschau-Zeitraum,
Anbieter- und Genre-Auswahl sowie dein TMDB-Schlüssel.
**Nicht drin:** die Termine selbst — die holt der nächste Abruf in Sekunden neu.

### So geht's

1. Oben rechts auf **„Einstellungen"**.
2. Falls du gerade etwas geändert hast: erst auf **„Speichern"**. Gesichert
   wird immer der *gespeicherte* Stand.
3. Ganz nach unten scrollen zum Abschnitt **„Sicherung"**.
4. Auf **„Sicherung erstellen"** klicken.

Der Browser lädt eine Datei namens `streaming-info-2026-09-28.json`
herunter — normalerweise in deinen Ordner *Downloads*. Das ist die
komplette Sicherung, mehr braucht es nicht.

> **Eine Warnung dazu:** In der Datei steht auch dein TMDB-Schlüssel. Sie ist
> zum Mitnehmen auf deine eigenen Geräte gedacht — gib sie niemandem weiter.

**Wann sichern?** Immer dann, wenn du deine Merkliste spürbar erweitert hast.
Für ein Update brauchst du **keine** Sicherung: Einstellungen und Schlüssel
werden beim Aktualisieren nicht angefasst.

---

# Sicherung einspielen

Damit holst du deine Liste zurück — auf denselben Rechner nach einem
Missgeschick oder auf einen neuen.

### So geht's

1. Oben rechts auf **„Einstellungen"**.
2. Ganz nach unten zum Abschnitt **„Sicherung einspielen"**.
3. Auf **„Datei auswählen"** klicken und deine `streaming-info-….json`
   heraussuchen. Sie darf überall liegen: *Downloads*, USB-Stick,
   Netzlaufwerk — es öffnet sich der normale Dateidialog deines Systems.
4. Auf **„Sicherung einspielen"** klicken und die Rückfrage bestätigen.

Oben erscheint eine grüne Meldung, was übernommen wurde, zum Beispiel:
*„7 gemerkte Titel, 3 ausgeblendet, TMDB-Schlüssel übernommen"*.

### Das Sicherheitsnetz

Bevor etwas ersetzt wird, legt das Tool deinen **bisherigen** Stand
automatisch als `config/vor-wiederherstellung-<Zeit>.json` ab — in demselben
Format. Hast du also aus Versehen die falsche Datei erwischt, kannst du diese
Kopie genauso wieder einspielen und bist zurück, wo du warst. Die letzten zehn
dieser Kopien bleiben liegen.

Eine Datei, die gar keine Streaming-Info-Sicherung ist oder aus einer
**neueren** Programmversion stammt, wird abgelehnt — deine Einstellungen
bleiben dann unberührt.

### Umzug auf einen neuen Rechner

1. Auf dem alten Rechner eine [Sicherung erstellen](#sicherung-erstellen).
2. Die Datei auf einen USB-Stick kopieren (oder ins Netzlaufwerk, per Mail an
   dich selbst, wie du magst).
3. Auf dem neuen Rechner die [Einrichtung](#schritt-2-installieren) machen.
4. Die Startseite weist dort von sich aus darauf hin, dass sich eine Sicherung
   einspielen lässt — dem Link folgen oder direkt in die Einstellungen gehen
   und die Datei einspielen.

Den TMDB-Schlüssel musst du dann **nicht** neu eintragen, er kommt aus der
Sicherung mit.

---

# Weitere Einstellungen

Alles unter **„Einstellungen"**; nach jeder Änderung unten auf **„Speichern"**
klicken. Jede Speicherung holt die Daten sofort neu.

- **Vorschau-Zeitraum** — wie viele Wochen im Voraus angezeigt werden.
  Je weiter, desto mehr steht drin; sehr weit im Voraus wird allerdings nur
  noch wenig angekündigt.
- **Streaming-Anbieter** — welche der sieben Anbieter überhaupt abgefragt
  werden. Wer kein Paramount+ hat, nimmt das Häkchen einfach raus.
- **Genres** — Einschränkung auf bestimmte Genres. **Kein Häkchen = alle
  Genres.**
- **TMDB-API-Schlüssel** — zum Ändern einen neuen eintragen. Lässt du das Feld
  leer, bleibt der bisherige erhalten.

### Warum nicht *alles* angezeigt wird

TMDB meldet für Deutschland weit mehr Starts, als für einen Menschen
interessant sind — überwiegend Festival-Einzelvorführungen und Titel einzelner
Ländermärkte. Gefiltert wird deshalb nach **Popularität** plus dem
Vorhandensein eines Posters.

Der naheliegendere Filter über die Zahl der Bewertungen funktioniert hier
prinzipbedingt nicht: Angekündigtes ist noch von niemandem bewertet worden. In
einem Vier-Wochen-Fenster kamen ganze zwei Kinostarts über diese Schwelle —
durchgefallen wären ausgerechnet Titel wie *Street Fighter* oder *Clayface*.

Fehlen dir Titel, die dort hingehören, oder steht zu viel Unbekanntes drin:
Die Schwellen stehen als `MIN_POPULARITAET_*` oben in
[`scraper/tmdb.py`](scraper/tmdb.py), mit den gemessenen Werten dokumentiert.

### Eine bekannte Einschränkung

Bei kommenden **Filmen** nennt TMDB zwar den Termin, aber **keine Plattform**.
Deshalb stehen sie im eigenen Abschnitt „Digital" ohne Anbieter-Logo — geraten
wird nichts. Bei **Serien** ist die Zuordnung dagegen sauber, weil sie über die
TV-Netzwerke des jeweiligen Anbieters läuft. Für WOW/Sky bleibt die Ausbeute
dünn, dort führt TMDB nur das Netzwerk Sky Deutschland.

Deutsche **Fernseh-Sendetermine** (Sat.1, RTL, ZDF …) kann das Tool nicht
anzeigen: TMDB führt pro Serienfolge nur ein einziges Ausstrahlungsdatum,
meist das des US-Originalsenders. Über die Merkliste bekommst du diesen
Originaltermin — als Vorwarnung brauchbar, das deutsche Fernsehen zieht später
nach.

---

# Wenn etwas nicht klappt

### Der Browser zeigt „Verbindung fehlgeschlagen"

Dann ist die App nicht gestartet. Seit Version 0.4.1 bekommst du in dem Fall
ein Hinweisfenster mit dem tatsächlichen Grund. Kommt keins, schau selbst ins
Protokoll:

- **Windows:** `%USERPROFILE%\streaming-info\logs\webapp.log`
- **Linux:** `~/streaming-info/logs/webapp.log`

Dort steht die letzte Fehlermeldung im Klartext. In `logs/start.log` steht
ergänzend, wie weit das Startskript gekommen ist.

### Linux: Es passiert nichts oder es fehlt etwas

Starte einmal **im Terminal** statt per Doppelklick:

```bash
~/streaming-info/start.sh
```

Nur dort siehst du alle Meldungen, und nur dort kann die Passwortabfrage
erscheinen, falls noch ein Paket nachinstalliert werden muss. Wird ein
`sudo apt-get install …`-Befehl vorgeschlagen: einmal ausführen und
`start.sh` erneut starten. Danach funktioniert die Desktop-Verknüpfung wieder.

### Die Übersicht bleibt leer

- Ist der **TMDB-Schlüssel** eingetragen? Fehlt er, steht oben ein Hinweis.
- Ist der **Vorschau-Zeitraum** sehr kurz? Probiere 8 oder 10 Wochen.
- Sind alle **Genres** abgewählt bis auf wenige? Kein Häkchen = alle.
- Steht bei den Anbietern oben ein **Fehler**-Abzeichen? Dann kam der Abruf
  nicht durch — meist ein Netzwerkproblem, einmal „Jetzt aktualisieren"
  drücken.

### Ein gemerkter Titel taucht nicht auf

Steht bei ihm *„Noch kein Termin bekannt"*, kennt TMDB schlicht kein Datum —
siehe [Merkliste](#merkliste-bestimmte-titel-im-blick-behalten). Fehlt er ganz,
ist er vermutlich nicht gespeichert: nach dem Hinzufügen muss unten
**„Speichern"** geklickt werden.

---

# Technisches

## Wo liegt was?

Alles unterhalb von `%USERPROFILE%\streaming-info` bzw. `~/streaming-info`:

| Pfad | Inhalt |
|---|---|
| `config/config.json` | der TMDB-API-Schlüssel (bleibt bei Updates erhalten) |
| `config/einstellungen.json` | Zeitraum, Anbieter/Genre-Auswahl, Merkliste, ausgeblendete Titel (bleibt bei Updates erhalten) |
| `config/vor-wiederherstellung-*.json` | der Stand vor dem letzten Einspielen einer Sicherung (die letzten zehn) |
| `data/streaming.db` | die geholten Titel und ihre angekündigten Starttermine |
| `logs/start.log` | Meldungen des Startskripts |
| `logs/webapp.log` | Meldungen der Web-App — **hier stehen Abstürze** |
| `logs/scraper.log` | Protokoll der Datenabrufe |
| `VERSION` | installierte Versionsnummer |

## Was das Startskript automatisch erledigt

- lädt beim allerersten Mal den Rest des Projekts von GitHub nach
- prüft, ob Python samt Zubehör vorhanden ist — falls nicht, installiert es
  nach (Windows: `winget`, Linux: `apt-get`, dort mit `sudo`)
- legt eine virtuelle Umgebung an und installiert die Abhängigkeiten;
  ist eine frühere Einrichtung abgebrochen, wird das erkannt und nachgeholt
- legt die Desktop-Verknüpfung an, falls noch keine da ist
- startet die Web-App ohne Fenster und öffnet den Browser, sobald sie
  antwortet — und zeigt einen Hinweis, falls sie es nicht tut

## Updates

Bei jedem Start wird die Datei `VERSION` mit der auf GitHub verglichen.
Ist die dort **wirklich neuer**, wird der komplette Code aufgefrischt und die
App neu gestartet. Nicht angefasst werden dabei `config/config.json` und
`config/einstellungen.json` — Schlüssel, Merkliste und Einstellungen überleben
jedes Update.

Die App läuft auf **Port 5100**. Datenquelle ist durchgehend
[TMDB](https://www.themoviedb.org); der Schlüssel bleibt lokal und wird
nirgendwo hochgeladen.

*(Wer lieber das ganze Repository klont oder als ZIP lädt, kann das tun —
`start.bat`/`start.sh` erkennen dann, dass der Rest schon da ist, und
überspringen den Download.)*
