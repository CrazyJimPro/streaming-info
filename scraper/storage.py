"""SQLite-Speicherung der Titel und ihrer angekuendigten Starts.

Gespeichert wird, WANN etwas anlaeuft - nicht, was gerade im Katalog liegt.
Die Tabelle 'starts' haelt je Titel und Anbieter ein Startereignis mit Datum
und Art (neue Serie, neue Staffel, Kinostart, digitaler Filmstart). Ein
erneuter Lauf aktualisiert ein bereits bekanntes Ereignis, damit verschobene
Termine nachziehen; 'gesehen_am' verraet, wann die Angabe zuletzt bestaetigt
wurde.

Vorgeschichte: Bis v0.1.1 stand hier eine Tabelle 'verfuegbarkeit', die sich
ueber wiederholte Laeufe selbst zusammenreimte, wann ein Titel neu in einem
Katalog auftauchte ("neu dazugekommen"). Das beantwortete aber die falsche
Frage - interessant ist, was noch kommt, nicht was schon da ist. Die alte
Tabelle wird nicht mehr beschrieben oder gelesen.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from scraper.base import StartEintrag, TitelEintrag

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
DB_PFAD = PROJEKT_ROOT / "data" / "streaming.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS titel (
    tmdb_id INTEGER NOT NULL,
    medientyp TEXT NOT NULL,
    titel TEXT NOT NULL,
    overview TEXT,
    poster_pfad TEXT,
    erscheinungsdatum TEXT,
    genre_ids TEXT NOT NULL DEFAULT '',
    kinostart_de TEXT,
    aktualisiert_am TEXT NOT NULL,
    PRIMARY KEY (tmdb_id, medientyp)
);

CREATE TABLE IF NOT EXISTS starts (
    tmdb_id INTEGER NOT NULL,
    medientyp TEXT NOT NULL,
    anbieter TEXT NOT NULL,
    startdatum TEXT NOT NULL,
    art TEXT NOT NULL,
    staffel INTEGER,
    gesehen_am TEXT NOT NULL,
    PRIMARY KEY (tmdb_id, medientyp, anbieter, art)
);

CREATE INDEX IF NOT EXISTS starts_datum ON starts (startdatum);

CREATE TABLE IF NOT EXISTS quellen_status (
    quelle TEXT PRIMARY KEY,
    letzter_erfolg_am TEXT,
    letzter_fehler TEXT,
    letzter_fehler_am TEXT
);
"""


def _verbindung(db_pfad: Path = DB_PFAD) -> sqlite3.Connection:
    db_pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_pfad)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_pfad: Path = DB_PFAD) -> None:
    with closing(_verbindung(db_pfad)) as conn, conn:
        conn.executescript(SCHEMA)


def speichere_titel(eintraege: list[TitelEintrag], db_pfad: Path = DB_PFAD) -> None:
    jetzt = datetime.now().isoformat(timespec="seconds")
    with closing(_verbindung(db_pfad)) as conn, conn:
        conn.executemany(
            """
            INSERT INTO titel (tmdb_id, medientyp, titel, overview, poster_pfad, erscheinungsdatum, genre_ids, kinostart_de, aktualisiert_am)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tmdb_id, medientyp) DO UPDATE SET
                titel = excluded.titel,
                overview = excluded.overview,
                poster_pfad = excluded.poster_pfad,
                erscheinungsdatum = excluded.erscheinungsdatum,
                genre_ids = excluded.genre_ids,
                kinostart_de = COALESCE(excluded.kinostart_de, kinostart_de),
                aktualisiert_am = excluded.aktualisiert_am
            """,
            [
                (
                    e.tmdb_id,
                    e.medientyp,
                    e.titel,
                    e.overview,
                    e.poster_pfad,
                    e.erscheinungsdatum,
                    ",".join(str(g) for g in e.genre_ids),
                    e.kinostart_de,
                    jetzt,
                )
                for e in eintraege
            ],
        )


def speichere_starts(eintraege: list[StartEintrag], heute: date, db_pfad: Path = DB_PFAD) -> None:
    """Schreibt Startereignisse. Ein schon bekanntes Ereignis wird
    aktualisiert - so ziehen verschobene Termine beim naechsten Lauf nach."""
    heute_iso = heute.isoformat()
    with closing(_verbindung(db_pfad)) as conn, conn:
        conn.executemany(
            """
            INSERT INTO starts (tmdb_id, medientyp, anbieter, startdatum, art, staffel, gesehen_am)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tmdb_id, medientyp, anbieter, art) DO UPDATE SET
                startdatum = excluded.startdatum,
                staffel = excluded.staffel,
                gesehen_am = excluded.gesehen_am
            """,
            [
                (e.tmdb_id, e.medientyp, e.anbieter, e.startdatum, e.art, e.staffel, heute_iso)
                for e in eintraege
            ],
        )


