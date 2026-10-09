"""Baut eine .ics-Kalenderdatei aus den Start-Eintraegen der Startseite.

Bewusst ohne Zusatzpaket (das Projekt braucht sonst nur flask/requests) -
das iCalendar-Format (RFC 5545) ist fuer das bisschen hier von Hand schnell
und ohne Fallstricke gebaut: ein VEVENT je Karte, ganztaegig (die Daten von
TMDB sind Tagesdaten, keine Uhrzeiten).

Die Datei spiegelt genau das, was die Startseite gerade zeigt (Zeitraum,
Anbieter-/Genre-/Sprachfilter) - wer die URL als Kalender-Abo eintraegt,
bekommt bei jedem Abruf den aktuellen Stand, solange die App laeuft. Die
Merkliste ist bewusst nicht dabei: sie hat mit "Jetzt verfuegbar" schon eine
eigene Behandlung, und viele ihrer Eintraege haben gar kein Datum.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _falte(zeile: str) -> str:
    """RFC 5545 verlangt eine Zeile nicht laenger als 75 Oktette - laengere
    werden mit \\r\\n plus einem fuehrenden Leerzeichen fortgesetzt.

    In Oktetten, nicht Zeichen geschnitten: ein Titel mit "–" oder
    thailaendischen Zeichen braucht sonst pro Zeichen mehrere Bytes, und ein
    Schnitt nach fester Zeichenzahl landet dann leicht ueber dem Limit."""
    roh = zeile.encode("utf-8")
    if len(roh) <= 75:
        return zeile
    teile = []
    rest = roh
    while len(rest) > 75:
        schnitt = 74
        # Nicht mitten in einem mehrbytigen UTF-8-Zeichen trennen -
        # Fortsetzungsbytes (10xxxxxx) zaehlen nicht als Zeichenanfang.
        while schnitt > 0 and (rest[schnitt] & 0xC0) == 0x80:
            schnitt -= 1
        teile.append(rest[:schnitt].decode("utf-8"))
        rest = rest[schnitt:]
    teile.append(rest.decode("utf-8"))
    return "\r\n ".join(teile)


def _ereignis(uid: str, titel: str, beschreibung: str, startdatum: str) -> list[str]:
    start = datetime.strptime(startdatum, "%Y-%m-%d").date()
    ende = start + timedelta(days=1)
    jetzt = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return [
        "BEGIN:VEVENT",
        _falte(f"UID:{uid}@streaming-info.local"),
        f"DTSTAMP:{jetzt}",
        f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{ende.strftime('%Y%m%d')}",
        _falte(f"SUMMARY:{_escape(titel)}"),
        _falte(f"DESCRIPTION:{_escape(beschreibung)}"),
        "END:VEVENT",
    ]


def baue_ics(streaming: list[dict], kino: list[dict], digital: list[dict]) -> str:
    zeilen = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//streaming-info//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Streaming-Info",
    ]

    for eintrag in streaming:
        anbieter = ", ".join(a["name"] for a in eintrag.get("anbieter_liste", []))
        titel = eintrag["titel"]
        if eintrag.get("zusatz"):
            titel = f"{titel} ({eintrag['zusatz']})"
        zeilen += _ereignis(
            f"{eintrag['tmdb_id']}-{eintrag['medientyp']}-{eintrag.get('art')}-{eintrag['startdatum']}",
            f"{titel} – {anbieter}" if anbieter else titel,
            f"Neu bei {anbieter}." if anbieter else "",
            eintrag["startdatum"],
        )

    for eintrag in kino:
        zeilen += _ereignis(
            f"{eintrag['tmdb_id']}-{eintrag['medientyp']}-kino-{eintrag['startdatum']}",
            f"{eintrag['titel']} – Kinostart",
            "Deutscher Kinostart.",
            eintrag["startdatum"],
        )

    for eintrag in digital:
        zeilen += _ereignis(
            f"{eintrag['tmdb_id']}-{eintrag['medientyp']}-digital-{eintrag['startdatum']}",
            f"{eintrag['titel']} – Digital",
            "Start digital/VOD (TMDB nennt dafuer keine Plattform).",
            eintrag["startdatum"],
        )

    zeilen.append("END:VCALENDAR")
    return "\r\n".join(zeilen) + "\r\n"
