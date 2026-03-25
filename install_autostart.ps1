# install_autostart.ps1
# Installs a shortcut in the Windows Startup folder so the StreamDeck app
# launches invisibly at login. Run once per computer.

$StartupPath = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupPath "StreamDeck.lnk"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = """$ScriptDir\run_streamdeck_invisible.vbs"""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.IconLocation = "$ScriptDir\app_icon.ico"
$Shortcut.Description = "StreamDeck Window Switcher (auto-start)"
$Shortcut.Save()

Write-Host "Autostart shortcut installed to: $ShortcutPath"
Write-Host "The StreamDeck app will now launch automatically at login."
