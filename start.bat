@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Streaming-Info ===
echo.

set "ZIEL_ORDNER=%USERPROFILE%\streaming-info"

rem --- -1. Pruefen, ob auf GitHub eine neuere Version liegt. Verglichen wird
rem     die Versionsnummer aus der Datei VERSION - und aufgefrischt wird nur,
rem     wenn die dort WIRKLICH neuer ist. Wird aufgefrischt, kommen alle
rem     Dateien ohnehin in ihrer neuen Fassung mit (Schritt 0). Nach dem
rem     bewaehrten Muster von reality-tv-programm/start.bat. ---
set "NEUERE_VERSION_GEFUNDEN="
call :pruefe_version

rem --- 0. Projektordner bestimmen und bei Bedarf (neu) laden: entweder weil
rem     hier noch gar kein komplettes Projekt liegt (nur diese eine Datei
rem     wurde heruntergeladen), oder weil Schritt -1 eine neuere Version
rem     gefunden hat. In beiden Faellen wird der KOMPLETTE Code von GitHub
rem     aufgefrischt (nicht nur start.bat), venv/data/logs bleiben dabei
rem     unberuehrt (die liegen nicht im heruntergeladenen Quellcode). ---
rem     WICHTIG: Laeuft dieses Skript AUS dem Ordner, der aufgefrischt wird,
rem     darf es sich dabei nicht selbst ueberschreiben - cmd.exe liest eine
rem     Batchdatei waehrend der Ausfuehrung immer wieder von der Platte
rem     (an der zuletzt erreichten Byte-Position). Wird sie unter den Fuessen
rem     ausgetauscht, laeuft danach ein wilder Mix aus alter und neuer Datei.
rem     Deshalb: start.bat/start_versteckt.bat in diesem Fall auslassen, die
rem     neue start.bat nach %TEMP% legen und von dort neu starten - der
rem     Neustart aus %TEMP% frischt den Ordner dann komplett auf (dann laeuft
rem     ja keine Datei mehr aus dem Zielordner).
if exist "requirements.txt" (
    set "PROJEKT_ZIEL=%cd%"
    set "EIGENEN_ORDNER=1"
    set "NEUSTART_DATEI=%TEMP%\si_start_neu.bat"
) else (
    set "PROJEKT_ZIEL=%ZIEL_ORDNER%"
    set "EIGENEN_ORDNER="
    set "NEUSTART_DATEI=%ZIEL_ORDNER%\start.bat"
)

set "MUSS_LADEN="
if not exist "requirements.txt" set "MUSS_LADEN=1"
if defined NEUERE_VERSION_GEFUNDEN set "MUSS_LADEN=1"

