"""Anbindung an die TMDB-API (https://developer.themoviedb.org/).

Nur mit Konzepten, die TMDB tatsaechlich liefert: aktuelle Verfuegbarkeit pro
Anbieter (aber KEIN "hinzugefuegt am"-Datum - das baut sich diff.py aus
wiederholten Laeufen selbst zusammen) und echte deutsche Kinostart-Termine
(die gibt es bei TMDB wirklich, ueber with_release_type=Kino).
"""
from __future__ import annotations

import logging
from datetime import date

import requests

from scraper.base import TitelEintrag, TmdbFehler, get_json

logger = logging.getLogger("tmdb")

# TMDB-interne release_type-Werte: 1=Premiere, 2=Limitiert, 3=Kino, 4=Digital,
# 5=Physisch, 6=TV. 2|3 deckt sowohl normale als auch limitierte Kinostarts ab.
KINOSTART_RELEASE_TYPES = "2|3"

MAX_SEITEN_PRO_ANBIETER = 150  # Sicherheitsdeckel: 150 x 20 = 3000 Titel/Anbieter/Medientyp
MAX_SEITEN_KINO = 25  # 25 x 20 = 500 Kinotitel - nach Popularitaet sortiert reicht das fuer alles Relevante


def hole_genres(session: requests.Session, api_key: str) -> dict[int, str]:
    """Liefert eine gemeinsame Genre-Zuordnung (id -> Name) ueber Filme und Serien hinweg."""
    genres: dict[int, str] = {}
    for pfad in ("/genre/movie/list", "/genre/tv/list"):
        daten = get_json(session, pfad, api_key)
        for genre in daten.get("genres", []):
            genres[genre["id"]] = genre["name"]
    return genres


def hole_anbieter_id(session: requests.Session, api_key: str, medientyp: str, tmdb_name: str) -> int | None:
    """Loest den TMDB-Anzeigenamen eines Anbieters (z.B. 'HBO Max') zur aktuellen
    numerischen provider_id fuer die Region Deutschland auf. Bewusst dynamisch
    statt hartkodiert, weil Anbieter-IDs sich bei Rebranding (siehe HBO Max/Max)
    aendern koennen."""
    pfad = "/watch/providers/movie" if medientyp == "film" else "/watch/providers/tv"
    daten = get_json(session, pfad, api_key, watch_region="DE")
    for eintrag in daten.get("results", []):
        if eintrag.get("provider_name") == tmdb_name:
            return eintrag["provider_id"]
    logger.warning("Anbieter '%s' nicht in TMDBs Anbieterliste (%s, DE) gefunden.", tmdb_name, medientyp)
    return None


def _zu_titel_eintrag(rohdaten: dict, medientyp: str) -> TitelEintrag:
    return TitelEintrag(
        tmdb_id=rohdaten["id"],
        medientyp=medientyp,
        titel=rohdaten.get("title") or rohdaten.get("name") or "(ohne Titel)",
        overview=rohdaten.get("overview") or None,
        poster_pfad=rohdaten.get("poster_path"),
        erscheinungsdatum=rohdaten.get("release_date") or rohdaten.get("first_air_date") or None,
        genre_ids=rohdaten.get("genre_ids", []),
    )


def hole_anbieter_katalog(
    session: requests.Session, api_key: str, medientyp: str, provider_id: int
) -> list[TitelEintrag]:
    """Paginiert durch den kompletten aktuellen Katalog eines Anbieters (DE)."""
    pfad = "/discover/movie" if medientyp == "film" else "/discover/tv"
    ergebnisse: list[TitelEintrag] = []
    seite = 1
    gesamtseiten = 1
    while seite <= gesamtseiten and seite <= MAX_SEITEN_PRO_ANBIETER:
        try:
            daten = get_json(
                session,
                pfad,
                api_key,
                with_watch_providers=provider_id,
                watch_region="DE",
                sort_by="popularity.desc",
                include_adult="false",
                page=seite,
            )
        except TmdbFehler as exc:
            logger.error("Katalog-Abruf Seite %d fuer Anbieter-ID %s fehlgeschlagen: %s", seite, provider_id, exc)
            break
        for rohdaten in daten.get("results", []):
            ergebnisse.append(_zu_titel_eintrag(rohdaten, medientyp))
        gesamtseiten = min(daten.get("total_pages", 1), MAX_SEITEN_PRO_ANBIETER)
        seite += 1
    return ergebnisse


def hole_kinostarts(session: requests.Session, api_key: str, ab: date, bis: date) -> list[TitelEintrag]:
    """Liefert deutsche Kinostarts (echte TMDB-Kinostart-Termine) im Zeitraum [ab, bis].

    Sortiert nach Popularitaet UND mit einem vote_count-Mindestfilter: TMDB
    meldet fuer die Region DE mehrere Tausend "Kinostarts" pro Monat, die ganz
    ueberwiegend Ein-Kino-/Festival-/Nischen-Titel ganz ohne jede Bewertung
    sind - per Stichprobe geprueft (2-Monats-Fenster, 4113 Roh-Treffer):
    vote_count>=1 half kaum (blieb bei 229 Treffern voller Nischentitel,
    Wrestling-PPVs, Ein-Kino-Festivalfilme); vote_count>=5 druecke auf 37
    plausible, erkennbare Titel (Resident Evil, Practical Magic 2, Shaun das
    Schaf, ...) - manuell gegengeprueft. Schaerfer als noetig fuer sehr
    kleine, aber echte Arthouse-Starts, aber die einzige der getesteten
    Schwellen ohne Muell-Ergebnisse; laesst sich hier leicht nachjustieren.
    Die Sortierung fuer die Anzeige (nach Kinostart-Datum) macht die Web-App
    bzw. die SQL-Abfrage in storage.py."""
    ergebnisse: list[TitelEintrag] = []
    seite = 1
    gesamtseiten = 1
    while seite <= gesamtseiten and seite <= MAX_SEITEN_KINO:
        try:
            daten = get_json(
                session,
                "/discover/movie",
                api_key,
                region="DE",
                with_release_type=KINOSTART_RELEASE_TYPES,
                **{"primary_release_date.gte": ab.isoformat(), "primary_release_date.lte": bis.isoformat()},
                sort_by="popularity.desc",
                include_adult="false",
                **{"vote_count.gte": 5},
                page=seite,
            )
        except TmdbFehler as exc:
            logger.error("Kinostart-Abruf Seite %d fehlgeschlagen: %s", seite, exc)
            break
        for rohdaten in daten.get("results", []):
            eintrag = _zu_titel_eintrag(rohdaten, "film")
            eintrag.kinostart_de = rohdaten.get("release_date")
            ergebnisse.append(eintrag)
        gesamtseiten = min(daten.get("total_pages", 1), MAX_SEITEN_KINO)
        seite += 1
    return ergebnisse
