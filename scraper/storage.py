"""SQLite-Speicherung der Titel, ihrer Anbieter-Verfuegbarkeit und Kinostarts.

Der Kern der "neu"-Erkennung fuer Streaming-Anbieter: TMDB liefert kein
"hinzugefuegt am"-Datum, also merkt sich die Tabelle 'verfuegbarkeit' bei
jedem Lauf selbst, wann ein Titel bei einem Anbieter zum ersten Mal gesehen
wurde (erstmals_gesehen_am). Ein INSERT ... ON CONFLICT DO NOTHING auf den
Zeitpunkt sorgt dafuer, dass dieses Datum nach dem ersten Mal nie wieder
veraendert wird.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from scraper.base import TitelEintrag

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

CREATE TABLE IF NOT EXISTS verfuegbarkeit (
    tmdb_id INTEGER NOT NULL,
    medientyp TEXT NOT NULL,
    anbieter TEXT NOT NULL,
    erstmals_gesehen_am TEXT NOT NULL,
    zuletzt_gesehen_am TEXT NOT NULL,
    PRIMARY KEY (tmdb_id, medientyp, anbieter)
);

CREATE TABLE IF NOT EXISTS anbieter_provider_ids (
    anbieter TEXT NOT NULL,
    medientyp TEXT NOT NULL,
    tmdb_provider_id INTEGER NOT NULL,
    aufgeloest_am TEXT NOT NULL,
    PRIMARY KEY (anbieter, medientyp)
);

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


def speichere_verfuegbarkeit(
    tmdb_id: int, medientyp: str, anbieter: str, heute: date, db_pfad: Path = DB_PFAD
) -> None:
    heute_iso = heute.isoformat()
    with closing(_verbindung(db_pfad)) as conn, conn:
        conn.execute(
            """
            INSERT INTO verfuegbarkeit (tmdb_id, medientyp, anbieter, erstmals_gesehen_am, zuletzt_gesehen_am)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tmdb_id, medientyp, anbieter) DO UPDATE SET zuletzt_gesehen_am = excluded.zuletzt_gesehen_am
            """,
            (tmdb_id, medientyp, anbieter, heute_iso, heute_iso),
        )


def hole_anbieter_provider_id(anbieter: str, medientyp: str, db_pfad: Path = DB_PFAD) -> int | None:
    with closing(_verbindung(db_pfad)) as conn:
        row = conn.execute(
            "SELECT tmdb_provider_id FROM anbieter_provider_ids WHERE anbieter = ? AND medientyp = ?",
            (anbieter, medientyp),
        ).fetchone()
        return row["tmdb_provider_id"] if row else None


def speichere_anbieter_provider_id(
    anbieter: str, medientyp: str, provider_id: int, db_pfad: Path = DB_PFAD
) -> None:
    jetzt = datetime.now().isoformat(timespec="seconds")
    with closing(_verbindung(db_pfad)) as conn, conn:
        conn.execute(
            """
            INSERT INTO anbieter_provider_ids (anbieter, medientyp, tmdb_provider_id, aufgeloest_am)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(anbieter, medientyp) DO UPDATE SET
                tmdb_provider_id = excluded.tmdb_provider_id, aufgeloest_am = excluded.aufgeloest_am
            """,
            (anbieter, medientyp, provider_id, jetzt),
        )


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


def hole_streaming_neuheiten(ab_datum: date, db_pfad: Path = DB_PFAD) -> list[dict]:
    """Alle Titel, die bei mindestens einem Anbieter seit ab_datum neu gesehen wurden."""
    with closing(_verbindung(db_pfad)) as conn:
        rows = conn.execute(
            """
            SELECT t.*, v.anbieter, v.erstmals_gesehen_am
            FROM verfuegbarkeit v
            JOIN titel t ON t.tmdb_id = v.tmdb_id AND t.medientyp = v.medientyp
            WHERE v.erstmals_gesehen_am >= ?
            ORDER BY v.erstmals_gesehen_am DESC
            """,
            (ab_datum.isoformat(),),
        ).fetchall()
        return [dict(row) for row in rows]


def hole_kinostarts_im_zeitraum(ab_datum: date, bis_datum: date, db_pfad: Path = DB_PFAD) -> list[dict]:
    with closing(_verbindung(db_pfad)) as conn:
        rows = conn.execute(
            """
            SELECT * FROM titel
            WHERE kinostart_de >= ? AND kinostart_de <= ?
            ORDER BY kinostart_de ASC
            """,
            (ab_datum.isoformat(), bis_datum.isoformat()),
        ).fetchall()
        return [dict(row) for row in rows]
