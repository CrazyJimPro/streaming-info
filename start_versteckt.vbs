' Startet start_versteckt.bat ohne sichtbares Konsolenfenster (Fensterstil 0).
' Wird von der Desktop-Verknuepfung als Ziel verwendet - siehe start.bat,
' Schritt "Desktop-Verknuepfung anlegen".
'
' WScript.Shell.Run fuehrt .bat-Dateien nicht zuverlaessig direkt aus (die
' Windows-Dateizuordnung fuer .bat greift hier nicht immer) - deshalb wird
' explizit ueber cmd.exe /c aufgerufen.
Dim objShell, objFSO, scriptDir, anfuehrungszeichen, batPfad, befehl

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
anfuehrungszeichen = Chr(34)
batPfad = scriptDir & "\start_versteckt.bat"
befehl = "cmd.exe /c " & anfuehrungszeichen & batPfad & anfuehrungszeichen

objShell.Run befehl, 0, False
