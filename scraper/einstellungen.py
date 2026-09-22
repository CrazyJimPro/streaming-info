"""Laden/Speichern der Nutzer-Einstellungen (Zeitraum, aktive Anbieter/Genres, Merkliste)."""
from __future__ import annotations

import json
from pathlib import Path

PROJEKT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PFAD = PROJEKT_ROOT / "config" / "einstellungen.json"
CONFIG_VORLAGE_PFAD = PROJEKT_ROOT / "config" / "einstellungen.default.json"
ANBIETER_PFAD = PROJEKT_ROOT / "config" / "anbieter.json"
API_SCHLUESSEL_PFAD = PROJEKT_ROOT / "config" / "config.json"


def lade_einstellungen(config_pfad: Path = CONFIG_PFAD) -> dict:
    """Laedt die aktiven Einstellungen. Existieren sie noch nicht (frische
    Installation), werden sie einmalig aus der versionierten Vorlage
    einstellungen.default.json angelegt - config_pfad selbst ist bewusst
    NICHT im Git-Repo verfolgt (siehe .gitignore), damit eine
    Projekt-Auffrischung nie die persoenliche Auswahl ueberschreibt."""
    if not config_pfad.exists() and CONFIG_VORLAGE_PFAD.exists():
        config_pfad.write_text(CONFIG_VORLAGE_PFAD.read_text(encoding="utf-8"), encoding="utf-8")
    return json.loads(config_pfad.read_text(encoding="utf-8"))


def speichere_einstellungen(daten: dict, config_pfad: Path = CONFIG_PFAD) -> None:
    config_pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lade_anbieter(anbieter_pfad: Path = ANBIETER_PFAD) -> list[dict]:
    return json.loads(anbieter_pfad.read_text(encoding="utf-8"))["anbieter"]


def lade_api_schluessel(pfad: Path = API_SCHLUESSEL_PFAD) -> str | None:
    if not pfad.exists():
        return None
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return daten.get("tmdb_api_key") or None


def speichere_api_schluessel(schluessel: str, pfad: Path = API_SCHLUESSEL_PFAD) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"tmdb_api_key": schluessel.strip()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
