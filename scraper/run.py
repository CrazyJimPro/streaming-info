"""Hauptskript: fragt bei TMDB ab, was in naechster Zeit anlaeuft, und
speichert das Ergebnis. Wird von der Web-App aufgerufen (beim Start und bei
Klick auf "Jetzt aktualisieren"), kann aber auch manuell laufen:

    python -m scraper.run

Gesucht wird ausschliesslich Zukuenftiges: kommende Serien und Staffelstarts
je Anbieter, deutsche Kinostarts und digitale Filmstarts. Der frueher hier
laufende Komplettabzug aller Anbieterkataloge (rund 18.000 Titel pro Lauf,
nur um per Vergleich "neu dazugekommen" zu erkennen) ist entfallen - damit
ist ein Lauf auch deutlich kuerzer.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from scraper.base import StartEintrag, TmdbApiSchluesselFehlt, TmdbFehler, neue_session
from scraper.einstellungen import lade_anbieter, lade_api_schluessel, lade_einstellungen
from scraper.storage import (
    init_db,
    markiere_quelle_erfolg,
    markiere_quelle_fehler,
    raeume_starts_auf,
    speichere_starts,
    speichere_titel,
)
from scraper.tmdb import (
    hole_digital_starts,
    hole_genres,
    hole_kinostarts,
    hole_kommende_serien,
    hole_kommende_staffeln,
)

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
LOG_PFAD = PROJEKT_ROOT / "logs" / "scraper.log"
GENRES_CACHE_PFAD = PROJEKT_ROOT / "data" / "genres.json"

# Wie weit vorausgeschaut wird, wenn in den Einstellungen nichts steht.
STANDARD_VORSCHAU_WOCHEN = 8
# Abgelaufene Startereignisse werden nach dieser Frist entsorgt.
AUFRAEUM_TAGE = 30


def _logging_einrichten() -> None:
    LOG_PFAD.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PFAD, encoding="utf-8"), logging.StreamHandler()],
    )


def main() -> None:
    _logging_einrichten()
    logger = logging.getLogger("run")
    logger.info("Scan gestartet")

    init_db()

    api_key = lade_api_schluessel()
    if not api_key:
        logger.critical("Kein TMDB-API-Schluessel hinterlegt (config/config.json). Scan abgebrochen.")
        return

    einstellungen = lade_einstellungen()
    alle_anbieter = {a["schluessel"]: a for a in lade_anbieter()}
    aktive_anbieter = [
        s for s in einstellungen.get("aktive_anbieter", []) if s in alle_anbieter and s != "kino"
    ]

    session = neue_session()
    heute = date.today()
    bis = heute + timedelta(weeks=einstellungen.get("zeitraum_wochen", STANDARD_VORSCHAU_WOCHEN))

    try:
        genres = hole_genres(session, api_key)
        GENRES_CACHE_PFAD.parent.mkdir(parents=True, exist_ok=True)
        GENRES_CACHE_PFAD.write_text(json.dumps(genres, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("%d Genres geladen", len(genres))
    except TmdbApiSchluesselFehlt as exc:
        logger.critical("API-Schluessel ungueltig: %s", exc)
        return
    except TmdbFehler as exc:
        logger.error("Genre-Liste konnte nicht geladen werden: %s", exc)

    for anbieter_schluessel in aktive_anbieter:
        anbieter = alle_anbieter[anbieter_schluessel]
        network_ids = anbieter.get("tmdb_network_ids") or []
        if not network_ids:
            logger.warning(
                "%s hat kein TMDB-Netzwerk hinterlegt - kommende Serien lassen sich dort nicht ermitteln.",
                anbieter_schluessel,
            )
            continue
        try:
            neue_serien = hole_kommende_serien(session, api_key, network_ids, anbieter_schluessel, heute, bis)
            staffeln = hole_kommende_staffeln(session, api_key, network_ids, anbieter_schluessel, heute, bis)
            paare = neue_serien + staffeln
            speichere_titel([t for t, _ in paare])
            speichere_starts([s for _, s in paare], heute)
            markiere_quelle_erfolg(anbieter_schluessel)
            logger.info(
                "%s: %d neue Serien, %d Staffelstarts",
                anbieter_schluessel, len(neue_serien), len(staffeln),
            )
        except TmdbFehler as exc:
            markiere_quelle_fehler(anbieter_schluessel, str(exc))
            logger.error("%s fehlgeschlagen: %s", anbieter_schluessel, exc)

    try:
        paare = hole_digital_starts(session, api_key, heute, bis)
        speichere_titel([t for t, _ in paare])
        speichere_starts([s for _, s in paare], heute)
        markiere_quelle_erfolg("digital")
        logger.info("digital: %d angekuendigte Filmstarts", len(paare))
    except TmdbFehler as exc:
        markiere_quelle_fehler("digital", str(exc))
        logger.error("digital fehlgeschlagen: %s", exc)

    try:
        kinostarts = hole_kinostarts(session, api_key, heute, bis)
        speichere_titel(kinostarts)
        # Auch Kinostarts landen als Startereignis in 'starts' - so liegen alle
        # drei Sektionen der Uebersicht in derselben Tabelle und werden mit
        # derselben Abfrage gelesen.
        speichere_starts(
            [
                StartEintrag(
                    tmdb_id=t.tmdb_id,
                    medientyp="film",
                    anbieter="kino",
                    startdatum=t.kinostart_de,
                    art="kino",
                )
                for t in kinostarts
                if t.kinostart_de
            ],
            heute,
        )
        markiere_quelle_erfolg("kino")
        logger.info("kino: %d Kinostarts zwischen %s und %s", len(kinostarts), heute, bis)
    except TmdbFehler as exc:
        markiere_quelle_fehler("kino", str(exc))
        logger.error("kino fehlgeschlagen: %s", exc)

    entfernt = raeume_starts_auf(heute - timedelta(days=AUFRAEUM_TAGE))
    if entfernt:
        logger.info("%d abgelaufene Startereignisse entfernt", entfernt)

    logger.info("Scan beendet")


if __name__ == "__main__":
    main()
