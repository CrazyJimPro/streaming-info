"""Hauptskript: fragt TMDB fuer alle aktiven Anbieter + Kinostarts ab und
speichert das Ergebnis. Wird von der Web-App aufgerufen (beim Start und bei
Klick auf "Jetzt aktualisieren"), kann aber auch manuell laufen:

    python -m scraper.run
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from scraper.base import TmdbApiSchluesselFehlt, TmdbFehler, neue_session
from scraper.einstellungen import lade_anbieter, lade_api_schluessel, lade_einstellungen
from scraper.storage import (
    hole_anbieter_provider_id,
    init_db,
    markiere_quelle_erfolg,
    markiere_quelle_fehler,
    speichere_anbieter_provider_id,
    speichere_titel,
    speichere_verfuegbarkeit,
)
from scraper.tmdb import hole_anbieter_id, hole_anbieter_katalog, hole_genres, hole_kinostarts

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
LOG_PFAD = PROJEKT_ROOT / "logs" / "scraper.log"
GENRES_CACHE_PFAD = PROJEKT_ROOT / "data" / "genres.json"

# Kinostarts zeigen zusaetzlich zu kuerzlich angelaufenen Filmen (14 Tage
# rueckblickend), damit gerade gestartete Filme nicht sofort aus der Liste
# verschwinden.
KINO_RUECKBLICK_TAGE = 14


def _logging_einrichten() -> None:
    LOG_PFAD.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PFAD, encoding="utf-8"), logging.StreamHandler()],
    )


def _anbieter_provider_id(session, api_key: str, anbieter_schluessel: str, tmdb_name: str, medientyp: str) -> int | None:
    cached = hole_anbieter_provider_id(anbieter_schluessel, medientyp)
    if cached is not None:
        return cached
    provider_id = hole_anbieter_id(session, api_key, medientyp, tmdb_name)
    if provider_id is not None:
        speichere_anbieter_provider_id(anbieter_schluessel, medientyp, provider_id)
    return provider_id


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
    aktive_anbieter = [s for s in einstellungen.get("aktive_anbieter", []) if s in alle_anbieter]

    session = neue_session()
    heute = date.today()

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
        for medientyp in ("film", "serie"):
            quelle = f"{anbieter_schluessel}-{medientyp}"
            try:
                provider_id = _anbieter_provider_id(session, api_key, anbieter_schluessel, anbieter["tmdb_name"], medientyp)
                if provider_id is None:
                    raise TmdbFehler(f"Kein TMDB-Anbieter '{anbieter['tmdb_name']}' fuer {medientyp} gefunden.")
                katalog = hole_anbieter_katalog(session, api_key, medientyp, provider_id)
                speichere_titel(katalog)
                for eintrag in katalog:
                    speichere_verfuegbarkeit(eintrag.tmdb_id, medientyp, anbieter_schluessel, heute)
                markiere_quelle_erfolg(quelle)
                logger.info("%s: %d Titel im aktuellen Katalog", quelle, len(katalog))
            except TmdbFehler as exc:
                markiere_quelle_fehler(quelle, str(exc))
                logger.error("%s fehlgeschlagen: %s", quelle, exc)

    try:
        ab = heute - timedelta(days=KINO_RUECKBLICK_TAGE)
        bis = heute + timedelta(weeks=einstellungen.get("zeitraum_wochen", 8))
        kinostarts = hole_kinostarts(session, api_key, ab, bis)
        speichere_titel(kinostarts)
        markiere_quelle_erfolg("kino")
        logger.info("kino: %d Kinostarts zwischen %s und %s", len(kinostarts), ab, bis)
    except TmdbFehler as exc:
        markiere_quelle_fehler("kino", str(exc))
        logger.error("kino fehlgeschlagen: %s", exc)

    logger.info("Scan beendet")


if __name__ == "__main__":
    main()
