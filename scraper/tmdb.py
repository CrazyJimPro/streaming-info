"""Anbindung an die TMDB-API (https://developer.themoviedb.org/).

Dieses Tool zeigt ausschliesslich ANGEKUENDIGTE Starts in der Zukunft, nicht
den laufenden Katalog. Was TMDB dafuer wirklich hergibt - per Stichprobe
geprueft, bevor hier etwas gebaut wurde:

* Kommende Serien und Staffelstarts je Anbieter: ueber die TV-Netzwerke
  (discover/tv mit with_networks). Der sonst naheliegende Anbieterfilter
  with_watch_providers taugt dafuer NICHT - er kennt nur, was bereits
  abrufbar ist, und eine Serie, die erst naechsten Monat startet, steht dort
  noch nicht drin.
* Deutsche Kinostarts: echte Termine ueber with_release_type=2|3 + region=DE.
* Digitale Filmstarts (VOD): with_release_type=4 + region=DE liefert das
  Datum. Die PLATTFORM liefert TMDB dazu nicht - fuer acht kommende Titel
  stichprobenartig geprueft, die Anbieterangabe war durchgehend leer. Solche
  Filme laufen deshalb unter dem Sammel-Schluessel "digital" statt unter
  einem Dienst, der nur geraten waere.
"""
from __future__ import annotations

import logging
from datetime import date

import requests

from scraper.base import StartEintrag, TitelEintrag, TmdbFehler, get_json

logger = logging.getLogger("tmdb")

# TMDB-interne release_type-Werte: 1=Premiere, 2=Limitiert, 3=Kino, 4=Digital,
# 5=Physisch, 6=TV. 2|3 deckt normale und limitierte Kinostarts ab.
KINOSTART_RELEASE_TYPES = "2|3"
DIGITAL_RELEASE_TYPE = 4

MAX_SEITEN_KINO = 25  # 25 x 20 = 500 Titel, nach Popularitaet sortiert
MAX_SEITEN_DIGITAL = 15
MAX_SEITEN_SERIEN = 10
# Staffelstarts kosten eine Detailabfrage pro Kandidat, deshalb ein Deckel.
MAX_STAFFEL_KANDIDATEN = 120

# --- Rauschfilter --------------------------------------------------------
# Frueher stand hier vote_count>=5. Fuer eine Vorschau ist das untauglich, und
# zwar systematisch: angekuendigte Titel haben noch keine Bewertungen. Gemessen
# an einem 4-Wochen-Fenster kamen ganze 2 Kinostarts ueber diese Schwelle -
# durchgefallen waeren ausgerechnet "Street Fighter", "Clayface" oder "Verity",
# also genau das, was man sehen will. Brauchbar ist stattdessen popularity, das
# TMDB auch fuer Unveroeffentlichtes fuehrt (Seitenaufrufe, Merklisten).
#
# Schwellen an echten Daten abgelesen (8-Wochen-Fenster, 160 Kinostarts):
# >=20 nur 4 Titel (zu streng), >=10 noch 15, >=5 schon 63 samt vieler
# Titel ohne deutschen Bezug (Bollywood-, China-, Thailand-Starts, die TMDB
# unter region=DE fuehrt). 8 trifft die Mitte: die grossen Starts bleiben,
# der lange Schwanz faellt weg.
MIN_POPULARITAET_KINO = 8.0
# Serien liegen auf einer deutlich niedrigeren Skala als Filme - dort trennt
# 2.0 die erkennbaren Produktionen (Carrie, East of Eden, Die Falle,
# Cyberpunk: Edgerunners 2) von Nischenware einzelner Laendermaerkte.
MIN_POPULARITAET_SERIE = 2.0
MIN_POPULARITAET_DIGITAL = 3.0


def hole_genres(session: requests.Session, api_key: str) -> dict[int, str]:
    """Liefert eine gemeinsame Genre-Zuordnung (id -> Name) ueber Filme und Serien hinweg."""
    genres: dict[int, str] = {}
    for pfad in ("/genre/movie/list", "/genre/tv/list"):
        daten = get_json(session, pfad, api_key)
        for genre in daten.get("genres", []):
            genres[genre["id"]] = genre["name"]
    return genres


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


