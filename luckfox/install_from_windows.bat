@echo off
chcp 65001 >nul
setlocal
title AirSense - εγκατάσταση σε Luckfox Pico
echo.
echo   AirSense - εγκατάσταση σε Luckfox Pico (Ubuntu)
echo   Nikolaos K. Paridis (aka nikkpap) - ALU DEV TEAM
echo.
echo   Θέλει: Luckfox με φρέσκο Ubuntu στην κάρτα SD + καλώδιο Ethernet στο router.
echo   Χρήστης: pico   Κωδικός: luckfox
echo   Την IP τη βλέπεις στο router (συνδεδεμένες συσκευές) ή με την εφαρμογή Fing.
echo.
set APPF=
for %%F in ("%~dp0AirSense_v*.pyw") do set "APPF=%%~fF"
if not defined APPF (
  echo Δεν βρέθηκε το AirSense_vX.pyw δίπλα σε αυτό το αρχείο.
  pause & exit /b 1
)
set PIHOST=
set /p PIHOST=IP της πλακέτας (π.χ. 192.168.1.50): 
if "%PIHOST%"=="" goto err
set PIUSER=
set /p PIUSER=Χρήστης [pico]: 
if "%PIUSER%"=="" set PIUSER=pico
echo.
echo [1/2] Αντιγραφή αρχείων (θα ζητήσει τον κωδικό: luckfox)...
ssh -o StrictHostKeyChecking=accept-new %PIUSER%@%PIHOST% "mkdir -p ~/airsense-setup"
if errorlevel 1 goto err
scp "%~dp0airsense-setup.sh" "%~dp0airsense-boot.sh" "%~dp0airsense" "%~dp0tailscale.sh" "%~dp0airsense-settings.txt" "%APPF%" %PIUSER%@%PIHOST%:airsense-setup/
if errorlevel 1 goto err
echo.
echo [2/2] Εγκατάσταση (ξανά ο κωδικός, για sudo)...
ssh -t %PIUSER%@%PIHOST% "cd ~/airsense-setup && sed -i 's/\r$//' airsense-setup.sh airsense-boot.sh airsense tailscale.sh airsense-settings.txt && sudo bash airsense-setup.sh"
echo.
echo Τελείωσε! Άνοιξε στο κινητό τη διεύθυνση που φαίνεται παραπάνω (http://IP:8765).
pause
exit /b 0
:err
echo.
echo Δεν συνδέθηκε. Έλεγξε την IP, το καλώδιο Ethernet και ότι η πλακέτα έχει ξεκινήσει (1-2 λεπτά).
pause
exit /b 1
