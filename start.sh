#!/usr/bin/env bash
# Einzige Datei, die man ausfuehren muss: installiert/richtet alles automatisch
# ein (Python-Check, venv, Abhaengigkeiten, erster Datenabruf) und startet
# danach die Web-App. Bei jedem weiteren Aufruf werden bereits erledigte
# Schritte uebersprungen. Nach dem bewaehrten Muster von
# reality-tv-programm/start.sh.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
SELBST="$(pwd)/$(basename "${BASH_SOURCE[0]}")"

# Alles, was ab hier ausgegeben wird, landet zusaetzlich in logs/start.log -
# wichtig, wenn per Desktop-Verknuepfung ohne sichtbares Terminal gestartet
# wird (dann gibt es sonst gar keine Rueckmeldung mehr bei einem Fehler).
mkdir -p logs
exec > >(tee logs/start.log) 2>&1

echo "=== Streaming-Info ==="
echo

ZIEL_ORDNER="$HOME/streaming-info"

# Laedt eine Datei aus dem Repository nach $2 (leise, curl oder wget).
hole_datei() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$2" "https://raw.githubusercontent.com/CrazyJimPro/streaming-info/main/$1" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$2" "https://raw.githubusercontent.com/CrazyJimPro/streaming-info/main/$1" 2>/dev/null
    fi
}

# Beendet eine noch laufende Instanz - erst hoeflich ueber /beenden, danach
# notfalls hart.
alte_instanz_beenden() {
    curl -s -o /dev/null --connect-timeout 1 http://127.0.0.1:5100/ 2>/dev/null || return 0
    echo "Beende die noch laufende Version (sonst liefe der alte Code weiter)..."
    curl -s -o /dev/null -X POST --max-time 10 http://127.0.0.1:5100/beenden 2>/dev/null || true
    for _ in $(seq 1 10); do
        curl -s -o /dev/null --connect-timeout 1 http://127.0.0.1:5100/ 2>/dev/null || return 0
        sleep 1
    done
    pkill -f "webapp/app.py" 2>/dev/null || true
    sleep 1
}

# --- -1. Pruefen, ob auf GitHub eine neuere Version liegt. Verglichen wird
# die Versionsnummer aus der Datei VERSION - und aufgefrischt wird nur, wenn
# die dort WIRKLICH neuer ist. Wird aufgefrischt, kommen alle Dateien ohnehin
# in ihrer neuen Fassung mit. ---
NEUERE_VERSION_GEFUNDEN=""

# Rechnet "1.4.7" in eine vergleichbare Zahl um; leer, wenn die Angabe nicht
# dem Muster Zahl.Zahl.Zahl entspricht.
version_zu_zahl() {
    case "$1" in
        ''|*[!0-9.]*) return 1 ;;
    esac
    _rest="${1#*.}"
    _a="${1%%.*}"; _b="${_rest%%.*}"; _c="${_rest#*.}"
    case "$_c" in ''|*[!0-9]*) return 1 ;; esac
    case "$_b" in ''|*[!0-9]*) return 1 ;; esac
    case "$_a" in ''|*[!0-9]*) return 1 ;; esac
    echo $(( _a * 1000000 + _b * 1000 + _c ))
}

TMP_VER="$(mktemp)"
# Der angehaengte Zufallswert umgeht den Zwischenspeicher von GitHub.
hole_datei "VERSION?nocache=$$$(date +%s)" "$TMP_VER"
if [ -s "$TMP_VER" ]; then
    VERSION_NEU="$(tr -d '\r' < "$TMP_VER" | head -1)"
    if [ -f VERSION ]; then
        VERSION_LOKAL="$(tr -d '\r' < VERSION | head -1)"
        ZAHL_NEU="$(version_zu_zahl "$VERSION_NEU" || true)"
        ZAHL_LOKAL="$(version_zu_zahl "$VERSION_LOKAL" || true)"
        if [ -n "$ZAHL_NEU" ] && [ -n "$ZAHL_LOKAL" ] && [ "$ZAHL_NEU" -gt "$ZAHL_LOKAL" ]; then
            echo "Neue Version verfuegbar: $VERSION_NEU (installiert: $VERSION_LOKAL)"
            NEUERE_VERSION_GEFUNDEN=1
        fi
    elif [ -f requirements.txt ]; then
        echo "Installierte Fassung ohne Versionsangabe - frische auf $VERSION_NEU auf."
        NEUERE_VERSION_GEFUNDEN=1
    fi
