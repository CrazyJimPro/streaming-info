@echo off
rem Wird von der Desktop-Verknuepfung (per start_versteckt.vbs, versteckt)
rem aufgerufen. Leitet alle Meldungen von start.bat in logs\start.log um,
rem da bei versteckter Ausfuehrung kein Konsolenfenster sichtbar ist.
rem
rem WICHTIG: start.bat wird hier ueber den vollen Pfad (%~dp0) aufgerufen,
rem nicht als blosser Dateiname - siehe reality-tv-programm/start_versteckt.bat
rem fuer die ausfuehrliche Begruendung (NoDefaultCurrentDirectoryInExePath).
cd /d "%~dp0"
if not exist logs mkdir logs
call "%~dp0start.bat" > logs\start.log 2>&1
