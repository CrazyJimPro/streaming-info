"""Sicherung und Wiederherstellung der persoenlichen Einstellungen.

Gesichert wird genau das, was sich nicht von selbst wiederbeschafft: die
Merkliste, die ausgeblendeten Titel, Zeitraum sowie Anbieter- und
Genre-/Sprachauswahl (config/einstellungen.json) und der TMDB-Schluessel
(config/config.json). **Nicht** gesichert wird data/streaming.db - das ist
reiner Abruf-Zwischenspeicher, den der naechste Scan in wenigen Sekunden neu
fuellt; sie in eine Sicherung zu packen wuerde die Datei nur aufblaehen und
alte Termine wieder einschleppen.

Vorbild ist das Sicherungs-Modell des Abo-Trackers: Sicherung als Download aus
der App heraus, Einspielen mit freier Dateiauswahl, Sicherheitskopie des
bisherigen Standes vor dem Ueberschreiben. Dort ist die Sicherung eine
SQLite-Datenbank, hier reicht eine kleine JSON-Datei - mehr gibt es nicht zu
retten.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from scraper.einstellungen import (
    CONFIG_PFAD,
    lade_api_schluessel,
    lade_einstellungen,
    speichere_api_schluessel,
    speichere_einstellungen,
)

# Kennung im Dateikopf. Gegenstueck zur Pruefung "sind die erwarteten Tabellen
# drin?" beim Abo-Tracker: verhindert, dass beim Einspielen irgendeine
# beliebige JSON-Datei als Sicherung durchgeht.
KENNUNG = "streaming-info-sicherung"

# Steigt nur, wenn sich der Aufbau der Datei so aendert, dass aeltere Staende
# nicht mehr ohne Umbau gelesen werden koennen. Eine Sicherung mit hoeherer
# Nummer stammt aus einer neueren Programmfassung und wird abgelehnt, statt
# halb verstanden eingespielt zu werden.
FORMAT_VERSION = 1


def erstelle_sicherung(version: str = "unbekannt") -> dict:
    """Baut den Inhalt einer Sicherungsdatei aus dem *gespeicherten* Stand.

    Ungespeicherte Aenderungen im geoeffneten Einstellungsformular sind also
    nicht enthalten - darauf weist die Einstellungsseite hin.
    """
    return {
        "typ": KENNUNG,
        "format": FORMAT_VERSION,
        "erstellt_am": datetime.now().isoformat(timespec="seconds"),
        "erstellt_mit_version": version,
        "einstellungen": lade_einstellungen(),
        # Der Schluessel gehoert bewusst mit hinein (Nutzerentscheidung): nach
        # dem Einspielen auf einem neuen Rechner laeuft das Tool sofort, ohne
        # ihn von Hand nachzutragen. Die Datei ist damit ein Geheimnistraeger
        # und sollte nicht weitergegeben werden - dieser Hinweis steht auch
        # neben dem Knopf in der App und im README.
        "tmdb_api_key": lade_api_schluessel(),
    }


def sicherungs_dateiname(zeitpunkt: datetime | None = None) -> str:
    """streaming-info-JJJJ-MM-TT.json - Ortszeit, nicht UTC.

    Mit UTC truege eine Sicherung kurz nach Mitternacht das Datum von gestern.
    """
    jetzt = zeitpunkt or datetime.now()
    return f"streaming-info-{jetzt:%Y-%m-%d}.json"


# --- Einspielen ------------------------------------------------------------

# Wie viele Sicherheitskopien (der Stand *vor* einem Einspielen) aufgehoben
# werden, bevor die aeltesten geloescht werden. Der Dateiname sortiert dank
# JJJJ-MM-TT-HHMMSS-Schema chronologisch.
SICHERHEITSKOPIEN_BEHALTEN = 10

MEDIENTYPEN = {"film", "serie"}


class SicherungsFehler(Exception):
    """Die uebergebene Datei taugt nicht als Sicherung. Der Text ist dafuer
    gedacht, dem Nutzer unveraendert angezeigt zu werden."""


def _liste_bereinigen(roh: object) -> tuple[list[dict], int]:
    """Filtert Merk-/Ausblendlisten auf brauchbare Eintraege.

    Liefert (Eintraege, Anzahl verworfener). Verworfen wird still, aber
    gezaehlt - lieber eine Sicherung teilweise einspielen und es sagen, als
    sie wegen eines kaputten Eintrags ganz abzulehnen.
    """
    if not isinstance(roh, list):
        return [], 0
    eintraege: list[dict] = []
    verworfen = 0
    for e in roh:
        try:
            tmdb_id = int(e["tmdb_id"])
            medientyp = str(e["medientyp"])
            titel = str(e.get("titel", ""))
        except (TypeError, KeyError, ValueError):
            verworfen += 1
            continue
        if medientyp not in MEDIENTYPEN:
            verworfen += 1
            continue
        # Doppelte zusammenfallen lassen: dieselbe ID kann in einer von Hand
        # bearbeiteten Datei mehrfach stehen.
        if any(v["tmdb_id"] == tmdb_id and v["medientyp"] == medientyp for v in eintraege):
            continue
        eintraege.append({"tmdb_id": tmdb_id, "medientyp": medientyp, "titel": titel})
    return eintraege, verworfen


def lies_sicherung(rohdaten: bytes | str, bekannte_anbieter: list[str] | None = None) -> dict:
    """Prueft eine hochgeladene Datei und gibt den bereinigten Inhalt zurueck.

    Wirft SicherungsFehler mit einem fuer den Nutzer lesbaren Text, wenn die
    Datei keine Sicherung dieses Programms ist. Der Bericht unter "notizen"
    haelt fest, was dabei uebergangen wurde.
    """
    if isinstance(rohdaten, bytes):
        # utf-8-sig: schluckt ein BOM, falls die Datei zwischendurch in einem
        # Editor gespeichert wurde, und liest sonst normales UTF-8.
        try:
            rohdaten = rohdaten.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise SicherungsFehler("Die Datei ist keine Textdatei - wurde vielleicht die falsche ausgewählt?")

    try:
        daten = json.loads(rohdaten)
    except json.JSONDecodeError:
        raise SicherungsFehler("Die Datei lässt sich nicht lesen. Erwartet wird eine JSON-Sicherung dieses Programms.")

    if not isinstance(daten, dict) or daten.get("typ") != KENNUNG:
        raise SicherungsFehler("Das ist keine Streaming-Info-Sicherung. Erwartet wird eine Datei wie streaming-info-2026-09-28.json.")

    # Eine Sicherung aus einer neueren Fassung kann Felder tragen, die dieser
    # Stand nicht kennt - halb eingespielt waere schlimmer als gar nicht.
    # Gegenstueck zur Migrationspruefung im Abo-Tracker.
    try:
        format_version = int(daten.get("format", 0))
    except (TypeError, ValueError):
        format_version = 0
    if format_version > FORMAT_VERSION:
        raise SicherungsFehler("Die Sicherung stammt aus einer neueren Programmfassung. Bitte zuerst Streaming-Info aktualisieren.")

    roh_einstellungen = daten.get("einstellungen")
    if not isinstance(roh_einstellungen, dict):
        raise SicherungsFehler("In der Sicherung fehlen die Einstellungen.")

    notizen: list[str] = []
    einstellungen: dict = {}

    try:
        wochen = int(roh_einstellungen.get("zeitraum_wochen", 8))
    except (TypeError, ValueError):
        wochen = 8
    einstellungen["zeitraum_wochen"] = min(52, max(1, wochen))

    roh_anbieter = roh_einstellungen.get("aktive_anbieter")
    anbieter = [str(a) for a in roh_anbieter] if isinstance(roh_anbieter, list) else []
    if bekannte_anbieter is not None:
        unbekannt = [a for a in anbieter if a not in bekannte_anbieter]
        if unbekannt:
            notizen.append(f"{len(unbekannt)} unbekannte(r) Anbieter übergangen")
        anbieter = [a for a in anbieter if a in bekannte_anbieter]
    einstellungen["aktive_anbieter"] = anbieter

    # Genres werden bewusst NICHT gegen data/genres.json geprueft: dieser
    # Zwischenspeicher wird erst beim ersten Scan gefuellt, auf einer frischen
    # Installation waere er leer - und die Genre-Auswahl ginge beim Einspielen
    # komplett verloren.
    roh_genres = roh_einstellungen.get("aktive_genres")
    einstellungen["aktive_genres"] = (
        [int(g) for g in roh_genres if str(g).lstrip("-").isdigit()] if isinstance(roh_genres, list) else []
    )

    # Sprachen: kurze Buchstaben-Codes, wie TMDB sie fuehrt. Aeltere
    # Sicherungen (vor v0.8.0) haben das Feld nicht - dann kein Filter.
    roh_sprachen = roh_einstellungen.get("sprachen")
    einstellungen["sprachen"] = (
        sorted({str(c).strip().lower() for c in roh_sprachen if str(c).strip().isalpha() and len(str(c).strip()) <= 3})
        if isinstance(roh_sprachen, list)
        else []
    )

    # Wer eine Sicherung einspielt, hat sich eingerichtet: der Wegweiser fuer
    # frische Installationen auf der Startseite ist damit erledigt.
    einstellungen["einrichtung_erledigt"] = True

    einstellungen["merkliste"], verworfen_merk = _liste_bereinigen(roh_einstellungen.get("merkliste"))
    einstellungen["ausgeblendet"], verworfen_aus = _liste_bereinigen(roh_einstellungen.get("ausgeblendet"))
    if verworfen_merk or verworfen_aus:
        notizen.append(f"{verworfen_merk + verworfen_aus} unlesbare(r) Titeleintrag übergangen")

    schluessel = daten.get("tmdb_api_key")
    schluessel = schluessel.strip() if isinstance(schluessel, str) and schluessel.strip() else None

    return {
        "einstellungen": einstellungen,
        "tmdb_api_key": schluessel,
        "erstellt_am": str(daten.get("erstellt_am", "")),
        "erstellt_mit_version": str(daten.get("erstellt_mit_version", "")),
        "notizen": notizen,
    }


def sicherheitskopie_anlegen(version: str = "unbekannt", ordner: Path | None = None) -> Path | None:
    """Legt den *bisherigen* Stand als vor-wiederherstellung-<Zeit>.json ab.

    Bewusst im selben Sicherungsformat: die Kopie laesst sich damit genauso
    wieder einspielen wie eine normale Sicherung - eine Rueckfahrkarte, die
    man nicht lesen kann, waere keine. Gibt es noch keine Einstellungen
    (frische Installation), gibt es auch nichts zu sichern: None.
    """
    ordner = ordner or CONFIG_PFAD.parent
    if not CONFIG_PFAD.exists():
        return None
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"vor-wiederherstellung-{datetime.now():%Y-%m-%d-%H%M%S}.json"
    ziel.write_text(
        json.dumps(erstelle_sicherung(version), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Aelteste wegraeumen, damit der Ordner nicht endlos voll laeuft. Der
    # Zeitstempel im Namen sortiert chronologisch.
    alle = sorted(ordner.glob("vor-wiederherstellung-*.json"))
    for veraltet in alle[:-SICHERHEITSKOPIEN_BEHALTEN]:
        veraltet.unlink(missing_ok=True)
    return ziel


def spiele_sicherung_ein(rohdaten: bytes | str, bekannte_anbieter: list[str] | None = None, version: str = "unbekannt") -> dict:
    """Prueft die Datei, sichert den bisherigen Stand und spielt sie ein.

    Erst wenn die Pruefung durch ist, wird irgendetwas geschrieben - eine
    abgelehnte Datei laesst den bisherigen Stand voellig unberuehrt.
    """
    gepruefte = lies_sicherung(rohdaten, bekannte_anbieter)

    sicherheitskopie = sicherheitskopie_anlegen(version)
    speichere_einstellungen(gepruefte["einstellungen"])
    if gepruefte["tmdb_api_key"]:
        speichere_api_schluessel(gepruefte["tmdb_api_key"])

    return {
        "merkliste": len(gepruefte["einstellungen"]["merkliste"]),
        "ausgeblendet": len(gepruefte["einstellungen"]["ausgeblendet"]),
        "schluessel_uebernommen": bool(gepruefte["tmdb_api_key"]),
        "erstellt_am": gepruefte["erstellt_am"],
        "sicherheitskopie": sicherheitskopie.name if sicherheitskopie else None,
        "notizen": gepruefte["notizen"],
    }
