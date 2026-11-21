@echo off
chcp 65001 >nul
title ALU AirSense - Εγκατάσταση σε Raspberry Pi
echo.
echo   ==============================================
echo     ALU AirSense - Εγκατάσταση σε Raspberry Pi
echo     Nikolaos K. Paridis (aka nikkpap)
echo   ==============================================
echo.
set "HERE=%~dp0"
set "PYW="
for %%F in ("%HERE%ALU_AirSense_v*.pyw") do set "PYW=%%~fF"
if "%PYW%"=="" (
  echo [X] Δεν βρέθηκε ALU_AirSense_v*.pyw σε αυτόν τον φάκελο.
  pause & exit /b 1
)
where ssh >nul 2>nul || (
  echo [X] Λείπει το OpenSSH. Ρυθμίσεις - Εφαρμογές - Προαιρετικές δυνατότητες - OpenSSH Client.
  pause & exit /b 1
)
set "PIHOST="
set /p PIHOST=Όνομα ή IP του Raspberry Pi [airsense.local - παλιό Pi: hygrolink.local]: 
if "%PIHOST%"=="" set "PIHOST=airsense.local"
set "PIUSER="
set /p PIUSER=Χρήστης του Raspberry Pi [pi]: 
if "%PIUSER%"=="" set "PIUSER=pi"
echo.
echo [1/2] Αντιγραφή αρχείων στο %PIUSER%@%PIHOST% (θα ζητηθεί ο κωδικός του Pi)...
scp -o StrictHostKeyChecking=accept-new "%HERE%install_pi.sh" "%HERE%airsense_wifi.py" "%PYW%" %PIUSER%@%PIHOST%:~/
if errorlevel 1 goto err
echo.
echo [2/2] Εγκατάσταση (ξανά ο κωδικός του Pi, μετά απάντα στις ερωτήσεις)...
ssh -t -o StrictHostKeyChecking=accept-new %PIUSER%@%PIHOST% "mkdir -p ~/AirSense-Pi && mv -f ~/install_pi.sh ~/airsense_wifi.py ~/AirSense-Pi/ && cp -f ~/ALU_AirSense_v*.pyw ~/AirSense-Pi/ && sed -i 's/\r$//' ~/AirSense-Pi/install_pi.sh && bash ~/AirSense-Pi/install_pi.sh"
if errorlevel 1 goto err
echo.
echo [OK] Τέλος! Σκάναρε το QR που εμφανίστηκε με το κινητό.
pause
exit /b 0
:err
echo.
echo [X] Κάτι πήγε στραβά. Έλεγξε: είναι αναμμένο το Pi; σωστό όνομα/χρήστης; είναι ενεργό το SSH;
pause
exit /b 1
