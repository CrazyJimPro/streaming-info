"""Wendet Genre-Auswahl, Merkliste und Ausblend-Liste aus den Einstellungen
auf die rohen Datenbank-Zeilen an. Reine Python-Filterung (wie beim
Reality-TV-Tool) statt komplexer SQL - die Datenmengen sind klein genug."""
from __future__ import annotations


def _genre_ids(zeile: dict) -> set[int]:
    roh = zeile.get("genre_ids") or ""
    return {int(g) for g in roh.split(",") if g}


def _ist_in_liste(zeile: dict, liste: list[dict]) -> bool:
    return any(e["tmdb_id"] == zeile["tmdb_id"] and e["medientyp"] == zeile["medientyp"] for e in liste)


def filtere_zeilen(zeilen: list[dict], einstellungen: dict) -> list[dict]:
    aktive_genres = set(einstellungen.get("aktive_genres", []))
    merkliste = einstellungen.get("merkliste", [])
    ausgeblendet = einstellungen.get("ausgeblendet", [])

    ergebnis = []
    for zeile in zeilen:
        if _ist_in_liste(zeile, ausgeblendet):
            continue
        if _ist_in_liste(zeile, merkliste):
            ergebnis.append(zeile)
            continue
        # Kein Genre ausgewaehlt = kein Filter, alles anzeigen.
        if not aktive_genres or (_genre_ids(zeile) & aktive_genres):
            ergebnis.append(zeile)
    return ergebnis