if defined MUSS_LADEN (
    echo Lade aktuellen Projektstand von GitHub ^(Code + Web-App werden aufgefrischt^)...
    rem PowerShell-Logik in eine temporaere .ps1-Datei schreiben statt als
    rem Inline-Befehl - vermeidet fragile verschachtelte Anfuehrungszeichen.
    > "%TEMP%\si_download.ps1" (
        echo $ErrorActionPreference = 'Stop'
        echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        echo Invoke-WebRequest -Uri 'https://github.com/CrazyJimPro/streaming-info/archive/refs/heads/main.zip' -OutFile "$env:TEMP\si.zip"
        echo Expand-Archive -Path "$env:TEMP\si.zip" -DestinationPath "$env:TEMP\si-extract" -Force
        echo New-Item -ItemType Directory -Force -Path '%PROJEKT_ZIEL%' ^| Out-Null
        echo $quelle = "$env:TEMP\si-extract\streaming-info-main"
        echo $ausnahmen = @^(^)
        echo if ^('%EIGENEN_ORDNER%' -eq '1'^) { $ausnahmen = @^('start.bat','start_versteckt.bat'^) }
        echo Get-ChildItem -Path $quelle -Force ^| Where-Object { $ausnahmen -notcontains $_.Name } ^| Copy-Item -Destination '%PROJEKT_ZIEL%' -Recurse -Force
        echo if ^($ausnahmen.Count -gt 0^) { Copy-Item -Path ^(Join-Path $quelle 'start.bat'^) -Destination "$env:TEMP\si_start_neu.bat" -Force }
        echo Remove-Item "$env:TEMP\si.zip","$env:TEMP\si-extract" -Recurse -Force
    )
    powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\si_download.ps1"
    if errorlevel 1 (
        del "%TEMP%\si_download.ps1" >nul 2>nul
        echo Fehler beim Herunterladen/Entpacken. Bitte Internetverbindung pruefen,
        echo oder das Repo manuell laden: https://github.com/CrazyJimPro/streaming-info
        pause
        exit /b 1
    )
    del "%TEMP%\si_download.ps1" >nul 2>nul

    if /I not "%cd%"=="%PROJEKT_ZIEL%" (
        echo Projekt liegt jetzt unter: %PROJEKT_ZIEL%
    ) else (
        echo Projekt aufgefrischt.
    )
    rem Eine noch laufende Instanz haelt den ALTEN Code im Speicher - die
    rem frisch heruntergeladenen Dateien wuerden erst beim naechsten Start
    rem wirksam. Deshalb hier sauber beenden, bevor neu gestartet wird.
    call :alte_instanz_beenden

    echo Starte neu ...
    echo.
    start "" cmd /c call "!NEUSTART_DATEI!"
    exit /b 0
)

rem --- 0.5 Welcher Stand laeuft hier? Steht auch in logs\start.log und
rem     oben in der Kopfzeile der Web-App. ---
if exist "%~dp0VERSION" (
    < "%~dp0VERSION" set /p SI_VERSION=
    echo Version: !SI_VERSION!
    echo.
)

rem --- 1. Python vorhanden? Sonst automatisch per winget installieren ---
rem Ein blosses "where python" reicht nicht: Windows legt standardmaessig
rem einen "python"-Platzhalter an, der nur auf den Microsoft Store verweist
rem und dabei erfolgreich gefunden wird, aber kein echtes Python ist. Daher
rem hier ein echter Funktionstest per Ausgabe-Pruefung.
set "PYTHON_EXE="
for /f "delims=" %%v in ('python -c "print(1)" 2^>nul') do if "%%v"=="1" set "PYTHON_EXE=python"
if not defined PYTHON_EXE (
    for /f "delims=" %%v in ('py -3 -c "print(1)" 2^>nul') do if "%%v"=="1" set "PYTHON_EXE=py -3"
)

if not defined PYTHON_EXE (
    echo Python wurde nicht gefunden ^(oder "python" ist nur der Microsoft-Store-Platzhalter^).
    echo Versuche automatische Installation per winget...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Fehler: winget ist nicht verfuegbar.
        echo Bitte Python manuell von https://www.python.org/downloads/ installieren
        echo und dieses Skript danach erneut starten.
        pause
        exit /b 1
    )
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo Python-Installation fehlgeschlagen. Bitte manuell installieren: https://www.python.org/downloads/
        pause
        exit /b 1
    )

    rem Frisch installiertes Python direkt am typischen Installationsort suchen,
    rem statt auf ein neues Terminal zu hoffen - der "python"-Befehl kann
    rem weiterhin auf den Microsoft-Store-Platzhalter zeigen, je nach PATH-Reihenfolge.
    for /d %%d in ("%LocalAppData%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_EXE=%%d\python.exe"
    )
    if not defined PYTHON_EXE (
        for /f "delims=" %%v in ('python -c "print(1)" 2^>nul') do if "%%v"=="1" set "PYTHON_EXE=python"
    )
    if not defined PYTHON_EXE (
        echo Python wurde installiert, konnte aber nicht automatisch gefunden werden.
        echo Bitte dieses Fenster schliessen, ein NEUES Terminal oeffnen und
        echo start.bat erneut starten ^(damit Windows den neuen PATH kennt^).
        pause
        exit /b 0
    )
    echo Python gefunden unter: %PYTHON_EXE%
)

