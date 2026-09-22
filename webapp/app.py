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
from scraper.filter import filtere_zeilen  # noqa: E402
from scraper.storage import DB_PFAD, hole_kinostarts_im_zeitraum, hole_quellen_status, hole_streaming_neuheiten, init_db  # noqa: E402
from scraper.tmdb import suche_titel  # noqa: E402

app = Flask(__name__)

TMDB_POSTER_BASIS = "https://image.tmdb.org/t/p/w300"
KINO_RUECKBLICK_TAGE = 14

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


def _streaming_gruppieren(zeilen: list[dict], anbieter_karte: dict[str, dict]) -> list[dict]:
    """Fasst mehrere Verfuegbarkeits-Zeilen desselben Titels (z.B. gleichzeitig
    neu bei Netflix UND Amazon) zu einer Anzeige-Zeile mit mehreren
    Anbieter-Badges zusammen."""
    gruppiert: dict[tuple, dict] = {}
    for zeile in zeilen:
        schluessel = (zeile["tmdb_id"], zeile["medientyp"])
        eintrag = gruppiert.setdefault(
            schluessel,
            {**zeile, "anbieter_liste": [], "neu_seit": zeile["erstmals_gesehen_am"]},
        )
        info = anbieter_karte.get(zeile["anbieter"])
        eintrag["anbieter_liste"].append(
            {"name": info["name"] if info else zeile["anbieter"], "farbe": info["farbe"] if info else "#888"}
        )
        eintrag["neu_seit"] = max(eintrag["neu_seit"], zeile["erstmals_gesehen_am"])
    ergebnis = list(gruppiert.values())
    ergebnis.sort(key=lambda e: e["neu_seit"], reverse=True)
    return ergebnis


@app.route("/")
def index():
    einstellungen = lade_einstellungen()
    anbieter_karte = _anbieter_karte()
    heute = date.today()
    zeitraum_wochen = einstellungen.get("zeitraum_wochen", 8)

    ab_streaming = heute - timedelta(weeks=zeitraum_wochen)
    streaming_rows = filtere_zeilen(hole_streaming_neuheiten(ab_streaming), einstellungen)
    streaming = _streaming_gruppieren(streaming_rows, anbieter_karte)
    for eintrag in streaming:
        eintrag["poster_url"] = _poster_url(eintrag.get("poster_pfad"))
        eintrag["neu_seit_lesbar"] = _datum_lesbar(eintrag.get("neu_seit"))

    ab_kino = heute - timedelta(days=KINO_RUECKBLICK_TAGE)
    bis_kino = heute + timedelta(weeks=zeitraum_wochen)
    kino_rows = filtere_zeilen(hole_kinostarts_im_zeitraum(ab_kino, bis_kino), einstellungen)
    for eintrag in kino_rows:
        eintrag["poster_url"] = _poster_url(eintrag.get("poster_pfad"))
        eintrag["kinostart_lesbar"] = _datum_lesbar(eintrag.get("kinostart_de"))
    kino_rows.sort(key=lambda r: r["kinostart_de"])

    status = _status_aufbereiten(hole_quellen_status(db_pfad=DB_PFAD))
    api_schluessel_fehlt = not lade_api_schluessel()

    return render_template(
        "index.html",
        streaming=streaming,
        kino=kino_rows,
        status=status,
        heute=heute,
        zeitraum_wochen=zeitraum_wochen,
        scan=_scan_status,
        api_schluessel_fehlt=api_schluessel_fehlt,
        kino_farbe=next((a["farbe"] for a in anbieter_karte.values() if a["schluessel"] == "kino"), "#e63946"),
    )


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

        # Merkliste/Ausblendliste: Titel per tmdb_id+medientyp+titel aus dem
        # Formular uebernehmen (siehe webapp/static/einstellungen.js).
        daten["merkliste"] = _liste_aus_formular("merk")
        daten["ausgeblendet"] = _liste_aus_formular("ausblend")

        api_schluessel = request.form.get("tmdb_api_key", "").strip()
        if api_schluessel:
            speichere_api_schluessel(api_schluessel)

        speichere_einstellungen(daten)
        _scan_im_hintergrund_starten()
        return redirect(url_for("einstellungen_seite", gespeichert=1))

    return render_template(
        "einstellungen.html",
        einstellungen=daten,
        anbieter=alle_anbieter,
        genres=sorted(genres.items(), key=lambda kv: kv[1]),
        api_schluessel_vorhanden=bool(lade_api_schluessel()),
        gespeichert=request.args.get("gespeichert") == "1",
    )


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