else
    echo "Versionspruefung fehlgeschlagen (kein Internet oder Netzwerk blockiert) - fahre mit der vorhandenen Version fort."
fi
rm -f "$TMP_VER"

# --- 0. Projektordner bestimmen und bei Bedarf (neu) laden ---
# WICHTIG: Laeuft dieses Skript AUS dem Ordner, der aufgefrischt wird, darf
# es sich dabei nicht selbst ueberschreiben - siehe start.bat fuer die
# ausfuehrliche Begruendung (gilt hier genauso).
if [ -f "requirements.txt" ]; then
    PROJEKT_ZIEL="$(pwd)"
    EIGENER_ORDNER=1
else
    PROJEKT_ZIEL="$ZIEL_ORDNER"
    EIGENER_ORDNER=""
fi

MUSS_LADEN=""
[ -f "requirements.txt" ] || MUSS_LADEN=1
[ -n "$NEUERE_VERSION_GEFUNDEN" ] && MUSS_LADEN=1

if [ -n "$MUSS_LADEN" ]; then
    echo "Lade aktuellen Projektstand von GitHub (Code + Web-App werden aufgefrischt)..."
    TMP_TAR="$(mktemp)"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$TMP_TAR" "https://github.com/CrazyJimPro/streaming-info/archive/refs/heads/main.tar.gz"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$TMP_TAR" "https://github.com/CrazyJimPro/streaming-info/archive/refs/heads/main.tar.gz"
    else
        echo "Fehler: weder curl noch wget gefunden."
        echo "Bitte eines davon installieren oder das Repo manuell laden:"
        echo "https://github.com/CrazyJimPro/streaming-info"
        exit 1
    fi
    if [ ! -s "$TMP_TAR" ]; then
        echo "Fehler beim Herunterladen. Bitte Internetverbindung pruefen,"
        echo "oder das Repo manuell laden: https://github.com/CrazyJimPro/streaming-info"
        rm -f "$TMP_TAR"
        exit 1
    fi
    mkdir -p "$PROJEKT_ZIEL"
    TMP_DIR="$(mktemp -d)"
    tar -xzf "$TMP_TAR" -C "$TMP_DIR" --strip-components=1
    rm -f "$TMP_TAR"
    if [ -n "$EIGENER_ORDNER" ]; then
        NEUSTART_DATEI="$(mktemp /tmp/si_start_neu.XXXXXX.sh)"
        cp "$TMP_DIR/start.sh" "$NEUSTART_DATEI"
        chmod +x "$NEUSTART_DATEI"
        rm -f "$TMP_DIR/start.sh"
    else
        NEUSTART_DATEI="$PROJEKT_ZIEL/start.sh"
    fi
    cp -r "$TMP_DIR/." "$PROJEKT_ZIEL/"
    rm -rf "$TMP_DIR"
    # Ausfuehrbar-Recht sicherstellen: aus einem heruntergeladenen Archiv kann
    # es fehlen, und dann startet die Desktop-Verknuepfung nicht mehr.
    chmod +x "$PROJEKT_ZIEL/start.sh" 2>/dev/null || true

    if [ "$(pwd)" != "$PROJEKT_ZIEL" ]; then
        echo "Projekt liegt jetzt unter: $PROJEKT_ZIEL"
    else
        echo "Projekt aufgefrischt."
    fi
    alte_instanz_beenden

    echo "Starte neu ..."
    echo
    chmod +x "$NEUSTART_DATEI"
    exec "$NEUSTART_DATEI" "$@"
fi

# --- 0.5 Welcher Stand laeuft hier? ---
if [ -f VERSION ]; then
    echo "Version: $(cat VERSION)"
    echo
fi

