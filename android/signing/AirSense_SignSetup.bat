@echo off
rem AirSense - APK signing setup (Nikolaos K. Paridis (aka nikkpap) - ALU DEV TEAM)
for %%F in ("%~dp0AirSense_SignSetup_v*.ps1") do set "PS1=%%~fF"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