def _ist_relevant(rohdaten: dict, min_popularitaet: float) -> bool:
    """Rauschfilter fuer Angekuendigtes: genug Popularitaet und ein Poster.

    Das Poster ist die zweite Huerde, weil TMDB-Eintraege ganz ohne
    Bildmaterial in aller Regel Platzhalter oder Datenmuell sind - und die
    Kachel in der Uebersicht waere ohnehin leer. Zu den Schwellen siehe oben.
    """
    if not rohdaten.get("poster_path"):
        return False
    return (rohdaten.get("popularity") or 0) >= min_popularitaet


def suche_titel(session: requests.Session, api_key: str, suchtext: str) -> list[TitelEintrag]:
    """Volltextsuche fuer die Merkliste in den Einstellungen (TMDB /search/multi,
    auf Filme und Serien eingeschraenkt)."""
    daten = get_json(session, "/search/multi", api_key, query=suchtext, include_adult="false")
    ergebnisse = []
    for rohdaten in daten.get("results", []):
        if rohdaten.get("media_type") == "movie":
            ergebnisse.append(_zu_titel_eintrag(rohdaten, "film"))
        elif rohdaten.get("media_type") == "tv":
            ergebnisse.append(_zu_titel_eintrag(rohdaten, "serie"))
    return ergebnisse


def _blaettere(session, api_key: str, pfad: str, max_seiten: int, **params):
    """Laeuft die Seiten einer Discover-Abfrage ab und liefert die Rohtreffer."""
    seite = 1
    gesamtseiten = 1
    while seite <= gesamtseiten and seite <= max_seiten:
        try:
            daten = get_json(session, pfad, api_key, page=seite, **params)
        except TmdbFehler as exc:
            logger.error("Abruf %s Seite %d fehlgeschlagen: %s", pfad, seite, exc)
            return
        for rohdaten in daten.get("results", []):
            yield rohdaten
        gesamtseiten = min(daten.get("total_pages", 1), max_seiten)
        seite += 1


def hole_kinostarts(session: requests.Session, api_key: str, ab: date, bis: date) -> list[TitelEintrag]:
    """Deutsche Kinostarts im Zeitraum [ab, bis].

    Mit vote_count-Mindestfilter: TMDB meldet fuer die Region DE mehrere
    Tausend "Kinostarts" pro Monat, ganz ueberwiegend Ein-Kino-/Festival-/
    Nischentitel. Per Stichprobe geprueft (2-Monats-Fenster, 4113 Roh-Treffer):
    vote_count>=1 half kaum (229 Treffer voller Nischentitel), vote_count>=5
    druecke auf 37 plausible, erkennbare Titel. Bei weit im Voraus
    angekuendigten Filmen ist die Schwelle allerdings hart - sie haben noch
    keine Stimmen -, deshalb zaehlt hier zusaetzlich ein vorhandenes Poster
    als Beleg dafuer, dass es den Film wirklich gibt.
    """
    ergebnisse: list[TitelEintrag] = []
    for rohdaten in _blaettere(
        session, api_key, "/discover/movie", MAX_SEITEN_KINO,
        region="DE",
        with_release_type=KINOSTART_RELEASE_TYPES,
        sort_by="popularity.desc",
        include_adult="false",
        **{"primary_release_date.gte": ab.isoformat(), "primary_release_date.lte": bis.isoformat()},
    ):
        if not _ist_relevant(rohdaten, MIN_POPULARITAET_KINO):
            continue
        eintrag = _zu_titel_eintrag(rohdaten, "film")
        eintrag.kinostart_de = rohdaten.get("release_date")
        ergebnisse.append(eintrag)
    return ergebnisse


def hole_digital_starts(
    session: requests.Session, api_key: str, ab: date, bis: date
) -> list[tuple[TitelEintrag, StartEintrag]]:
    """Filme mit angekuendigtem digitalen Start (VOD) in der Region DE.

    Ohne Plattformangabe - siehe Modulkopf. Deshalb bekommt jeder Treffer den
    Sammel-Anbieter "digital".
    """
    ergebnisse: list[tuple[TitelEintrag, StartEintrag]] = []
    for rohdaten in _blaettere(
        session, api_key, "/discover/movie", MAX_SEITEN_DIGITAL,
        region="DE",
        with_release_type=DIGITAL_RELEASE_TYPE,
        sort_by="primary_release_date.asc",
        include_adult="false",
        **{"release_date.gte": ab.isoformat(), "release_date.lte": bis.isoformat()},
    ):
        if not _ist_relevant(rohdaten, MIN_POPULARITAET_DIGITAL):
            continue
        datum = rohdaten.get("release_date")
        if not datum:
            continue
        titel = _zu_titel_eintrag(rohdaten, "film")
        start = StartEintrag(
            tmdb_id=titel.tmdb_id,
            medientyp="film",
            anbieter="digital",
            startdatum=datum,
            art="digital",
        )
        ergebnisse.append((titel, start))
    return ergebnisse


