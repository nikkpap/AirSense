@echo off
chcp 65001 >nul
setlocal
title AirSense - install on Raspberry Pi
echo.
echo   AirSense - install on Raspberry Pi (Zero 2 W / 3 / 4 / 5)
echo   Nikolaos K. Paridis (aka nikkpap) - ALU DEV TEAM
echo.
echo   Needs: Raspberry Pi OS (Lite) made with Raspberry Pi Imager, SSH enabled, on your WiFi.
echo   Easier: ssh into the Pi and run the one-line command from ODIGIES_Raspberry_Pi.md
echo.
set APPF=
for %%F in ("%~dp0AirSense_v*.pyw") do set "APPF=%%~fF"
if not defined APPF (
  echo AirSense_vX.pyw was not found next to this file.
  pause & exit /b 1
)
where ssh >nul 2>nul || (
  echo OpenSSH is missing: Settings - Apps - Optional features - OpenSSH Client.
  pause & exit /b 1
)
set PIHOST=
set /p PIHOST=Pi name or IP [airsense.local]: 
if "%PIHOST%"=="" set PIHOST=airsense.local
set PIUSER=
set /p PIUSER=User (the one you set in Raspberry Pi Imager) [pi]: 
if "%PIUSER%"=="" set PIUSER=pi
echo.
echo [1/2] Copying files (the Pi password)...
ssh -o StrictHostKeyChecking=accept-new %PIUSER%@%PIHOST% "mkdir -p ~/AirSense-Pi"
if errorlevel 1 goto err
scp "%~dp0airsense-setup.sh" "%~dp0airsense-boot.sh" "%~dp0airsense" "%~dp0tailscale.sh" "%~dp0airsense-update.sh" "%~dp0post-update.sh" "%~dp0airsense-pwcheck.sh" "%~dp0airsense-password.sh" "%~dp0airsense-settings.txt" "%~dp0airsense_wifi.py" "%APPF%" %PIUSER%@%PIHOST%:AirSense-Pi/
if errorlevel 1 goto err
echo.
echo [2/2] Installing (password again, for sudo)...
ssh -t %PIUSER%@%PIHOST% "cd ~/AirSense-Pi && sed -i 's/\r$//' *.sh airsense airsense-settings.txt && sudo bash airsense-setup.sh"
echo.
echo Done! Open the address shown above on your phone (http://IP:8765).
pause
exit /b 0
:err
echo.
echo Could not connect. Check the name/IP, that the Pi has booted (1-2 minutes) and that SSH is enabled.
pause
exit /b 1
