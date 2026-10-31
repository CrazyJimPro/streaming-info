"""Hauptskript: fragt bei TMDB ab, was in naechster Zeit anlaeuft, und
speichert das Ergebnis. Wird von der Web-App aufgerufen (beim Start und bei
Klick auf "Jetzt aktualisieren"), kann aber auch manuell laufen:

    python -m scraper.run

Gesucht wird ausschliesslich Zukuenftiges: kommende Serien und Staffelstarts
je Anbieter, deutsche Kinostarts und digitale Filmstarts. Der frueher hier
laufende Komplettabzug aller Anbieterkataloge (rund 18.000 Titel pro Lauf,
nur um per Vergleich "neu dazugekommen" zu erkennen) ist entfallen - damit
ist ein Lauf auch deutlich kuerzer. Einzige Ausnahme seit v1.7.0: fuer
"Neu im Abo" werden die Abo-Kataloge gelesen, aber nur Filme der letzten 18
Monate (zusammen gut 1.300 Titel) - siehe hole_abo_filme.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from scraper.base import StartEintrag, TmdbApiSchluesselFehlt, TmdbFehler, neue_session
from scraper.einstellungen import lade_anbieter, lade_api_schluessel, lade_einstellungen
from scraper.storage import (
    entferne_unbestaetigte_starts,
    init_db,
    markiere_quelle_erfolg,
    markiere_quelle_fehler,
    quelle_schon_erfolgreich,
    raeume_abo_katalog_auf,
    raeume_starts_auf,
    speichere_abo_katalog,
    speichere_starts,
    speichere_titel,
)
from scraper.tmdb import (
    ABO_RUECKBLICK_MONATE,
    hole_abo_filme,
    hole_digital_starts,
    hole_genres,
    hole_kinostarts,
    hole_kommende_serien,
    hole_kommende_staffeln,
    hole_merkliste_termine,
)

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
LOG_PFAD = PROJEKT_ROOT / "logs" / "scraper.log"
GENRES_CACHE_PFAD = PROJEKT_ROOT / "data" / "genres.json"

# Wie weit vorausgeschaut wird, wenn in den Einstellungen nichts steht.
STANDARD_VORSCHAU_WOCHEN = 8
# Abgelaufene Startereignisse werden nach dieser Frist entsorgt.
AUFRAEUM_TAGE = 30
# Filme, die so lange nicht mehr im Abo lagen, fliegen aus dem Abo-Abgleich.
ABO_AUFRAEUM_TAGE = 180


def _abo_kataloge_abgleichen(api_key: str, anbieter_liste: list[dict], heute: date, logger) -> None:
    """Liest die Abo-Kataloge der aktiven Anbieter (parallel, je eigene
    Session) und gleicht sie mit dem Vorlauf ab - Grundlage fuer "Neu im Abo".
    Jeder Anbieter zaehlt als eigene Quelle 'abo-<schluessel>': schlaegt einer
    fehl, bleibt sein bisheriger Stand unangetastet."""
    mit_id = [a for a in anbieter_liste if a.get("tmdb_provider_id")]
    if not mit_id:
        return
    ab_erscheinung = heute - timedelta(days=ABO_RUECKBLICK_MONATE * 30)

    def _lesen(anbieter: dict):
        try:
            return anbieter, hole_abo_filme(neue_session(), api_key, anbieter["tmdb_provider_id"], ab_erscheinung), None
        except TmdbFehler as exc:
            return anbieter, None, exc

    with ThreadPoolExecutor(max_workers=len(mit_id)) as pool:
        ergebnisse = list(pool.map(_lesen, mit_id))

    for anbieter, filme, fehler in ergebnisse:
        quelle = f"abo-{anbieter['schluessel']}"
        if fehler is not None:
            markiere_quelle_fehler(quelle, str(fehler))
            logger.error("%s fehlgeschlagen: %s", quelle, fehler)
            continue
        ist_basis = not quelle_schon_erfolgreich(quelle)
        speichere_titel(filme)
        neu = speichere_abo_katalog(anbieter["schluessel"], [f.tmdb_id for f in filme], heute, ist_basis)
        markiere_quelle_erfolg(quelle)
        if ist_basis:
            logger.info("%s: %d Filme im Abo - erster Abgleich, dient als Vergleichsbasis", quelle, len(filme))
        else:
            logger.info("%s: %d Filme im Abo, %d neu hinzugekommen", quelle, len(filme), neu)


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
            # Erst nach dem erfolgreichen Abruf aufraeumen: was dieser Lauf
            # nicht mehr gemeldet hat, ist abgesagt oder aus dem Fenster
            # gewandert und darf nicht als bevorstehend stehen bleiben.
            veraltet = entferne_unbestaetigte_starts(anbieter_schluessel, heute)
            markiere_quelle_erfolg(anbieter_schluessel)
            logger.info(
                "%s: %d neue Serien, %d Staffelstarts%s",
                anbieter_schluessel, len(neue_serien), len(staffeln),
                f", {veraltet} nicht mehr gemeldete entfernt" if veraltet else "",
            )
        except TmdbFehler as exc:
            markiere_quelle_fehler(anbieter_schluessel, str(exc))
            logger.error("%s fehlgeschlagen: %s", anbieter_schluessel, exc)

    try:
        paare = hole_digital_starts(session, api_key, heute, bis)
        speichere_titel([t for t, _ in paare])
        speichere_starts([s for _, s in paare], heute)
        veraltet = entferne_unbestaetigte_starts("digital", heute)
        markiere_quelle_erfolg("digital")
        logger.info(
            "digital: %d angekuendigte Filmstarts%s",
            len(paare),
            f", {veraltet} nicht mehr gemeldete entfernt" if veraltet else "",
        )
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
        veraltet = entferne_unbestaetigte_starts("kino", heute)
        markiere_quelle_erfolg("kino")
        logger.info(
            "kino: %d Kinostarts zwischen %s und %s%s",
            len(kinostarts), heute, bis,
            f", {veraltet} nicht mehr gemeldete entfernt" if veraltet else "",
        )
    except TmdbFehler as exc:
        markiere_quelle_fehler("kino", str(exc))
        logger.error("kino fehlgeschlagen: %s", exc)

    # Merkliste zuletzt: sie fragt gezielt je Titel nach und ist damit
    # unabhaengig von Popularitaetsfilter und Anbieterauswahl.
    merkliste = einstellungen.get("merkliste", [])
    if merkliste:
        try:
            paare = hole_merkliste_termine(session, api_key, merkliste, heute)
            speichere_titel([t for t, _ in paare])
            speichere_starts([s for _, s in paare if s is not None], heute)
            entferne_unbestaetigte_starts("merkliste", heute)
            markiere_quelle_erfolg("merkliste")
            mit_termin = sum(1 for _, s in paare if s is not None)
            logger.info(
                "merkliste: %d Titel geprueft, %d mit bekanntem Termin",
                len(paare), mit_termin,
            )
        except TmdbFehler as exc:
            markiere_quelle_fehler("merkliste", str(exc))
            logger.error("merkliste fehlgeschlagen: %s", exc)

    _abo_kataloge_abgleichen(api_key, [alle_anbieter[s] for s in aktive_anbieter], heute, logger)
    raeume_abo_katalog_auf(heute - timedelta(days=ABO_AUFRAEUM_TAGE))

    entfernt = raeume_starts_auf(heute - timedelta(days=AUFRAEUM_TAGE))
    if entfernt:
        logger.info("%d abgelaufene Startereignisse entfernt", entfernt)

    logger.info("Scan beendet")


if __name__ == "__main__":
    main()
