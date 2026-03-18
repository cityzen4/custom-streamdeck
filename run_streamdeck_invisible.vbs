Set WshShell = CreateObject("WScript.Shell")
' 0 ensures the window is completely hidden, False means don't wait for execution to finish
WshShell.Run """c:\projects\streamdeck\.venv\Scripts\pythonw.exe"" ""c:\projects\streamdeck\main.py""", 0, False
Set WshShell = Nothing
