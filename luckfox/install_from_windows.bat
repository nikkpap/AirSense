@echo off
chcp 65001 >nul
setlocal
title AirSense - install on Luckfox Pico
echo.
echo   AirSense - install on Luckfox Pico (Ubuntu)
echo   Nikolaos K. Paridis (aka nikkpap) - ALU DEV TEAM
echo.
echo   Needs: Luckfox with a fresh Ubuntu on the SD card + Ethernet cable to the router.
echo   User: pico   Password: luckfox
echo   Find the IP in your router (connected devices) or with the Fing app.
echo.
set APPF=
for %%F in ("%~dp0AirSense_v*.pyw") do set "APPF=%%~fF"
if not defined APPF (
  echo AirSense_vX.pyw was not found next to this file.
  pause & exit /b 1
)
set PIHOST=
set /p PIHOST=Board IP (e.g. 192.168.1.50):
if "%PIHOST%"=="" goto err
set PIUSER=
set /p PIUSER=User [pico]:
if "%PIUSER%"=="" set PIUSER=pico
echo.
echo [1/2] Copying files (password: luckfox)...
ssh -o StrictHostKeyChecking=accept-new %PIUSER%@%PIHOST% "mkdir -p ~/airsense-setup"
if errorlevel 1 goto err
scp "%~dp0airsense-setup.sh" "%~dp0airsense-boot.sh" "%~dp0airsense" "%~dp0tailscale.sh" "%~dp0airsense-update.sh" "%~dp0post-update.sh" "%~dp0airsense-pwcheck.sh" "%~dp0airsense-password.sh" "%~dp0airsense-settings.txt" "%APPF%" %PIUSER%@%PIHOST%:airsense-setup/
if errorlevel 1 goto err
echo.
echo [2/2] Installing (password again, for sudo)...
ssh -t %PIUSER%@%PIHOST% "cd ~/airsense-setup && sed -i 's/\r$//' *.sh airsense airsense-settings.txt && sudo bash airsense-setup.sh"
echo.
echo Done! Open the address shown above on your phone (http://IP:8765).
pause
exit /b 0
:err
echo.
echo Could not connect. Check the IP, the Ethernet cable and that the board has finished booting (1-2 minutes).
pause
exit /b 1
