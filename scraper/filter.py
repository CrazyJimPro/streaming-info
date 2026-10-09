"""Wendet Genre- und Sprachauswahl, Merkliste und Ausblend-Liste aus den Einstellungen
auf die rohen Datenbank-Zeilen an. Reine Python-Filterung (wie beim
Reality-TV-Tool) statt komplexer SQL - die Datenmengen sind klein genug."""
from __future__ import annotations

# Originalsprachen (ISO 639-1, so wie TMDB sie in original_language fuehrt),
# die in der Einstellungsauswahl immer angeboten werden - auch wenn gerade
# kein Titel in der Sprache ansteht. Weitere Codes, die in den Daten
# auftauchen, kommen in der Auswahl automatisch dazu.
SPRACHNAMEN = {
    "de": "Deutsch",
    "en": "Englisch",
    "fr": "Französisch",
    "es": "Spanisch",
    "it": "Italienisch",
    "nl": "Niederländisch",
    "da": "Dänisch",
    "sv": "Schwedisch",
    "no": "Norwegisch",
    "fi": "Finnisch",
    "pl": "Polnisch",
    "pt": "Portugiesisch",
    "tr": "Türkisch",
    "ru": "Russisch",
    "ja": "Japanisch",
    "ko": "Koreanisch",
    "zh": "Chinesisch",
    "cn": "Kantonesisch",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "th": "Thailändisch",
    "ar": "Arabisch",
    "tl": "Tagalog",
    "id": "Indonesisch",
    "he": "Hebräisch",
    "cs": "Tschechisch",
    "hu": "Ungarisch",
    "el": "Griechisch",
    "uk": "Ukrainisch",
}


def _genre_ids(zeile: dict) -> set[int]:
    roh = zeile.get("genre_ids") or ""
    return {int(g) for g in roh.split(",") if g}


def _ist_in_liste(zeile: dict, liste: list[dict]) -> bool:
    return any(e["tmdb_id"] == zeile["tmdb_id"] and e["medientyp"] == zeile["medientyp"] for e in liste)


def filtere_zeilen(zeilen: list[dict], einstellungen: dict) -> list[dict]:
    aktive_genres = set(einstellungen.get("aktive_genres", []))
    sprachen = set(einstellungen.get("sprachen", []))
    merkliste = einstellungen.get("merkliste", [])
    ausgeblendet = einstellungen.get("ausgeblendet", [])

    ergebnis = []
    for zeile in zeilen:
        if _ist_in_liste(zeile, ausgeblendet):
            continue
        if _ist_in_liste(zeile, merkliste):
            ergebnis.append(zeile)
            continue
        # Keine Sprache ausgewaehlt = kein Filter. Titel ohne bekannte Sprache
        # (Datenbank von vor v0.8.0, noch nicht neu abgerufen) bleiben sichtbar,
        # statt bis zum naechsten Scan stillschweigend zu verschwinden.
        sprache = zeile.get("originalsprache")
        if sprachen and sprache and sprache not in sprachen:
            continue
        # Kein Genre ausgewaehlt = kein Filter, alles anzeigen.
        if not aktive_genres or (_genre_ids(zeile) & aktive_genres):
            ergebnis.append(zeile)
    return ergebnis
