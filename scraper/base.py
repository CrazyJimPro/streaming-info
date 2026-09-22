"""Gemeinsame Datenstrukturen und HTTP-Hilfsfunktionen fuer die TMDB-Anbindung."""
from __future__ import annotations

from dataclasses import dataclass

import requests

USER_AGENT = "Streaming-Info-Privatscraper/1.0"
REQUEST_TIMEOUT = 15
API_BASIS_URL = "https://api.themoviedb.org/3"


@dataclass
class TitelEintrag:
    """Ein Film oder eine Serie, wie TMDB ihn liefert."""

    tmdb_id: int
    medientyp: str  # "film" oder "serie"
    titel: str
    overview: str | None
    poster_pfad: str | None
    erscheinungsdatum: str | None
    genre_ids: list[int]
    kinostart_de: str | None = None


class TmdbFehler(Exception):
    """Wird geworfen, wenn ein TMDB-Aufruf fehlschlaegt."""


class TmdbApiSchluesselFehlt(TmdbFehler):
    """Wird geworfen, wenn noch kein API-Schluessel hinterlegt ist."""


def neue_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def get_json(session: requests.Session, pfad: str, api_key: str, **params) -> dict:
    if not api_key:
        raise TmdbApiSchluesselFehlt("Kein TMDB-API-Schluessel hinterlegt.")
    query = {"api_key": api_key, "language": "de-DE", **params}
    try:
        response = session.get(f"{API_BASIS_URL}{pfad}", params=query, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise TmdbFehler(f"Netzwerkfehler bei {pfad}: {exc}") from exc
    if response.status_code == 401:
        raise TmdbApiSchluesselFehlt("TMDB hat den API-Schluessel abgelehnt (ungueltig).")
    if response.status_code == 429:
        raise TmdbFehler("TMDB-Ratelimit erreicht (429) - spaeter erneut versuchen.")
    if response.status_code >= 400:
        raise TmdbFehler(f"HTTP {response.status_code} bei {pfad}: {response.text[:200]}")
    return response.json()
