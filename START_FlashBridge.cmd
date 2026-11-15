@echo off
cd /d "%~dp0"
%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_FlashBridge.ps1"
if errorlevel 1 (
  echo FlashBridge failed to start. Verify Python with Tkinter and UAC permissions.
  pause
)