rem --- 2. Virtuelle Umgebung + Abhaengigkeiten, falls noch nicht vorhanden ---
if not exist "venv\Scripts\python.exe" (
    echo Richte virtuelle Umgebung ein ^(einmalig, dauert etwas^)...
    %PYTHON_EXE% -m venv venv
    if errorlevel 1 (
        echo Fehler beim Anlegen der virtuellen Umgebung.
        pause
        exit /b 1
    )
    venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo Fehler beim Installieren der Abhaengigkeiten.
        pause
        exit /b 1
    )
)

rem --- 3. Desktop-Verknuepfung anlegen, falls noch nicht vorhanden - startet
rem     kuenftig per Doppelklick ohne sichtbares Konsolenfenster (siehe
rem     start_versteckt.bat/.vbs), Meldungen landen in logs\start.log.
rem
rem     Der Desktop-Ordner wird NICHT als "%USERPROFILE%\Desktop" geraten:
rem     ist der Desktop nach OneDrive umgeleitet (auf Windows 11 haeufig),
rem     gibt es diesen Ordner gar nicht.
rem     [Environment]::GetFolderPath^('Desktop'^) liefert immer den
rem     tatsaechlich benutzten Ordner; Erfolg wie Fehlschlag werden
rem     ausgegeben (und landen damit auch in logs\start.log). ---
> "%TEMP%\si_shortcut.ps1" (
    echo $ErrorActionPreference = 'Stop'
    echo try {
    echo     $desktop = [Environment]::GetFolderPath^('Desktop'^)
    echo     if ^(-not $desktop -or -not ^(Test-Path -LiteralPath $desktop^)^) { throw "Desktop-Ordner nicht gefunden (gemeldet: '$desktop')" }
    echo     $ziel = Join-Path $desktop 'Streaming-Info.lnk'
    echo     if ^(Test-Path -LiteralPath $ziel^) { Write-Host "Desktop-Verknuepfung vorhanden: $ziel"; exit 0 }
    echo     $WshShell = New-Object -ComObject WScript.Shell
    echo     $Shortcut = $WshShell.CreateShortcut^($ziel^)
    echo     $Shortcut.TargetPath = '%~dp0start_versteckt.vbs'
    echo     $Shortcut.WorkingDirectory = '%~dp0'
    echo     $Shortcut.Description = 'Streaming-Info starten'
    echo     $Shortcut.Save^(^)
    echo     Write-Host "Desktop-Verknuepfung angelegt: $ziel"
    echo } catch {
    echo     Write-Host "Desktop-Verknuepfung konnte nicht angelegt werden: $_"
    echo }
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\si_shortcut.ps1"
del "%TEMP%\si_shortcut.ps1" >nul 2>nul

rem --- 4. Web-App starten und Browser oeffnen (nur falls nicht schon eine
rem     laeuft - sonst Port-Konflikt, z.B. bei erneutem Klick auf die
rem     Desktop-Verknuepfung waehrend die App schon offen ist). Geprueft wird
rem     mit einem echten Verbindungsversuch, siehe :pruefe_port. ---
call :pruefe_port
if "!PORT_ANTWORTET!"=="JA" (
    echo Web-App laeuft bereits - stosse Aktualisierung an und oeffne Browser ...
    rem Auch beim Klick auf die Verknuepfung waehrend die App schon laeuft
    rem sollen frische Daten geholt werden. Der Aufruf kommt sofort zurueck,
    rem der Lauf selbst passiert im Hintergrund der App.
    rem Kein "| Out-Null" verwenden: das Pipe-Zeichen wird in einer
    rem Klammer-Gruppe von cmd.exe auch innerhalb der Anfuehrungszeichen
    rem zickig behandelt - Zuweisung an $null tut dasselbe ohne Pipe.
    powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -Method POST -Uri 'http://127.0.0.1:5100/aktualisieren' -TimeoutSec 10 } catch { }" >nul 2>nul
    powershell -NoProfile -Command "Start-Process 'http://127.0.0.1:5100'" >nul 2>nul
    exit /b 0
)

