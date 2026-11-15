$ErrorActionPreference = 'Stop'
$scriptFile = Join-Path $PSScriptRoot 'flashbridge_gui.pyw'
$pythonWindowed = (Get-Command pythonw.exe -ErrorAction Stop).Source
# UAC elevation is required for raw disk handles; no registry or policy changes.
Start-Process -FilePath $pythonWindowed -ArgumentList ('"' + $scriptFile + '"') -WorkingDirectory $PSScriptRoot -Verb RunAs
