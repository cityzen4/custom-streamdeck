$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\StreamDeck.lnk")
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = """c:\projects\streamdeck\run_streamdeck_invisible.vbs"""
$Shortcut.WorkingDirectory = "c:\projects\streamdeck"
$Shortcut.IconLocation = "c:\projects\streamdeck\app_icon.ico"
$Shortcut.Description = "Launch StreamDeck Window Switcher"
$Shortcut.Save()
Write-Host "Shortcut created on desktop: $DesktopPath\StreamDeck.lnk"
