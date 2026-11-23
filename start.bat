@echo off
rem Double-click to set up (first time) and open the job-hunt agent control panel.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