echo.
echo Oeffne http://127.0.0.1:5100 im Browser ...
echo Die Daten werden dabei im Hintergrund frisch geholt ^(2-5 Minuten^),
echo die Seite aktualisiert sich von selbst, sobald der Lauf fertig ist.
echo Dieses Fenster schliesst sich gleich von selbst, die App laeuft dann
echo ohne Fenster weiter. Zum Beenden den Knopf "Beenden" oben auf der Seite
echo benutzen - danach laeuft nichts mehr im Hintergrund.
echo.
rem Die App wird mit pythonw.exe gestartet: die hat gar kein Konsolenfenster,
rem dadurch kann dieses Fenster hier sofort zugehen, waehrend die App
rem weiterlaeuft. Ihre Meldungen schreibt sie nach logs\webapp.log.
rem
rem WICHTIG: Start ueber PowerShell statt ueber "start". Ein mit "start"
rem erzeugter Prozess erbt die Ausgabe-Handles dieses Fensters - also auch
rem logs\start.log, in das start_versteckt.bat umleitet. Die App hielte diese
rem Datei dann offen, solange sie laeuft; ein erneuter Klick auf die
rem Desktop-Verknuepfung scheiterte danach lautlos daran, dass sich das Log
rem nicht beschreiben laesst (es passierte dann einfach GAR nichts).
rem Start-Process gibt die Handles nicht weiter.
set "APP_EXE=%~dp0venv\Scripts\pythonw.exe"
if not exist "!APP_EXE!" set "APP_EXE=%~dp0venv\Scripts\python.exe"
> "%TEMP%\si_startapp.ps1" (
    echo $exe = '!APP_EXE!'
    echo $app = '"%~dp0webapp\app.py"'
    echo Start-Process -FilePath $exe -ArgumentList $app -WorkingDirectory '%~dp0'
    rem Browser erst oeffnen, wenn Port 5100 antwortet - sonst zeigt er kurz
    rem eine Fehlerseite.
    echo for ^($i = 0; $i -lt 30; $i++^) {
    echo     Start-Sleep -Milliseconds 500
    echo     $c = New-Object Net.Sockets.TcpClient
    echo     try { $c.Connect^('127.0.0.1',5100^); $c.Close^(^); break } catch { }
    echo }
    echo Start-Process 'http://127.0.0.1:5100'
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\si_startapp.ps1"
del "%TEMP%\si_startapp.ps1" >nul 2>nul
exit /b 0


rem ===================== Unterprogramme =====================

rem --- Vergleicht die lokale VERSION mit der auf GitHub. Unterprogramm statt
rem     Klammer-Block, weil "for /f" mit Pipe darin sonst am cmd.exe-Escaping
rem     in verschachtelten Bloecken scheitert. ---
:pruefe_version
set "SI_VERSION_LOKAL="
set "SI_VERSION_NEU="
if exist "%~dp0VERSION" for /f "usebackq delims=" %%v in ("%~dp0VERSION") do set "SI_VERSION_LOKAL=%%v"
del "%TEMP%\si_version_latest.txt" >nul 2>nul
rem Der angehaengte Zufallswert umgeht den Zwischenspeicher von GitHub -
rem sonst kommt hier minutenlang eine veraltete Versionsnummer an.
> "%TEMP%\si_versioncheck.ps1" (
    echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    echo try {
    echo     ^(New-Object System.Net.WebClient^).DownloadFile^('https://raw.githubusercontent.com/CrazyJimPro/streaming-info/main/VERSION?nocache=%RANDOM%%RANDOM%','%TEMP%\si_version_latest.txt'^)
    echo } catch { }
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\si_versioncheck.ps1"
del "%TEMP%\si_versioncheck.ps1" >nul 2>nul
if not exist "%TEMP%\si_version_latest.txt" (
    echo Versionspruefung fehlgeschlagen ^(kein Internet oder Netzwerk/Firewall blockiert^) - fahre mit der vorhandenen Version fort.
    goto :eof
)
for /f "usebackq delims=" %%v in ("%TEMP%\si_version_latest.txt") do set "SI_VERSION_NEU=%%v"
del "%TEMP%\si_version_latest.txt" >nul 2>nul
if not defined SI_VERSION_NEU goto :eof

if not defined SI_VERSION_LOKAL (
    echo Installierte Fassung ohne Versionsangabe - frische auf %SI_VERSION_NEU% auf.
    set "NEUERE_VERSION_GEFUNDEN=1"
    goto :eof
)

call :version_zu_zahl "%SI_VERSION_LOKAL%" SI_ZAHL_LOKAL
call :version_zu_zahl "%SI_VERSION_NEU%" SI_ZAHL_NEU
if not defined SI_ZAHL_LOKAL goto :eof
if not defined SI_ZAHL_NEU goto :eof
if %SI_ZAHL_NEU% GTR %SI_ZAHL_LOKAL% (
    echo Neue Version verfuegbar: %SI_VERSION_NEU% ^(installiert: %SI_VERSION_LOKAL%^)
    set "NEUERE_VERSION_GEFUNDEN=1"
)
goto :eof

rem --- Rechnet "1.4.7" in eine vergleichbare Zahl um. %1 = Version,
rem     %2 = Name der Zielvariablen. Bleibt leer, wenn die Angabe nicht dem
rem     Muster Zahl.Zahl.Zahl entspricht - dann wird lieber nicht
rem     aufgefrischt als auf Verdacht. ---
:version_zu_zahl
set "%~2="
set "SI_TEIL1="
set "SI_TEIL2="
set "SI_TEIL3="
for /f "tokens=1-3 delims=." %%a in ("%~1") do (
    set "SI_TEIL1=%%a"
    set "SI_TEIL2=%%b"
    set "SI_TEIL3=%%c"
)
if not defined SI_TEIL3 goto :eof
echo %SI_TEIL1%%SI_TEIL2%%SI_TEIL3%| findstr /r "^[0-9][0-9]*$" >nul 2>nul
if errorlevel 1 goto :eof
set /a "SI_ZAHL=%SI_TEIL1%*1000000+%SI_TEIL2%*1000+%SI_TEIL3%" >nul 2>nul
set "%~2=%SI_ZAHL%"
goto :eof

rem --- Beendet eine noch laufende Instanz. Erst hoeflich ueber /beenden,
rem     danach notfalls hart ueber die PID auf Port 5100. ---
:alte_instanz_beenden
call :pruefe_port
if not "%PORT_ANTWORTET%"=="JA" goto :eof
echo Beende die noch laufende Version ^(sonst liefe der alte Code weiter^)...
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -Method POST -Uri 'http://127.0.0.1:5100/beenden' -TimeoutSec 10 } catch { }" >nul 2>nul
ping -n 4 127.0.0.1 >nul
call :pruefe_port
if not "%PORT_ANTWORTET%"=="JA" goto :eof
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5100 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -match 'python') { Stop-Process -Id $p.Id -Force } }" >nul 2>nul
ping -n 3 127.0.0.1 >nul
goto :eof

rem --- Prueft mit einem echten Verbindungsversuch, ob auf Port 5100 eine App
rem     antwortet. Eine netstat-Textsuche waere unzuverlaessig: der
rem     Zustandstext ist sprachabhaengig, und es tauchen dort auch
rem     Verbindungsreste auf. ---
:pruefe_port
set "PORT_ANTWORTET="
for /f "delims=" %%r in ('powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',5100); 'JA' } catch { 'NEIN' } finally { $c.Close() }"') do set "PORT_ANTWORTET=%%r"
goto :eof
