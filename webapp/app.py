"""Lokale Flask-Web-App: zeigt Kinostarts und neue Streaming-Titel an.

Start (aus dem Projektverzeichnis):
    python webapp/app.py
Danach im Browser: http://127.0.0.1:5000

Die Daten werden bei jedem Start der App einmal frisch geholt (im
Hintergrund, damit die Seite sofort da ist - ein TMDB-Scan dauert je nach
Anbindung 2-5 Minuten). Nach dem Vorbild von reality-tv-programm/webapp/app.py.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJEKT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJEKT_ROOT))

from flask import Flask, jsonify, redirect, render_template, request, url_for  # noqa: E402

from scraper.einstellungen import (  # noqa: E402
    lade_anbieter,
    lade_api_schluessel,
    lade_einstellungen,
    speichere_api_schluessel,
    speichere_einstellungen,
)
from scraper.base import TmdbFehler, neue_session  # noqa: E402
from scraper.filter import SPRACHNAMEN, filtere_zeilen  # noqa: E402
from scraper.sicherung import (  # noqa: E402
    SicherungsFehler,
    erstelle_sicherung,
    sicherungs_dateiname,
    spiele_sicherung_ein,
)
from scraper.storage import (  # noqa: E402
    DB_PFAD,
    hole_merkliste_eintraege,
    hole_quellen_status,
    hole_starts_im_zeitraum,
    hole_vorkommende_sprachen,
    init_db,
)
from scraper.tmdb import suche_titel, suche_verfuegbarkeit  # noqa: E402

app = Flask(__name__)

# Eine Sicherung ist wenige Kilobyte gross. Das Limit faengt nur den Fall ab,
# dass versehentlich etwas ganz anderes hochgeladen wird - ohne es wuerde
# Flask die Datei erst komplett annehmen und dann verwerfen.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

TMDB_POSTER_BASIS = "https://image.tmdb.org/t/p/w300"

VERALTET_AB_STUNDEN = 24

VERSION_PFAD = PROJEKT_ROOT / "VERSION"
LOG_PFAD = PROJEKT_ROOT / "logs" / "webapp.log"
GENRES_CACHE_PFAD = PROJEKT_ROOT / "data" / "genres.json"


def _version() -> str:
    try:
        return VERSION_PFAD.read_text(encoding="utf-8").strip() or "unbekannt"
    except OSError:
        return "unbekannt"


_scan_sperre = threading.Lock()
_scan_status: dict[str, object] = {"laeuft": False, "fehler": None, "fertig_am": None}
_laufender_prozess: subprocess.Popen | None = None


def _logging_einrichten() -> None:
    LOG_PFAD.parent.mkdir(parents=True, exist_ok=True)
    handler: list[logging.Handler] = [logging.FileHandler(LOG_PFAD, encoding="utf-8")]
    if sys.stderr is not None and getattr(sys.stderr, "isatty", lambda: False)():
        handler.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handler)

    def _unbehandelt(typ, wert, spur):
        logging.getLogger("webapp").critical("Unbehandelter Fehler", exc_info=(typ, wert, spur))

    sys.excepthook = _unbehandelt


@app.context_processor
def _vorlagen_kontext() -> dict:
    return {"version": _version()}


def _scanner_ausfuehren() -> None:
    """Fuehrt einen TMDB-Scan aus (dauert ca. 2-5 Minuten) und haelt das
    Ergebnis in _scan_status fest. Nutzt denselben Interpreter wie die
    Web-App (venv), damit start.bat/start.sh und der In-App-Aufruf denselben
    Codepfad benutzen."""
    global _laufender_prozess
    if not _scan_sperre.acquire(blocking=False):
        return
    try:
        _scan_status["laeuft"] = True
        _scan_status["fehler"] = None
        extra = {} if os.name == "nt" else {"start_new_session": True}
        _laufender_prozess = subprocess.Popen(
            [sys.executable, "-m", "scraper.run"],
            cwd=PROJEKT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **extra,
        )
        stdout, stderr = _laufender_prozess.communicate()
        if _laufender_prozess.returncode != 0:
            ausgabe = (stderr or stdout or "").strip()
            letzte_zeilen = " / ".join(ausgabe.splitlines()[-3:])
            _scan_status["fehler"] = letzte_zeilen or f"Scan endete mit Code {_laufender_prozess.returncode}"
    except Exception as exc:
        _scan_status["fehler"] = str(exc)
    finally:
        _laufender_prozess = None
        _scan_status["laeuft"] = False
        _scan_status["fertig_am"] = datetime.now().isoformat(timespec="seconds")
        _scan_sperre.release()


def _laufenden_scan_beenden() -> None:
    prozess = _laufender_prozess
    if prozess is None or prozess.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(prozess.pid)], capture_output=True, check=False)
        else:
            os.killpg(os.getpgid(prozess.pid), signal.SIGTERM)
    except Exception:
        try:
            prozess.kill()
        except Exception:
            pass


def _scan_im_hintergrund_starten() -> bool:
    if _scan_status["laeuft"]:
        return False
    threading.Thread(target=_scanner_ausfuehren, name="si-scan", daemon=True).start()
    return True


def _alter_text(alter: timedelta) -> str:
    tage = alter.days
    stunden = int(alter.total_seconds() // 3600)
    if tage >= 1:
        return f"vor {tage} Tag" + ("en" if tage != 1 else "")
    if stunden >= 1:
        return f"vor {stunden} Stunde" + ("n" if stunden != 1 else "")
    return "gerade eben"


def _status_aufbereiten(status: list[dict]) -> list[dict]:
    jetzt = datetime.now()
    aufbereitet = []
    for roh_eintrag in status:
        eintrag = dict(roh_eintrag)
        eintrag["erfolg_text"] = None
        eintrag["alter_text"] = None
        eintrag["veraltet"] = False
        roh = eintrag.get("letzter_erfolg_am")
        if roh:
            try:
                zeitpunkt = datetime.fromisoformat(str(roh))
            except ValueError:
                eintrag["erfolg_text"] = str(roh)
            else:
                eintrag["erfolg_text"] = zeitpunkt.strftime("%d.%m.%Y, %H:%M")
                alter = jetzt - zeitpunkt
                eintrag["veraltet"] = alter > timedelta(hours=VERALTET_AB_STUNDEN)
                eintrag["alter_text"] = _alter_text(alter)
        aufbereitet.append(eintrag)
    return aufbereitet


def _anbieter_karte() -> dict[str, dict]:
    return {a["schluessel"]: a for a in lade_anbieter()}


def _poster_url(poster_pfad: str | None) -> str | None:
    return f"{TMDB_POSTER_BASIS}{poster_pfad}" if poster_pfad else None


def _datum_lesbar(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso


def _tage_bis(iso: str | None, heute: date) -> int | None:
    if not iso:
        return None
    try:
        return (datetime.strptime(iso, "%Y-%m-%d").date() - heute).days
    except ValueError:
        return None


def _countdown_text(tage: int | None) -> str:
    """Kurze Angabe, wie weit der Start noch weg ist - das ist bei einer
    Vorschau die eigentlich interessante Information."""
    if tage is None:
        return ""
    if tage <= 0:
        return "heute"
    if tage == 1:
        return "morgen"
    if tage < 7:
        return f"in {tage} Tagen"
    if tage < 14:
        return "nächste Woche"
    return f"in {tage // 7} Wochen"


def _starts_aufbereiten(zeilen: list[dict], anbieter_karte: dict[str, dict], heute: date) -> list[dict]:
    """Macht aus Start-Zeilen Anzeigeeintraege und fasst denselben Titel
    zusammen, wenn er am selben Tag bei mehreren Anbietern anlaeuft (dann eine
    Kachel mit mehreren Badges statt zwei fast gleichen Kacheln)."""
    gruppiert: dict[tuple, dict] = {}
    for zeile in zeilen:
        schluessel = (zeile["tmdb_id"], zeile["medientyp"], zeile["startdatum"])
        eintrag = gruppiert.setdefault(schluessel, {**zeile, "anbieter_liste": []})
        info = anbieter_karte.get(zeile["anbieter"])
        eintrag["anbieter_liste"].append(
            {
                "schluessel": zeile["anbieter"],
                "name": info["name"] if info else zeile["anbieter"],
                "farbe": info["farbe"] if info else "#888",
            }
        )
    ergebnis = list(gruppiert.values())
    for eintrag in ergebnis:
        tage = _tage_bis(eintrag.get("startdatum"), heute)
        eintrag["poster_url"] = _poster_url(eintrag.get("poster_pfad"))
        eintrag["start_lesbar"] = _datum_lesbar(eintrag.get("startdatum"))
        eintrag["countdown"] = _countdown_text(tage)
        # Staffelstarts brauchen den Zusatz, sonst sieht die Kachel aus wie
        # eine brandneue Serie.
        if eintrag.get("art") == "staffel" and eintrag.get("staffel"):
            eintrag["zusatz"] = f"Staffel {eintrag['staffel']}"
        elif eintrag.get("art") == "serie":
            eintrag["zusatz"] = "neue Serie"
        else:
            eintrag["zusatz"] = ""
    ergebnis.sort(key=lambda e: e["startdatum"])
    return ergebnis


DIGITAL_FARBE = "#6b7280"


def _schnellfilter_quellen(
    aktive: list[str], anbieter_karte: dict[str, dict], abschnitte: list[list[dict]]
) -> list[dict]:
    """Knoepfe fuer den Schnellfilter auf der Startseite: die in den
    Einstellungen aktiven Anbieter in der Reihenfolge von anbieter.json, dann
    Kino und Digital - je mit der Zahl der Karten, die sie gerade tragen."""
    anzahl: dict[str, int] = defaultdict(int)
    for eintraege in abschnitte:
        for eintrag in eintraege:
            for schluessel in {a["schluessel"] for a in eintrag["anbieter_liste"]}:
                anzahl[schluessel] += 1
    quellen = [
        {"schluessel": s, "name": a["name"], "farbe": a["farbe"], "anzahl": anzahl[s]}
        for s, a in anbieter_karte.items()
        if s != "kino" and s in aktive
    ]
    kino = anbieter_karte.get("kino", {})
    quellen.append({"schluessel": "kino", "name": "Kino", "farbe": kino.get("farbe", "#e63946"), "anzahl": anzahl["kino"]})
    quellen.append({"schluessel": "digital", "name": "Digital", "farbe": DIGITAL_FARBE, "anzahl": anzahl["digital"]})
    return quellen


def _merkliste_aufbereiten(zeilen: list[dict], heute: date) -> list[dict]:
    """Wie _starts_aufbereiten, aber fuer Eintraege, die auch ganz ohne Termin
    angezeigt werden."""
    for eintrag in zeilen:
        eintrag["poster_url"] = _poster_url(eintrag.get("poster_pfad"))
        eintrag["anbieter_liste"] = []
        datum = eintrag.get("startdatum")
        if datum:
            eintrag["start_lesbar"] = _datum_lesbar(datum)
            eintrag["countdown"] = _countdown_text(_tage_bis(datum, heute))
            eintrag["zusatz"] = f"Staffel {eintrag['staffel']}" if eintrag.get("staffel") else ""
        else:
            eintrag["start_lesbar"] = "Noch kein Termin bekannt"
            eintrag["countdown"] = ""
            eintrag["zusatz"] = ""
    return zeilen


@app.route("/")
def index():
    einstellungen = lade_einstellungen()
    anbieter_karte = _anbieter_karte()
    heute = date.today()
    zeitraum_wochen = einstellungen.get("zeitraum_wochen", 8)
    bis = heute + timedelta(weeks=zeitraum_wochen)

    # Nur aktive Anbieter zeigen - der Scan holt zwar nur diese, aber nach dem
    # Abwaehlen eines Anbieters lagen dessen Starts sonst noch in der Datenbank.
    aktive = set(einstellungen.get("aktive_anbieter", []))

    streaming_rows = [
        z
        for z in hole_starts_im_zeitraum(heute, bis, ("serie", "staffel"), db_pfad=DB_PFAD)
        if z["anbieter"] in aktive
    ]
    streaming = _starts_aufbereiten(filtere_zeilen(streaming_rows, einstellungen), anbieter_karte, heute)

    digital_rows = hole_starts_im_zeitraum(heute, bis, ("digital",), db_pfad=DB_PFAD)
    digital = _starts_aufbereiten(filtere_zeilen(digital_rows, einstellungen), anbieter_karte, heute)

    kino_rows = hole_starts_im_zeitraum(heute, bis, ("kino",), db_pfad=DB_PFAD)
    kino = _starts_aufbereiten(filtere_zeilen(kino_rows, einstellungen), anbieter_karte, heute)

    # Merkliste bewusst ungefiltert und ohne Zeitraumgrenze: gemerkt ist
    # gemerkt. Auch Titel ohne bekannten Termin bleiben sichtbar, sonst wirkt
    # das Merken wie wirkungslos.
    merkliste = _merkliste_aufbereiten(
        hole_merkliste_eintraege(einstellungen.get("merkliste", []), db_pfad=DB_PFAD), heute
    )

    status = _status_aufbereiten(hole_quellen_status(db_pfad=DB_PFAD))
    api_schluessel_fehlt = not lade_api_schluessel()

    # Einmaliger Wegweiser nach einer frischen Installation - das Gegenstueck
    # zur Frage "Daten aus einer Sicherung uebernehmen?", die beim Abo-Tracker
    # das Installationsprogramm stellt. Hier gibt es keines: die App fragt
    # deshalb selbst, und zwar sichtbar auf der Startseite, weil der uebliche
    # Start ueber die Desktop-Verknuepfung gar kein Fenster zeigt, in dem eine
    # Konsolenfrage auffallen wuerde.
    # Der Merker steht in den Einstellungen selbst, nicht im Arbeitsspeicher:
    # sonst waere der Hinweis nach dem ersten Neustart weg, obwohl noch nichts
    # eingerichtet ist. Die Pruefung auf leere Listen faengt zusaetzlich
    # bestehende Installationen ab, die den Merker noch nicht kennen.
    einrichtung_offen = (
        not einstellungen.get("einrichtung_erledigt")
        and not einstellungen.get("merkliste")
        and not einstellungen.get("ausgeblendet")
    )

    return render_template(
        "index.html",
        streaming=streaming,
        digital=digital,
        kino=kino,
        merkliste=merkliste,
        schnellfilter_quellen=_schnellfilter_quellen(
            einstellungen.get("aktive_anbieter", []), anbieter_karte, [streaming, kino, digital]
        ),
        gemerkt_ids={(m["tmdb_id"], m["medientyp"]) for m in einstellungen.get("merkliste", [])},
        status=status,
        heute=heute,
        bis=bis,
        zeitraum_wochen=zeitraum_wochen,
        scan=_scan_status,
        api_schluessel_fehlt=api_schluessel_fehlt,
        einrichtung_offen=einrichtung_offen,
        kino_farbe=next((a["farbe"] for a in anbieter_karte.values() if a["schluessel"] == "kino"), "#e63946"),
    )


@app.route("/einrichtung-erledigt", methods=["POST"])
def einrichtung_erledigt():
    """Blendet den Wegweiser fuer frische Installationen dauerhaft aus."""
    daten = lade_einstellungen()
    daten["einrichtung_erledigt"] = True
    speichere_einstellungen(daten)
    return redirect(url_for("index"))


@app.route("/scan-status")
def scan_status():
    return jsonify(laeuft=bool(_scan_status["laeuft"]), fehler=_scan_status["fehler"])


@app.route("/aktualisieren", methods=["POST"])
def aktualisieren():
    _scan_im_hintergrund_starten()
    return redirect(url_for("index"))


@app.route("/beenden", methods=["POST"])
def beenden():
    def _stoppen() -> None:
        time.sleep(0.5)
        _laufenden_scan_beenden()
        os._exit(0)

    threading.Thread(target=_stoppen, name="si-stop", daemon=True).start()
    return render_template("beendet.html")


def _liste_aus_formular(praefix: str) -> list[dict]:
    return [
        {"tmdb_id": int(tmdb_id), "medientyp": medientyp, "titel": titel}
        for tmdb_id, medientyp, titel in zip(
            request.form.getlist(f"{praefix}_tmdb_id"),
            request.form.getlist(f"{praefix}_medientyp"),
            request.form.getlist(f"{praefix}_titel"),
        )
    ]


def _sprachauswahl(gewaehlt: list[str]) -> list[dict]:
    """Feste Sprachliste plus alles, was in den bevorstehenden Starts oder in
    der eigenen Auswahl vorkommt - nach Anzeigename sortiert, Deutsch und
    Englisch vorneweg, weil die fast jeder anhaken wird."""
    anzahl = hole_vorkommende_sprachen(date.today(), db_pfad=DB_PFAD)
    codes = set(SPRACHNAMEN) | set(anzahl) | set(gewaehlt)
    auswahl = [
        {"code": code, "name": SPRACHNAMEN.get(code, code), "anzahl": anzahl.get(code, 0)}
        for code in codes
    ]
    return sorted(auswahl, key=lambda s: (s["code"] not in ("de", "en"), s["code"] != "de", s["name"].lower()))


@app.route("/einstellungen", methods=["GET", "POST"])
def einstellungen_seite():
    daten = lade_einstellungen()
    alle_anbieter = lade_anbieter()
    genres: dict[int, str] = {}
    if GENRES_CACHE_PFAD.exists():
        roh = json.loads(GENRES_CACHE_PFAD.read_text(encoding="utf-8"))
        genres = {int(k): v for k, v in roh.items()}

    if request.method == "POST":
        daten["zeitraum_wochen"] = max(1, int(request.form.get("zeitraum_wochen", daten.get("zeitraum_wochen", 8))))
        daten["aktive_anbieter"] = request.form.getlist("aktive_anbieter")
        daten["aktive_genres"] = [int(g) for g in request.form.getlist("aktive_genres")]
        daten["sprachen"] = request.form.getlist("sprachen")

        # Merkliste/Ausblendliste: Titel per tmdb_id+medientyp+titel aus dem
        # Formular uebernehmen (siehe webapp/static/einstellungen.js).
        daten["merkliste"] = _liste_aus_formular("merk")
        daten["ausgeblendet"] = _liste_aus_formular("ausblend")

        api_schluessel = request.form.get("tmdb_api_key", "").strip()
        if api_schluessel:
            speichere_api_schluessel(api_schluessel)

        # Wer hier speichert, hat sich eingerichtet - der Wegweiser auf der
        # Startseite hat sich damit erledigt.
        daten["einrichtung_erledigt"] = True

        speichere_einstellungen(daten)
        _scan_im_hintergrund_starten()
        return redirect(url_for("einstellungen_seite", gespeichert=1))

    return render_template(
        "einstellungen.html",
        einstellungen=daten,
        anbieter=alle_anbieter,
        genres=sorted(genres.items(), key=lambda kv: kv[1]),
        sprachen=_sprachauswahl(daten.get("sprachen", [])),
        api_schluessel_vorhanden=bool(lade_api_schluessel()),
        gespeichert=request.args.get("gespeichert") == "1",
        eingespielt=request.args.get("eingespielt"),
        fehler=request.args.get("fehler"),
    )


@app.route("/sicherung")
def sicherung_herunterladen():
    """Laedt die persoenlichen Einstellungen als JSON-Datei herunter.

    Bewusst ein Download statt einer Datei irgendwo im Projektordner: so
    landet die Sicherung dort, wo der Browser hinspeichert, und laesst sich
    von dort auf einen USB-Stick oder einen anderen Rechner mitnehmen.
    """
    inhalt = json.dumps(erstelle_sicherung(_version()), ensure_ascii=False, indent=2) + "\n"
    return app.response_class(
        inhalt,
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{sicherungs_dateiname()}"',
            "Cache-Control": "no-store",
        },
    )


@app.route("/sicherung-einspielen", methods=["POST"])
def sicherung_einspielen():
    """Spielt eine hochgeladene Sicherungsdatei ein.

    Der Weg ueber den Datei-Dialog des Browsers ist Absicht: so laesst sich
    eine Sicherung von ueberall holen - Downloads, USB-Stick, Netzlaufwerk -,
    ohne dass das Programm Suchpfade fest verdrahtet.
    """
    datei = request.files.get("datei")
    if datei is None or not datei.filename:
        return redirect(url_for("einstellungen_seite", fehler="Keine Datei ausgewählt."))

    try:
        bericht = spiele_sicherung_ein(
            datei.read(),
            bekannte_anbieter=[a["schluessel"] for a in lade_anbieter()],
            version=_version(),
        )
    except SicherungsFehler as fehler:
        return redirect(url_for("einstellungen_seite", fehler=str(fehler)))
    except OSError as fehler:
        logging.getLogger("webapp").exception("Sicherung konnte nicht eingespielt werden")
        return redirect(url_for("einstellungen_seite", fehler=f"Die Einstellungen ließen sich nicht schreiben: {fehler}"))

    meldung = f"{bericht['merkliste']} gemerkte Titel, {bericht['ausgeblendet']} ausgeblendet"
    if bericht["schluessel_uebernommen"]:
        meldung += ", TMDB-Schlüssel übernommen"
    if bericht["erstellt_am"]:
        meldung += f" (Sicherung vom {bericht['erstellt_am'][:10]})"
    if bericht["notizen"]:
        meldung += " – " + ", ".join(bericht["notizen"])
    if bericht["sicherheitskopie"]:
        meldung += f". Der bisherige Stand liegt als {bericht['sicherheitskopie']} im Ordner config."

    logging.getLogger("webapp").info("Sicherung eingespielt: %s", meldung)
    _scan_im_hintergrund_starten()
    return redirect(url_for("einstellungen_seite", eingespielt=meldung))


@app.errorhandler(413)
def _datei_zu_gross(_fehler):
    """Ohne diesen Handler bekaeme der Nutzer Flasks nackte Fehlerseite zu
    sehen und muesste selbst zurueckfinden."""
    return redirect(url_for("einstellungen_seite", fehler="Die Datei ist zu groß für eine Sicherung (über 5 MB)."))


@app.route("/titel-suche")
def titel_suche():
    """Fuer die Merkliste in den Einstellungen: Live-Suche per TMDB waehrend
    des Tippens (siehe webapp/static/einstellungen.js)."""
    suchtext = request.args.get("q", "").strip()
    api_key = lade_api_schluessel()
    if not suchtext or not api_key:
        return jsonify([])
    try:
        treffer = suche_titel(neue_session(), api_key, suchtext)
    except TmdbFehler:
        return jsonify([])
    return jsonify(
        [
            {
                "tmdb_id": t.tmdb_id,
                "medientyp": t.medientyp,
                "titel": t.titel,
                "jahr": (t.erscheinungsdatum or "")[:4],
                "poster_url": _poster_url(t.poster_pfad),
            }
            for t in treffer[:10]
        ]
    )


@app.route("/suche")
def suche():
    """Titelsuche mit Verfuegbarkeit: bei welchem Anbieter laeuft ein Film oder
    eine Serie in Deutschland. Anders als die Uebersicht ist das unabhaengig von
    der Anbieterauswahl in den Einstellungen - gesucht wird bei allen."""
    suchtext = request.args.get("q", "").strip()
    api_key = lade_api_schluessel()
    treffer: list[dict] = []
    fehler = None
    if suchtext and not api_key:
        fehler = "Ohne TMDB-Schlüssel ist keine Suche möglich. Er wird in den Einstellungen eingetragen."
    elif suchtext:
        try:
            roh = suche_verfuegbarkeit(neue_session(), api_key, suchtext)
        except TmdbFehler as exc:
            roh = []
            fehler = f"Die Suche bei TMDB ist fehlgeschlagen: {exc}"
        # Eigene Anbieter bekommen ihre Farbe aus der Uebersicht, alle anderen
        # (Maxdome, Videoload, Google Play ...) bleiben grau.
        farben = {a["tmdb_name"]: a["farbe"] for a in lade_anbieter() if a.get("tmdb_name")}
        gemerkt = {(m["tmdb_id"], m["medientyp"]) for m in lade_einstellungen().get("merkliste", [])}
        for eintrag in roh:
            titel = eintrag["titel"]
            bezug = eintrag["bezug"]
            if bezug is not None:
                for gruppe in bezug:
                    gruppe["anbieter"] = [
                        {"name": name, "farbe": farben.get(name, "#6b7280")} for name in gruppe["anbieter"]
                    ]
            treffer.append(
                {
                    "titel": titel.titel,
                    "jahr": (titel.erscheinungsdatum or "")[:4],
                    "art": "Film" if titel.medientyp == "film" else "Serie",
                    "tmdb_id": titel.tmdb_id,
                    "medientyp": titel.medientyp,
                    "gemerkt": (titel.tmdb_id, titel.medientyp) in gemerkt,
                    "poster_url": _poster_url(titel.poster_pfad),
                    "bezug": bezug,
                }
            )
    return render_template("suche.html", suchtext=suchtext, treffer=treffer, fehler=fehler)


@app.route("/merken", methods=["POST"])
def merken():
    """Setzt einen Titel auf die Merkliste - per Knopf in der Suche (mit 'q',
    dann geht es dorthin zurueck) oder an einer Karte der Uebersicht (ohne 'q',
    dann zurueck zur Startseite). Das Gegenstueck zur Live-Suche in den
    Einstellungen, ohne den Umweg dorthin."""
    try:
        tmdb_id = int(request.form["tmdb_id"])
    except (KeyError, ValueError):
        return redirect(url_for("index"))
    medientyp = request.form.get("medientyp")
    suchtext = request.form.get("q", "")
    zurueck = url_for("suche", q=suchtext) if suchtext else url_for("index")
    if medientyp not in ("film", "serie"):
        return redirect(zurueck)
    daten = lade_einstellungen()
    merkliste = daten.setdefault("merkliste", [])
    if not any(e["tmdb_id"] == tmdb_id and e["medientyp"] == medientyp for e in merkliste):
        merkliste.append({"tmdb_id": tmdb_id, "medientyp": medientyp, "titel": request.form.get("titel", "")})
        speichere_einstellungen(daten)
        # Der Termin des neuen Titels wird erst beim Scan abgefragt; ohne ihn
        # stuende er auf der Startseite zunaechst als "Noch kein Termin bekannt".
        _scan_im_hintergrund_starten()
    return redirect(zurueck)


@app.route("/entmerken", methods=["POST"])
def entmerken():
    """Nimmt einen Titel von der Merkliste - in der Suche und direkt an der
    Karte in der Merkliste. Mit 'q' geht es zurueck zur Suche, sonst zur
    Startseite. Der zugehoerige Termin in der Datenbank bleibt liegen und wird
    nicht mehr angezeigt, denn die Merkliste richtet sich nach den
    Einstellungen."""
    try:
        tmdb_id = int(request.form["tmdb_id"])
    except (KeyError, ValueError):
        return redirect(url_for("index"))
    medientyp = request.form.get("medientyp")
    daten = lade_einstellungen()
    behalten = [
        e for e in daten.get("merkliste", []) if not (e["tmdb_id"] == tmdb_id and e["medientyp"] == medientyp)
    ]
    if len(behalten) != len(daten.get("merkliste", [])):
        daten["merkliste"] = behalten
        speichere_einstellungen(daten)
    suchtext = request.form.get("q")
    return redirect(url_for("suche", q=suchtext) if suchtext else url_for("index"))


@app.route("/ausblenden", methods=["POST"])
def ausblenden():
    """Blendet einen einzelnen Titel direkt aus der Uebersicht aus (Knopf an
    jeder Karte) - ohne Umweg ueber die Einstellungsseite."""
    daten = lade_einstellungen()
    eintrag = {
        "tmdb_id": int(request.form["tmdb_id"]),
        "medientyp": request.form["medientyp"],
        "titel": request.form.get("titel", ""),
    }
    if not any(e["tmdb_id"] == eintrag["tmdb_id"] and e["medientyp"] == eintrag["medientyp"] for e in daten.get("ausgeblendet", [])):
        daten.setdefault("ausgeblendet", []).append(eintrag)
        speichere_einstellungen(daten)
    return redirect(url_for("index"))


if __name__ == "__main__":
    _logging_einrichten()
    logging.getLogger("webapp").info("Streaming-Info Version %s startet", _version())
    init_db(DB_PFAD)
    _scan_im_hintergrund_starten()
    app.run(host="127.0.0.1", port=5100, debug=False, use_reloader=False)