def hole_merkliste_eintraege(merkliste: list[dict], db_pfad: Path = DB_PFAD) -> list[dict]:
    """Liefert je gemerktem Titel die bekannten Angaben - mit Starttermin,
    falls einer vorliegt, sonst ohne.

    Anders als bei den uebrigen Abschnitten wird hier NICHT gefiltert: Ein
    gemerkter Titel erscheint auch ohne Termin, damit sichtbar bleibt, dass er
    beobachtet wird. Titel, die noch nie abgerufen wurden (frisch gemerkt, vor
    dem naechsten Scan), kommen mit dem in der Merkliste gespeicherten Namen.
    """
    ergebnis: list[dict] = []
    with closing(_verbindung(db_pfad)) as conn:
        for eintrag in merkliste:
            tmdb_id, medientyp = eintrag.get("tmdb_id"), eintrag.get("medientyp")
            row = conn.execute(
                """
                SELECT t.*, s.startdatum, s.art, s.staffel
                FROM titel t
                LEFT JOIN starts s
                  ON s.tmdb_id = t.tmdb_id AND s.medientyp = t.medientyp AND s.art = 'merkliste'
                WHERE t.tmdb_id = ? AND t.medientyp = ?
                """,
                (tmdb_id, medientyp),
            ).fetchone()
            if row:
                ergebnis.append(dict(row))
            else:
                ergebnis.append(
                    {
                        "tmdb_id": tmdb_id,
                        "medientyp": medientyp,
                        "titel": eintrag.get("titel") or "(unbekannt)",
                        "poster_pfad": None,
                        "genre_ids": "",
                        "startdatum": None,
                        "art": "merkliste",
                        "staffel": None,
                    }
                )
    # Titel mit Termin zuerst, das Naechste oben; alles Weitere dahinter.
    ergebnis.sort(key=lambda e: (e.get("startdatum") is None, e.get("startdatum") or ""))
    return ergebnis


def entferne_unbestaetigte_starts(anbieter: str, stand: date, db_pfad: Path = DB_PFAD) -> int:
    """Entfernt Startereignisse eines Anbieters, die im Lauf vom 'stand' nicht
    mehr gemeldet wurden.

    Ohne das bliebe ein einmal gespeicherter Termin ewig stehen, auch wenn
    TMDB ihn gar nicht mehr fuehrt - ein abgesagter oder weit verschobener
    Start wuerde also weiter als bevorstehend angezeigt. Verglichen wird
    'gesehen_am': was der aktuelle Lauf angefasst hat, traegt sein Datum.

    Wichtig: Das darf nur je Anbieter geschehen und nur nach einem
    ERFOLGREICHEN Abruf - sonst wuerde ein Netzwerkfehler die vorhandenen
    Termine dieses Anbieters mit loeschen.
    """
    with closing(_verbindung(db_pfad)) as conn, conn:
        cur = conn.execute(
            "DELETE FROM starts WHERE anbieter = ? AND gesehen_am < ?",
            (anbieter, stand.isoformat()),
        )
        return cur.rowcount


def raeume_starts_auf(vor_datum: date, db_pfad: Path = DB_PFAD) -> int:
    """Entfernt Startereignisse, die laengst vorbei sind. Ohne das wuechse die
    Tabelle mit jedem Lauf weiter, obwohl nur Zukuenftiges angezeigt wird."""
    with closing(_verbindung(db_pfad)) as conn, conn:
        cur = conn.execute("DELETE FROM starts WHERE startdatum < ?", (vor_datum.isoformat(),))
        return cur.rowcount


def markiere_quelle_erfolg(quelle: str, db_pfad: Path = DB_PFAD) -> None:
    jetzt = datetime.now().isoformat(timespec="seconds")
    with closing(_verbindung(db_pfad)) as conn, conn:
        conn.execute(
            """
            INSERT INTO quellen_status (quelle, letzter_erfolg_am, letzter_fehler, letzter_fehler_am)
            VALUES (?, ?, NULL, NULL)
            ON CONFLICT(quelle) DO UPDATE SET letzter_erfolg_am = excluded.letzter_erfolg_am
            """,
            (quelle, jetzt),
        )


def markiere_quelle_fehler(quelle: str, fehlertext: str, db_pfad: Path = DB_PFAD) -> None:
    jetzt = datetime.now().isoformat(timespec="seconds")
    with closing(_verbindung(db_pfad)) as conn, conn:
        conn.execute(
            """
            INSERT INTO quellen_status (quelle, letzter_erfolg_am, letzter_fehler, letzter_fehler_am)
            VALUES (?, NULL, ?, ?)
            ON CONFLICT(quelle) DO UPDATE SET letzter_fehler = excluded.letzter_fehler, letzter_fehler_am = excluded.letzter_fehler_am
            """,
            (quelle, fehlertext, jetzt),
        )


def hole_quellen_status(db_pfad: Path = DB_PFAD) -> list[dict]:
    with closing(_verbindung(db_pfad)) as conn:
        rows = conn.execute("SELECT * FROM quellen_status ORDER BY quelle").fetchall()
        return [dict(row) for row in rows]


def hole_starts_im_zeitraum(
    ab_datum: date, bis_datum: date, arten: tuple[str, ...], db_pfad: Path = DB_PFAD
) -> list[dict]:
    """Angekuendigte Starts der gewuenschten Arten im Zeitraum, das frueheste
    zuerst. 'arten' waehlt die Sektion aus: ("serie", "staffel") fuer die
    Streaming-Starts, ("digital",) fuer digitale Filmstarts."""
    platzhalter = ",".join("?" for _ in arten)
    with closing(_verbindung(db_pfad)) as conn:
        rows = conn.execute(
            f"""
            SELECT t.*, s.anbieter, s.startdatum, s.art, s.staffel
            FROM starts s
            JOIN titel t ON t.tmdb_id = s.tmdb_id AND t.medientyp = s.medientyp
            WHERE s.startdatum >= ? AND s.startdatum <= ? AND s.art IN ({platzhalter})
            ORDER BY s.startdatum ASC
            """,
            (ab_datum.isoformat(), bis_datum.isoformat(), *arten),
        ).fetchall()
        return [dict(row) for row in rows]