# --- 1. Python3 vorhanden? Sonst automatisch per apt installieren ---
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 wurde nicht gefunden. Versuche automatische Installation..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-venv python3-pip
    else
        echo "Fehler: kein unterstuetzter Paketmanager (apt-get) gefunden."
        echo "Bitte Python 3 manuell installieren und dieses Skript erneut starten."
        exit 1
    fi
fi

# venv-Modul ist auf manchen Distros ein separates Paket
if ! python3 -m venv --help >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        echo "Installiere python3-venv nach..."
        sudo apt-get update -qq && sudo apt-get install -y python3-venv
    fi
fi

# --- 2. Virtuelle Umgebung + Abhaengigkeiten, falls noch nicht vorhanden ---
if [ ! -x "venv/bin/python" ]; then
    echo "Richte virtuelle Umgebung ein (einmalig, dauert etwas)..."
    python3 -m venv venv || { echo "Fehler beim Anlegen der virtuellen Umgebung."; exit 1; }
    ./venv/bin/pip install --quiet --upgrade pip || { echo "Fehler beim pip-Upgrade."; exit 1; }
    ./venv/bin/pip install --quiet -r requirements.txt || { echo "Fehler beim Installieren der Abhaengigkeiten."; exit 1; }
fi

PROJEKT_PFAD="$(pwd)"
VENV_PYTHON="$PROJEKT_PFAD/venv/bin/python"

# --- 3. Desktop-Verknuepfung anlegen, falls noch nicht vorhanden - startet
# kuenftig per Doppelklick ohne sichtbares Terminal (Terminal=false), alle
# Meldungen landen trotzdem in logs/start.log (siehe oben). ---
DESKTOP_ORDNER="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
DESKTOP_DATEI="$DESKTOP_ORDNER/streaming-info.desktop"
if [ -d "$DESKTOP_ORDNER" ] && [ ! -f "$DESKTOP_DATEI" ]; then
    echo "Richte Desktop-Verknuepfung ein..."
    cat > "$DESKTOP_DATEI" <<EOF
[Desktop Entry]
Type=Application
Name=Streaming-Info
Comment=Streaming-Info starten
Exec=$PROJEKT_PFAD/start.sh
Path=$PROJEKT_PFAD
Terminal=false
Icon=video-television
EOF
    chmod +x "$DESKTOP_DATEI"
    # Manche Dateimanager (z.B. GNOME Files) verlangen beim ersten Start
    # zusaetzlich eine "Vertrauen"-Markierung, sonst kommt eine Rueckfrage.
    gio set "$DESKTOP_DATEI" metadata::trusted true 2>/dev/null || true
fi

# --- 4. Web-App starten und Browser oeffnen (nur falls nicht schon eine
# laeuft) ---
if curl -s -o /dev/null --connect-timeout 1 http://127.0.0.1:5100/ 2>/dev/null; then
    echo "Web-App laeuft bereits - stosse Aktualisierung an und oeffne Browser ..."
    curl -s -o /dev/null -X POST --max-time 10 http://127.0.0.1:5100/aktualisieren || true
    xdg-open http://127.0.0.1:5100 >/dev/null 2>&1 || true
    exit 0
fi

echo
echo "Oeffne http://127.0.0.1:5100 im Browser ..."
echo "Die Daten werden dabei im Hintergrund frisch geholt (2-5 Minuten),"
echo "die Seite aktualisiert sich von selbst, sobald der Lauf fertig ist."
echo "Die App laeuft im Hintergrund weiter, dieses Terminal wird nicht belegt."
echo "Zum Beenden den Knopf \"Beenden\" oben auf der Seite benutzen - danach"
echo "laeuft nichts mehr im Hintergrund."
echo
nohup "$VENV_PYTHON" webapp/app.py >> logs/webapp.log 2>&1 &
for _ in $(seq 1 20); do
    if curl -s -o /dev/null --connect-timeout 1 http://127.0.0.1:5100/ 2>/dev/null; then break; fi
    sleep 1
done
xdg-open http://127.0.0.1:5100 >/dev/null 2>&1 || true