def hole_kommende_serien(
    session: requests.Session,
    api_key: str,
    network_ids: list[int],
    anbieter_schluessel: str,
    ab: date,
    bis: date,
) -> list[tuple[TitelEintrag, StartEintrag]]:
    """Serien, die beim Anbieter im Zeitraum erstmals anlaufen (erste Staffel)."""
    if not network_ids:
        return []
    ergebnisse: list[tuple[TitelEintrag, StartEintrag]] = []
    for rohdaten in _blaettere(
        session, api_key, "/discover/tv", MAX_SEITEN_SERIEN,
        with_networks="|".join(str(n) for n in network_ids),
        sort_by="first_air_date.asc",
        include_adult="false",
        **{"first_air_date.gte": ab.isoformat(), "first_air_date.lte": bis.isoformat()},
    ):
        if not _ist_relevant(rohdaten, MIN_POPULARITAET_SERIE):
            continue
        datum = rohdaten.get("first_air_date")
        if not datum:
            continue
        titel = _zu_titel_eintrag(rohdaten, "serie")
        start = StartEintrag(
            tmdb_id=titel.tmdb_id,
            medientyp="serie",
            anbieter=anbieter_schluessel,
            startdatum=datum,
            art="serie",
            staffel=1,
        )
        ergebnisse.append((titel, start))
    return ergebnisse


def hole_kommende_staffeln(
    session: requests.Session,
    api_key: str,
    network_ids: list[int],
    anbieter_schluessel: str,
    ab: date,
    bis: date,
) -> list[tuple[TitelEintrag, StartEintrag]]:
    """Neue Staffeln laufender Serien beim Anbieter.

    TMDB hat dafuer keine eigene Abfrage. Der Weg in zwei Schritten: erst per
    air_date-Fenster alle Serien einsammeln, die im Zeitraum ueberhaupt eine
    Folge ausstrahlen, dann je Kandidat die Detailangabe next_episode_to_air
    holen. Nur wenn die naechste Folge die ERSTE einer Staffel ist
    (episode_number == 1), ist es ein Staffelstart - sonst laeuft die Staffel
    schon und die Serie gehoert nicht in eine Startliste (so fallen z.B.
    woechentliche Dauerlaeufer wie Talk- oder Animeserien heraus).
    """
    if not network_ids:
        return []
    kandidaten: list[dict] = []
    for rohdaten in _blaettere(
        session, api_key, "/discover/tv", MAX_SEITEN_SERIEN,
        with_networks="|".join(str(n) for n in network_ids),
        sort_by="popularity.desc",
        include_adult="false",
        **{"air_date.gte": ab.isoformat(), "air_date.lte": bis.isoformat()},
    ):
        if _ist_relevant(rohdaten, MIN_POPULARITAET_SERIE):
            kandidaten.append(rohdaten)
        if len(kandidaten) >= MAX_STAFFEL_KANDIDATEN:
            break

    ergebnisse: list[tuple[TitelEintrag, StartEintrag]] = []
    for rohdaten in kandidaten:
        try:
            detail = get_json(session, f"/tv/{rohdaten['id']}", api_key)
        except TmdbFehler as exc:
            logger.error("Detailabruf Serie %s fehlgeschlagen: %s", rohdaten.get("id"), exc)
            continue
        naechste = detail.get("next_episode_to_air") or {}
        if naechste.get("episode_number") != 1:
            continue
        datum = naechste.get("air_date")
        if not datum or not (ab.isoformat() <= datum <= bis.isoformat()):
            continue
        staffel = naechste.get("season_number")
        # Staffel 1 kommt bereits ueber hole_kommende_serien herein.
        if staffel is not None and staffel <= 1:
            continue
        titel = _zu_titel_eintrag(rohdaten, "serie")
        start = StartEintrag(
            tmdb_id=titel.tmdb_id,
            medientyp="serie",
            anbieter=anbieter_schluessel,
            startdatum=datum,
            art="staffel",
            staffel=staffel,
        )
        ergebnisse.append((titel, start))
    return ergebnisse
